"""
scheduler.py — Cron-style scheduler for Silver Tier periodic jobs.

Runs scheduled jobs that trigger Claude Code skills and orchestrator actions.
Uses the `schedule` library for simplicity — no system cron required.

Jobs defined here:
    - 07:00 daily    → /daily-briefing
    - 09:00 Monday   → /post-linkedin
    - 19:00 daily    → /process-inbox
    - 17:00 Friday   → weekly-review

Environment variables (via .env):
    VAULT_PATH       — Absolute path to vault root
    DRY_RUN          — If "true", log but don't run Claude (default: false)
    CLAUDE_BIN       — Path to claude binary (default: "claude")
"""

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import schedule
import time
from dotenv import load_dotenv

load_dotenv()

VAULT_PATH = os.getenv("VAULT_PATH") or str(Path(__file__).parent)
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "claude")

# Setup logging
log_dir = Path(VAULT_PATH) / "Logs"
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | Scheduler | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.FileHandler(log_dir / "scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Scheduler")


def run_claude_skill(skill: str, description: str) -> None:
    """
    Run a Claude Code slash command inside the vault directory.

    Args:
        skill: The slash command to run, e.g. "/daily-briefing"
        description: Human-readable description for logging
    """
    logger.info(f"Running scheduled job: {description} ({skill})")

    if DRY_RUN:
        logger.info(f"[DRY RUN] Would run: {CLAUDE_BIN} --print '{skill}'")
        return

    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--print", skill],
            cwd=VAULT_PATH,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if result.returncode == 0:
            logger.info(f"Completed: {description}")
            if result.stdout.strip():
                logger.info(f"Output: {result.stdout[:500]}")  # Log first 500 chars
        else:
            logger.error(
                f"Failed: {description} | exit={result.returncode} | "
                f"stderr={result.stderr[:200]}"
            )
    except FileNotFoundError:
        logger.error(
            f"Claude binary not found: '{CLAUDE_BIN}'. "
            "Install with: npm i -g @anthropic-ai/claude-code"
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout (5 min) running: {description}")
    except Exception as e:
        logger.error(f"Unexpected error running {skill}: {e}", exc_info=True)


def write_vault_note(filename: str, content: str) -> None:
    """Write a note directly to the vault (for scheduler events that don't need Claude)."""
    target = Path(VAULT_PATH) / filename
    if not DRY_RUN:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info(f"Vault note written: {filename}")
    else:
        logger.info(f"[DRY RUN] Would write: {filename}")


# ── Job definitions ───────────────────────────────────────────────────────────

def job_daily_briefing():
    run_claude_skill("/daily-briefing", "Daily morning briefing")


def job_inbox_sweep():
    run_claude_skill("/process-inbox", "Evening inbox sweep")


def job_linkedin_draft():
    run_claude_skill("/post-linkedin", "Weekly LinkedIn post draft")


def job_weekly_review():
    """Friday end-of-week review — extended briefing + next week prep."""
    logger.info("Running weekly review job...")
    run_claude_skill("/daily-briefing", "Friday weekly review briefing")


def job_check_pending_approvals():
    """Check Pending_Approval/ for items older than 48 hours and flag them."""
    pending_dir = Path(VAULT_PATH) / "Pending_Approval"
    if not pending_dir.exists():
        return

    now = datetime.now().timestamp()
    stale = []
    for f in pending_dir.glob("*.md"):
        age_hours = (now - f.stat().st_mtime) / 3600
        if age_hours > 48:
            stale.append((f.name, round(age_hours)))

    if stale:
        logger.warning(f"Stale approvals ({len(stale)} items over 48h):")
        for name, hours in stale:
            logger.warning(f"  - {name} ({hours}h old)")

        # Write a reminder note to Needs_Action
        reminder = f"""---
type: system_reminder
created: {datetime.now().isoformat()}
priority: P1
tags: [needs_action, approvals]
---

# Reminder: {len(stale)} Pending Approval(s) Awaiting Review

The following items in `Pending_Approval/` have been waiting over 48 hours:

"""
        for name, hours in stale:
            reminder += f"- `{name}` ({hours} hours old)\n"

        reminder += "\n\nPlease review and move to `Approved/` or `Rejected/`.\n"
        write_vault_note(
            f"Needs_Action/APPROVAL_REMINDER_{datetime.now().strftime('%Y-%m-%d')}.md",
            reminder,
        )


def job_health_check():
    """Hourly health check — log system status."""
    vault = Path(VAULT_PATH)
    inbox_count = len(list((vault / "Inbox").glob("*.md"))) if (vault / "Inbox").exists() else 0
    needs_action_count = len(list((vault / "Needs_Action").glob("*.md"))) if (vault / "Needs_Action").exists() else 0
    pending_count = len(list((vault / "Pending_Approval").glob("*.md"))) if (vault / "Pending_Approval").exists() else 0

    logger.info(
        f"Health: inbox={inbox_count} | needs_action={needs_action_count} | "
        f"pending_approval={pending_count}"
    )


# ── Schedule configuration ────────────────────────────────────────────────────

def setup_schedule():
    # Daily jobs
    schedule.every().day.at("07:00").do(job_daily_briefing)
    schedule.every().day.at("19:00").do(job_inbox_sweep)
    schedule.every().hour.do(job_health_check)
    schedule.every().day.at("09:00").do(job_check_pending_approvals)

    # Weekly jobs
    schedule.every().monday.at("08:00").do(job_linkedin_draft)
    schedule.every().friday.at("17:00").do(job_weekly_review)

    logger.info("Schedule configured:")
    for job in schedule.get_jobs():
        logger.info(f"  {job}")


def main():
    logger.info("=" * 60)
    logger.info("Personal AI Employee — Silver Tier Scheduler starting")
    logger.info(f"Vault: {VAULT_PATH}")
    logger.info(f"DRY_RUN={DRY_RUN}")

    setup_schedule()

    logger.info("Scheduler running. Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
