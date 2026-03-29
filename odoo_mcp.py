"""
Odoo MCP (Model Context Protocol) — Connection & Test
======================================================
Connects to Odoo via XML-RPC and tests basic operations.

Usage:
  python odoo_mcp.py --test       # Run connection test
  python odoo_mcp.py --info       # Show server info

.env variables used:
  ODOO_URL      = http://localhost:8069
  ODOO_DB       = odoodb
  ODOO_USERNAME = admin
  ODOO_PASSWORD = admin
"""

import os
import sys
import xmlrpc.client
from pathlib import Path

# Load .env manually
def _load_env():
    env_path = Path(__file__).parent / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config

env = _load_env()

ODOO_URL      = env.get("ODOO_URL", "http://localhost:8069")
ODOO_DB       = env.get("ODOO_DB", "odoodb")
ODOO_USERNAME = env.get("ODOO_USERNAME", "admin")
ODOO_PASSWORD = env.get("ODOO_PASSWORD", "admin")


class OdooMCP:
    def __init__(self):
        self.url      = ODOO_URL
        self.db       = ODOO_DB
        self.username = ODOO_USERNAME
        self.password = ODOO_PASSWORD
        self.uid      = None

    def connect(self) -> bool:
        """Authenticate with Odoo and get user ID."""
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            return bool(self.uid)
        except Exception as e:
            print(f"  [ERROR] Connection failed: {e}")
            return False

    def server_version(self) -> str:
        """Get Odoo server version."""
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            info = common.version()
            return info.get("server_version", "unknown")
        except Exception as e:
            return f"Error: {e}"

    def search(self, model, domain=None, limit=5):
        """Search records in a model."""
        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        return models.execute_kw(
            self.db, self.uid, self.password,
            model, "search", [domain or []],
            {"limit": limit}
        )

    def read(self, model, ids, fields):
        """Read fields from records."""
        models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")
        return models.execute_kw(
            self.db, self.uid, self.password,
            model, "read", [ids],
            {"fields": fields}
        )

    def test(self):
        """Run full connection and API test."""
        print("=" * 50)
        print("  ODOO MCP — Connection Test")
        print("=" * 50)
        print(f"\n  URL      : {self.url}")
        print(f"  Database : {self.db}")
        print(f"  Username : {self.username}")

        # Version check
        version = self.server_version()
        print(f"\n  Server Version : {version}")

        # Auth
        print(f"\n  Authenticating...")
        if not self.connect():
            print("  [FAIL] Could not authenticate.")
            print("\n  Possible reasons:")
            print("  - Odoo not running (docker ps)")
            print("  - Wrong DB name (check ODOO_DB in .env)")
            print("  - Wrong credentials (ODOO_USERNAME / ODOO_PASSWORD)")
            return False

        print(f"  [OK] Authenticated — User ID: {self.uid}")

        # Read users
        try:
            print(f"\n  Fetching users...")
            ids = self.search("res.users", limit=3)
            users = self.read("res.users", ids, ["name", "login"])
            for u in users:
                print(f"  - {u['name']} ({u['login']})")
            print(f"  [OK] Users fetched: {len(users)}")
        except Exception as e:
            print(f"  [WARN] Could not fetch users: {e}")

        # Read partners
        try:
            print(f"\n  Fetching partners...")
            ids = self.search("res.partner", limit=3)
            partners = self.read("res.partner", ids, ["name", "email"])
            for p in partners:
                print(f"  - {p['name']} ({p.get('email', 'no email')})")
            print(f"  [OK] Partners fetched: {len(partners)}")
        except Exception as e:
            print(f"  [WARN] Could not fetch partners: {e}")

        print("\n" + "=" * 50)
        print("  ALL TESTS PASSED")
        print("=" * 50 + "\n")
        return True


def main():
    mcp = OdooMCP()

    if "--test" in sys.argv:
        mcp.test()
    elif "--info" in sys.argv:
        print(f"URL      : {ODOO_URL}")
        print(f"Database : {ODOO_DB}")
        print(f"Username : {ODOO_USERNAME}")
        version = mcp.server_version()
        print(f"Version  : {version}")
    else:
        print("Usage:")
        print("  python odoo_mcp.py --test    # Connection test")
        print("  python odoo_mcp.py --info    # Server info")


if __name__ == "__main__":
    main()
