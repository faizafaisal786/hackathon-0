"""
PLATINUM Multi-Agent System
============================
Four specialized agents with distinct roles and responsibilities.

Pipeline: THINKER -> PLANNER -> EXECUTOR -> REVIEWER (-> REVISION loop if score < 7)

  THINKER   -- Understands task, retrieves memory context, picks tools
  PLANNER   -- Creates step-by-step execution plan with quality checklist
  EXECUTOR  -- Drafts final ready-to-send content, calls any required tools
  REVIEWER  -- Scores 1-10, approves or requests revision with specific feedback

All agents use FREE AI (Groq Llama-3.3-70b -> Gemini 1.5 Flash -> fallback).
All decisions are logged via tool_log_decision.
Memory is read before and written after every pipeline run.
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

from memory_manager import (
    retrieve_similar,
    format_memory_context,
    get_improved_prompt,
    save_memory,
    update_stats,
)
from tools import (
    get_tool_descriptions,
    execute_tool_calls,
    tool_log_decision,
)


# ── Free AI Backend ────────────────────────────────────────────────────────────

def _get_groq_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    return key if key and "your_" not in key and len(key) > 10 else ""


def _get_gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    return key if key and "your_" not in key and len(key) > 10 else ""


def _active_backend() -> str:
    if _get_groq_key():
        return "groq"
    if _get_gemini_key():
        return "gemini"
    return "fallback"


def _call_ai(messages: list, system: str = None, max_tokens: int = 1024) -> str:
    """
    Universal AI call. Groq (free) -> Gemini (free) -> hardcoded fallback.
    Always returns a string -- never raises.
    """
    # ── Try Groq ────────────────────────────────────────────────────────────
    groq_key = _get_groq_key()
    if groq_key:
        try:
            from groq import Groq
            client = Groq(api_key=groq_key)
            full_messages = []
            if system:
                full_messages.append({"role": "system", "content": system})
            full_messages.extend(messages)
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=full_messages,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"  [AI] Groq failed: {e} -- trying Gemini...")

    # ── Try Gemini ───────────────────────────────────────────────────────────
    gemini_key = _get_gemini_key()
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            parts = []
            if system:
                parts.append(f"SYSTEM INSTRUCTIONS:\n{system}")
            for msg in messages:
                role    = msg.get("role", "user").upper()
                content = msg.get("content", "")
                parts.append(f"{role}:\n{content}")
            response = model.generate_content("\n\n".join(parts))
            return response.text.strip()
        except Exception as e:
            print(f"  [AI] Gemini failed: {e} -- using fallback")

    # ── Fallback: structured minimal response ────────────────────────────────
    user_content = messages[-1].get("content", "") if messages else ""
    return (
        '{"channel":"General","priority":"Normal","recipient":"N/A",'
        f'"intent":"{user_content[:80].replace(chr(34), chr(39))}",'
        '"tone":"professional","confidence":0.3,"tool_calls":[],'
        '"reasoning":"No AI backend available"}'
    )


def _parse_json(text: str) -> dict | None:
    """Safely parse JSON from AI response. Handles code fences and embedded JSON."""
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text.strip())
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON object within text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


# ════════════════════════════════════════════════════════════════════════════
# AGENT 1: THINKER
# Role: Understand what the task actually wants. Pick channel, tone, tools.
# ════════════════════════════════════════════════════════════════════════════

class ThinkerAgent:

    def __init__(self):
        self.name = "THINKER"

    def think(self, content: str, filename: str) -> dict:
        """
        Input:  raw task content, filename
        Output: {channel, priority, recipient, intent, tone, confidence,
                 tool_calls, reasoning, memory_context, memories_found}
        """
        print(f"  [THINKER] Analyzing: {filename}")

        # Retrieve relevant past task memory FIRST
        memories       = retrieve_similar(content[:300], top_k=3)
        memory_context = format_memory_context(memories)

        # Get current (possibly improved) prompt
        base_prompt = get_improved_prompt("system_think")
        tool_descs  = get_tool_descriptions()

        system = f"""{base_prompt}
{memory_context}
{tool_descs}

