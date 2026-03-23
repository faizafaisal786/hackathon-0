"""
WhatsApp Watcher — Platinum Tier
===================================
Monitors WhatsApp Web for incoming messages using Playwright browser automation.
Saves urgent messages as task files in AI_Employee_Vault/Inbox/

TWO MODES:
  1. Playwright mode (full browser automation) — requires playwright install
  2. Twilio Webhook mode (production, cloud-friendly) — requires Twilio number

Detection keywords (creates task file if found in message):
  urgent, asap, invoice, payment, price, help, order, delivery,
  kab, please, zaroor, confirm, meeting, call

Usage:
  python whatsapp_watcher.py              # Single check (Playwright)
  python whatsapp_watcher.py --loop       # Continuous (every 30s)
  python whatsapp_watcher.py --twilio     # Start Twilio webhook server
  python whatsapp_watcher.py --test       # Self-test (no browser needed)
  python whatsapp_watcher.py --simulate   # Add a fake WA message to Inbox

Requirements (Playwright mode):
  pip install playwright
  playwright install chromium

Requirements (Twilio mode):
  pip install twilio flask
  Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE in .env
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

LOOP_INTERVAL = 30  # seconds

# Keywords that trigger task file creation
URGENT_KEYWORDS = [
    "urgent", "asap", "invoice", "payment", "price", "help",
    "order", "delivery", "kab", "please", "zaroor", "confirm",
    "meeting", "call", "quote", "cost", "buy", "purchase",
    "problem", "issue", "fix", "error", "support",
]


# ══════════════════════════════════════════════════════════════════════════════
# TASK FILE CREATOR
# ══════════════════════════════════════════════════════════════════════════════

def create_task_file(sender: str, message: str, phone: str = "", source: str = "whatsapp") -> Path:
    """Save an incoming WhatsApp message as a task .md file in Inbox/."""
    inbox = VAULT / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name  = "".join(c if c.isalnum() else "_" for c in sender)[:30]
    filename   = f"WHATSAPP_{timestamp}_{safe_name}.md"

    # Detect priority
    msg_lower = message.lower()
    is_urgent = any(kw in msg_lower for kw in URGENT_KEYWORDS)
    priority  = "urgent" if is_urgent else "normal"

    content = f"""# WhatsApp Message — {sender}

## Metadata

| Field    | Value |
|----------|-------|
| From     | {sender} |
| Phone    | {phone or 'unknown'} |
| Received | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| Channel  | WhatsApp |
| Priority | {priority} |
| Source   | {source} |

## Message

{message}

## Suggested Actions

- [ ] Reply via WhatsApp (`whatsapp_sender.py`)
- [ ] Create invoice if payment requested (`odoo_mcp.py`)
- [ ] Escalate to CEO if urgent

## Instructions

