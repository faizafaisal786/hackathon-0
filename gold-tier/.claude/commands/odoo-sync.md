# Skill: Odoo Accounting Sync

Sync business data between Obsidian vault and Odoo Community.

**Usage**: `/odoo-sync`

Steps:
1. Use the `odoo-mcp` server tool `get_accounting_summary` — read current A/R and A/P.
2. Use `list_invoices` to get open invoices.
3. Write summary to `/Accounting/Odoo_Snapshot_<date>.md`:

```markdown
---
type: odoo_snapshot
generated: <ISO>
---
# Odoo Accounting Snapshot — <date>
## Summary
| Metric | Amount |
| Accounts Receivable | $X |
| Accounts Payable | $X |
| Net Position | $X |
## Open Invoices (<count>)
<invoice list>
```

4. If any invoice is overdue > 30 days → create alert in `/Needs_Action/`.
5. Update `/Accounting/Current_Month.md` with latest totals.
6. Log sync to `/Logs/`.

**Draft Invoice**: To create a new invoice:
- Use `/request-approval payment` first.
- After approval, use `create_invoice_draft` MCP tool.
- Posting in Odoo always requires approval.

Output: `Odoo sync complete. Snapshot saved.`
