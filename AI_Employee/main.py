"""
AI Employee — Master Demo Pipeline
====================================
Runs the complete workflow end-to-end:

  Inbox -> Needs_Action -> Plans -> Pending_Approval -> Approved -> Done

Modes:
  --demo     : Full auto demo (no human input needed)
  --live     : Interactive mode (asks for human approval)
  --status   : Show current pipeline status only

Usage:
  python main.py --demo     # Hackathon demo (auto-approves everything)
  python main.py --live     # Real mode (human approves each task)
  python main.py --status   # Just show pipeline status
"""

import os
import sys
import shutil
import json
import time
from pathlib import Path
from datetime import datetime

from channel_dispatcher import dispatch


# ============================================================
# PATHS
# ============================================================
BASE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.join(BASE, "AI_Employee_Vault")

INBOX = os.path.join(VAULT, "Inbox")
NEEDS_ACTION = os.path.join(VAULT, "Needs_Action")
PLANS = os.path.join(VAULT, "Plans")
PENDING_APPROVAL = os.path.join(VAULT, "Pending_Approval")
APPROVED = os.path.join(VAULT, "Approved")
DONE = os.path.join(VAULT, "Done")
LOGS = os.path.join(VAULT, "Logs")

ALL_FOLDERS = [INBOX, NEEDS_ACTION, PLANS, PENDING_APPROVAL, APPROVED, DONE, LOGS]


def ensure_folders():
    """Create all vault folders if they don't exist"""
    for folder in ALL_FOLDERS:
        os.makedirs(folder, exist_ok=True)


def list_files(folder):
    """List files in a folder (ignore directories)"""
    if not os.path.exists(folder):
        return []
    return [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]


def banner(text):
    """Print a nice banner"""
    width = 60
    print(f"\n{'='*width}")
    print(f"  {text}")
    print(f"{'='*width}")


# ============================================================
# STAGE 1: INBOX -> NEEDS_ACTION (Watcher)
# ============================================================
def stage_1_watcher():
    """Move files from Inbox to Needs_Action"""
    banner("STAGE 1: Inbox -> Needs_Action (Watcher)")

    files = list_files(INBOX)
    if not files:
        print("  No new files in Inbox/")
        return 0

    for f in files:
        src = os.path.join(INBOX, f)
        dst = os.path.join(NEEDS_ACTION, f)
        shutil.move(src, dst)
        print(f"  Moved: {f} -> Needs_Action/")

    return len(files)


# ============================================================
# STAGE 2: NEEDS_ACTION -> PLANS + PENDING_APPROVAL (Brain)
# ============================================================
def stage_2_brain():
    """Claude Runner processes tasks"""
    banner("STAGE 2: Needs_Action -> Plans + Pending_Approval (AI Brain)")

    # Import and run claude_runner
    os.chdir(BASE)
    from claude_runner import process_needs_action
    results = process_needs_action()

    if not results:
        print("  No tasks to process.")
        return []

    for r in results:
        print(f"  Processed: {r['file']} | Channel: {r['channel']}")

    return results


# ============================================================
# STAGE 3: PENDING_APPROVAL -> APPROVED (Human Approval)
# ============================================================
def stage_3_approval(auto_approve=False):
    """Human reviews and approves tasks"""
    banner("STAGE 3: Pending_Approval -> Approved (Human Gate)")

    files = list_files(PENDING_APPROVAL)
    if not files:
        print("  No tasks pending approval.")
        return 0

    approved_count = 0
    for f in files:
        src = os.path.join(PENDING_APPROVAL, f)

        if auto_approve:
            # Demo mode: auto-approve everything
            print(f"  [AUTO-APPROVED] {f}")
            approved = True
        else:
            # Live mode: ask human
            print(f"\n  Task: {f}")
            print(f"  ---")

            # Show a preview of the file
            with open(src, "r", encoding="utf-8") as fp:
                content = fp.read()
            # Show first 15 lines as preview
            preview_lines = content.split("\n")[:15]
            for line in preview_lines:
                print(f"    {line}")
            if len(content.split("\n")) > 15:
                print(f"    ... ({len(content.split(chr(10)))} total lines)")

            print()
            choice = input("  Approve? (y/n/q): ").strip().lower()
            if choice == "q":
                print("  Stopping approval process.")
                break
            approved = choice in ("y", "yes", "")

        if approved:
            # Update status in the file
            with open(src, "r", encoding="utf-8") as fp:
                content = fp.read()
            content = content.replace("PENDING APPROVAL", "APPROVED")
            content = content.replace("PENDING — Awaiting Human Approval", "APPROVED — Ready to Send")

            dst = os.path.join(APPROVED, f)
            with open(dst, "w", encoding="utf-8") as fp:
                fp.write(content)
            os.remove(src)

            approved_count += 1
        else:
            print(f"  [REJECTED] {f} — stays in Pending_Approval/")

    return approved_count


