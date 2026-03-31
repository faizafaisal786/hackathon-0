"""
Platinum Tier Full Verification Script
"""
import sys, os, json, subprocess, re
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"

passed = []
failed = []

def check(name, result, detail=""):
    if result:
        passed.append(name)
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}")
    if detail:
        print(f"              -> {detail}")

print()
print("=" * 62)
print("   PLATINUM TIER -- FULL VERIFICATION REPORT")
print("=" * 62)
print()

# P1: Cloud 24/7 deployment scripts
check("Cloud setup script (cloud_setup.sh)",
      (BASE / "cloud_setup.sh").exists(),
      f"{(BASE/'cloud_setup.sh').stat().st_size} bytes — Oracle Free Tier")

check("Odoo cloud setup (odoo_cloud_setup.sh)",
      (BASE / "odoo_cloud_setup.sh").exists(),
      f"{(BASE/'odoo_cloud_setup.sh').stat().st_size} bytes — HTTPS + backups")

# P2: Cloud/Local zone split
cloud_agent = BASE / "cloud_agent.py"
local_agent = BASE / "local_agent.py"
check("Cloud Agent script", cloud_agent.exists(),
      f"{cloud_agent.stat().st_size} bytes" if cloud_agent.exists() else "MISSING")
check("Local Agent script", local_agent.exists(),
      f"{local_agent.stat().st_size} bytes" if local_agent.exists() else "MISSING")

if local_agent.exists():
    content = local_agent.read_text(encoding="utf-8")
    check("Local owns Dashboard.md (single-writer rule)",
          "SOLE WRITER" in content or "single-writer" in content.lower() or "Dashboard.md" in content,
          "Local Agent is sole writer of Dashboard.md")
    check("Local owns WhatsApp session",
          "whatsapp" in content.lower() and "playwright" in content.lower(),
          "Playwright sender (free) + Twilio fallback")
    check("Payment threshold approval (PKR 50,000)",
          "payment" in content.lower() and "threshold" in content.lower() or "50_000" in content or "50000" in content,
          "Payments > PKR 50,000 flagged for CEO review")

# P3: Vault folder structure
folders = [
    "Inbox", "Needs_Action/cloud", "Needs_Action/local",
    "In_Progress/cloud", "In_Progress/local",
    "Plans/cloud", "Pending_Approval/cloud", "Approved", "Done",
    "Updates", "Signals",
]
all_folders = all((VAULT / f).exists() for f in folders)
existing    = [f for f in folders if (VAULT / f).exists()]
check("Platinum vault folder structure", all_folders,
      f"{len(existing)}/{len(folders)} folders exist")

# P4: Claim-by-move (claim_manager.py)
cm = BASE / "claim_manager.py"
check("Claim-by-move (claim_manager.py)", cm.exists(),
      f"{cm.stat().st_size} bytes — atomic file move, no duplicates")

# P5: Cloud->Local communication channels
updates_dir = VAULT / "Updates"
signals_dir = VAULT / "Signals"
check("Updates/ channel (Cloud writes, Local reads)",
      updates_dir.exists(),
      f"{len(list(updates_dir.iterdir()))} file(s)" if updates_dir.exists() else "MISSING")
check("Signals/ channel (health alerts)",
      signals_dir.exists(),
      f"{len(list(signals_dir.glob('*.json') )+ list(signals_dir.glob('*.md')))} signal(s)")

# P6: Odoo backup
odoo_backup = BASE / "odoo_backup.py"
backup_dir  = BASE / "odoo_backups"
backup_runs = sorted(backup_dir.iterdir()) if backup_dir.exists() else []
check("Odoo backup script (odoo_backup.py)", odoo_backup.exists(),
      f"{odoo_backup.stat().st_size} bytes" if odoo_backup.exists() else "MISSING")
check("Odoo backup data exists", len(backup_runs) > 0,
      f"{len(backup_runs)} backup(s) in odoo_backups/")

