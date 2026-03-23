"""
audit_logic.py — Business Accounting & Subscription Audit
==========================================================
Analyzes bank transactions, detects subscriptions, flags anomalies,
and generates weekly audit reports for the CEO Briefing.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("AuditLogic")

# ─── Subscription Patterns ───────────────────────────────────────────────────

SUBSCRIPTION_PATTERNS: dict[str, str] = {
    "netflix.com": "Netflix",
    "spotify.com": "Spotify",
    "adobe.com": "Adobe Creative Cloud",
    "notion.so": "Notion",
    "slack.com": "Slack",
    "github.com": "GitHub",
    "openai.com": "OpenAI",
    "anthropic.com": "Anthropic (Claude)",
    "aws.amazon.com": "AWS",
    "google.com/cloud": "Google Cloud",
    "digitalocean.com": "DigitalOcean",
    "vercel.com": "Vercel",
    "heroku.com": "Heroku",
    "zoom.us": "Zoom",
    "dropbox.com": "Dropbox",
    "figma.com": "Figma",
    "canva.com": "Canva",
    "hubspot.com": "HubSpot",
    "mailchimp.com": "Mailchimp",
}


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class Transaction:
    date: date
    amount: float  # Positive = income, Negative = expense
    description: str
    category: str = "uncategorized"
    is_subscription: bool = False
    subscription_name: Optional[str] = None

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @property
    def is_income(self) -> bool:
        return self.amount > 0


@dataclass
class AuditReport:
    period_start: date
    period_end: date
    total_income: float = 0.0
    total_expenses: float = 0.0
    subscriptions: list[dict] = field(default_factory=list)
    flagged_items: list[dict] = field(default_factory=list)
    top_expenses: list[dict] = field(default_factory=list)

    @property
    def net(self) -> float:
        return self.total_income + self.total_expenses  # expenses are negative

    @property
    def savings_rate(self) -> float:
        if self.total_income == 0:
            return 0.0
        return (self.net / self.total_income) * 100


# ─── Core Analysis Functions ─────────────────────────────────────────────────

def classify_transaction(tx: Transaction) -> Transaction:
    """Detect if a transaction is a known subscription."""
    desc_lower = tx.description.lower()
    for pattern, name in SUBSCRIPTION_PATTERNS.items():
        if pattern in desc_lower:
            tx.is_subscription = True
            tx.subscription_name = name
            tx.category = "subscription"
            return tx
    # Basic category detection
    if any(k in desc_lower for k in ["salary", "payroll", "freelance", "invoice", "payment received"]):
        tx.category = "income"
    elif any(k in desc_lower for k in ["rent", "mortgage"]):
        tx.category = "housing"
    elif any(k in desc_lower for k in ["food", "restaurant", "cafe", "grocery"]):
        tx.category = "food"
    elif any(k in desc_lower for k in ["uber", "lyft", "taxi", "transport", "fuel"]):
        tx.category = "transport"
    return tx


def analyze_transactions(transactions: list[Transaction]) -> AuditReport:
    """Full audit analysis on a list of transactions."""
    if not transactions:
        return AuditReport(period_start=date.today(), period_end=date.today())

    period_start = min(tx.date for tx in transactions)
    period_end = max(tx.date for tx in transactions)
    report = AuditReport(period_start=period_start, period_end=period_end)

    expense_totals: dict[str, float] = {}

    for tx in transactions:
        tx = classify_transaction(tx)

        if tx.is_income:
            report.total_income += tx.amount
        else:
            report.total_expenses += tx.amount
            key = tx.description[:40]
            expense_totals[key] = expense_totals.get(key, 0) + abs(tx.amount)

        if tx.is_subscription:
            report.subscriptions.append({
                "name": tx.subscription_name,
                "amount": abs(tx.amount),
                "date": tx.date.isoformat(),
            })

        # Flag high-value expenses
        if tx.is_expense and abs(tx.amount) > 500:
            report.flagged_items.append({
                "reason": "High-value expense",
                "description": tx.description,
                "amount": abs(tx.amount),
                "date": tx.date.isoformat(),
            })

    # Top 5 expenses
    report.top_expenses = sorted(
        [{"description": k, "total": v} for k, v in expense_totals.items()],
        key=lambda x: x["total"],
        reverse=True,
    )[:5]

    return report


def detect_unused_subscriptions(
    subscriptions: list[dict], days_threshold: int = 30
) -> list[dict]:
    """Flag subscriptions with no recent usage (placeholder — integrate with app login data)."""
    flagged = []
    cutoff = datetime.now().date() - timedelta(days=days_threshold)

    for sub in subscriptions:
        last_use_str = sub.get("last_login_date")
        if last_use_str:
            last_use = date.fromisoformat(last_use_str)
            if last_use < cutoff:
                flagged.append({
                    **sub,
                    "days_since_use": (datetime.now().date() - last_use).days,
                    "recommendation": "Consider cancelling",
                })
    return flagged


def generate_markdown_report(report: AuditReport, vault_path: Path) -> Path:
    """Write the audit report as a Markdown file in /Briefings."""
    now = datetime.now()
    filename = f"{now.strftime('%Y-%m-%d')}_Weekly_Audit.md"
    output_path = vault_path / "Briefings" / filename

    subscription_table = "\n".join(
        f"| {s['name']} | ${s['amount']:.2f} | {s['date']} |"
        for s in report.subscriptions
    ) or "| _(none detected)_ | — | — |"

    flagged_table = "\n".join(
        f"| {f['description'][:30]} | ${f['amount']:.2f} | {f['reason']} |"
        for f in report.flagged_items
    ) or "| _(none)_ | — | — |"

    content = f"""---
type: weekly_audit
generated: {now.isoformat()}
period_start: {report.period_start.isoformat()}
period_end: {report.period_end.isoformat()}
---

# Weekly Business Audit
**Period**: {report.period_start} → {report.period_end}

## Financial Summary
| Metric | Amount |
|--------|--------|
| Total Income | **${report.total_income:,.2f}** |
| Total Expenses | **${abs(report.total_expenses):,.2f}** |
| Net | **${report.net:,.2f}** |
| Savings Rate | **{report.savings_rate:.1f}%** |

## Subscriptions Detected
| Service | Monthly Cost | Last Charged |
|---------|-------------|--------------|
{subscription_table}

## Flagged Items (Review Required)
| Description | Amount | Reason |
|-------------|--------|--------|
{flagged_table}

## Top 5 Expenses
{chr(10).join(f"{i+1}. {e['description'][:40]} — ${e['total']:.2f}" for i, e in enumerate(report.top_expenses))}

---
*Generated by AI Employee Audit System*
"""
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info(f"Audit report saved: {output_path.name}")
    return output_path
