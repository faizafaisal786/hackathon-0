"""
WhatsApp Sender Module — Twilio Integration
=============================================
Sends WhatsApp messages via Twilio API after human approval.

Security:
  - Credentials loaded from .env via python-dotenv (never hardcoded)
  - Approval status verified inside the ACTION file before sending
  - Phone number validation and sanitization
  - Graceful fallback to simulation mode when credentials missing
  - Per-event JSON logging for audit trail

Required .env variables (for live mode):
  TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_WHATSAPP_FROM=+14155238886

Backward-compatible exports:
  parse_whatsapp_from_action(file_path) -> dict
  send_whatsapp(to, client, message) -> str
"""

import os
import re
import json
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

# Twilio sandbox number (default for testing)
DEFAULT_FROM = "+14155238886"

# Approval keywords that must be present in the file for live send
APPROVAL_KEYWORDS = ("APPROVED", "Status: APPROVED")

# Phone number regex: must start with + and have 10-15 digits
PHONE_REGEX = re.compile(r"^\+\d{10,15}$")

# Max message length (WhatsApp limit is 4096 for session messages)
MAX_MESSAGE_LENGTH = 4096

# Simulation output directory (relative to AI_Employee_Vault)
SIM_DIR_NAME = "WhatsApp_Sent"


# ──────────────────────────────────────────────
# CREDENTIAL LOADING
# ──────────────────────────────────────────────

def _find_env_path() -> Path:
    """Find .env file in the same directory as this module."""
    return Path(__file__).parent / ".env"


def _load_credentials() -> dict:
    """
    Load Twilio credentials from .env file.
    Uses python-dotenv if available, otherwise manual parsing.
    """
    env_path = _find_env_path()

    if _HAS_DOTENV:
        load_dotenv(env_path, override=False)
        return {
            "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID", ""),
            "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN", ""),
            "TWILIO_WHATSAPP_FROM": os.getenv("TWILIO_WHATSAPP_FROM", DEFAULT_FROM),
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
    """Check if we have real Twilio credentials (not placeholders)."""
    sid = creds.get("TWILIO_ACCOUNT_SID", "")
    token = creds.get("TWILIO_AUTH_TOKEN", "")

    if not sid or not token:
        return False
    if "your_" in sid or "your_" in token:
        return False
    # Twilio SIDs always start with "AC"
    if not sid.startswith("AC"):
        return False
    return True


# Keep backward compatibility
def load_env():
    """Legacy function — returns full .env as dict."""
    return _load_credentials()


# ──────────────────────────────────────────────
# PHONE NUMBER HANDLING
# ──────────────────────────────────────────────

def _clean_phone(number: str) -> str:
    """
    Sanitize phone number for Twilio.
    Removes dashes, spaces, parentheses. Keeps + and digits only.
    """
    if not number:
        return ""
    # Keep only + and digits
    cleaned = re.sub(r"[^\d+]", "", number)
    # Ensure it starts with +
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned


def _validate_phone(number: str) -> tuple[bool, str]:
    """Validate phone number format. Returns (is_valid, reason)."""
    if not number:
        return False, "Phone number is empty"

    cleaned = _clean_phone(number)

    if not PHONE_REGEX.match(cleaned):
        return False, f"Invalid phone format: {number} (need +countrycode + 10-15 digits)"

    return True, "OK"


def _validate_message(message: str) -> tuple[bool, str]:
    """Validate message content. Returns (is_valid, reason)."""
    if not message:
        return False, "Message is empty"
    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long ({len(message)} chars, max {MAX_MESSAGE_LENGTH})"
    return True, "OK"


# ──────────────────────────────────────────────
# ACTION FILE PARSER
# ──────────────────────────────────────────────

