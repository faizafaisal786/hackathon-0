"""
Odoo MCP Server — Gold Tier
=============================
Dedicated MCP server for Odoo Community accounting integration.
Connects to a self-hosted Odoo 19+ instance via JSON-RPC APIs.

This is a SEPARATE MCP server from mcp_server.py (which handles
communication). Together they satisfy the Gold Tier requirement of
"Multiple MCP servers for different action types."

Tools exposed:
  get_invoices           -- Fetch customer invoices (with filters)
  create_invoice         -- Create a new customer invoice
  get_customers          -- List customers/partners
  get_products           -- List products/services
  get_accounting_summary -- Weekly revenue, expenses, top clients
  get_payments           -- Fetch payment records
  create_customer        -- Create a new customer/partner
  check_connection       -- Verify Odoo connectivity

Required .env variables:
  ODOO_URL=http://localhost:8069
  ODOO_DB=your_database_name
  ODOO_USERNAME=admin
  ODOO_PASSWORD=admin

Odoo Setup (Docker — one command):
  docker run -d -p 8069:8069 --name odoo19 \\
    -e HOST=db -e USER=odoo -e PASSWORD=odoo \\
    odoo:19

Usage:
  python odoo_mcp.py              # Start MCP server (stdio)
  python odoo_mcp.py --test       # Diagnostic test (no server started)
  python odoo_mcp.py --demo       # Demo mode (no Odoo needed)

Install dependencies:
  pip install fastmcp python-dotenv
"""

import sys
import json
import os
import xmlrpc.client
from datetime import datetime, timedelta
from pathlib import Path

BASE  = Path(__file__).parent
VAULT = BASE / "AI_Employee_Vault"
LOGS  = VAULT / "Logs"

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=True)
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════════
# ODOO JSON-RPC CLIENT
# Uses Python's built-in xmlrpc.client — no extra package needed.
# Odoo exposes both XML-RPC and JSON-RPC; we use XML-RPC (standard library).
# ══════════════════════════════════════════════════════════════════════════════

class OdooClient:
    """
    Lightweight Odoo client using XML-RPC (Odoo's standard API).
    Compatible with Odoo 16, 17, 18, 19+.

    Odoo API endpoints:
      /xmlrpc/2/common  → authenticate
      /xmlrpc/2/object  → CRUD operations
    """

    def __init__(self, url: str, db: str, username: str, password: str):
        self.url      = url.rstrip("/")
        self.db       = db
        self.username = username
        self.password = password
        self.uid      = None
        self._common  = None
        self._models  = None

    def _get_common(self):
        if self._common is None:
            self._common = xmlrpc.client.ServerProxy(
                f"{self.url}/xmlrpc/2/common",
                allow_none=True,
            )
        return self._common

    def _get_models(self):
        if self._models is None:
            self._models = xmlrpc.client.ServerProxy(
                f"{self.url}/xmlrpc/2/object",
                allow_none=True,
            )
        return self._models

    def authenticate(self) -> int:
        """Authenticate and return uid. Raises on failure."""
        common = self._get_common()
        uid = common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            raise ConnectionError(
                f"Odoo authentication failed for user '{self.username}' "
                f"on database '{self.db}' at {self.url}"
            )
        self.uid = uid
        return uid

    def _ensure_authenticated(self):
        if self.uid is None:
            self.authenticate()

    def search_read(self, model: str, domain: list, fields: list,
                    limit: int = 50, order: str = "") -> list:
        """Search and read records from Odoo model."""
        self._ensure_authenticated()
        kwargs = {"limit": limit}
        if order:
            kwargs["order"] = order
        return self._get_models().execute_kw(
            self.db, self.uid, self.password,
            model, "search_read",
            [domain], {"fields": fields, **kwargs},
        )

    def create(self, model: str, values: dict) -> int:
        """Create a record. Returns the new record ID."""
        self._ensure_authenticated()
        return self._get_models().execute_kw(
            self.db, self.uid, self.password,
            model, "create",
            [values],
        )

    def write(self, model: str, ids: list, values: dict) -> bool:
        """Update existing records."""
        self._ensure_authenticated()
        return self._get_models().execute_kw(
            self.db, self.uid, self.password,
            model, "write",
            [ids, values],
        )

    def version(self) -> dict:
        """Return Odoo server version info."""
        return self._get_common().version()


