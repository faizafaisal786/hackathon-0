"""
RALPH WIGGUM LOOP v3.0 -- PLATINUM Tier Autonomous AI Employee
==============================================================
Fully autonomous, self-healing, self-improving AI pipeline.

What's new in v3.0 (PLATINUM over GOLD):
  1. MEMORY           -- every task writes to memory, AI reads past context
  2. SELF-IMPROVEMENT -- every N passes, prompts are auto-improved from outcomes
  3. MULTI-AGENT      -- THINKER->PLANNER->EXECUTOR->REVIEWER with revision loop
  4. SELF-HEALING     -- per-task failure tracking + quarantine after 3 failures
  5. MEMORY OUTCOMES  -- executed/rejected tasks feed back into memory quality
  6. PLATINUM DASHBOARD -- quality scores, memory stats, improvement history

Pipeline per pass:
  Inbox -> Needs_Action -> PLATINUM AI (4-agent) -> [Auto/Manual Approve]
       -> Execute -> Done (+memory outcome update)

Config: AI_Employee/config.py
  AUTO_APPROVE          = True      -> fully autonomous
  ENABLE_PLATINUM       = True      -> 4-agent pipeline
  ENABLE_MEMORY         = True      -> persistent context
  ENABLE_SELF_IMPROVEMENT = True    -> auto-improve prompts
  IMPROVEMENT_INTERVAL  = 10        -> improve every 10 passes
  MAX_TASK_FAILURES     = 3         -> quarantine after 3 failures
  LOOP_INTERVAL         = 60        -> seconds between passes

Usage:
  python ralph_loop.py          # start infinite loop
  python ralph_loop.py --once   # single pass (for testing)

"Me fail? That's unpossible!" -- Ralph Wiggum
"""

import sys
import time
import json
import shutil
import os
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent
AI_DIR = ROOT / "AI_Employee"
VAULT  = AI_DIR / "AI_Employee_Vault"

sys.path.insert(0, str(AI_DIR))

# ── Config (with safe defaults if config.py missing) ──────────────────────────
try:
    from config import (
        AUTO_APPROVE,
        LOOP_INTERVAL,
        MULTISTEP_AI,
        ENABLE_PLATINUM,
        ENABLE_MEMORY,
        ENABLE_SELF_IMPROVEMENT,
        IMPROVEMENT_INTERVAL,
        MAX_TASK_FAILURES,
    )
except ImportError:
    AUTO_APPROVE             = False
    LOOP_INTERVAL            = 60
    MULTISTEP_AI             = True
    ENABLE_PLATINUM          = True
    ENABLE_MEMORY            = True
    ENABLE_SELF_IMPROVEMENT  = True
    IMPROVEMENT_INTERVAL     = 10
    MAX_TASK_FAILURES        = 3

# ── Folders ────────────────────────────────────────────────────────────────────
FOLDERS = {
    "inbox":      VAULT / "Inbox",
    "needs":      VAULT / "Needs_Action",
    "pending":    VAULT / "Pending_Approval",
    "approved":   VAULT / "Approved",
    "rejected":   VAULT / "Rejected",
    "done":       VAULT / "Done",
    "logs":       VAULT / "Logs",
    "plans":      VAULT / "Plans",
    "quarantine": VAULT / "Quarantine",
}

# ── Self-healing: per-task failure tracking ─────────────────────────────────────
FAILURES_FILE = AI_DIR / "memory" / "failures.json"
_pass_count   = 0


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOGGER
# ══════════════════════════════════════════════════════════════════════════════

def log_event(
    action: str,
    actor: str,
    details: str,
    severity: str = "INFO",
    result: str = "SUCCESS",
    metadata: dict = None,
):
    """Append one event to today's JSON audit log."""
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = FOLDERS["logs"] / f"{today}.json"

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        data = raw if isinstance(raw, dict) else {
            "audit_date": today, "system": "AI Employee",
            "version": "2.0", "total_events": len(raw), "events": raw,
        }
    else:
        data = {
            "audit_date":   today,
            "system":       "AI Employee Platinum",
            "version":      "3.0",
            "total_events": 0,
            "events":       [],
        }

    data["total_events"] = data.get("total_events", 0) + 1
    event = {
        "id":        f"EVT-{data['total_events']:04d}",
        "timestamp": datetime.now().isoformat(),
        "actor":     actor,
        "action":    action,
        "details":   details,
        "severity":  severity,
        "result":    result,
    }
    if metadata:
        event["metadata"] = metadata
    data["events"].append(event)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════════════════════
