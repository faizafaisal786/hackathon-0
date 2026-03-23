"""
watchdog.py — Process Monitor & Auto-Restart
============================================
Monitors critical AI Employee processes and automatically restarts
them if they die. Sends a Markdown alert to /Needs_Action when
a restart happens.

Usage:
    python error_recovery/watchdog.py
    python error_recovery/watchdog.py --vault-path /path/to/vault
"""

import os
import sys
import time
import json
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

VAULT_PATH = Path(os.getenv("VAULT_PATH", Path(__file__).parent.parent))
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("Watchdog")

CHECK_INTERVAL = 60  # seconds

# Processes to monitor: name → (script path, args)
MONITORED_PROCESSES = {
    "orchestrator": ("orchestrator.py", []),
    "filesystem_watcher": ("watchers/filesystem_watcher.py", []),
    "gmail_watcher": ("watchers/gmail_watcher.py", []),
}


class ProcessMonitor:
    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.processes: dict[str, subprocess.Popen] = {}
        self.restart_counts: dict[str, int] = {}
        self.pid_dir = vault_path / "Logs" / "pids"
        self.pid_dir.mkdir(parents=True, exist_ok=True)

    def start(self, name: str, script: str, extra_args: list[str] = None):
        script_path = self.vault_path / script
        if not script_path.exists():
            logger.warning(f"Script not found: {script_path}")
            return

        cmd = [sys.executable, str(script_path), "--vault-path", str(self.vault_path)]
        if extra_args:
            cmd.extend(extra_args)

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            self.processes[name] = proc
            self.restart_counts.setdefault(name, 0)

            # Save PID
            (self.pid_dir / f"{name}.pid").write_text(str(proc.pid))
            logger.info(f"Started '{name}' (PID {proc.pid})")
        except Exception as e:
            logger.error(f"Failed to start '{name}': {e}")

    def start_all(self):
        for name, (script, args) in MONITORED_PROCESSES.items():
            self.start(name, script, args)

    def is_running(self, name: str) -> bool:
        proc = self.processes.get(name)
        if proc is None:
            return False
        return proc.poll() is None

    def check_and_restart(self):
        for name, (script, args) in MONITORED_PROCESSES.items():
            if not self.is_running(name):
                self.restart_counts[name] = self.restart_counts.get(name, 0) + 1
                count = self.restart_counts[name]
                logger.warning(f"'{name}' is not running! Restart #{count}")
                self._alert_human(name, count)
                self.start(name, script, args)

    def _alert_human(self, process_name: str, restart_count: int):
        """Create an alert in /Needs_Action for the human."""
        now = datetime.now()
        filename = f"ALERT_Process_Restart_{process_name}_{now.strftime('%Y%m%d_%H%M%S')}.md"
        alert_path = self.vault_path / "Needs_Action" / filename

        content = f"""---
type: system_alert
process: {process_name}
restart_count: {restart_count}
timestamp: {now.isoformat()}
priority: {"critical" if restart_count > 3 else "high"}
status: pending
---

# System Alert: Process Restarted

The process **`{process_name}`** stopped unexpectedly and was automatically restarted.

## Details
- **Process**: `{process_name}`
- **Restart Count**: {restart_count}
- **Time**: {now.strftime('%Y-%m-%d %H:%M:%S')}

## Action Required
{"- [ ] **CRITICAL**: Process has restarted more than 3 times. Manual investigation needed." if restart_count > 3 else "- [ ] Review logs to understand why the process stopped."}
- [ ] Check logs at `Logs/` for errors.
- [ ] Verify the process is now running correctly.
- [ ] Move to /Done when resolved.
"""
        alert_path.write_text(content, encoding="utf-8")
        logger.info(f"Alert created: {filename}")

        # Log the event
        log_file = self.vault_path / "Logs" / f"{now.strftime('%Y-%m-%d')}.json"
        entry = {
            "timestamp": now.isoformat(),
            "action_type": "process_restarted",
            "actor": "watchdog",
            "process": process_name,
            "restart_count": restart_count,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def stop_all(self):
        for name, proc in self.processes.items():
            proc.terminate()
            logger.info(f"Stopped: {name}")


def main():
    parser = argparse.ArgumentParser(description="AI Employee Watchdog — Gold Tier")
    parser.add_argument("--vault-path", type=Path, default=VAULT_PATH)
    args = parser.parse_args()

    vault_path = args.vault_path.resolve()
    monitor = ProcessMonitor(vault_path)
    monitor.start_all()

    logger.info("Watchdog running. Checking every 60 seconds...")

    try:
        while True:
            monitor.check_and_restart()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("Watchdog shutting down...")
        monitor.stop_all()


if __name__ == "__main__":
    main()