Analyze the task and return ONLY valid JSON:
{{
  "channel": "Email|WhatsApp|LinkedIn|General",
  "priority": "High|Medium|Low",
  "recipient": "who to contact or N/A",
  "intent": "one clear sentence describing what this task wants done",
  "tone": "formal|friendly|urgent|professional",
  "confidence": 0.1-1.0,
  "tool_calls": [
    {{"name": "tool_name", "params": {{"key": "value"}}}}
  ],
  "reasoning": "brief explanation of your channel and intent decision"
}}

tool_calls is a list of any tools to run NOW (can be empty []).
Only include tools genuinely needed for understanding or setup."""

        raw = _call_ai(
            messages=[{
                "role":    "user",
                "content": f"File: {filename}\n\nTask content:\n{content}",
            }],
            system=system,
            max_tokens=600,
        )

        result = _parse_json(raw) or {
            "channel":    "General",
            "priority":   "Normal",
            "recipient":  "N/A",
            "intent":     content[:100],
            "tone":       "professional",
            "confidence": 0.3,
            "tool_calls": [],
            "reasoning":  "JSON parse failed -- defaults applied",
        }

        # Execute any immediate tool calls the thinker requested
        if result.get("tool_calls"):
            tool_results           = execute_tool_calls(result["tool_calls"])
            result["tool_results"] = tool_results

        result["memory_context"] = memory_context
        result["memories_found"] = len(memories)

        tool_log_decision({
            "action":  "THINKER_COMPLETE",
            "actor":   "thinker_agent",
            "details": (
                f"file={filename} channel={result.get('channel')} "
                f"priority={result.get('priority')} "
                f"confidence={result.get('confidence', 0):.2f} "
                f"memories_used={len(memories)}"
            ),
        })

        print(
            f"  [THINKER] Channel={result.get('channel')} | "
            f"Priority={result.get('priority')} | "
            f"Confidence={result.get('confidence', 0):.2f} | "
            f"Memories={len(memories)}"
        )
        print(f"  [THINKER] Intent: {result.get('intent','')[:80]}")

        return result


# ════════════════════════════════════════════════════════════════════════════
# AGENT 2: PLANNER
# Role: Turn the thinker's understanding into a concrete, ordered action plan.
# ════════════════════════════════════════════════════════════════════════════

class PlannerAgent:

    def __init__(self):
        self.name = "PLANNER"

    def plan(self, content: str, filename: str, think: dict) -> dict:
        """
        Input:  task content, filename, thinker output
        Output: {steps, subject, action_required, tools_to_use,
                 quality_checklist, estimated_quality}
        """
        print(f"  [PLANNER] Creating execution plan...")

        base_prompt    = get_improved_prompt("system_plan")
        memory_snippet = (think.get("memory_context") or "")[:400]

        system = f"""{base_prompt}

Thinker context:
  Channel:   {think.get('channel')}
  Intent:    {think.get('intent')}
  Recipient: {think.get('recipient')}
  Tone:      {think.get('tone')}
  Confidence:{think.get('confidence', 0.5):.2f}

{memory_snippet}

Return ONLY valid JSON:
{{
  "steps": ["specific step 1", "specific step 2", "specific step 3"],
  "subject": "email or message subject line",
  "action_required": "send_email|send_whatsapp|post_linkedin|write_file|review",
  "tools_to_use": ["tool_name_1"],
  "quality_checklist": [
    "Has clear opening referencing the task",
    "Contains specific actionable detail",
    "Appropriate tone for {think.get('channel','General')}",
    "Ends with clear next step or CTA"
  ],
  "estimated_quality": 7
}}

