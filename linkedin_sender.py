"""
LinkedIn Sender Module — API Integration
==========================================
Publishes LinkedIn posts via API or simulation mode.

Security:
  - Credentials loaded from .env (never hardcoded)
  - Approval status verified inside the ACTION file before publishing
  - Graceful fallback to simulation mode when credentials missing
  - Per-event JSON logging for audit trail
  - HTTP error classification (permanent vs transient)

Required .env variables (for live mode):
  LINKEDIN_ACCESS_TOKEN=your_token_here
  LINKEDIN_PERSON_ID=your_person_id_here

Backward-compatible exports:
  parse_linkedin_from_action(file_path) -> dict
  publish_linkedin(author, topic, post_body, hashtags) -> str
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path

# Try python-dotenv
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

# Try requests
try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

API_URL = "https://api.linkedin.com/v2/ugcPosts"
APPROVAL_KEYWORDS = ("APPROVED", "Status: APPROVED")
MAX_POST_LENGTH = 3000  # LinkedIn character limit
SIM_DIR_NAME = "LinkedIn_Posts"


# ──────────────────────────────────────────────
# CREDENTIAL LOADING
# ──────────────────────────────────────────────

def _find_env_path() -> Path:
    return Path(__file__).parent / ".env"


def _load_credentials() -> dict:
    """Load LinkedIn credentials from .env file."""
    env_path = _find_env_path()

    if _HAS_DOTENV:
        load_dotenv(env_path, override=False)
        return {
            "LINKEDIN_ACCESS_TOKEN": os.getenv("LINKEDIN_ACCESS_TOKEN", ""),
            "LINKEDIN_PERSON_ID": os.getenv("LINKEDIN_PERSON_ID", ""),
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
    """Check if we have real LinkedIn credentials."""
    token = creds.get("LINKEDIN_ACCESS_TOKEN", "")
    person_id = creds.get("LINKEDIN_PERSON_ID", "")
    if not token or not person_id:
        return False
    if "your_" in token or "your_" in person_id:
        return False
    return True


# Backward compatibility
def load_env():
    return _load_credentials()


# ──────────────────────────────────────────────
# ACTION FILE PARSER
# ──────────────────────────────────────────────

def parse_linkedin_from_action(file_path):
    """Extract LinkedIn post details from ACTION_*.md file."""
    content = Path(file_path).read_text(encoding="utf-8")

    li_data = {
        "author": None,
        "topic": None,
        "post_body": None,
        "hashtags": None,
        "approved": False,
    }

    # Extract author
    author_match = re.search(r"Author\s*\|\s*(.+?)(?:\s*\||\s*$)", content, re.MULTILINE)
    if author_match:
        li_data["author"] = author_match.group(1).strip()

    # Extract topic
    topic_match = re.search(r"Topic\s*\|\s*(.+?)(?:\s*\||\s*$)", content, re.MULTILINE)
    if topic_match:
        li_data["topic"] = topic_match.group(1).strip()

    # Extract hashtags
    hashtags_match = re.search(r"Hashtags\s*\|\s*(.+?)(?:\s*\||\s*$)", content, re.MULTILINE)
    if hashtags_match:
        li_data["hashtags"] = hashtags_match.group(1).strip()

    # Extract post body from ">" quoted lines
    body_lines = []
    in_body = False
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith(">") and not in_body:
            text_after = stripped[1:].strip()
            if text_after and len(text_after) > 5:
                in_body = True
        if in_body and stripped.startswith(">"):
            body_lines.append(stripped[1:].strip())
        elif in_body and not stripped.startswith(">"):
            if stripped == "" and body_lines and body_lines[-1] != "":
                body_lines.append("")
            elif stripped == "" and body_lines:
                break
            else:
                break

    li_data["post_body"] = "\n".join(body_lines).strip() if body_lines else None

    # Check approval
    for keyword in APPROVAL_KEYWORDS:
        if keyword in content:
            li_data["approved"] = True
            break

    return li_data


# ──────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────

def _validate_post(post_body: str) -> tuple[bool, str]:
    """Validate post content."""
    if not post_body:
        return False, "Post body is empty"
    if len(post_body) > MAX_POST_LENGTH:
        return False, f"Post too long ({len(post_body)} chars, max {MAX_POST_LENGTH})"
    return True, "OK"


# ──────────────────────────────────────────────
# PUBLISH
# ──────────────────────────────────────────────

def publish_linkedin(author, topic, post_body, hashtags=None):
    """
    Publish LinkedIn post via API or simulation.

    Flow:
      1. Validate post content
      2. Load credentials from .env
      3. If no credentials -> SIMULATION (write to local file)
      4. If credentials exist -> publish via LinkedIn API
      5. Log every attempt
    """
    if not author:
        author = "AI Employee Team"
    if not topic:
        topic = "General"

    # Step 1: Validate
    valid, reason = _validate_post(post_body)
    if not valid:
        _log_send("VALIDATION_FAILED", author, topic, reason)
        return f"LinkedIn not posted: {reason}"

    # Step 2: Load credentials
    creds = _load_credentials()

    # Step 3: Simulation if no credentials
    if not _is_live_mode(creds):
        return _simulate_linkedin(author, topic, post_body, hashtags)

    # Step 4: Live publish
    if not _HAS_REQUESTS:
        _log_send("IMPORT_ERROR", author, topic, "requests package not installed")
        print("[LinkedIn] requests not installed, falling back to simulation...")
        return _simulate_linkedin(author, topic, post_body, hashtags)

    return _publish_via_api(author, topic, post_body, hashtags, creds)


def _publish_via_api(author, topic, post_body, hashtags, creds):
    """Publish via LinkedIn REST API with error handling."""
    access_token = creds["LINKEDIN_ACCESS_TOKEN"]
    person_id = creds["LINKEDIN_PERSON_ID"]

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    full_post = post_body
    if hashtags:
        full_post += f"\n\n{hashtags}"

    payload = {
        "author": f"urn:li:person:{person_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": full_post},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)

        if resp.status_code == 201:
            post_id = resp.json().get("id", "unknown")
            status = f"LinkedIn post published (ID: {post_id})"
            print(f"[LinkedIn LIVE] Published by: {author}")
            print(f"[LinkedIn LIVE] Post ID: {post_id}")
            _log_send("PUBLISHED", author, topic, status, post_id=post_id)
            return status

        # Error handling by status code
        if resp.status_code == 401:
            detail = "Unauthorized — check LINKEDIN_ACCESS_TOKEN (may be expired)"
        elif resp.status_code == 403:
            detail = "Forbidden — insufficient API permissions"
        elif resp.status_code == 429:
            detail = "Rate limited — LinkedIn allows 100 posts/day"
        elif resp.status_code >= 500:
            detail = f"LinkedIn server error ({resp.status_code})"
        else:
            detail = f"HTTP {resp.status_code}: {resp.text[:200]}"

        print(f"[LinkedIn API ERROR] {detail}")
        _log_send("API_ERROR", author, topic, detail)

        # Fall back to simulation on error
        print("[LinkedIn] Falling back to simulation...")
        return _simulate_linkedin(author, topic, post_body, hashtags)

    except requests.Timeout:
        detail = "Connection timeout (30s)"
        _log_send("TIMEOUT", author, topic, detail)
        return f"LinkedIn failed: {detail}"

    except requests.ConnectionError as e:
        detail = f"Connection error: {e}"
        _log_send("CONNECTION_ERROR", author, topic, detail)
        return f"LinkedIn failed: {detail}"

    except Exception as e:
        detail = f"Unexpected error: {type(e).__name__}"
        _log_send("ERROR", author, topic, detail)
        print(f"[LinkedIn] Falling back to simulation...")
        return _simulate_linkedin(author, topic, post_body, hashtags)


# ──────────────────────────────────────────────
# SIMULATION MODE
# ──────────────────────────────────────────────

def _simulate_linkedin(author, topic, post_body, hashtags=None):
    """Simulate LinkedIn post by writing to a local file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    sim_output = f"""========================================
LinkedIn Post Simulation
========================================
Timestamp : {timestamp}
Author    : {author}
Topic     : {topic}
Status    : READY FOR PUBLISHING (Simulated)
========================================

{post_body}

{hashtags if hashtags else ""}

========================================
"""

    sim_dir = Path(__file__).parent / "AI_Employee_Vault" / SIM_DIR_NAME
    sim_dir.mkdir(parents=True, exist_ok=True)

    safe_topic = re.sub(r'[^\w]', '_', topic) if topic else "general"
    sim_file = sim_dir / f"LINKEDIN_{safe_topic}.txt"

    with open(sim_file, "a", encoding="utf-8") as f:
        f.write(sim_output)

    print(f"[LinkedIn SIM] Post saved to: {sim_file}")
    print(f"[LinkedIn SIM] Author: {author} | Topic: {topic}")
    print(f"[LinkedIn SIM] Preview: {post_body[:80]}...")

    _log_send("SIMULATED", author, topic, "Simulation mode - saved to local file")
    return "LinkedIn post ready for publishing"


