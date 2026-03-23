"""
orchestrator.py — Master orchestrator for Silver Tier.

Starts all configured watchers in separate threads and provides a unified
control interface. When a watcher deposits a new item in Inbox/, the orchestrator
triggers Claude Code via subprocess to run /process-inbox automatically (optional).

Environment variables (via .env):
    VAULT_PATH          — Absolute path to vault root
    ENABLE_GMAIL        — "true" to start Gmail watcher (default: false)
    ENABLE_LINKEDIN     — "true" to start LinkedIn watcher (default: false)
    ENABLE_FILESYSTEM   — "true" to start filesystem watcher (default: true)
    AUTO_TRIGGER_CLAUDE — "true" to auto-run Claude on new inbox items (default: false)
    WATCH_PATH          — Drop folder for filesystem watcher
    DRY_RUN             — "true" to disable all writes
"""

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# ── Path resolution ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR / "watchers"))

from filesystem_watcher import FilesystemWatcher
from gmail_watcher import GmailWatcher
from linkedin_watcher import LinkedInWatcher
from base_watcher import setup_logger

# ── Configuration ────────────────────────────────────────────────────────────
VAULT_PATH = os.getenv("VAULT_PATH") or str(SCRIPT_DIR)
ENABLE_GMAIL = os.getenv("ENABLE_GMAIL", "false").lower() == "true"
ENABLE_LINKEDIN = os.getenv("ENABLE_LINKEDIN", "false").lower() == "true"
ENABLE_FILESYSTEM = os.getenv("ENABLE_FILESYSTEM", "true").lower() == "true"
AUTO_TRIGGER_CLAUDE = os.getenv("AUTO_TRIGGER_CLAUDE", "false").lower() == "true"
WATCH_PATH = os.getenv("WATCH_PATH") or str(Path(VAULT_PATH) / "Drop")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))

LOG_FILE = Path(VAULT_PATH) / "Logs" / "orchestrator.log"
logger = setup_logger("Orchestrator", LOG_FILE)


class WatcherThread(threading.Thread):
    """Runs a BaseWatcher instance in a daemon thread with auto-restart on crash."""

    MAX_RESTARTS = 5
    RESTART_DELAY = 30  # seconds

    def __init__(self, watcher, name: str):
        super().__init__(name=name, daemon=True)
        self._watcher = watcher
        self._restarts = 0

    def run(self):
        while self._restarts <= self.MAX_RESTARTS:
            try:
                logger.info(f"[{self.name}] Starting watcher (attempt {self._restarts + 1})")
                self._watcher.run()
                break  # Normal exit
            except Exception as e:
                self._restarts += 1
                logger.error(
                    f"[{self.name}] Crashed: {e}. "
                    f"Restart {self._restarts}/{self.MAX_RESTARTS} in {self.RESTART_DELAY}s..."
                )
                if self._restarts <= self.MAX_RESTARTS:
                    time.sleep(self.RESTART_DELAY)

        if self._restarts > self.MAX_RESTARTS:
            logger.critical(f"[{self.name}] Exceeded max restarts. Giving up.")


