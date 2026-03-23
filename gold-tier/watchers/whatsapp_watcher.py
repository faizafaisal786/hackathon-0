"""
whatsapp_watcher.py — Monitors WhatsApp Web for new messages using Playwright.

Uses browser automation to watch WhatsApp Web for unread messages,
then deposits them into the vault Inbox/ for Claude to triage.

IMPORTANT:
    - Keep your phone connected and WhatsApp Web session active
    - This watcher requires an initial QR code scan in the browser
    - After initial scan, session is cached in a Playwright profile
    - WhatsApp's Terms of Service apply — use responsibly

Environment variables (via .env):
    VAULT_PATH             — Absolute path to vault root
    WHATSAPP_PROFILE_DIR   — Path to store Playwright browser profile (default: ~/.whatsapp_profile)
    WHATSAPP_CONTACTS      — JSON list of contact names to monitor, e.g. '["Alice","Bob"]'
                             Empty = monitor all chats
    POLL_INTERVAL          — Seconds between checks (default: 60)
    DRY_RUN                — If "true", log but don't write files
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeout

from base_watcher import BaseWatcher

load_dotenv()

WHATSAPP_URL = "https://web.whatsapp.com"


class WhatsAppMessage:
    """Value object for a single WhatsApp message."""

    def __init__(
        self,
        msg_id: str,
        contact: str,
        chat_name: str,
        content: str,
        timestamp: str,
        is_group: bool = False,
    ):
        self.id = msg_id
        self.contact = contact
        self.chat_name = chat_name
        self.content = content
        self.timestamp = timestamp
        self.is_group = is_group
        self.received_at = datetime.now().isoformat()


class WhatsAppWatcher(BaseWatcher):
    """
    Playwright-based WhatsApp Web watcher.
    Monitors specified chats for new unread messages and deposits them in vault Inbox/.
    """

    WHATSAPP_READY_SELECTOR = 'div[data-testid="chat-list"]'
    UNREAD_BADGE_SELECTOR = 'span[data-testid="icon-unread-count"]'
    CHAT_ITEM_SELECTOR = 'div[data-testid="cell-frame-container"]'

    def __init__(self, vault_path: str, **kwargs):
        super().__init__(vault_path, **kwargs)
        self.profile_dir = os.getenv(
            "WHATSAPP_PROFILE_DIR",
            str(Path.home() / ".whatsapp_playwright_profile"),
        )
        contacts_env = os.getenv("WHATSAPP_CONTACTS", "[]")
        try:
            self.monitored_contacts: list[str] = json.loads(contacts_env)
        except json.JSONDecodeError:
            self.monitored_contacts = []

        self._seen_ids: set[str] = self._load_seen_ids()
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None

    def on_start(self) -> None:
        self.logger.info("Launching Playwright for WhatsApp Web...")
        self._playwright = sync_playwright().start()

        # Persistent context preserves the WhatsApp session across restarts
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.profile_dir,
            headless=False,  # Must be visible for QR code scan on first run
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        self._page = self._context.new_page()
        self._page.goto(WHATSAPP_URL, timeout=30000)

        self.logger.info(
            "WhatsApp Web loading. If this is your first run, "
            "scan the QR code in the browser window."
        )

        # Wait for the chat list to appear (up to 60 seconds for QR scan)
        try:
            self._page.wait_for_selector(
                self.WHATSAPP_READY_SELECTOR, timeout=60000
            )
            self.logger.info("WhatsApp Web ready.")
        except PWTimeout:
            self.logger.error(
                "WhatsApp Web did not load in 60 seconds. "
                "Ensure you've scanned the QR code."
            )
            raise

    def on_stop(self) -> None:
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()

    def poll(self) -> list[WhatsAppMessage]:
        """Scan WhatsApp Web for unread messages."""
        if self._page is None:
            return []

        messages = []
        try:
            # Reload chat list view
            self._page.wait_for_selector(self.WHATSAPP_READY_SELECTOR, timeout=15000)

            # Find all chats with unread badges
            chats = self._page.query_selector_all(self.CHAT_ITEM_SELECTOR)

            for chat in chats[:30]:  # Check first 30 chats
                try:
                    badge = chat.query_selector(self.UNREAD_BADGE_SELECTOR)
                    if not badge:
                        continue

                    # Get chat name
                    name_el = chat.query_selector(
                        'span[data-testid="conversation-title"] span, '
                        'span[title], div[role="gridcell"] span'
                    )
                    chat_name = name_el.inner_text().strip() if name_el else "Unknown"

                    # Filter by monitored contacts if configured
                    if self.monitored_contacts and chat_name not in self.monitored_contacts:
                        continue

                    # Click on the chat to read messages
                    chat.click()
                    time.sleep(1)  # Allow messages to load

                    # Extract unread messages
                    msgs = self._extract_unread_messages(chat_name)
                    messages.extend(msgs)

                    # Press Escape to go back to chat list
                    self._page.keyboard.press("Escape")
                    time.sleep(0.5)

                except Exception as e:
                    self.logger.debug(f"Error processing chat: {e}")

        except PWTimeout:
            self.logger.warning("WhatsApp Web timed out during poll.")
        except Exception as e:
            raise RuntimeError(f"WhatsApp poll failed: {e}") from e

        self._save_seen_ids()
        return messages

    def _extract_unread_messages(self, chat_name: str) -> list[WhatsAppMessage]:
        """Extract unread messages from the currently open chat."""
        messages = []
        try:
            # Find unread message markers
            unread_divider = self._page.query_selector(
                'div[data-testid="msg-unread"]'
            )

            msg_elements = self._page.query_selector_all(
                'div[data-testid="msg-container"], div[class*="message-in"]'
            )

            in_unread = unread_divider is None  # If no divider, treat all as potential unread

            for el in msg_elements[-20:]:  # Last 20 messages
                try:
                    # Generate a stable ID from content + timestamp
                    text_el = el.query_selector(
                        'span[data-testid="msg-text"], span.selectable-text'
                    )
                    time_el = el.query_selector(
                        'span[data-testid="msg-meta"], span[class*="time"]'
                    )

                    content = text_el.inner_text().strip() if text_el else ""
                    timestamp = time_el.inner_text().strip() if time_el else ""

                    if not content:
                        continue

                    # Create a pseudo-ID from content hash
                    import hashlib
                    msg_id = hashlib.md5(
                        f"{chat_name}:{content}:{timestamp}".encode()
                    ).hexdigest()[:12]

                    if msg_id in self._seen_ids:
                        continue

                    self._seen_ids.add(msg_id)

                    is_group = self._page.query_selector(
                        'span[data-testid="group-icon"]'
                    ) is not None

                    contact_el = el.query_selector(
                        'span[data-testid="author"], span[aria-label*="from"]'
                    )
                    contact = contact_el.inner_text().strip() if contact_el else chat_name

                    msg = WhatsAppMessage(
                        msg_id=msg_id,
                        contact=contact,
                        chat_name=chat_name,
                        content=content,
                        timestamp=timestamp,
                        is_group=is_group,
                    )
                    messages.append(msg)
                except Exception:
                    pass

        except Exception as e:
            self.logger.debug(f"Error extracting messages from {chat_name}: {e}")

        return messages

    def process_item(self, item: WhatsAppMessage) -> Optional[str]:
        """Convert a WhatsApp message to vault markdown."""
        chat_type = "Group Chat" if item.is_group else "Direct Message"
        return f"""---
