"""
local_agent.py — Local AI Employee Agent (Platinum Tier)
=========================================================
Runs on your local machine.
Handles: human approvals, WhatsApp, payments, final send/post execution.
Merges cloud updates into Dashboard.md (single-writer rule).

Usage:
    python local/local_agent.py
    python local/local_agent.py --dry-run
"""

import os
import re
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
AGENT_ID = "local"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
APPROVAL_CHECK_INTERVAL = int(os.getenv("APPROVAL_CHECK_INTERVAL", "10"))
UPDATE_CHECK_INTERVAL = int(os.getenv("UPDATE_CHECK_INTERVAL", "30"))

LOG_FORMAT = "%(asctime)s [LOCAL] %(levelname)s %(name)s: %(message)s"
(VAULT_PATH / "Logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            VAULT_PATH / "Logs" / f"local_agent_{datetime.now().strftime('%Y%m%d')}.log"
        ),
    ],
)
logger = logging.getLogger("LocalAgent")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def log_action(action_type: str, details: dict):
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = VAULT_PATH / "Logs" / f"{today}.json"
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "actor": "local",
        **details,
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def extract_frontmatter_value(content: str, key: str) -> str:
    for line in content.split("\n"):
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


# ─── Cloud Update Merger ──────────────────────────────────────────────────────

class CloudUpdateMerger:
    """
    Reads update files from /Updates/ written by Cloud agent,
    and merges them into Dashboard.md (local is single writer).
    """

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.updates_dir = vault_path / "Updates"
        self.dashboard = vault_path / "Dashboard.md"

    def process_updates(self):
        if not self.updates_dir.exists():
            return

        update_files = list(self.updates_dir.glob("*.md"))
        if not update_files:
            return

        for update_file in update_files:
            self._merge_update(update_file)

    def _merge_update(self, update_file: Path):
        """Merge a cloud update into Dashboard.md."""
        try:
            content = update_file.read_text(encoding="utf-8")
            update_type = extract_frontmatter_value(content, "update_type")

            logger.info(f"Merging cloud update: {update_file.name} (type: {update_type})")

            # Append the update to Dashboard's Recent Actions section
            dashboard_content = self.dashboard.read_text(encoding="utf-8")
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            update_line = f"| {now} | Cloud | {update_type} | See {update_file.name} |"

            # Insert into Recent Actions table
            if "| _(none)_ |" in dashboard_content:
                dashboard_content = dashboard_content.replace(
                    "| _(none)_ | — | — | — |", update_line
                )
            else:
                # Append after the last table row
                dashboard_content = re.sub(
                    r"(\| \*\(none\)\* \|.*\n)",
                    update_line + "\n",
                    dashboard_content,
                )

            # Update last_updated
            dashboard_content = re.sub(
                r"last_updated:.*",
                f"last_updated: {datetime.now().strftime('%Y-%m-%d')}",
                dashboard_content,
            )

            self.dashboard.write_text(dashboard_content, encoding="utf-8")

            # Archive the update
            done_dir = self.vault_path / "Done"
            shutil.move(str(update_file), str(done_dir / f"UPDATE_{update_file.name}"))
            log_action("cloud_update_merged", {"file": update_file.name, "type": update_type})

        except Exception as e:
            logger.error(f"Failed to merge update {update_file.name}: {e}")


# ─── Approval Executor ────────────────────────────────────────────────────────

class ApprovalExecutor:
    """
    Watches /Approved/ and executes approved actions via MCP.
    Local agent is the only one with authority to execute sends/posts/payments.
    """

    def __init__(self, vault_path: Path, dry_run: bool = False):
        self.vault_path = vault_path
        self.approved = vault_path / "Approved"
        self.done = vault_path / "Done"
        self.dry_run = dry_run

    def check_and_execute(self):
        if not self.approved.exists():
            return

        for file in self.approved.glob("*.md"):
            if file.stat().st_size == 0:
                continue
            self._execute(file)

    def _execute(self, file: Path):
        content = file.read_text(encoding="utf-8")
        action = extract_frontmatter_value(content, "action")

        logger.info(f"Executing approved action: {action} ({file.name})")

        if self.dry_run:
            logger.info(f"[DRY RUN] Would execute: {action}")
        else:
            self._trigger_claude_execution(file, action)

        # Move to Done
        dest = self.done / f"EXECUTED_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
        shutil.move(str(file), str(dest))
        log_action("approved_action_executed", {"file": file.name, "action": action})

    def _trigger_claude_execution(self, file: Path, action: str):
        """Ask Claude to execute the approved action using the appropriate MCP."""
        try:
            subprocess.run(
                ["claude", "--cwd", str(self.vault_path), "--print",
                 f"Execute the approved action in file: {file.name}. "
                 f"Action type: {action}. Use the appropriate MCP server tool. "
                 f"Log the result. Output <promise>EXECUTED</promise> when done."],
                capture_output=True, text=True, timeout=120,
            )
        except Exception as e:
            logger.error(f"Failed to trigger Claude for execution: {e}")


# ─── Git Pull (Local Side) ────────────────────────────────────────────────────

def pull_latest_vault():
    """Pull latest cloud changes into local vault."""
    try:
        result = subprocess.run(
            ["git", "-C", str(VAULT_PATH), "pull", "--rebase"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.debug("Vault pulled successfully.")
        else:
            logger.warning(f"Git pull warning: {result.stderr[:100]}")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # Not fatal — vault sync is best-effort


# ─── Main Loop ───────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("Local AI Employee Agent — Platinum Tier")
    logger.info(f"Vault : {VAULT_PATH}")
    logger.info(f"Dry   : {DRY_RUN}")
    logger.info("=" * 60)

    merger = CloudUpdateMerger(VAULT_PATH)
    executor = ApprovalExecutor(VAULT_PATH, dry_run=DRY_RUN)

    tick = 0
    pull_ticks = UPDATE_CHECK_INTERVAL // APPROVAL_CHECK_INTERVAL

    try:
        while True:
            tick += 1

            # Always check for approved actions
            executor.check_and_execute()

            # Periodically pull vault + merge cloud updates
            if tick % pull_ticks == 0:
                pull_latest_vault()
                merger.process_updates()

            time.sleep(APPROVAL_CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Local agent shutting down...")


if __name__ == "__main__":
    main()