class InboxMonitor(threading.Thread):
    """
    Watches the Inbox/ folder for new files.
    Optionally triggers Claude Code via subprocess when new items arrive.
    """

    def __init__(self, vault_path: str, auto_trigger: bool = False):
        super().__init__(name="InboxMonitor", daemon=True)
        self.inbox = Path(vault_path) / "Inbox"
        self.auto_trigger = auto_trigger
        self._last_count = self._count_items()

    def _count_items(self) -> int:
        if not self.inbox.exists():
            return 0
        return len([f for f in self.inbox.iterdir() if f.suffix == ".md"])

    def run(self):
        logger.info(f"InboxMonitor watching: {self.inbox}")
        while True:
            try:
                current_count = self._count_items()
                if current_count > self._last_count:
                    new_items = current_count - self._last_count
                    logger.info(f"InboxMonitor: {new_items} new item(s) detected in Inbox/")
                    if self.auto_trigger and not DRY_RUN:
                        self._trigger_claude()
                    self._last_count = current_count
                time.sleep(5)
            except Exception as e:
                logger.error(f"InboxMonitor error: {e}")
                time.sleep(10)

    def _trigger_claude(self):
        """Run Claude Code slash command to process inbox."""
        logger.info("Auto-triggering Claude: /process-inbox")
        try:
            result = subprocess.run(
                ["claude", "--print", "/process-inbox"],
                cwd=VAULT_PATH,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("Claude /process-inbox completed successfully.")
            else:
                logger.warning(
                    f"Claude exited with code {result.returncode}: {result.stderr}"
                )
        except FileNotFoundError:
            logger.error("Claude Code not found. Install with: npm i -g @anthropic-ai/claude-code")
        except subprocess.TimeoutExpired:
            logger.warning("Claude /process-inbox timed out after 120s.")


def print_status(threads: list[WatcherThread]):
    """Print current thread status to console."""
    print("\n" + "=" * 60)
    print("  Personal AI Employee — Silver Tier Orchestrator")
    print("=" * 60)
    for t in threads:
        status = "RUNNING" if t.is_alive() else "STOPPED"
        restarts = f"(restarts: {t._restarts})" if t._restarts > 0 else ""
        print(f"  {t.name:<25} {status} {restarts}")
    print(f"\n  Vault: {VAULT_PATH}")
    print(f"  Dry Run: {DRY_RUN}")
    print(f"  Auto-trigger Claude: {AUTO_TRIGGER_CLAUDE}")
    print("=" * 60 + "\n")


def main():
    logger.info("=" * 60)
    logger.info("Personal AI Employee — Silver Tier Orchestrator starting")
    logger.info(f"Vault: {VAULT_PATH}")
    logger.info(f"DRY_RUN={DRY_RUN} | AUTO_TRIGGER={AUTO_TRIGGER_CLAUDE}")

    threads: list[WatcherThread] = []

    # ── Filesystem Watcher ────────────────────────────────────────────────────
    if ENABLE_FILESYSTEM:
        fs_watcher = FilesystemWatcher(
            vault_path=VAULT_PATH,
            watch_path=WATCH_PATH,
            poll_interval_seconds=POLL_INTERVAL,
            dry_run=DRY_RUN,
        )
        t = WatcherThread(fs_watcher, "FilesystemWatcher")
        threads.append(t)
        t.start()
        logger.info(f"FilesystemWatcher started — watching: {WATCH_PATH}")

    # ── Gmail Watcher ─────────────────────────────────────────────────────────
    if ENABLE_GMAIL:
        gmail_watcher = GmailWatcher(vault_path=VAULT_PATH, poll_interval_seconds=120, dry_run=DRY_RUN)
        t = WatcherThread(gmail_watcher, "GmailWatcher")
        threads.append(t)
        t.start()
        logger.info("GmailWatcher started.")

    # ── LinkedIn Watcher ──────────────────────────────────────────────────────
    if ENABLE_LINKEDIN:
        li_watcher = LinkedInWatcher(vault_path=VAULT_PATH, poll_interval_seconds=300, dry_run=DRY_RUN)
        t = WatcherThread(li_watcher, "LinkedInWatcher")
        threads.append(t)
        t.start()
        logger.info("LinkedInWatcher started.")

    # ── Inbox Monitor ─────────────────────────────────────────────────────────
    inbox_monitor = InboxMonitor(VAULT_PATH, auto_trigger=AUTO_TRIGGER_CLAUDE)
    inbox_monitor.start()

    if not threads:
        logger.warning("No watchers enabled. Set ENABLE_FILESYSTEM=true or ENABLE_GMAIL=true.")

    print_status(threads)

    # Keep the main thread alive and print periodic status
    try:
        while True:
            time.sleep(300)  # Print status every 5 minutes
            print_status(threads)

            # Check if all watcher threads have died
            alive = [t for t in threads if t.is_alive()]
            if threads and not alive:
                logger.critical("All watcher threads have died. Exiting.")
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Orchestrator shutting down (KeyboardInterrupt).")
        for t in threads:
            if hasattr(t, "_watcher"):
                t._watcher.stop()
        logger.info("Orchestrator stopped.")


if __name__ == "__main__":
    main()