# SELF-HEALING: FAILURE TRACKER
# ══════════════════════════════════════════════════════════════════════════════

def _get_failures() -> dict:
    """Load task failure counts from disk."""
    FAILURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if FAILURES_FILE.exists():
        try:
            with open(FAILURES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_failures(failures: dict):
    """Persist task failure counts to disk."""
    FAILURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FAILURES_FILE, "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)


def _increment_failure(task_name: str) -> int:
    """Increment failure count for a task. Returns new count."""
    failures               = _get_failures()
    failures[task_name]    = failures.get(task_name, 0) + 1
    _save_failures(failures)
    return failures[task_name]


def _clear_failure(task_name: str):
    """Clear failure count for a successfully processed task."""
    failures = _get_failures()
    if task_name in failures:
        del failures[task_name]
        _save_failures(failures)


def _quarantine_task(filepath: Path, reason: str):
    """Move a repeatedly-failing task to Quarantine/ for manual review."""
    FOLDERS["quarantine"].mkdir(parents=True, exist_ok=True)
    dest = FOLDERS["quarantine"] / filepath.name
    try:
        content = filepath.read_text(encoding="utf-8")
        stamp   = (
            f"\n\n---\n"
            f"**QUARANTINED**\n"
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"**Reason:** {reason}\n"
            f"**Action:** Manual review required\n"
        )
        dest.write_text(content + stamp, encoding="utf-8")
        filepath.unlink()
        log_event(
            "QUARANTINED", "ralph_loop",
            f"{filepath.name}: {reason}",
            severity="WARNING",
            result="QUARANTINED",
        )
        print(f"  [QUARANTINE] {filepath.name} -> Quarantine/ ({reason})")
    except Exception as e:
        print(f"  [ERROR] Quarantine failed for {filepath.name}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 0 -- INBOX SHUTTLE
# ══════════════════════════════════════════════════════════════════════════════

def step_inbox():
    """Move new files from Inbox/ to Needs_Action/."""
    files = (
        list(FOLDERS["inbox"].glob("*.md")) +
        list(FOLDERS["inbox"].glob("*.txt"))
    )
    for f in files:
        dest = FOLDERS["needs"] / f.name
        shutil.move(str(f), str(dest))
        log_event("INBOX_TO_NEEDS", "ralph_loop", f.name)
        print(f"  [INBOX] {f.name} -> Needs_Action/")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 -- AI BRAIN (PLATINUM 4-agent pipeline)
# ══════════════════════════════════════════════════════════════════════════════

def step_ai_brain():
    """
    Run claude_runner (Platinum or Gold mode) on all files in Needs_Action/.
    Implements per-task failure tracking and quarantine.
    Returns count of files processed.
    """
    try:
        os.chdir(str(AI_DIR))
        from claude_runner import process_needs_action
        results = process_needs_action()

        count = len(results) if results else 0
        for r in results or []:
            task_name = Path(r["file"]).stem
            _clear_failure(task_name)  # success -> reset failure count

            log_event(
                "AI_PROCESSED", "claude_runner",
                f"{r['file']} -> {r.get('channel','?')} | {r.get('ai_mode','?')}",
                metadata={
                    "channel":  r.get("channel"),
                    "mode":     r.get("ai_mode"),
                    "quality":  r.get("quality_score", "N/A"),
                    "memories": r.get("memories_used", 0),
                },
            )
            quality_info = ""
            if r.get("quality_score"):
                quality_info = f" | Quality={r['quality_score']}/10"
            if r.get("memories_used"):
                quality_info += f" | Memories={r['memories_used']}"
            print(
                f"  [BRAIN] {r['file']} | {r.get('channel')} | "
                f"{r.get('ai_mode','?')[:40]}{quality_info}"
            )
        return count

    except Exception as e:
        # Per-task self-healing: check which files caused the error
        needs_files = list(FOLDERS["needs"].glob("*.md"))
        for f in needs_files:
            task_name    = f.stem
            fail_count   = _increment_failure(task_name)
            if fail_count >= MAX_TASK_FAILURES:
                _quarantine_task(
                    f,
                    f"AI Brain failed {fail_count} times: {str(e)[:100]}",
                )
            else:
                print(
                    f"  [SELF-HEAL] {f.name} failure {fail_count}/{MAX_TASK_FAILURES} "
                    f"-- will retry next pass"
                )

        log_event(
            "AI_BRAIN_ERROR", "ralph_loop",
            str(e), severity="ERROR", result="RECOVERED",
        )
        print(f"  [ERROR] AI Brain error: {e} -- self-healing active")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 -- APPROVAL (AUTO or MANUAL)
# ══════════════════════════════════════════════════════════════════════════════

def step_approve():
    """
    AUTO_APPROVE=True  -> approve all pending files automatically.
    AUTO_APPROVE=False -> wait for human (file drag in Obsidian).
    """
    pending = list(FOLDERS["pending"].glob("*.md"))
    if not pending:
        return 0

    if not AUTO_APPROVE:
        print(f"  [GATE] {len(pending)} file(s) awaiting human approval.")
        print("         Drag to Approved/ in Obsidian, or set AUTO_APPROVE=true")
        return 0

    approved = 0
    for filepath in pending:
        try:
            content = filepath.read_text(encoding="utf-8")
            content = content.replace("PENDING APPROVAL", "APPROVED")
            content = content.replace(
                "PENDING -- Awaiting Human Approval",
                "APPROVED -- Auto-Approved by System",
            )
            content += (
                f"\n\n---\n"
                f"**Auto-Approved by:** Ralph Loop v3.0 (Platinum)\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Mode:** AUTO_APPROVE=True\n"
            )
            dest = FOLDERS["approved"] / filepath.name
            dest.write_text(content, encoding="utf-8")
            filepath.unlink()

            log_event("AUTO_APPROVED", "ralph_loop", filepath.name)
            print(f"  [AUTO-APPROVED] {filepath.name}")
            approved += 1

        except Exception as e:
            log_event(
                "APPROVE_ERROR", "ralph_loop",
                f"{filepath.name}: {e}", severity="ERROR",
            )
            print(f"  [ERROR] Approve failed for {filepath.name}: {e}")

    return approved


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 -- EXECUTE
# ══════════════════════════════════════════════════════════════════════════════

def step_execute():
    """
    Execute all approved files via channel_dispatcher.
    After execution, update memory outcomes (SUCCESS/FAILED).
    """
    approved = list(FOLDERS["approved"].glob("*.md"))
    if not approved:
        return 0

    try:
        os.chdir(str(AI_DIR))
        from channel_dispatcher import dispatch
    except Exception as e:
        log_event("DISPATCHER_ERROR", "ralph_loop", str(e), severity="ERROR")
        print(f"  [ERROR] Dispatcher import failed: {e}")
        return 0

    executed = 0
    for filepath in approved:
        try:
            content = filepath.read_text(encoding="utf-8")
            status, channel, recipient = dispatch(filepath, content)

            stamp = (
                f"\n\n---\n"
                f"**Executed by:** Ralph Loop v3.0 (Platinum)\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Channel:** {channel}\n"
                f"**Recipient:** {recipient}\n"
                f"**Status:** {status}\n"
            )
            dest = FOLDERS["done"] / filepath.name
            dest.write_text(content + stamp, encoding="utf-8")
            filepath.unlink()

            # Update memory outcome
            if ENABLE_MEMORY:
                try:
                    from memory_manager import update_memory_outcome
                    outcome = "SUCCESS" if "SENT" in str(status).upper() or "DEMO" in str(status).upper() else "FAILED"
                    update_memory_outcome(filepath.name, outcome)
                except Exception:
                    pass

            log_event(
                "EXECUTED", "executor",
                f"{filepath.name} -> {status}",
                metadata={"channel": channel, "to": recipient, "status": status},
            )
            print(f"  [SENT] [{channel}] -> {recipient} | {status}")
            executed += 1

        except Exception as e:
            log_event(
                "EXECUTE_ERROR", "executor",
                f"{filepath.name}: {e}", severity="ERROR", result="FAILED",
            )
            print(f"  [ERROR] Execute failed for {filepath.name}: {e}")

    return executed


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 -- ARCHIVE REJECTED (with memory outcome update)
# ══════════════════════════════════════════════════════════════════════════════

def step_rejected():
    """Move rejected files to Done/ and update memory with REJECTED outcome."""
    for filepath in FOLDERS["rejected"].glob("*.md"):
        try:
            stamp = (
                f"\n\n---\n"
                f"**Rejected:** Human said NO\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Status:** REJECTED -- No action taken\n"
            )
            dest = FOLDERS["done"] / filepath.name
            dest.write_text(
                filepath.read_text(encoding="utf-8") + stamp, encoding="utf-8"
            )
            filepath.unlink()

            # Update memory: this type of task gets rejected
            if ENABLE_MEMORY:
                try:
                    from memory_manager import update_memory_outcome
                    update_memory_outcome(filepath.name, "REJECTED")
                except Exception:
                    pass

            log_event(
                "REJECTED_ARCHIVED", "ralph_loop",
                filepath.name, severity="WARNING",
            )
            print(f"  [REJECTED] {filepath.name} -> Done/ (memory updated)")

        except Exception as e:
            print(f"  [ERROR] Reject handler: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SELF-IMPROVEMENT TRIGGER
# ══════════════════════════════════════════════════════════════════════════════

def step_self_improve():
    """
    Every IMPROVEMENT_INTERVAL passes, analyze outcomes and improve prompts.
    Only runs if ENABLE_SELF_IMPROVEMENT=True.
    """
    if not ENABLE_SELF_IMPROVEMENT:
        return

    global _pass_count
    if _pass_count % IMPROVEMENT_INTERVAL != 0:
        return

    print(f"  [IMPROVE] Running self-improvement analysis (pass #{_pass_count})...")
    try:
        os.chdir(str(AI_DIR))
        from self_improvement import improve_prompts
        improvements = improve_prompts()
        if improvements:
            for rule, desc in improvements.items():
                print(f"  [IMPROVE] {rule}: {desc}")
            log_event(
                "SELF_IMPROVEMENT_RUN", "self_improvement",
                f"{len(improvements)} prompt(s) improved: {list(improvements.keys())}",
                metadata={"improvements": improvements},
            )
        else:
            print("  [IMPROVE] No changes needed -- system performing well")
    except Exception as e:
        print(f"  [IMPROVE] Self-improvement error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PLATINUM DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def update_dashboard():
    """Write live PLATINUM status to Dashboard.md."""
    counts = {
        name: len(list(folder.glob("*.md")))
        for name, folder in FOLDERS.items()
        if name not in ("logs",)
    }
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pending = counts.get("pending", 0)

    attention = ""
    if pending > 0 and not AUTO_APPROVE:
        files     = [f.name for f in FOLDERS["pending"].glob("*.md")][:5]
        attention = f"\n## Needs Your Attention\n{pending} file(s) awaiting approval:\n"
        attention += "\n".join(f"- {f}" for f in files) + "\n"

    # Memory stats
    memory_section = ""
    if ENABLE_MEMORY:
        try:
            os.chdir(str(AI_DIR))
            from memory_manager import get_stats
            stats = get_stats()
            memory_section = f"""
## Platinum Intelligence
| Metric | Value |
|--------|-------|
| Total Processed | {stats.get('total_processed', 0)} |
| Success Rate | {stats.get('total_success', 0)}/{stats.get('total_processed', 1)} |
| Avg Quality Score | {stats.get('avg_quality_score', 0):.1f}/10 |
| Total Improvements | {stats.get('total_improvements', 0)} |
| Last Improvement | {(stats.get('last_improvement_run') or 'Never')[:16]} |
| Active Backend | {max(stats.get('backend_usage', {'none': 1}), key=stats.get('backend_usage', {'none': 1}).get, default='none')} |
| Quarantined Tasks | {counts.get('quarantine', 0)} |
"""
        except Exception:
            memory_section = "\n## Platinum Intelligence\nMemory system initializing...\n"

    # Improvement summary
    improve_section = ""
    if ENABLE_SELF_IMPROVEMENT:
        try:
            from self_improvement import get_improvement_summary
            improve_section = f"\n## Self-Improvement Log\n```\n{get_improvement_summary()}\n```\n"
        except Exception:
            pass

    content = f"""# Ralph Loop v3.0 -- PLATINUM Dashboard

## Today Status
- Pending Tasks: {counts.get('needs', 0)}
- Awaiting Approval: {counts.get('pending', 0)}
- Approved: {counts.get('approved', 0)}
- Rejected: {counts.get('rejected', 0)}
- Done Today: {counts.get('done', 0)}
- Quarantined: {counts.get('quarantine', 0)}

## Pipeline
| Folder | Count |
|--------|-------|
| Needs_Action | {counts.get('needs', 0)} |
| Pending_Approval | {counts.get('pending', 0)} |
| Approved | {counts.get('approved', 0)} |
| Rejected | {counts.get('rejected', 0)} |
| Done | {counts.get('done', 0)} |
| Quarantine | {counts.get('quarantine', 0)} |
{attention}
## Mode
- Tier: **PLATINUM** (4-agent pipeline)
- AUTO_APPROVE: {'ON (fully autonomous)' if AUTO_APPROVE else 'OFF (human approval required)'}
- Memory System: {'ON' if ENABLE_MEMORY else 'OFF'}
- Self-Improvement: {'ON (every ' + str(IMPROVEMENT_INTERVAL) + ' passes)' if ENABLE_SELF_IMPROVEMENT else 'OFF'}
- Loop Interval: {LOOP_INTERVAL}s
- Pass Count: {_pass_count}
{memory_section}{improve_section}
## Last Update
- {now}
- Ralph Wiggum Loop v3.0 -- PLATINUM ACTIVE
"""
    dashboard = ROOT / "Dashboard.md"
    dashboard.write_text(content, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# ONE FULL PASS
# ══════════════════════════════════════════════════════════════════════════════

def run_pass():
    """Execute one complete PLATINUM pipeline pass."""
    global _pass_count
    _pass_count += 1

    ts = datetime.now().strftime("%H:%M:%S")
    print(
        f"\n[{ts}] === Ralph Loop PLATINUM Pass #{_pass_count} === "
        f"AUTO={'ON' if AUTO_APPROVE else 'OFF'}"
    )

    step_inbox()
    ai_count  = step_ai_brain()
    approved  = step_approve()
    executed  = step_execute()
    step_rejected()

    # Self-improvement (every N passes)
    step_self_improve()

    update_dashboard()

    print(
        f"  [OK] Pass #{_pass_count} done: "
        f"AI={ai_count} | Approved={approved} | Executed={executed}"
    )
    log_event(
        "PASS_COMPLETE", "ralph_loop",
        f"Pass#{_pass_count} AI:{ai_count} Approved:{approved} Executed:{executed}",
        metadata={
            "pass":     _pass_count,
            "ai":       ai_count,
            "approved": approved,
            "executed": executed,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════════════════════

def ensure_folders():
    """Create all pipeline folders if they don't exist."""
    for folder in FOLDERS.values():
        folder.mkdir(parents=True, exist_ok=True)


def main():
    one_shot = len(sys.argv) > 1 and sys.argv[1] == "--once"

    print("=" * 65)
    print("  RALPH WIGGUM LOOP v3.0 -- PLATINUM Autonomous AI Employee")
    print('  "Me fail? That\'s unpossible!"')
    print(f"  Tier         : PLATINUM (4-agent + Memory + Self-Improvement)")
    print(f"  AUTO_APPROVE : {'ON' if AUTO_APPROVE else 'OFF'}")
    print(f"  PLATINUM AI  : {'ON' if ENABLE_PLATINUM else 'OFF (Gold fallback)'}")
    print(f"  Memory       : {'ON' if ENABLE_MEMORY else 'OFF'}")
    print(f"  Self-Improve : {'ON (every ' + str(IMPROVEMENT_INTERVAL) + ' passes)' if ENABLE_SELF_IMPROVEMENT else 'OFF'}")
    print(f"  Interval     : {LOOP_INTERVAL}s")
    print(f"  Vault        : {VAULT}")
    print(f"  Mode         : {'SINGLE PASS (--once)' if one_shot else 'INFINITE LOOP -- Ctrl+C to stop'}")
    print("=" * 65)

    ensure_folders()
    log_event(
        "LOOP_START", "ralph_loop",
        (
            f"v3.0 PLATINUM started | "
            f"AUTO_APPROVE={AUTO_APPROVE} | "
            f"PLATINUM={ENABLE_PLATINUM} | "
            f"MEMORY={ENABLE_MEMORY} | "
            f"IMPROVE={ENABLE_SELF_IMPROVEMENT}"
        ),
    )

    if one_shot:
        run_pass()
        return

    # ── Infinite loop -- self-healing, never dies ─────────────────────────────
    while True:
        try:
            run_pass()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log_event(
                "PASS_ERROR", "ralph_loop",
                str(e), severity="ERROR", result="RECOVERED",
            )
            print(f"  [ERROR] Pass failed: {e} -- self-healing, continuing in {LOOP_INTERVAL}s")

        time.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Ralph Loop PLATINUM stopped by user.")
        log_event("LOOP_STOP", "ralph_loop", "Stopped by Ctrl+C")
