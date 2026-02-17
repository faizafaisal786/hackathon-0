"""
Email Sender Module — Secure Gmail SMTP Integration
=====================================================
Sends emails via Gmail SMTP after human approval.

Security:
  - Credentials loaded from .env via python-dotenv (never hardcoded)
  - Approval status verified inside the ACTION file before sending
  - SMTP connection uses context manager (auto-cleanup on error)
  - Input validation: recipient, subject, body all checked
  - Graceful fallback to DEMO MODE when credentials missing

Required .env variables:
  GMAIL_USER=you@gmail.com
  GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx

Backward-compatible exports:
  parse_email_from_action(file_path) -> dict
  send_email(to, subject, body) -> str
"""

import os
import re
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Try python-dotenv, fall back to manual parsing
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_TIMEOUT = 30  # seconds

# Approval keywords that must be present in the file for live send
APPROVAL_KEYWORDS = ("APPROVED", "Status: APPROVED")

# Blocked patterns — never send to these (safety net)
BLOCKED_RECIPIENTS = {"test@test.com", "example@example.com", "your_email@gmail.com"}

# Max body length (prevent accidental huge emails)
MAX_BODY_LENGTH = 50_000

# Daily send limit (Gmail allows 500 for free, 2000 for Workspace)
MAX_DAILY_SENDS = 100


# ──────────────────────────────────────────────
# CREDENTIAL LOADING
# ──────────────────────────────────────────────

def _find_env_path() -> Path:
    """Find .env file in the same directory as this module."""
    return Path(__file__).parent / ".env"


def _load_credentials() -> dict:
    """
    Load Gmail credentials from .env file.
    Uses python-dotenv if available, otherwise manual parsing.
    Returns dict with GMAIL_USER and GMAIL_APP_PASSWORD.
    """
    env_path = _find_env_path()

    if _HAS_DOTENV:
        load_dotenv(env_path, override=False)
        return {
            "GMAIL_USER": os.getenv("GMAIL_USER", ""),
            "GMAIL_APP_PASSWORD": os.getenv("GMAIL_APP_PASSWORD", ""),
        }

    # Manual fallback
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config


def _is_live_mode(creds: dict) -> bool:
    """Check if we have real credentials (not placeholders)."""
    user = creds.get("GMAIL_USER", "")
    password = creds.get("GMAIL_APP_PASSWORD", "")

    if not user or not password:
        return False
    if "your_" in user or "your_" in password:
        return False
    if user in BLOCKED_RECIPIENTS:
        return False
    return True


# Keep backward compatibility
def load_env():
    """Legacy function — returns full .env as dict."""
    return _load_credentials()


# ──────────────────────────────────────────────
# ACTION FILE PARSER
# ──────────────────────────────────────────────

def parse_email_from_action(file_path: str) -> dict:
    """
    Extract email details from an ACTION_*.md file.

    Parses markdown tables and quoted body blocks:
      | Recipient | user@example.com |
      | Subject   | Meeting Note     |
      > Dear User,
      > Body text here...

    Returns:
        dict with keys: to, subject, body, channel, approved
    """
    content = Path(file_path).read_text(encoding="utf-8")

    email_data = {
        "to": None,
        "subject": None,
        "body": None,
        "channel": None,
        "approved": False,
    }

    # Channel from markdown table: | Channel | Email |
    channel_match = re.search(r"Channel\s*\|\s*(\w+)", content)
    if channel_match:
        email_data["channel"] = channel_match.group(1).strip()

    # Recipient from markdown table: | Recipient | user@example.com |
    # Support emails with dots, hyphens, underscores, plus signs
    to_match = re.search(r"Recipient\s*\|\s*([\w.+\-@]+)", content)
    if to_match:
        email_data["to"] = to_match.group(1).strip()

    # Subject from markdown table: | Subject | text here |
    subject_match = re.search(r"Subject\s*\|\s*(.+?)(?:\s*\||\s*$)", content, re.MULTILINE)
    if subject_match:
        email_data["subject"] = subject_match.group(1).strip()

    # Fallback: Subject from plain "Subject: text" line
    if not email_data["subject"]:
        subject_line = re.search(r"^Subject:\s*(.+)$", content, re.MULTILINE)
        if subject_line:
            email_data["subject"] = subject_line.group(1).strip()

    # Body: extract all ">" quoted lines (the drafted email content)
    body_lines = []
    in_body = False
    for line in content.split("\n"):
        stripped = line.strip()

        # Start capturing on any quoted line that looks like email content
        if not in_body and stripped.startswith(">"):
            text_after = stripped[1:].strip()
            # Start on greeting lines or any substantial content
            if text_after and (
                text_after.startswith(("Dear", "Hi", "Hello", "Thank", "Assalam",
                                       "Good", "Sir", "Madam", "Team", "We ", "I ",
                                       "This", "Please", "As ")) or
                len(text_after) > 10
            ):
                in_body = True

        if in_body and stripped.startswith(">"):
            body_lines.append(stripped[1:].strip())
        elif in_body and not stripped.startswith(">"):
            # Allow one blank line inside the body (paragraph break)
            if stripped == "" and body_lines and body_lines[-1] != "":
                body_lines.append("")
            elif stripped == "" and body_lines:
                break  # Second blank line = end of body
            else:
                break

    email_data["body"] = "\n".join(body_lines).strip() if body_lines else None

    # Check approval status
    for keyword in APPROVAL_KEYWORDS:
        if keyword in content:
            email_data["approved"] = True
            break

    return email_data