To: {phone or sender}
Channel: WhatsApp
"""

    task_path = inbox / filename
    task_path.write_text(content, encoding="utf-8")

    # Log it
    logs_dir = VAULT / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"whatsapp_watcher_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            entries = []

    entries.append({
        "event":     "MESSAGE_RECEIVED",
        "sender":    sender,
        "phone":     phone,
        "priority":  priority,
        "preview":   message[:100],
        "task_file": filename,
        "timestamp": datetime.now().isoformat(),
    })
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  [WA] Task created: {filename} (priority={priority})")
    return task_path


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1: PLAYWRIGHT (WhatsApp Web browser automation)
# ══════════════════════════════════════════════════════════════════════════════

class PlaywrightWatcher:
    """
    Uses Playwright to open WhatsApp Web and scrape unread messages.
    Session is persisted to avoid QR code scan every time.
    """

    SESSION_DIR = BASE / ".whatsapp_session"

    def __init__(self):
        self.processed_ids = set()
        self._load_processed()

    def _load_processed(self):
        """Load already-processed message IDs to avoid duplicates."""
        ids_file = BASE / ".whatsapp_processed.json"
        if ids_file.exists():
            try:
                self.processed_ids = set(json.loads(ids_file.read_text()))
            except Exception:
                self.processed_ids = set()

    def _save_processed(self):
        ids_file = BASE / ".whatsapp_processed.json"
        # Keep only last 1000 IDs to prevent file bloat
        ids_list = list(self.processed_ids)[-1000:]
        ids_file.write_text(json.dumps(ids_list), encoding="utf-8")

    def check_messages(self) -> int:
        """
        Open WhatsApp Web, find unread messages, create task files.
        Returns count of new tasks created.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("  [WA] Playwright not installed.")
            print("       Run: pip install playwright && playwright install chromium")
            return 0

        self.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        created = 0

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    str(self.SESSION_DIR),
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                page = browser.pages[0] if browser.pages else browser.new_page()

                print("  [WA] Opening WhatsApp Web...")
                page.goto("https://web.whatsapp.com", timeout=30000)

                # Wait for chat list (means we're logged in)
                try:
                    page.wait_for_selector('[data-testid="chat-list"]', timeout=15000)
                except Exception:
                    print("  [WA] Not logged in — scan QR code first.")
                    print(f"       Session dir: {self.SESSION_DIR}")
                    print("       Run: python whatsapp_watcher.py --login")
                    browser.close()
                    return 0

                # Find unread chats
                unread_chats = page.query_selector_all('[data-testid="cell-frame-container"]')
                print(f"  [WA] Found {len(unread_chats)} chat(s)")

                for chat in unread_chats:
                    try:
                        # Check for unread badge
                        badge = chat.query_selector('[data-testid="icon-unread-count"]')
                        if not badge:
                            continue

                        # Get sender name
                        name_el = chat.query_selector('[data-testid="cell-frame-title"]')
                        sender  = name_el.inner_text() if name_el else "Unknown"

                        # Get last message preview
                        msg_el  = chat.query_selector('[data-testid="last-msg-status"] + span')
                        message = msg_el.inner_text() if msg_el else "(no preview)"

                        # Create unique ID
                        msg_id = f"{sender}:{message[:50]}"
                        if msg_id in self.processed_ids:
                            continue

                        # Check if message matches keywords
                        msg_lower = (sender + " " + message).lower()
                        if any(kw in msg_lower for kw in URGENT_KEYWORDS):
                            create_task_file(sender, message, source="playwright")
                            self.processed_ids.add(msg_id)
                            created += 1

                    except Exception:
                        pass

                self._save_processed()
                browser.close()

        except Exception as e:
            print(f"  [WA] Playwright error: {e}")

        return created

    def login(self):
        """Open WhatsApp Web in headed mode for QR code scan."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("  pip install playwright && playwright install chromium")
            return

        self.SESSION_DIR.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                str(self.SESSION_DIR),
                headless=False,  # visible for QR scan
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://web.whatsapp.com")
            print("  Scan the QR code in the browser window.")
            print("  Press Enter after scanning...")
            input()
            print("  Session saved. You can now run in headless mode.")
            browser.close()


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2: TWILIO WEBHOOK (production, no browser needed)
# ══════════════════════════════════════════════════════════════════════════════

def start_twilio_webhook(port: int = 5000):
    """
    Start a Flask webhook server that receives WhatsApp messages via Twilio.

    Setup:
      1. Get a Twilio number with WhatsApp capability
      2. Set Webhook URL in Twilio console to: http://YOUR_IP:5000/whatsapp
      3. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE in .env
    """
    try:
        from flask import Flask, request
    except ImportError:
        print("  Flask not installed. Run: pip install flask")
        return

    app = Flask(__name__)

    @app.route("/whatsapp", methods=["POST"])
    def whatsapp_webhook():
        sender  = request.form.get("From", "unknown").replace("whatsapp:+", "+")
        message = request.form.get("Body", "")
        profile = request.form.get("ProfileName", sender)

        print(f"  [WA Webhook] From: {profile} ({sender}): {message[:60]}")

        # Always create task for incoming WhatsApp messages
        create_task_file(profile, message, phone=sender, source="twilio_webhook")

        # Return TwiML response (empty = no auto-reply)
        return '<?xml version="1.0" encoding="UTF-8"?><Response></Response>', 200, {
            "Content-Type": "text/xml"
        }

    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok", "service": "whatsapp_watcher"}, 200

    print(f"  [WA Webhook] Starting on port {port}")
    print(f"  [WA Webhook] Set Twilio webhook to: http://YOUR_PUBLIC_IP:{port}/whatsapp")
    print(f"  [WA Webhook] Use ngrok for local testing: ngrok http {port}")
    app.run(host="0.0.0.0", port=port, debug=False)


# ══════════════════════════════════════════════════════════════════════════════
# MODE 3: SIMULATE (for testing without browser or Twilio)
# ══════════════════════════════════════════════════════════════════════════════

def simulate_message():
    """Add a fake WhatsApp message to Inbox/ for testing."""
    test_messages = [
        ("Ahmed Khan", "+92-321-1234567", "Urgent: Can you send me the invoice for last month? I need it asap."),
        ("Sara Ali", "+92-300-9876543", "Hi, what is your price for social media management?"),
        ("Client XYZ", "+92-333-1111111", "Please confirm our meeting tomorrow at 3pm."),
        ("Tech Solutions", "+92-312-5555555", "We have a payment ready, please send account details."),
    ]

    import random
    sender, phone, message = random.choice(test_messages)
    path = create_task_file(sender, message, phone=phone, source="simulate")
    print(f"  [WA Simulate] Created: {path.name}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
# SELF TEST
# ══════════════════════════════════════════════════════════════════════════════

def run_test():
    print("=" * 55)
    print("  WHATSAPP WATCHER — Self Test")
    print("=" * 55)

    # Test 1: Create task from simulated message
    print("\n  [1] Creating simulated WhatsApp task...")
    path = create_task_file(
        "Test Client",
        "Urgent: Please send invoice for AI automation services. Payment ready.",
        phone="+92-300-0000000",
        source="test",
    )

    exists = path.exists()
    print(f"  [2] Task file exists: {exists}")

    if exists:
        content = path.read_text(encoding="utf-8")
        has_urgent = "urgent" in content.lower()
        has_channel = "WhatsApp" in content
        print(f"  [3] Priority detected: {'urgent' if has_urgent else 'normal'}")
        print(f"  [4] Channel set: {'OK' if has_channel else 'FAIL'}")

    # Test 2: Check log
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = VAULT / "Logs" / f"whatsapp_watcher_{today}.json"
    has_log  = log_file.exists()
    print(f"  [5] Log file created: {has_log}")

    # Test 3: Check Twilio env
    twilio_configured = bool(
        os.getenv("TWILIO_ACCOUNT_SID") and
        os.getenv("TWILIO_AUTH_TOKEN")
    )
    print(f"  [6] Twilio configured: {'YES' if twilio_configured else 'NO (add to .env)'}")

    # Test 4: Check Playwright
    try:
        import playwright
        print(f"  [7] Playwright installed: YES")
    except ImportError:
        print(f"  [7] Playwright installed: NO (pip install playwright)")

    print(f"\n  Result: {'PASS' if exists else 'FAIL'}")
    print("=" * 55)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if "--test" in args:
        run_test()
        return

    if "--simulate" in args:
        simulate_message()
        return

    if "--login" in args:
        watcher = PlaywrightWatcher()
        watcher.login()
        return

    if "--twilio" in args:
        port = 5000
        for a in args:
            if a.isdigit():
                port = int(a)
        start_twilio_webhook(port)
        return

    # Default: Playwright mode
    watcher = PlaywrightWatcher()

    if "--loop" in args:
        interval = LOOP_INTERVAL
        for a in args:
            if a.isdigit():
                interval = int(a)

        print("=" * 55)
        print("  WHATSAPP WATCHER — Continuous Mode (Playwright)")
        print(f"  Interval: {interval}s")
        print(f"  Keywords: {len(URGENT_KEYWORDS)} triggers")
        print("  Press Ctrl+C to stop")
        print("=" * 55)

        try:
            while True:
                print(f"\n  [{time.strftime('%H:%M:%S')}] Checking WhatsApp...")
                count = watcher.check_messages()
                if count:
                    print(f"  [{time.strftime('%H:%M:%S')}] {count} new message(s) -> Inbox/")
                else:
                    print(f"  [{time.strftime('%H:%M:%S')}] No new urgent messages.")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n  WhatsApp Watcher stopped.")

    else:
        # Single check
        print("  [WhatsApp Watcher] Checking for new messages...")
        count = watcher.check_messages()
        print(f"  Done. New tasks created: {count}")


if __name__ == "__main__":
    main()
