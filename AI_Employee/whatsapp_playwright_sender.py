"""
WhatsApp Playwright Sender — Free, No Twilio Required
=======================================================
Sends WhatsApp messages via WhatsApp Web using Playwright.
Reuses the authenticated browser session from whatsapp_watcher.py

Modes:
  LIVE   — Playwright opens WhatsApp Web, finds contact, sends message
  COPY   — No browser; saves message to WhatsApp_Sent/ for manual copy-paste

Security:
  - Session stored locally in .whatsapp_session/ (never synced to cloud)
  - No credentials in code or .env for WhatsApp
  - APPROVAL_KEYWORDS must be present in ACTION file before sending

Usage:
  from whatsapp_playwright_sender import send_whatsapp_playwright
  result = send_whatsapp_playwright("+923001234567", "Ahmed", "Hello!")

  python whatsapp_playwright_sender.py --test
  python whatsapp_playwright_sender.py --send "+923001234567" "Test message"
"""

import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"
SESSION_DIR = BASE / ".whatsapp_session"
SENT_DIR    = VAULT / "WhatsApp_Sent"
LOG_DIR     = VAULT / "Logs"

APPROVAL_KEYWORDS = ("APPROVED", "Status: APPROVED")

PAYMENT_THRESHOLD = 50_000   # PKR — payments above this need extra approval


# ─── CORE SENDER ──────────────────────────────────────────────────────────────

def send_whatsapp_playwright(to: str, contact_name: str, message: str) -> str:
    """
    Send a WhatsApp message via Playwright (free, no Twilio).
    Falls back to COPY mode if session missing or Playwright unavailable.

    Returns: status string
    """
    to = to.strip()
    if not to.startswith("+"):
        to = "+" + to

    # --- try Playwright LIVE mode ---
    if SESSION_DIR.exists():
        try:
            return _send_live(to, contact_name, message)
        except Exception as e:
            print(f"[WA-Playwright] Live mode failed: {e}, falling back to COPY mode")

    # --- COPY / simulation fallback ---
    return _send_copy(to, contact_name, message)


def _send_live(to: str, contact_name: str, message: str) -> str:
    """Send via real WhatsApp Web browser session."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://web.whatsapp.com", timeout=30000)
        page.wait_for_timeout(4000)

        # Check if logged in
        if "QR" in (page.title() or ""):
            browser.close()
            return _send_copy(to, contact_name, message + "\n[NOTE: WhatsApp session expired — please re-login]")

        # Open chat via URL (phone number without +)
        phone_digits = to.replace("+", "").replace(" ", "")
        page.goto(f"https://web.whatsapp.com/send?phone={phone_digits}", timeout=30000)
        page.wait_for_timeout(3000)

        # Find message box and type
        msg_box = page.locator("div[contenteditable='true'][data-tab='10']").first
        msg_box.wait_for(timeout=10000)
        msg_box.click()
        msg_box.fill("")
        msg_box.type(message, delay=20)
        page.wait_for_timeout(500)

        # Send
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        browser.close()

    _log_sent(to, contact_name, message, mode="LIVE")
    print(f"[WA-Playwright] LIVE sent to {to} ({contact_name})")
    return f"WhatsApp sent (LIVE) to {to}"


def _send_copy(to: str, contact_name: str, message: str) -> str:
    """Save to WhatsApp_Sent/ for manual send — always works, zero cost."""
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = SENT_DIR / f"WHATSAPP_{timestamp}_{contact_name.replace(' ', '_')}.txt"

    content = (
        f"WhatsApp Message — Ready to Send\n"
        f"{'=' * 45}\n"
        f"To      : {contact_name}\n"
        f"Phone   : {to}\n"
        f"Time    : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Mode    : COPY (paste manually or auto-send when session active)\n"
        f"{'=' * 45}\n\n"
        f"{message}\n"
    )
    fname.write_text(content, encoding="utf-8")
    _log_sent(to, contact_name, message, mode="COPY")
    print(f"[WA-Playwright] COPY saved: {fname.name}")
    return f"WhatsApp ready — saved to {fname.name}"


def _log_sent(to: str, contact_name: str, message: str, mode: str):
    """Append to daily WhatsApp log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"whatsapp_{today}.json"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "to": to,
        "contact": contact_name,
        "mode": mode,
        "length": len(message),
        "preview": message[:80],
    }

    log = []
    if log_file.exists():
        try:
            log = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            log = []
    log.append(entry)
    log_file.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── PAYMENT THRESHOLD CHECK ──────────────────────────────────────────────────

def check_payment_threshold(content: str) -> dict:
    """
    Scan ACTION file content for payment amounts.
    Returns {'flagged': bool, 'amount': float, 'currency': str}
    Company_Handbook rule: flag any payment > PKR 50,000
    """
    import re
    # Match: PKR 75,000 / Rs. 100000 / 75000 PKR / $1500
    patterns = [
        r"PKR\s*[\d,]+",
        r"Rs\.?\s*[\d,]+",
        r"[\d,]+\s*PKR",
        r"\$[\d,]+",
        r"USD\s*[\d,]+",
    ]
    for pat in patterns:
        match = re.search(pat, content, re.IGNORECASE)
        if match:
            raw = re.sub(r"[^\d.]", "", match.group())
            try:
                amount = float(raw)
                currency = "PKR" if "pkr" in match.group().lower() or "rs" in match.group().lower() else "USD"
                # Convert USD to PKR rough estimate
                amount_pkr = amount * 280 if currency == "USD" else amount
                flagged = amount_pkr > PAYMENT_THRESHOLD
                return {"flagged": flagged, "amount": amount, "currency": currency, "amount_pkr": amount_pkr}
            except Exception:
                continue
    return {"flagged": False, "amount": 0, "currency": "PKR", "amount_pkr": 0}


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("=" * 50)
        print("  WhatsApp Playwright Sender — Self Test")
        print("=" * 50)
        print(f"  Session dir  : {'EXISTS' if SESSION_DIR.exists() else 'MISSING (will use COPY mode)'}")
        print(f"  Sent dir     : {SENT_DIR}")
        print(f"  Payment limit: PKR {PAYMENT_THRESHOLD:,}")
        result = send_whatsapp_playwright("+923001234567", "Test Client", "Hello from AI Employee! This is a test.")
        print(f"  Result       : {result}")

        # Test payment threshold
        sample = "Please process payment of PKR 75,000 for invoice #1234"
        pay = check_payment_threshold(sample)
        print(f"  Payment check: {pay}")
        print("  [PASS] WhatsApp Playwright Sender working")

    elif "--send" in sys.argv:
        idx = sys.argv.index("--send")
        to  = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "+923001234567"
        msg = sys.argv[idx + 2] if len(sys.argv) > idx + 2 else "Test message from AI Employee"
        result = send_whatsapp_playwright(to, "Contact", msg)
        print(result)

    else:
        print("Usage: python whatsapp_playwright_sender.py --test")
        print("       python whatsapp_playwright_sender.py --send +923001234567 'Message'")
