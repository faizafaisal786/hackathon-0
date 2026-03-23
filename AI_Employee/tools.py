"""
PLATINUM Tool Registry
========================
All tools available for AI agents to dynamically select and execute.

Each tool:
  - Has a name, description, and parameters schema
  - Is registered in TOOLS dict
  - Can be called by agents via execute_tool(name, params)
  - Logs every execution to the audit trail

Available Tools:
  send_email      -- Send email via Gmail SMTP (DEMO mode if no credentials)
  write_file      -- Write content to vault folder
  log_decision    -- Append decision to audit trail
  create_task     -- Create new task in Inbox for future processing
  search_memory   -- Find similar past tasks from memory
  web_search      -- Free DuckDuckGo search (no API key needed)
"""

import os
import json
import smtplib
import html
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

VAULT = Path(__file__).parent / "AI_Employee_Vault"


# ═══════════════════════════════════════════════════════════
# TOOL FUNCTIONS
# ═══════════════════════════════════════════════════════════

def tool_send_email(params: dict) -> dict:
    """
    Send an email via Gmail SMTP.
    Falls back to DEMO mode (writes file) if credentials are missing.
    Params: to (str), subject (str), body (str)
    """
    to      = params.get("to", "").strip()
    subject = params.get("subject", "").strip()
    body    = params.get("body", "").strip()

    if not to or not subject or not body:
        return {"success": False, "error": "Missing required params: to, subject, body"}

    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_user or not gmail_pass or "your_" in gmail_user:
        # DEMO MODE: write to file
        demo_dir  = VAULT / "WhatsApp_Sent"
        demo_dir.mkdir(parents=True, exist_ok=True)
        demo_file = demo_dir / f"EMAIL_DEMO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        demo_file.write_text(
            f"DEMO EMAIL\nTo: {to}\nSubject: {subject}\n\n{body}",
            encoding="utf-8",
        )
        return {"success": True, "mode": "demo", "path": str(demo_file)}

    try:
        msg = MIMEMultipart()
        msg["From"]    = gmail_user
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_pass)
            server.send_message(msg)
        return {"success": True, "mode": "live", "to": to, "subject": subject}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_write_file(params: dict) -> dict:
    """
    Write content to a file inside the vault.
    Params: filename (str), content (str), folder (str, default='Done')
    """
    filename = params.get("filename", f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    content  = params.get("content", "")
    folder   = params.get("folder", "Done")

    if not content:
        return {"success": False, "error": "No content provided"}

    target_dir = VAULT / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
    file_path = target_dir / safe_name
    file_path.write_text(content, encoding="utf-8")

    return {"success": True, "path": str(file_path), "bytes": len(content)}


def tool_log_decision(params: dict) -> dict:
    """
    Append a decision or event to today's audit log.
    Params: action (str), actor (str), details (str), severity (str, default='INFO')
    """
    action   = params.get("action", "DECISION")
    actor    = params.get("actor", "ai_agent")
    details  = params.get("details", "")
    severity = params.get("severity", "INFO")

    today    = datetime.now().strftime("%Y-%m-%d")
    log_dir  = VAULT / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{today}.json"

    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        data = raw if isinstance(raw, dict) else {
            "events": raw,
            "total_events": len(raw),
        }
    else:
        data = {
            "audit_date":   today,
            "system":       "AI Employee Platinum",
            "version":      "3.0",
            "total_events": 0,
            "events":       [],
        }

    data["total_events"] = data.get("total_events", 0) + 1
    data["events"].append({
        "id":        f"EVT-{data['total_events']:04d}",
        "timestamp": datetime.now().isoformat(),
        "actor":     actor,
        "action":    action,
        "details":   details,
        "severity":  severity,
    })

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {"success": True, "logged": action}


def tool_create_task(params: dict) -> dict:
    """
    Create a new task file in Inbox/ for future pipeline processing.
    Params: filename (str), content (str), priority (str, default='Normal')
    """
    filename = params.get(
        "filename",
        f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
    )
    content  = params.get("content", "")
    priority = params.get("priority", "Normal")

    if not content:
        return {"success": False, "error": "No content provided"}

    inbox = VAULT / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
    task_content = (
        f"# Task: {safe_name}\n\n"
        f"Priority: {priority}\n"
        f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Created By: AI Agent (tool_create_task)\n\n"
        f"## Content\n\n{content}\n"
    )
    (inbox / safe_name).write_text(task_content, encoding="utf-8")
    return {"success": True, "created": safe_name}


def tool_search_memory(params: dict) -> dict:
    """
    Search past task memory for similar completed tasks.
    Params: query (str), channel (str, optional), top_k (int, optional)
    """
    query   = params.get("query", "")
    channel = params.get("channel")
    top_k   = int(params.get("top_k", 3))

    if not query:
        return {"success": False, "error": "No query provided"}

    try:
        from memory_manager import retrieve_similar, format_memory_context
        memories = retrieve_similar(query, channel, top_k)
        context  = format_memory_context(memories)
        return {"success": True, "count": len(memories), "context": context}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_web_search(params: dict) -> dict:
    """
    Free DuckDuckGo Instant Answer API search. No API key required.
    Params: query (str), max_results (int, optional, default=3)
    """
    query       = params.get("query", "")
    max_results = int(params.get("max_results", 3))

    if not query:
        return {"success": False, "error": "No query provided"}

    try:
        encoded = urllib.parse.quote(query)
        url     = (
            f"https://api.duckduckgo.com/?q={encoded}"
            "&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (AI Employee Bot)"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = []

        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "Summary"),
                "text":  html.unescape(data["Abstract"])[:500],
                "url":   data.get("AbstractURL", ""),
            })

        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "text":  html.unescape(topic.get("Text", ""))[:300],
                    "url":   topic.get("FirstURL", ""),
                })
            if len(results) >= max_results:
                break

        return {"success": True, "results": results, "count": len(results)}

    except Exception as e:
        return {"success": False, "error": str(e), "results": []}


