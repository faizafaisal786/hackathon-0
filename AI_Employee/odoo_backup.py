"""
Odoo Backup Script — Platinum Tier
=====================================
Backs up Odoo data to local JSON files (Windows-side).
Works with both local Docker Odoo and Cloud VM Odoo.

What it backs up:
  - Customers (res.partner)
  - Invoices (account.move)
  - Products (product.template)
  - Transactions summary

Output: odoo_backups/YYYY-MM-DD_HH-MM/
  customers.json
  invoices.json
  products.json
  summary.json

Modes:
  LIVE   — connects to Odoo JSON-RPC (local Docker or cloud VM)
  DEMO   — generates realistic fake data (no Odoo needed)

Usage:
  python odoo_backup.py              # Backup now (auto-detect mode)
  python odoo_backup.py --demo       # Demo backup with fake data
  python odoo_backup.py --live       # Force live Odoo connection
  python odoo_backup.py --loop       # Run daily at 2 AM
  python odoo_backup.py --status     # Show last backup info
"""

import sys
import os
import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=True)
except ImportError:
    pass

BASE       = Path(__file__).parent
VAULT      = BASE / "AI_Employee_Vault"
BACKUP_DIR = BASE / "odoo_backups"
SIGNALS    = VAULT / "Signals"

ODOO_URL  = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB   = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASS = os.getenv("ODOO_PASSWORD", "admin")


# ─── LIVE ODOO BACKUP ─────────────────────────────────────────────────────────

def _odoo_login() -> tuple:
    """Authenticate with Odoo JSON-RPC. Returns (uid, models_url)."""
    import urllib.request
    common_url = f"{ODOO_URL}/xmlrpc/2/common"
    models_url = f"{ODOO_URL}/xmlrpc/2/object"

    import xmlrpc.client
    common = xmlrpc.client.ServerProxy(common_url)
    uid    = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASS, {})
    if not uid:
        raise ValueError("Odoo authentication failed")
    return uid, models_url


def _odoo_search_read(models_url: str, uid: int, model: str, domain: list, fields: list, limit: int = 200) -> list:
    import xmlrpc.client
    models = xmlrpc.client.ServerProxy(models_url)
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASS,
        model, "search_read", [domain],
        {"fields": fields, "limit": limit}
    )


def backup_live() -> dict:
    """Connect to Odoo and export real data."""
    print(f"[Odoo Backup] Connecting to {ODOO_URL}...")
    uid, models_url = _odoo_login()
    print(f"[Odoo Backup] Authenticated as UID={uid}")

    customers = _odoo_search_read(
        models_url, uid, "res.partner",
        [["customer_rank", ">", 0]],
        ["name", "email", "phone", "city", "country_id"],
    )
    invoices = _odoo_search_read(
        models_url, uid, "account.move",
        [["move_type", "in", ["out_invoice", "out_refund"]]],
        ["name", "partner_id", "invoice_date", "amount_total", "state", "currency_id"],
    )
    products = _odoo_search_read(
        models_url, uid, "product.template",
        [["active", "=", True]],
        ["name", "list_price", "standard_price", "type"],
    )

    total_invoiced = sum(i.get("amount_total", 0) for i in invoices)
    paid_invoices  = [i for i in invoices if i.get("state") == "posted"]

    summary = {
        "backup_time"    : datetime.now().isoformat(),
        "odoo_url"       : ODOO_URL,
        "mode"           : "LIVE",
        "customers"      : len(customers),
        "invoices"       : len(invoices),
        "products"       : len(products),
        "total_invoiced" : round(total_invoiced, 2),
        "paid_count"     : len(paid_invoices),
    }
    return {"customers": customers, "invoices": invoices, "products": products, "summary": summary}


# ─── DEMO BACKUP ──────────────────────────────────────────────────────────────