# ──────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────

def _validate_recipient(to: str) -> tuple[bool, str]:
    """Validate email recipient. Returns (is_valid, reason)."""
    if not to:
        return False, "Recipient is empty"
    if "@" not in to or "." not in to:
        return False, f"Invalid email format: {to}"
    if to.lower() in BLOCKED_RECIPIENTS:
        return False, f"Blocked recipient: {to}"
    return True, "OK"


def _validate_body(body: str) -> tuple[bool, str]:
    """Validate email body. Returns (is_valid, reason)."""
    if not body:
        return False, "Body is empty"
    if len(body) > MAX_BODY_LENGTH:
        return False, f"Body too long ({len(body)} chars, max {MAX_BODY_LENGTH})"
    return True, "OK"


# ──────────────────────────────────────────────
# RATE LIMITING
# ──────────────────────────────────────────────

def _check_daily_limit() -> tuple[bool, int]:
    """Check if daily send limit has been reached. Returns (allowed, count)."""
    logs_dir = Path(__file__).parent / "AI_Employee_Vault" / "Logs"
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"email_{today}.json"

    if not log_file.exists():
        return True, 0

    try:
        entries = json.loads(log_file.read_text(encoding="utf-8"))
        sent_count = sum(1 for e in entries if e.get("event") in ("SENT", "DEMO_SEND"))
        if sent_count >= MAX_DAILY_SENDS:
            return False, sent_count
        return True, sent_count
    except (json.JSONDecodeError, KeyError):
        return True, 0


# ──────────────────────────────────────────────
# SEND EMAIL
# ──────────────────────────────────────────────

