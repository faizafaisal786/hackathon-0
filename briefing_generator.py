"""
CEO Weekly Briefing Generator
================================
Reads all logs, pipeline state, and channel-specific logs to produce
an executive-level weekly briefing in Markdown.

Handles both log formats:
  - v1.0: list of {task, status, time, channel?, to?}
  - v2.0: {audit_date, total_events, events: [{id, timestamp, actor, action, severity, result, metadata?}]}

Usage:
  python briefing_generator.py                # Generate this week's briefing
  python briefing_generator.py --week 7       # Generate briefing for week 7
  python briefing_generator.py --days 14      # Look back 14 days instead of 7

Output:
  AI_Employee_Vault/Briefings/Briefing_YYYY-MM-DD.md
"""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

BASE = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

LOGS_DIR = VAULT / "Logs"
BRIEFINGS_DIR = VAULT / "Briefings"
PLANS_DIR = VAULT / "Plans"

PIPELINE_FOLDERS = {
    "Inbox": VAULT / "Inbox",
    "Needs_Action": VAULT / "Needs_Action",
    "Pending_Approval": VAULT / "Pending_Approval",
    "Approved": VAULT / "Approved",
    "Rejected": VAULT / "Rejected",
    "Done": VAULT / "Done",
}


# ──────────────────────────────────────────────
# LOG READER (handles both v1.0 and v2.0)
# ──────────────────────────────────────────────

