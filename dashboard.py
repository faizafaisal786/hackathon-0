"""
AI Employee Monitoring Dashboard
==================================
Terminal-based live dashboard showing pipeline status, channel stats,
recent activity, and system health at a glance.

Modes:
  python dashboard.py              # Show once and exit
  python dashboard.py --live       # Auto-refresh every 5 seconds
  python dashboard.py --live 10    # Auto-refresh every 10 seconds

Reads from:
  - AI_Employee_Vault/ folders (pipeline counts)
  - AI_Employee_Vault/Logs/*.json (event history + channel stats)
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from collections import Counter


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

BASE = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"
LOGS_DIR = VAULT / "Logs"

PIPELINE = [
    ("Inbox", VAULT / "Inbox"),
    ("Needs_Action", VAULT / "Needs_Action"),
    ("Plans", VAULT / "Plans"),
    ("Pending_Approval", VAULT / "Pending_Approval"),
    ("Approved", VAULT / "Approved"),
    ("Rejected", VAULT / "Rejected"),
    ("Done", VAULT / "Done"),
]


# ──────────────────────────────────────────────
# DATA COLLECTION
# ──────────────────────────────────────────────

def count_files(folder: Path) -> list[str]:
    """List task file names in a folder."""
    if not folder.exists():
        return []
    return sorted([
        f.name for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in (".md", ".txt")
    ])


def get_pipeline_data() -> list[tuple[str, int, list[str]]]:
    """Get (name, count, filenames) for each pipeline stage."""
    data = []
    for name, folder in PIPELINE:
        files = count_files(folder)
        data.append((name, len(files), files))
    return data


def get_today_log() -> list[dict]:
    """Read today's main audit log (v2.0 format)."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{today}.json"
    if not log_file.exists():
        return []
    try:
        raw = json.loads(log_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "events" in raw:
            return raw["events"]
        if isinstance(raw, list):
            return raw
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    return []


def get_channel_log(channel: str) -> list[dict]:
    """Read today's channel-specific log (email/whatsapp)."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{channel}_{today}.json"
    if not log_file.exists():
        return []
    try:
        return json.loads(log_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []


def get_all_log_stats() -> dict:
    """Aggregate stats from all of today's log sources."""
    events = get_today_log()
    email_log = get_channel_log("email")
    wa_log = get_channel_log("whatsapp")

    total = len(events) + len(email_log) + len(wa_log)
    errors = 0
    channels = Counter()

    # Main audit log
    for ev in events:
        if ev.get("result") in ("FAILED", "BLOCKED") or ev.get("severity") == "ERROR":
            errors += 1
        ch = ""
        if isinstance(ev, dict):
            ch = (ev.get("metadata") or {}).get("channel", "") or ev.get("channel", "")
        if ch:
            channels[ch] += 1

    # Channel logs
    for entry in email_log:
        channels["Email"] += 1
        if "error" in entry.get("event", "").lower() or "fail" in entry.get("details", "").lower():
            errors += 1
    for entry in wa_log:
        channels["WhatsApp"] += 1
        if "error" in entry.get("event", "").lower() or "fail" in entry.get("details", "").lower():
            errors += 1

    return {
        "total": total,
        "errors": errors,
        "channels": channels,
    }


def get_last_events(n: int = 5) -> list[dict]:
    """Get the N most recent events from today's log."""
    events = get_today_log()
    return events[-n:] if events else []


# ──────────────────────────────────────────────
# DISPLAY HELPERS
# ──────────────────────────────────────────────

def _bar(value: int, max_val: int, width: int = 20) -> str:
    """Render a horizontal bar: [########............]"""
    if max_val == 0:
        return "[" + "." * width + "]"
    filled = min(int((value / max_val) * width), width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def _status_icon(count: int) -> str:
    """Return a text status indicator."""
    if count == 0:
        return "  OK "
    return " >>> "


def _truncate(text: str, length: int) -> str:
    """Truncate text to length with ellipsis."""
    if len(text) <= length:
        return text
    return text[:length - 3] + "..."


def _clear_screen():
    """Clear terminal screen (cross-platform)."""
    os.system("cls" if os.name == "nt" else "clear")


# ──────────────────────────────────────────────
# RENDER DASHBOARD
# ──────────────────────────────────────────────

def render() -> str:
    """Build the full dashboard as a string."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %I:%M:%S %p")

    pipeline = get_pipeline_data()
    log_stats = get_all_log_stats()
    last_events = get_last_events(5)

    # Totals
    total_files = sum(count for _, count, _ in pipeline)
    done_count = next((c for n, c, _ in pipeline if n == "Done"), 0)
    pending_count = next((c for n, c, _ in pipeline if n == "Pending_Approval"), 0)
    needs_count = next((c for n, c, _ in pipeline if n == "Needs_Action"), 0)
    approved_count = next((c for n, c, _ in pipeline if n == "Approved"), 0)
    inbox_count = next((c for n, c, _ in pipeline if n == "Inbox"), 0)
    active_work = inbox_count + needs_count + pending_count + approved_count

    # Header
    lines = []
    lines.append("")
    lines.append("  ================================================")
    lines.append("   AI EMPLOYEE DASHBOARD            v2.0")
    lines.append(f"   {timestamp}")
    lines.append("  ================================================")
    lines.append("")

    # ── Summary Cards ──
    lines.append("  +------------+  +------------+  +------------+")
    lines.append(f"  | TOTAL  {total_files:3d} |  | DONE   {done_count:3d} |  | ACTIVE {active_work:3d} |")
    lines.append("  +------------+  +------------+  +------------+")
    lines.append(f"  | PENDING {pending_count:2d} |  | NEEDS  {needs_count:3d} |  | ERRORS {log_stats['errors']:3d} |")
    lines.append("  +------------+  +------------+  +------------+")
    lines.append("")

    # ── Pipeline ──
    lines.append("  PIPELINE")
    lines.append("  " + "-" * 56)

    max_count = max((c for _, c, _ in pipeline), default=1)
    for name, count, files in pipeline:
        icon = _status_icon(count)
        bar = _bar(count, max_count, 16)
        lines.append(f"  {icon} {name:20s} {count:4d}  {bar}")

        # Show file names for non-Done folders with items
        if count > 0 and name != "Done":
            for fname in files[:3]:
                lines.append(f"         {_truncate(fname, 40)}")
            if count > 3:
                lines.append(f"         ... +{count - 3} more")

    lines.append("  " + "-" * 56)
    lines.append("")

    # ── Channel Stats ──
    lines.append("  CHANNELS TODAY")
    lines.append("  " + "-" * 40)

    ch_total = sum(log_stats["channels"].values()) or 1
    for ch_name in ["Email", "WhatsApp", "LinkedIn"]:
        ch_count = log_stats["channels"].get(ch_name, 0)
        pct = (ch_count / ch_total) * 100 if ch_count else 0
        bar = _bar(ch_count, ch_total, 12)
        status = "ACTIVE" if ch_count > 0 else "  --  "
        lines.append(f"    {ch_name:12s}  {ch_count:3d}  {pct:5.1f}%  {bar}  {status}")

    lines.append("  " + "-" * 40)
    lines.append(f"    Events today: {log_stats['total']}")
    lines.append("")

    # ── Last Actions ──
    lines.append("  RECENT ACTIVITY")
    lines.append("  " + "-" * 56)

    if last_events:
        for ev in last_events:
            # Handle both v1.0 and v2.0 event formats
            if "action" in ev and "details" in ev:
                # v2.0
                ts = ev.get("timestamp", "")
                if "T" in ts:
                    ts = ts.split("T")[1][:8]
                action = ev.get("action", "")
                detail = ev.get("details", "")
                severity = ev.get("severity", "INFO")
                tag = "!!" if severity == "ERROR" else "  "
            else:
                # v1.0
                ts = ev.get("time", "")
                action = ev.get("task", "")
                detail = ev.get("status", "")
                tag = "  "

            line = f"    {tag} {ts:>8s}  {_truncate(action, 18):18s}  {_truncate(detail, 24)}"
            lines.append(line)
    else:
        lines.append("    (no events today)")

    lines.append("  " + "-" * 56)
    lines.append("")

    # ── Alerts ──
    pending_files = next((f for n, _, f in pipeline if n == "Pending_Approval"), [])
    needs_files = next((f for n, _, f in pipeline if n == "Needs_Action"), [])

    if pending_files or needs_files:
        lines.append("  ALERTS")
        lines.append("  " + "-" * 40)
        if pending_files:
            lines.append(f"    [!] {len(pending_files)} task(s) awaiting YOUR approval")
            for f in pending_files[:3]:
                lines.append(f"        -> {f}")
        if needs_files:
            lines.append(f"    [!] {len(needs_files)} task(s) need processing")
            for f in needs_files[:3]:
                lines.append(f"        -> {f}")
        lines.append("  " + "-" * 40)
    else:
        lines.append("  STATUS: Pipeline clear. No action needed.")

    lines.append("")
    lines.append("  ================================================")
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--live" in args:
        # Live refresh mode
        idx = args.index("--live")
        interval = 5
        if idx + 1 < len(args):
            try:
                interval = int(args[idx + 1])
            except ValueError:
                pass

        print(f"  Live mode: refreshing every {interval}s  (Ctrl+C to stop)")
        time.sleep(1)

        try:
            while True:
                _clear_screen()
                print(render())
                print(f"  [Live: refreshing in {interval}s | Ctrl+C to exit]")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n  Dashboard stopped.")

    else:
        # Single render
        print(render())


if __name__ == "__main__":
    main()
