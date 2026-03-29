"""
LinkedIn Auto-Poster — Silver Tier
=====================================
Automatically generates professional LinkedIn posts about your business.
Uses Groq AI (FREE) — no paid subscriptions needed.

How it works:
  1. Reads Business_Goals.md for context (revenue, projects, goals)
  2. Uses Groq Llama-3 (free) to generate a unique post
  3. Creates approval task in Inbox/ for human review (HITL)
  4. After approval, ralph_loop executes the post via linkedin_sender.py

Modes:
  python linkedin_autoposter.py              # Generate + create approval task
  python linkedin_autoposter.py --now        # Post directly (simulation mode)
  python linkedin_autoposter.py --daemon     # Run daily at 9 AM automatically
  python linkedin_autoposter.py --test       # Test without creating any files
"""

import os
import sys
import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

# Fix Windows console encoding (handles emojis and special chars)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

# Post topics — business and AI focused
TOPICS = [
    "How AI automation is saving 10+ hours per week in business operations",
    "Why every small business needs a digital AI Employee in 2026",
    "Building a personal AI system that handles emails while you sleep",
    "From 100 unread emails to inbox zero — using AI triage automation",
    "The real cost of manual email replies vs AI-powered responses",
    "How I automated my client follow-ups using Claude Code and Python",
    "AI + Obsidian: the perfect local-first productivity system",
    "What I learned building an autonomous AI Employee from scratch",
    "Why local-first AI matters: your data stays private and secure",
    "The 24/7 advantage: AI handles tasks while you rest",
    "How AI is reshaping freelance business management in Pakistan",
    "Automating LinkedIn posting, email triage, and invoicing with AI",
    "Building real AI agents with Claude Code — a practical guide",
    "Why WhatsApp automation is a game-changer for Pakistani businesses",
    "How I reduced response time from 24 hours to 5 minutes with AI",
]

POST_HOUR = 9   # Default: post at 9 AM daily


# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def _get_groq_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    return key if key and "your_" not in key and len(key) > 10 else ""


def _read_business_goals() -> str:
    goals_file = VAULT / "Business_Goals.md"
    if goals_file.exists():
        text = goals_file.read_text(encoding="utf-8")
        # Return first 600 chars (enough context, not too long)
        return text[:600]
    return "AI automation business — helping clients save time and grow revenue."


def _last_post_date() -> datetime | None:
    """Return timestamp of the most recently generated LinkedIn post."""
    posts_dir = VAULT / "LinkedIn_Posts"
    if posts_dir.exists():
        files = sorted(
            posts_dir.glob("LINKEDIN_*.txt"),
            key=lambda f: f.stat().st_mtime,
        )
        if files:
            return datetime.fromtimestamp(files[-1].stat().st_mtime)
    # Also check Inbox for pending LinkedIn tasks
    inbox = VAULT / "Inbox"
    if inbox.exists():
        files = sorted(
            inbox.glob("LINKEDIN_*.md"),
            key=lambda f: f.stat().st_mtime,
        )
        if files:
            return datetime.fromtimestamp(files[-1].stat().st_mtime)
    return None


def _already_posted_today() -> bool:
    last = _last_post_date()
    if last is None:
        return False
    return last.date() == datetime.now().date()


def _log(event: str, details: str):
    logs_dir = VAULT / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"linkedin_autoposter_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            entries = []

    entries.append({
        "event":     event,
        "details":   details,
        "timestamp": datetime.now().isoformat(),
    })
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# POST GENERATOR (Groq AI — free)
# ─────────────────────────────────────────────────────────────────

def generate_post(topic: str) -> str:
    """
    Use Groq Llama-3 (free) to write a LinkedIn post.
    Falls back to a professional template if no API key.
    """
    business_ctx = _read_business_goals()
    groq_key     = _get_groq_key()

    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)

            prompt = f"""Write a professional LinkedIn post about: "{topic}"

Business context:
{business_ctx[:400]}

Requirements:
- Start with a strong hook (first line must grab attention)
- 3-4 short paragraphs — easy to read on mobile
- Share a real insight, lesson, or tip
- End with a thought-provoking question OR clear call-to-action
- Add 4-5 relevant hashtags on the last line
- Tone: professional but conversational (not corporate-speak)
- Length: 200-350 words

Write ONLY the post content. No labels, no JSON, no markdown headers."""

            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
            )
            post = resp.choices[0].message.content.strip()
            print(f"  [LinkedIn] AI generated post ({len(post)} chars)")
            return post

        except Exception as e:
            print(f"  [LinkedIn] Groq failed: {e} — using template")

    # Professional fallback template
    return f"""🤖 {topic}

Running a business means juggling dozens of tasks every day.
But what if you could automate the repetitive ones and focus only on what truly matters?

I've been building AI-powered workflows that handle email triage, client follow-ups,
and social media posting — automatically. The result? More time for strategy,
less time stuck in an inbox.

The technology exists today. Groq, Claude Code, Python, Obsidian — all free or low-cost tools
that together create a powerful autonomous AI Employee working 24/7.

What task do you wish you could automate in your business?

#AI #Automation #Productivity #BusinessGrowth #ArtificialIntelligence"""


# ─────────────────────────────────────────────────────────────────
# CREATE APPROVAL TASK (HITL workflow)
# ─────────────────────────────────────────────────────────────────

