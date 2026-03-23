"""
gmail_watcher.py — Polls Gmail via Google API and deposits new emails into the vault Inbox.

Authentication:
    1. Create a Google Cloud project and enable Gmail API
    2. Download OAuth 2.0 credentials as 'credentials.json' (place next to this file)
    3. On first run, a browser will open for OAuth consent
    4. Token is cached in 'token.json' — do NOT commit this file

Environment variables (via .env):
    VAULT_PATH       — Absolute path to the vault root
    GMAIL_LABEL      — Gmail label to watch (default: INBOX)
    GMAIL_MAX_RESULTS — Max emails per poll (default: 10)
    POLL_INTERVAL    — Seconds between polls (default: 120)
    DRY_RUN          — If "true", log but don't write files (default: false)
"""

import base64
import email as email_lib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from base_watcher import BaseWatcher

load_dotenv()

# Gmail OAuth scope — read-only is sufficient for triage
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"


def get_gmail_service():
    """Authenticate and return an authorized Gmail API service object."""
    creds: Optional[Credentials] = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"OAuth credentials not found at {CREDENTIALS_FILE}. "
                    "Download them from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def decode_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if payload.get("mimeType", "").startswith("multipart"):
        for part in payload.get("parts", []):
            text = decode_body(part)
            if text:
                return text

    return ""


def sanitize_filename(text: str, max_len: int = 60) -> str:
    """Remove characters unsafe for filenames and truncate."""
    safe = re.sub(r'[\\/*?:"<>|]', "_", text)
    safe = safe.strip().replace(" ", "_")
    return safe[:max_len]


class GmailWatcher(BaseWatcher):
    """
    Polls Gmail for new unread emails and deposits them into the vault Inbox as markdown.

    Each email becomes a .md file with structured frontmatter and full body text,
    ready for Claude to triage via /process-inbox.
    """

    def __init__(self, vault_path: str, **kwargs):
        super().__init__(vault_path, **kwargs)
        self.label = os.getenv("GMAIL_LABEL", "INBOX")
        self.max_results = int(os.getenv("GMAIL_MAX_RESULTS", "10"))
        self._seen_ids: set[str] = self._load_seen_ids()
        self._service = None

    def on_start(self) -> None:
        self.logger.info("Authenticating with Gmail API...")
        self._service = get_gmail_service()
        self.logger.info("Gmail authentication successful.")

    def _load_seen_ids(self) -> set[str]:
        """Load already-processed message IDs from a state file."""
        state_file = self.logs_path / "gmail_seen_ids.json"
        if state_file.exists():
            try:
                return set(json.loads(state_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return set()

    def _save_seen_ids(self) -> None:
        """Persist seen message IDs to avoid re-processing."""
        state_file = self.logs_path / "gmail_seen_ids.json"
        if not self.dry_run:
            state_file.write_text(json.dumps(list(self._seen_ids)))

    def poll(self) -> list[dict]:
        """Fetch new unread emails from Gmail."""
        if self._service is None:
            return []

        try:
            result = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    labelIds=[self.label],
                    q="is:unread",
                    maxResults=self.max_results,
                )
                .execute()
            )
        except HttpError as e:
            raise RuntimeError(f"Gmail API error: {e}") from e

        messages = result.get("messages", [])
        new_messages = []

        for msg_stub in messages:
            msg_id = msg_stub["id"]
            if msg_id in self._seen_ids:
                continue
            # Fetch full message
            try:
                full_msg = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                new_messages.append(full_msg)
                self._seen_ids.add(msg_id)
            except HttpError as e:
                self.logger.warning(f"Could not fetch message {msg_id}: {e}")

        self._save_seen_ids()
        return new_messages

    def process_item(self, item: dict) -> Optional[str]:
        """Convert a Gmail message dict to Obsidian markdown."""
        headers = {
            h["name"]: h["value"]
            for h in item.get("payload", {}).get("headers", [])
        }

        msg_id = item.get("id", "unknown")
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "unknown")
        date_str = headers.get("Date", "")
        snippet = item.get("snippet", "")
        body = decode_body(item.get("payload", {}))

        # Truncate very long bodies to keep vault files manageable
        body_preview = body[:2000] + ("\n\n[...truncated...]" if len(body) > 2000 else "")

        # Parse date for frontmatter
        try:
            from email.utils import parsedate_to_datetime
            parsed_date = parsedate_to_datetime(date_str).isoformat()
        except Exception:
            parsed_date = datetime.now().isoformat()

        return f"""---
source: gmail
message_id: {msg_id}
from: "{sender}"
subject: "{subject}"
received: {parsed_date}
status: unread
priority: unset
tags: [inbox, email]
---

# Email: {subject}

**From:** {sender}
**Date:** {date_str}
**Subject:** {subject}

---

## Preview

{snippet}

---

## Body

{body_preview}

---

## Action Required

> Claude: Triage this email. Assign priority P0-P4 per Company_Handbook.md.
> Create a task in Needs_Action/ if P0-P2. Archive if P3-P4.
"""

    def get_item_filename(self, item: dict) -> str:
        headers = {
            h["name"]: h["value"]
            for h in item.get("payload", {}).get("headers", [])
        }
        subject = headers.get("Subject", "no_subject")
        msg_id = item.get("id", "unknown")[:8]
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        safe_subject = sanitize_filename(subject)
        return f"email_{date_prefix}_{safe_subject}_{msg_id}.md"


if __name__ == "__main__":
    vault = os.getenv("VAULT_PATH", str(Path(__file__).parent.parent))
    interval = int(os.getenv("POLL_INTERVAL", "120"))
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    watcher = GmailWatcher(
        vault_path=vault,
        poll_interval_seconds=interval,
        dry_run=dry_run,
    )
    watcher.run()
