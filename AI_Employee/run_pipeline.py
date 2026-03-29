"""
AI Employee Pipeline Runner
=============================
Wires the StateMachine to real channel senders (Email, WhatsApp, LinkedIn).

Usage:
  python run_pipeline.py --demo       # Single pass, auto-approve for hackathon
  python run_pipeline.py --live       # Single pass, human approves via CLI
  python run_pipeline.py --daemon     # Always-on loop (60s interval)
  python run_pipeline.py --status     # Show pipeline status only
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Ensure imports work from this directory
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

# Load .env so GROQ_API_KEY and other keys are available
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=True)
except ImportError:
    pass

from state_machine import StateMachine, State
from email_sender import parse_email_from_action, send_email
from whatsapp_sender import parse_whatsapp_from_action, send_whatsapp
from linkedin_sender import parse_linkedin_from_action, publish_linkedin


VAULT = BASE / "AI_Employee_Vault"


# ──────────────────────────────────────────────
# AI PLAN BUILDER (uses Groq reasoning output)
# ──────────────────────────────────────────────

def _build_ai_plan(filepath: Path, content: str, ai: dict) -> tuple[str, str]:
    """Build Plan.md and Action.md from AI pipeline result."""
    task_name    = filepath.stem
    today        = datetime.now().strftime("%Y-%m-%d")
    channel      = ai.get("channel", "General")
    priority     = ai.get("priority", "Normal")
    recipient    = ai.get("recipient", "N/A")
    subject_line = ai.get("subject", "")
    steps        = ai.get("plan_steps", [])
    drafted      = ai.get("drafted_response", content.strip())
    quality      = ai.get("quality_score", 7)
    tone         = ai.get("tone", "professional")
    action_req   = ai.get("action_required", "review")
    summary      = ai.get("summary", "")
    backend      = ai.get("ai_mode", "AI")

    # Channel-specific meta rows
    meta_extra = ""
    if channel == "Email":
        meta_extra = f"| Recipient | {recipient} |\n"
        if subject_line:
            meta_extra += f"| Subject | {subject_line} |\n"
    elif channel == "WhatsApp":
        meta_extra = f"| Recipient | {recipient} |\n"
    elif channel == "LinkedIn":
        meta_extra = "| Author | AI Employee Team |\n| Topic | Business Insights |\n"

    steps_md = "\n".join(f"- [ ] {step}" for step in steps) if steps else "- [ ] Review and send"
    quoted   = "\n".join(f"> {line}" for line in drafted.split("\n"))

    plan_md = f"""# PLAN: {task_name}

| Field | Value |
|-------|-------|
| Source | Needs_Action/{filepath.name} |
| Created | {today} |
| Channel | {channel} |
| Priority | {priority} |
{meta_extra}| Tone | {tone} |
| Quality Score | {quality}/10 |
| AI Backend | {backend} |
| Status | Ready for Approval |

## AI Reasoning

> {summary}

## Execution Steps (AI Generated)

{steps_md}

## Drafted Content (AI Generated — Quality {quality}/10)

{quoted}

## Next Step

Approve ACTION_{task_name}.md in Pending_Approval/ to execute.
"""

    action_md = f"""# ACTION: {task_name}

## Status: PENDING APPROVAL

| Field | Value |
|-------|-------|
| Channel | {channel} |
{meta_extra}| Created | {today} |
| Priority | {priority} |
| Action | {action_req} |
| Quality | {quality}/10 |

## Drafted {channel} Content

{quoted}

