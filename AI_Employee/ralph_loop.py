"""
Ralph Loop v3.0 — Platinum Continuous Pipeline Runner
=======================================================
The main orchestrator loop for AI Employee.
Runs the full pipeline (Inbox → Done) on a configurable interval.

Usage:
    python ralph_loop.py              # Continuous loop (uses LOOP_INTERVAL from config)
    python ralph_loop.py --once       # Single pass only
    python ralph_loop.py --status     # Show pipeline status only
    python ralph_loop.py --live       # Single pass with human approval
"""

import sys
import time
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from config import (
    LOOP_INTERVAL,
    AUTO_APPROVE,
    ENABLE_SELF_IMPROVEMENT,
    IMPROVEMENT_INTERVAL,
    VAULT_PATH,
)
from state_machine import StateMachine, State
from run_pipeline import smart_planner, channel_executor, auto_approve, interactive_approve

VAULT = VAULT_PATH


def run_once(sm: StateMachine, mode: str = "--demo") -> dict:
    """
    Execute one full pipeline pass.
    Returns a summary dict of what happened.
    """
    summary = {"moved": 0, "planned": 0, "approved": 0, "executed": 0, "rejected": 0}

    # Stage 1: Inbox → Needs_Action
    inbox_files = sm.list_files(State.INBOX)
    for f in inbox_files:
        try:
            if sm.transition(f, State.INBOX, State.NEEDS_ACTION, actor="ralph_loop"):
                summary["moved"] += 1
        except Exception as e:
            print(f"  [ERROR] Inbox move {f.name}: {e}")

    # Stage 2: Needs_Action → Plans + Pending_Approval
    needs_action_files = sm.list_files(State.NEEDS_ACTION)
    for f in needs_action_files:
        try:
            content = sm.read_file(f)
            task_name = f.stem

            # Idempotency guard
            if (VAULT / "Plans" / f"PLAN_{task_name}.md").exists():
                continue

            plan_md, action_md = smart_planner(f, content)

            plan_path = VAULT / "Plans" / f"PLAN_{task_name}.md"
            action_path = VAULT / "Pending_Approval" / f"ACTION_{task_name}.md"

            plan_path.parent.mkdir(parents=True, exist_ok=True)
            action_path.parent.mkdir(parents=True, exist_ok=True)

            plan_path.write_text(plan_md, encoding="utf-8")
            action_path.write_text(action_md, encoding="utf-8")

            sm.transition(f, State.NEEDS_ACTION, State.DONE,
                          actor="ralph_loop", stamp="\n\n---\n**Processed by:** Ralph Loop v3.0 (Platinum)\n")
            sm.logger.log("PLANNED", "ralph_loop", f"{f.name} -> PLAN + ACTION created",
                          metadata={"task": task_name})
            summary["planned"] += 1

        except Exception as e:
            sm.logger.log("PLAN_ERROR", "ralph_loop", f"{f.name}: {e}",
                          severity="ERROR", result="FAILED")
            print(f"  [ERROR] Planning {f.name}: {e}")

    # Stage 3: Approval
    if mode == "--live":
        interactive_approve(sm)
    else:
        pending = sm.list_files(State.PENDING_APPROVAL)
        for f in pending:
            try:
                sm.transition(f, State.PENDING_APPROVAL, State.APPROVED, actor="ralph_loop")
                print(f"  [AUTO-APPROVED] {f.name}")
                summary["approved"] += 1
            except Exception as e:
                print(f"  [ERROR] Approval {f.name}: {e}")

    # Stage 4: Execute approved tasks
    approved_files = sm.list_files(State.APPROVED)
    for f in approved_files:
        try:
            content = sm.read_file(f)
            status = channel_executor(f, content)

            stamp = (
                f"\n\n---\n"
                f"**Executed by:** Ralph Loop v3.0 (Platinum)\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Status:** {status}\n"
            )
            sm.transition(f, State.APPROVED, State.DONE, actor="ralph_loop", stamp=stamp)
            sm.logger.log("EXECUTED", "ralph_loop", f"{f.name} -> {status}",
                          metadata={"status": status})
            print(f"  [EXECUTED] {f.name} -> {status}")
            summary["executed"] += 1

        except Exception as e:
            sm.logger.log("EXECUTE_ERROR", "ralph_loop", f"{f.name}: {e}",
                          severity="ERROR", result="FAILED")
            print(f"  [ERROR] Execute {f.name}: {e}")

    # Stage 5: Handle rejected tasks
    rejected_files = sm.list_files(State.REJECTED)
    for f in rejected_files:
        try:
            sm.transition(f, State.REJECTED, State.DONE, actor="ralph_loop",
                          stamp="\n\n---\n**Note:** Rejected by human. Archived.\n")
            summary["rejected"] += 1
        except Exception as e:
            print(f"  [ERROR] Reject archive {f.name}: {e}")

    sm._update_dashboard()
    return summary