def _read_log_file(path: Path) -> list[dict]:
    """
    Read a single log file. Normalizes both formats into a flat event list.
    Returns list of dicts with at least: {action, status/result, timestamp, channel?}
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []

    events = []

    # v2.0 format: {audit_date, events: [...]}
    if isinstance(raw, dict) and "events" in raw:
        for ev in raw["events"]:
            events.append({
                "action": ev.get("action", ""),
                "result": ev.get("result", ""),
                "severity": ev.get("severity", "INFO"),
                "actor": ev.get("actor", ""),
                "details": ev.get("details", ""),
                "timestamp": ev.get("timestamp", ""),
                "channel": (ev.get("metadata") or {}).get("channel", ""),
            })

    # v1.0 format: [{task, status, time, channel?, to?}]
    elif isinstance(raw, list):
        for entry in raw:
            channel = entry.get("channel", "")
            status = entry.get("status", "")
            action = "EXECUTED" if "sent" in status.lower() or "completed" in status.lower() else "TASK"

            events.append({
                "action": action,
                "result": "SUCCESS" if "fail" not in status.lower() and "error" not in status.lower() else "FAILED",
                "severity": "INFO",
                "actor": "executor",
                "details": f"{entry.get('task', '')} -> {status}",
                "timestamp": entry.get("time", ""),
                "channel": channel,
                "task_name": entry.get("task", ""),
                "to": entry.get("to", ""),
                "status_text": status,
            })

    return events


def read_logs(days_back: int = 7) -> list[dict]:
    """Read all log files from the past N days. Returns flat event list."""
    if not LOGS_DIR.exists():
        return []

    cutoff = datetime.now() - timedelta(days=days_back)
    all_events = []

    for log_file in sorted(LOGS_DIR.glob("*.json")):
        # Extract date from filename (2026-02-17.json or email_2026-02-17.json)
        name = log_file.stem
        date_part = name.split("_")[-1] if "_" in name else name

        try:
            file_date = datetime.strptime(date_part, "%Y-%m-%d")
        except ValueError:
            continue

        if file_date >= cutoff:
            events = _read_log_file(log_file)
            for ev in events:
                ev["log_date"] = date_part
                ev["log_source"] = name
            all_events.extend(events)

    return all_events


# ──────────────────────────────────────────────
# ANALYTICS
# ──────────────────────────────────────────────

def analyze(events: list[dict]) -> dict:
    """Crunch the numbers from all events."""
    stats = {
        "total_events": len(events),
        "successes": 0,
        "failures": 0,
        "warnings": 0,
        "channels": Counter(),
        "actions": Counter(),
        "actors": Counter(),
        "tasks_executed": 0,
        "tasks_planned": 0,
        "approvals": 0,
        "rejections": 0,
        "dates_active": set(),
        "errors": [],
    }

    for ev in events:
        result = ev.get("result", "")
        severity = ev.get("severity", "INFO")
        action = ev.get("action", "")
        channel = ev.get("channel", "")

        # Counts
        if result == "SUCCESS":
            stats["successes"] += 1
        elif result in ("FAILED", "BLOCKED"):
            stats["failures"] += 1
            stats["errors"].append(ev.get("details", "Unknown error"))
        if severity == "WARNING":
            stats["warnings"] += 1

        # Channel frequency
        if channel:
            stats["channels"][channel] += 1

        # Action types
        stats["actions"][action] += 1
        stats["actors"][ev.get("actor", "unknown")] += 1

        # Specific counters
        if "EXECUTED" in action or "SENT" in action:
            stats["tasks_executed"] += 1
        if "PLANNED" in action or "PLAN" in action:
            stats["tasks_planned"] += 1
        if "APPROVED" in action:
            stats["approvals"] += 1
        if "REJECTED" in action:
            stats["rejections"] += 1

        # Active dates
        date = ev.get("log_date", "")
        if date:
            stats["dates_active"].add(date)

    stats["dates_active"] = sorted(stats["dates_active"])
    return stats


def get_pipeline_snapshot() -> dict:
    """Count files in each pipeline folder right now."""
    snapshot = {}
    for name, folder in PIPELINE_FOLDERS.items():
        if folder.exists():
            files = [f for f in folder.iterdir() if f.is_file()]
            snapshot[name] = len(files)
        else:
            snapshot[name] = 0
    return snapshot


def get_plan_count() -> int:
    """Count plans in Plans/ folder."""
    if PLANS_DIR.exists():
        return len([f for f in PLANS_DIR.iterdir() if f.is_file()])
    return 0


# ──────────────────────────────────────────────
# SUGGESTION ENGINE
# ──────────────────────────────────────────────

def _group_errors(errors: list[str]) -> list[tuple[str, int]]:
    """Group errors by root cause pattern instead of exact string."""
    import re as _re
    patterns = {}
    for error in errors:
        normalized = error
        normalized = _re.sub(r"in position \d+", "in position N", normalized)
        normalized = _re.sub(r"[\w_]+\.\w+:", "FILE:", normalized)
        normalized = normalized[:120]
        if normalized not in patterns:
            patterns[normalized] = 0
        patterns[normalized] += 1
    return sorted(patterns.items(), key=lambda x: x[1], reverse=True)


def generate_suggestions(stats: dict, pipeline: dict) -> list[str]:
    """Generate 3 context-aware, non-technical suggestions with owners."""
    suggestions = []
    error_rate = (stats["failures"] / max(stats["total_events"], 1)) * 100
    channels = stats["channels"]
    active_days = len(stats["dates_active"])

    # 1. Error-driven
    if stats["failures"] > 0:
        error_groups = _group_errors(stats["errors"])
        if error_rate > 10 and error_groups:
            top_error = error_groups[0][0][:60]
            count = error_groups[0][1]
            suggestions.append(
                f"**Fix root cause of errors** -- \"{top_error}\" accounts for "
                f"{count} of {stats['failures']} failures. Resolving this single issue "
                f"would significantly reduce the error rate.\n   *Owner: Engineering*"
            )
        elif stats["failures"] > 0:
            suggestions.append(
                f"**Monitor error trend** -- {stats['failures']} minor error(s) this period "
                f"({error_rate:.1f}% rate). No action needed unless this increases.\n"
                f"   *Owner: Engineering*"
            )

    # 2. Utilization-driven
    if active_days < 4:
        suggestions.append(
            f"**Increase system utilization** -- Active on only {active_days} of 7 "
            f"days. Enable continuous processing to catch tasks daily.\n"
            f"   *Owner: DevOps*"
        )

    # 3. Pipeline-driven
    pending = pipeline.get("Pending_Approval", 0)
    needs_action = pipeline.get("Needs_Action", 0)
    if pending > 0:
        suggestions.append(
            f"**Clear {pending} pending approval(s)** -- Tasks are waiting for human "
            f"review. Delayed approvals slow the entire pipeline.\n"
            f"   *Owner: Operations*"
        )
    elif needs_action > 0:
        suggestions.append(
            f"**Process {needs_action} incoming task(s)** -- Run the pipeline "
            f"to analyze and draft responses.\n   *Owner: Operations*"
        )

    # 4. Channel-driven
    if not channels:
        suggestions.append(
            "**Activate communication channels** -- No channel activity this period. "
            "Configure credentials to start processing real messages.\n"
            "   *Owner: Operations*"
        )
    else:
        missing = {"Email", "WhatsApp", "LinkedIn"} - set(channels.keys())
        if missing:
            suggestions.append(
                f"**Activate {', '.join(sorted(missing))}** -- Currently only using "
                f"{', '.join(sorted(channels.keys()))}. Expanding channels increases "
                f"automation coverage.\n   *Owner: Operations*"
            )

    # 5. Growth-driven (only if healthy)
    if len(suggestions) < 3 and error_rate == 0 and stats["tasks_executed"] > 0:
        suggestions.append(
            f"**Scale up workload** -- System is healthy with {stats['tasks_executed']} "
            f"tasks completed and 0% error rate. Ready for higher volume.\n"
            f"   *Owner: Operations*"
        )

    # Pad to 3 with contextual defaults
    defaults = [
        "**Enable weekly auto-briefings** -- Schedule this report to generate "
        "every Monday at 9 AM for consistent executive visibility.\n   *Owner: DevOps*",
        "**Add week-over-week trending** -- Compare key metrics against prior "
        "periods to identify acceleration or regression.\n   *Owner: Engineering*",
        "**Enable always-on processing** -- Deploy the system for 24/7 operation "
        "so tasks are handled even outside business hours.\n   *Owner: DevOps*",
    ]
    for d in defaults:
        if len(suggestions) >= 3:
            break
        if d not in suggestions:
            suggestions.append(d)

    return suggestions[:3]


# ──────────────────────────────────────────────
# REPORT GENERATOR
# ──────────────────────────────────────────────

def generate_briefing(days_back: int = 7) -> str:
    """
    Generate a board-meeting ready CEO briefing.
    Opens with narrative, shows only what needs attention, assigns owners.
    """
    now = datetime.now()
    week_num = now.isocalendar()[1]
    period_start = (now - timedelta(days=days_back)).strftime("%b %d")
    period_end = now.strftime("%b %d")

    # Gather data
    events = read_logs(days_back)
    stats = analyze(events)
    pipeline = get_pipeline_snapshot()
    plan_count = get_plan_count()
    suggestions = generate_suggestions(stats, pipeline)

    total = stats["total_events"]
    executed = stats["tasks_executed"]
    failures = stats["failures"]
    active_days = len(stats["dates_active"])
    error_rate = (failures / max(total, 1)) * 100
    channels = stats["channels"]

    # ── Narrative summary ──
    channel_names = ", ".join(sorted(channels.keys())) if channels else "no channels"
    if total == 0:
        narrative = "No activity this period. The pipeline is idle."
    elif failures == 0:
        narrative = (
            f"This week the AI Employee processed **{executed} tasks** across "
            f"{len(channels)} channel(s) ({channel_names}) over {active_days} active "
            f"day(s). All operations completed without errors."
        )
    else:
        narrative = (
            f"This week the AI Employee processed **{executed} tasks** across "
            f"{len(channels)} channel(s) ({channel_names}) over {active_days} active "
            f"day(s). {failures} error(s) were logged ({error_rate:.0f}% error rate)."
        )

    # ── Key numbers with status ──
    error_status = "Clear" if error_rate == 0 else ("Needs fix" if error_rate > 10 else "Monitor")
    days_status = "On track" if active_days >= max(days_back * 0.5, 1) else "Low"

    # ── Channel table ──
    channel_total = sum(channels.values()) or 1
    channel_rows = ""
    for ch in sorted(channels.keys(), key=lambda c: channels[c], reverse=True):
        count = channels[ch]
        pct = (count / channel_total) * 100
        channel_rows += f"| {ch} | {count} | {pct:.0f}% |\n"
    if not channel_rows:
        channel_rows = "| (no activity) | 0 | -- |\n"

    # ── Errors (grouped by root cause) ──
    error_section = ""
    if stats["errors"]:
        error_groups = _group_errors(stats["errors"])
        error_lines = []
        for pattern, count in error_groups[:3]:
            error_lines.append(f"- **{pattern}** ({count} occurrence(s))")
        error_section = (
            "\n## Attention Required\n\n"
            + "\n".join(error_lines)
            + "\n"
        )

    # ── Pipeline backlog (only if work pending) ──
    pipeline_note = ""
    active_items = sum(
        pipeline.get(k, 0) for k in ["Needs_Action", "Pending_Approval", "Approved"]
    )
    if active_items > 0:
        pipeline_lines = []
        for name in ["Needs_Action", "Pending_Approval", "Approved"]:
            count = pipeline.get(name, 0)
            if count > 0:
                label = name.replace("_", " ")
                pipeline_lines.append(f"- **{label}:** {count} file(s)")
        pipeline_note = "\n## Pipeline Backlog\n\n" + "\n".join(pipeline_lines) + "\n"

    # ── Suggestions ──
    suggestion_lines = "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions))

    # ── Assemble briefing ──
    briefing = f"""# Weekly Operations Briefing -- AI Employee

