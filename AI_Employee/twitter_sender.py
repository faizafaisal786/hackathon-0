"""
Twitter/X Sender Module — API Integration + Copy-Ready Fallback
================================================================
Posts tweets/threads to Twitter (X) via API v2, or generates
copy-ready markdown when credentials are not configured.

Modes:
  LIVE mode    — requires TWITTER_BEARER_TOKEN + TWITTER_API_KEY +
                 TWITTER_API_SECRET + TWITTER_ACCESS_TOKEN +
                 TWITTER_ACCESS_SECRET in .env
  COPY mode    — no credentials needed; saves READY-TO-COPY tweet file

Required .env variables (for live mode):
  TWITTER_BEARER_TOKEN=...
  TWITTER_API_KEY=...
  TWITTER_API_SECRET=...
  TWITTER_ACCESS_TOKEN=...
  TWITTER_ACCESS_SECRET=...

Public API:
  parse_twitter_from_action(file_path)  -> dict
  post_tweet(author, topic, body, hashtags) -> str

Usage:
  python twitter_sender.py           # diagnostic self-test
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path


# ──────────────────────────────────────────────
# OPTIONAL IMPORTS
# ──────────────────────────────────────────────

try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

try:
    import tweepy
    _HAS_TWEEPY = True
except ImportError:
    _HAS_TWEEPY = False

try:
    from groq import Groq
    _HAS_GROQ = True
except ImportError:
    _HAS_GROQ = False


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

MAX_TWEET_CHARS   = 280        # Standard Twitter character limit
MAX_THREAD_TWEETS = 10         # Max tweets in one thread
SIM_DIR_NAME      = "Twitter_Posts"

BASE_DIR = Path(__file__).parent
VAULT    = BASE_DIR / "AI_Employee_Vault"
LOGS_DIR = VAULT / "Logs"
DONE_DIR = VAULT / "Done"

GROQ_MODEL = "llama-3.3-70b-versatile"


# ──────────────────────────────────────────────
# CREDENTIAL LOADING
# ──────────────────────────────────────────────

def _load_env() -> dict:
    """Load Twitter credentials from .env file."""
    env_path = BASE_DIR / ".env"
    if _HAS_DOTENV:
        load_dotenv(env_path, override=False)
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip()
    return {
        "TWITTER_BEARER_TOKEN":  os.getenv("TWITTER_BEARER_TOKEN",  config.get("TWITTER_BEARER_TOKEN",  "")),
        "TWITTER_API_KEY":       os.getenv("TWITTER_API_KEY",       config.get("TWITTER_API_KEY",       "")),
        "TWITTER_API_SECRET":    os.getenv("TWITTER_API_SECRET",    config.get("TWITTER_API_SECRET",    "")),
        "TWITTER_ACCESS_TOKEN":  os.getenv("TWITTER_ACCESS_TOKEN",  config.get("TWITTER_ACCESS_TOKEN",  "")),
        "TWITTER_ACCESS_SECRET": os.getenv("TWITTER_ACCESS_SECRET", config.get("TWITTER_ACCESS_SECRET", "")),
        "GROQ_API_KEY":          os.getenv("GROQ_API_KEY",          config.get("GROQ_API_KEY",          "")),
    }


def _is_live(creds: dict) -> bool:
    """Return True only if all required Twitter credentials are present."""
    required = [
        "TWITTER_API_KEY", "TWITTER_API_SECRET",
        "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET",
    ]
    return all(
        creds.get(k) and "your_" not in creds[k]
        for k in required
    )


# ──────────────────────────────────────────────
# AI CONTENT GENERATION  (Groq → template)
# ──────────────────────────────────────────────

def _call_groq(prompt: str, system: str = "", max_tokens: int = 600) -> str:
    """Call Groq LLM. Returns empty string on failure."""
    if not _HAS_GROQ:
        return ""
    creds   = _load_env()
    api_key = creds.get("GROQ_API_KEY", "")
    if not api_key or "your_" in api_key:
        return ""
    try:
        client   = Groq(api_key=api_key)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=GROQ_MODEL, messages=messages,
            max_tokens=max_tokens, temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Twitter] Groq error: {e}")
        return ""


def _generate_tweet_content(topic: str, body: str, hashtags: str) -> dict:
    """
    Use AI to generate tweet(s) from the task content.

    Returns dict:
        single_tweet: str  (≤280 chars, for a simple post)
        thread:       list[str]  (for a thread, each ≤280 chars)
        summary:      str  (one-line summary for log)
    """
    system = (
        "You are a professional Twitter/X content strategist. "
        "You write engaging, concise tweets that drive engagement. "
        "Always stay within Twitter's 280-character limit per tweet."
    )
    prompt = (
        f"Create Twitter/X content about:\n\nTopic: {topic}\n\n{body}\n\n"
        f"Format your response EXACTLY like this:\n\n"
        f"SINGLE_TWEET:\n"
        f"[One powerful tweet under 260 characters — include {hashtags} at end]\n\n"
        f"THREAD_1:\n"
        f"[First tweet of a thread — hook, under 260 chars]\n\n"
        f"THREAD_2:\n"
        f"[Second tweet — main point, under 260 chars]\n\n"
        f"THREAD_3:\n"
        f"[Third tweet — value/insight, under 260 chars]\n\n"
        f"THREAD_4:\n"
        f"[Final tweet — CTA + hashtags, under 260 chars]\n\n"
        f"SUMMARY:\n"
        f"[One-line description of what was posted]"
    )

    ai_text = _call_groq(prompt, system, max_tokens=700)

    def _extract(text: str, key: str) -> str:
        match = re.search(rf"{key}:\s*\n(.*?)(?=\n[A-Z_]+:|$)", text, re.DOTALL)
        return match.group(1).strip() if match else ""

    if ai_text:
        single  = _extract(ai_text, "SINGLE_TWEET")
        t1      = _extract(ai_text, "THREAD_1")
        t2      = _extract(ai_text, "THREAD_2")
        t3      = _extract(ai_text, "THREAD_3")
        t4      = _extract(ai_text, "THREAD_4")
        summary = _extract(ai_text, "SUMMARY")
        thread  = [t for t in [t1, t2, t3, t4] if t]
    else:
        # Template fallback
        tag_str   = hashtags if hashtags else "#AI #Business #Innovation"
        base_body = body[:200] if body else topic
        single    = f"{base_body[:230]} {tag_str}"[:MAX_TWEET_CHARS]
        thread    = [
            f"🧵 {topic[:240]}",
            f"{base_body[:240]}",
            f"Key insight: AI automation saves 85-90% on operational costs. {tag_str}"[:MAX_TWEET_CHARS],
        ]
        summary   = f"Tweet about: {topic[:80]}"

    # Enforce character limits
    single = single[:MAX_TWEET_CHARS]
    thread = [t[:MAX_TWEET_CHARS] for t in thread]

    return {"single_tweet": single, "thread": thread, "summary": summary}


# ──────────────────────────────────────────────
# LIVE POSTING VIA TWEEPY
# ──────────────────────────────────────────────

def _post_live(creds: dict, tweet_data: dict) -> str:
    """Post tweet/thread via Tweepy (Twitter API v2)."""
    if not _HAS_TWEEPY:
        return "tweepy not installed — run: pip install tweepy"

    try:
        client = tweepy.Client(
            bearer_token=creds.get("TWITTER_BEARER_TOKEN"),
            consumer_key=creds.get("TWITTER_API_KEY"),
            consumer_secret=creds.get("TWITTER_API_SECRET"),
            access_token=creds.get("TWITTER_ACCESS_TOKEN"),
            access_token_secret=creds.get("TWITTER_ACCESS_SECRET"),
            wait_on_rate_limit=True,
        )

        thread = tweet_data.get("thread", [])

        if len(thread) > 1:
            # Post as thread
            prev_id = None
            for i, tweet_text in enumerate(thread[:MAX_THREAD_TWEETS]):
                if prev_id:
                    resp = client.create_tweet(text=tweet_text, in_reply_to_tweet_id=prev_id)
                else:
                    resp = client.create_tweet(text=tweet_text)
                prev_id = resp.data["id"]
            return f"Twitter thread posted ({len(thread)} tweets) — ID: {prev_id}"
        else:
            # Post single tweet
            text = tweet_data.get("single_tweet", "")
            resp = client.create_tweet(text=text)
            tweet_id = resp.data["id"]
            return f"Tweet posted successfully — ID: {tweet_id}"

    except tweepy.TweepyException as e:
        error_msg = str(e)
        if "403" in error_msg:
            return f"Twitter 403 Forbidden — check API permissions (need Read+Write)"
        if "401" in error_msg:
            return f"Twitter 401 Unauthorized — check credentials in .env"
        if "429" in error_msg:
            return f"Twitter rate limit hit — try again in 15 minutes"
        return f"Twitter API error: {error_msg}"
    except Exception as e:
        return f"Twitter unexpected error: {e}"


# ──────────────────────────────────────────────
# COPY-READY FILE (Simulation / No Credentials)
# ──────────────────────────────────────────────

def _save_copy_ready(tweet_data: dict, author: str, topic: str, source_file: str) -> str:
    """Save a READY-TO-COPY markdown file when credentials are not configured."""
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    single = tweet_data.get("single_tweet", "")
    thread = tweet_data.get("thread", [])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file  = DONE_DIR / f"TWITTER_POST_{timestamp}.md"

    thread_block = ""
    if thread:
        thread_block = "## THREAD (Copy tweets in order)\n\n"
        for i, t in enumerate(thread, 1):
            thread_block += (
                f"### Tweet {i}/{len(thread)}\n\n"
                f"```\n{t}\n```\n"
                f"**Characters:** {len(t)} / {MAX_TWEET_CHARS}\n\n"
            )

    md = (
        f"# TWITTER/X POST — READY TO COPY\n\n"
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"**Source:** {source_file}\n"
        f"**Author:** {author}\n"
        f"**Topic:** {topic}\n"
        f"**Mode:** COPY-READY (set Twitter credentials in .env for live posting)\n\n"
        f"---\n\n"
        f"## SINGLE TWEET (Quick post)\n\n"
        f"```\n{single}\n```\n\n"
        f"**Characters:** {len(single)} / {MAX_TWEET_CHARS}\n\n"
        f"---\n\n"
        f"{thread_block}"
        f"---\n\n"
        f"## POSTING CHECKLIST\n\n"
        f"**Option A — Single Tweet:**\n"
        f"- [ ] Copy the SINGLE TWEET block above\n"
        f"- [ ] Go to X.com (Twitter) → compose new tweet\n"
        f"- [ ] Paste and review\n"
        f"- [ ] Click Post\n\n"
        f"**Option B — Thread:**\n"
        f"- [ ] Go to X.com → click compose\n"
        f"- [ ] Paste Tweet 1, click '+' to add next tweet\n"
        f"- [ ] Repeat for all thread tweets\n"
        f"- [ ] Post All\n\n"
        f"**Option C — Activate Live Posting:**\n"
        f"Add to `AI_Employee/.env`:\n"
        f"```\n"
        f"TWITTER_API_KEY=your_api_key\n"
        f"TWITTER_API_SECRET=your_api_secret\n"
        f"TWITTER_ACCESS_TOKEN=your_access_token\n"
        f"TWITTER_ACCESS_SECRET=your_access_secret\n"
        f"```\n"
        f"Get keys at: developer.twitter.com/en/portal/dashboard\n\n"
        f"---\n\n"
        f"*Generated by AI Employee | Ralph Loop v3.0 PLATINUM*\n"
    )

    out_file.write_text(md, encoding="utf-8")
    return str(out_file)


# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

def _log_twitter(event: str, filename: str, details: str, status: str = "INFO"):
    """Append Twitter event to daily JSON log."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"twitter_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []

    entries.append({
        "event":     event,
        "source":    filename,
        "details":   details,
        "status":    status,
        "timestamp": datetime.now().isoformat(),
    })
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────

