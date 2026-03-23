"""
base_watcher.py — Abstract base class for all Silver/Gold/Platinum tier watchers.

All watchers inherit from BaseWatcher and implement the `poll()` and `process_item()`
methods. The base class handles logging, vault writing, and error recovery.
"""

import os
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def setup_logger(name: str, log_file: Path, level: int = logging.INFO) -> logging.Logger:
    """Configure and return a named logger that writes to file and stdout."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # File handler
    log_file.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger


class BaseWatcher(ABC):
    """
    Abstract base class for all watchers.

    Subclasses must implement:
        - poll() -> list[Any]: Fetch new items from the source
        - process_item(item) -> Optional[str]: Convert item to vault markdown content
        - get_item_filename(item) -> str: Generate a filename for the item

    Subclasses may override:
        - on_start(): Called once when the watcher starts
        - on_stop(): Called once when the watcher stops
        - on_error(error): Called when poll() raises an exception
    """

    def __init__(
        self,
        vault_path: str,
        inbox_subdir: str = "Inbox",
        poll_interval_seconds: int = 60,
        dry_run: bool = False,
    ):
        self.vault_path = Path(vault_path)
        self.inbox_path = self.vault_path / inbox_subdir
        self.logs_path = self.vault_path / "Logs"
        self.poll_interval = poll_interval_seconds
        self.dry_run = dry_run
        self._running = False

        # Ensure directories exist
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

        # Setup logger
        log_file = self.logs_path / f"{self.__class__.__name__.lower()}.log"
        self.logger = setup_logger(self.__class__.__name__, log_file)

        if self.dry_run:
            self.logger.info("DRY RUN MODE — no files will be written to vault")

    # ------------------------------------------------------------------
    # Abstract methods — must be implemented by subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def poll(self) -> list[Any]:
        """
        Fetch new items from the external source.

        Returns:
            List of raw items (emails, messages, events, etc.)
        """
        ...

    @abstractmethod
    def process_item(self, item: Any) -> Optional[str]:
        """
        Convert a raw item into Obsidian-flavored markdown.

        Args:
            item: Raw item from poll()

        Returns:
            Markdown string to write to vault, or None to skip this item.
        """
        ...

    @abstractmethod
    def get_item_filename(self, item: Any) -> str:
        """
        Generate a unique filename for a vault item.

        Args:
            item: Raw item from poll()

        Returns:
            Filename string (without path), e.g. "email_abc123_2026-03-13.md"
        """
        ...

    # ------------------------------------------------------------------
    # Optional hooks
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """Called once before the main loop begins."""
        pass

    def on_stop(self) -> None:
        """Called once after the main loop ends."""
        pass

    def on_error(self, error: Exception) -> None:
        """Called when poll() raises an exception. Default: log and continue."""
        self.logger.error(f"Poll error: {type(error).__name__}: {error}", exc_info=True)

    # ------------------------------------------------------------------
    # Core run loop
    # ------------------------------------------------------------------

    def write_to_vault(self, filename: str, content: str) -> Path:
        """
        Write a markdown file to the Inbox folder.

        Args:
            filename: Target filename (basename only)
            content: Markdown content to write

        Returns:
            Path to the written file.
        """
        target = self.inbox_path / filename
        if target.exists():
            # Avoid duplicates — add a counter suffix
            stem = target.stem
            suffix = target.suffix
            counter = 1
            while target.exists():
                target = self.inbox_path / f"{stem}_{counter}{suffix}"
                counter += 1

        if not self.dry_run:
            target.write_text(content, encoding="utf-8")
            self.logger.info(f"Written to vault: {target.name}")
        else:
            self.logger.info(f"[DRY RUN] Would write: {target.name}")

        return target

    def log_action(self, action: str, detail: str, outcome: str = "success") -> None:
        """Append a structured action log entry."""
        entry = (
            f"{datetime.now().isoformat()} | {action} | {detail} | {outcome}\n"
        )
        log_file = self.logs_path / "agent.log"
        if not self.dry_run:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)

    def run(self) -> None:
        """Start the watcher loop. Blocks until stop() is called or KeyboardInterrupt."""
        self.logger.info(
            f"Starting {self.__class__.__name__} | vault={self.vault_path} "
            f"| interval={self.poll_interval}s | dry_run={self.dry_run}"
        )
        self._running = True

        try:
            self.on_start()
            while self._running:
                self._tick()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user.")
        finally:
            self._running = False
            self.on_stop()
            self.logger.info(f"Stopped {self.__class__.__name__}.")

    def stop(self) -> None:
        """Signal the run loop to exit after the current poll."""
        self._running = False

    def _tick(self) -> None:
        """Single poll cycle: fetch items, process, write to vault."""
        try:
            items = self.poll()
            self.logger.debug(f"Polled {len(items)} items.")
            for item in items:
                try:
                    content = self.process_item(item)
                    if content is None:
                        continue
                    filename = self.get_item_filename(item)
                    self.write_to_vault(filename, content)
                    self.log_action(
                        action=f"{self.__class__.__name__}.process_item",
                        detail=filename,
                        outcome="success",
                    )
                except Exception as item_err:
                    self.logger.error(
                        f"Error processing item: {item_err}", exc_info=True
                    )
                    self.log_action(
                        action=f"{self.__class__.__name__}.process_item",
                        detail=str(item),
                        outcome=f"error: {item_err}",
                    )
        except Exception as poll_err:
            self.on_error(poll_err)
