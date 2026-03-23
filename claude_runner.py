"""
Claude Runner — The AI Brain
=============================
Reads tasks from Needs_Action/, analyzes them with Claude AI,
creates PLAN + ACTION files, moves to Pending_Approval.

This is the core intelligence layer of the AI Employee.

Modes:
  - LIVE AI: Uses Anthropic Claude API for real AI reasoning
  - FALLBACK: Uses regex-based parsing when API key is unavailable

The system auto-detects which mode to use based on ANTHROPIC_API_KEY in .env.
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path

# Import centralized channel detection
from channel_dispatcher import detect_channel


# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

BASE = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"
NEEDS_ACTION = VAULT / "Needs_Action"
PLANS = VAULT / "Plans"
PENDING_APPROVAL = VAULT / "Pending_Approval"

# Try loading Anthropic client
try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

# Try loading env
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=False)
except ImportError:
    pass


def _get_api_key() -> str:
    """Get Anthropic API key from environment."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key and "your_" not in key and len(key) > 10:
        return key
    return ""


def _is_ai_mode() -> bool:
    """Check if real AI mode is available."""
    return _HAS_ANTHROPIC and bool(_get_api_key())


# ──────────────────────────────────────────────
# AI ANALYSIS (Claude API)
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI Employee assistant. Your job is to analyze incoming tasks
and generate professional responses.

Given a task, you MUST return valid JSON with these fields:
{
  "channel": "Email" or "WhatsApp" or "LinkedIn" or "General",
  "priority": "High" or "Medium" or "Low",
  "recipient": "email or phone or name of recipient",
  "subject": "subject line (for email) or topic",
  "summary": "1-2 sentence summary of what this task is about",
  "drafted_response": "A professionally drafted response body ready to send",
  "tone": "formal" or "friendly" or "urgent",
  "action_required": "send_email" or "send_whatsapp" or "post_linkedin" or "review"
}

Rules:
- For emails: draft a complete, professional email body
- For WhatsApp: draft a concise, friendly message
- For LinkedIn: draft an engaging post with relevant hashtags
- Always maintain a professional tone appropriate to the channel
- If the task is unclear, set action_required to "review"
- Return ONLY valid JSON, no markdown or extra text"""


def ai_analyze_task(content: str, filename: str) -> dict:
    """
    Use Claude API to analyze a task and generate a response plan.

    Returns dict with: channel, priority, recipient, subject, summary,
                       drafted_response, tone, action_required
    """
    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Filename: {filename}\n\nTask Content:\n{content}"
            }]
        )

        response_text = response.content[0].text.strip()

        # Parse JSON from response (handle markdown code blocks)
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)

        result = json.loads(response_text)

        # Validate required fields
        required = ["channel", "priority", "drafted_response"]
        for field in required:
            if field not in result:
                result[field] = "General" if field == "channel" else "Normal" if field == "priority" else content

        print(f"  [AI] Claude analysis complete")
        print(f"  [AI] Channel: {result.get('channel')} | Priority: {result.get('priority')}")
        print(f"  [AI] Summary: {result.get('summary', 'N/A')[:80]}")

        return result

    except json.JSONDecodeError:
        print(f"  [AI] Warning: Could not parse Claude response as JSON, using fallback")
        return None
    except anthropic.APIError as e:
        print(f"  [AI] API error: {e}")
        return None
    except Exception as e:
        print(f"  [AI] Unexpected error: {e}")
        return None


# ──────────────────────────────────────────────
# REGEX FALLBACK PARSER (original logic)
# ──────────────────────────────────────────────

def parse_task_file(file_path):
    """Parse any task file and extract structured data using regex."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    data = {
        "raw": content,
        "channel": None,
        "to": None,
        "client": None,
        "subject": None,
        "priority": "Normal",
        "author": None,
        "topic": None,
        "hashtags": None,
        "body": None,
    }

    # Extract fields via regex
    field_patterns = {
        "channel": r"Channel:\s*(.+)",
        "to": r"To:\s*(.+)",
        "client": r"Client:\s*(.+)",
        "subject": r"Subject:\s*(.+)",
        "priority": r"Priority:\s*(.+)",
        "author": r"Author:\s*(.+)",
        "topic": r"Topic:\s*(.+)",
    }

    for field, pattern in field_patterns.items():
        match = re.search(pattern, content)
        if match:
            data[field] = match.group(1).strip()

    # Body extraction
    body_lines = []
    in_body = False
    for line in content.split("\n"):
        if in_body:
            body_lines.append(line)
        elif line.strip().lower().startswith(("message:", "post:", "body:", "details:")):
            in_body = True
            after_label = line.split(":", 1)[1].strip()
            if after_label:
                body_lines.append(after_label)

    body_text = "\n".join(body_lines).strip() if body_lines else None
    if not body_text:
        body_text = content.strip()
    data["body"] = body_text

    # Hashtags
    hash_match = re.search(r"(#\w+(?:\s+#\w+)+)", content)
    if hash_match:
        data["hashtags"] = hash_match.group(1).strip()

    return data