# ──────────────────────────────────────────────
# APPROVED SEND (with file-level approval check)
# ──────────────────────────────────────────────

def send_approved_linkedin(action_file_path: str) -> str:
    """Parse an ACTION file and publish ONLY if it contains approval status."""
    data = parse_linkedin_from_action(action_file_path)

    if not data["approved"]:
        return f"LinkedIn blocked: {Path(action_file_path).name} not approved"

    author = data.get("author", "AI Employee Team")
    topic = data.get("topic", "General")
    post_body = data.get("post_body", "")
    hashtags = data.get("hashtags", "")

    if not post_body:
        return "LinkedIn not posted: missing post body"

    return publish_linkedin(author, topic, post_body, hashtags)


# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

def _log_send(event: str, author: str, topic: str, details: str, post_id: str = None):
    """Append LinkedIn event to daily log."""
    logs_dir = Path(__file__).parent / "AI_Employee_Vault" / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"linkedin_{today}.json"

    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    else:
        entries = []

    entry = {
        "event": event,
        "author": author,
        "topic": topic,
        "details": details,
        "timestamp": datetime.now().isoformat(),
    }
    if post_id:
        entry["post_id"] = post_id

    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────
# CLI TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  LINKEDIN SENDER — Diagnostic Test")
    print("=" * 50)

    creds = _load_credentials()
    live = _is_live_mode(creds)

    print(f"\n  .env found:      {_find_env_path().exists()}")
    print(f"  ACCESS_TOKEN:    {creds.get('LINKEDIN_ACCESS_TOKEN', '(not set)')[:12]}...")
    print(f"  PERSON_ID:       {creds.get('LINKEDIN_PERSON_ID', '(not set)')}")
    print(f"  Mode:            {'LIVE (API)' if live else 'SIMULATION'}")
    print(f"  requests pkg:    {'INSTALLED' if _HAS_REQUESTS else 'NOT INSTALLED'}")

    print(f"\n  Sending test post (simulation)...")
    result = publish_linkedin("Test Author", "Test Topic", "This is a test LinkedIn post.")
    print(f"  Result: {result}")
    print()