def post_tweet(
    author:   str = "AI Employee",
    topic:    str = "Business Update",
    body:     str = "",
    hashtags: str = "#AI #Business",
    source_file: str = "unknown",
) -> str:
    """
    Main entry point. Generate tweet content and post or save copy-ready file.

    Args:
        author:      Person/brand posting
        topic:       Short topic label
        body:        Full task content / brief
        hashtags:    Hashtags string (e.g. "#AI #Automation")
        source_file: Source ACTION filename (for logging)

    Returns:
        Status string
    """
    creds      = _load_env()
    tweet_data = _generate_tweet_content(topic, body, hashtags)
    live       = _is_live(creds) and _HAS_TWEEPY

    if live:
        print(f"[Twitter] LIVE MODE — posting via API...")
        status = _post_live(creds, tweet_data)
        mode   = "LIVE"
    else:
        print(f"[Twitter] COPY MODE — saving ready-to-post file...")
        out_path = _save_copy_ready(tweet_data, author, topic, source_file)
        status   = f"Twitter content ready — saved to {Path(out_path).name}"
        mode     = "COPY"

    # Console output
    single = tweet_data.get("single_tweet", "")
    print(f"[Twitter] Mode     : {mode}")
    print(f"[Twitter] Author   : {author}")
    print(f"[Twitter] Topic    : {topic[:60]}")
    print(f"[Twitter] Tweet    : {single[:80]}{'...' if len(single) > 80 else ''}")
    print(f"[Twitter] Status   : {status}")

    _log_twitter("POST", source_file, status)
    return status


