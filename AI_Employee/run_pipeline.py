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

from state_machine import StateMachine, State
from email_sender import parse_email_from_action, send_email
from whatsapp_sender import parse_whatsapp_from_action, send_whatsapp
from linkedin_sender import parse_linkedin_from_action, publish_linkedin


VAULT = BASE / "AI_Employee_Vault"


# ──────────────────────────────────────────────
# CUSTOM PLANNER (uses claude_runner logic)
# ──────────────────────────────────────────────

def smart_planner(filepath: Path, content: str) -> tuple[str, str]:
    """
    Enhanced planner that parses structured fields from task files.
    Returns (plan_markdown, action_markdown).
    """
    task_name = filepath.stem
    today = datetime.now().strftime("%Y-%m-%d")

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

    priority = fields.get("priority", "Normal")
    recipient = fields.get("to", "N/A")
    subject_line = fields.get("subject", "")

    # Extract body (everything after Message:/Body:/Post:/Details: label)
    body_lines = []
    in_body = False
    for line in content.split("\n"):
        if in_body:
            body_lines.append(line)
        elif line.strip().lower().startswith(("message:", "post:", "body:", "details:")):
            in_body = True
            after = line.split(":", 1)[1].strip()
            if after:
                body_lines.append(after)
    body = "\n".join(body_lines).strip() if body_lines else content.strip()
    quoted = "\n".join(f"> {line}" for line in body.split("\n"))

    # Build channel-specific meta rows
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
{meta_extra}| Status | Ready for Approval |

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
