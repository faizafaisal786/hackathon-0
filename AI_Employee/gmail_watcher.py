"""
Gmail Watcher — Silver Tier
=============================
Watches Gmail inbox via IMAP, converts unread emails into task files
in AI_Employee_Vault/Inbox/ for the AI Employee pipeline to process.

How it works:
  1. Connect to Gmail via IMAP (SSL)
  2. Fetch all UNSEEN emails
  3. Convert each email → task .md file in Inbox/
  4. Mark email as READ so it is not processed again
  5. Sleep for interval, then repeat

Required .env variables:
  GMAIL_USER=you@gmail.com
  GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

Gmail setup (one-time):
  1. Google Account -> Security -> 2-Step Verification -> ON
  2. Google Account -> Security -> App Passwords
  3. Create App Password for "Mail"
  4. Paste 16-char password into GMAIL_APP_PASSWORD

Usage:
  python gmail_watcher.py              # Single check and exit
  python gmail_watcher.py --loop       # Continuous monitoring (60s interval)
  python gmail_watcher.py --loop 30    # Custom interval (30 seconds)
  python gmail_watcher.py --test       # Test credentials only (no file creation)
"""

import sys
import time
import imaplib
import email
import re
import json
from datetime import datetime
from pathlib import Path
from email.header import decode_header
from email.utils import parseaddr

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

import os

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"
INBOX = VAULT / "Inbox"
LOGS  = VAULT / "Logs"

IMAP_HOST    = "imap.gmail.com"
IMAP_PORT    = 993
MAX_EMAILS   = 20   # Max emails to fetch per pass (safety limit)
MAX_BODY_LEN = 2000 # Truncate long email bodies in task files


# ══════════════════════════════════════════════════════════════════════════════
# CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════════

def _load_credentials() -> dict:
    return {
        "user":     os.getenv("GMAIL_USER", "").strip(),
        "password": os.getenv("GMAIL_APP_PASSWORD", "").strip(),
    }


def _credentials_valid(creds: dict) -> bool:
    user = creds.get("user", "")
    pwd  = creds.get("password", "")
    if not user or not pwd:
        return False
    if "your_" in user or "your_" in pwd:
        return False
    if "@" not in user:
        return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL PARSING
# ══════════════════════════════════════════════════════════════════════════════

def _decode_mime_words(text: str) -> str:
    """Decode MIME-encoded email headers (e.g. =?utf-8?b?...?=)."""
    if not text:
        return ""
    parts = decode_header(text)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("utf-8", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded).strip()