# ──────────────────────────────────────────────
# PLAN + ACTION GENERATORS
# ──────────────────────────────────────────────

def generate_plan(filename, data, channel, plan_id, ai_result=None):
    """Generate a structured PLAN markdown file."""
    today = datetime.now().strftime("%Y-%m-%d")
    task_name = os.path.splitext(filename)[0]
    mode = "Claude AI" if ai_result else "Regex Parser"

    # AI-enhanced fields
    if ai_result:
        priority = ai_result.get("priority", "Normal")
        summary = ai_result.get("summary", "Task analysis pending")
        tone = ai_result.get("tone", "professional")
        action = ai_result.get("action_required", "review")
        body_text = ai_result.get("drafted_response", data.get("body", "No content"))
    else:
        priority = data.get("priority", "Normal")
        summary = f"Process {channel.lower()} task from {filename}"
        tone = "professional"
        action = "review"
        body_text = data.get("body", "No content found")

    # Channel-specific target
    if channel == "Email":
        target_line = f"| Recipient          | {data.get('to') or (ai_result or {}).get('recipient', 'N/A')}"
        purpose = f"Send email reply to {data.get('to', 'client')}"
    elif channel == "WhatsApp":
        target_line = f"| Recipient          | {data.get('to', 'N/A')} ({data.get('client', '')})"
        purpose = f"Send WhatsApp message to {data.get('client', 'client')}"
    elif channel == "LinkedIn":
        target_line = f"| Author             | {data.get('author', 'AI Employee Team')}"
        purpose = f"Publish LinkedIn post about {data.get('topic', 'topic')}"
    else:
        target_line = f"| Target             | {data.get('to', 'N/A')}"
        purpose = "Process and complete task"

    quoted_body = "\n".join(f"> {line}" for line in body_text.split("\n"))

    plan = f"""# PLAN: {task_name}

## Meta

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| Source File        | Needs_Action/{filename}                    |
| Plan ID            | PLAN-{plan_id:03d}                          |
| Plan Created       | {today}                                    |
| Analysis Mode      | {mode}                                     |
| Status             | Ready for Approval                         |
| Priority           | {priority}                                 |
| Channel            | {channel}                                  |
{target_line}                                                       |
| Assigned To        | AI Employee                                |

---

## 1. Task Summary

**From:** AI Employee System
**Channel:** {channel}
**Purpose:** {purpose}
**AI Summary:** {summary}
**Tone:** {tone}
**Action:** {action}

---

## 2. Analysis

| Check              | Result                              |
|--------------------|-------------------------------------|
| File exists        | Yes                                 |
| Has content        | {"Yes" if body_text else "No"}      |
| Actionable         | {"Yes" if body_text else "Needs Review"} |
| Channel detected   | {channel}                           |
| AI Analyzed        | {"Yes" if ai_result else "No (fallback mode)"} |

---

## 3. Drafted Content

{quoted_body}

---

## 4. Next Step

Upon approval -> **Approved/ACTION_{task_name}.md** -> executor sends + logs
"""
    return plan


def generate_action(filename, data, channel, ai_result=None):
    """Generate an ACTION markdown file for Pending_Approval."""
    today = datetime.now().strftime("%Y-%m-%d")
    task_name = os.path.splitext(filename)[0]

    # Use AI-drafted response if available, else regex-extracted body
    if ai_result:
        body_text = ai_result.get("drafted_response", data.get("body", "No content"))
        priority = ai_result.get("priority", "Normal")
    else:
        body_text = data.get("body", "No content")
        priority = data.get("priority", "Normal")

    quoted_body = "\n".join(f"> {line}" for line in body_text.split("\n"))

    # Build meta table
    meta_rows = f"| Channel            | {channel}                                  |\n"

    if channel == "Email":
        recipient = data.get("to") or (ai_result or {}).get("recipient", "N/A")
        subject = data.get("subject") or (ai_result or {}).get("subject", "")
        meta_rows += f"| Recipient          | {recipient}                    |\n"
        if subject:
            meta_rows += f"| Subject            | {subject}                      |\n"
    elif channel == "WhatsApp":
        meta_rows += f"| Recipient          | {data.get('to', 'N/A')}                    |\n"
        meta_rows += f"| Client             | {data.get('client', 'N/A')}                |\n"
    elif channel == "LinkedIn":
        meta_rows += f"| Author             | {data.get('author', 'AI Employee Team')}   |\n"
        meta_rows += f"| Topic              | {data.get('topic', 'General')}             |\n"
        if data.get("hashtags"):
            meta_rows += f"| Hashtags           | {data.get('hashtags')}                     |\n"

    meta_rows += f"| Created            | {today}                                    |\n"
    meta_rows += f"| Priority           | {priority}                                 |"

    action = f"""# ACTION: {task_name}

## Status: PENDING APPROVAL

| Field              | Value                                      |
|--------------------|--------------------------------------------|
{meta_rows}

## Drafted {channel} Content

{quoted_body}

## Result: PENDING — Awaiting Human Approval
"""
    return action


