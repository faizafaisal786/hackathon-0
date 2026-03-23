"""
Claim Manager — Platinum Tier
================================
Implements the claim-by-move rule to prevent duplicate processing
between cloud and local agents.

Rules:
  - A task is "claimed" by atomically moving it from /Needs_Action/<zone>/
    to /In_Progress/<agent>/ before any processing starts.
  - If a move fails (file already moved by another agent), the claim fails
    silently — the other agent owns it.
  - A task is "released" by moving it out of /In_Progress/<agent>/
    (to Plans/, Pending_Approval/, Done/, or Rejected/).
  - Stale claims (file in /In_Progress/ > MAX_CLAIM_AGE_SECONDS) are
    automatically released back to /Needs_Action/.

Zone assignment:
  - CLOUD handles: email triage, social media drafts, reply drafts
  - LOCAL handles: WhatsApp, payments, final sends, human approval items

Usage:
  cm = ClaimManager(vault_path)
  task = cm.claim_next("cloud")
  if task:
      # process task...
      cm.release(task, destination="Plans/cloud")
  else:
      print("No tasks available for cloud zone")
"""

import os
import time
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

# Tasks older than this in In_Progress/ are considered stale
MAX_CLAIM_AGE_SECONDS = 300  # 5 minutes


# ══════════════════════════════════════════════════════════════════════════════
# ZONE CONFIG
# ══════════════════════════════════════════════════════════════════════════════

ZONE_KEYWORDS = {
    "cloud": [
        "email", "linkedin", "twitter", "facebook", "instagram",
        "social", "draft", "reply", "post", "content",
    ],
    "local": [
        "whatsapp", "payment", "invoice", "odoo", "send", "approve",
        "urgent", "call", "meet", "cash",
    ],
}


def _detect_zone(filename: str, content: str = "") -> str:
    """
    Detect which zone (cloud/local) should handle a task.
    Returns 'cloud' or 'local'.
    """
    text = (filename + " " + content).lower()

    cloud_score = sum(1 for kw in ZONE_KEYWORDS["cloud"] if kw in text)
    local_score = sum(1 for kw in ZONE_KEYWORDS["local"] if kw in text)

    return "local" if local_score > cloud_score else "cloud"


# ══════════════════════════════════════════════════════════════════════════════
# CLAIM RECORD
# ══════════════════════════════════════════════════════════════════════════════

class ClaimRecord:
    """Represents a claimed task."""

    def __init__(self, filename: str, agent: str, source_zone: str, path: Path):
        self.filename   = filename
        self.agent      = agent        # "cloud" or "local"
        self.zone       = source_zone  # original zone
        self.path       = path         # current path (In_Progress/<agent>/<filename>)
        self.claimed_at = datetime.now().isoformat()

    def __repr__(self):
        return f"ClaimRecord({self.filename!r}, agent={self.agent!r})"

    def age_seconds(self) -> float:
        claimed_dt = datetime.fromisoformat(self.claimed_at)
        return (datetime.now() - claimed_dt).total_seconds()