steps must be concrete and specific -- no generic filler steps.
tools_to_use is which tools the Executor should call (can be [])."""

        raw = _call_ai(
            messages=[{
                "role":    "user",
                "content": (
                    f"File: {filename}\n"
                    f"Channel: {think.get('channel')}\n"
                    f"Intent: {think.get('intent')}\n\n"
                    f"Task content:\n{content}"
                ),
            }],
            system=system,
            max_tokens=500,
        )

        result = _parse_json(raw) or {
            "steps":             ["Analyze task", "Draft professional response", "Verify content", "Send"],
            "subject":           "Task Response",
            "action_required":   "review",
            "tools_to_use":      [],
            "quality_checklist": [
                "Has clear opening",
                "Contains specific actionable content",
                "Appropriate channel tone",
                "Clear call to action",
            ],
            "estimated_quality": 6,
        }

        tool_log_decision({
            "action":  "PLANNER_COMPLETE",
            "actor":   "planner_agent",
            "details": (
                f"file={filename} "
                f"steps={len(result.get('steps', []))} "
                f"action={result.get('action_required')} "
                f"est_quality={result.get('estimated_quality', 0)}/10"
            ),
        })

        print(
            f"  [PLANNER] Steps: {' -> '.join(result.get('steps', []))[:80]}"
        )
        print(
            f"  [PLANNER] Action: {result.get('action_required')} | "
            f"Est.Quality: {result.get('estimated_quality', 0)}/10"
        )

        return result


# ════════════════════════════════════════════════════════════════════════════
# AGENT 3: EXECUTOR
# Role: Draft the final, ready-to-send content. Execute tool calls.
# ════════════════════════════════════════════════════════════════════════════

class ExecutorAgent:

    def __init__(self):
        self.name = "EXECUTOR"

    def execute(self, content: str, filename: str, think: dict, plan: dict) -> dict:
        """
        Input:  task content, filename, thinker output, planner output
        Output: {drafted_response, tools_executed, execution_status, char_count}
        """
        print(f"  [EXECUTOR] Drafting final content...")

        channel = think.get("channel", "General")
        tone    = think.get("tone", "professional")

        channel_instruction = {
            "Email": (
                "Write a complete professional email body only (no subject line). "
                "Include: greeting, 2-3 focused body paragraphs, professional closing, name. "
                "Be specific. Reference the original task directly."
            ),
            "WhatsApp": (
                "Write a concise, friendly WhatsApp message (2-4 sentences MAX). "
                "Natural conversational tone. No headers. No bullet points."
            ),
            "LinkedIn": (
                "Write an engaging LinkedIn post (3-5 short paragraphs). "
                "Hook on line 1. Share insights in body. End with 3-5 relevant #hashtags."
            ),
            "General": (
                "Write a professional response or document. "
                "Clear structure. Specific content. Actionable conclusions."
            ),
        }.get(channel, "Write a professional response.")

        base_prompt    = get_improved_prompt("system_execute")
        memory_snippet = (think.get("memory_context") or "")[:250]
        checklist_str  = "\n".join(
            f"  - {c}" for c in plan.get("quality_checklist", [])
        )

        system = f"""{base_prompt}

CHANNEL INSTRUCTION:
{channel_instruction}

Tone: {tone}

Quality checklist (meet ALL of these):
{checklist_str}

{memory_snippet}

Return ONLY the message content -- no labels, no JSON, no markdown headers.
Write as if this will be sent immediately."""

        drafted = _call_ai(
            messages=[{
                "role":    "user",
                "content": (
                    f"Task: {think.get('intent')}\n"
                    f"Recipient: {think.get('recipient', 'N/A')}\n"
                    f"Steps: {' | '.join(plan.get('steps', []))}\n\n"
                    f"Original task content:\n{content}"
                ),
            }],
            system=system,
            max_tokens=900,
        )

        # Execute any tools the planner specified
        tool_results = []
        for tool_name in plan.get("tools_to_use", []):
            if tool_name == "log_decision":
                res = execute_tool_calls([{
                    "name": "log_decision",
                    "params": {
                        "action":  "EXECUTOR_TOOL",
                        "actor":   "executor_agent",
                        "details": f"Tool '{tool_name}' called during execution of {filename}",
                    },
                }])
                tool_results.extend(res)

        tool_log_decision({
            "action":  "EXECUTOR_COMPLETE",
            "actor":   "executor_agent",
            "details": (
                f"file={filename} "
                f"drafted={len(drafted)} chars | "
                f"channel={channel} | "
                f"tools_called={len(tool_results)}"
            ),
        })

        print(f"  [EXECUTOR] Draft: {len(drafted)} chars | Channel: {channel}")

        return {
            "drafted_response": drafted,
            "tools_executed":   tool_results,
            "execution_status": "complete",
            "char_count":       len(drafted),
        }


# ════════════════════════════════════════════════════════════════════════════
# AGENT 4: REVIEWER
# Role: Score output 1-10. Approve or request specific revision.
# ════════════════════════════════════════════════════════════════════════════

class ReviewerAgent:

    QUALITY_THRESHOLD = 7   # Minimum score to approve
    MAX_REVISIONS     = 2   # Max revision rounds before forcing approval

    def __init__(self):
        self.name = "REVIEWER"

    def review(self, drafted: str, think: dict, plan: dict, original: str, filename: str = "unknown") -> dict:
        """
        Input:  drafted content, context dicts, original task
        Output: {score, approved, strengths, weaknesses, feedback, revision_needed}
        """
        print(f"  [REVIEWER] Reviewing output quality...")

        channel   = think.get("channel", "General")
        checklist = plan.get("quality_checklist", [
            "Has clear opening referencing the task",
            "Contains specific actionable content",
            "Appropriate tone for channel",
            "Ends with clear next step or call to action",
        ])
        checklist_str = "\n".join(f"  - {c}" for c in checklist)

        base_prompt = get_improved_prompt("system_review")

        system = f"""{base_prompt}

