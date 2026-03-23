"""
State Machine Workflow Engine
==============================
File-based state machine where FOLDERS = STATES and MOVING a file = STATE TRANSITION.

States:  Inbox → Needs_Action → Pending_Approval → Approved → Done
                      ↓                                ↑
                   Plans/ (audit)              Rejected → Done

Guards:
  - Duplicate detection (never process same file twice per pass)
  - Empty file protection (skip → Done with warning)
  - Loop breaker (max 3 passes before forced stop)
  - Error isolation (one bad file doesn't kill the pipeline)

Usage:
  from state_machine import StateMachine
  sm = StateMachine(vault_path)
  sm.run()               # Single pass through all states
  sm.run_daemon(60)      # Loop every 60 seconds
"""

import os
import json
import shutil
from enum import Enum
from pathlib import Path
from datetime import datetime


# ──────────────────────────────────────────────
# STATES
# ──────────────────────────────────────────────

class State(Enum):
    INBOX = "Inbox"
    NEEDS_ACTION = "Needs_Action"
    PLANS = "Plans"
    PENDING_APPROVAL = "Pending_Approval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    DONE = "Done"


# Valid transitions: from_state → [allowed_to_states]
TRANSITIONS = {
    State.INBOX:            [State.NEEDS_ACTION],
    State.NEEDS_ACTION:     [State.PENDING_APPROVAL, State.DONE],  # DONE for empty files
    State.PENDING_APPROVAL: [State.APPROVED, State.REJECTED],       # Human decides
    State.APPROVED:         [State.DONE],
    State.REJECTED:         [State.DONE],
    State.DONE:             [],  # Terminal state — no transitions out
}


# ──────────────────────────────────────────────
# LOGGER
# ──────────────────────────────────────────────

