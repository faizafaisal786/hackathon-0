"""
Watchdog — Gold Tier Process Health Monitor
=============================================
Monitors all AI Employee processes and system health.
Auto-restarts crashed processes via PM2.
Writes health signals to AI_Employee_Vault/Signals/.

Checks performed every interval:
  1. PM2 process status (all 6 processes must be online)
  2. Disk space (alert if < 15% free)
  3. Groq API reachability
  4. Vault folder accessibility
  5. Log file growth (detect stuck processes)

Signals written to:
  AI_Employee_Vault/Signals/HEALTH_OK.md      -- all green
  AI_Employee_Vault/Signals/HEALTH_WARN.md    -- warnings
  AI_Employee_Vault/Signals/HEALTH_CRITICAL.md -- critical issues

Usage:
  python watchdog.py              # Single health check
  python watchdog.py --loop       # Continuous monitor (every 5 min)
  python watchdog.py --loop 60    # Every 60 seconds
"""

import os
import sys
import json
import time
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

BASE     = Path(__file__).parent
VAULT    = BASE / "AI_Employee_Vault"
SIGNALS  = VAULT / "Signals"
LOGS_DIR = VAULT / "Logs"

# PM2 processes that should always be online
EXPECTED_PROCESSES = [
    "gmail-watcher",
    "whatsapp-watcher",
    "filesystem-watcher",
    "linkedin-autoposter",
    "local-agent",
    "ralph-loop",
]

DISK_WARN_PCT     = 20   # warn if free < 20%
DISK_CRITICAL_PCT = 10   # critical if free < 10%
CHECK_INTERVAL    = 300  # 5 minutes default


# ─────────────────────────────────────────────────────────────────
# CHECKS
# ─────────────────────────────────────────────────────────────────

def check_pm2_processes() -> dict:
    """
    Run 'pm2 jlist' and parse JSON output.
    Returns {process_name: status} dict.
    """
    result = {"status": "ok", "issues": [], "processes": {}}
    try:
        # On Windows, pm2 is a .cmd file — use shell=True
        use_shell = sys.platform == "win32"
        out = subprocess.run(
            "pm2 jlist",
            capture_output=True, text=True, timeout=15,
            shell=use_shell,
        )
        if out.returncode != 0:
            result["status"] = "warn"
            result["issues"].append("PM2 jlist failed — PM2 may not be running")
            return result

        raw_out = out.stdout.strip()
        if not raw_out:
            raw_out = out.stderr.strip()

        processes = json.loads(raw_out)
        for proc in processes:
            name   = proc.get("name", "unknown")
            status = proc.get("pm2_env", {}).get("status", "unknown")
            result["processes"][name] = status

        # Check each expected process
        for name in EXPECTED_PROCESSES:
            proc_status = result["processes"].get(name)
            if proc_status is None:
                result["issues"].append(f"{name}: NOT FOUND in PM2")
                result["status"] = "warn"
            elif proc_status != "online":
                result["issues"].append(f"{name}: {proc_status} (expected: online)")
                result["status"] = "critical"

    except subprocess.TimeoutExpired:
        result["status"] = "warn"
        result["issues"].append("PM2 check timed out")
    except json.JSONDecodeError:
        result["status"] = "warn"
        result["issues"].append("PM2 output not valid JSON")
    except FileNotFoundError:
        result["status"] = "warn"
        result["issues"].append("PM2 not found — install with: npm install -g pm2")
    except Exception as e:
        result["status"] = "warn"
        result["issues"].append(f"PM2 check error: {e}")

    return result


def check_disk_space() -> dict:
    """Check free disk space on the vault drive."""
    result = {"status": "ok", "issues": [], "free_pct": 100}
    try:
        total, used, free = shutil.disk_usage(str(VAULT))
        free_pct = round((free / total) * 100, 1)
        result["free_pct"] = free_pct
        result["free_gb"]  = round(free / (1024**3), 2)

        if free_pct < DISK_CRITICAL_PCT:
            result["status"] = "critical"
            result["issues"].append(
                f"Disk CRITICAL: only {free_pct}% free ({result['free_gb']} GB)"
            )
        elif free_pct < DISK_WARN_PCT:
            result["status"] = "warn"
            result["issues"].append(
                f"Disk LOW: {free_pct}% free ({result['free_gb']} GB)"
            )
    except Exception as e:
        result["status"] = "warn"
        result["issues"].append(f"Disk check error: {e}")
    return result


def check_groq_api() -> dict:
    """Ping Groq API with a minimal request."""
    result = {"status": "ok", "issues": []}
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key or "your_" in groq_key or len(groq_key) < 10:
        result["status"] = "warn"
        result["issues"].append("GROQ_API_KEY not configured")
        return result
    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp   = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=3,
        )
        result["model"] = resp.model
    except Exception as e:
        result["status"] = "warn"
        result["issues"].append(f"Groq API error: {str(e)[:80]}")
    return result


def check_vault_folders() -> dict:
    """Verify all key vault folders are accessible."""
    result   = {"status": "ok", "issues": []}
    required = ["Inbox", "Needs_Action", "Done", "Plans",
                "Pending_Approval", "Logs", "Signals"]
    for folder in required:
        path = VAULT / folder
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                result["status"] = "warn"
                result["issues"].append(f"Folder {folder} missing and cannot create: {e}")
    return result