source: whatsapp
message_id: "{item.id}"
contact: "{item.contact}"
chat: "{item.chat_name}"
chat_type: {chat_type}
received: {item.received_at}
status: unread
priority: unset
tags: [inbox, whatsapp, {'group' if item.is_group else 'direct'}]
---

# WhatsApp {chat_type}: {item.contact}

**From:** {item.contact}
**Chat:** {item.chat_name} ({chat_type})
**Time:** {item.timestamp}
**Received:** {item.received_at}

---

## Message

{item.content}

---

## Action Required

> Claude: Triage this WhatsApp message per Company_Handbook.md.
> Direct messages from customers/leads: treat as P1.
> Group chat messages: treat as P2 unless urgent.
> Draft a WhatsApp reply in Needs_Action/ if response required (requires approval to send).
"""

    def get_item_filename(self, item: WhatsAppMessage) -> str:
        date_prefix = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_contact = re.sub(r'[\\/*?:"<>| ]', "_", item.contact)[:30]
        return f"whatsapp_{date_prefix}_{safe_contact}_{item.id}.md"

    def _load_seen_ids(self) -> set[str]:
        state_file = self.logs_path / "whatsapp_seen_ids.json"
        if state_file.exists():
            try:
                return set(json.loads(state_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return set()

    def _save_seen_ids(self) -> None:
        state_file = self.logs_path / "whatsapp_seen_ids.json"
        if not self.dry_run:
            state_file.write_text(json.dumps(list(self._seen_ids)[-5000:]))  # Keep last 5000


if __name__ == "__main__":
    vault = os.getenv("VAULT_PATH", str(Path(__file__).parent.parent))
    interval = int(os.getenv("POLL_INTERVAL", "60"))
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    watcher = WhatsAppWatcher(
        vault_path=vault,
        poll_interval_seconds=interval,
        dry_run=dry_run,
    )
    watcher.run()
