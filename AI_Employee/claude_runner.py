"""
Claude Runner -- The AI Brain (Platinum Tier)
=============================================
Reads tasks from Needs_Action/, analyzes them with the Platinum 4-agent
pipeline, creates PLAN + ACTION files, moves to Pending_Approval.

Modes (priority order):
  - PLATINUM (ENABLE_PLATINUM=True) : 4-agent pipeline
      THINKER -> PLANNER -> EXECUTOR -> REVIEWER (with memory + self-improvement)
  - GOLD (MULTISTEP_AI=True)        : 3-step Groq pipeline (THINK->PLAN->EXECUTE)
  - LIVE AI (single call)            : one API call (faster)
  - FALLBACK                         : regex parsing (no API key)

Set GROQ_API_KEY or GEMINI_API_KEY in AI_Employee/.env for free AI.
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

# Try loading Anthropic client (paid)
try:
    import anthropic
    _HAS_ANTHROPIC = True
except ImportError:
    _HAS_ANTHROPIC = False

# Try loading Groq client (FREE)
try:
    from groq import Groq
    _HAS_GROQ = True
except ImportError:
    _HAS_GROQ = False

# Try loading Gemini client (FREE)
try:
    import google.generativeai as genai
    _HAS_GEMINI = True
except ImportError:
    _HAS_GEMINI = False

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=True)
except ImportError:
    pass


def _get_api_key() -> str:
    """Get Anthropic API key (paid)."""
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key and "your_" not in key and len(key) > 20:
        return key
    return ""


def _get_groq_key() -> str:
    """Get Groq API key (FREE)."""
    key = os.getenv("GROQ_API_KEY", "")
    if key and "your_" not in key and len(key) > 10:
        return key
    return ""


def _get_gemini_key() -> str:
    """Get Google Gemini API key (FREE)."""
    key = os.getenv("GEMINI_API_KEY", "")
    if key and "your_" not in key and len(key) > 10:
        return key
    return ""


def _is_ai_mode() -> bool:
    """True if ANY real AI is available (Groq, Gemini, or Anthropic)."""
    return bool(_get_groq_key()) or bool(_get_gemini_key()) or (_HAS_ANTHROPIC and bool(_get_api_key()))


def _ai_backend() -> str:
    """Which AI backend is active."""
    if _get_groq_key() and _HAS_GROQ:
        return "groq"
    if _get_gemini_key() and _HAS_GEMINI:
        return "gemini"
    if _get_api_key() and _HAS_ANTHROPIC:
        return "anthropic"
    return "fallback"


def _get_multistep_setting() -> bool:
    """Check if multi-step AI reasoning is enabled."""
    try:
        from config import MULTISTEP_AI
        return MULTISTEP_AI
    except ImportError:
        return True  # Default: Gold Tier multi-step ON


def _get_platinum_setting() -> bool:
    """Check if Platinum 4-agent pipeline is enabled."""
    try:
        from config import ENABLE_PLATINUM
        return ENABLE_PLATINUM
    except ImportError:
        return True  # Default: Platinum ON


def _get_model() -> str:
    """Get AI model name from config."""
    try:
        from config import AI_MODEL
        return AI_MODEL
    except ImportError:
        return "claude-sonnet-4-5-20250929"


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
# FREE AI: GROQ (llama-3.3-70b -- completely free)
# ──────────────────────────────────────────────

GROQ_MODEL = "llama-3.3-70b-versatile"   # free, very capable


def _groq_chat(messages: list, max_tokens: int = 1024) -> str:
    """Single Groq API call. Returns response text."""
    client = Groq(api_key=_get_groq_key())
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def _parse_json_safe(text: str) -> dict | None:
    """Parse JSON from AI response, handling markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def ai_multistep_groq(content: str, filename: str) -> dict:
    """
    Gold Tier multi-step reasoning using FREE Groq API.

    STEP 1 -- THINK  : What is this task? Which channel? Priority?
    STEP 2 -- PLAN   : Break into concrete steps.
    STEP 3 -- EXECUTE: Draft final professional content.
    """
    # ── STEP 1: THINK ──────────────────────────────────────
    print(f"  [THINK] Analyzing with Groq (free)...")
    think_text = _groq_chat([
        {"role": "system", "content": (
            "You are an AI Employee. Analyze this task and return ONLY valid JSON:\n"
            '{"channel":"Email|WhatsApp|LinkedIn|General",'
            '"priority":"High|Medium|Low",'
            '"recipient":"who to contact",'
            '"intent":"one sentence what this task wants done",'
            '"tone":"formal|friendly|urgent"}'
        )},
        {"role": "user", "content": f"File: {filename}\n\n{content}"},
    ], max_tokens=300)

    think = _parse_json_safe(think_text) or {
        "channel": "General", "priority": "Normal",
        "recipient": "N/A", "intent": content[:100], "tone": "professional"
    }
    print(f"  [THINK] Channel={think.get('channel')} | Priority={think.get('priority')}")
    print(f"  [THINK] Intent: {think.get('intent','')[:70]}")

    # ── STEP 2: PLAN ───────────────────────────────────────
    print(f"  [PLAN] Creating action plan...")
    plan_text = _groq_chat([
        {"role": "system", "content": (
            "You are an AI Employee. Given a task analysis, return ONLY valid JSON:\n"
            '{"steps":["step 1","step 2","step 3"],'
            '"subject":"subject line",'
            '"action_required":"send_email|send_whatsapp|post_linkedin|review"}'
        )},
        {"role": "user", "content": (
            f"File: {filename}\n"
            f"Channel: {think.get('channel')}\n"
            f"Intent: {think.get('intent')}\n"
            f"Recipient: {think.get('recipient')}\n"
            f"Task:\n{content}"
        )},
    ], max_tokens=300)

    plan = _parse_json_safe(plan_text) or {
        "steps": ["Analyze", "Draft response", "Send"],
        "subject": "Task Response",
        "action_required": "review"
    }
    print(f"  [PLAN] Steps: {' > '.join(plan.get('steps', []))[:70]}")

    # ── STEP 3: EXECUTE ────────────────────────────────────
    print(f"  [EXECUTE] Drafting final content...")
    channel = think.get("channel", "General")
    channel_instruction = {
        "Email":    "Write a complete professional email body only (no subject line).",
        "WhatsApp": "Write a short friendly WhatsApp message (max 3 sentences).",
        "LinkedIn": "Write an engaging LinkedIn post with 3-5 hashtags at end.",
        "General":  "Write a professional response.",
    }.get(channel, "Write a professional response.")

    drafted = _groq_chat([
        {"role": "system", "content": (
            f"You are an AI Employee. {channel_instruction} "
            f"Tone: {think.get('tone','professional')}. "
            "Return ONLY the message content -- no labels, no JSON."
        )},
        {"role": "user", "content": (
            f"Task: {think.get('intent')}\n"
            f"Recipient: {think.get('recipient')}\n"
            f"Steps: {', '.join(plan.get('steps', []))}\n"
            f"Original:\n{content}"
        )},
    ], max_tokens=600)

    print(f"  [EXECUTE] Draft ready ({len(drafted)} chars)")

    return {
        "channel":          think.get("channel", "General"),
        "priority":         think.get("priority", "Normal"),
        "recipient":        think.get("recipient", "N/A"),
        "subject":          plan.get("subject", "Task Response"),
        "summary":          think.get("intent", ""),
        "plan_steps":       plan.get("steps", []),
        "action_required":  plan.get("action_required", "review"),
        "tone":             think.get("tone", "professional"),
        "drafted_response": drafted,
        "ai_mode":          "Gold-Groq (THINK->PLAN->EXECUTE) [FREE]",
    }


