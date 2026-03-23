"""
Watcher — Inbox Monitor
=========================
Watches Inbox/ for new task files and moves them to Needs_Action/.

Uses StateMachine.transition() for validated, logged file moves.

Usage:
    python watcher.py              # Single pass
    python watcher.py --loop       # Continuous monitoring (5s interval)
"""

import sys
import time
from pathlib import Path

from state_machine import StateMachine, State


BASE = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"


def watch_once(sm: StateMachine) -> int:
    """Single pass: move all Inbox files to Needs_Action."""
    files = sm.list_files(State.INBOX)
    moved = 0
    for filepath in files:
        try:
            if sm.transition(filepath, State.INBOX, State.NEEDS_ACTION, actor="watcher"):
                print(f"  Moved: {filepath.name} -> Needs_Action/")
                moved += 1
        except Exception as e:
            print(f"  [ERROR] {filepath.name}: {e}")
    return moved


def watch_loop(sm: StateMachine, interval: int = 5):
    """Continuous loop: check Inbox every N seconds."""
    print("=" * 50)
    print("  WATCHER — Monitoring Inbox/")
    print(f"  Interval: {interval}s")
    print("  Press Ctrl+C to stop")
    print("=" * 50)

    sm.logger.log("WATCHER_START", "watcher", f"Watcher started (interval={interval}s)")

    try:
        while True:
            moved = watch_once(sm)
            if moved > 0:
                print(f"  [{time.strftime('%H:%M:%S')}] Moved {moved} file(s)")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  Watcher stopped.")
        sm.logger.log("WATCHER_STOP", "watcher", "Stopped by user (Ctrl+C)")


def main():
    sm = StateMachine(VAULT)

    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        watch_loop(sm)
    else:
        moved = watch_once(sm)
        if moved == 0:
            print("  No files in Inbox/")
        else:
            print(f"  Moved {moved} file(s) to Needs_Action/")


if __name__ == "__main__":
    main()