class AuditLogger:
    """Append-only JSON audit logger. One file per day."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_path(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.logs_dir / f"{today}.json"

    def _load(self) -> dict:
        path = self._get_log_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "audit_date": datetime.now().strftime("%Y-%m-%d"),
            "system": "AI Employee State Machine",
            "version": "2.0",
            "total_events": 0,
            "events": [],
        }

    def log(self, action: str, actor: str, details: str,
            severity: str = "INFO", result: str = "SUCCESS",
            metadata: dict = None):
        """Write one event to today's audit log."""
        data = self._load()
        data["total_events"] += 1

        event = {
            "id": f"EVT-{data['total_events']:04d}",
            "timestamp": datetime.now().isoformat(),
            "actor": actor,
            "action": action,
            "details": details,
            "severity": severity,
            "result": result,
        }
        if metadata:
            event["metadata"] = metadata

        data["events"].append(event)

        with open(self._get_log_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        tag = f"[{severity}]" if severity != "INFO" else "[OK]"
        # Safe print for Windows consoles (cp1252 can't handle unicode arrows)
        safe_details = details.replace("\u2192", "->").replace("\u2190", "<-")
        print(f"  {tag} {action}: {safe_details}")


# ──────────────────────────────────────────────
# STATE MACHINE
# ──────────────────────────────────────────────

class StateMachine:
    """
    File-based state machine.
    Each folder = a state. Moving a file between folders = a state transition.
    """

    MAX_PASSES = 3  # Loop breaker: max consecutive passes with work

    def __init__(self, vault_path: str | Path):
        self.vault = Path(vault_path)
        self.folders: dict[State, Path] = {}
        self.logger: AuditLogger = None
        self._processed_this_pass: set[str] = set()
        self._pass_count = 0

        self._init_folders()

    def _init_folders(self):
        """Create all state folders + logs dir."""
        for state in State:
            folder = self.vault / state.value
            folder.mkdir(parents=True, exist_ok=True)
            self.folders[state] = folder

        logs_dir = self.vault / "Logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.logger = AuditLogger(logs_dir)

        plans_dir = self.vault / "Plans"
        plans_dir.mkdir(parents=True, exist_ok=True)

    # ──────────── Core: Transition ────────────

    def transition(self, filepath: Path, from_state: State, to_state: State,
                   actor: str = "state_machine", stamp: str = None) -> bool:
        """
        Move a file from one state to another.
        Returns True if successful, False if blocked.
        """
        # Guard: validate transition
        if to_state not in TRANSITIONS.get(from_state, []):
            self.logger.log(
                "BLOCKED_TRANSITION", actor,
                f"{filepath.name}: {from_state.value} -> {to_state.value} NOT ALLOWED",
                severity="ERROR", result="BLOCKED"
            )
            return False

        # Guard: source file must exist
        if not filepath.exists():
            self.logger.log(
                "FILE_NOT_FOUND", actor,
                f"{filepath.name} not found in {from_state.value}/",
                severity="ERROR", result="FAILED"
            )
            return False

        # Guard: duplicate detection
        file_key = f"{filepath.name}:{from_state.value}→{to_state.value}"
        if file_key in self._processed_this_pass:
            self.logger.log(
                "DUPLICATE_SKIP", actor,
                f"{filepath.name} already processed this pass",
                severity="WARNING", result="SKIPPED"
            )
            return False

        # Execute transition
        dest = self.folders[to_state] / filepath.name
        try:
            # Add stamp to file before moving (if provided)
            if stamp:
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(stamp)

            shutil.move(str(filepath), str(dest))
            self._processed_this_pass.add(file_key)

            self.logger.log(
                f"{from_state.value}_TO_{to_state.value}", actor,
                f"{filepath.name} -> {to_state.value}/"
            )
            return True

        except Exception as e:
            self.logger.log(
                "TRANSITION_ERROR", actor,
                f"{filepath.name}: {e}",
                severity="ERROR", result="FAILED"
            )
            return False

    # ──────────── File Helpers ────────────

    def list_files(self, state: State, extensions: tuple = (".md", ".txt")) -> list[Path]:
        """List task files in a state folder (ignoring system files)."""
        folder = self.folders[state]
        if not folder.exists():
            return []
        return sorted([
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in extensions
        ])

    def read_file(self, filepath: Path) -> str:
        """Safely read a file's content."""
        try:
            return filepath.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def write_file(self, folder_path: Path, filename: str, content: str) -> Path:
        """Write a new file into a folder. Returns the path."""
        path = folder_path / filename
        path.write_text(content, encoding="utf-8")
        return path

    # ──────────── Stage Processors ────────────

    def process_inbox(self) -> int:
        """
        INBOX → NEEDS_ACTION
        Auto-move all incoming files. No logic, just transit.
        """
        files = self.list_files(State.INBOX)
        moved = 0
        for f in files:
            if self.transition(f, State.INBOX, State.NEEDS_ACTION, actor="watcher"):
                moved += 1
        return moved

    def process_needs_action(self, planner=None) -> int:
        """
        NEEDS_ACTION → PENDING_APPROVAL (with plan)
        NEEDS_ACTION → DONE (if empty/unparseable)

        Args:
            planner: callable(filepath, content) → (plan_md, action_md) or None
                     If None, uses built-in planner.
        """
        files = self.list_files(State.NEEDS_ACTION)
        processed = 0

        for filepath in files:
            content = self.read_file(filepath)

            # Guard: empty file → skip to Done
            if not content:
                stamp = f"\n\n---\n**Skipped:** Empty file\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                self.transition(filepath, State.NEEDS_ACTION, State.DONE,
                                actor="brain", stamp=stamp)
                self.logger.log("SKIP_EMPTY", "brain",
                                f"{filepath.name} was empty -> Done/",
                                severity="WARNING")
                continue

            # Generate plan + action using provided planner or built-in
            try:
                if planner:
                    plan_md, action_md = planner(filepath, content)
                else:
                    plan_md, action_md = self._default_planner(filepath, content)

                # Write PLAN to Plans/ (audit trail, stays there)
                task_name = filepath.stem
                plans_dir = self.vault / "Plans"
                self.write_file(plans_dir, f"PLAN_{task_name}.md", plan_md)

                # Write ACTION to Pending_Approval/
                action_path = self.write_file(
                    self.folders[State.PENDING_APPROVAL],
                    f"ACTION_{task_name}.md",
                    action_md
                )

                # Move original from Needs_Action → Done (it's been consumed)
                stamp = f"\n\n---\n**Processed by:** AI Brain\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n**Plan:** PLAN_{task_name}.md\n**Action:** ACTION_{task_name}.md\n"
                self.transition(filepath, State.NEEDS_ACTION, State.DONE,
                                actor="brain", stamp=stamp)

                self.logger.log("PLANNED", "brain",
                                f"{filepath.name} -> PLAN + ACTION created",
                                metadata={"channel": self._detect_channel(filepath.name, content)})
                processed += 1

            except Exception as e:
                self.logger.log("PLAN_ERROR", "brain",
                                f"{filepath.name}: {e}",
                                severity="ERROR", result="FAILED")
        return processed

    def process_approved(self, executor=None) -> int:
        """
        APPROVED → DONE
        Execute the approved action, then archive.

        Args:
            executor: callable(filepath, content) → status_string
                      If None, uses built-in executor (stamp only).
        """
        files = self.list_files(State.APPROVED)
        executed = 0

        for filepath in files:
            content = self.read_file(filepath)

            try:
                if executor:
                    status = executor(filepath, content)
                else:
                    status = "Completed (no executor configured)"

                stamp = (
                    f"\n\n---\n"
                    f"**Executed by:** AI Employee\n"
                    f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"**Status:** {status}\n"
                )
                self.transition(filepath, State.APPROVED, State.DONE,
                                actor="executor", stamp=stamp)

                self.logger.log("EXECUTED", "executor",
                                f"{filepath.name} -> {status}",
                                metadata={"status": status})
                executed += 1

            except Exception as e:
                self.logger.log("EXECUTE_ERROR", "executor",
                                f"{filepath.name}: {e}",
                                severity="ERROR", result="FAILED")
        return executed

    def process_rejected(self) -> int:
        """
        REJECTED → DONE
        Log the rejection and archive.
        """
        files = self.list_files(State.REJECTED)
        moved = 0

        for filepath in files:
            stamp = (
                f"\n\n---\n"
                f"**Rejected:** Noted\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Status:** REJECTED — No action taken\n"
            )
            if self.transition(filepath, State.REJECTED, State.DONE,
                               actor="rejection_handler", stamp=stamp):
                moved += 1
        return moved

    # ──────────── Built-in Planner ────────────

    def _detect_channel(self, filename: str, content: str) -> str:
        """Detect communication channel from filename or content."""
        combined = (filename + " " + content).upper()
        if "EMAIL" in combined:
            return "Email"
        if "WHATSAPP" in combined:
            return "WhatsApp"
        if "LINKEDIN" in combined:
            return "LinkedIn"
        return "General"

    def _default_planner(self, filepath: Path, content: str) -> tuple[str, str]:
        """
        Built-in planner. Returns (plan_markdown, action_markdown).
        Override by passing a custom planner to process_needs_action().
        """
        task_name = filepath.stem
        channel = self._detect_channel(filepath.name, content)
        today = datetime.now().strftime("%Y-%m-%d")
        quoted = "\n".join(f"> {line}" for line in content.split("\n"))

        plan_md = f"""# PLAN: {task_name}

| Field | Value |
|-------|-------|
| Source | Needs_Action/{filepath.name} |
| Created | {today} |
| Channel | {channel} |
| Status | Ready for Approval |

## Task Content

{quoted}

## Next Step

Human reviews ACTION_{task_name}.md in Pending_Approval/
"""

        action_md = f"""# ACTION: {task_name}

## Status: PENDING APPROVAL

| Field | Value |
|-------|-------|
| Channel | {channel} |
| Created | {today} |
| Priority | Normal |

## Content

{quoted}

## Result: PENDING — Awaiting Human Approval
"""
        return plan_md, action_md

    # ──────────── Pipeline Run ────────────

    def run(self, planner=None, executor=None) -> dict:
        """
        Run one complete pass through all states.
        Returns a summary dict.
        """
        self._processed_this_pass.clear()
        self._pass_count += 1

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*50}")
        print(f"  Pass #{self._pass_count} at {timestamp}")
        print(f"{'='*50}")

        results = {
            "pass": self._pass_count,
            "inbox_moved": self.process_inbox(),
            "planned": self.process_needs_action(planner=planner),
            "executed": self.process_approved(executor=executor),
            "rejected": self.process_rejected(),
        }

        results["total_actions"] = sum(results[k] for k in results if k != "pass")

        self._update_dashboard()

        self.logger.log("PASS_COMPLETE", "state_machine",
                        f"Pass #{self._pass_count}: {results['total_actions']} actions",
                        metadata=results)

        return results

    def run_daemon(self, interval: int = 60, planner=None, executor=None):
        """
        Run the state machine in a loop.
        Loop breaker: stops after MAX_PASSES consecutive passes with zero work.
        """
        import time

        print("=" * 50)
        print("  STATE MACHINE DAEMON — Active")
        print(f"  Vault: {self.vault}")
        print(f"  Interval: {interval}s")
        print(f"  Loop breaker: {self.MAX_PASSES} idle passes")
        print("  Press Ctrl+C to stop")
        print("=" * 50)

        self.logger.log("DAEMON_START", "state_machine",
                        f"Daemon started (interval={interval}s)")

        idle_count = 0

        try:
            while True:
                results = self.run(planner=planner, executor=executor)

                if results["total_actions"] == 0:
                    idle_count += 1
                    print(f"  Pipeline clear. Idle: {idle_count}/{self.MAX_PASSES}")
                    if idle_count >= self.MAX_PASSES:
                        print(f"\n  Loop breaker: {self.MAX_PASSES} idle passes. Stopping.")
                        self.logger.log("LOOP_BREAKER", "state_machine",
                                        f"Stopped after {self.MAX_PASSES} idle passes",
                                        severity="WARNING")
                        break
                else:
                    idle_count = 0  # Reset on work

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n  Daemon stopped by user.")
            self.logger.log("DAEMON_STOP", "state_machine", "Stopped by user (Ctrl+C)")

    # ──────────── Dashboard ────────────

    def _update_dashboard(self):
        """Update Dashboard.md with current pipeline counts."""
        counts = {}
        for state in State:
            files = self.list_files(state)
            counts[state.value] = len(files)

        pending_approval = self.list_files(State.PENDING_APPROVAL)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rows = "\n".join(
            f"| {state.value:20s} | {counts[state.value]:5d} |"
            for state in State
        )

        attention = ""
        if pending_approval:
            names = ", ".join(f.name for f in pending_approval[:5])
            attention = f"\n## Needs Your Attention\n\n{len(pending_approval)} file(s) awaiting approval: {names}\n"

        dashboard = f"""# AI Employee Dashboard

## Pipeline Status

| Folder               | Count |
|----------------------|-------|
{rows}
{attention}
## Last Updated
- {now}
- State Machine v2.0
"""
        path = self.vault / "Dashboard.md"
        path.write_text(dashboard, encoding="utf-8")

    # ──────────── Status ────────────

    def status(self) -> dict:
        """Return current pipeline counts."""
        result = {}
        for state in State:
            files = self.list_files(state)
            result[state.value] = {
                "count": len(files),
                "files": [f.name for f in files],
            }
        return result

    def print_status(self):
        """Print a formatted pipeline status."""
        print(f"\n{'='*50}")
        print("  PIPELINE STATUS")
        print(f"{'='*50}")

        for state in State:
            files = self.list_files(state)
            indicator = ">>>" if files else "   "
            print(f"  {indicator} {state.value:20s} : {len(files)} file(s)")
            for f in files:
                print(f"       - {f.name}")
        print()
