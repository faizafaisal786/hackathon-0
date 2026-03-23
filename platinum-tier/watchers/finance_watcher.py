"""
finance_watcher.py — Bank/finance transaction watcher for Gold Tier.

Monitors financial data sources and deposits transaction summaries,
alerts, and anomalies into the vault for Claude to analyze.

Supported data sources:
    1. CSV file drop (manual export from bank, auto-detected)
    2. Odoo XML-RPC API (live data when Odoo is configured)
    3. Generic JSON transaction feed (for custom bank API integrations)

Environment variables (via .env):
    VAULT_PATH              — Absolute path to vault root
    FINANCE_SOURCE          — "csv"|"odoo"|"json" (default: csv)
    FINANCE_CSV_DROP        — Folder to watch for CSV bank exports
    ODOO_URL                — Odoo instance URL (e.g. http://localhost:8069)
    ODOO_DB                 — Odoo database name
    ODOO_USERNAME           — Odoo username
    ODOO_PASSWORD           — Odoo password (env only)
    FINANCE_ALERT_THRESHOLD — Flag transactions above this amount (default: 500)
    POLL_INTERVAL           — Seconds between checks (default: 3600 = 1 hour)
    DRY_RUN                 — If "true", log but don't write files
"""

import csv
import json
import os
import re
import xmlrpc.client
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from base_watcher import BaseWatcher

load_dotenv()

ALERT_THRESHOLD = float(os.getenv("FINANCE_ALERT_THRESHOLD", "500"))


class Transaction:
    """Value object for a financial transaction."""

    def __init__(
        self,
        txn_id: str,
        date: str,
        description: str,
        amount: float,
        currency: str = "USD",
        category: str = "uncategorized",
        account: str = "",
        source: str = "unknown",
    ):
        self.id = txn_id
        self.date = date
        self.description = description
        self.amount = amount
        self.currency = currency
        self.category = category
        self.account = account
        self.source = source
        self.is_credit = amount > 0
        self.is_debit = amount < 0
        self.is_large = abs(amount) >= ALERT_THRESHOLD


