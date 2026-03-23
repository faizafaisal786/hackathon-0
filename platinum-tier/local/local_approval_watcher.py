"""
local_approval_watcher.py — Approval Folder Watcher (Platinum Tier)
====================================================================
Uses watchdog to instantly detect when files arrive in /Pending_Approval/
and notifies the user (desktop notification or terminal alert).

This is LOCAL-ONLY — never runs on cloud.

Usage:
    pip install watchdog plyer
    python local/local_approval_watcher.py
"""

import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    from plyer import notification
    HAS_NOTIFIER = True
except ImportError:
    HAS_NOTIFIER = False

VAULT_PATH = Path(os.getenv("VAULT_PATH") or Path(__file__).parent.parent)
LOG_FORMAT = "%(asctime)s [LOCAL-APPROVAL] %(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("ApprovalWatcher")


def extract_frontmatter_value(content: str, key: str) -> str:
    for line in content.split("\n"):
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


class ApprovalHandler(FileSystemEventHandler):
    """Watches /Pending_Approval/ and alerts the user when approval is needed."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.pending_dir = vault_path / "Pending_Approval"
        self.alerted: set[str] = set()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix != ".md":
            return
        if path.name in self.alerted:
            return

        self.alerted.add(path.name)
        self._handle_approval_request(path)

    def _handle_approval_request(self, file: Path):
        try:
            content = file.read_text(encoding="utf-8")
        except Exception:
            return

        action = extract_frontmatter_value(content, "action")
        priority = extract_frontmatter_value(content, "priority")

        logger.info(f"APPROVAL NEEDED: {file.name} | action={action} | priority={priority}")

        # Terminal alert
        print("\n" + "=" * 60)
        print(f"  ACTION REQUIRED: {action.upper()}")
        print(f"  File: {file.name}")
        print(f"  Priority: {priority}")
        print(f"  → Move to /Approved to execute")
        print(f"  → Move to /Rejected to cancel")
        print("=" * 60 + "\n")

        # Desktop notification
        if HAS_NOTIFIER:
            try:
                notification.notify(
                    title="AI Employee: Approval Required",
                    message=f"{action.upper()} — {file.name}",
                    app_name="AI Employee",
                    timeout=10,
                )
            except Exception:
                pass  # Notification failure is non-critical


def main():
    pending_dir = VAULT_PATH / "Pending_Approval"
    pending_dir.mkdir(exist_ok=True)

    handler = ApprovalHandler(VAULT_PATH)
    observer = Observer()
    observer.schedule(handler, str(pending_dir), recursive=False)
    observer.start()

    logger.info(f"Watching /Pending_Approval/ for approval requests...")
    logger.info("Press Ctrl+C to stop.")

    # Check for existing pending files on startup
    for f in pending_dir.glob("*.md"):
        if f.stat().st_size > 0:
            handler._handle_approval_request(f)
            handler.alerted.add(f.name)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    logger.info("Approval watcher stopped.")


if __name__ == "__main__":
    main()