## Result: PENDING — Awaiting Human Approval
"""
    return plan_md, action_md


# ──────────────────────────────────────────────
# REGEX FALLBACK PLANNER (no AI needed)
# ──────────────────────────────────────────────

def _regex_planner(filepath: Path, content: str) -> tuple[str, str]:
    """
    Regex-based planner (fallback when AI is unavailable).
    Parses structured fields from task files.
    """
    task_name = filepath.stem
    today     = datetime.now().strftime("%Y-%m-%d")

    # Detect channel
    combined = (filepath.name + " " + content).upper()
    if "EMAIL" in combined:
        channel = "Email"
    elif "WHATSAPP" in combined:
        channel = "WhatsApp"
    elif "LINKEDIN" in combined:
        channel = "LinkedIn"
    else:
        channel = "General"

    # Parse metadata fields
    fields = {}
    for key in ("To", "Client", "Subject", "Priority", "Author", "Topic", "Channel"):
        match = re.search(rf"{key}:\s*(.+)", content)
        if match:
            fields[key.lower()] = match.group(1).strip()

    if "channel" in fields:
        channel = fields["channel"]

    priority     = fields.get("priority", "Normal")
    recipient    = fields.get("to", "N/A")
    subject_line = fields.get("subject", "")

    # Extract body
    body_lines = []
    in_body    = False
    for line in content.split("\n"):
        if in_body:
            body_lines.append(line)
        elif line.strip().lower().startswith(("message:", "post:", "body:", "details:")):
            in_body = True
            after   = line.split(":", 1)[1].strip()
            if after:
                body_lines.append(after)
    body   = "\n".join(body_lines).strip() if body_lines else content.strip()
    quoted = "\n".join(f"> {line}" for line in body.split("\n"))

    # Channel-specific meta rows
    meta_extra = ""
    if channel == "Email":
        meta_extra = f"| Recipient | {recipient} |\n"
        if subject_line:
            meta_extra += f"| Subject | {subject_line} |\n"
    elif channel == "WhatsApp":
        meta_extra = f"| Recipient | {recipient} |\n| Client | {fields.get('client', 'N/A')} |\n"
    elif channel == "LinkedIn":
        meta_extra = f"| Author | {fields.get('author', 'AI Employee Team')} |\n| Topic | {fields.get('topic', 'General')} |\n"

    plan_md = f"""# PLAN: {task_name}

| Field | Value |
|-------|-------|
| Source | Needs_Action/{filepath.name} |
| Created | {today} |
| Channel | {channel} |
| Priority | {priority} |
{meta_extra}| Planner | Regex (no AI key) |
| Status | Ready for Approval |

## Analysis

| Check | Result |
|-------|--------|
| Has content | {"Yes" if body else "No"} |
| Channel detected | {channel} |
| Actionable | {"Yes" if body else "Needs Review"} |

## Drafted Content

{quoted}

## Next Step

Approve ACTION_{task_name}.md in Pending_Approval/ to execute.
"""

    action_md = f"""# ACTION: {task_name}

## Status: PENDING APPROVAL

| Field | Value |
|-------|-------|
| Channel | {channel} |
{meta_extra}| Created | {today} |
| Priority | {priority} |

## Drafted {channel} Content

{quoted}

