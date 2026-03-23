"""
filesystem_watcher.py — Monitors a local drop folder and deposits new files into the vault Inbox.

Drop any file into the WATCH_PATH folder; this watcher will copy it (as a markdown wrapper
or raw content) into the vault Inbox/ for Claude to process via /process-inbox.

Environment variables (via .env):
    VAULT_PATH    — Absolute path to vault root
    WATCH_PATH    — Folder to monitor (default: ~/Desktop/AI_Inbox)
    POLL_INTERVAL — Seconds between checks (default: 10)
    DRY_RUN       — If "true", log but don't write (default: false)
"""

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

from base_watcher import BaseWatcher

load_dotenv()

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".html", ".xml", ".log"
}


def file_hash(path: Path) -> str:
    """Compute MD5 hash of a file for deduplication."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class FilesystemWatcher(BaseWatcher):
    """
    Monitors a local folder (WATCH_PATH) for new files.

    Text files: wrapped in markdown with frontmatter and full content
    Binary/other files: wrapped in markdown with file metadata only
    """

    def __init__(self, vault_path: str, watch_path: str, **kwargs):
        super().__init__(vault_path, **kwargs)
        self.watch_path = Path(watch_path)
        self.watch_path.mkdir(parents=True, exist_ok=True)
        self._seen_hashes: set[str] = set()
        self._pending_files: list[Path] = []

        # Watchdog observer for immediate event-driven detection
        self._observer = Observer()
        handler = _DropFolderHandler(self)
        self._observer.schedule(handler, str(self.watch_path), recursive=False)

    def on_start(self) -> None:
        self.logger.info(f"Watching drop folder: {self.watch_path}")
        self._observer.start()

    def on_stop(self) -> None:
        self._observer.stop()
        self._observer.join()

    def poll(self) -> list[Path]:
        """Return any files queued by the watchdog event handler."""
        pending = list(self._pending_files)
        self._pending_files.clear()
        return pending

    def queue_file(self, path: Path) -> None:
        """Called by the watchdog handler when a new file appears."""
        if not path.is_file():
            return
        fhash = file_hash(path)
        if fhash in self._seen_hashes:
            self.logger.debug(f"Duplicate file skipped: {path.name}")
            return
        self._seen_hashes.add(fhash)
        self._pending_files.append(path)
        self.logger.info(f"Queued new file: {path.name}")

    def process_item(self, item: Path) -> Optional[str]:
        """Wrap a local file as Obsidian markdown."""
        now = datetime.now().isoformat()
        size_bytes = item.stat().st_size
        ext = item.suffix.lower()

        if ext in SUPPORTED_TEXT_EXTENSIONS:
            try:
                raw_content = item.read_text(encoding="utf-8", errors="replace")
                # Truncate to 5000 chars to keep vault files manageable
                if len(raw_content) > 5000:
                    raw_content = raw_content[:5000] + "\n\n[...truncated — original file preserved in drop folder...]"
                content_block = f"```\n{raw_content}\n```"
            except OSError:
                content_block = "*Could not read file content.*"
        else:
            content_block = f"*Binary file ({ext}) — content not displayed. Original file: `{item}`*"

        return f"""---
source: filesystem
original_path: "{item}"
filename: "{item.name}"
extension: "{ext}"
size_bytes: {size_bytes}
deposited: {now}
status: unread
priority: unset
tags: [inbox, file-drop]
---

# File Drop: {item.name}

**Original Path:** `{item}`
**Size:** {size_bytes:,} bytes
**Deposited:** {now}

---

## Content

{content_block}

---

## Action Required

> Claude: Review this dropped file. Determine its purpose and priority per Company_Handbook.md.
> Create a task in Needs_Action/ if action is required.
"""

    def get_item_filename(self, item: Path) -> str:
        date_prefix = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_name = item.stem.replace(" ", "_")[:40]
        return f"file_{date_prefix}_{safe_name}.md"


class _DropFolderHandler(FileSystemEventHandler):
    """Watchdog event handler that queues new files for the watcher."""

    def __init__(self, watcher: FilesystemWatcher):
        super().__init__()
        self._watcher = watcher

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory:
            self._watcher.queue_file(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        if not event.is_directory:
            self._watcher.queue_file(Path(event.dest_path))


if __name__ == "__main__":
    vault = os.getenv("VAULT_PATH", str(Path(__file__).parent.parent))
    watch = os.getenv("WATCH_PATH", str(Path.home() / "Desktop" / "AI_Inbox"))
    interval = int(os.getenv("POLL_INTERVAL", "10"))
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    watcher = FilesystemWatcher(
        vault_path=vault,
        watch_path=watch,
        poll_interval_seconds=interval,
        dry_run=dry_run,
    )
    watcher.run()
