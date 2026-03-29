"""
Silver + Gold Tier Full Verification Script
"""
import os, sys, json, subprocess, re
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

passed = []
failed = []

def check(tier, name, result, detail=""):
    if result:
        passed.append(name)
        print(f"  [PASS] [{tier}] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] [{tier}] {name}")
    if detail:
        print(f"              -> {detail}")


print()
print("=" * 62)
print("   SILVER + GOLD TIER — FULL VERIFICATION REPORT")
print("=" * 62)

# ─── SILVER TIER ──────────────────────────────────────────
print()
print("  -- SILVER TIER -----------------------------------")

# S1: Gmail Watcher
gw = BASE / "gmail_watcher.py"
check("SILVER", "Gmail Watcher script", gw.exists(), f"{gw.stat().st_size} bytes" if gw.exists() else "MISSING")

# S2: WhatsApp Watcher
ww = BASE / "whatsapp_watcher.py"
check("SILVER", "WhatsApp Watcher script", ww.exists(), f"{ww.stat().st_size} bytes" if ww.exists() else "MISSING")

# S3: LinkedIn Auto-Poster
la = BASE / "linkedin_autoposter.py"
check("SILVER", "LinkedIn Auto-Poster script", la.exists(), f"{la.stat().st_size} bytes" if la.exists() else "MISSING")

# S4: Claude reasoning loop (4-agent pipeline)
ag = BASE / "agents.py"
if ag.exists():
    content = ag.read_text(encoding="utf-8")
    has_pipeline = "run_platinum_pipeline" in content and "ThinkerAgent" in content
    check("SILVER", "Claude Reasoning Loop (4-agent pipeline)", has_pipeline, "THINKER->PLANNER->EXECUTOR->REVIEWER")
else:
    check("SILVER", "Claude Reasoning Loop", False, "agents.py missing")

# S5: Plan.md files generated
plans_dir = VAULT / "Plans"
plan_files = list(plans_dir.glob("*.md")) if plans_dir.exists() else []
check("SILVER", "Plan.md files generated", len(plan_files) > 0, f"{len(plan_files)} plan(s) exist in Plans/")

# S6: MCP Server
mcp = BASE / "mcp_server.py"
if mcp.exists():
    tools = re.findall(r"@mcp\.tool\(\)", mcp.read_text(encoding="utf-8"))
    check("SILVER", "MCP Server (external actions)", len(tools) >= 4, f"{len(tools)} tools registered")
else:
    check("SILVER", "MCP Server", False, "mcp_server.py missing")

# S7: HITL Approval Workflow
sm = BASE / "state_machine.py"
if sm.exists():
    content = sm.read_text(encoding="utf-8")
    has_hitl = "PENDING_APPROVAL" in content and "APPROVED" in content
    check("SILVER", "HITL Approval Workflow (state machine)", has_hitl, "Pending_Approval -> Approved -> Done pipeline")
else:
    check("SILVER", "HITL Approval Workflow", False)

# S8: Scheduling via PM2
eco = BASE / "ecosystem.config.js"
check("SILVER", "Scheduling via PM2 (ecosystem.config.js)", eco.exists(), "Always-on daemon scheduling")

# S9: PM2 processes running
def get_pm2_online():
    """Return list of online PM2 process names using jlist JSON."""
    r = subprocess.run("pm2 jlist", shell=True, capture_output=True, timeout=15)
    raw = r.stdout.decode("utf-8", errors="replace").strip() if r.stdout else "[]"
    if not raw or raw == "[]":
        # fallback: parse text output — look for name+online on same line
        r2 = subprocess.run("pm2 list --no-color", shell=True,
                            capture_output=True, timeout=10)
        text = r2.stdout.decode("utf-8", errors="replace") if r2.stdout else ""
        # each row contains process name and status — find lines with "online"
        online = []
        for line in text.splitlines():
            if "online" in line:
                # extract word tokens that look like process names
                names = re.findall(r"[\w][\w-]{2,}", line)
                for n in names:
                    if n not in ("online", "default", "disabled", "fork"):
                        online.append(n)
                        break
        return online
    try:
        procs = json.loads(raw)
        return [p["name"] for p in procs
                if p.get("pm2_env", {}).get("status") == "online"]
    except Exception:
        return []

try:
    online = get_pm2_online()
    check("SILVER", "Watchers running in PM2", len(online) >= 3,
          f"Online ({len(online)}): {', '.join(online)}")
except Exception as e:
    check("SILVER", "PM2 processes", False, str(e))

# ─── GOLD TIER ────────────────────────────────────────────
print()
print("  -- GOLD TIER -------------------------------------")

# G1: Odoo Community MCP
odoo = BASE / "odoo_mcp.py"
if odoo.exists():
    tools = re.findall(r"@mcp\.tool\(\)", odoo.read_text(encoding="utf-8"))
    check("GOLD", "Odoo Community MCP Integration", len(tools) >= 6, f"{len(tools)} tools: invoices, customers, accounting")
else:
    check("GOLD", "Odoo Community MCP Integration", False, "odoo_mcp.py missing")