# ══════════════════════════════════════════════════════════════════════════════
# CREDENTIAL LOADING
# ══════════════════════════════════════════════════════════════════════════════

def _load_credentials() -> dict:
    return {
        "url":      os.getenv("ODOO_URL",      "http://localhost:8069"),
        "db":       os.getenv("ODOO_DB",       ""),
        "username": os.getenv("ODOO_USERNAME", "admin"),
        "password": os.getenv("ODOO_PASSWORD", "admin"),
    }


def _credentials_configured(creds: dict) -> bool:
    """Check if Odoo credentials are properly set."""
    db = creds.get("db", "")
    if not db or "your_" in db:
        return False
    return True


def _get_client() -> OdooClient:
    """Create and return an authenticated OdooClient."""
    creds = _load_credentials()
    return OdooClient(
        url      = creds["url"],
        db       = creds["db"],
        username = creds["username"],
        password = creds["password"],
    )


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def _log(event: str, details: str, success: bool = True):
    """Append event to today's Odoo MCP log."""
    LOGS.mkdir(parents=True, exist_ok=True)
    today    = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS / f"odoo_mcp_{today}.json"

    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []

    entries.append({
        "event":     event,
        "details":   details,
        "success":   success,
        "timestamp": datetime.now().isoformat(),
    })
    log_file.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════════════════════
# DEMO DATA (when Odoo is not running)
# ══════════════════════════════════════════════════════════════════════════════

DEMO_INVOICES = [
    {"id": 1, "name": "INV/2026/00001", "partner_id": [1, "Ahmed Khan"],
     "amount_total": 15000.0, "state": "posted", "invoice_date": "2026-03-01",
     "invoice_date_due": "2026-03-31", "payment_state": "not_paid"},
    {"id": 2, "name": "INV/2026/00002", "partner_id": [2, "Sara Ali"],
     "amount_total": 8500.0, "state": "posted", "invoice_date": "2026-03-05",
     "invoice_date_due": "2026-04-05", "payment_state": "paid"},
    {"id": 3, "name": "INV/2026/00003", "partner_id": [3, "Tech Solutions PK"],
     "amount_total": 32000.0, "state": "draft", "invoice_date": "2026-03-10",
     "invoice_date_due": "2026-04-10", "payment_state": "not_paid"},
]

DEMO_CUSTOMERS = [
    {"id": 1, "name": "Ahmed Khan",        "email": "ahmed@example.com",  "phone": "+92300111"},
    {"id": 2, "name": "Sara Ali",          "email": "sara@example.com",   "phone": "+92301222"},
    {"id": 3, "name": "Tech Solutions PK", "email": "info@techpk.com",    "phone": "+92321333"},
]

DEMO_PAYMENTS = [
    {"id": 1, "name": "BNK1/2026/00001", "partner_id": [2, "Sara Ali"],
     "amount": 8500.0, "date": "2026-03-08", "state": "posted",
     "payment_type": "inbound"},
]


# ══════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _tool_check_connection() -> dict:
    """Verify Odoo server is reachable and credentials work."""
    creds = _load_credentials()

    if not _credentials_configured(creds):
        return {
            "success":  True,
            "mode":     "demo",
            "message":  "DEMO mode active — all tools working with sample data",
            "setup":    "Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD in .env for live mode",
        }

    try:
        client  = _get_client()
        version = client.version()
        uid     = client.authenticate()
        return {
            "success":        True,
            "mode":           "live",
            "odoo_version":   version.get("server_version", "unknown"),
            "uid":            uid,
            "url":            creds["url"],
            "db":             creds["db"],
            "username":       creds["username"],
            "message":        "Odoo connection successful",
        }
    except Exception as e:
        return {
            "success": False,
            "mode":    "error",
            "error":   str(e),
            "tip":     "Is Odoo running? Try: docker run -d -p 8069:8069 odoo:19",
        }