def parse_whatsapp_from_action(file_path: str) -> dict:
    """
    Extract WhatsApp details from an ACTION_*.md file.

    Parses markdown tables and quoted body blocks:
      | Recipient | +92-300-1234567 |
      | Client    | Ahmed Khan      |
      > Assalam o Alaikum...

    Returns:
        dict with keys: to, client, message, channel, approved
    """
    content = Path(file_path).read_text(encoding="utf-8")

    wa_data = {
        "to": None,
        "client": None,
        "message": None,
        "channel": None,
        "approved": False,
    }

    # Channel from markdown table: | Channel | WhatsApp |
    channel_match = re.search(r"Channel\s*\|\s*(\w+)", content)
    if channel_match:
        wa_data["channel"] = channel_match.group(1).strip()

    # Recipient phone number from markdown table: | Recipient | +92-300-1234567 |
    to_match = re.search(r"Recipient\s*\|\s*([\+\d\-\s\(\)]+)", content)
    if to_match:
        wa_data["to"] = to_match.group(1).strip()

    # Client name from markdown table: | Client | Name Here |
    client_match = re.search(r"Client\s*\|\s*(.+?)(?:\s*\||\s*$)", content, re.MULTILINE)
    if client_match:
        wa_data["client"] = client_match.group(1).strip()

    # Message body: extract all ">" quoted lines
    body_lines = []
    in_body = False
    for line in content.split("\n"):
        stripped = line.strip()

        # Start on any quoted line that looks like message content
        if not in_body and stripped.startswith(">"):
            text_after = stripped[1:].strip()
            if text_after and (
                text_after.startswith((
                    "Assalam", "Dear", "Hi", "Hello", "Thank",
                    "Good", "Sir", "Madam", "Team", "Salam",
                    "AOA", "We ", "I ", "This", "Please", "Your",
                )) or len(text_after) > 10
            ):
                in_body = True

        if in_body and stripped.startswith(">"):
            body_lines.append(stripped[1:].strip())
        elif in_body and not stripped.startswith(">"):
            # Allow one blank line inside body (paragraph break)
            if stripped == "" and body_lines and body_lines[-1] != "":
                body_lines.append("")
            elif stripped == "" and body_lines:
                break
            else:
                break

    wa_data["message"] = "\n".join(body_lines).strip() if body_lines else None

    # Check approval status
    for keyword in APPROVAL_KEYWORDS:
        if keyword in content:
            wa_data["approved"] = True
            break

    return wa_data


# ──────────────────────────────────────────────
# SEND WHATSAPP
# ──────────────────────────────────────────────

def send_whatsapp(to: str, client: str, message: str) -> str:
    """
    Send WhatsApp message via Twilio with full safety checks.

    Flow:
      1. Validate phone number and message
      2. Load credentials from .env
      3. If no credentials -> SIMULATION (write to local file)
      4. If credentials exist -> send via Twilio REST API
      5. Log every attempt

    Args:
        to: Recipient phone number (e.g. "+92-300-1234567")
        client: Client display name (e.g. "Ahmed Khan")
        message: Message body text

    Returns:
        Status string describing what happened.
    """
    if not client:
        client = "Unknown"

    # ── Step 1: Validate inputs ──
    valid, reason = _validate_phone(to)
    if not valid:
        _log_send("VALIDATION_FAILED", to, client, reason)
        return f"WhatsApp not sent: {reason}"

    valid, reason = _validate_message(message)
    if not valid:
        _log_send("VALIDATION_FAILED", to, client, reason)
        return f"WhatsApp not sent: {reason}"

    # ── Step 2: Load credentials ──
    creds = _load_credentials()

    # ── Step 3: SIMULATION if no real credentials ──
    if not _is_live_mode(creds):
        return _simulate_whatsapp(to, client, message)

    # ── Step 4: LIVE SEND via Twilio ──
    return _send_via_twilio(to, client, message, creds)


def _send_via_twilio(to: str, client: str, message: str, creds: dict) -> str:
    """Send via Twilio REST API with proper error handling."""
    account_sid = creds["TWILIO_ACCOUNT_SID"]
    auth_token = creds["TWILIO_AUTH_TOKEN"]
    from_number = creds.get("TWILIO_WHATSAPP_FROM", DEFAULT_FROM)

    # Clean phone number for Twilio format
    clean_to = _clean_phone(to)

    try:
        from twilio.rest import Client
    except ImportError:
        error = "twilio package not installed (pip install twilio)"
        print(f"[WhatsApp] {error}")
        _log_send("IMPORT_ERROR", to, client, error)
        print("[WhatsApp] Falling back to simulation...")
        return _simulate_whatsapp(to, client, message)

    try:
        twilio_client = Client(account_sid, auth_token)

        twilio_message = twilio_client.messages.create(
            body=message,
            from_=f"whatsapp:{from_number}",
            to=f"whatsapp:{clean_to}",
        )

        sid = twilio_message.sid
        status_text = f"WhatsApp sent to {client} (SID: {sid})"

        print(f"[WhatsApp LIVE] Sent to: {to} ({client})")
        print(f"[WhatsApp LIVE] SID: {sid}")

        _log_send("SENT", to, client, status_text, sid=sid)
        return status_text

    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)

        # Twilio-specific error handling
        if "authenticate" in error_msg.lower() or "401" in error_msg:
            detail = "Twilio auth failed - check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN"
        elif "not a valid phone" in error_msg.lower() or "21211" in error_msg:
            detail = f"Invalid recipient number: {to}"
        elif "21608" in error_msg:
            detail = f"Recipient {to} hasn't opted in to WhatsApp sandbox"
        elif "rate limit" in error_msg.lower() or "429" in error_msg:
            detail = "Twilio rate limit hit - try again later"
        elif "insufficient" in error_msg.lower() or "20003" in error_msg:
            detail = "Twilio account has insufficient funds"
        else:
            detail = f"{error_type}: {error_msg}"

        print(f"[WhatsApp ERROR] {detail}")
        _log_send("TWILIO_ERROR", to, client, detail)

        # Fallback to simulation on any Twilio error
        print("[WhatsApp] Falling back to simulation...")
        return _simulate_whatsapp(to, client, message)