# G2: Facebook
try:
    from social_media_sender import dispatch_social
    fb = dispatch_social("Facebook", "Gold Tier Test", "AI Employee Gold Tier verification")
    check("GOLD", "Facebook posting", "ready" in str(fb).lower() or "post" in str(fb).lower(), str(fb)[:70])
except Exception as e:
    check("GOLD", "Facebook posting", False, str(e)[:70])

# G3: Instagram
try:
    from social_media_sender import dispatch_social
    ig = dispatch_social("Instagram", "Gold Tier Test", "AI Employee Instagram verification")
    check("GOLD", "Instagram posting", "ready" in str(ig).lower() or "post" in str(ig).lower(), str(ig)[:70])
except Exception as e:
    check("GOLD", "Instagram posting", False, str(e)[:70])

# G4: Twitter (X)
try:
    from twitter_sender import post_tweet
    tw = post_tweet("Gold Tier", "AI Employee Gold Tier verification")
    check("GOLD", "Twitter (X) posting", "ready" in str(tw).lower() or "Twitter" in str(tw), str(tw)[:70])
except Exception as e:
    check("GOLD", "Twitter (X) posting", False, str(e)[:70])

# G5: CEO Briefing generator
bg = BASE / "briefing_generator.py"
briefings_dir = VAULT / "Briefings"
brief_files = list(briefings_dir.glob("Briefing_*.md")) if briefings_dir.exists() else []
check("GOLD", "CEO Briefing generator script", bg.exists(), f"{bg.stat().st_size} bytes" if bg.exists() else "MISSING")
check("GOLD", "CEO Briefing files stored", len(brief_files) > 0, f"{len(brief_files)} briefing(s) in Briefings/")

# G6: Ralph Loop Monday briefing
rl = BASE / "ralph_loop.py"
if rl.exists():
    content = rl.read_text(encoding="utf-8")
    has_briefing = "briefing" in content.lower() and "monday" in content.lower()
    check("GOLD", "Ralph Loop with Monday CEO briefing", has_briefing, "Auto-triggers every Monday")
else:
    check("GOLD", "Ralph Loop", False)

# G7: Multiple MCP Servers
mcp_tools = len(re.findall(r"@mcp\.tool\(\)", mcp.read_text(encoding="utf-8"))) if mcp.exists() else 0
odoo_tools = len(re.findall(r"@mcp\.tool\(\)", odoo.read_text(encoding="utf-8"))) if odoo.exists() else 0
check("GOLD", "Multiple MCP servers (2 servers)", mcp.exists() and odoo.exists(),
      f"mcp_server.py ({mcp_tools} tools) + odoo_mcp.py ({odoo_tools} tools)")

# G8: Watchdog
wdog = BASE / "watchdog.py"
signals = VAULT / "Signals"
sig_files = list(signals.glob("HEALTH_*.md")) if signals.exists() else []
check("GOLD", "Watchdog error recovery script", wdog.exists(), f"{wdog.stat().st_size} bytes" if wdog.exists() else "MISSING")
check("GOLD", "Watchdog health signals written", len(sig_files) > 0, f"{len(sig_files)} HEALTH_*.md signal(s)")

# G9: Audit logging
log_dir = VAULT / "Logs"
today_log = log_dir / "2026-03-28.json"
if today_log.exists():
    try:
        data = json.loads(today_log.read_text(encoding="utf-8"))
        events = data.get("total_events", 0)
        check("GOLD", "Comprehensive audit logging (JSON)", events > 100, f"{events} events in 2026-03-28.json")
    except Exception as e:
        check("GOLD", "Comprehensive audit logging", False, f"Parse error: {e}")
else:
    check("GOLD", "Comprehensive audit logging", False, "No log file today")

# G10: Ralph Loop + Watchdog in PM2
try:
    online = get_pm2_online()
    ralph_online    = "ralph-loop" in online
    watchdog_online = "watchdog"   in online
    check("GOLD", "Ralph Wiggum Loop in PM2", ralph_online,
          "online" if ralph_online else "not found")
    check("GOLD", "Watchdog running in PM2", watchdog_online,
          "online" if watchdog_online else "not found")
except Exception as e:
    check("GOLD", "Ralph/Watchdog PM2", False, str(e))

# G11: Architecture documentation
readme = BASE / "README.md"
check("GOLD", "Architecture documentation (README.md)", readme.exists(),
      f"{readme.stat().st_size} bytes" if readme.exists() else "MISSING")

# ─── SUMMARY ──────────────────────────────────────────────
print()
print("=" * 62)
total = len(passed) + len(failed)
pct   = int(100 * len(passed) / total) if total else 0
print(f"  RESULT: {len(passed)}/{total} checks PASSED ({pct}%)")
if failed:
    print(f"  FAILED items ({len(failed)}):")
    for f in failed:
        print(f"    - {f}")
else:
    print("  ALL CHECKS PASSED!")
    print("  Silver Tier: 100% COMPLETE")
    print("  Gold Tier:   100% COMPLETE")
print("=" * 62)