def _tool_get_invoices(state: str = "all", limit: int = 20) -> dict:
    """
    Fetch customer invoices from Odoo.
    state: 'all' | 'draft' | 'posted' | 'cancel'
    """
    creds = _load_credentials()

    # Demo mode
    if not _credentials_configured(creds):
        invoices = DEMO_INVOICES
        if state != "all":
            invoices = [i for i in invoices if i["state"] == state]
        return {
            "success":  True,
            "mode":     "demo",
            "count":    len(invoices),
            "invoices": invoices[:limit],
        }

    try:
        client = _get_client()
        domain = [("move_type", "=", "out_invoice")]
        if state != "all":
            domain.append(("state", "=", state))

        records = client.search_read(
            model  = "account.move",
            domain = domain,
            fields = [
                "name", "partner_id", "amount_total",
                "state", "invoice_date", "invoice_date_due",
                "payment_state", "ref",
            ],
            limit  = limit,
            order  = "invoice_date desc",
        )

        _log("GET_INVOICES", f"state={state} count={len(records)}")
        return {
            "success":  True,
            "mode":     "live",
            "count":    len(records),
            "invoices": records,
        }
    except Exception as e:
        _log("GET_INVOICES_ERROR", str(e), success=False)
        return {"success": False, "error": str(e)}