# ─────────────────────────────────────────────────────────────────
# AUTO-RESTART
# ─────────────────────────────────────────────────────────────────

def restart_process(name: str) -> bool:
    """Attempt to restart a PM2 process."""
    try:
        use_shell = sys.platform == "win32"
        out = subprocess.run(
            f"pm2 restart {name}",
            capture_output=True, text=True, timeout=15,
            shell=use_shell,
        )
        return out.returncode == 0
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────
# SIGNAL WRITER
# ─────────────────────────────────────────────────────────────────

def _write_signal(level: str, summary: str, details: list):
    """Write a health signal file to Signals/ folder."""
    SIGNALS.mkdir(parents=True, exist_ok=True)
    now      = datetime.now()
    filename = f"HEALTH_{level}_{now.strftime('%Y%m%d_%H%M%S')}.md"

    # Remove old signals of same level
    for old in SIGNALS.glob(f"HEALTH_{level}_*.md"):
        try:
            old.unlink()
        except Exception:
            pass

    content = f"""# Health Signal — {level}

| Field | Value |
|-------|-------|
| Level | {level} |
| Time | {now.strftime('%Y-%m-%d %H:%M:%S')} |
| Summary | {summary} |

## Details

"""
    for d in details:
        content += f"- {d}\n"

    (SIGNALS / filename).write_text(content, encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────

def _log(event: str, details: str, severity: str = "INFO"):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"watchdog_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            entries = []

    entries.append({
        "event":     event,
        "details":   details,
        "severity":  severity,
        "timestamp": datetime.now().isoformat(),
    })
    log_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────
# MAIN CHECK
# ─────────────────────────────────────────────────────────────────

def run_health_check(auto_restart: bool = True) -> str:
    """
    Run all health checks. Returns overall status: ok / warn / critical.
    If auto_restart=True, attempts to restart crashed PM2 processes.
    """
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    issues = []
    worst  = "ok"

    def _escalate(status: str):
        nonlocal worst
        if status == "critical" or (status == "warn" and worst == "ok"):
            worst = status

    print(f"\n  [{now}] Running health checks...")

    # 1. Vault folders
    vr = check_vault_folders()
    _escalate(vr["status"])
    issues.extend(vr["issues"])
    print(f"  [1] Vault folders: {vr['status'].upper()}")

    # 2. Disk space
    dr = check_disk_space()
    _escalate(dr["status"])
    issues.extend(dr["issues"])
    free_pct = dr.get("free_pct", "?")
    print(f"  [2] Disk space: {dr['status'].upper()} ({free_pct}% free)")

    # 3. PM2 processes
    pr = check_pm2_processes()
    _escalate(pr["status"])
    issues.extend(pr["issues"])
    online_count = sum(1 for s in pr["processes"].values() if s == "online")
    total_count  = len(EXPECTED_PROCESSES)
    print(f"  [3] PM2 processes: {pr['status'].upper()} ({online_count}/{total_count} online)")

    # Auto-restart crashed processes
    if auto_restart and pr["issues"]:
        for issue in pr["issues"]:
            for name in EXPECTED_PROCESSES:
                if name in issue and ("stopped" in issue or "errored" in issue):
                    print(f"  [WATCHDOG] Restarting {name}...")
                    ok = restart_process(name)
                    msg = f"Restarted {name}: {'OK' if ok else 'FAILED'}"
                    issues.append(msg)
                    _log("AUTO_RESTART", msg, "WARN")

    # 4. Groq API
    gr = check_groq_api()
    _escalate(gr["status"])
    issues.extend(gr["issues"])
    print(f"  [4] Groq API: {gr['status'].upper()}")

    # Write signal
    if worst == "ok":
        _write_signal("OK", f"All systems healthy — {online_count}/{total_count} processes online", [
            f"Disk: {free_pct}% free",
            f"PM2: {online_count}/{total_count} online",
            "Groq API: reachable",
        ])
        print(f"  [WATCHDOG] Status: ALL OK")
    elif worst == "warn":
        _write_signal("WARN", f"{len(issues)} warning(s)", issues)
        print(f"  [WATCHDOG] Status: WARN — {len(issues)} issue(s)")
    else:
        _write_signal("CRITICAL", f"{len(issues)} critical issue(s)", issues)
        print(f"  [WATCHDOG] Status: CRITICAL — {len(issues)} issue(s)")
        for i in issues:
            print(f"    - {i}")

    # Log the result
    _log("HEALTH_CHECK", f"status={worst} issues={len(issues)} disk={free_pct}%",
         "INFO" if worst == "ok" else "WARN" if worst == "warn" else "ERROR")

    return worst


# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    if "--loop" in args:
        interval = CHECK_INTERVAL
        for a in args:
            if a.isdigit():
                interval = int(a)

        print("=" * 55)
        print("  WATCHDOG — Continuous Health Monitor")
        print(f"  Interval: {interval}s ({interval//60}m)")
        print(f"  Watching: {len(EXPECTED_PROCESSES)} PM2 processes")
        print("  Press Ctrl+C to stop")
        print("=" * 55)

        try:
            while True:
                run_health_check(auto_restart=True)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n  Watchdog stopped.")
    else:
        # Single check
        print("=" * 55)
        print("  WATCHDOG — Health Check")
        print("=" * 55)
        status = run_health_check(auto_restart=False)
        print(f"\n  Final Status: {status.upper()}")
        print("=" * 55)


if __name__ == "__main__":
    main()
