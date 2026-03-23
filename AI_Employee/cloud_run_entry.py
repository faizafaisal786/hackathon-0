"""
Cloud Run Entry Point - Platinum Tier
======================================
Single-pass runner for Google Cloud Run Jobs.

Flow:
  1. Decode Gmail credentials from env vars -> write temp files
  2. Git pull vault from GitHub (hackathon-0)
  3. Run gmail_watcher (single pass) -> Needs_Action/cloud/
  4. Run cloud_agent (single pass) -> Pending_Approval/cloud/
  5. Git commit + push vault changes back
  6. Exit 0 (Cloud Run Job completes)

Triggered every 5 min by Cloud Scheduler.
All secrets passed via Cloud Run environment variables.

Required env vars:
  GROQ_API_KEY             -- AI backend (free)
  GIT_TOKEN                -- GitHub personal access token
  GIT_REPO                 -- GitHub repo URL (default: hackathon-0)
  GMAIL_CREDENTIALS_B64    -- base64(credentials.json) from Google OAuth
  GMAIL_TOKEN_B64          -- base64(token.json) from Google OAuth
"""

import os
import sys
import json
import base64
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# Load .env if present (local dev only)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}", flush=True)


def write_signal(signal_type: str, message: str):
    try:
        signals_dir = VAULT / "Signals"
        signals_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = {
            "type": signal_type,
            "message": message,
            "agent": "cloud_run",
            "timestamp": datetime.now().isoformat(),
        }
        (signals_dir / f"SIGNAL_{ts}_{signal_type}.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# STEP 1 - Decode Gmail credentials from env vars
# ══════════════════════════════════════════════════════════════

def setup_gmail_credentials() -> bool:
    """
    Decode base64-encoded Gmail credentials from env vars.
    Set in Cloud Run secrets:
      GMAIL_CREDENTIALS_B64 = base64(credentials.json)
      GMAIL_TOKEN_B64       = base64(token.json)
    """
    creds_dir = BASE / "watchers"
    creds_dir.mkdir(parents=True, exist_ok=True)

    creds_b64 = os.getenv("GMAIL_CREDENTIALS_B64", "")
    token_b64 = os.getenv("GMAIL_TOKEN_B64", "")

    if creds_b64:
        try:
            creds_json = base64.b64decode(creds_b64).decode("utf-8")
            (creds_dir / "credentials.json").write_text(creds_json)
            log("Gmail credentials decoded OK")
        except Exception as e:
            log(f"WARNING: Could not decode GMAIL_CREDENTIALS_B64: {e}")

    if token_b64:
        try:
            token_json = base64.b64decode(token_b64).decode("utf-8")
            (creds_dir / "token.json").write_text(token_json)
            log("Gmail token decoded OK")
        except Exception as e:
            log(f"WARNING: Could not decode GMAIL_TOKEN_B64: {e}")

    return (creds_dir / "credentials.json").exists()


# ══════════════════════════════════════════════════════════════
# STEP 2 - Git vault sync
# ══════════════════════════════════════════════════════════════

def git_pull() -> bool:
    """Pull latest vault state from GitHub."""
    git_token = os.getenv("GIT_TOKEN", "")
    git_repo  = os.getenv("GIT_REPO", "https://github.com/faizafaisal786/hackathon-0.git")

    if git_token:
        repo_url = git_repo.replace("https://", f"https://{git_token}@")
        subprocess.run(
            ["git", "remote", "set-url", "origin", repo_url],
            cwd=str(BASE.parent), capture_output=True
        )

    subprocess.run(["git", "config", "user.email", "cloud@ai-employee.local"],
                   cwd=str(BASE.parent), capture_output=True)
    subprocess.run(["git", "config", "user.name", "AI Employee Cloud"],
                   cwd=str(BASE.parent), capture_output=True)

    result = subprocess.run(
        ["git", "pull", "--rebase", "origin", "master"],
        cwd=str(BASE.parent), capture_output=True, text=True
    )

    if result.returncode == 0:
        log("Git pull OK")
        return True
    else:
        log(f"Git pull warning: {result.stderr.strip()[:120]}")
        return False


def git_push() -> bool:
    """Stage safe vault files and push cloud agent output back."""
    vault_rel = "AI_Employee/AI_Employee_Vault"
    safe_folders = [
        f"{vault_rel}/Needs_Action",
        f"{vault_rel}/Plans",
        f"{vault_rel}/Pending_Approval",
        f"{vault_rel}/Updates",
        f"{vault_rel}/Signals",
        f"{vault_rel}/Done",
        f"{vault_rel}/Logs",
    ]

    subprocess.run(["git", "add"] + safe_folders,
                   cwd=str(BASE.parent), capture_output=True)

    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(BASE.parent), capture_output=True, text=True
    )

    if not status.stdout.strip():
        log("Nothing new to push - vault up to date")
        return True

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subprocess.run(
        ["git", "commit", "-m",
         f"Cloud agent sync: {ts} [skip ci]",
         "--author=AI Employee Cloud <cloud@ai-employee.local>"],
        cwd=str(BASE.parent), capture_output=True
    )

    result = subprocess.run(
        ["git", "push", "origin", "master"],
        cwd=str(BASE.parent), capture_output=True, text=True
    )

    if result.returncode == 0:
        log("Git push OK - drafts available for local approval")
        return True
    else:
        log(f"Git push failed: {result.stderr.strip()[:120]}")
        write_signal("PUSH_FAILED", result.stderr.strip())
        return False