def _extract_body(msg) -> str:
    """Extract plain text body from email message."""
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition  = str(part.get("Content-Disposition", ""))

            if content_type == "text/plain" and "attachment" not in disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body    = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception:
                    continue
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body    = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            body = ""

    # Clean up whitespace
    body = re.sub(r"\r\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    return body


def _parse_email(raw_email: bytes) -> dict:
    """Parse raw email bytes into a structured dict."""
    msg = email.message_from_bytes(raw_email)

    subject  = _decode_mime_words(msg.get("Subject", "(No Subject)"))
    from_raw = msg.get("From", "unknown@unknown.com")
    date_raw = msg.get("Date", "")

    # Parse sender
    sender_name, sender_addr = parseaddr(from_raw)
    sender_name = _decode_mime_words(sender_name) or sender_addr

    body = _extract_body(msg)

    # Detect channel hint from subject
    subject_upper = subject.upper()
    if any(kw in subject_upper for kw in ("LINKEDIN", "POST", "PUBLISH")):
        channel = "LinkedIn"
    elif any(kw in subject_upper for kw in ("WHATSAPP", "WA ", "WHATS")):
        channel = "WhatsApp"
    elif any(kw in subject_upper for kw in ("URGENT", "ASAP", "CRITICAL")):
        channel = "Email"
        priority = "High"
    else:
        channel = "Email"

    priority = "High" if any(kw in subject_upper for kw in ("URGENT", "ASAP", "CRITICAL")) else "Normal"

    return {
        "subject":     subject,
        "sender_name": sender_name,
        "sender_addr": sender_addr,
        "date":        date_raw,
        "body":        body,
        "channel":     channel,
        "priority":    priority,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TASK FILE CREATION
# ══════════════════════════════════════════════════════════════════════════════

def _safe_filename(text: str, max_len: int = 40) -> str:
    """Convert text to a safe filename slug."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text.strip())
    return text[:max_len]


def _create_task_file(parsed: dict, email_index: int) -> Path:
    """Write parsed email as a task .md file in Inbox/."""
    INBOX.mkdir(parents=True, exist_ok=True)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subject = _safe_filename(parsed["subject"])
    filename    = f"EMAIL_{timestamp}_{safe_subject}.md"

    # Truncate long bodies
    body = parsed["body"]
    if len(body) > MAX_BODY_LEN:
        body = body[:MAX_BODY_LEN] + f"\n\n[... truncated at {MAX_BODY_LEN} chars]"

    content = f"""# Email Task — {parsed['subject']}

## Metadata

| Field    | Value |
|----------|-------|
| From     | {parsed['sender_name']} <{parsed['sender_addr']}> |
| Subject  | {parsed['subject']} |
| Date     | {parsed['date']} |
| Channel  | {parsed['channel']} |
| Priority | {parsed['priority']} |
| Source   | Gmail Watcher |

## Message

{body}

## Instructions

Reply to this email professionally.
To: {parsed['sender_addr']}
Subject: Re: {parsed['subject']}
"""

    task_path = INBOX / filename
    task_path.write_text(content, encoding="utf-8")
    return task_path


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def _log(event: str, details: str, success: bool = True):
    """Append event to today's Gmail watcher log."""
    LOGS.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS / f"gmail_watcher_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []

    entries.append({
        "event":     event,
        "details":   details,
        "success":   success,
        "timestamp": datetime.now().isoformat(),
    })

    log_file.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════════════════════
# IMAP OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _connect(creds: dict) -> imaplib.IMAP4_SSL:
    """Connect and login to Gmail IMAP."""
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(creds["user"], creds["password"])
    return mail


def watch_once(creds: dict) -> int:
    """
    Single pass: fetch UNSEEN emails, create task files, mark as READ.
    Returns number of task files created.
    """
    created = 0

    try:
        mail = _connect(creds)
        mail.select("INBOX")

        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            print("  [Gmail] Could not search inbox.")
            mail.logout()
            return 0

        email_ids = messages[0].split()

        if not email_ids:
            print("  [Gmail] No new emails.")
            mail.logout()
            return 0

        # Limit per pass
        email_ids = email_ids[:MAX_EMAILS]
        print(f"  [Gmail] Found {len(email_ids)} unread email(s)...")

        for i, email_id in enumerate(email_ids, 1):
            try:
                # Fetch email
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                parsed    = _parse_email(raw_email)

                # Create task file
                task_path = _create_task_file(parsed, i)
                print(f"  [Gmail] [{i}] Task created: {task_path.name}")
                print(f"          From: {parsed['sender_addr']}")
                print(f"          Subject: {parsed['subject'][:60]}")

                # Mark as READ so it won't be processed again
                mail.store(email_id, "+FLAGS", "\\Seen")

                _log(
                    "EMAIL_FETCHED",
                    f"from={parsed['sender_addr']} subject={parsed['subject'][:60]}",
                )
                created += 1

            except Exception as e:
                print(f"  [Gmail] [ERROR] Email {email_id}: {e}")
                _log("FETCH_ERROR", str(e), success=False)

        mail.logout()

    except imaplib.IMAP4.error as e:
        msg = f"IMAP auth error: {e}"
        print(f"  [Gmail] [ERROR] {msg}")
        print("  [Gmail] Check GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        _log("AUTH_ERROR", msg, success=False)

    except ConnectionRefusedError:
        msg = "Connection refused — check internet connection"
        print(f"  [Gmail] [ERROR] {msg}")
        _log("CONNECTION_ERROR", msg, success=False)

    except Exception as e:
        msg = f"Unexpected error: {type(e).__name__}: {e}"
        print(f"  [Gmail] [ERROR] {msg}")
        _log("ERROR", msg, success=False)

    return created


def watch_loop(creds: dict, interval: int = 60):
    """Continuous loop: check Gmail every N seconds."""
    print("=" * 50)
    print("  GMAIL WATCHER — Monitoring Inbox")
    print(f"  Account:  {creds['user']}")
    print(f"  Interval: {interval}s")
    print("  Press Ctrl+C to stop")
    print("=" * 50)

    _log("WATCHER_START", f"interval={interval}s user={creds['user']}")

    try:
        while True:
            print(f"\n  [{time.strftime('%H:%M:%S')}] Checking Gmail...")
            created = watch_once(creds)

            if created > 0:
                print(f"  [{time.strftime('%H:%M:%S')}] {created} task(s) created in Inbox/")
            else:
                print(f"  [{time.strftime('%H:%M:%S')}] Inbox clear.")

            print(f"  Next check in {interval}s...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n  Gmail Watcher stopped.")
        _log("WATCHER_STOP", "Stopped by user (Ctrl+C)")


def test_credentials(creds: dict):
    """Test Gmail credentials without fetching or creating any files."""
    print("=" * 50)
    print("  GMAIL WATCHER — Credential Test")
    print("=" * 50)
    print(f"\n  GMAIL_USER:         {creds['user'] or '(not set)'}")
    pwd_preview = creds['password'][:4] + "****" if creds['password'] else "(not set)"
    print(f"  GMAIL_APP_PASSWORD: {pwd_preview}")
    print(f"  Credentials valid:  {_credentials_valid(creds)}")

    if not _credentials_valid(creds):
        print("\n  [FAIL] Set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        print("  Get App Password: Google Account -> Security -> App Passwords")
        return

    print("\n  Connecting to Gmail IMAP...")
    try:
        mail = _connect(creds)
        mail.select("INBOX")
        status, messages = mail.search(None, "UNSEEN")
        count = len(messages[0].split()) if messages[0] else 0
        mail.logout()
        print(f"  [PASS] Connected successfully!")
        print(f"  [PASS] Unread emails: {count}")
        print(f"  [PASS] Vault Inbox/: {INBOX}")
    except Exception as e:
        print(f"  [FAIL] {e}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    creds = _load_credentials()
    args  = sys.argv[1:]

    # Test mode
    if "--test" in args:
        test_credentials(creds)
        return

    # Validate credentials
    if not _credentials_valid(creds):
        print("[Gmail Watcher] ERROR: Gmail credentials not set in .env")
        print("  Set GMAIL_USER and GMAIL_APP_PASSWORD")
        print("  Get App Password: Google Account -> Security -> App Passwords")
        print()
        print("  To test: python gmail_watcher.py --test")
        sys.exit(1)

    # Loop mode
    if "--loop" in args:
        interval = 60
        idx = args.index("--loop")
        if idx + 1 < len(args):
            try:
                interval = int(args[idx + 1])
            except ValueError:
                pass
        watch_loop(creds, interval)
        return

    # Single pass
    print("=" * 50)
    print("  GMAIL WATCHER — Single Pass")
    print(f"  Account: {creds['user']}")
    print("=" * 50)
    created = watch_once(creds)
    if created == 0:
        print("  No new emails.")
    else:
        print(f"  Done. {created} task file(s) created in Inbox/")


if __name__ == "__main__":
    main()