# ──────────────────────────────────────────────
# GOLD TIER: MULTI-STEP AI REASONING
# ──────────────────────────────────────────────

def ai_multistep_analyze_task(content: str, filename: str) -> dict:
    """
    Gold Tier: Three separate Claude API calls.

    STEP 1 -- THINK : Understand what the task is
    STEP 2 -- PLAN  : Break it into concrete steps
    STEP 3 -- EXECUTE: Draft the final professional content

    Returns same dict shape as ai_analyze_task().
    """
    client = anthropic.Anthropic()
    model  = _get_model()

    print(f"  [THINK] Analyzing task...")

    # ── STEP 1: THINK ──────────────────────────────────────
    think_resp = client.messages.create(
        model=model,
        max_tokens=512,
        system=(
            "You are an AI Employee. Analyze the given task and return JSON:\n"
            '{"channel": "Email|WhatsApp|LinkedIn|General", '
            '"priority": "High|Medium|Low", '
            '"recipient": "who to contact", '
            '"intent": "one sentence: what does this task want me to do", '
            '"tone": "formal|friendly|urgent"}'
            "\nReturn ONLY valid JSON."
        ),
        messages=[{"role": "user", "content": f"File: {filename}\n\n{content}"}]
    )

    think_text = think_resp.content[0].text.strip()
    if think_text.startswith("```"):
        think_text = re.sub(r"^```(?:json)?\s*", "", think_text)
        think_text = re.sub(r"\s*```$", "", think_text.strip())

    try:
        think = json.loads(think_text)
    except json.JSONDecodeError:
        think = {"channel": "General", "priority": "Normal",
                 "recipient": "N/A", "intent": content[:100], "tone": "professional"}

    print(f"  [THINK] Channel={think.get('channel')} | Priority={think.get('priority')}")
    print(f"  [THINK] Intent: {think.get('intent', '')[:80]}")

    # ── STEP 2: PLAN ───────────────────────────────────────
    print(f"  [PLAN] Creating action plan...")

    plan_resp = client.messages.create(
        model=model,
        max_tokens=512,
        system=(
            "You are an AI Employee. Given a task analysis, create a short action plan.\n"
            "Return JSON: {\"steps\": [\"step 1\", \"step 2\", \"step 3\"], "
            "\"subject\": \"email/message subject line\", "
            "\"action_required\": \"send_email|send_whatsapp|post_linkedin|review\"}"
            "\nReturn ONLY valid JSON."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Task file: {filename}\n"
                f"Channel: {think.get('channel')}\n"
                f"Intent: {think.get('intent')}\n"
                f"Recipient: {think.get('recipient')}\n"
                f"Original content:\n{content}"
            )
        }]
    )

    plan_text = plan_resp.content[0].text.strip()
    if plan_text.startswith("```"):
        plan_text = re.sub(r"^```(?:json)?\s*", "", plan_text)
        plan_text = re.sub(r"\s*```$", "", plan_text.strip())

    try:
        plan = json.loads(plan_text)
    except json.JSONDecodeError:
        plan = {"steps": ["Analyze task", "Draft response", "Send via channel"],
                "subject": "Task Response", "action_required": "review"}

    print(f"  [PLAN] Steps: {' -> '.join(plan.get('steps', []))[:80]}")

    # ── STEP 3: EXECUTE ────────────────────────────────────
    print(f"  [EXECUTE] Drafting final content...")

    channel = think.get("channel", "General")
    channel_instruction = {
        "Email":    "Write a complete professional email body (no subject line, just the body).",
        "WhatsApp": "Write a concise, friendly WhatsApp message (max 3 sentences).",
        "LinkedIn": "Write an engaging LinkedIn post with 3-5 relevant hashtags at the end.",
        "General":  "Write a professional response or note.",
    }.get(channel, "Write a professional response.")

    execute_resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=(
            f"You are an AI Employee. {channel_instruction}\n"
            f"Tone: {think.get('tone', 'professional')}.\n"
            "Return ONLY the message content -- no labels, no JSON, no markdown headers."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Task: {think.get('intent')}\n"
                f"Recipient: {think.get('recipient')}\n"
                f"Action plan steps: {', '.join(plan.get('steps', []))}\n"
                f"Original task:\n{content}"
            )
        }]
    )

    drafted = execute_resp.content[0].text.strip()
    print(f"  [EXECUTE] Draft ready ({len(drafted)} chars)")

    # ── Combine into final result ──────────────────────────
    return {
        "channel":          think.get("channel", "General"),
        "priority":         think.get("priority", "Normal"),
        "recipient":        think.get("recipient", "N/A"),
        "subject":          plan.get("subject", "Task Response"),
        "summary":          think.get("intent", ""),
        "plan_steps":       plan.get("steps", []),
        "action_required":  plan.get("action_required", "review"),
        "tone":             think.get("tone", "professional"),
        "drafted_response": drafted,
        "ai_mode":          "Gold (THINK->PLAN->EXECUTE)",
    }


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
    mode = ai_result.get("ai_mode", "Claude AI") if ai_result else "Regex Parser"

    # AI-enhanced fields
    if ai_result:
        priority  = ai_result.get("priority", "Normal")
        summary   = ai_result.get("summary", "Task analysis pending")
        tone      = ai_result.get("tone", "professional")
        action    = ai_result.get("action_required", "review")
        body_text = ai_result.get("drafted_response", data.get("body", "No content"))
        # Gold tier: include plan steps in PLAN file
        plan_steps = ai_result.get("plan_steps", [])
        steps_md = "\n".join(f"{i+1}. {s}" for i, s in enumerate(plan_steps)) if plan_steps else "N/A"
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