def create_approval_task(post_content: str, topic: str) -> Path:
    """
    Create a LinkedIn task file in Inbox/ for human review.
    The ralph_loop will pick this up, create a Plan, and route for approval.
    """
    inbox = VAULT / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_topic = "".join(c if c.isalnum() or c == "_" else "_" for c in topic)[:35]
    filename   = f"LINKEDIN_{timestamp}_{safe_topic}.md"

    content = f"""# LinkedIn Post — {topic}

## Metadata

| Field | Value |
|-------|-------|
| Channel | LinkedIn |
| Author | AI Employee Team |
| Topic | {topic} |
| Generated | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| Priority | normal |
| Source | linkedin_autoposter.py |

## Post Content

{post_content}

## Instructions

Channel: LinkedIn
Author: AI Employee Team
Topic: {topic}
"""

    task_path = inbox / filename
    task_path.write_text(content, encoding="utf-8")
    print(f"  [LinkedIn] Approval task → Inbox/{filename}")
    _log("TASK_CREATED", f"topic={topic} file={filename}")
    return task_path


# ─────────────────────────────────────────────────────────────────
# DIRECT POST (no HITL — for --now mode)
# ─────────────────────────────────────────────────────────────────

def post_directly(post_content: str, topic: str) -> str:
    """Post immediately via linkedin_sender (live API or simulation)."""
    try:
        from linkedin_sender import publish_linkedin
        result = publish_linkedin("AI Employee Team", topic, post_content)
        _log("POSTED_DIRECT", f"topic={topic} result={result}")
        print(f"  [LinkedIn] {result}")
        return result
    except Exception as e:
        _log("POST_ERROR", str(e))
        print(f"  [LinkedIn] Error: {e}")
        return f"Error: {e}"


# ─────────────────────────────────────────────────────────────────
# MAIN ACTIONS
# ─────────────────────────────────────────────────────────────────

def run_once(direct: bool = False) -> str:
    """Generate one LinkedIn post. Either creates approval task or posts directly."""
    topic = random.choice(TOPICS)

    print(f"\n  [LinkedIn Auto-Poster] Topic: {topic}")
    post_content = generate_post(topic)

    if direct:
        return post_directly(post_content, topic)
    else:
        path = create_approval_task(post_content, topic)
        return f"Task created: {path.name}"


def run_test():
    """Test mode — generate post but don't save anything."""
    print("=" * 55)
    print("  LINKEDIN AUTO-POSTER — Test Mode")
    print("=" * 55)

    groq_key = _get_groq_key()
    print(f"\n  Groq AI key:   {'SET OK' if groq_key else 'NOT SET (using template)'}")
    print(f"  Business goals: {'FOUND OK' if (VAULT / 'Business_Goals.md').exists() else 'NOT FOUND'}")
    print(f"  Already posted today: {_already_posted_today()}")

    topic = TOPICS[0]
    print(f"\n  Generating test post for: {topic}")
    post  = generate_post(topic)

    print(f"\n  {'─'*50}")
    print(post)
    print(f"  {'─'*50}")
    print(f"\n  Length: {len(post)} chars")
    print(f"\n  Test PASSED ✓ (no files created)")
    print("=" * 55)


def run_daemon(post_hour: int = POST_HOUR):
    """
    Daemon mode: wake up every hour, post once per day at post_hour.
    Creates approval task in Inbox/ (not direct post).
    """
    print("=" * 55)
    print("  LINKEDIN AUTO-POSTER — Daemon Mode")
    print(f"  Posting daily at {post_hour:02d}:00 → Inbox/ (for approval)")
    print(f"  Business context: {(VAULT / 'Business_Goals.md').exists()}")
    print(f"  AI backend: {'Groq OK' if _get_groq_key() else 'Template fallback'}")
    print("  Press Ctrl+C to stop")
    print("=" * 55)

    last_post_day = None

    try:
        while True:
            now   = datetime.now()
            today = now.date()

            # Reset flag on new day
            if last_post_day != today:
                if _already_posted_today():
                    last_post_day = today  # already posted, skip today

            # Time to post?
            if last_post_day != today and now.hour >= post_hour:
                print(f"\n  [{now.strftime('%H:%M')}] Generating daily LinkedIn post...")
                try:
                    result = run_once(direct=False)
                    print(f"  Result: {result}")
                    last_post_day = today
                except Exception as e:
                    print(f"  [ERROR] {e}")
                    _log("DAEMON_ERROR", str(e))
            else:
                # Show next post time
                next_post = now.replace(hour=post_hour, minute=0, second=0, microsecond=0)
                if now.hour >= post_hour:
                    next_post += timedelta(days=1)
                wait_h = max(0, int((next_post - now).total_seconds() / 3600))
                print(f"  [{now.strftime('%H:%M')}] Next LinkedIn post in ~{wait_h}h "
                      f"({'already posted today' if last_post_day == today else 'waiting'})")

            time.sleep(3600)  # Check every hour

    except KeyboardInterrupt:
        print("\n  LinkedIn Auto-Poster daemon stopped.")


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--test" in args:
        run_test()
        return

    if "--now" in args:
        print("  [LinkedIn] Direct post mode (no HITL)...")
        result = run_once(direct=True)
        print(f"  Result: {result}")
        return

    if "--daemon" in args:
        hour = POST_HOUR
        for a in args:
            if a.isdigit() and 0 <= int(a) <= 23:
                hour = int(a)
        run_daemon(post_hour=hour)
        return

    # Default: generate + create approval task
    print("=" * 55)
    print("  LINKEDIN AUTO-POSTER")
    print("=" * 55)
    result = run_once(direct=False)
    print(f"\n  Done: {result}")
    print("  (ralph_loop will process this from Inbox → approval → post)")
    print("=" * 55)


if __name__ == "__main__":
    main()