def _tool_create_invoice(
    customer_name: str,
    amount: float,
    description: str,
    due_days: int = 30,
) -> dict:
    """Create a new customer invoice in Odoo."""
    creds = _load_credentials()

    # Demo mode
    if not _credentials_configured(creds):
        inv_num = f"INV/2026/DEMO_{datetime.now().strftime('%H%M%S')}"
        return {
            "success":      True,
            "mode":         "demo",
            "invoice_id":   999,
            "invoice_name": inv_num,
            "customer":     customer_name,
            "amount":       amount,
            "due_date":     (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d"),
            "message":      f"Demo invoice {inv_num} created for {customer_name}",
        }

    try:
        client = _get_client()

        # Find partner by name
        partners = client.search_read(
            model  = "res.partner",
            domain = [("name", "ilike", customer_name)],
            fields = ["id", "name"],
            limit  = 1,
        )
        if not partners:
            return {
                "success": False,
                "error":   f"Customer '{customer_name}' not found in Odoo. Create them first.",
            }

        partner_id  = partners[0]["id"]
        today       = datetime.now().strftime("%Y-%m-%d")
        due_date    = (datetime.now() + timedelta(days=due_days)).strftime("%Y-%m-%d")

        invoice_vals = {
            "move_type":           "out_invoice",
            "partner_id":          partner_id,
            "invoice_date":        today,
            "invoice_date_due":    due_date,
            "invoice_line_ids": [(0, 0, {
                "name":       description,
                "quantity":   1.0,
                "price_unit": amount,
            })],
        }

        invoice_id = client.create("account.move", invoice_vals)

        # Fetch the created invoice name
        created = client.search_read(
            model  = "account.move",
            domain = [("id", "=", invoice_id)],
            fields = ["name", "amount_total"],
            limit  = 1,
        )
        inv_name = created[0]["name"] if created else f"ID:{invoice_id}"

        _log("CREATE_INVOICE", f"customer={customer_name} amount={amount} id={invoice_id}")
        return {
            "success":      True,
            "mode":         "live",
            "invoice_id":   invoice_id,
            "invoice_name": inv_name,
            "customer":     customer_name,
            "partner_id":   partner_id,
            "amount":       amount,
            "due_date":     due_date,
            "message":      f"Invoice {inv_name} created for {customer_name}",
        }
    except Exception as e:
        _log("CREATE_INVOICE_ERROR", str(e), success=False)
        return {"success": False, "error": str(e)}


def _tool_get_customers(search: str = "", limit: int = 20) -> dict:
    """List customers/partners from Odoo."""
    creds = _load_credentials()

    if not _credentials_configured(creds):
        customers = DEMO_CUSTOMERS
        if search:
            customers = [c for c in customers
                         if search.lower() in c["name"].lower()]
        return {
            "success":   True,
            "mode":      "demo",
            "count":     len(customers),
            "customers": customers[:limit],
        }

    try:
        client = _get_client()
        domain = [("customer_rank", ">", 0)]
        if search:
            domain.append(("name", "ilike", search))

        records = client.search_read(
            model  = "res.partner",
            domain = domain,
            fields = ["name", "email", "phone", "city", "customer_rank", "vat"],
            limit  = limit,
            order  = "name asc",
        )

        _log("GET_CUSTOMERS", f"search={search!r} count={len(records)}")
        return {
            "success":   True,
            "mode":      "live",
            "count":     len(records),
            "customers": records,
        }
    except Exception as e:
        _log("GET_CUSTOMERS_ERROR", str(e), success=False)
        return {"success": False, "error": str(e)}


def _tool_get_products(search: str = "", limit: int = 20) -> dict:
    """List products/services from Odoo."""
    creds = _load_credentials()

    if not _credentials_configured(creds):
        return {
            "success":  True,
            "mode":     "demo",
            "count":    2,
            "products": [
                {"id": 1, "name": "AI Consulting Service", "list_price": 5000.0,
                 "type": "service", "active": True},
                {"id": 2, "name": "Software Development",  "list_price": 8000.0,
                 "type": "service", "active": True},
            ],
        }

    try:
        client = _get_client()
        domain = [("active", "=", True), ("sale_ok", "=", True)]
        if search:
            domain.append(("name", "ilike", search))

        records = client.search_read(
            model  = "product.template",
            domain = domain,
            fields = ["name", "list_price", "type", "active", "description_sale"],
            limit  = limit,
            order  = "name asc",
        )

        _log("GET_PRODUCTS", f"search={search!r} count={len(records)}")
        return {
            "success":  True,
            "mode":     "live",
            "count":    len(records),
            "products": records,
        }
    except Exception as e:
        _log("GET_PRODUCTS_ERROR", str(e), success=False)
        return {"success": False, "error": str(e)}


def _tool_get_payments(limit: int = 20) -> dict:
    """Fetch recent payment records from Odoo."""
    creds = _load_credentials()

    if not _credentials_configured(creds):
        return {
            "success":  True,
            "mode":     "demo",
            "count":    len(DEMO_PAYMENTS),
            "payments": DEMO_PAYMENTS,
        }

    try:
        client = _get_client()
        records = client.search_read(
            model  = "account.payment",
            domain = [("state", "=", "posted"), ("payment_type", "=", "inbound")],
            fields = ["name", "partner_id", "amount", "date", "state", "payment_type"],
            limit  = limit,
            order  = "date desc",
        )

        _log("GET_PAYMENTS", f"count={len(records)}")
        return {
            "success":  True,
            "mode":     "live",
            "count":    len(records),
            "payments": records,
        }
    except Exception as e:
        _log("GET_PAYMENTS_ERROR", str(e), success=False)
        return {"success": False, "error": str(e)}


def _tool_create_customer(
    name: str,
    email: str = "",
    phone: str = "",
    city:  str = "",
) -> dict:
    """Create a new customer in Odoo."""
    creds = _load_credentials()

    if not name:
        return {"success": False, "error": "Customer name is required"}

    if not _credentials_configured(creds):
        return {
            "success":     True,
            "mode":        "demo",
            "customer_id": 999,
            "name":        name,
            "email":       email,
            "message":     f"Demo customer '{name}' created",
        }

    try:
        client = _get_client()
        vals = {
            "name":          name,
            "customer_rank": 1,
        }
        if email:
            vals["email"] = email
        if phone:
            vals["phone"] = phone
        if city:
            vals["city"] = city

        customer_id = client.create("res.partner", vals)

        _log("CREATE_CUSTOMER", f"name={name} id={customer_id}")
        return {
            "success":     True,
            "mode":        "live",
            "customer_id": customer_id,
            "name":        name,
            "email":       email,
            "phone":       phone,
            "message":     f"Customer '{name}' created with ID {customer_id}",
        }
    except Exception as e:
        _log("CREATE_CUSTOMER_ERROR", str(e), success=False)
        return {"success": False, "error": str(e)}


def _tool_get_accounting_summary(days: int = 7) -> dict:
    """
    Generate a weekly accounting summary:
    total invoiced, total paid, outstanding, top clients.
    Used by briefing_generator.py for CEO briefings.
    """
    creds = _load_credentials()

    if not _credentials_configured(creds):
        # Demo summary
        total_invoiced   = sum(i["amount_total"] for i in DEMO_INVOICES)
        total_paid       = sum(p["amount"] for p in DEMO_PAYMENTS)
        outstanding      = total_invoiced - total_paid
        top_clients      = [
            {"name": i["partner_id"][1], "amount": i["amount_total"]}
            for i in sorted(DEMO_INVOICES, key=lambda x: x["amount_total"], reverse=True)[:3]
        ]
        return {
            "success":         True,
            "mode":            "demo",
            "period_days":     days,
            "total_invoiced":  total_invoiced,
            "total_paid":      total_paid,
            "outstanding":     outstanding,
            "invoice_count":   len(DEMO_INVOICES),
            "payment_count":   len(DEMO_PAYMENTS),
            "top_clients":     top_clients,
            "currency":        "PKR",
            "generated_at":    datetime.now().isoformat(),
        }

    try:
        client   = _get_client()
        cutoff   = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        invoices = client.search_read(
            model  = "account.move",
            domain = [
                ("move_type",    "=", "out_invoice"),
                ("state",        "=", "posted"),
                ("invoice_date", ">=", cutoff),
            ],
            fields = ["name", "partner_id", "amount_total", "payment_state"],
            limit  = 200,
        )

        payments = client.search_read(
            model  = "account.payment",
            domain = [
                ("state",        "=", "posted"),
                ("payment_type", "=", "inbound"),
                ("date",         ">=", cutoff),
            ],
            fields = ["name", "partner_id", "amount", "date"],
            limit  = 200,
        )

        total_invoiced = sum(i["amount_total"] for i in invoices)
        total_paid     = sum(p["amount"] for p in payments)
        outstanding    = total_invoiced - total_paid

        # Top 3 clients by invoiced amount
        client_totals = {}
        for inv in invoices:
            partner = inv["partner_id"][1] if isinstance(inv["partner_id"], list) else str(inv["partner_id"])
            client_totals[partner] = client_totals.get(partner, 0) + inv["amount_total"]

        top_clients = sorted(
            [{"name": k, "amount": v} for k, v in client_totals.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:3]

        _log("GET_ACCOUNTING_SUMMARY", f"days={days} invoiced={total_invoiced} paid={total_paid}")
        return {
            "success":        True,
            "mode":           "live",
            "period_days":    days,
            "total_invoiced": total_invoiced,
            "total_paid":     total_paid,
            "outstanding":    outstanding,
            "invoice_count":  len(invoices),
            "payment_count":  len(payments),
            "top_clients":    top_clients,
            "currency":       "PKR",
            "generated_at":   datetime.now().isoformat(),
        }
    except Exception as e:
        _log("GET_ACCOUNTING_SUMMARY_ERROR", str(e), success=False)
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# MCP SERVER
# ══════════════════════════════════════════════════════════════════════════════

def build_mcp_server():
    """Build and return the Odoo FastMCP server."""
    from fastmcp import FastMCP

    mcp = FastMCP(
        name="Odoo Accounting",
        instructions=(
            "Odoo Accounting MCP Server. Provides tools for managing invoices, "
            "customers, products, payments, and generating accounting summaries "
            "from a self-hosted Odoo 19+ instance via JSON-RPC. "
            "Falls back to demo data when Odoo is not configured."
        ),
    )

    # ── Tool 1: Check Connection ─────────────────────────────────────────────

    @mcp.tool()
    def check_odoo_connection() -> str:
        """
        Check if Odoo is reachable and credentials are valid.
        Run this first to verify your Odoo setup.
        """
        return json.dumps(_tool_check_connection(), indent=2)

    # ── Tool 2: Get Invoices ─────────────────────────────────────────────────

    @mcp.tool()
    def get_invoices(state: str = "all", limit: int = 20) -> str:
        """
        Fetch customer invoices from Odoo accounting.

        Args:
            state: Filter by invoice state — 'all', 'draft', 'posted', 'cancel'
            limit: Maximum number of invoices to return (default 20)
        """
        return json.dumps(_tool_get_invoices(state, limit), indent=2, ensure_ascii=False)

    # ── Tool 3: Create Invoice ───────────────────────────────────────────────

    @mcp.tool()
    def create_invoice(
        customer_name: str,
        amount: float,
        description: str,
        due_days: int = 30,
    ) -> str:
        """
        Create a new customer invoice in Odoo.

        Args:
            customer_name: Name of the customer (must exist in Odoo)
            amount:        Invoice amount (in your Odoo currency)
            description:   Line item description / service name
            due_days:      Payment due in N days from today (default 30)
        """
        return json.dumps(
            _tool_create_invoice(customer_name, amount, description, due_days),
            indent=2, ensure_ascii=False,
        )

    # ── Tool 4: Get Customers ────────────────────────────────────────────────

    @mcp.tool()
    def get_customers(search: str = "", limit: int = 20) -> str:
        """
        List customers/partners from Odoo.

        Args:
            search: Optional search term to filter by name
            limit:  Maximum number of customers to return (default 20)
        """
        return json.dumps(_tool_get_customers(search, limit), indent=2, ensure_ascii=False)

    # ── Tool 5: Get Products ─────────────────────────────────────────────────

    @mcp.tool()
    def get_products(search: str = "", limit: int = 20) -> str:
        """
        List products and services available in Odoo.

        Args:
            search: Optional search term to filter by product name
            limit:  Maximum number of products to return (default 20)
        """
        return json.dumps(_tool_get_products(search, limit), indent=2, ensure_ascii=False)

    # ── Tool 6: Get Payments ─────────────────────────────────────────────────

    @mcp.tool()
    def get_payments(limit: int = 20) -> str:
        """
        Fetch recent incoming payment records from Odoo.

        Args:
            limit: Maximum number of payments to return (default 20)
        """
        return json.dumps(_tool_get_payments(limit), indent=2, ensure_ascii=False)

    # ── Tool 7: Create Customer ──────────────────────────────────────────────

    @mcp.tool()
    def create_customer(
        name:  str,
        email: str = "",
        phone: str = "",
        city:  str = "",
    ) -> str:
        """
        Create a new customer in Odoo.

        Args:
            name:  Customer full name (required)
            email: Customer email address (optional)
            phone: Customer phone number (optional)
            city:  Customer city (optional)
        """
        return json.dumps(
            _tool_create_customer(name, email, phone, city),
            indent=2, ensure_ascii=False,
        )

    # ── Tool 8: Accounting Summary ───────────────────────────────────────────

    @mcp.tool()
    def get_accounting_summary(days: int = 7) -> str:
        """
        Generate a weekly accounting summary for CEO briefing.
        Returns: total invoiced, total paid, outstanding, top clients.

        Args:
            days: Number of days to look back (default 7 = last week)
        """
        return json.dumps(
            _tool_get_accounting_summary(days),
            indent=2, ensure_ascii=False,
        )

    return mcp


# ══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC TEST
# ══════════════════════════════════════════════════════════════════════════════

def run_diagnostic():
    """Test all tool functions without starting the MCP server."""
    print("=" * 60)
    print("  ODOO MCP SERVER — Diagnostic Test")
    print("=" * 60)

    creds = _load_credentials()
    print(f"\n  ODOO_URL:      {creds['url']}")
    print(f"  ODOO_DB:       {creds['db'] or '(not set)'}")
    print(f"  ODOO_USERNAME: {creds['username']}")
    print(f"  Configured:    {_credentials_configured(creds)}")

    mode = "LIVE" if _credentials_configured(creds) else "DEMO"
    print(f"  Mode:          {mode}\n")

    tests = [
        ("check_connection",       lambda: _tool_check_connection()),
        ("get_accounting_summary", lambda: _tool_get_accounting_summary(7)),
        ("get_invoices (all)",     lambda: _tool_get_invoices("all", 5)),
        ("get_customers",          lambda: _tool_get_customers("", 5)),
        ("get_products",           lambda: _tool_get_products("", 5)),
        ("get_payments",           lambda: _tool_get_payments(5)),
        ("create_customer (demo)", lambda: _tool_create_customer(
            "Test Customer MCP", "test@example.com", "+923001234567", "Karachi"
        )),
    ]

    passed = 0
    for name, fn in tests:
        try:
            result = fn()
            ok     = result.get("success", False)
            status = "PASS" if ok else "WARN"
            print(f"  [{status}] {name}")

            if name == "get_accounting_summary":
                r = result
                print(f"        Invoiced: {r.get('total_invoiced', 0):,.0f} | "
                      f"Paid: {r.get('total_paid', 0):,.0f} | "
                      f"Outstanding: {r.get('outstanding', 0):,.0f}")
            elif name == "get_invoices (all)":
                print(f"        Invoices found: {result.get('count', 0)}")
            elif name == "get_customers":
                print(f"        Customers found: {result.get('count', 0)}")
            elif name == "check_connection":
                mode = result.get("mode", "demo")
                print(f"        Mode: {mode.upper()} | {result.get('message', '')}")

            if ok:
                passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")

    try:
        from fastmcp import FastMCP
        fastmcp_ok = True
    except ImportError:
        fastmcp_ok = False

    print(f"\n  {'-'*40}")
    print(f"  Results: {passed}/{len(tests)} tests passed")
    print(f"  fastmcp installed: {fastmcp_ok}")
    if not fastmcp_ok:
        print("  -> Run: pip install fastmcp")
    print()
    print("  Odoo setup (Docker):")
    print("  docker run -d -p 8069:8069 --name odoo19 odoo:19")
    print()
    print("  Then add to .env:")
    print("  ODOO_URL=http://localhost:8069")
    print("  ODOO_DB=your_database_name")
    print("  ODOO_USERNAME=admin")
    print("  ODOO_PASSWORD=admin")
    print("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]

    if "--test" in args or "--demo" in args:
        run_diagnostic()
        return

    try:
        from fastmcp import FastMCP
    except ImportError:
        print("[ERROR] fastmcp not installed.")
        print("  Run: pip install fastmcp")
        print()
        print("  To test without MCP: python odoo_mcp.py --test")
        sys.exit(1)

    print("=" * 60)
    print("  ODOO ACCOUNTING MCP SERVER v1.0")
    creds = _load_credentials()
    print(f"  Odoo URL: {creds['url']}")
    print(f"  Database: {creds['db'] or '(not set — demo mode)'}")
    print("  Transport: stdio")
    print("  Tools: 8 registered")
    print("=" * 60)

    mcp = build_mcp_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
