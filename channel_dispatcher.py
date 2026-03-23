"""
Channel Dispatcher — Single Source of Truth
=============================================
Centralized channel detection and message dispatch.

All modules route through here instead of duplicating channel logic.
Eliminates the 4-way code duplication across main.py, executor.py,
run_pipeline.py, and state_machine.py.

Usage:
    from channel_dispatcher import detect_channel, dispatch

    channel = detect_channel(filename, content)
    status  = dispatch(filepath, content)
"""

import re
from pathlib import Path

from email_sender import parse_email_from_action, send_email
from whatsapp_sender import parse_whatsapp_from_action, send_whatsapp
from linkedin_sender import parse_linkedin_from_action, publish_linkedin


# ──────────────────────────────────────────────
# CHANNEL DETECTION
# ──────────────────────────────────────────────

def detect_channel(filename: str, content: str) -> str:
    """
    Detect communication channel from filename or content.
    Single source of truth — all modules call this.

    Priority:
      1. Explicit 'Channel:' field in content
      2. Keyword in filename
      3. Keyword in content body
      4. Default to 'General'
    """
    # 1. Explicit field
    field_match = re.search(r"Channel:\s*(\w+)", content, re.IGNORECASE)
    if field_match:
        value = field_match.group(1).strip().capitalize()
        if value in ("Email", "Whatsapp", "Linkedin"):
            return "WhatsApp" if value == "Whatsapp" else "LinkedIn" if value == "Linkedin" else value

    # 2+3. Keyword scan
    combined = (filename + " " + content).upper()
    if "EMAIL" in combined:
        return "Email"
    if "WHATSAPP" in combined:
        return "WhatsApp"
    if "LINKEDIN" in combined:
        return "LinkedIn"

    return "General"


# ──────────────────────────────────────────────
# DISPATCH — send via detected channel
# ──────────────────────────────────────────────

def dispatch(filepath: Path, content: str) -> tuple[str, str, str]:
    """
    Parse an approved ACTION file and send via the correct channel.

    Returns:
        (status_string, channel, recipient)
    """
    filename_upper = filepath.name.upper()
    channel = detect_channel(filepath.name, content)

    # --- EMAIL ---
    if channel == "Email" or "EMAIL" in filename_upper:
        data = parse_email_from_action(str(filepath))
        to = data.get("to")
        subject = data.get("subject", "No Subject")
        body = data.get("body", "")
        if to and body:
            status = send_email(to, subject, body)
        else:
            status = "Email drafted (missing recipient or body)"
        return status, "Email", to or "unknown"

    # --- WHATSAPP ---
    if channel == "WhatsApp" or "WHATSAPP" in filename_upper:
        data = parse_whatsapp_from_action(str(filepath))
        to = data.get("to")
        client = data.get("client", "unknown")
        message = data.get("message", "")
        if to and message:
            status = send_whatsapp(to, client, message)
        else:
            status = "WhatsApp drafted (missing recipient or message)"
        return status, "WhatsApp", to or "unknown"

    # --- LINKEDIN ---
    if channel == "LinkedIn" or "LINKEDIN" in filename_upper:
        data = parse_linkedin_from_action(str(filepath))
        author = data.get("author", "AI Employee Team")
        topic = data.get("topic", "General")
        post_body = data.get("post_body", "")
        hashtags = data.get("hashtags", "")
        if post_body:
            status = publish_linkedin(author, topic, post_body, hashtags)
        else:
            status = "LinkedIn drafted (missing post body)"
        return status, "LinkedIn", author

    # --- GENERAL ---
    return "Completed (general task)", "General", "N/A"
