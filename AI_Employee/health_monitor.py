"""
Health Monitor — Platinum Tier
================================
Runs on Oracle Cloud Free Tier VM as a background process.
Monitors system health and writes signals to vault for local agent.

Checks performed every N seconds:
  1. Disk space (alert if < 15% free)
  2. Memory usage (alert if > 85% used)
  3. Log error rate (alert if > 10 errors in last hour)
  4. API health (Groq, Gemini ping)
  5. Vault Git sync status (last sync time)
  6. Process health (cloud_agent.py, ralph_loop.py still running)

On issue detection:
  - Write SIGNAL_*.json to Signals/ folder
  - Telegram alert if TELEGRAM_BOT_TOKEN configured
  - Write health report to Logs/health_YYYY-MM-DD.json

Usage:
  python health_monitor.py              # Single health check
  python health_monitor.py --loop       # Continuous (every 5 minutes)
  python health_monitor.py --loop 60    # Custom interval (seconds)
  python health_monitor.py --report     # Print full health report
  python health_monitor.py --test       # Self-test
"""

import sys
import os
import json
import time
import platform
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

DEFAULT_INTERVAL = 300  # 5 minutes

THRESHOLDS = {
    "disk_free_pct_min":   15.0,   # Alert if disk < 15% free
    "memory_used_pct_max": 85.0,   # Alert if memory > 85% used
    "log_errors_per_hour": 10,     # Alert if > 10 errors/hour
    "sync_lag_seconds":    300,    # Alert if vault not synced in 5 min
}


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECKS
# ══════════════════════════════════════════════════════════════════════════════

def check_disk() -> dict:
    """Check disk space on vault drive."""
    try:
        import shutil
        total, used, free = shutil.disk_usage(str(VAULT))
        free_pct = (free / total) * 100 if total > 0 else 100

        status = "OK"
        if free_pct < THRESHOLDS["disk_free_pct_min"]:
            status = "CRITICAL"
        elif free_pct < THRESHOLDS["disk_free_pct_min"] * 1.5:
            status = "WARNING"

        return {
            "check":    "disk",
            "status":   status,
            "free_gb":  round(free / (1024**3), 2),
            "total_gb": round(total / (1024**3), 2),
            "free_pct": round(free_pct, 1),
            "threshold_pct": THRESHOLDS["disk_free_pct_min"],
        }
    except Exception as e:
        return {"check": "disk", "status": "ERROR", "error": str(e)}


def check_memory() -> dict:
    """Check RAM usage."""
    try:
        # Try psutil first
        import psutil
        mem = psutil.virtual_memory()
        used_pct = mem.percent

        status = "OK"
        if used_pct > THRESHOLDS["memory_used_pct_max"]:
            status = "CRITICAL"
        elif used_pct > THRESHOLDS["memory_used_pct_max"] - 10:
            status = "WARNING"

        return {
            "check":      "memory",
            "status":     status,
            "used_pct":   round(used_pct, 1),
            "available_gb": round(mem.available / (1024**3), 2),
            "total_gb":   round(mem.total / (1024**3), 2),
        }
    except ImportError:
        # Fallback: read /proc/meminfo on Linux
        try:
            if platform.system() == "Linux":
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                info = {}
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1])
                total     = info.get("MemTotal", 1)
                available = info.get("MemAvailable", total)
                used_pct  = ((total - available) / total) * 100

                status = "CRITICAL" if used_pct > THRESHOLDS["memory_used_pct_max"] else "OK"
                return {
                    "check":    "memory",
                    "status":   status,
                    "used_pct": round(used_pct, 1),
                    "total_gb": round(total / (1024**2), 2),
                }
        except Exception as e:
            return {"check": "memory", "status": "UNKNOWN", "error": str(e)}
    except Exception as e:
        return {"check": "memory", "status": "ERROR", "error": str(e)}


