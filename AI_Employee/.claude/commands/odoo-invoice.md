# Agent Skill: Create Odoo Invoice

Create and manage invoices in Odoo Community accounting system.

## Instructions

1. Read task details: client name, amount, items, due date
2. Check `AI_Employee_Vault/Company_Handbook.md` for payment terms
3. Connect to Odoo via `odoo_mcp.py` (JSON-RPC API)
4. Steps:
   - Search for existing customer or create new one
   - Get product/service from Odoo product catalog
   - Create draft invoice with line items
   - Write APPROVAL file to `AI_Employee_Vault/Pending_Approval/local/`
5. After human approval (drag to Approved/ in Obsidian):
   - Confirm (post) the invoice in Odoo
   - Send invoice email to client via `email_sender.py`
   - Log to `AI_Employee_Vault/Logs/odoo_YYYY-MM-DD.json`
6. Move task to `AI_Employee_Vault/Done/`

## Security Rules

- Draft only — never post invoice without human approval
- All payments > PKR 5,000 require CEO approval
- Never store banking credentials in vault

## Usage

```
/odoo-invoice "Ahmed Khan, PKR 15000, AI Automation Services, due 2026-03-25"
/odoo-invoice
```