def parse_twitter_from_action(file_path: str) -> dict:
    """
    Extract Twitter/X details from an approved ACTION_*.md file.

    Returns:
        dict with keys: author, topic, body, hashtags, approved
    """
    raw = Path(file_path).read_text(encoding="utf-8")

    data = {
        "author":   "AI Employee",
        "topic":    "Business Update",
        "body":     raw,
        "hashtags": "#AI #Business #Automation",
        "approved": False,
    }

    # Author from markdown table
    m = re.search(r"Author\s*[|:]\s*(.+)", raw, re.IGNORECASE)
    if m:
        data["author"] = m.group(1).strip()

    # Topic
    m = re.search(r"Topic\s*[|:]\s*(.+)", raw, re.IGNORECASE)
    if m:
        data["topic"] = m.group(1).strip()

    # Hashtags
    m = re.search(r"Hashtags?\s*[|:]\s*(.+)", raw, re.IGNORECASE)
    if m:
        data["hashtags"] = m.group(1).strip()

    # Extract quoted body lines (> lines in markdown)
    body_lines = [
        line.strip()[1:].strip()
        for line in raw.split("\n")
        if line.strip().startswith(">")
    ]
    if body_lines:
        data["body"] = "\n".join(body_lines).strip()

    # Approval check
    if "APPROVED" in raw:
        data["approved"] = True

    return data