def print_header(mode_label: str):
    print("=" * 52)
    print("  Ralph Loop v3.0 — AI Employee (Platinum)")
    print(f"  Mode : {mode_label}")
    print(f"  Time : {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print(f"  Auto : {'ON' if AUTO_APPROVE else 'OFF'} | Interval: {LOOP_INTERVAL}s")
    print("=" * 52)


def main():
    sm = StateMachine(VAULT)

    args = sys.argv[1:]
    mode = args[0] if args else "--auto"

    # ── Status only ──────────────────────────────────
    if mode == "--status":
        sm.print_status()
        return

    # ── Single pass ──────────────────────────────────
    if mode in ("--once", "--live"):
        approve_mode = "--live" if mode == "--live" else "--demo"
        print_header("SINGLE PASS (live)" if mode == "--live" else "SINGLE PASS")
        summary = run_once(sm, mode=approve_mode)
        print(f"\n  Moved: {summary['moved']} | Planned: {summary['planned']} | "
              f"Approved: {summary['approved']} | Executed: {summary['executed']}")
        sm.print_status()
        return

    # ── Continuous loop ───────────────────────────────
    print_header("CONTINUOUS LOOP")
    print("  Press Ctrl+C to stop\n")
    sm.logger.log("RALPH_START", "ralph_loop",
                  f"Ralph Loop started (interval={LOOP_INTERVAL}s, auto={AUTO_APPROVE})")

    pass_count = 0
    try:
        while True:
            pass_count += 1
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] Pass #{pass_count}")

            approve_mode = "--demo" if AUTO_APPROVE else "--live"
            summary = run_once(sm, mode=approve_mode)

            total = sum(summary.values())
            if total > 0:
                print(f"    Moved:{summary['moved']} Planned:{summary['planned']} "
                      f"Approved:{summary['approved']} Executed:{summary['executed']}")
            else:
                print("    Nothing to do.")

            # Self-improvement run
            if ENABLE_SELF_IMPROVEMENT and pass_count % IMPROVEMENT_INTERVAL == 0:
                try:
                    from self_improvement import run_self_improvement
                    run_self_improvement()
                    print(f"  [Self-Improvement] Pass #{pass_count} — improvement cycle done.")
                except Exception as e:
                    print(f"  [Self-Improvement] Skipped: {e}")

            # Weekly CEO Briefing — auto-generates every Monday (once per week)
            now = datetime.now()
            if now.weekday() == 0:  # Monday = 0
                briefing_flag = VAULT / "Logs" / f"briefing_done_{now.strftime('%Y-%W')}.flag"
                if not briefing_flag.exists():
                    try:
                        from briefing_generator import generate_briefing
                        briefing_path = generate_briefing()
                        briefing_flag.touch()
                        print(f"  [CEO Briefing] Weekly briefing generated: {Path(briefing_path).name}")
                        sm.logger.log("CEO_BRIEFING", "ralph_loop",
                                      f"Weekly CEO briefing generated: {briefing_path}")
                    except Exception as e:
                        print(f"  [CEO Briefing] Skipped: {e}")

            time.sleep(LOOP_INTERVAL)

    except KeyboardInterrupt:
        print("\n  Ralph Loop stopped.")
        sm.logger.log("RALPH_STOP", "ralph_loop", f"Stopped by user after {pass_count} passes")


if __name__ == "__main__":
    main()