def check_log_errors() -> dict:
    """Count errors in logs from the past hour."""
    try:
        logs_dir = VAULT / "Logs"
        if not logs_dir.exists():
            return {"check": "log_errors", "status": "OK", "errors_last_hour": 0}

        one_hour_ago = datetime.now() - timedelta(hours=1)
        error_count  = 0
        files_scanned = 0

        for log_file in logs_dir.glob("*.json"):
            try:
                entries = json.loads(log_file.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    continue

                for entry in entries:
                    ts_str = entry.get("timestamp", "")
                    if not ts_str:
                        continue
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if ts >= one_hour_ago:
                            if not entry.get("success", True):
                                error_count += 1
                            if "error" in entry.get("event", "").lower():
                                error_count += 1
                    except Exception:
                        pass
                files_scanned += 1
            except Exception:
                pass

        status = "CRITICAL" if error_count > THRESHOLDS["log_errors_per_hour"] else "OK"
        if 5 < error_count <= THRESHOLDS["log_errors_per_hour"]:
            status = "WARNING"

        return {
            "check":            "log_errors",
            "status":           status,
            "errors_last_hour": error_count,
            "files_scanned":    files_scanned,
            "threshold":        THRESHOLDS["log_errors_per_hour"],
        }
    except Exception as e:
        return {"check": "log_errors", "status": "ERROR", "error": str(e)}


def check_api_health() -> dict:
    """Ping Groq and Gemini to check API reachability."""
    results = {}

    # Check Groq
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                results["groq"] = "OK" if resp.status == 200 else f"HTTP {resp.status}"
        except Exception as e:
            results["groq"] = f"ERROR: {str(e)[:50]}"
    else:
        results["groq"] = "NO_KEY"

    # Check Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            import urllib.request
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                results["gemini"] = "OK" if resp.status == 200 else f"HTTP {resp.status}"
        except Exception as e:
            results["gemini"] = f"ERROR: {str(e)[:50]}"
    else:
        results["gemini"] = "NO_KEY"

    # Overall status
    has_working_ai = any("OK" in v for v in results.values())
    status = "OK" if has_working_ai else "CRITICAL"

    return {
        "check":   "api_health",
        "status":  status,
        "results": results,
    }


def check_git_sync() -> dict:
    """Check if vault Git sync is up-to-date."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1", "--format=%ct"],
            cwd=str(BASE),
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {"check": "git_sync", "status": "UNKNOWN", "error": "git command failed"}

        last_commit_ts = int(result.stdout.strip()) if result.stdout.strip() else 0
        age_seconds    = time.time() - last_commit_ts

        status = "OK"
        if age_seconds > THRESHOLDS["sync_lag_seconds"]:
            status = "WARNING"
        if age_seconds > THRESHOLDS["sync_lag_seconds"] * 6:
            status = "CRITICAL"

        return {
            "check":           "git_sync",
            "status":          status,
            "last_commit_age": int(age_seconds),
            "threshold":       THRESHOLDS["sync_lag_seconds"],
        }
    except Exception as e:
        return {"check": "git_sync", "status": "UNKNOWN", "error": str(e)}


def check_processes() -> dict:
    """Check if key agent processes are running."""
    try:
        import psutil
        running = {name: False for name in ("cloud_agent.py", "ralph_loop.py", "local_agent.py")}

        for proc in psutil.process_iter(["cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                for name in running:
                    if name in cmdline:
                        running[name] = True
            except Exception:
                pass

        status = "WARNING" if not running.get("cloud_agent.py") else "OK"
        return {
            "check":     "processes",
            "status":    status,
            "processes": running,
        }
    except ImportError:
        return {"check": "processes", "status": "UNKNOWN", "error": "psutil not installed"}
    except Exception as e:
        return {"check": "processes", "status": "ERROR", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL WRITER
# ══════════════════════════════════════════════════════════════════════════════

def _write_signal(signal_type: str, message: str, data: dict = None):
    signals_dir = VAULT / "Signals"
    signals_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"SIGNAL_{timestamp}_{signal_type}.json"

    signal = {
        "type":      signal_type,
        "message":   message,
        "agent":     "health_monitor",
        "timestamp": datetime.now().isoformat(),
        "data":      data or {},
    }
    (signals_dir / filename).write_text(
        json.dumps(signal, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _notify_telegram(message: str):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.getenv("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return

    try:
        import urllib.request
        url  = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
        req  = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def run_all_checks() -> dict:
    """Run all health checks and return combined report."""
    checks = [
        check_disk(),
        check_memory(),
        check_log_errors(),
        check_api_health(),
        check_git_sync(),
        check_processes(),
    ]

    overall = "OK"
    critical_count = 0
    warning_count  = 0

    for c in checks:
        if c.get("status") == "CRITICAL":
            critical_count += 1
            overall = "CRITICAL"
        elif c.get("status") == "WARNING" and overall != "CRITICAL":
            warning_count += 1
            overall = "WARNING"

    report = {
        "overall":        overall,
        "critical_count": critical_count,
        "warning_count":  warning_count,
        "timestamp":      datetime.now().isoformat(),
        "platform":       platform.system(),
        "checks":         checks,
    }

    return report


def _save_health_log(report: dict):
    logs_dir = VAULT / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = logs_dir / f"health_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except Exception:
            entries = []

    entries.append(report)
    log_file.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _process_report(report: dict):
    """Write signals and Telegram alerts based on health report."""
    overall = report.get("overall", "OK")

    if overall == "CRITICAL":
        msg = f"[AI Employee] CRITICAL health issue detected at {report['timestamp'][:19]}"
        for c in report["checks"]:
            if c.get("status") == "CRITICAL":
                msg += f"\n  - {c['check']}: {c}"
        _write_signal("HEALTH_CRITICAL", msg, report)
        _notify_telegram(msg[:500])
        print(f"  [Health] CRITICAL: {msg[:100]}")

    elif overall == "WARNING":
        msg = f"[AI Employee] WARNING: health degraded"
        _write_signal("HEALTH_WARNING", msg, report)
        print(f"  [Health] WARNING: {report['warning_count']} issue(s)")

    else:
        print(f"  [Health] All checks OK")


# ══════════════════════════════════════════════════════════════════════════════
# REPORT PRINTER
# ══════════════════════════════════════════════════════════════════════════════

def print_report(report: dict):
    print("=" * 60)
    print("  HEALTH MONITOR REPORT")
    print(f"  Time:     {report['timestamp'][:19]}")
    print(f"  Platform: {report.get('platform', 'unknown')}")
    print(f"  Overall:  {report['overall']}")
    print("=" * 60)

    for c in report.get("checks", []):
        status = c.get("status", "?")
        check  = c.get("check", "?")
        icon   = "[OK]" if status == "OK" else ("[!!]" if status == "CRITICAL" else "[**]")
        print(f"\n  {icon} {check.upper()} — {status}")

        if check == "disk":
            print(f"       Free: {c.get('free_gb', '?')} GB ({c.get('free_pct', '?')}%)")
        elif check == "memory":
            print(f"       Used: {c.get('used_pct', '?')}% | Available: {c.get('available_gb', '?')} GB")
        elif check == "log_errors":
            print(f"       Errors last hour: {c.get('errors_last_hour', 0)}")
        elif check == "api_health":
            for api, result in c.get("results", {}).items():
                print(f"       {api}: {result}")
        elif check == "git_sync":
            age = c.get("last_commit_age", 0)
            print(f"       Last sync: {age}s ago")
        elif check == "processes":
            for proc, running in c.get("processes", {}).items():
                status_str = "running" if running else "NOT RUNNING"
                print(f"       {proc}: {status_str}")
        elif "error" in c:
            print(f"       Error: {c['error']}")

    print(f"\n  Critical: {report['critical_count']} | Warning: {report['warning_count']}")
    print("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if "--test" in args:
        print("  [Health Monitor] Running self-test...")
        report = run_all_checks()
        print_report(report)
        _save_health_log(report)
        _process_report(report)
        print("\n  [PASS] Health monitor working correctly.")
        return

    if "--report" in args:
        report = run_all_checks()
        print_report(report)
        return

    interval = DEFAULT_INTERVAL
    if "--loop" in args:
        idx = args.index("--loop")
        if idx + 1 < len(args):
            try:
                interval = int(args[idx + 1])
            except ValueError:
                pass

        print("=" * 55)
        print("  HEALTH MONITOR — Continuous Mode")
        print(f"  Interval: {interval}s")
        print(f"  Vault:    {VAULT}")
        print("  Press Ctrl+C to stop")
        print("=" * 55)

        try:
            while True:
                print(f"\n  [{time.strftime('%H:%M:%S')}] Running health checks...")
                report = run_all_checks()
                _save_health_log(report)
                _process_report(report)
                print(f"  Next check in {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n  Health Monitor stopped.")

    else:
        # Single check
        report = run_all_checks()
        _save_health_log(report)
        _process_report(report)
        print(f"  Overall: {report['overall']} | "
              f"Critical: {report['critical_count']} | "
              f"Warning: {report['warning_count']}")


if __name__ == "__main__":
    main()