# ──────────────────────────────────────────────
# MAIN PROCESSOR
# ──────────────────────────────────────────────

def process_needs_action():
    """Main function: process all files in Needs_Action/"""
    if not NEEDS_ACTION.exists():
        print("[Brain] Needs_Action folder not found.")
        return []

    files = [f for f in os.listdir(NEEDS_ACTION) if os.path.isfile(NEEDS_ACTION / f)]

    if not files:
        print("[Brain] No tasks in Needs_Action/")
        return []

    # Check AI mode
    ai_mode = _is_ai_mode()
    if ai_mode:
        print("[Brain] Mode: LIVE AI (Claude API)")
    else:
        if _HAS_ANTHROPIC:
            print("[Brain] Mode: FALLBACK (no API key — set ANTHROPIC_API_KEY in .env)")
        else:
            print("[Brain] Mode: FALLBACK (pip install anthropic for AI mode)")

    # Count existing plans for ID numbering
    existing_plans = len(os.listdir(PLANS)) if PLANS.exists() else 0
    PLANS.mkdir(parents=True, exist_ok=True)
    PENDING_APPROVAL.mkdir(parents=True, exist_ok=True)

    processed = []

    for i, filename in enumerate(files):
        file_path = NEEDS_ACTION / filename
        task_name = os.path.splitext(filename)[0]
        plan_id = existing_plans + i + 1

        # Guard: skip if PLAN or ACTION already exists (idempotency)
        if (PLANS / f"PLAN_{task_name}.md").exists():
            print(f"[Brain] SKIP: {filename} already has a PLAN — not reprocessing")
            continue
        if (PENDING_APPROVAL / f"ACTION_{task_name}.md").exists():
            print(f"[Brain] SKIP: {filename} already has an ACTION — not reprocessing")
            continue

        print(f"\n{'='*50}")
        print(f"[Brain] Processing: {filename}")
        print(f"{'='*50}")

        # Step 1: Parse with regex (always, for structured field extraction)
        data = parse_task_file(str(file_path))
        channel = detect_channel(filename, data["raw"])
        if data.get("channel"):
            channel = data["channel"]

        # Step 2: AI analysis (if available)
        ai_result = None
        if ai_mode:
            ai_result = ai_analyze_task(data["raw"], filename)
            if ai_result:
                # AI may override channel detection
                ai_channel = ai_result.get("channel", "")
                if ai_channel in ("Email", "WhatsApp", "LinkedIn"):
                    channel = ai_channel

        print(f"[Brain] Channel: {channel}")
        print(f"[Brain] Priority: {(ai_result or {}).get('priority', data.get('priority', 'Normal'))}")
        print(f"[Brain] AI Mode: {'Active' if ai_result else 'Fallback'}")

        # Step 3: Generate PLAN (audit trail)
        plan_content = generate_plan(filename, data, channel, plan_id, ai_result)
        plan_file = PLANS / f"PLAN_{task_name}.md"
        plan_file.write_text(plan_content, encoding="utf-8")
        print(f"[Brain] Plan created: PLAN_{task_name}.md")

        # Step 4: Generate ACTION (for approval)
        action_content = generate_action(filename, data, channel, ai_result)
        action_file = PENDING_APPROVAL / f"ACTION_{task_name}.md"
        action_file.write_text(action_content, encoding="utf-8")
        print(f"[Brain] Action created: ACTION_{task_name}.md -> Pending_Approval/")

        processed.append({
            "file": filename,
            "channel": channel,
            "plan": f"PLAN_{task_name}.md",
            "action": f"ACTION_{task_name}.md",
            "status": "Pending Approval",
            "ai_mode": "Claude AI" if ai_result else "Fallback",
        })

    return processed


if __name__ == "__main__":
    os.chdir(str(BASE))
    print("=" * 50)
    print("  AI EMPLOYEE BRAIN")
    print(f"  AI Mode: {'LIVE (Claude API)' if _is_ai_mode() else 'FALLBACK (regex)'}")
    print("=" * 50)

    results = process_needs_action()
    print(f"\n[Brain] Processed {len(results)} task(s)")
    for r in results:
        print(f"  - {r['file']} -> {r['channel']} ({r['ai_mode']}) -> {r['status']}")
