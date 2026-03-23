"""
LOCAL APPROVAL WATCHER
Runs on YOUR local PC alongside Obsidian.
Watches for approval/rejection actions and auto-syncs via Git.

How it works:
1. You open Obsidian and see tasks in Pending_Approval/
2. You move files to Approved/ or Rejected/
3. This watcher detects the move and auto git commit + push
4. Cloud VM pulls the changes and acts on them

Usage: python local_approval_watcher.py
Requirements: pip install watchdog
"""

import time
import subprocess
import json
from pathlib import Path
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("Install watchdog: pip install watchdog")


VAULT_PATH = Path(r"C:\Users\HDD BANK\Desktop\Obsidian Vaults")

WATCH_FOLDERS = [
    VAULT_PATH / "Approved",
    VAULT_PATH / "Rejected",
    VAULT_PATH / "Pending_Approval",
]


class ApprovalHandler(FileSystemEventHandler):
    """Watches for file changes in approval folders"""

    def __init__(self):
        self.last_sync = None

    def on_created(self, event):
        if event.is_directory:
            return
        filepath = Path(event.src_path)
        folder = filepath.parent.name
        filename = filepath.name

        print(f"\n[{self._timestamp()}] NEW: {folder}/{filename}")

        if folder == "Approved":
            self._log_action("APPROVED", filename)
            self._git_sync(f"APPROVED: {filename}")

        elif folder == "Rejected":
            self._log_action("REJECTED", filename)
            self._git_sync(f"REJECTED: {filename}")

    def on_moved(self, event):
        if event.is_directory:
            return
        src = Path(event.src_path)
        dest = Path(event.dest_path)

        src_folder = src.parent.name
        dest_folder = dest.parent.name
        filename = dest.name

        print(f"\n[{self._timestamp()}] MOVED: {src_folder}/{filename} -> {dest_folder}/{filename}")

        if dest_folder == "Approved":
            self._log_action("APPROVED", filename)
            self._git_sync(f"APPROVED: {filename}")

        elif dest_folder == "Rejected":
            self._log_action("REJECTED", filename)
            self._git_sync(f"REJECTED: {filename}")

    def _git_sync(self, message):
        """Commit and push changes to git"""
        try:
            timestamp = self._timestamp()
            commit_msg = f"[Local Approval] {message} — {timestamp}"

            subprocess.run(["git", "add", "-A"], cwd=VAULT_PATH, check=True,
                           capture_output=True)
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=VAULT_PATH,
                           check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=VAULT_PATH,
                           check=True, capture_output=True)

            print(f"[{timestamp}] Git synced: {message}")
            self.last_sync = timestamp

        except subprocess.CalledProcessError as e:
            print(f"[{self._timestamp()}] Git sync error: {e.stderr.decode() if e.stderr else str(e)}")

    def _log_action(self, action, filename):
        """Log approval/rejection to audit log"""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = VAULT_PATH / "Logs" / f"{today}.json"

            if log_file.exists():
                with open(log_file, "r", encoding="utf-8") as f:
                    log_data = json.load(f)
            else:
                log_data = {
                    "audit_date": today,
                    "system": "AI Employee Vault",
                    "version": "1.0",
                    "total_events": 0,
                    "events": []
                }

            event_id = f"EVT-{log_data['total_events'] + 1:03d}"
            log_data["total_events"] += 1
            log_data["events"].append({
                "id": event_id,
                "timestamp": datetime.now().isoformat(),
                "actor": "human",
                "action": f"LOCAL_{action}",
                "category": "approval",
                "details": f"Human {action.lower()} {filename} from local Obsidian",
                "file": filename,
                "severity": "INFO",
                "result": "SUCCESS"
            })

            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2)

            print(f"[{self._timestamp()}] Logged: {action} {filename}")

        except Exception as e:
            print(f"[{self._timestamp()}] Log error: {e}")

    def _timestamp(self):
        return datetime.now().strftime("%H:%M:%S")


def main():
    if not WATCHDOG_AVAILABLE:
        print("ERROR: pip install watchdog")
        return

    print("=" * 50)
    print("  LOCAL APPROVAL WATCHER")
    print("  Watching: Approved/, Rejected/, Pending_Approval/")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    print()

    handler = ApprovalHandler()
    observer = Observer()

    for folder in WATCH_FOLDERS:
        folder.mkdir(exist_ok=True)
        observer.schedule(handler, str(folder), recursive=False)
        print(f"  Watching: {folder.name}/")

    observer.start()
    print(f"\n  Started at {datetime.now().strftime('%H:%M:%S')}")
    print("  Waiting for approvals...\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n  Stopped.")

    observer.join()


if __name__ == "__main__":
    main()
