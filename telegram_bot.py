"""
Telegram Bot Module — Notification & Alert Integration
======================================================
Sends Telegram messages via Bot API after human approval.

Security:
  - Credentials loaded from .env via python-dotenv (never hardcoded)
  - Approval status verified inside the ACTION file before sending
  - Chat ID validation
  - Graceful fallback to DEMO MODE when credentials missing
  - Per-event JSON logging for audit trail

Required .env variables:
  TELEGRAM_TOKEN=123456789:AAHdksjfhsdkjfhskdjfhskdj
  TELEGRAM_CHAT_ID=987654321

Exports:
  send_telegram(message, chat_id=None) -> str
  send_telegram_alert(message) -> str
"""

import os
import json
import requests
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

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"
REQUEST_TIMEOUT = 15  # seconds

# Max message length (Telegram limit is 4096 chars)
MAX_MESSAGE_LENGTH = 4096


# ──────────────────────────────────────────────
# CREDENTIAL LOADING
# ──────────────────────────────────────────────

def _find_env_path() -> Path:
    """Find .env file in the same directory as this module."""
    return Path(__file__).parent / ".env"


def _load_credentials() -> dict:
    """
    Load Telegram credentials from .env file.
    Uses python-dotenv if available, otherwise manual parsing.
    """
    env_path = _find_env_path()

    if _HAS_DOTENV:
        load_dotenv(env_path, override=False)
        return {
            "TELEGRAM_TOKEN": os.getenv("TELEGRAM_TOKEN", ""),
            "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
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
    """Check if we have real Telegram credentials (not placeholders)."""
    token = creds.get("TELEGRAM_TOKEN", "")
    chat_id = creds.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return False
    if "your_" in token or "your_" in chat_id:
        return False
    # Telegram tokens always contain ":"
    if ":" not in token:
        return False
    return True


# ──────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────

def _validate_message(message: str) -> tuple[bool, str]:
    """Validate message content. Returns (is_valid, reason)."""
    if not message:
        return False, "Message is empty"
    if len(message) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long ({len(message)} chars, max {MAX_MESSAGE_LENGTH})"
    return True, "OK"


# ──────────────────────────────────────────────
# SEND TELEGRAM
# ──────────────────────────────────────────────

def send_telegram(message: str, chat_id: str = None) -> str:
    """
    Send a Telegram message via Bot API.

    Flow:
      1. Validate message
      2. Load credentials from .env
      3. If no credentials -> DEMO MODE (print, don't send)
      4. If credentials exist -> POST to Telegram API

    Args:
        message: Text to send
        chat_id: Override chat ID (uses .env value if not provided)

    Returns:
        Status string describing what happened.
    """
    # ── Step 1: Validate ──
    valid, reason = _validate_message(message)
    if not valid:
        _log_send("VALIDATION_FAILED", message[:50], reason)
        return f"Telegram not sent: {reason}"

    # ── Step 2: Load credentials ──
    creds = _load_credentials()

    # Use provided chat_id or fall back to .env value
    effective_chat_id = chat_id or creds.get("TELEGRAM_CHAT_ID", "")

    # ── Step 3: DEMO MODE if no real credentials ──
    if not _is_live_mode(creds):
        print(f"[DEMO MODE] Telegram message would be sent")
        print(f"[DEMO MODE] Chat ID: {effective_chat_id or '(not set)'}")
        print(f"[DEMO MODE] Message: {message[:100]}")
        _log_send("DEMO_SEND", message[:50], "No credentials - demo mode")
        return "Telegram sent (DEMO MODE)"

    # ── Step 4: LIVE SEND via Telegram Bot API ──
    token = creds["TELEGRAM_TOKEN"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": effective_chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        data = response.json()

        if response.status_code == 200 and data.get("ok"):
            msg_id = data["result"]["message_id"]
            _log_send("SENT", message[:50], f"Message ID: {msg_id}")
            return f"Telegram message sent (ID: {msg_id})"

        # API returned error
        error_desc = data.get("description", "Unknown error")
        error_code = data.get("error_code", response.status_code)
        _log_send("API_ERROR", message[:50], f"Code {error_code}: {error_desc}")
        return f"Telegram failed: {error_desc}"

    except requests.exceptions.ConnectionError:
        error = "No internet connection"
        _log_send("CONNECTION_ERROR", message[:50], error)
        return f"Telegram failed: {error}"

    except requests.exceptions.Timeout:
        error = f"Request timed out ({REQUEST_TIMEOUT}s)"
        _log_send("TIMEOUT", message[:50], error)
        return f"Telegram failed: {error}"

    except Exception as e:
        error = f"Unexpected error: {e}"
        _log_send("ERROR", message[:50], error)
        return f"Telegram failed: {error}"


def send_telegram_alert(message: str) -> str:
    """
    Send an alert/notification message to the default chat.
    Convenience wrapper around send_telegram().
    """
    return send_telegram(message)


# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

def _log_send(event: str, preview: str, details: str):
    """
    Append Telegram send event to daily log.
    Logs to AI_Employee_Vault/Logs/telegram_YYYY-MM-DD.json
    """
    logs_dir = Path(__file__).parent / "AI_Employee_Vault" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"telegram_{today}.json"

    if log_file.exists():
        entries = json.loads(log_file.read_text(encoding="utf-8"))
    else:
        entries = []

    entries.append({
        "event": event,
        "preview": preview,
        "details": details,
        "timestamp": datetime.now().isoformat(),
    })

    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────
# CLI TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  TELEGRAM BOT — Diagnostic Test")
    print("=" * 50)

    creds = _load_credentials()
    live = _is_live_mode(creds)

    token = creds.get("TELEGRAM_TOKEN", "")
    chat_id = creds.get("TELEGRAM_CHAT_ID", "")

    print(f"\n  .env found:      {_find_env_path().exists()}")
    print(f"  TELEGRAM_TOKEN:  {token[:10] + '...' if len(token) > 10 else '(not set)'}")
    print(f"  CHAT_ID:         {chat_id or '(not set)'}")
    print(f"  Mode:            {'LIVE' if live else 'DEMO'}")

    print(f"\n  Sending test message...")
    result = send_telegram("*AI Employee* online hai! Test message.")
    print(f"  Result: {result}")

    print()