# ═══════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═══════════════════════════════════════════════════════════

TOOLS = {
    "send_email": {
        "name":        "send_email",
        "description": "Send an email via Gmail SMTP. Use for Email channel tasks.",
        "parameters":  {"to": "str", "subject": "str", "body": "str"},
        "execute":     tool_send_email,
    },
    "write_file": {
        "name":        "write_file",
        "description": "Write content to a file in the vault (specify folder).",
        "parameters":  {"filename": "str", "content": "str", "folder": "str (optional)"},
        "execute":     tool_write_file,
    },
    "log_decision": {
        "name":        "log_decision",
        "description": "Log an important decision or action to the audit trail.",
        "parameters":  {"action": "str", "actor": "str", "details": "str"},
        "execute":     tool_log_decision,
    },
    "create_task": {
        "name":        "create_task",
        "description": "Create a new task in Inbox/ for future pipeline processing.",
        "parameters":  {"filename": "str", "content": "str", "priority": "str (optional)"},
        "execute":     tool_create_task,
    },
    "search_memory": {
        "name":        "search_memory",
        "description": "Search past task memory for similar completed tasks and patterns.",
        "parameters":  {"query": "str", "channel": "str (optional)", "top_k": "int (optional)"},
        "execute":     tool_search_memory,
    },
    "web_search": {
        "name":        "web_search",
        "description": "Free DuckDuckGo web search -- useful for research or factual tasks.",
        "parameters":  {"query": "str", "max_results": "int (optional)"},
        "execute":     tool_web_search,
    },
}


# ═══════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════

def get_tool_descriptions() -> str:
    """Return formatted tool list for AI system prompts."""
    lines = ["\nAVAILABLE TOOLS (request these by name in tool_calls):"]
    for name, tool in TOOLS.items():
        params = ", ".join(f"{k}={v}" for k, v in tool["parameters"].items())
        lines.append(f"  {name}: {tool['description']}")
        lines.append(f"    params: {{{params}}}")
    return "\n".join(lines)


def execute_tool(tool_name: str, params: dict) -> dict:
    """Execute a single tool by name. Returns result dict."""
    if tool_name not in TOOLS:
        return {"success": False, "error": f"Unknown tool: '{tool_name}'"}
    try:
        result = TOOLS[tool_name]["execute"](params)
        # Auto-log every tool execution
        tool_log_decision({
            "action":  "TOOL_EXECUTED",
            "actor":   "tool_system",
            "details": (
                f"{tool_name} -> "
                f"{'SUCCESS' if result.get('success') else 'FAILED'}: "
                f"{str(result)[:100]}"
            ),
        })
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_tool_calls(tool_calls: list) -> list:
    """
    Execute a list of tool calls.
    Input:  [{"name": "tool_name", "params": {...}}, ...]
    Output: [{"tool": "tool_name", "result": {...}}, ...]
    """
    results = []
    for call in tool_calls:
        name   = call.get("name", "")
        params = call.get("params", {})
        result = execute_tool(name, params)
        results.append({"tool": name, "result": result})
    return results
