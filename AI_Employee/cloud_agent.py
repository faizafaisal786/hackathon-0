"""
Cloud Agent — Platinum Tier
==============================
Work-zone agent running on Oracle Cloud Free Tier VM (24/7).

Responsibilities:
  - Monitors Needs_Action/cloud/ for new tasks
  - Claims tasks via claim_manager.py (atomic file move)
  - Runs THINKER -> PLANNER -> EXECUTOR -> REVIEWER pipeline (agents.py)
  - Writes plan files to Plans/cloud/
  - Writes approved drafts to Pending_Approval/cloud/
  - Posts status updates to Updates/ folder (read by local agent)
  - NEVER sends emails/WhatsApp directly — only drafts for local to send
  - Syncs vault via cloud_sync.sh (Git pull/push)

Separation of duties:
  Cloud does  : triage, planning, drafting content, scoring quality
  Cloud never : send email, send WhatsApp, touch payments, update Dashboard.md

Usage:
  python cloud_agent.py              # Single pass
  python cloud_agent.py --loop       # Continuous (60s interval)
  python cloud_agent.py --loop 30    # Custom interval
  python cloud_agent.py --test       # Self-test
"""

import sys
import os
import json
import time
import shutil
from datetime import datetime
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

AGENT_NAME    = "cloud"
LOOP_INTERVAL = 60  # seconds between passes


# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS WITH GRACEFUL DEGRADATION
# ══════════════════════════════════════════════════════════════════════════════

def _import_agents():
    try:
        from agents import ThinkerAgent, PlannerAgent, ExecutorAgent, ReviewerAgent
        return ThinkerAgent, PlannerAgent, ExecutorAgent, ReviewerAgent
    except ImportError:
        return None, None, None, None


def _import_claim_manager():
    try:
        from claim_manager import ClaimManager
        return ClaimManager
    except ImportError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE WRITER (Cloud -> Local communication)
# ══════════════════════════════════════════════════════════════════════════════

