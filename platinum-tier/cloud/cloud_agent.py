"""
cloud_agent.py — Cloud AI Employee Agent (Platinum Tier)
=========================================================
Runs 24/7 on a cloud VM (Oracle Cloud Free Tier / AWS / etc.)
Handles: email triage, draft replies, social scheduling.
NEVER sends or posts directly — always creates approval files.

Deployment:
    # On cloud VM:
    pip install -r requirements.txt
    cp .env.example .env && nano .env
    python cloud/cloud_agent.py

    # Or with Docker:
    docker-compose up -d cloud_agent
"""

import os
import sys
import time
import json
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ─── Config ──────────────────────────────────────────────────────────────────

VAULT_PATH = Path(os.getenv("VAULT_PATH") or Path(__file__).parent.parent)
AGENT_ID = "cloud"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "300"))     # 5 min vault sync
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "120"))    # 2 min inbox check

LOG_FORMAT = "%(asctime)s [CLOUD] %(levelname)s %(name)s: %(message)s"
(VAULT_PATH / "Logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            VAULT_PATH / "Logs" / f"cloud_agent_{datetime.now().strftime('%Y%m%d')}.log"
        ),
    ],
)
logger = logging.getLogger("CloudAgent")


# ─── Claim-by-Move ────────────────────────────────────────────────────────────

def claim_item(item_path: Path) -> Path | None:
    """
    Atomically claim an item from /Needs_Action/<domain>/ by moving it
    to /In_Progress/cloud/. Returns new path or None if claim failed.
    """
    in_progress_dir = VAULT_PATH / "In_Progress" / AGENT_ID
    in_progress_dir.mkdir(parents=True, exist_ok=True)
    dest = in_progress_dir / item_path.name

    try:
        item_path.rename(dest)  # Atomic on POSIX; best-effort on Windows
        logger.info(f"Claimed: {item_path.name}")
        return dest
    except (FileNotFoundError, OSError):
        # Another agent already claimed it
        return None


def release_to_done(item_path: Path):
    """Move a completed item to /Done/."""
    done_dir = VAULT_PATH / "Done"
    done_dir.mkdir(exist_ok=True)
    dest = done_dir / item_path.name
    shutil.move(str(item_path), str(dest))
    logger.info(f"Moved to Done: {item_path.name}")


# ─── Vault Sync ───────────────────────────────────────────────────────────────

def sync_vault():
    """Sync vault with Git. Cloud pulls latest, then pushes its changes."""
    vault_git = VAULT_PATH
    try:
        # Pull first to get latest local changes
        subprocess.run(["git", "-C", str(vault_git), "pull", "--rebase"], check=True, capture_output=True)
        # Stage only safe files (no .env, no secrets)
        subprocess.run(["git", "-C", str(vault_git), "add", "*.md", "Logs/*.json", "Updates/"], capture_output=True)
        # Commit if there are changes
        result = subprocess.run(["git", "-C", str(vault_git), "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run([
                "git", "-C", str(vault_git), "commit", "-m",
                f"chore: cloud agent sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(vault_git), "push"], check=True, capture_output=True)
            logger.info("Vault synced and pushed.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Vault sync failed: {e}")


# ─── Claude Trigger ───────────────────────────────────────────────────────────

def trigger_claude_for_domain(domain: str) -> bool:
    """Trigger Claude to process a domain's Needs_Action queue."""
    domain_dir = VAULT_PATH / "Needs_Action" / domain
    if not domain_dir.exists():
        return False

    items = list(domain_dir.glob("*.md"))
    if not items:
        return False

    logger.info(f"Triggering Claude for domain '{domain}' ({len(items)} items)")

    if DRY_RUN:
        logger.info(f"[DRY RUN] Would run claude /process-inbox for {domain}")
        return True

    try:
        result = subprocess.run(
            ["claude", "--cwd", str(VAULT_PATH), "--print",
             f"Process all pending items in /Needs_Action/{domain}/. "
             f"Draft replies and create approval files. Follow Company_Handbook.md rules. "
             f"You are the CLOUD agent — never send or post directly. "
             f"Output <promise>DONE</promise> when complete."],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            log_action("claude_triggered", {"domain": domain, "items": len(items), "result": "success"})
            return True
        else:
            logger.error(f"Claude error: {result.stderr[:200]}")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error(f"Claude invoke failed: {e}")
        return False


def write_update(content: str, filename: str):
    """Write a status update to /Updates/ for the Local agent to merge."""
    updates_dir = VAULT_PATH / "Updates"
    updates_dir.mkdir(exist_ok=True)
    update_file = updates_dir / filename
    update_file.write_text(content, encoding="utf-8")
    logger.info(f"Update written: {filename}")


def log_action(action_type: str, details: dict):
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    entry = {"timestamp": datetime.now().isoformat(), "action_type": action_type, "actor": "cloud", **details}
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ─── Main Loop ───────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("Cloud AI Employee Agent — Platinum Tier")
    logger.info(f"Vault : {VAULT_PATH}")
    logger.info(f"Agent : {AGENT_ID}")
    logger.info(f"Dry   : {DRY_RUN}")
    logger.info("=" * 60)

    tick = 0
    sync_ticks = SYNC_INTERVAL // CHECK_INTERVAL

    try:
        while True:
            tick += 1

            # Process each domain
            for domain in ["email", "social"]:
                trigger_claude_for_domain(domain)

            # Periodic vault sync
            if tick % sync_ticks == 0:
                sync_vault()

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Cloud agent shutting down...")


if __name__ == "__main__":
    main()
