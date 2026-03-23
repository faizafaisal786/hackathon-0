"""
orchestrator.py — Gold Tier Master Orchestrator
================================================
Coordinates all watchers, triggers Claude Code for reasoning,
monitors approval folders, and manages the full automation pipeline.

Usage:
    python orchestrator.py
    python orchestrator.py --dry-run
    python orchestrator.py --vault-path /path/to/vault
"""

import os
import sys
import time
import json
import shutil
import logging
import argparse
import subprocess
import threading
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

VAULT_PATH = Path(os.getenv("VAULT_PATH") or Path(__file__).parent)
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
CLAUDE_CHECK_INTERVAL = int(os.getenv("CLAUDE_CHECK_INTERVAL", "30"))  # seconds
APPROVAL_CHECK_INTERVAL = int(os.getenv("APPROVAL_CHECK_INTERVAL", "10"))

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
(VAULT_PATH / "Logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(VAULT_PATH / "Logs" / f"orchestrator_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
logger = logging.getLogger("Orchestrator")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def log_action(action_type: str, details: dict):
    """Append structured log entry to today's JSON log."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "actor": "orchestrator",
        **details,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def count_pending_items() -> int:
    """Count pending items in Needs_Action."""
    needs_action = VAULT_PATH / "Needs_Action"
    if not needs_action.exists():
        return 0
    return sum(1 for f in needs_action.glob("*.md") if f.stat().st_size > 0)


# ─── Watcher Process Manager ─────────────────────────────────────────────────

class WatcherManager:
    """Starts and monitors all watcher subprocesses."""

    WATCHERS = {
        "filesystem": "watchers/filesystem_watcher.py",
        "gmail": "watchers/gmail_watcher.py",
        "whatsapp": "watchers/whatsapp_watcher.py",
        "finance": "watchers/finance_watcher.py",
    }

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.processes: dict[str, subprocess.Popen] = {}
        self.logger = logging.getLogger("WatcherManager")

    def start_all(self):
        for name, script in self.WATCHERS.items():
            self.start_watcher(name, script)

    def start_watcher(self, name: str, script: str):
        script_path = self.vault_path / script
        if not script_path.exists():
            self.logger.warning(f"Watcher script not found: {script_path}")
            return
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.vault_path / "watchers")
            env["VAULT_PATH"] = str(self.vault_path)
            # Default drop folder separate from vault Inbox to avoid self-watch loop
            if not env.get("WATCH_PATH"):
                env["WATCH_PATH"] = str(self.vault_path / "Drop")
            proc = subprocess.Popen(
                [sys.executable, str(script_path), "--vault-path", str(self.vault_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=env,
            )
            self.processes[name] = proc
            self.logger.info(f"Started watcher: {name} (PID {proc.pid})")
        except Exception as e:
            self.logger.error(f"Failed to start {name}: {e}")

    def check_and_restart(self):
        """Restart any dead watcher processes."""
        for name, proc in list(self.processes.items()):
            if proc.poll() is not None:
                self.logger.warning(f"Watcher '{name}' died, restarting...")
                self.start_watcher(name, self.WATCHERS[name])

    def stop_all(self):
        for name, proc in self.processes.items():
            proc.terminate()
            self.logger.info(f"Stopped watcher: {name}")


# ─── Claude Trigger ──────────────────────────────────────────────────────────

class ClaudeTrigger:
    """Triggers Claude Code when new items appear in Needs_Action."""

    def __init__(self, vault_path: Path, dry_run: bool = False):
        self.vault_path = vault_path
        self.needs_action = vault_path / "Needs_Action"
        self.dry_run = dry_run
        self.last_count = 0
        self.logger = logging.getLogger("ClaudeTrigger")

    def check_and_trigger(self):
        """If new items appeared, trigger Claude to process them."""
        current_count = count_pending_items()
        if current_count > self.last_count:
            self.logger.info(f"New items detected: {current_count} pending. Triggering Claude...")
            self._trigger_claude()
        self.last_count = current_count

    def _trigger_claude(self):
        if self.dry_run:
            self.logger.info("[DRY RUN] Would trigger Claude: /process-inbox")
            return
        try:
            result = subprocess.run(
                ["claude", "--cwd", str(self.vault_path), "/process-inbox"],
                capture_output=True, text=True, timeout=300,
            )
            if result.returncode == 0:
                self.logger.info("Claude processed inbox successfully.")
                log_action("claude_triggered", {"command": "process-inbox", "result": "success"})
            else:
                self.logger.error(f"Claude error: {result.stderr[:200]}")
                log_action("claude_triggered", {"command": "process-inbox", "result": "error"})
        except subprocess.TimeoutExpired:
            self.logger.error("Claude timed out after 5 minutes.")
        except FileNotFoundError:
            self.logger.error("Claude Code not found. Is it installed?")


# ─── Approval Watcher ────────────────────────────────────────────────────────

class ApprovalWatcher:
    """Watches /Approved folder and executes approved MCP actions."""

    def __init__(self, vault_path: Path, dry_run: bool = False):
        self.vault_path = vault_path
        self.approved = vault_path / "Approved"
        self.done = vault_path / "Done"
        self.dry_run = dry_run
        self.logger = logging.getLogger("ApprovalWatcher")

    def check(self):
        if not self.approved.exists():
            return
        for file in self.approved.glob("*.md"):
            if file.stat().st_size == 0:
                continue
            self.logger.info(f"Approved action found: {file.name}")
            self._execute_approved_action(file)

    def _execute_approved_action(self, file: Path):
        """Read the approval file and execute the corresponding MCP action."""
        content = file.read_text(encoding="utf-8")

        # Parse frontmatter
        action_type = self._extract_frontmatter_value(content, "action")

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would execute approved action: {action_type} for {file.name}")
            return

        self.logger.info(f"Executing approved action: {action_type}")
        log_action("approved_action_executed", {"file": file.name, "action": action_type})

        # Move to Done after execution
        dest = self.done / f"APPROVED_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
        shutil.move(str(file), str(dest))
        self.logger.info(f"Moved to Done: {dest.name}")

    @staticmethod
    def _extract_frontmatter_value(content: str, key: str) -> str:
        for line in content.split("\n"):
            if line.startswith(f"{key}:"):
                return line.split(":", 1)[1].strip()
        return "unknown"


# ─── Main Loop ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee Orchestrator — Gold Tier")
    parser.add_argument("--vault-path", type=Path, default=VAULT_PATH)
    parser.add_argument("--dry-run", action="store_true", default=DRY_RUN)
    args = parser.parse_args()

    vault_path = args.vault_path.resolve()

    logger.info("=" * 60)
    logger.info("AI Employee Orchestrator — Gold Tier")
    logger.info(f"Vault: {vault_path}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("=" * 60)

    watcher_mgr = WatcherManager(vault_path)
    claude_trigger = ClaudeTrigger(vault_path, dry_run=args.dry_run)
    approval_watcher = ApprovalWatcher(vault_path, dry_run=args.dry_run)

    # Start all watchers in background threads
    watcher_mgr.start_all()

    tick = 0
    try:
        while True:
            tick += 1

            # Every cycle: check for new inbox items → trigger Claude
            claude_trigger.check_and_trigger()

            # Every cycle: check for approved actions
            approval_watcher.check()

            # Every 5 minutes: restart dead watchers
            if tick % (300 // CLAUDE_CHECK_INTERVAL) == 0:
                watcher_mgr.check_and_restart()

            time.sleep(CLAUDE_CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutting down orchestrator...")
        watcher_mgr.stop_all()
        logger.info("Goodbye.")


if __name__ == "__main__":
    main()