# ============================================================
# STAGE 4: APPROVED -> DONE + SEND (Executor)
# ============================================================
def stage_4_executor():
    """Execute approved tasks — send messages via all channels"""
    banner("STAGE 4: Approved -> Execute + Done (Executor)")

    files = list_files(APPROVED)
    if not files:
        print("  No approved tasks to execute.")
        return 0

    os.chdir(BASE)

    # Load existing logs
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOGS, f"{today}.json")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []

    executed = 0
    for file in files:
        file_path = os.path.join(APPROVED, file)

        try:
            with open(file_path, "r", encoding="utf-8") as fp:
                content = fp.read()

            # Dispatch via unified channel handler
            send_status, channel, recipient = dispatch(Path(file_path), content)
        except Exception as e:
            send_status = f"ERROR: {e}"
            channel = "Unknown"
            recipient = "N/A"

        # Move to Done
        shutil.move(file_path, os.path.join(DONE, file))

        # Log
        log_entry = {
            "task": os.path.splitext(file)[0],
            "status": send_status,
            "time": datetime.now().strftime("%I:%M %p"),
            "channel": channel,
            "to": recipient,
        }
        logs.append(log_entry)

        print(f"  [{channel}] {file} -> {send_status}")
        executed += 1

    # Save logs
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    print(f"\n  Log saved: {log_file}")

    return executed


# ============================================================
# STATUS — Show Pipeline Overview
# ============================================================
def show_status():
    """Display current pipeline status"""
    banner("AI EMPLOYEE — Pipeline Status")

    stages = [
        ("Inbox", INBOX),
        ("Needs_Action", NEEDS_ACTION),
        ("Plans", PLANS),
        ("Pending_Approval", PENDING_APPROVAL),
        ("Approved", APPROVED),
        ("Done", DONE),
    ]

    total = 0
    for name, path in stages:
        files = list_files(path)
        count = len(files)
        total += count
        indicator = ">>>" if count > 0 else "   "
        print(f"  {indicator} {name:20s} : {count} file(s)")
        for f in files:
            print(f"       - {f}")

    print(f"\n  Total files in pipeline: {total}")

    # Show today's log
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(LOGS, f"{today}.json")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
        print(f"\n  Today's log ({today}): {len(logs)} entries")
        for entry in logs[-5:]:
            ch = entry.get("channel", "")
            print(f"    [{entry['time']}] {ch:10s} | {entry['task']} -> {entry['status']}")
    print()


# ============================================================
# MAIN
# ============================================================
def main():
    ensure_folders()
    os.chdir(BASE)

    mode = "--demo"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    if mode == "--status":
        show_status()
        return

    banner("AI EMPLOYEE — Full Pipeline Demo")
    print(f"  Mode: {'AUTO DEMO' if mode == '--demo' else 'LIVE (Interactive)'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")

    # Run all 4 stages
    print()

    # Stage 1: Inbox -> Needs_Action
    moved = stage_1_watcher()
    print(f"  Result: {moved} file(s) moved\n")

    # Stage 2: Brain processes tasks
    results = stage_2_brain()
    print(f"  Result: {len(results)} task(s) processed\n")

    # Stage 3: Approval
    auto = (mode == "--demo")
    approved = stage_3_approval(auto_approve=auto)
    print(f"  Result: {approved} task(s) approved\n")

    # Stage 4: Execute + Send
    executed = stage_4_executor()
    print(f"  Result: {executed} task(s) executed\n")

    # Final Status
    show_status()

    banner("PIPELINE COMPLETE")
    print("  External actions are abstracted behind")
    print("  an approval-gated execution layer.")
    print()


if __name__ == "__main__":
    main()