# ──────────────────────────────────────────────
# CLI DIAGNOSTIC TEST
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  TWITTER/X SENDER — Diagnostic Test")
    print("=" * 60)

    creds = _load_env()
    live  = _is_live(creds)

    print(f"\n  tweepy installed   : {'YES' if _HAS_TWEEPY else 'NO  -> pip install tweepy'}")
    print(f"  Groq installed     : {'YES' if _HAS_GROQ else 'NO  -> pip install groq'}")
    print(f"  API Key set        : {'YES' if creds.get('TWITTER_API_KEY') and 'your_' not in creds['TWITTER_API_KEY'] else 'NO'}")
    print(f"  API Secret set     : {'YES' if creds.get('TWITTER_API_SECRET') and 'your_' not in creds['TWITTER_API_SECRET'] else 'NO'}")
    print(f"  Access Token set   : {'YES' if creds.get('TWITTER_ACCESS_TOKEN') and 'your_' not in creds['TWITTER_ACCESS_TOKEN'] else 'NO'}")
    print(f"  Access Secret set  : {'YES' if creds.get('TWITTER_ACCESS_SECRET') and 'your_' not in creds['TWITTER_ACCESS_SECRET'] else 'NO'}")
    print(f"\n  Mode               : {'LIVE (will post to Twitter)' if live else 'COPY-READY (no credentials)'}")
    print(f"  Output dir         : {DONE_DIR}")
    print()

    result = post_tweet(
        author="AI Employee",
        topic="AI Employee System Launch",
        body=(
            "Announcing the AI Employee — a PLATINUM-tier autonomous agent that handles "
            "emails, WhatsApp, LinkedIn, Facebook, Instagram, and Twitter using a "
            "4-agent pipeline (Thinker→Planner→Executor→Reviewer) with memory, "
            "self-improvement, and human-in-the-loop approval. "
            "85-90% cost reduction vs human labor."
        ),
        hashtags="#AI #Automation #AIEmployee #Hackathon #Claude #LLM",
        source_file="CLI_TEST",
    )

    print(f"\n  Final status: {result}")
    print("=" * 60)