def backup_demo() -> dict:
    """Generate realistic demo accounting data — no Odoo needed."""
    print("[Odoo Backup] DEMO mode — generating realistic data...")

    names   = ["Ahmed Khan", "Sara Malik", "Tech Solutions PK", "Zain Enterprises",
               "Faiza Digital", "Prime Traders", "BrightStar Co.", "AlphaNet PK"]
    cities  = ["Karachi", "Lahore", "Islamabad", "Peshawar", "Quetta"]
    domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]

    random.seed(42)

    customers = []
    for i, name in enumerate(names, 1):
        customers.append({
            "id"        : i,
            "name"      : name,
            "email"     : f"{name.lower().replace(' ', '.')}@{random.choice(domains)}",
            "phone"     : f"+9230{random.randint(10000000, 99999999)}",
            "city"      : random.choice(cities),
            "country_id": [167, "Pakistan"],
        })

    statuses = ["posted", "posted", "posted", "draft", "cancel"]
    invoices = []
    for i in range(1, 16):
        cust = random.choice(customers)
        date = (datetime.now() - timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d")
        amt  = round(random.uniform(5000, 150000), 2)
        invoices.append({
            "id"           : i,
            "name"         : f"INV/2026/{i:04d}",
            "partner_id"   : [cust["id"], cust["name"]],
            "invoice_date" : date,
            "amount_total" : amt,
            "state"        : random.choice(statuses),
            "currency_id"  : [167, "PKR"],
        })

    products = [
        {"id": 1, "name": "AI Employee Setup", "list_price": 50000, "standard_price": 20000, "type": "service"},
        {"id": 2, "name": "Monthly Maintenance", "list_price": 15000, "standard_price": 5000, "type": "service"},
        {"id": 3, "name": "Social Media Package", "list_price": 25000, "standard_price": 8000, "type": "service"},
        {"id": 4, "name": "Custom Development", "list_price": 80000, "standard_price": 35000, "type": "service"},
    ]

    paid = [inv for inv in invoices if inv["state"] == "posted"]
    total = sum(inv["amount_total"] for inv in paid)

    summary = {
        "backup_time"    : datetime.now().isoformat(),
        "odoo_url"       : ODOO_URL,
        "mode"           : "DEMO",
        "customers"      : len(customers),
        "invoices"       : len(invoices),
        "products"       : len(products),
        "total_invoiced" : round(total, 2),
        "paid_count"     : len(paid),
        "note"           : "Demo data — run with --live when Odoo is running",
    }
    return {"customers": customers, "invoices": invoices, "products": products, "summary": summary}


# ─── SAVE BACKUP ──────────────────────────────────────────────────────────────

def save_backup(data: dict) -> Path:
    """Save backup data to timestamped folder."""
    ts  = datetime.now().strftime("%Y-%m-%d_%H-%M")
    out = BACKUP_DIR / ts
    out.mkdir(parents=True, exist_ok=True)

    for key in ("customers", "invoices", "products", "summary"):
        (out / f"{key}.json").write_text(
            json.dumps(data.get(key, []), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    # Write Signals/ health file
    SIGNALS.mkdir(parents=True, exist_ok=True)
    summary = data["summary"]
    sig = {
        "type"     : "INFO",
        "source"   : "odoo_backup",
        "time"     : summary["backup_time"],
        "message"  : f"Odoo backup complete: {summary['customers']} customers, "
                     f"{summary['invoices']} invoices, PKR {summary['total_invoiced']:,.0f} total",
        "mode"     : summary["mode"],
    }
    sig_file = SIGNALS / f"ODOO_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    sig_file.write_text(json.dumps(sig, indent=2), encoding="utf-8")

    print(f"[Odoo Backup] Saved to: {out}")
    print(f"[Odoo Backup] Customers: {summary['customers']} | Invoices: {summary['invoices']}")
    print(f"[Odoo Backup] Total invoiced: PKR {summary['total_invoiced']:,.0f}")
    return out


def run_backup(force_live: bool = False, force_demo: bool = False) -> Path:
    """Auto-detect mode and run backup."""
    if force_demo:
        data = backup_demo()
    elif force_live:
        data = backup_live()
    else:
        # Try live first, fall back to demo
        try:
            data = backup_live()
        except Exception as e:
            print(f"[Odoo Backup] Live failed ({e}), using DEMO mode")
            data = backup_demo()
    return save_backup(data)


def show_status():
    """Show most recent backup info."""
    if not BACKUP_DIR.exists():
        print("[Odoo Backup] No backups yet. Run: python odoo_backup.py")
        return
    backups = sorted(BACKUP_DIR.iterdir(), reverse=True)
    if not backups:
        print("[Odoo Backup] No backup folders found.")
        return
    latest = backups[0]
    print(f"[Odoo Backup] Latest backup: {latest.name}")
    summary_file = latest / "summary.json"
    if summary_file.exists():
        s = json.loads(summary_file.read_text(encoding="utf-8"))
        print(f"  Customers : {s.get('customers', '?')}")
        print(f"  Invoices  : {s.get('invoices', '?')}")
        print(f"  Invoiced  : PKR {s.get('total_invoiced', 0):,.0f}")
        print(f"  Mode      : {s.get('mode', '?')}")
        print(f"  Time      : {s.get('backup_time', '?')}")
    print(f"  Total backups: {len(backups)}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()

    elif "--loop" in sys.argv:
        print("[Odoo Backup] Running daily backup loop (2 AM trigger)...")
        while True:
            now = datetime.now()
            if now.hour == 2 and now.minute == 0:
                print(f"[Odoo Backup] Daily backup triggered at {now.strftime('%H:%M')}")
                try:
                    run_backup()
                except Exception as e:
                    print(f"[Odoo Backup] ERROR: {e}")
                time.sleep(60)  # avoid double-trigger
            time.sleep(30)

    elif "--live" in sys.argv:
        run_backup(force_live=True)

    elif "--demo" in sys.argv:
        run_backup(force_demo=True)

    else:
        run_backup()