Channel: {channel}
Intent:  {think.get('intent')}
Recipient: {think.get('recipient')}

Quality checklist (check each item):
{checklist_str}

Score the drafted content and return ONLY valid JSON:
{{
  "score": 1-10,
  "approved": true|false,
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1 (if any)"],
  "feedback": "specific revision instruction (required if score < {self.QUALITY_THRESHOLD})",
  "revision_needed": true|false
}}

Scoring guide:
  9-10 = Outstanding, send immediately
  7-8  = Good, approved
  5-6  = Acceptable but needs revision
  1-4  = Poor, must revise
approved=true only when score >= {self.QUALITY_THRESHOLD}."""

        raw = _call_ai(
            messages=[{
                "role":    "user",
                "content": (
                    f"Original task (first 300 chars):\n{original[:300]}\n\n"
                    f"Drafted content to review:\n{drafted}"
                ),
            }],
            system=system,
            max_tokens=400,
        )

        result = _parse_json(raw) or {
            "score":           7,
            "approved":        True,
            "strengths":       ["Content drafted successfully"],
            "weaknesses":      [],
            "feedback":        "",
            "revision_needed": False,
        }

        # Enforce threshold strictly
        score              = int(result.get("score", 7))
        approved           = score >= self.QUALITY_THRESHOLD
        result["approved"]         = approved
        result["revision_needed"]  = not approved
        result["score"]            = score

        tool_log_decision({
            "action":  "REVIEWER_COMPLETE",
            "actor":   "reviewer_agent",
            "details": (
                f"file={filename} "
                f"score={score}/10 approved={approved} "
                f"revision={result.get('revision_needed')}"
            ),
        })

        status = "APPROVED" if approved else f"REVISION NEEDED (score={score})"
        print(f"  [REVIEWER] {status}")
        if result.get("feedback") and not approved:
            print(f"  [REVIEWER] Feedback: {result['feedback'][:90]}")

        return result

    def request_revision(
        self,
        original_drafted: str,
        feedback: str,
        think: dict,
        original_task: str,
    ) -> str:
        """Ask Executor to revise based on reviewer feedback."""
        print(f"  [REVIEWER] Requesting revision...")

        channel = think.get("channel", "General")
        channel_instruction = {
            "Email":     "Complete professional email body only.",
            "WhatsApp":  "Concise friendly WhatsApp message (2-4 sentences).",
            "LinkedIn":  "Engaging LinkedIn post with hashtags.",
            "General":   "Professional response.",
        }.get(channel, "Professional response.")

        revised = _call_ai(
            messages=[{
                "role":    "user",
                "content": (
                    f"Original task (summary): {original_task[:200]}\n\n"
                    f"Your previous draft:\n{original_drafted}\n\n"
                    f"Reviewer feedback:\n{feedback}\n\n"
                    "Revise the content addressing ALL feedback points."
                ),
            }],
            system=(
                f"You are an AI Employee revising a draft based on quality feedback. "
                f"{channel_instruction} "
                "Address every feedback point explicitly. "
                "Return ONLY the revised content -- no labels, no JSON."
            ),
            max_tokens=900,
        )

        print(f"  [REVIEWER] Revision complete: {len(revised)} chars")
        return revised


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════════════

def run_platinum_pipeline(content: str, filename: str) -> dict:
    """
    Execute the full PLATINUM 4-agent pipeline.

    Flow:
      THINKER -> PLANNER -> EXECUTOR -> REVIEWER
                                    ↓ (if score < 7)
                                  REVISION -> REVIEWER (max 2 rounds)

    Saves result to memory. Updates stats.
    Returns full result dict (same shape as Gold tier ai_result).
    """
    start_time = datetime.now()
    backend    = _active_backend()

    thinker  = ThinkerAgent()
    planner  = PlannerAgent()
    executor = ExecutorAgent()
    reviewer = ReviewerAgent()

    # Phase 1 -- THINK
    think_result = thinker.think(content, filename)

    # Phase 2 -- PLAN
    plan_result = planner.plan(content, filename, think_result)

    # Phase 3 -- EXECUTE
    exec_result = executor.execute(content, filename, think_result, plan_result)
    drafted     = exec_result["drafted_response"]

    # Phase 4 -- REVIEW (with revision loop)
    review_result   = reviewer.review(drafted, think_result, plan_result, content, filename)
    final_score     = review_result.get("score", 7)
    revision_count  = 0

    while (
        review_result.get("revision_needed")
        and revision_count < ReviewerAgent.MAX_REVISIONS
    ):
        revision_count += 1
        print(
            f"  [PIPELINE] Revision {revision_count}/{ReviewerAgent.MAX_REVISIONS}..."
        )
        drafted       = reviewer.request_revision(
            drafted,
            review_result.get("feedback", "Improve clarity and specificity."),
            think_result,
            content,
        )
        review_result = reviewer.review(drafted, think_result, plan_result, content, filename)
        final_score   = review_result.get("score", 7)

    elapsed = round((datetime.now() - start_time).total_seconds(), 2)

    # Save to Memory
    save_memory({
        "filename":                  filename,
        "channel":                   think_result.get("channel", "General"),
        "intent":                    think_result.get("intent", ""),
        "outcome":                   "PENDING",
        "quality_score":             final_score,
        "was_rejected":              False,
        "ai_backend":                backend,
        "revisions_needed":          revision_count,
        "confidence":                think_result.get("confidence", 0.5),
        "drafted_response_snippet":  drafted[:200],
        "tags": [
            think_result.get("channel", ""),
            think_result.get("tone", ""),
        ],
    })

    # Update Stats
    update_stats(
        channel=think_result.get("channel", "General"),
        outcome="PENDING",
        quality_score=final_score,
        backend=backend,
    )

    tool_log_decision({
        "action":  "PLATINUM_PIPELINE_COMPLETE",
        "actor":   "pipeline_orchestrator",
        "details": (
            f"file={filename} "
            f"channel={think_result.get('channel')} "
            f"quality={final_score}/10 "
            f"revisions={revision_count} "
            f"elapsed={elapsed}s "
            f"backend={backend}"
        ),
    })

    print(
        f"  [PLATINUM] Done | Quality={final_score}/10 | "
        f"Revisions={revision_count} | {elapsed}s | backend={backend}"
    )

    return {
        # Core output (same shape as Gold tier)
        "channel":          think_result.get("channel", "General"),
        "priority":         think_result.get("priority", "Normal"),
        "recipient":        think_result.get("recipient", "N/A"),
        "subject":          plan_result.get("subject", "Task Response"),
        "summary":          think_result.get("intent", ""),
        "drafted_response": drafted,
        "tone":             think_result.get("tone", "professional"),
        "action_required":  plan_result.get("action_required", "review"),
        "plan_steps":       plan_result.get("steps", []),
        # Quality metrics
        "quality_score":    final_score,
        "review_approved":  review_result.get("approved", True),
        "revisions_made":   revision_count,
        # Meta
        "confidence":       think_result.get("confidence", 0.5),
        "memories_used":    think_result.get("memories_found", 0),
        "elapsed_seconds":  elapsed,
        "ai_mode":          f"PLATINUM (THINKER->PLANNER->EXECUTOR->REVIEWER) [{backend}]",
        # Full agent outputs (for audit trail)
        "_think":           think_result,
        "_plan":            plan_result,
        "_exec":            exec_result,
        "_review":          review_result,
    }
