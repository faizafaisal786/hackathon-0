"""
AI Employee MCP Server — Silver Tier
======================================
Model Context Protocol server exposing AI Employee capabilities
as external tools for Claude and other MCP-compatible clients.

Tools exposed:
  send_email          -- Send email via Gmail SMTP
  send_whatsapp       -- Send WhatsApp message via Twilio
  post_linkedin       -- Post to LinkedIn (API or simulation)
  create_vault_task   -- Drop a new task file into Inbox/
  read_dashboard      -- Read current Dashboard.md status
  move_task           -- Move a task between pipeline stages
  get_pipeline_status -- Get file counts for all pipeline stages
  read_vault_file     -- Read any file from the vault

Usage:
  python mcp_server.py              # Start MCP server (stdio transport)
  python mcp_server.py --test       # Run diagnostic test (no server)

Install dependency:
  pip install fastmcp
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=True)
except ImportError:
    pass


# ── Dependency Check ────────────────────────────────────────────────────────

def _check_fastmcp():
    try:
        import fastmcp
        return True
    except ImportError:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# Each function is a standalone tool — no MCP dependency in the logic itself.
# ══════════════════════════════════════════════════════════════════════════════

def _tool_send_email(to: str, subject: str, body: str) -> dict:
    """
    Send an email via Gmail SMTP.
    Falls back to demo mode (writes file) if credentials missing.
    """
    if not to or not subject or not body:
        return {"success": False, "error": "Missing required fields: to, subject, body"}

    try:
        from email_sender import send_email
        result = send_email(to, subject, body)
        return {"success": True, "result": result, "to": to, "subject": subject}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_send_whatsapp(to: str, client: str, message: str) -> dict:
    """
    Send a WhatsApp message via Twilio.
    Falls back to simulation mode if credentials missing.
    """
    if not to or not message:
        return {"success": False, "error": "Missing required fields: to, message"}

    try:
        from whatsapp_sender import send_whatsapp
        result = send_whatsapp(to, client or "client", message)
        return {"success": True, "result": result, "to": to}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_post_linkedin(author: str, topic: str, body: str, hashtags: str = "") -> dict:
    """
    Post to LinkedIn via API or simulation mode.
    Requires LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID in .env for live mode.
    """
    if not body:
        return {"success": False, "error": "Missing required field: body"}

    try:
        from linkedin_sender import publish_linkedin
        result = publish_linkedin(
            author  or "AI Employee",
            topic   or "General",
            body,
            hashtags or None,
        )
        return {"success": True, "result": result, "author": author, "topic": topic}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_create_vault_task(filename: str, content: str) -> dict:
    """
    Create a new task file in Inbox/ for the AI Employee to process.
    The watcher will pick it up and move it to Needs_Action automatically.
    """
    if not filename or not content:
        return {"success": False, "error": "Missing required fields: filename, content"}

    inbox = VAULT / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = filename.strip().replace(" ", "_")
    if not safe_name.endswith(".md"):
        safe_name += ".md"

    task_path = inbox / safe_name

    try:
        task_path.write_text(content, encoding="utf-8")
        return {
            "success": True,
            "file":    safe_name,
            "path":    str(task_path),
            "message": f"Task '{safe_name}' created in Inbox/ — watcher will process it",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_read_dashboard() -> dict:
    """
    Read the current Dashboard.md and return its contents + pipeline summary.
    """
    dashboard_path = VAULT / "Dashboard.md"

    if not dashboard_path.exists():
        return {"success": False, "error": "Dashboard.md not found"}

    try:
        content = dashboard_path.read_text(encoding="utf-8")
        return {
            "success":   True,
            "content":   content,
            "last_read": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_get_pipeline_status() -> dict:
    """
    Return file counts for all pipeline stages (Inbox, Needs_Action, Plans,
    Pending_Approval, Approved, Rejected, Done).
    """
    stages = [
        "Inbox", "Needs_Action", "Plans",
        "Pending_Approval", "Approved", "Rejected", "Done",
    ]

    status = {}
    total  = 0

    for stage in stages:
        folder = VAULT / stage
        if folder.exists():
            files = [
                f.name for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() in (".md", ".txt")
            ]
            count         = len(files)
            status[stage] = {"count": count, "files": files[:10]}
            total        += count
        else:
            status[stage] = {"count": 0, "files": []}

    return {
        "success":     True,
        "stages":      status,
        "total_files": total,
        "timestamp":   datetime.now().isoformat(),
    }


def _tool_read_vault_file(folder: str, filename: str) -> dict:
    """
    Read any file from the vault.
    folder: one of Inbox, Needs_Action, Plans, Pending_Approval, Approved, Done, Logs
    filename: the file name (e.g. PLAN_task1.md)
    """
    if not folder or not filename:
        return {"success": False, "error": "Missing required fields: folder, filename"}

    file_path = VAULT / folder / filename

    if not file_path.exists():
        return {"success": False, "error": f"File not found: {folder}/{filename}"}

    # Security: prevent path traversal
    try:
        file_path.resolve().relative_to(VAULT.resolve())
    except ValueError:
        return {"success": False, "error": "Access denied: path outside vault"}

    try:
        content = file_path.read_text(encoding="utf-8")
        return {
            "success":  True,
            "folder":   folder,
            "filename": filename,
            "content":  content,
            "size":     len(content),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_move_task(filename: str, from_stage: str, to_stage: str) -> dict:
    """
    Move a task file between pipeline stages.
    Valid stages: Inbox, Needs_Action, Pending_Approval, Approved, Rejected, Done
    """
    valid_stages = {
        "Inbox", "Needs_Action", "Plans",
        "Pending_Approval", "Approved", "Rejected", "Done",
    }

    if from_stage not in valid_stages or to_stage not in valid_stages:
        return {
            "success": False,
            "error":   f"Invalid stage. Valid: {', '.join(sorted(valid_stages))}",
        }

    src = VAULT / from_stage / filename
    dst = VAULT / to_stage / filename

    if not src.exists():
        return {"success": False, "error": f"File not found: {from_stage}/{filename}"}

    try:
        (VAULT / to_stage).mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return {
            "success":   True,
            "file":      filename,
            "from":      from_stage,
            "to":        to_stage,
            "message":   f"Moved {filename}: {from_stage}/ → {to_stage}/",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# MCP SERVER
# ══════════════════════════════════════════════════════════════════════════════

def build_mcp_server():
    """Build and return the FastMCP server with all tools registered."""
    from fastmcp import FastMCP

    mcp = FastMCP(
        name="AI Employee",
        instructions=(
            "AI Employee MCP Server. Provides tools for sending emails, "
            "WhatsApp messages, LinkedIn posts, managing the Obsidian vault "
            "task pipeline, and reading system status."
        ),
    )

    # ── Tool 1: Send Email ───────────────────────────────────────────────────

    @mcp.tool()
    def send_email(to: str, subject: str, body: str) -> str:
        """
        Send an email via Gmail SMTP.
        Falls back to demo mode (writes .md file) if GMAIL credentials not set.

        Args:
            to:      Recipient email address
            subject: Email subject line
            body:    Email body text
        """
        result = _tool_send_email(to, subject, body)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Tool 2: Send WhatsApp ────────────────────────────────────────────────

    @mcp.tool()
    def send_whatsapp(to: str, message: str, client: str = "client") -> str:
        """
        Send a WhatsApp message via Twilio.
        Falls back to simulation mode if TWILIO credentials not set.

        Args:
            to:      Recipient phone number (e.g. +923001234567)
            message: Message text to send
            client:  Client name for logging (optional)
        """
        result = _tool_send_whatsapp(to, client, message)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Tool 3: Post to LinkedIn ─────────────────────────────────────────────

    @mcp.tool()
    def post_linkedin(body: str, author: str = "AI Employee", topic: str = "General", hashtags: str = "") -> str:
        """
        Post content to LinkedIn via API or simulation mode.
        Live mode requires LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID in .env.

        Args:
            body:     Post content (max 3000 characters)
            author:   Post author name
            topic:    Post topic/category for logging
            hashtags: Hashtags to append (e.g. #AI #Automation)
        """
        result = _tool_post_linkedin(author, topic, body, hashtags)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Tool 4: Create Vault Task ────────────────────────────────────────────

    @mcp.tool()
    def create_task(filename: str, content: str) -> str:
        """
        Create a new task file in the vault Inbox/ folder.
        The AI Employee watcher will automatically pick it up and process it.

        Args:
            filename: Task file name (e.g. EMAIL_client_followup or LINKEDIN_post)
            content:  Task description and details
        """
        result = _tool_create_vault_task(filename, content)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Tool 5: Read Dashboard ───────────────────────────────────────────────

    @mcp.tool()
    def read_dashboard() -> str:
        """
        Read the current AI Employee Dashboard.md.
        Returns the full dashboard content including pipeline status and last update time.
        """
        result = _tool_read_dashboard()
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Tool 6: Get Pipeline Status ──────────────────────────────────────────

    @mcp.tool()
    def get_pipeline_status() -> str:
        """
        Get current file counts for all pipeline stages.
        Returns counts for: Inbox, Needs_Action, Plans, Pending_Approval,
        Approved, Rejected, Done.
        """
        result = _tool_get_pipeline_status()
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Tool 7: Read Vault File ──────────────────────────────────────────────

    @mcp.tool()
    def read_vault_file(folder: str, filename: str) -> str:
        """
        Read any file from the AI Employee vault.

        Args:
            folder:   Vault folder name (Inbox, Needs_Action, Plans,
                      Pending_Approval, Approved, Done, Logs, Briefings)
            filename: File name to read (e.g. PLAN_task1.md)
        """
        result = _tool_read_vault_file(folder, filename)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # ── Tool 8: Move Task ────────────────────────────────────────────────────

    @mcp.tool()
    def move_task(filename: str, from_stage: str, to_stage: str) -> str:
        """
        Move a task file between pipeline stages.
        Use this to manually approve, reject, or reprocess tasks.

        Args:
            filename:   File name to move (e.g. ACTION_EMAIL_client.md)
            from_stage: Current stage (e.g. Pending_Approval)
            to_stage:   Target stage  (e.g. Approved or Rejected)
        """
        result = _tool_move_task(filename, from_stage, to_stage)
        return json.dumps(result, ensure_ascii=False, indent=2)

    return mcp


# ══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC TEST (no MCP required)
# ══════════════════════════════════════════════════════════════════════════════

def run_diagnostic():
    """Test all tool functions without starting the MCP server."""
    print("=" * 60)
    print("  AI EMPLOYEE MCP SERVER — Diagnostic Test")
    print("=" * 60)

    tests = [
        ("get_pipeline_status", lambda: _tool_get_pipeline_status()),
        ("read_dashboard",      lambda: _tool_read_dashboard()),
        ("read_vault_file",     lambda: _tool_read_vault_file("Done", _first_done_file())),
        ("create_vault_task",   lambda: _tool_create_vault_task(
            "MCP_TEST_TASK",
            "Channel: General\nPriority: Low\nMessage: MCP server test task created at "
            + datetime.now().strftime("%Y-%m-%d %H:%M"),
        )),
    ]

    passed = 0
    for name, fn in tests:
        try:
            result = fn()
            ok = result.get("success", False)
            status = "PASS" if ok else "WARN"
            print(f"\n  [{status}] {name}")
            if not ok:
                print(f"        {result.get('error', 'unknown')}")
            else:
                # Print one key piece of info
                if name == "get_pipeline_status":
                    total = result.get("total_files", 0)
                    print(f"        Total files in vault: {total}")
                elif name == "read_dashboard":
                    lines = result.get("content", "").count("\n")
                    print(f"        Dashboard: {lines} lines")
                elif name == "create_vault_task":
                    print(f"        Created: {result.get('file')}")
                else:
                    print(f"        Size: {result.get('size', '?')} chars")
            if ok:
                passed += 1
        except Exception as e:
            print(f"\n  [FAIL] {name}: {e}")

    print(f"\n  {'-'*40}")
    print(f"  Results: {passed}/{len(tests)} tests passed")
    print(f"  fastmcp installed: {_check_fastmcp()}")
    if not _check_fastmcp():
        print("  -> Run: pip install fastmcp")
    print("=" * 60)


def _first_done_file() -> str:
    """Return the name of the first file in Done/ for testing."""
    done = VAULT / "Done"
    if done.exists():
        files = [f.name for f in done.iterdir() if f.suffix in (".md", ".txt")]
        if files:
            return files[0]
    return "Dashboard.md"


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    # ── Diagnostic mode ──
    if "--test" in args:
        run_diagnostic()
        return

    # ── Check fastmcp installed ──
    if not _check_fastmcp():
        print("[ERROR] fastmcp not installed.")
        print("  Run: pip install fastmcp")
        print()
        print("  To test tool functions without MCP:")
        print("  python mcp_server.py --test")
        sys.exit(1)

    # ── Start MCP server ──
    print("=" * 60)
    print("  AI EMPLOYEE MCP SERVER v1.0")
    print(f"  Vault: {VAULT}")
    print("  Transport: stdio (for Claude Code / MCP clients)")
    print("  Tools: 8 registered")
    print("=" * 60)

    mcp = build_mcp_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
