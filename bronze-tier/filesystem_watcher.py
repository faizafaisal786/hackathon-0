"""
filesystem_watcher.py — Bronze Tier Watcher Script
====================================================
Watches the /Inbox folder for new files and automatically creates
action items in /Needs_Action for Claude Code to process.

Setup:
    pip install watchdog

Usage:
    python filesystem_watcher.py
    python filesystem_watcher.py --vault-path /path/to/vault
    python filesystem_watcher.py --dry-run
"""

import os
import sys
import time
import shutil
import logging
import argparse
from pathlib import Path
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ─── Config ──────────────────────────────────────────────────────────────────

DEFAULT_VAULT_PATH = Path(__file__).parent  # Same folder as this script
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

IGNORE_EXTENSIONS = {".tmp", ".part", ".crdownload", ".py", ".md"}
IGNORE_PREFIXES = {".", "_", "~"}

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("FileSystemWatcher")


# ─── Event Handler ───────────────────────────────────────────────────────────

class InboxHandler(FileSystemEventHandler):
    """Handles new file events in the /Inbox folder."""

    def __init__(self, vault_path: Path, dry_run: bool = False):
        self.vault_path = vault_path
        self.inbox = vault_path / "Inbox"
        self.needs_action = vault_path / "Needs_Action"
        self.logs_dir = vault_path / "Logs"
        self.dry_run = dry_run

        # Ensure required folders exist
        self.needs_action.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        logger.info(f"Watching: {self.inbox}")
        if dry_run:
            logger.warning("DRY RUN MODE — no files will be moved or created")

    def on_created(self, event):
        if event.is_directory:
            return

        source = Path(event.src_path)

        # Skip ignored files
        if source.suffix.lower() in IGNORE_EXTENSIONS:
            return
        if source.name[0] in IGNORE_PREFIXES:
            return

        logger.info(f"New file detected: {source.name}")
        self._process_file(source)

    def _process_file(self, source: Path):
        """Move file to Needs_Action and create a metadata .md action file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_filename = f"FILE_{timestamp}_{source.name}"
        dest = self.needs_action / dest_filename
        meta_path = self.needs_action / f"ACTION_{timestamp}_{source.stem}.md"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would move: {source.name} → Needs_Action/{dest_filename}")
            logger.info(f"[DRY RUN] Would create: {meta_path.name}")
            return

        try:
            # Copy file to Needs_Action (keep original in Inbox until processed)
            shutil.copy2(source, dest)
            logger.info(f"Copied to Needs_Action: {dest_filename}")

            # Create metadata/action markdown file
            self._create_action_file(source, dest, meta_path)

            # Log the action
            self._log_action(source, dest)

        except Exception as e:
            logger.error(f"Failed to process {source.name}: {e}")

    def _create_action_file(self, source: Path, dest: Path, meta_path: Path):
        """Create a Markdown action file for Claude to process."""
        now = datetime.now().isoformat()
        file_size = source.stat().st_size if source.exists() else 0
        size_str = self._format_size(file_size)

        content = f"""---
type: file_drop
original_name: {source.name}
destination: Needs_Action/{dest.name}
size: {size_str}
received: {now}
priority: normal
status: pending
---

# New File: {source.name}

A new file was dropped into the Inbox and is awaiting processing.

## File Details
- **Name**: `{source.name}`
- **Size**: {size_str}
- **Received**: {now}
- **Moved to**: `Needs_Action/{dest.name}`

## Suggested Actions
- [ ] Review file content
- [ ] Determine action required (reply, archive, forward, process)
- [ ] Move this file to `/Done` when complete

## Notes
> Add any notes here after reviewing.
"""
        meta_path.write_text(content, encoding="utf-8")
        logger.info(f"Created action file: {meta_path.name}")

    def _log_action(self, source: Path, dest: Path):
        """Append a JSON log entry to today's log file."""
        import json
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"{today}.json"

        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": "file_received",
            "actor": "filesystem_watcher",
            "source": str(source.name),
            "destination": str(dest.name),
            "result": "success"
        }

        # Append to log file (one JSON object per line)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / 1024**2:.1f} MB"


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Employee File System Watcher (Bronze Tier)")
    parser.add_argument(
        "--vault-path",
        type=Path,
        default=DEFAULT_VAULT_PATH,
        help="Path to your Obsidian vault (default: same folder as this script)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=DRY_RUN,
        help="Log actions without actually moving files"
    )
    args = parser.parse_args()

    vault_path = args.vault_path.resolve()
    inbox_path = vault_path / "Inbox"

    if not vault_path.exists():
        logger.error(f"Vault path not found: {vault_path}")
        sys.exit(1)

    if not inbox_path.exists():
        logger.info(f"Creating Inbox folder: {inbox_path}")
        inbox_path.mkdir(parents=True)

    event_handler = InboxHandler(vault_path=vault_path, dry_run=args.dry_run)
    observer = Observer()
    observer.schedule(event_handler, str(inbox_path), recursive=False)
    observer.start()

    logger.info("=" * 50)
    logger.info("AI Employee File Watcher — Bronze Tier")
    logger.info(f"Vault : {vault_path}")
    logger.info(f"Inbox : {inbox_path}")
    logger.info("Drop files into /Inbox to trigger action items.")
    logger.info("Press Ctrl+C to stop.")
    logger.info("=" * 50)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()

    observer.join()
    logger.info("Watcher stopped.")


if __name__ == "__main__":
    main()
