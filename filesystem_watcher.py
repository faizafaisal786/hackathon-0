from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from datetime import datetime
import time, shutil

VAULT = Path(r"C:\Users\HDD BANK\Desktop\Obsidian Vaults")
NEEDS = VAULT / "Needs_Action"

# Folders to ignore (don't copy pipeline folders back into Needs_Action)
IGNORE_FOLDERS = {
    "Needs_Action", "Pending_Approval", "Approved", "Rejected",
    "Done", "Plans", "Logs", "Briefings", "AI_Employee_Vault",
    ".obsidian", ".git"
}

IGNORE_EXTENSIONS = {".py", ".sh", ".log", ".pickle", ".json"}

NEEDS.mkdir(exist_ok=True)

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        src = Path(event.src_path)

        # Skip files from pipeline/system folders
        if src.parent.name in IGNORE_FOLDERS:
            return

        # Skip system/script files
        if src.suffix in IGNORE_EXTENSIONS:
            return

        dest = NEEDS / src.name
        try:
            shutil.copy(src, dest)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] Copied: {src.name} -> Needs_Action/")
        except Exception as e:
            print(f"[ERROR] {src.name}: {e}")

print("=" * 45)
print("  FILESYSTEM WATCHER — Active")
print(f"  Watching: {VAULT}")
print(f"  Target:   Needs_Action/")
print("  Press Ctrl+C to stop")
print("=" * 45)

observer = Observer()
observer.schedule(Handler(), str(VAULT), recursive=False)
observer.start()

try:
    while True:
        time.sleep(5)
except KeyboardInterrupt:
    observer.stop()
    print("\n  Stopped.")

observer.join()