class FinanceWatcher(BaseWatcher):
    """
    Monitors financial data sources and deposits summaries and alerts in vault.

    On each poll cycle:
    1. Reads new transactions from configured source
    2. Flags large transactions, overdue invoices, and anomalies
    3. Writes transaction summaries to vault Inbox/
    4. Updates Accounting/ folder with running ledger
    """

    def __init__(self, vault_path: str, **kwargs):
        super().__init__(vault_path, **kwargs)
        self.source = os.getenv("FINANCE_SOURCE", "csv")
        self.csv_drop = Path(
            os.getenv("FINANCE_CSV_DROP", str(Path.home() / "Desktop" / "bank_exports"))
        )
        self.odoo_url = os.getenv("ODOO_URL", "")
        self.odoo_db = os.getenv("ODOO_DB", "")
        self.odoo_user = os.getenv("ODOO_USERNAME", "")
        self.odoo_pass = os.getenv("ODOO_PASSWORD", "")
        self._seen_ids: set[str] = self._load_seen_ids()
        self._odoo_uid: Optional[int] = None
        self.accounting_path = Path(vault_path) / "Accounting"
        self.accounting_path.mkdir(parents=True, exist_ok=True)

    def on_start(self) -> None:
        if self.source == "odoo":
            self._authenticate_odoo()
        elif self.source == "csv":
            self.csv_drop.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Watching CSV drop folder: {self.csv_drop}")

    def _authenticate_odoo(self) -> None:
        """Authenticate with Odoo XML-RPC API."""
        if not all([self.odoo_url, self.odoo_db, self.odoo_user, self.odoo_pass]):
            self.logger.warning(
                "Odoo credentials incomplete. Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD."
            )
            return
        try:
            common = xmlrpc.client.ServerProxy(f"{self.odoo_url}/xmlrpc/2/common")
            self._odoo_uid = common.authenticate(
                self.odoo_db, self.odoo_user, self.odoo_pass, {}
            )
            self.logger.info(f"Odoo authenticated. UID: {self._odoo_uid}")
        except Exception as e:
            self.logger.error(f"Odoo authentication failed: {e}")

    def _odoo_call(self, model: str, method: str, args: list, kwargs: dict = None) -> Any:
        """Execute an Odoo XML-RPC call."""
        models = xmlrpc.client.ServerProxy(f"{self.odoo_url}/xmlrpc/2/object")
        return models.execute_kw(
            self.odoo_db, self._odoo_uid, self.odoo_pass,
            model, method, args, kwargs or {}
        )

    def poll(self) -> list[Transaction]:
        """Fetch new financial transactions from configured source."""
        if self.source == "csv":
            return self._poll_csv()
        elif self.source == "odoo":
            return self._poll_odoo()
        elif self.source == "json":
            return self._poll_json()
        return []

    def _poll_csv(self) -> list[Transaction]:
        """Read new CSV files from the bank export drop folder."""
        transactions = []
        if not self.csv_drop.exists():
            return []

        for csv_file in self.csv_drop.glob("*.csv"):
            if csv_file.name in self._seen_ids:
                continue

            self.logger.info(f"Processing CSV: {csv_file.name}")
            try:
                txns = self._parse_csv(csv_file)
                transactions.extend(txns)
                self._seen_ids.add(csv_file.name)
                # Archive processed CSV
                if not self.dry_run:
                    archive = self.csv_drop / "processed"
                    archive.mkdir(exist_ok=True)
                    csv_file.rename(archive / csv_file.name)
            except Exception as e:
                self.logger.error(f"CSV parse error {csv_file.name}: {e}")

        return transactions

    def _parse_csv(self, path: Path) -> list[Transaction]:
        """Parse a bank CSV export. Handles common bank CSV formats."""
        transactions = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            # Try to sniff the delimiter
            sample = f.read(1024)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except csv.Error:
                dialect = csv.excel

            reader = csv.DictReader(f, dialect=dialect)
            for i, row in enumerate(reader):
                # Normalize common bank CSV column names
                date_val = (
                    row.get("Date") or row.get("date") or
                    row.get("Transaction Date") or row.get("Posting Date", "")
                ).strip()
                desc = (
                    row.get("Description") or row.get("Narration") or
                    row.get("Memo") or row.get("Details", "")
                ).strip()
                amount_str = (
                    row.get("Amount") or row.get("Debit") or
                    row.get("Credit") or row.get("Transaction Amount", "0")
                ).strip().replace(",", "").replace("$", "")

                try:
                    amount = float(amount_str)
                except ValueError:
                    continue

                txn_id = f"{path.stem}_{i}"
                transactions.append(Transaction(
                    txn_id=txn_id,
                    date=date_val,
                    description=desc,
                    amount=amount,
                    source="csv",
                    account=path.stem,
                ))

        return transactions

    def _poll_odoo(self) -> list[Transaction]:
        """Read recent account moves from Odoo."""
        if not self._odoo_uid:
            self.logger.warning("Odoo not authenticated. Skipping poll.")
            return []

        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        try:
            moves = self._odoo_call(
                "account.move",
                "search_read",
                [[
                    ["state", "=", "posted"],
                    ["date", ">=", since],
                ]],
                {
                    "fields": ["name", "date", "amount_total", "move_type", "partner_id", "state"],
                    "limit": 50,
                }
            )
        except Exception as e:
            raise RuntimeError(f"Odoo poll failed: {e}") from e

        transactions = []
        for move in moves:
            move_id = str(move["id"])
            if move_id in self._seen_ids:
                continue

            amount = move.get("amount_total", 0)
            move_type = move.get("move_type", "")
            if move_type in ("in_invoice", "in_receipt"):
                amount = -abs(amount)  # Expense

            partner = move.get("partner_id")
            partner_name = partner[1] if isinstance(partner, list) else "Unknown"

            txn = Transaction(
                txn_id=move_id,
                date=str(move.get("date", "")),
                description=f"{move.get('name', '')} — {partner_name}",
                amount=amount,
                source="odoo",
                category=move_type,
                account="odoo",
            )
            transactions.append(txn)
            self._seen_ids.add(move_id)

        self._save_seen_ids()
        return transactions

    def _poll_json(self) -> list[Transaction]:
        """Read transactions from a JSON file drop (custom bank API)."""
        json_drop = Path(os.getenv("FINANCE_JSON_DROP", str(self.csv_drop)))
        transactions = []
        for json_file in json_drop.glob("*.json"):
            if json_file.name in self._seen_ids:
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                txns_raw = data if isinstance(data, list) else data.get("transactions", [])
                for i, t in enumerate(txns_raw):
                    transactions.append(Transaction(
                        txn_id=f"{json_file.stem}_{i}",
                        date=str(t.get("date", "")),
                        description=t.get("description", ""),
                        amount=float(t.get("amount", 0)),
                        currency=t.get("currency", "USD"),
                        category=t.get("category", "uncategorized"),
                        source="json",
                    ))
                self._seen_ids.add(json_file.name)
            except Exception as e:
                self.logger.error(f"JSON parse error {json_file.name}: {e}")

        return transactions

    def process_item(self, item: Transaction) -> Optional[str]:
        """Convert a transaction to vault markdown. Only write notable transactions."""
        # Update running ledger in Accounting/
        self._append_to_ledger(item)

        # Only create Inbox items for notable transactions
        if not item.is_large and item.source != "odoo":
            return None

        priority = "P0" if abs(item.amount) > ALERT_THRESHOLD * 10 else "P1"
        direction = "CREDIT (+)" if item.is_credit else "DEBIT (-)"

        return f"""---
source: finance
transaction_id: "{item.id}"
txn_date: "{item.date}"
amount: {item.amount}
currency: {item.currency}
category: {item.category}
account: "{item.account}"
finance_source: {item.source}
received: {datetime.now().isoformat()}
priority: {priority}
tags: [inbox, finance, {'large-transaction' if item.is_large else 'odoo'}]
---

# Finance Alert: {direction} {item.currency} {abs(item.amount):,.2f}

**Date:** {item.date}
**Description:** {item.description}
**Amount:** {direction} {item.currency} {abs(item.amount):,.2f}
**Category:** {item.category}
**Account/Source:** {item.account or item.source}

---

## Why This Was Flagged

{"Large transaction: amount exceeds alert threshold of " + str(ALERT_THRESHOLD) if item.is_large else "Odoo accounting entry requiring review"}

---

## Action Required

> Claude: Review this financial transaction per Company_Handbook.md.
> - For large unexpected expenses: create P1 task, flag in CEO briefing
> - For large revenue: update Business_Goals.md KPIs
> - For Odoo invoices: check if payment reminder is needed
> - Always add to Accounting/ summary file
"""

    def _append_to_ledger(self, txn: Transaction) -> None:
        """Append transaction to running monthly ledger in Accounting/."""
        month = datetime.now().strftime("%Y-%m")
        ledger_file = self.accounting_path / f"Ledger_{month}.md"

        if not self.dry_run:
            if not ledger_file.exists():
                ledger_file.write_text(
                    f"# Transaction Ledger — {month}\n\n"
                    "| Date | Description | Amount | Category | Source |\n"
                    "|---|---|---|---|---|\n",
                    encoding="utf-8",
                )
            with open(ledger_file, "a", encoding="utf-8") as f:
                sign = "+" if txn.is_credit else ""
                f.write(
                    f"| {txn.date} | {txn.description[:60]} | "
                    f"{sign}{txn.amount:,.2f} {txn.currency} | "
                    f"{txn.category} | {txn.source} |\n"
                )

    def get_item_filename(self, item: Transaction) -> str:
        date_prefix = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_desc = re.sub(r'[\\/*?:"<>| ]', "_", item.description)[:30] if hasattr(item, 'description') else "txn"
        return f"finance_{date_prefix}_{item.id}_{safe_desc}.md"

    def _load_seen_ids(self) -> set[str]:
        state_file = self.logs_path / "finance_seen_ids.json"
        if state_file.exists():
            try:
                return set(json.loads(state_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return set()

    def _save_seen_ids(self) -> None:
        state_file = self.logs_path / "finance_seen_ids.json"
        if not self.dry_run:
            state_file.write_text(json.dumps(list(self._seen_ids)[-10000:]))


if __name__ == "__main__":
    vault = os.getenv("VAULT_PATH", str(Path(__file__).parent.parent))
    interval = int(os.getenv("POLL_INTERVAL", "3600"))
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    watcher = FinanceWatcher(
        vault_path=vault,
        poll_interval_seconds=interval,
        dry_run=dry_run,
    )
    watcher.run()
