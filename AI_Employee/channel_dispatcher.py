"""
Channel Dispatcher -- Single Source of Truth
=============================================
Centralized channel detection and message dispatch.

All modules route through here instead of duplicating channel logic.
Eliminates the 4-way code duplication across main.py, executor.py,
run_pipeline.py, and state_machine.py.

Supported channels:
  Email, WhatsApp, LinkedIn, Facebook, Instagram, Twitter, General

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
from social_media_sender import dispatch_social, parse_social_from_action
from twitter_sender import parse_twitter_from_action, post_tweet

# Channels handled by social_media_sender (save-and-display, no live API)
SOCIAL_CHANNELS = {"Facebook", "Instagram"}

# All channels that produce READY-TO-COPY output (no direct send)
COPY_READY_CHANNELS = {"Facebook", "Instagram"}


# --------------------------------------------------
# CHANNEL DETECTION
# --------------------------------------------------

def detect_channel(filename: str, content: str) -> str:
    """
    Detect communication channel from filename or content.
    Single source of truth -- all modules call this.

    Priority:
      1. Explicit 'Channel:' field in content
      2. Keyword in filename
      3. Keyword in content body
      4. Default to 'General'
    """
    # 1. Explicit 'Channel:' field in markdown table
    field_match = re.search(r"Channel\s*[|:]\s*(\w+)", content, re.IGNORECASE)
    if field_match:
        value = field_match.group(1).strip()
        normalized = _normalize_channel(value)
        if normalized:
            return normalized

    # 2+3. Keyword scan (filename + content body)
    combined = (filename + " " + content).upper()
    if "EMAIL" in combined:
        return "Email"
    if "WHATSAPP" in combined:
        return "WhatsApp"
    if "TWITTER" in combined or " TWEET" in combined or "THREAD" in combined:
        return "Twitter"
    if "FACEBOOK" in combined:
        return "Facebook"
    if "INSTAGRAM" in combined:
        return "Instagram"
    if "LINKEDIN" in combined:
        return "LinkedIn"

    return "General"


def _normalize_channel(value: str) -> str:
    """Map raw channel string to canonical channel name."""
    _map = {
        "email":     "Email",
        "whatsapp":  "WhatsApp",
        "linkedin":  "LinkedIn",
        "facebook":  "Facebook",
        "instagram": "Instagram",
        "twitter":   "Twitter",
        "tweet":     "Twitter",
        "x":         "Twitter",
    }
    return _map.get(value.lower(), "")


# --------------------------------------------------
# DISPATCH -- send / generate via detected channel
# --------------------------------------------------

def dispatch(filepath: Path, content: str) -> tuple[str, str, str]:
    """
    Parse an approved ACTION file and send/generate via the correct channel.

    For Email / WhatsApp / LinkedIn: sends via API (or simulation).
    For Facebook / Instagram: generates READY TO COPY markdown file.

    Returns:
        (status_string, channel, recipient_or_author)
    """
    filename_upper = filepath.name.upper()
    channel        = detect_channel(filepath.name, content)

    # --- EMAIL ---
    if channel == "Email" or "EMAIL" in filename_upper:
        data    = parse_email_from_action(str(filepath))
        to      = data.get("to")
        subject = data.get("subject", "No Subject")
        body    = data.get("body", "")
        if to and body:
            status = send_email(to, subject, body)
        else:
            status = "Email drafted (missing recipient or body)"
        return status, "Email", to or "unknown"

    # --- WHATSAPP ---
    if channel == "WhatsApp" or "WHATSAPP" in filename_upper:
        data    = parse_whatsapp_from_action(str(filepath))
        to      = data.get("to")
        client  = data.get("client", "unknown")
        message = data.get("message", "")
        if to and message:
            status = send_whatsapp(to, client, message)
        else:
            status = "WhatsApp drafted (missing recipient or message)"
        return status, "WhatsApp", to or "unknown"

    # --- LINKEDIN ---
    if channel == "LinkedIn" or "LINKEDIN" in filename_upper:
        data      = parse_linkedin_from_action(str(filepath))
        author    = data.get("author", "AI Employee Team")
        topic     = data.get("topic", "General")
        post_body = data.get("post_body", "")
        hashtags  = data.get("hashtags", "")
        if post_body:
            status = publish_linkedin(author, topic, post_body, hashtags)
        else:
            status = "LinkedIn drafted (missing post body)"
        return status, "LinkedIn", author

    # --- FACEBOOK ---
    if channel == "Facebook" or "FACEBOOK" in filename_upper:
        data    = parse_social_from_action(str(filepath))
        phone   = data.get("phone", "")
        social_content = data.get("content", content)
        status  = dispatch_social("Facebook", social_content, filepath.name, phone)
        return status, "Facebook", "Page"

    # --- INSTAGRAM ---
    if channel == "Instagram" or "INSTAGRAM" in filename_upper:
        data    = parse_social_from_action(str(filepath))
        phone   = data.get("phone", "")
        social_content = data.get("content", content)
        status  = dispatch_social("Instagram", social_content, filepath.name, phone)
        return status, "Instagram", "Profile"

    # --- TWITTER ---
    if channel == "Twitter" or "TWITTER" in filename_upper or "TWEET" in filename_upper:
        data     = parse_twitter_from_action(str(filepath))
        author   = data.get("author", "AI Employee")
        topic    = data.get("topic", "Business Update")
        body     = data.get("body", content)
        hashtags = data.get("hashtags", "#AI #Business")
        status   = post_tweet(author, topic, body, hashtags, source_file=filepath.name)
        return status, "Twitter", author

    # --- GENERAL ---
    return "Completed (general task)", "General", "N/A"