# ══════════════════════════════════════════════════════════════════════════════
# CLAIM MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class ClaimManager:

    def __init__(self, vault: Path = VAULT):
        self.vault = vault
        self._log_path = vault / "Logs"
        self._log_path.mkdir(parents=True, exist_ok=True)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _needs_action_dir(self, zone: str) -> Path:
        d = self.vault / "Needs_Action" / zone
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _in_progress_dir(self, agent: str) -> Path:
        d = self.vault / "In_Progress" / agent
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _task_files(self, folder: Path) -> list[Path]:
        return sorted(
            [f for f in folder.iterdir() if f.is_file() and f.suffix in (".md", ".txt")],
            key=lambda f: f.stat().st_mtime,
        )

    def _log(self, event: str, details: str, agent: str = ""):
        today    = datetime.now().strftime("%Y-%m-%d")
        log_file = self._log_path / f"claim_manager_{today}.json"

        entries = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
            except Exception:
                entries = []

        entries.append({
            "event":     event,
            "agent":     agent,
            "details":   details,
            "timestamp": datetime.now().isoformat(),
        })
        log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Zone routing ─────────────────────────────────────────────────────────

    def route_task(self, task_path: Path) -> str:
        """
        Move a task from Needs_Action/ (root) into the correct zone subfolder.
        Returns the detected zone ('cloud' or 'local').
        """
        try:
            content = task_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

        zone    = _detect_zone(task_path.name, content)
        dst_dir = self._needs_action_dir(zone)
        dst     = dst_dir / task_path.name

        if dst.exists():
            # Already routed — no-op
            return zone

        try:
            shutil.move(str(task_path), str(dst))
            self._log("ROUTED", f"{task_path.name} -> Needs_Action/{zone}/", agent=zone)
            print(f"  [Claim] Routed {task_path.name} -> {zone}")
        except Exception as e:
            self._log("ROUTE_ERROR", f"{task_path.name}: {e}", agent=zone)

        return zone

    def route_all_pending(self):
        """
        Route all unzoned tasks from Needs_Action/ (root) into zone subfolders.
        Call this once per loop pass before claiming.
        """
        needs_action_root = self.vault / "Needs_Action"
        pending = [
            f for f in needs_action_root.iterdir()
            if f.is_file() and f.suffix in (".md", ".txt")
        ]
        for task in pending:
            self.route_task(task)

    # ── Claim ─────────────────────────────────────────────────────────────────

    def claim_next(self, agent: str) -> Optional[ClaimRecord]:
        """
        Atomically claim the next available task for this agent's zone.
        Returns a ClaimRecord or None if nothing available.
        """
        # Release any stale claims first
        self._release_stale(agent)

        # Route unzoned tasks
        self.route_all_pending()

        src_dir = self._needs_action_dir(agent)
        dst_dir = self._in_progress_dir(agent)

        tasks = self._task_files(src_dir)
        if not tasks:
            return None

        for task_path in tasks:
            dst = dst_dir / task_path.name
            if dst.exists():
                continue  # Already claimed (race condition)

            try:
                shutil.move(str(task_path), str(dst))
                record = ClaimRecord(task_path.name, agent, agent, dst)
                self._log(
                    "CLAIMED",
                    f"{task_path.name} -> In_Progress/{agent}/",
                    agent=agent,
                )
                print(f"  [Claim] {agent} claimed: {task_path.name}")
                return record
            except Exception:
                continue  # Another agent beat us to it

        return None

    def claim_specific(self, agent: str, filename: str, zone: str = None) -> Optional[ClaimRecord]:
        """
        Claim a specific file by name.
        zone defaults to agent zone if not specified.
        """
        zone    = zone or agent
        src_dir = self._needs_action_dir(zone)
        dst_dir = self._in_progress_dir(agent)

        src = src_dir / filename
        dst = dst_dir / filename

        if not src.exists():
            return None
        if dst.exists():
            return None  # Already claimed

        try:
            shutil.move(str(src), str(dst))
            record = ClaimRecord(filename, agent, zone, dst)
            self._log("CLAIMED_SPECIFIC", f"{filename} by {agent}", agent=agent)
            return record
        except Exception:
            return None

    # ── Release ───────────────────────────────────────────────────────────────

    def release(self, record: ClaimRecord, destination: str) -> bool:
        """
        Release a claimed task to a destination folder.

        destination examples:
          "Plans/cloud"
          "Pending_Approval/cloud"
          "Done"
          "Rejected"
          "Needs_Action/local"  (hand off to other zone)

        Returns True on success.
        """
        dst_dir = self.vault / destination
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / record.filename

        try:
            shutil.move(str(record.path), str(dst))
            self._log(
                "RELEASED",
                f"{record.filename}: In_Progress/{record.agent}/ -> {destination}/",
                agent=record.agent,
            )
            print(f"  [Claim] {record.agent} released: {record.filename} -> {destination}/")
            return True
        except Exception as e:
            self._log("RELEASE_ERROR", f"{record.filename}: {e}", agent=record.agent)
            return False

    def release_to_handoff(self, record: ClaimRecord, target_zone: str) -> bool:
        """Hand off a task to the other zone's Needs_Action folder."""
        return self.release(record, f"Needs_Action/{target_zone}")

    # ── Stale claim cleanup ───────────────────────────────────────────────────

    def _release_stale(self, agent: str):
        """Move stale claims back to Needs_Action/<agent>/."""
        in_progress = self._in_progress_dir(agent)
        needs_action = self._needs_action_dir(agent)

        for task in self._task_files(in_progress):
            age = time.time() - task.stat().st_mtime
            if age > MAX_CLAIM_AGE_SECONDS:
                dst = needs_action / task.name
                try:
                    shutil.move(str(task), str(dst))
                    self._log(
                        "STALE_RELEASED",
                        f"{task.name} age={int(age)}s -> Needs_Action/{agent}/",
                        agent=agent,
                    )
                    print(f"  [Claim] Stale claim released: {task.name} (age {int(age)}s)")
                except Exception:
                    pass

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return current claim status for all zones."""
        result = {}
        for zone in ("cloud", "local"):
            needs_action = self._task_files(self._needs_action_dir(zone))
            in_progress  = self._task_files(self._in_progress_dir(zone))
            result[zone] = {
                "needs_action": [f.name for f in needs_action],
                "in_progress":  [f.name for f in in_progress],
            }
        return result


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import sys
    args = sys.argv[1:]

    cm = ClaimManager()

    if "--status" in args or not args:
        status = cm.status()
        print("=" * 50)
        print("  CLAIM MANAGER STATUS")
        print("=" * 50)
        for zone, data in status.items():
            print(f"\n  Zone: {zone}")
            print(f"    Needs_Action : {len(data['needs_action'])} tasks")
            for f in data["needs_action"]:
                print(f"      - {f}")
            print(f"    In_Progress  : {len(data['in_progress'])} tasks")
            for f in data["in_progress"]:
                print(f"      - {f}")
        print()

    elif "--route" in args:
        cm.route_all_pending()
        print("[OK] All pending tasks routed to zone subfolders.")

    elif "--stale" in args:
        cm._release_stale("cloud")
        cm._release_stale("local")
        print("[OK] Stale claims released.")

    elif "--test" in args:
        print("=" * 50)
        print("  CLAIM MANAGER — Test")
        print("=" * 50)

        # Create a test task in Needs_Action/cloud/
        test_file = VAULT / "Needs_Action" / "cloud" / "TEST_CLAIM_TASK.md"
        test_file.write_text(
            "# Test Task\nChannel: Email\nPriority: Low\nMessage: Claim manager test",
            encoding="utf-8",
        )
        print(f"\n  [1] Created test task: {test_file.name}")

        # Claim it
        record = cm.claim_next("cloud")
        if record:
            print(f"  [2] Claimed: {record.filename} (agent={record.agent})")
            # Release to Plans
            ok = cm.release(record, "Plans/cloud")
            print(f"  [3] Released to Plans/cloud: {'OK' if ok else 'FAIL'}")
        else:
            print("  [2] FAIL: Could not claim test task")

        print("\n  Status after test:")
        status = cm.status()
        for zone, data in status.items():
            print(f"    {zone}: needs_action={len(data['needs_action'])} in_progress={len(data['in_progress'])}")

        print("\n  [PASS] Claim manager working correctly.")
        print("=" * 50)


if __name__ == "__main__":
    main()