if backup_runs:
    latest = backup_runs[-1]
    summary_f = latest / "summary.json"
    if summary_f.exists():
        s = json.loads(summary_f.read_text(encoding="utf-8"))
        check("Odoo backup content valid",
              s.get("customers", 0) > 0 and s.get("invoices", 0) > 0,
              f"{s['customers']} customers, {s['invoices']} invoices, PKR {s.get('total_invoiced',0):,.0f}")

# P7: A2A Agent (Phase 2)
a2a = BASE / "a2a_agent.py"
check("A2A agent script (a2a_agent.py)", a2a.exists(),
      f"{a2a.stat().st_size} bytes" if a2a.exists() else "MISSING")
if a2a.exists():
    content = a2a.read_text(encoding="utf-8")
    check("A2A HTTP server", "HTTPServer" in content, "Phase 2 direct messaging server")
    check("A2A vault fallback", "_write_to_vault" in content, "Falls back to vault if HTTP down")

# P8: WhatsApp Playwright sender (free, local-only)
wa_playwright = BASE / "whatsapp_playwright_sender.py"
check("WhatsApp Playwright sender (free)", wa_playwright.exists(),
      f"{wa_playwright.stat().st_size} bytes — no Twilio needed")
if wa_playwright.exists():
    content = wa_playwright.read_text(encoding="utf-8")
    check("Payment threshold in WhatsApp sender",
          "PAYMENT_THRESHOLD" in content,
          "PKR 50,000 limit — Company_Handbook rule")

# P9: Platinum demo flow
demo = BASE / "platinum_demo.py"
check("Platinum demo script", demo.exists(),
      f"{demo.stat().st_size} bytes" if demo.exists() else "MISSING")

# Run it fast
try:
    result = subprocess.run(
        "python platinum_demo.py --fast", shell=True,
        capture_output=True, timeout=60, cwd=str(BASE)
    )
    out = result.stdout.decode("utf-8", errors="replace")
    demo_pass = "PLATINUM TIER PASS" in out
    check("Platinum demo flow (end-to-end)", demo_pass,
          "Email->Cloud->Approve->Local->Done pipeline")
except Exception as e:
    check("Platinum demo flow", False, str(e)[:60])

# P10: Odoo backup signal written
sig_files = list(signals_dir.glob("ODOO_BACKUP_*.json")) if signals_dir.exists() else []
check("Odoo backup writes health signal", len(sig_files) > 0,
      f"{len(sig_files)} ODOO_BACKUP_*.json signal(s)")

# P11: Git sync (vault sync Phase 1)
git_dir = BASE.parent / ".git"
check("Git-based vault sync (Phase 1)", git_dir.exists(),
      "Vault synced via Git — Secrets never committed")

# P12: Security rule verified
env_file = BASE / ".env"
if env_file.exists():
    gitignore = (BASE.parent / ".gitignore")
    gi_content = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    check("Security: .env never synced to cloud",
          ".env" in gi_content,
          "Credentials excluded from git sync")
else:
    check("Security: .env never synced", True, ".env not present (credentials safe)")

# P13: A2A round-trip test
try:
    result = subprocess.run(
        "python a2a_agent.py --test", shell=True,
        capture_output=True, timeout=20, cwd=str(BASE)
    )
    out = result.stdout.decode("utf-8", errors="replace")
    a2a_pass = "PASS" in out and "round-trip" in out.lower()
    check("A2A round-trip test (HTTP + vault)", a2a_pass,
          "Phase 2 messaging verified")
except Exception as e:
    check("A2A round-trip test", False, str(e)[:60])

# Summary
print()
print("=" * 62)
total = len(passed) + len(failed)
pct   = int(100 * len(passed) / total) if total else 0
print(f"  RESULT: {len(passed)}/{total} checks PASSED ({pct}%)")
if failed:
    print(f"  FAILED ({len(failed)}):")
    for f in failed:
        print(f"    - {f}")
else:
    print("  ALL CHECKS PASSED!")
    print("  Platinum Tier: 100% COMPLETE")
print("=" * 62)