## Result: PENDING -- Awaiting Human Approval
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

    # Detect active AI backend
    backend = _ai_backend()
    backend_labels = {
        "groq":      "LIVE AI -- Groq/Llama3 (FREE)",
        "gemini":    "LIVE AI -- Google Gemini (FREE)",
        "anthropic": "LIVE AI -- Anthropic Claude (PAID)",
        "fallback":  "FALLBACK -- regex only (add GROQ_API_KEY to .env for free AI)",
    }
    print(f"[Brain] Mode: {backend_labels.get(backend, backend)}")
    ai_mode = backend != "fallback"

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
            print(f"[Brain] SKIP: {filename} already has a PLAN -- archiving original")
            try:
                done_dir = VAULT / "Done"
                done_dir.mkdir(parents=True, exist_ok=True)
                (done_dir / filename).write_text(
                    file_path.read_text(encoding="utf-8") +
                    f"\n\n---\n**Archived (duplicate skip):** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
                    encoding="utf-8"
                )
                file_path.unlink()
            except Exception:
                pass
            continue
        if (PENDING_APPROVAL / f"ACTION_{task_name}.md").exists():
            print(f"[Brain] SKIP: {filename} already has an ACTION -- not reprocessing")
            continue

        print(f"\n{'='*50}")
        print(f"[Brain] Processing: {filename}")
        print(f"{'='*50}")

        # Step 1: Parse with regex (always, for structured field extraction)
        data = parse_task_file(str(file_path))
        channel = detect_channel(filename, data["raw"])
        if data.get("channel"):
            channel = data["channel"]

        # Step 2: AI analysis -- PLATINUM > GOLD > Fallback
        ai_result = None
        if ai_mode:
            use_platinum  = _get_platinum_setting()
            use_multistep = _get_multistep_setting()

            # ── PLATINUM: 4-agent pipeline (THINKER->PLANNER->EXECUTOR->REVIEWER) ──
            if use_platinum:
                try:
                    print(f"[Brain] Using PLATINUM 4-agent pipeline [FREE]")
                    from agents import run_platinum_pipeline
                    ai_result = run_platinum_pipeline(data["raw"], filename)
                except Exception as e:
                    print(f"[Brain] PLATINUM pipeline failed ({e}), falling back to GOLD")
                    ai_result = None

            # ── GOLD fallback: 3-step multi-step ───────────────────────────────
            if ai_result is None:
                try:
                    if backend == "groq" and _HAS_GROQ:
                        print(f"[Brain] Using GOLD multi-step Groq (THINK->PLAN->EXECUTE) [FREE]")
                        ai_result = ai_multistep_groq(data["raw"], filename)
                    elif backend == "anthropic" and _HAS_ANTHROPIC:
                        if use_multistep:
                            print(f"[Brain] Using GOLD Anthropic multi-step (THINK->PLAN->EXECUTE)")
                            ai_result = ai_multistep_analyze_task(data["raw"], filename)
                        else:
                            ai_result = ai_analyze_task(data["raw"], filename)
                except Exception as e:
                    print(f"[Brain] GOLD fallback also failed ({e}), using regex")

            if ai_result:
                ai_channel = ai_result.get("channel", "")
                if ai_channel in ("Email", "WhatsApp", "LinkedIn"):
                    channel = ai_channel

        print(f"[Brain] Channel: {channel}")
        print(f"[Brain] Priority: {(ai_result or {}).get('priority', data.get('priority', 'Normal'))}")
        print(f"[Brain] AI Mode: {(ai_result or {}).get('ai_mode', 'Fallback (no API key)') if ai_result else 'Fallback (no API key)'}")

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

        # Step 5: Archive original task file (move Needs_Action -> Done)
        try:
            done_dir = VAULT / "Done"
            done_dir.mkdir(parents=True, exist_ok=True)
            done_stamp = (
                f"\n\n---\n"
                f"**Processed by:** AI Brain\n"
                f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"**Plan:** PLAN_{task_name}.md\n"
                f"**Action:** ACTION_{task_name}.md\n"
            )
            (done_dir / filename).write_text(
                file_path.read_text(encoding="utf-8") + done_stamp, encoding="utf-8"
            )
            file_path.unlink()
            print(f"[Brain] Task archived: {filename} -> Done/")
        except Exception as e:
            print(f"[Brain] Archive warning: {e}")

        processed.append({
            "file":          filename,
            "channel":       channel,
            "plan":          f"PLAN_{task_name}.md",
            "action":        f"ACTION_{task_name}.md",
            "status":        "Pending Approval",
            "ai_mode":       ai_result.get("ai_mode", "Claude AI") if ai_result else "Fallback",
            "quality_score": ai_result.get("quality_score") if ai_result else None,
            "memories_used": ai_result.get("memories_used", 0) if ai_result else 0,
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
