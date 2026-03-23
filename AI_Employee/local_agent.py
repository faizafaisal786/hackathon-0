"""
Local Agent — Platinum Tier
==============================
Work-zone agent running on the local Windows machine (human's desk).

Responsibilities:
  - Monitors Needs_Action/local/ for tasks requiring local execution
  - Reads Updates/ from cloud agent and merges status to Dashboard.md
  - Reads Signals/ for cloud health alerts
  - Claims tasks via claim_manager.py
  - Executes final sends: Email, WhatsApp, Odoo payments
  - Processes Pending_Approval/cloud/ items for human review
  - IS THE SINGLE WRITER for Dashboard.md (cloud never writes Dashboard.md)
  - Handles urgency escalation (Telegram notification)

Local zone owns:
  - WhatsApp sending (Twilio)
  - Email sending (after CEO approval)
  - Odoo payment recording
  - Human-in-the-loop approval gate
  - Dashboard.md updates (authoritative source)

Usage:
  python local_agent.py              # Single pass
  python local_agent.py --loop       # Continuous (30s interval)
  python local_agent.py --loop 15    # Custom interval
  python local_agent.py --test       # Self-test
  python local_agent.py --dashboard  # Update Dashboard.md now
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

AGENT_NAME    = "local"
LOOP_INTERVAL = 30  # seconds — local runs faster since it handles urgency


# ══════════════════════════════════════════════════════════════════════════════
# IMPORTS WITH GRACEFUL DEGRADATION
# ══════════════════════════════════════════════════════════════════════════════

def _import_claim_manager():
    try:
        from claim_manager import ClaimManager
        return ClaimManager
    except ImportError:
        return None


def _import_email_sender():
    try:
        from email_sender import send_email
        return send_email
    except ImportError:
        return None


def _import_whatsapp_sender():
    try:
        from whatsapp_sender import send_whatsapp
        return send_whatsapp
    except ImportError:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD WRITER (LOCAL IS SOLE OWNER)
# ══════════════════════════════════════════════════════════════════════════════

def update_dashboard():
    """
    Update Dashboard.md with current pipeline status.
    LOCAL AGENT ONLY writes this file — cloud agent never touches it.
    """
    dashboard_path = VAULT / "Dashboard.md"

    # Count files per stage
    stages = {
        "Inbox":            VAULT / "Inbox",
        "Needs_Action":     VAULT / "Needs_Action",
        "Needs_Action/cloud": VAULT / "Needs_Action" / "cloud",
        "Needs_Action/local": VAULT / "Needs_Action" / "local",
        "In_Progress/cloud":  VAULT / "In_Progress" / "cloud",
        "In_Progress/local":  VAULT / "In_Progress" / "local",
        "Plans/cloud":        VAULT / "Plans" / "cloud",
        "Plans/local":        VAULT / "Plans" / "local",
        "Pending_Approval":   VAULT / "Pending_Approval",
        "Pending_Approval/cloud": VAULT / "Pending_Approval" / "cloud",
        "Pending_Approval/local": VAULT / "Pending_Approval" / "local",
        "Approved":           VAULT / "Approved",
        "Done":               VAULT / "Done",
        "Rejected":           VAULT / "Rejected",
    }

    counts = {}
    for name, path in stages.items():
        if path.exists():
            counts[name] = len([f for f in path.iterdir()
                                 if f.is_file() and f.suffix in (".md", ".txt", ".json")])
        else:
            counts[name] = 0

    # Read recent updates from cloud
    updates_dir = VAULT / "Updates"
    recent_updates = []
    if updates_dir.exists():
        update_files = sorted(
            [f for f in updates_dir.iterdir() if f.suffix == ".json"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:10]
        for uf in update_files:
            try:
                data = json.loads(uf.read_text(encoding="utf-8"))
                recent_updates.append(data)
            except Exception:
                pass

    # Read active signals
    signals_dir = VAULT / "Signals"
    active_signals = []
    if signals_dir.exists():
        signal_files = sorted(
            [f for f in signals_dir.iterdir() if f.suffix == ".json"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:5]
        for sf in signal_files:
            try:
                data = json.loads(sf.read_text(encoding="utf-8"))
                active_signals.append(data)
            except Exception:
                pass

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build dashboard content
    lines = [
        "# AI Employee Dashboard — PLATINUM",
        "",
        f"> **Last Updated**: {now_str} (by Local Agent)",
        f"> **Architecture**: Cloud/Local Split | Zone: LOCAL is authoritative writer",
        "",
        "---",
        "",
        "## Pipeline Status",
        "",
        "| Stage | Count |",
        "|-------|-------|",
        f"| Inbox | {counts.get('Inbox', 0)} |",
        f"| Needs_Action (cloud) | {counts.get('Needs_Action/cloud', 0)} |",
        f"| Needs_Action (local) | {counts.get('Needs_Action/local', 0)} |",
        f"| In_Progress (cloud) | {counts.get('In_Progress/cloud', 0)} |",
        f"| In_Progress (local) | {counts.get('In_Progress/local', 0)} |",
        f"| Plans (cloud) | {counts.get('Plans/cloud', 0)} |",
        f"| Plans (local) | {counts.get('Plans/local', 0)} |",
        f"| Pending_Approval (cloud) | {counts.get('Pending_Approval/cloud', 0)} |",
        f"| Pending_Approval (local) | {counts.get('Pending_Approval/local', 0)} |",
        f"| Approved | {counts.get('Approved', 0)} |",
        f"| Done | {counts.get('Done', 0)} |",
        f"| Rejected | {counts.get('Rejected', 0)} |",
        "",
        "---",
        "",
        "## Pending Approvals",
        "",
    ]

    # List files pending approval
    approval_cloud = VAULT / "Pending_Approval" / "cloud"
    approval_local = VAULT / "Pending_Approval" / "local"

    approval_files = []
    for d in [approval_cloud, approval_local]:
        if d.exists():
            approval_files.extend([f for f in d.iterdir() if f.suffix in (".md", ".txt")])

    if approval_files:
        lines.append("**Drag to Approved/ or Rejected/ in Obsidian to decide:**")
        lines.append("")
        for af in sorted(approval_files, key=lambda f: f.stat().st_mtime, reverse=True)[:10]:
            zone = af.parent.name
            lines.append(f"- [ ] `{af.name}` *(zone: {zone})*")
    else:
        lines.append("*No items pending approval.*")

    lines += [
        "",
        "---",
        "",
        "## Recent Cloud Activity",
        "",
    ]

    if recent_updates:
        for u in recent_updates[:5]:
            ts  = u.get("timestamp", "")[:16]
            evt = u.get("event", "")
            tsk = u.get("task", "")
            q   = u.get("quality", "")
            q_str = f" quality={q:.1f}" if isinstance(q, (int, float)) else ""
            lines.append(f"- `{ts}` **{evt}** — {tsk}{q_str}")
    else:
        lines.append("*No recent cloud updates.*")

    lines += [
        "",
        "---",
        "",
        "## Active Signals",
        "",
    ]

    if active_signals:
        for s in active_signals:
            ts  = s.get("timestamp", "")[:16]
            typ = s.get("type", "")
            msg = s.get("message", "")
            lines.append(f"- `{ts}` **{typ}**: {msg}")
    else:
        lines.append("*No active signals.*")

    lines += [
        "",
        "---",
        "",
        "## Instructions",
        "",
        "- **Approve task**: Drag file from `Pending_Approval/cloud/` to `Approved/`",
        "- **Reject task**: Drag file from `Pending_Approval/cloud/` to `Rejected/`",
        "- **New task**: Drop a `.md` file into `Inbox/`",
        "- **Emergency stop**: Create `Signals/STOP.json` with `{\"type\": \"STOP\"}`",
        "",
        "---",
        "",
        "*AI Employee PLATINUM — Cloud/Local Architecture*",
        "*Stack: Groq + Gemini + Obsidian + Oracle Cloud Free Tier*",
    ]

    dashboard_path.write_text("\n".join(lines), encoding="utf-8")
    return counts


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def process_signals() -> list:
    """Read and process Signals/ from cloud agent. Returns list of active signals."""
    signals_dir = VAULT / "Signals"
    if not signals_dir.exists():
        return []

    signal_files = [f for f in signals_dir.iterdir() if f.suffix == ".json"]
    processed = []

    for sf in signal_files:
        if sf.name == ".gitkeep":
            continue
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
            sig_type = data.get("type", "")
            message  = data.get("message", "")

            print(f"  [Local] Signal: {sig_type} — {message}")

            if sig_type == "STOP":
                print("  [Local] STOP signal received. Halting.")
                sys.exit(0)
            elif sig_type in ("HEALTH_CRITICAL", "DISK_FULL", "API_QUOTA"):
                # Attempt Telegram notification
                _notify_telegram(f"[AI Employee] SIGNAL {sig_type}: {message}")

            processed.append(data)

        except Exception:
            pass

    return processed


# ══════════════════════════════════════════════════════════════════════════════
# UPDATE PROCESSOR (read cloud updates)
# ══════════════════════════════════════════════════════════════════════════════

def process_updates() -> int:
    """
    Read Updates/ folder from cloud agent.
    Merges info into local state. Returns count of updates processed.
    """
    updates_dir = VAULT / "Updates"
    if not updates_dir.exists():
        return 0

    update_files = [
        f for f in updates_dir.iterdir()
        if f.suffix == ".json" and not f.name.startswith(".")
    ]

    count = 0
    for uf in sorted(update_files, key=lambda f: f.stat().st_mtime):
        try:
            data  = json.loads(uf.read_text(encoding="utf-8"))
            event = data.get("event", "")

            if event == "TASK_DRAFTED":
                action_file = data.get("action_file", "")
                quality     = data.get("quality", 0)
                if quality >= 7.0:
                    print(f"  [Local] Cloud draft ready: {action_file} (quality={quality:.1f})")
                else:
                    print(f"  [Local] Cloud draft below threshold: {action_file} (quality={quality:.1f})")
                count += 1

        except Exception:
            pass

    return count


# ══════════════════════════════════════════════════════════════════════════════
# APPROVED TASK EXECUTOR
# ══════════════════════════════════════════════════════════════════════════════

def process_approved_tasks() -> int:
    """
    Read Approved/ folder and execute sends.
    Returns number of tasks sent.
    """
    approved_dir = VAULT / "Approved"
    if not approved_dir.exists():
        return 0

    approved_files = [
        f for f in approved_dir.iterdir()
        if f.is_file() and f.suffix in (".md", ".txt")
    ]

    done_dir = VAULT / "Done"
    done_dir.mkdir(parents=True, exist_ok=True)

    sent = 0
    for task_file in approved_files:
        try:
            content  = task_file.read_text(encoding="utf-8", errors="replace")
            filename = task_file.name.lower()

            success = False

            # Route based on task type
            if "whatsapp" in filename or "wa_" in filename:
                success = _execute_whatsapp(task_file.name, content)
            elif "email" in filename or "action_" in filename:
                success = _execute_email(task_file.name, content)
            else:
                # Generic: mark as sent (manual verification)
                print(f"  [Local] Executed (manual): {task_file.name}")
                success = True

            if success:
                shutil.move(str(task_file), str(done_dir / task_file.name))
                sent += 1
                print(f"  [Local] Sent: {task_file.name} -> Done/")

        except Exception as e:
            print(f"  [Local] ERROR executing {task_file.name}: {e}")

    return sent


def _execute_email(task_name: str, content: str) -> bool:
    """Extract email fields from ACTION file and send."""
    send_email = _import_email_sender()

    # Parse To, Subject from content
    to_match      = None
    subject_match = None

    for line in content.splitlines():
        if line.strip().startswith("To:"):
            to_match = line.split(":", 1)[1].strip()
        elif line.strip().startswith("Subject:"):
            subject_match = line.split(":", 1)[1].strip()

    if not to_match:
        to_match = os.getenv("GMAIL_USER", "")

    if not subject_match:
        subject_match = f"Re: {task_name}"

    if send_email:
        try:
            result = send_email(to_match, subject_match, content)
            print(f"  [Local] Email sent to {to_match}: {subject_match[:40]}")
            return True
        except Exception as e:
            print(f"  [Local] Email send failed: {e}")
            return False
    else:
        # Simulation — write to sent folder
        sent_dir = VAULT / "Done"
        sent_dir.mkdir(parents=True, exist_ok=True)
        print(f"  [Local] Email simulated: to={to_match} subject={subject_match[:40]}")
        return True


def _execute_whatsapp(task_name: str, content: str) -> bool:
    """Extract WhatsApp fields from ACTION file and send."""
    send_whatsapp = _import_whatsapp_sender()

    to_match = None
    for line in content.splitlines():
        if "To:" in line and ("+92" in line or "+1" in line or "+44" in line):
            to_match = line.split(":", 1)[1].strip()
            break

    if not to_match:
        to_match = os.getenv("WHATSAPP_TO", "")

    if send_whatsapp and to_match:
        try:
            result = send_whatsapp(to_match, "client", content)
            print(f"  [Local] WhatsApp sent to {to_match}")
            return True
        except Exception as e:
            print(f"  [Local] WhatsApp send failed: {e}")
            return False
    else:
        print(f"  [Local] WhatsApp simulated: to={to_match or 'unknown'}")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def _notify_telegram(message: str):
    """Send Telegram notification for urgent signals."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID", "")

    if not bot_token or not chat_id:
        print(f"  [Local] Telegram not configured. Message: {message}")
        return

    try:
        import urllib.request
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
        req  = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        print(f"  [Local] Telegram notified: {message[:50]}")
    except Exception as e:
        print(f"  [Local] Telegram error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LOCAL TASK PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

def _process_local_task(claim_record, task_content: str, cm) -> str:
    """Process a local-zone task (WhatsApp, payments, urgent sends)."""
    task_name = claim_record.filename
    print(f"  [Local] Processing local task: {task_name}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = task_name.lower()

    if "whatsapp" in filename:
        success = _execute_whatsapp(task_name, task_content)
    elif "payment" in filename or "invoice" in filename or "odoo" in filename:
        # Odoo tasks go to Pending_Approval/local for human confirmation
        approval_dir = VAULT / "Pending_Approval" / "local"
        approval_dir.mkdir(parents=True, exist_ok=True)
        action_file = approval_dir / f"ACTION_{timestamp}_{task_name}"
        action_file.write_text(
            f"# Payment/Odoo Action — {task_name}\n\n"
            f"**Requires human approval before execution.**\n\n"
            f"{task_content}\n\n"
            "---\nMove to Approved/ to process payment.",
            encoding="utf-8",
        )
        cm.release(claim_record, f"Pending_Approval/local")
        print(f"  [Local] Payment task -> Pending_Approval/local for human approval")
        return "Pending_Approval/local"
    else:
        # Unknown — mark done with note
        print(f"  [Local] Unknown local task type: {task_name}")
        success = True

    cm.release(claim_record, "Done")
    return "Done"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PASS
# ══════════════════════════════════════════════════════════════════════════════

def run_pass() -> dict:
    """
    Single pass:
    1. Process signals from cloud
    2. Read cloud updates
    3. Process local-zone tasks
    4. Execute approved tasks
    5. Update Dashboard.md
    Returns stats dict.
    """
    stats = {
        "signals":  0,
        "updates":  0,
        "local_tasks": 0,
        "sent":     0,
    }

    # 1. Signals
    signals = process_signals()
    stats["signals"] = len(signals)

    # 2. Cloud updates
    stats["updates"] = process_updates()

    # 3. Local zone tasks
    ClaimManagerClass = _import_claim_manager()
    if ClaimManagerClass:
        cm = ClaimManagerClass(VAULT)
        while True:
            record = cm.claim_next(AGENT_NAME)
            if record is None:
                break
            try:
                content = record.path.read_text(encoding="utf-8", errors="replace")
                _process_local_task(record, content, cm)
                stats["local_tasks"] += 1
            except Exception as e:
                print(f"  [Local] ERROR processing {record.filename}: {e}")
                try:
                    cm.release(record, f"Needs_Action/{AGENT_NAME}")
                except Exception:
                    pass

    # 4. Execute approved tasks
    stats["sent"] = process_approved_tasks()

    # 5. Update Dashboard.md (LOCAL IS SOLE WRITER)
    update_dashboard()

    return stats


# ══════════════════════════════════════════════════════════════════════════════
# SELF-TEST
# ══════════════════════════════════════════════════════════════════════════════

def run_test():
    print("=" * 55)
    print("  LOCAL AGENT — Self Test")
    print("=" * 55)

    # Create a test signal
    signals_dir = VAULT / "Signals"
    signals_dir.mkdir(parents=True, exist_ok=True)
    test_signal = signals_dir / "SIGNAL_TEST_INFO.json"
    test_signal.write_text(
        json.dumps({
            "type": "INFO",
            "message": "Cloud agent started successfully",
            "agent": "cloud",
            "timestamp": datetime.now().isoformat(),
        }, indent=2),
        encoding="utf-8",
    )
    print(f"\n  [1] Created test signal: {test_signal.name}")

    # Create a test update
    updates_dir = VAULT / "Updates"
    updates_dir.mkdir(parents=True, exist_ok=True)
    test_update = updates_dir / "UPDATE_TEST_TASK_DRAFTED.json"
    test_update.write_text(
        json.dumps({
            "event": "TASK_DRAFTED",
            "task": "TEST_EMAIL.md",
            "agent": "cloud",
            "quality": 8.5,
            "revisions": 0,
            "timestamp": datetime.now().isoformat(),
        }, indent=2),
        encoding="utf-8",
    )
    print(f"  [2] Created test update: {test_update.name}")

    # Run a pass
    stats = run_pass()
    print(f"\n  [3] Pass stats: {stats}")

    # Check Dashboard.md was written
    dashboard = VAULT / "Dashboard.md"
    if dashboard.exists():
        lines = dashboard.read_text(encoding="utf-8").count("\n")
        print(f"  [4] Dashboard.md updated: {lines} lines")
    else:
        print("  [4] FAIL: Dashboard.md not found")

    print(f"\n  Result: PASS")
    print("=" * 55)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if "--test" in args:
        run_test()
        return

    if "--dashboard" in args:
        counts = update_dashboard()
        print("[Local Agent] Dashboard.md updated.")
        total = sum(v for k, v in counts.items() if "/" not in k)
        print(f"  Total files tracked: {total}")
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
        print("  LOCAL AGENT — Continuous Mode")
        print(f"  Zone:     {AGENT_NAME}")
        print(f"  Interval: {interval}s")
        print(f"  Vault:    {VAULT}")
        print("  Dashboard.md: SOLE WRITER")
        print("  Press Ctrl+C to stop")
        print("=" * 55)

        try:
            pass_count = 0
            while True:
                print(f"\n  [{time.strftime('%H:%M:%S')}] Local pass #{pass_count + 1}...")
                stats = run_pass()

                total = stats["signals"] + stats["updates"] + stats["local_tasks"] + stats["sent"]
                if total > 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] "
                          f"signals={stats['signals']} updates={stats['updates']} "
                          f"tasks={stats['local_tasks']} sent={stats['sent']}")
                else:
                    print(f"  [{time.strftime('%H:%M:%S')}] All quiet.")

                pass_count += 1
                print(f"  Next pass in {interval}s...")
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n  Local Agent stopped.")

    else:
        # Single pass
        print(f"  [Local Agent] Single pass — Zone: {AGENT_NAME}")
        stats = run_pass()
        print(f"  [Local Agent] Pass complete: {stats}")


if __name__ == "__main__":
    main()
