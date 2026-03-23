"""
AI Employee — Platinum Tier Configuration
==========================================
Edit this file to control system behavior.
All settings can also be set in .env file.
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass


# ── Approval Mode ─────────────────────────────────────────
# True  = system auto-approves all tasks (fully autonomous)
# False = human must drag file to Approved/ folder
AUTO_APPROVE = os.getenv("AUTO_APPROVE", "false").lower() == "true"

# ── Loop Timing ───────────────────────────────────────────
# How often (in seconds) ralph_loop checks for new tasks
LOOP_INTERVAL = int(os.getenv("LOOP_INTERVAL", "60"))

# ── AI Model ──────────────────────────────────────────────
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-5-20250929")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1024"))

# ── Multi-step Reasoning ──────────────────────────────────
# True  = 3 separate AI calls (THINK → PLAN → EXECUTE)  [Gold Tier]
# False = single AI call (faster, less thorough)
MULTISTEP_AI = os.getenv("MULTISTEP_AI", "true").lower() == "true"

# ── Vault Path ────────────────────────────────────────────
VAULT_PATH = Path(__file__).parent / "AI_Employee_Vault"


# ═══════════════════════════════════════════════════════════
# PLATINUM SETTINGS
# ═══════════════════════════════════════════════════════════

# ── Platinum Mode ─────────────────────────────────────────
# True  = Full 4-agent pipeline (THINKER→PLANNER→EXECUTOR→REVIEWER)
# False = Gold 3-step mode (THINK→PLAN→EXECUTE)
ENABLE_PLATINUM = os.getenv("ENABLE_PLATINUM", "true").lower() == "true"

# ── Memory System ─────────────────────────────────────────
# True  = Store and retrieve past task memories for context
ENABLE_MEMORY = os.getenv("ENABLE_MEMORY", "true").lower() == "true"

# ── Self-Improvement ──────────────────────────────────────
# True  = Automatically improve prompts based on outcomes
ENABLE_SELF_IMPROVEMENT = os.getenv("ENABLE_SELF_IMPROVEMENT", "true").lower() == "true"

# How many loop passes between self-improvement runs
IMPROVEMENT_INTERVAL = int(os.getenv("IMPROVEMENT_INTERVAL", "10"))

# ── Reviewer Threshold ────────────────────────────────────
# Minimum quality score (1-10) for Reviewer to approve without revision
REVIEWER_THRESHOLD = int(os.getenv("REVIEWER_THRESHOLD", "7"))

# ── Self-Healing ──────────────────────────────────────────
# Max consecutive failures before task is quarantined
MAX_TASK_FAILURES = int(os.getenv("MAX_TASK_FAILURES", "3"))
