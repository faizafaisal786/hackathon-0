"""
ralph_loop.py — Ralph Wiggum Autonomous Loop
=============================================
Keeps Claude Code working autonomously until a task is complete.
Named after Ralph Wiggum: "I'm helping!" — it re-injects the prompt
every time Claude tries to exit before finishing.

Completion Strategies:
  1. Promise-based: Claude outputs <promise>TASK_COMPLETE</promise>
  2. File-based: Task file moves from /Needs_Action to /Done

Usage:
    python ralph_loop.py "Process all files in /Needs_Action" --completion-promise "TASK_COMPLETE"
    python ralph_loop.py "Weekly audit" --completion-file "weekly_audit_done.md" --max-iterations 10
"""

import os
import re
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH") or Path(__file__).parent)
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("RalphLoop")

DEFAULT_MAX_ITERATIONS = 10
PROMISE_PATTERN = re.compile(r"<promise>(.*?)</promise>", re.IGNORECASE)


class RalphLoop:
    """
    Autonomous loop that re-runs Claude until the task is complete.
    Uses the 'Stop Hook' pattern — intercepts Claude exit and re-injects.
    """

    def __init__(
        self,
        vault_path: Path,
        prompt: str,
        completion_promise: str = "TASK_COMPLETE",
        completion_file: str | None = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        dry_run: bool = False,
    ):
        self.vault_path = vault_path
        self.prompt = prompt
        self.completion_promise = completion_promise
        self.completion_file = Path(completion_file) if completion_file else None
        self.max_iterations = max_iterations
        self.dry_run = dry_run
        self.iteration = 0
        self.state_file = vault_path / "Logs" / f"ralph_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    def is_complete(self, output: str) -> bool:
        """Check if the task is done via promise or file movement."""
        # Strategy 1: Promise in output
        matches = PROMISE_PATTERN.findall(output)
        if any(self.completion_promise.upper() in m.upper() for m in matches):
            logger.info(f"Completion promise found: {matches}")
            return True

        # Strategy 2: Completion file in /Done
        if self.completion_file:
            done_file = self.vault_path / "Done" / self.completion_file.name
            if done_file.exists():
                logger.info(f"Completion file found in /Done: {done_file.name}")
                return True

        return False

    def save_state(self, status: str, last_output: str = ""):
        """Persist loop state for debugging."""
        state = {
            "timestamp": datetime.now().isoformat(),
            "prompt": self.prompt,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "status": status,
            "last_output_preview": last_output[:500],
        }
        self.state_file.parent.mkdir(exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2))

    def run(self) -> bool:
        """
        Run the loop. Returns True if task completed, False if max iterations hit.
        """
        logger.info("=" * 60)
        logger.info("Ralph Wiggum Loop Starting")
        logger.info(f"Task   : {self.prompt[:80]}...")
        logger.info(f"Promise: {self.completion_promise}")
        logger.info(f"Max    : {self.max_iterations} iterations")
        logger.info("=" * 60)

        self.save_state("started")

        while self.iteration < self.max_iterations:
            self.iteration += 1
            logger.info(f"── Iteration {self.iteration}/{self.max_iterations} ──")

            if self.dry_run:
                logger.info(f"[DRY RUN] Would run Claude with prompt: {self.prompt[:60]}...")
                output = f"<promise>{self.completion_promise}</promise>"  # Simulate completion
            else:
                output = self._run_claude()

            if output is None:
                logger.error("Claude returned no output. Stopping loop.")
                self.save_state("error_no_output")
                return False

            if self.is_complete(output):
                logger.info(f"Task completed after {self.iteration} iteration(s)!")
                self.save_state("completed", output)
                return True

            logger.info("Task not yet complete. Re-injecting prompt...")
            self.save_state("in_progress", output)
            time.sleep(2)  # Brief pause before next iteration

        logger.warning(f"Max iterations ({self.max_iterations}) reached. Task may be incomplete.")
        self.save_state("max_iterations_reached")
        return False

    def _run_claude(self) -> str | None:
        """Execute Claude Code with the given prompt."""
        try:
            result = subprocess.run(
                ["claude", "--cwd", str(self.vault_path), "--print", self.prompt],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout per iteration
            )
            if result.returncode != 0:
                logger.error(f"Claude error (exit {result.returncode}): {result.stderr[:300]}")
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error("Claude timed out after 10 minutes.")
            return None
        except FileNotFoundError:
            logger.error("Claude Code not found. Install with: npm install -g @anthropic/claude-code")
            return None


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ralph Wiggum Autonomous Loop — Gold Tier")
    parser.add_argument("prompt", help="The task prompt to run autonomously")
    parser.add_argument(
        "--completion-promise",
        default="TASK_COMPLETE",
        help="Token Claude must output to signal completion (default: TASK_COMPLETE)",
    )
    parser.add_argument(
        "--completion-file",
        default=None,
        help="Filename that must appear in /Done to signal completion",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Max re-runs before giving up (default: {DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument("--vault-path", type=Path, default=VAULT_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    loop = RalphLoop(
        vault_path=args.vault_path.resolve(),
        prompt=args.prompt,
        completion_promise=args.completion_promise,
        completion_file=args.completion_file,
        max_iterations=args.max_iterations,
        dry_run=args.dry_run,
    )

    success = loop.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