## Result: PENDING — Awaiting Human Approval
"""
    return plan_md, action_md


# ──────────────────────────────────────────────
# SMART PLANNER — AI first, regex fallback
# ──────────────────────────────────────────────

def smart_planner(filepath: Path, content: str) -> tuple[str, str]:
    """
    Claude reasoning loop: uses Groq AI (free) for intelligent planning.
    Falls back to regex parsing when no AI key is available.
    Returns (plan_markdown, action_markdown).
    """
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_groq  = groq_key and "your_" not in groq_key and len(groq_key) > 10

    if has_groq:
        try:
            from agents import run_platinum_pipeline
            print(f"  [PLANNER] Running AI reasoning for {filepath.name}...")
            ai_result = run_platinum_pipeline(content, filepath.name)
            return _build_ai_plan(filepath, content, ai_result)
        except Exception as e:
            print(f"  [PLANNER] AI reasoning failed ({e}), using regex fallback...")

    return _regex_planner(filepath, content)


# ──────────────────────────────────────────────
# CUSTOM EXECUTOR (sends via real channels)
# ──────────────────────────────────────────────

def channel_executor(filepath: Path, content: str) -> str:
    """
    Execute an approved ACTION file by sending via the detected channel.
    Returns a status string.
    """
    filename_upper = filepath.name.upper()

    # --- EMAIL ---
    if "EMAIL" in filename_upper:
        data = parse_email_from_action(str(filepath))
        to = data.get("to")
        subject = data.get("subject", "No Subject")
        body = data.get("body", "")
        if to and body:
            return send_email(to, subject, body)
        return "Email drafted (missing recipient or body)"

    # --- WHATSAPP ---
    if "WHATSAPP" in filename_upper:
        data = parse_whatsapp_from_action(str(filepath))
        to = data.get("to")
        client = data.get("client", "unknown")
        message = data.get("message", "")
        if to and message:
            return send_whatsapp(to, client, message)
        return "WhatsApp drafted (missing recipient or message)"

    # --- LINKEDIN ---
    if "LINKEDIN" in filename_upper:
        data = parse_linkedin_from_action(str(filepath))
        author = data.get("author", "AI Employee Team")
        topic = data.get("topic", "General")
        post_body = data.get("post_body", "")
        hashtags = data.get("hashtags", "")
        if post_body:
            return publish_linkedin(author, topic, post_body, hashtags)
        return "LinkedIn drafted (missing post body)"

    # --- TWITTER / X ---
    if "TWITTER" in filename_upper or "_X_" in filename_upper:
        try:
            from twitter_sender import parse_twitter_from_action, post_tweet
            data    = parse_twitter_from_action(str(filepath))
            topic   = data.get("topic", "Business Update")
            body    = data.get("post_body", "")
            if body:
                return post_tweet(topic, body)
            # fallback: use raw content
            return post_tweet("Business Update", content[:280])
        except Exception as e:
            return f"Twitter error: {e}"

    # --- FACEBOOK ---
    if "FACEBOOK" in filename_upper:
        try:
            from social_media_sender import dispatch_social, parse_social_from_action
            data  = parse_social_from_action(str(filepath))
            topic = data.get("topic", "Business Update")
            body  = data.get("post_body", "") or content.strip()[:600]
            status, _, _ = dispatch_social("Facebook", topic, body)
            return status
        except Exception as e:
            return f"Facebook error: {e}"

    # --- INSTAGRAM ---
    if "INSTAGRAM" in filename_upper:
        try:
            from social_media_sender import dispatch_social, parse_social_from_action
            data  = parse_social_from_action(str(filepath))
            topic = data.get("topic", "Business Update")
            body  = data.get("post_body", "") or content.strip()[:600]
            status, _, _ = dispatch_social("Instagram", topic, body)
            return status
        except Exception as e:
            return f"Instagram error: {e}"

    # --- GENERAL ---
    return "Completed (general task)"


# ──────────────────────────────────────────────
# AUTO-APPROVE HELPER (for --demo mode)
# ──────────────────────────────────────────────

def auto_approve(sm: StateMachine):
    """Move all Pending_Approval files to Approved (demo mode)."""
    files = sm.list_files(State.PENDING_APPROVAL)
    for f in files:
        sm.transition(f, State.PENDING_APPROVAL, State.APPROVED, actor="auto_approve")
        print(f"  [AUTO-APPROVED] {f.name}")


def interactive_approve(sm: StateMachine):
    """Ask human to approve each file via CLI (live mode)."""
    files = sm.list_files(State.PENDING_APPROVAL)
    if not files:
        print("  No tasks pending approval.")
        return

    for f in files:
        content = sm.read_file(f)
        print(f"\n  {'─'*40}")
        print(f"  Task: {f.name}")
        print(f"  {'─'*40}")

        # Show preview (first 12 lines)
        lines = content.split("\n")[:12]
        for line in lines:
            print(f"    {line}")
        if len(content.split("\n")) > 12:
            print(f"    ... ({len(content.splitlines())} total lines)")

        choice = input("\n  Approve? (y/n/q): ").strip().lower()
        if choice == "q":
            print("  Stopping approval.")
            break
        elif choice in ("y", "yes", ""):
            # Update status text inside the file
            updated = content.replace("PENDING APPROVAL", "APPROVED")
            updated = updated.replace("PENDING — Awaiting Human Approval", "APPROVED — Ready to Execute")
            f.write_text(updated, encoding="utf-8")
            sm.transition(f, State.PENDING_APPROVAL, State.APPROVED, actor="human")
        else:
            sm.transition(f, State.PENDING_APPROVAL, State.REJECTED, actor="human")
            print(f"  [REJECTED] {f.name}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    sm = StateMachine(VAULT)

    mode = "--demo"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    # ── Status only ──
    if mode == "--status":
        sm.print_status()
        return

    # ── Daemon mode ──
    if mode == "--daemon":
        print("\n  Daemon mode: approval must happen externally")
        print("  (Drag files in Obsidian or use another terminal)\n")
        sm.run_daemon(interval=60, planner=smart_planner, executor=channel_executor)
        return

    # ── Single pass modes ──
    print(f"\n{'='*50}")
    print(f"  AI EMPLOYEE STATE MACHINE v2.0")
    print(f"  Mode: {'AUTO DEMO' if mode == '--demo' else 'LIVE (Interactive)'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print(f"{'='*50}")

    # Stage 1-2: Inbox → Needs_Action → Plan
    sm.process_inbox()
    sm.process_needs_action(planner=smart_planner)

    # Stage 3: Approval
    if mode == "--demo":
        auto_approve(sm)
    else:
        interactive_approve(sm)

    # Stage 4-5: Execute + Reject handling
    sm.process_approved(executor=channel_executor)
    sm.process_rejected()

    # Final status
    sm._update_dashboard()
    sm.print_status()

    print(f"{'='*50}")
    print("  PIPELINE COMPLETE")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