def _write_update(event: str, task_name: str, details: dict):
    """
    Write an update file to Updates/ so the local agent can read it.
    Local agent is the single writer for Dashboard.md — cloud uses Updates/.
    """
    updates_dir = VAULT / "Updates"
    updates_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"UPDATE_{timestamp}_{event}.json"

    update = {
        "event":     event,
        "task":      task_name,
        "agent":     AGENT_NAME,
        "timestamp": datetime.now().isoformat(),
        **details,
    }

    (updates_dir / filename).write_text(
        json.dumps(update, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_signal(signal_type: str, message: str, data: dict = None):
    """
    Write a signal file to Signals/ for urgent cloud -> local communication.
    Signals are like alerts: health issues, quota exceeded, critical errors.
    """
    signals_dir = VAULT / "Signals"
    signals_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"SIGNAL_{timestamp}_{signal_type}.json"

    signal = {
        "type":      signal_type,
        "message":   message,
        "agent":     AGENT_NAME,
        "timestamp": datetime.now().isoformat(),
        "data":      data or {},
    }

    (signals_dir / filename).write_text(
        json.dumps(signal, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def _run_ai_pipeline(task_content: str, task_name: str) -> dict:
    """
    Run THINKER -> PLANNER -> EXECUTOR -> REVIEWER on a task.
    Returns a dict with plan, draft, quality_score.
    Falls back to template output if agents unavailable.
    """
    ThinkerAgent, PlannerAgent, ExecutorAgent, ReviewerAgent = _import_agents()

    if ThinkerAgent is None:
        # Graceful fallback — no agents module
        return {
            "plan": f"# Plan for {task_name}\n\nTask: Review and respond.\nChannel: Email\nPriority: Normal",
            "draft": f"Draft response for: {task_name}\n\n[Cloud agent generated draft]",
            "quality_score": 7.0,
            "revision_rounds": 0,
            "fallback": True,
        }

    try:
        # Stage 1: THINKER — understand intent
        thinker = ThinkerAgent()
        context = thinker.analyze(task_content)

        # Stage 2: PLANNER — create execution steps
        planner    = PlannerAgent()
        plan_text  = planner.plan(task_content, context)

        # Stage 3: EXECUTOR — draft the content
        executor   = ExecutorAgent()
        draft      = executor.execute(task_content, plan_text, context)

        # Stage 4: REVIEWER — score and maybe revise
        reviewer       = ReviewerAgent()
        review_result  = reviewer.review(draft, task_content, context)
        quality_score  = review_result.get("score", 7.0)
        revision_count = 0

        # Revision loop (max 2 rounds)
        while quality_score < 7.0 and revision_count < 2:
            feedback = review_result.get("feedback", "Improve quality and clarity.")
            draft    = executor.revise(draft, feedback, task_content, context)
            review_result = reviewer.review(draft, task_content, context)
            quality_score = review_result.get("score", 7.0)
            revision_count += 1

        return {
            "plan":            plan_text,
            "draft":           draft,
            "quality_score":   quality_score,
            "revision_rounds": revision_count,
            "context":         context,
            "fallback":        False,
        }

    except Exception as e:
        _write_signal("PIPELINE_ERROR", f"Pipeline failed for {task_name}: {e}")
        return {
            "plan":  f"# Auto-Plan for {task_name}\n\nError during pipeline: {e}",
            "draft": f"[Pipeline error — manual review required]\n\nTask: {task_name}",
            "quality_score": 0,
            "revision_rounds": 0,
            "error": str(e),
            "fallback": True,
        }


# ══════════════════════════════════════════════════════════════════════════════
# TASK PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def _process_task(claim_record, task_content: str, cm) -> str:
    """
    Process a claimed task through the full cloud pipeline.
    Returns final destination folder name.
    """
    task_name = claim_record.filename
    print(f"  [Cloud] Processing: {task_name}")

    # Run AI pipeline
    result = _run_ai_pipeline(task_content, task_name)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Write PLAN file to Plans/cloud/
    plan_name = f"PLAN_{timestamp}_{task_name}"
    plan_dir  = VAULT / "Plans" / "cloud"
    plan_dir.mkdir(parents=True, exist_ok=True)

    plan_content = f"""# Plan — {task_name}

**Generated by**: Cloud Agent (PLATINUM)
**Timestamp**: {datetime.now().isoformat()}
**Quality Score**: {result['quality_score']:.1f}/10
**Revision Rounds**: {result['revision_rounds']}

---

## Original Task

{task_content}

---

## Execution Plan

{result['plan']}

---

## Drafted Content

{result['draft']}

---

## Routing Decision

{'Sending to Pending_Approval/cloud/ for human review.' if result['quality_score'] >= 7.0 else 'Quality below threshold — flagged for revision.'}
"""

    (plan_dir / plan_name).write_text(plan_content, encoding="utf-8")

    # Write ACTION file to Pending_Approval/cloud/ (ready for local to send)
    action_name = f"ACTION_{timestamp}_{task_name}"
    approval_dir = VAULT / "Pending_Approval" / "cloud"
    approval_dir.mkdir(parents=True, exist_ok=True)

    action_content = f"""# Action — {task_name}

**Zone**: Cloud Draft (requires Local execution)
**Quality Score**: {result['quality_score']:.1f}/10
**Timestamp**: {datetime.now().isoformat()}

---

## Ready-to-Send Content

{result['draft']}

---

## Instructions for Local Agent

1. Review the content above
2. If approved: move this file to Approved/ and execute send
3. If rejected: move this file to Rejected/
4. Original task: {task_name}

---

## Status

[ ] Pending Review
[ ] Approved
[ ] Sent
"""

    (approval_dir / action_name).write_text(action_content, encoding="utf-8")

    # Release original task to Done
    cm.release(claim_record, "Done")

    # Write update for local agent
    _write_update("TASK_DRAFTED", task_name, {
        "plan_file":   plan_name,
        "action_file": action_name,
        "quality":     result['quality_score'],
        "revisions":   result['revision_rounds'],
    })

    quality_str = f"{result['quality_score']:.1f}"
    print(f"  [Cloud] Done: {task_name} (quality={quality_str}/10)")
    print(f"    Plan   -> Plans/cloud/{plan_name}")
    print(f"    Action -> Pending_Approval/cloud/{action_name}")

    return "Pending_Approval/cloud"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PASS
# ══════════════════════════════════════════════════════════════════════════════

def run_pass() -> int:
    """
    Single pass: claim and process tasks from Needs_Action/cloud/.
    Returns number of tasks processed.
    """
    ClaimManagerClass = _import_claim_manager()
    if ClaimManagerClass is None:
        print("  [Cloud] ERROR: claim_manager.py not found")
        return 0

    cm      = ClaimManagerClass(VAULT)
    processed = 0

    while True:
        record = cm.claim_next(AGENT_NAME)
        if record is None:
            break

        try:
            task_content = record.path.read_text(encoding="utf-8", errors="replace")
            _process_task(record, task_content, cm)
            processed += 1
        except Exception as e:
            print(f"  [Cloud] ERROR processing {record.filename}: {e}")
            _write_signal("TASK_ERROR", f"Failed to process {record.filename}: {e}")
            # Release back to needs_action
            try:
                cm.release(record, f"Needs_Action/{AGENT_NAME}")
            except Exception:
                pass

    return processed


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST
# ══════════════════════════════════════════════════════════════════════════════

def run_test():
    print("=" * 55)
    print("  CLOUD AGENT — Self Test")
    print("=" * 55)

    # Create a test task
    test_dir  = VAULT / "Needs_Action" / "cloud"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "TEST_CLOUD_EMAIL_task.md"
    test_file.write_text(
        "# Test Email Task\n\nChannel: Email\nPriority: Normal\n"
        "Message: Write a professional reply to a client asking about our services.\n"
        "To: client@example.com",
        encoding="utf-8",
    )
    print(f"\n  [1] Created test task: {test_file.name}")

    # Run a single pass
    count = run_pass()
    print(f"\n  [2] Tasks processed: {count}")

    # Check outputs
    plans   = list((VAULT / "Plans" / "cloud").glob("PLAN_*TEST*"))
    actions = list((VAULT / "Pending_Approval" / "cloud").glob("ACTION_*TEST*"))
    updates = list((VAULT / "Updates").glob("UPDATE_*TASK_DRAFTED*"))

    print(f"  [3] Plan files created: {len(plans)}")
    print(f"  [4] Action files created: {len(actions)}")
    print(f"  [5] Update files written: {len(updates)}")

    all_pass = count >= 1 and len(plans) >= 1 and len(actions) >= 1
    print(f"\n  Result: {'PASS' if all_pass else 'FAIL'}")
    print("=" * 55)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if "--test" in args:
        run_test()
        return

    interval = LOOP_INTERVAL
    if "--loop" in args:
        idx = args.index("--loop")
        if idx + 1 < len(args):
            try:
                interval = int(args[idx + 1])
            except ValueError:
                pass

        print("=" * 55)
        print("  CLOUD AGENT — Continuous Mode")
        print(f"  Zone:     {AGENT_NAME}")
        print(f"  Interval: {interval}s")
        print(f"  Vault:    {VAULT}")
        print("  Press Ctrl+C to stop")
        print("=" * 55)

        _write_update("AGENT_START", "cloud_agent", {"interval": interval})

        try:
            pass_count = 0
            while True:
                print(f"\n  [{time.strftime('%H:%M:%S')}] Cloud pass #{pass_count + 1}...")
                processed = run_pass()

                if processed > 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] Processed {processed} task(s)")
                else:
                    print(f"  [{time.strftime('%H:%M:%S')}] No tasks in cloud queue.")

                pass_count += 1
                print(f"  Next pass in {interval}s...")
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n  Cloud Agent stopped.")
            _write_update("AGENT_STOP", "cloud_agent", {"reason": "KeyboardInterrupt"})

    else:
        # Single pass
        print(f"  [Cloud Agent] Single pass — Zone: {AGENT_NAME}")
        count = run_pass()
        print(f"  [Cloud Agent] Pass complete. Processed: {count} task(s)")


if __name__ == "__main__":
    main()