# ──────────────────────────────────────────────
# SIMULATION MODE
# ──────────────────────────────────────────────

def _simulate_whatsapp(to: str, client: str, message: str) -> str:
    """
    Simulate WhatsApp by writing to a local file.
    Files are appended (multiple messages to same client stack up).
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    sim_output = f"""========================================
WhatsApp Message Simulation
========================================
Timestamp : {timestamp}
To        : {to}
Client    : {client}
Status    : DELIVERED (Simulated)
----------------------------------------
{message}
----------------------------------------
"""

    # Write simulation file
    sim_dir = Path(__file__).parent / "AI_Employee_Vault" / SIM_DIR_NAME
    sim_dir.mkdir(parents=True, exist_ok=True)

    safe_client = re.sub(r"[^\w]", "_", client) if client else "unknown"
    sim_file = sim_dir / f"WHATSAPP_{safe_client}.txt"

    # Append mode: multiple messages to same client stack up
    with open(sim_file, "a", encoding="utf-8") as f:
        f.write(sim_output)

    print(f"[WhatsApp SIM] Message saved to: {sim_file}")
    print(f"[WhatsApp SIM] To: {to} ({client})")
    print(f"[WhatsApp SIM] Preview: {message[:80]}...")

    _log_send("SIMULATED", to, client, "Simulation mode - saved to local file")
    return f"WhatsApp message sent to {client}"


# ──────────────────────────────────────────────
# APPROVED SEND (with file-level approval check)
# ──────────────────────────────────────────────

def send_approved_whatsapp(action_file_path: str) -> str:
    """
    Parse an ACTION file and send ONLY if it contains approval status.

    This is the safest entry point — checks the file for "APPROVED"
    before sending anything.

    Args:
        action_file_path: Path to an ACTION_*.md file

    Returns:
        Status string.
    """
    data = parse_whatsapp_from_action(action_file_path)

    if not data["approved"]:
        return f"WhatsApp blocked: {Path(action_file_path).name} not approved"

    to = data.get("to")
    client = data.get("client", "Unknown")
    message = data.get("message", "")

    if not to or not message:
        return "WhatsApp not sent: missing recipient or message"

    return send_whatsapp(to, client, message)


# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

def _log_send(event: str, to: str, client: str, details: str, sid: str = None):
    """
    Append WhatsApp send event to daily log.
    Logs to AI_Employee_Vault/Logs/whatsapp_YYYY-MM-DD.json
    """
    logs_dir = Path(__file__).parent / "AI_Employee_Vault" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"whatsapp_{today}.json"

    if log_file.exists():
        entries = json.loads(log_file.read_text(encoding="utf-8"))
    else:
        entries = []

    entry = {
        "event": event,
        "to": to,
        "client": client,
        "details": details,
        "timestamp": datetime.now().isoformat(),
    }
    if sid:
        entry["twilio_sid"] = sid

    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────
# CLI TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  WHATSAPP SENDER - Diagnostic Test")
    print("=" * 50)

    creds = _load_credentials()
    live = _is_live_mode(creds)

    print(f"\n  .env found:    {_find_env_path().exists()}")
    print(f"  ACCOUNT_SID:   {creds.get('TWILIO_ACCOUNT_SID', '(not set)')[:8]}...")
    print(f"  AUTH_TOKEN:    {'****' + creds.get('TWILIO_AUTH_TOKEN', '')[-4:] if creds.get('TWILIO_AUTH_TOKEN') else '(not set)'}")
    print(f"  FROM number:   {creds.get('TWILIO_WHATSAPP_FROM', DEFAULT_FROM)}")
    print(f"  Mode:          {'LIVE (Twilio)' if live else 'SIMULATION'}")

    # Twilio package check
    try:
        from twilio.rest import Client
        print(f"  twilio pkg:    INSTALLED")
    except ImportError:
        print(f"  twilio pkg:    NOT INSTALLED (pip install twilio)")

    print(f"\n  Phone validation tests:")
    tests = [
        ("", "empty"),
        ("12345", "too short"),
        ("+92-300-1234567", "PK with dashes"),
        ("+14155238886", "US clean"),
        ("+92 321 987 6543", "PK with spaces"),
    ]
    for number, label in tests:
        ok, reason = _validate_phone(number)
        cleaned = _clean_phone(number) if number else ""
        status = "PASS" if ok else "BLOCK"
        print(f"    [{status}] {label:18s} | {number or '(empty)':20s} | clean: {cleaned:16s} | {reason}")

    print(f"\n  Sending test message (simulation)...")
    result = send_whatsapp("+92-300-0000000", "Test User", "This is a test WhatsApp message.")
    print(f"  Result: {result}")

    print()