# ══════════════════════════════════════════════════════════════
# STEP 3 - Gmail watcher single pass
# ══════════════════════════════════════════════════════════════

def run_gmail_watcher() -> int:
    watcher_script = BASE / "gmail_watcher.py"
    if not watcher_script.exists():
        log("gmail_watcher.py not found - skipping")
        return 0

    try:
        result = subprocess.run(
            [sys.executable, str(watcher_script)],
            cwd=str(BASE), capture_output=True, text=True, timeout=120
        )
        output = result.stdout + result.stderr
        created = output.count("Task created:")
        log(f"Gmail: {created} new task(s) created")
        return created
    except subprocess.TimeoutExpired:
        log("Gmail watcher timed out (120s)")
        return 0
    except Exception as e:
        log(f"Gmail watcher error: {e}")
        return 0


# ══════════════════════════════════════════════════════════════
# STEP 4 - Route email tasks to cloud queue
# ══════════════════════════════════════════════════════════════

def route_tasks_to_cloud() -> int:
    needs_action = VAULT / "Needs_Action"
    cloud_queue  = needs_action / "cloud"
    cloud_queue.mkdir(parents=True, exist_ok=True)

    moved = 0
    for f in needs_action.glob("EMAIL_*.md"):
        dest = cloud_queue / f.name
        if not dest.exists():
            shutil.move(str(f), str(dest))
            moved += 1

    if moved:
        log(f"Routed {moved} email task(s) to cloud queue")
    return moved


# ══════════════════════════════════════════════════════════════
# STEP 5 - Cloud agent single pass
# ══════════════════════════════════════════════════════════════

def run_cloud_agent() -> int:
    agent_script = BASE / "cloud_agent.py"
    if not agent_script.exists():
        log("cloud_agent.py not found - skipping")
        return 0

    try:
        result = subprocess.run(
            [sys.executable, str(agent_script)],
            cwd=str(BASE), capture_output=True, text=True, timeout=300
        )
        output = result.stdout + result.stderr
        if output.strip():
            print(output[:3000])

        processed = output.count("[Cloud] Done:")
        log(f"Cloud agent: {processed} task(s) drafted for approval")
        return processed
    except subprocess.TimeoutExpired:
        log("Cloud agent timed out (300s)")
        write_signal("AGENT_TIMEOUT", "cloud_agent exceeded 300s")
        return 0
    except Exception as e:
        log(f"Cloud agent error: {e}")
        write_signal("AGENT_ERROR", str(e))
        return 0


# ══════════════════════════════════════════════════════════════
# HEALTH STATUS
# ══════════════════════════════════════════════════════════════

def write_health(gmail_tasks: int, processed: int, push_ok: bool):
    try:
        updates_dir = VAULT / "Updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        data = {
            "type": "CLOUD_RUN_HEALTH",
            "timestamp": datetime.now().isoformat(),
            "agent": "cloud_run",
            "gmail_tasks": gmail_tasks,
            "processed": processed,
            "pushed": push_ok,
            "status": "OK" if push_ok else "DEGRADED",
        }
        (updates_dir / f"UPDATE_{ts}_CLOUD_RUN_HEALTH.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  AI EMPLOYEE - Cloud Run Job (Platinum Tier)")
    print(f"  Time:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  Zone:  Cloud (draft-only, never sends directly)")
    print(f"  Vault: {VAULT}")
    print("=" * 60)

    log("Step 1/5 - Setting up Gmail credentials...")
    has_gmail = setup_gmail_credentials()

    log("Step 2/5 - Syncing vault from GitHub...")
    git_pull()

    gmail_tasks = 0
    if has_gmail:
        log("Step 3/5 - Checking Gmail for new emails...")
        gmail_tasks = run_gmail_watcher()
    else:
        log("Step 3/5 - No Gmail credentials, skipping")

    log("Step 4/5 - Routing tasks to cloud queue...")
    route_tasks_to_cloud()

    log("Step 5/5 - Processing tasks with AI pipeline...")
    processed = run_cloud_agent()

    log("Step 6/6 - Pushing drafts to GitHub...")
    push_ok = git_push()

    write_health(gmail_tasks, processed, push_ok)

    print("\n" + "=" * 60)
    print("  CLOUD RUN COMPLETE")
    print(f"  Gmail tasks   : {gmail_tasks}")
    print(f"  Tasks drafted : {processed}")
    print(f"  Approval dir  : Pending_Approval/cloud/")
    print(f"  Git push      : {'OK' if push_ok else 'FAILED'}")
    print("=" * 60)

    sys.exit(0)


if __name__ == "__main__":
    main()
