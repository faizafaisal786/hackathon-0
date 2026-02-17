"""
Executor — Approved Task Processor
====================================
Processes approved tasks using the StateMachine for safe transitions
and channel_dispatcher for unified message dispatch.

All file moves go through StateMachine.transition() — no raw shutil.move().
All channel sends go through channel_dispatcher.dispatch() — no duplication.

Usage:
    python executor.py              # Process all approved tasks
    python executor.py --status     # Show pipeline status only
"""

import sys
from pathlib import Path
from datetime import datetime

from state_machine import StateMachine, State
from channel_dispatcher import dispatch


BASE = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"


def execute_approved(sm: StateMachine) -> int:
    """
    Process all files in Approved/ via the state machine.
    Uses channel_dispatcher for unified send logic.
    Returns number of tasks executed.
    """
    files = sm.list_files(State.APPROVED)
    if not files:
        print("  No approved tasks to execute.")
        return 0

    executed = 0
    for filepath in files:
        content = sm.read_file(filepath)

        try:
            # Dispatch via unified channel handler
            status, channel, recipient = dispatch(filepath, content)

            print(f"  [{channel}] {filepath.name} -> {recipient} | {status}")

            # Move to Done via state machine (validates transition + logs)
            stamp = (
                f"\n\n---\n"
                f"**Executed by:** AI Employee\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Channel:** {channel}\n"
                f"**Recipient:** {recipient}\n"
                f"**Status:** {status}\n"
            )
            sm.transition(filepath, State.APPROVED, State.DONE,
                          actor="executor", stamp=stamp)

            sm.logger.log("EXECUTED", "executor",
                          f"{filepath.name} -> {status}",
                          metadata={"channel": channel, "to": recipient, "status": status})
            executed += 1

        except Exception as e:
            sm.logger.log("EXECUTE_ERROR", "executor",
                          f"{filepath.name}: {e}",
                          severity="ERROR", result="FAILED")
            print(f"  [ERROR] {filepath.name}: {e}")

    return executed


def main():
    sm = StateMachine(VAULT)

    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        sm.print_status()
        return

    print("=" * 50)
    print("  EXECUTOR — Processing Approved Tasks")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 50)

    executed = execute_approved(sm)

    print(f"\n  Executed: {executed} task(s)")
    sm._update_dashboard()
    sm.print_status()


if __name__ == "__main__":
    main()