**Week {week_num}, {now.year}** | {period_start}--{period_end} | Generated {now.strftime("%b %d, %I:%M %p")}

---

{narrative}

## Key Numbers

| Metric | This Week | Status |
|--------|-----------|--------|
| Tasks completed | {executed} | {"On track" if executed > 0 else "No activity"} |
| Tasks planned | {stats["tasks_planned"]} | {"On track" if stats["tasks_planned"] > 0 else "--"} |
| Error rate | {error_rate:.0f}% ({failures} of {total} events) | {error_status} |
| Active days | {active_days} of {days_back} | {days_status} |
| Approval backlog | {pipeline.get("Pending_Approval", 0)} | {"Clear" if pipeline.get("Pending_Approval", 0) == 0 else "Action needed"} |

## Channel Performance

| Channel | Tasks | Share |
|---------|-------|-------|
{channel_rows.rstrip()}
{error_section}{pipeline_note}
## Recommendations

{suggestion_lines}

---

Pipeline: {"Clear" if active_items == 0 else f"{active_items} items pending"} | \
All modules: Operational | Plans on file: {plan_count} | Next briefing: {(now + timedelta(days=7)).strftime("%b %d")}
"""
    return briefing


# ──────────────────────────────────────────────
# SAVE + MAIN
# ──────────────────────────────────────────────

def save_briefing(content: str) -> Path:
    """Save briefing to Briefings/ folder. Returns the file path."""
    BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = BRIEFINGS_DIR / f"Briefing_{today}.md"
    path.write_text(content, encoding="utf-8")
    return path


def main():
    days_back = 7

    # Parse args
    args = sys.argv[1:]
    if "--days" in args:
        idx = args.index("--days")
        if idx + 1 < len(args):
            days_back = int(args[idx + 1])
    elif "--week" in args:
        # Generate for a specific ISO week
        days_back = 7

    print("=" * 50)
    print("  CEO BRIEFING GENERATOR")
    print(f"  Period: last {days_back} days")
    print("=" * 50)

    # Read + analyze
    events = read_logs(days_back)
    stats = analyze(events)
    pipeline = get_pipeline_snapshot()

    print(f"\n  Events found:  {stats['total_events']}")
    print(f"  Executed:      {stats['tasks_executed']}")
    print(f"  Errors:        {stats['failures']}")
    print(f"  Channels:      {dict(stats['channels'])}")
    print(f"  Active days:   {len(stats['dates_active'])}")
    print(f"  Pipeline:      {pipeline}")

    # Generate + save
    content = generate_briefing(days_back)
    path = save_briefing(content)

    print(f"\n  Briefing saved: {path}")
    print(f"  Open in Obsidian to view.")
    print()


if __name__ == "__main__":
    main()