def send_email(to: str, subject: str, body: str) -> str:
    """
    Send email via Gmail SMTP with full safety checks.

    Flow:
      1. Validate recipient and body
      2. Load credentials from .env
      3. If no credentials -> DEMO MODE (print, don't send)
      4. If credentials exist -> connect SMTP, send, close

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body (plain text)

    Returns:
        Status string describing what happened.
    """
    # ── Step 1: Validate inputs ──
    valid, reason = _validate_recipient(to)
    if not valid:
        _log_send("VALIDATION_FAILED", to, subject, reason)
        return f"Email not sent: {reason}"

    valid, reason = _validate_body(body)
    if not valid:
        _log_send("VALIDATION_FAILED", to, subject, reason)
        return f"Email not sent: {reason}"

    if not subject:
        subject = "(No Subject)"

    # ── Step 1b: Daily rate limit ──
    allowed, count = _check_daily_limit()
    if not allowed:
        _log_send("RATE_LIMITED", to, subject, f"Daily limit reached ({count}/{MAX_DAILY_SENDS})")
        return f"Email not sent: daily limit reached ({count} sent today)"

    # ── Step 2: Load credentials ──
    creds = _load_credentials()

    # ── Step 3: DEMO MODE if no real credentials ──
    if not _is_live_mode(creds):
        print(f"[DEMO MODE] Email would be sent to: {to}")
        print(f"[DEMO MODE] Subject: {subject}")
        print(f"[DEMO MODE] Body preview: {body[:100]}...")
        _log_send("DEMO_SEND", to, subject, "No credentials - demo mode")
        return "Email sent successfully (DEMO MODE)"

    # ── Step 4: LIVE SEND via Gmail SMTP ──
    gmail_user = creds["GMAIL_USER"]
    gmail_pass = creds["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart()
    msg["From"] = gmail_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, [to], msg.as_string())

        _log_send("SENT", to, subject, "Email sent successfully")
        return "Email sent successfully"

    except smtplib.SMTPAuthenticationError:
        error = "Gmail auth failed - check GMAIL_APP_PASSWORD in .env"
        _log_send("AUTH_ERROR", to, subject, error)
        return f"Email failed: {error}"

    except smtplib.SMTPRecipientsRefused:
        error = f"Recipient refused: {to}"
        _log_send("RECIPIENT_ERROR", to, subject, error)
        return f"Email failed: {error}"

    except smtplib.SMTPException as e:
        error = f"SMTP error: {e}"
        _log_send("SMTP_ERROR", to, subject, error)
        return f"Email failed: {error}"

    except TimeoutError:
        error = f"Connection timeout ({SMTP_TIMEOUT}s)"
        _log_send("TIMEOUT", to, subject, error)
        return f"Email failed: {error}"

    except Exception as e:
        error = f"Unexpected error: {e}"
        _log_send("ERROR", to, subject, error)
        return f"Email failed: {error}"


# ──────────────────────────────────────────────
# APPROVED SEND (with file-level approval check)
# ──────────────────────────────────────────────

def send_approved_email(action_file_path: str) -> str:
    """
    Parse an ACTION file and send ONLY if it contains approval status.

    This is the safest entry point — it checks the file for
    "APPROVED" before sending anything.

    Args:
        action_file_path: Path to an ACTION_*.md file

    Returns:
        Status string.
    """
    data = parse_email_from_action(action_file_path)

    if not data["approved"]:
        return f"Email blocked: {Path(action_file_path).name} not approved"

    to = data.get("to")
    subject = data.get("subject", "(No Subject)")
    body = data.get("body", "")

    if not to or not body:
        return "Email not sent: missing recipient or body"

    return send_email(to, subject, body)


# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

def _log_send(event: str, to: str, subject: str, details: str):
    """
    Append email send event to daily log.
    Logs to AI_Employee_Vault/Logs/email_YYYY-MM-DD.json
    """
    logs_dir = Path(__file__).parent / "AI_Employee_Vault" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"email_{today}.json"

    if log_file.exists():
        entries = json.loads(log_file.read_text(encoding="utf-8"))
    else:
        entries = []

    entries.append({
        "event": event,
        "to": to,
        "subject": subject,
        "details": details,
        "timestamp": datetime.now().isoformat(),
    })

    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────
# CLI TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  EMAIL SENDER — Diagnostic Test")
    print("=" * 50)

    creds = _load_credentials()
    live = _is_live_mode(creds)

    print(f"\n  .env found:  {_find_env_path().exists()}")
    print(f"  GMAIL_USER:  {creds.get('GMAIL_USER', '(not set)')}")
    print(f"  APP_PASS:    {'****' + creds.get('GMAIL_APP_PASSWORD', '')[-4:] if creds.get('GMAIL_APP_PASSWORD') else '(not set)'}")
    print(f"  Mode:        {'LIVE' if live else 'DEMO'}")

    print(f"\n  Sending test email...")
    result = send_email("test@example.com", "Test Subject", "This is a test body.")
    print(f"  Result: {result}")

    print(f"\n  Validation tests:")
    tests = [
        ("", "empty"),
        ("notanemail", "no @"),
        ("your_email@gmail.com", "blocked"),
        ("real.user@company.com", "valid"),
    ]
    for addr, label in tests:
        ok, reason = _validate_recipient(addr)
        status = "PASS" if ok else "BLOCK"
        print(f"    [{status}] {label:12s} | {addr or '(empty)':30s} | {reason}")

    print()
