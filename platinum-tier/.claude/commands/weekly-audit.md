# Skill: Weekly Audit (Platinum)

Full cross-domain weekly business audit — Cloud drafts, Local finalizes.

**Cloud Agent Steps**:
1. Analyze `/Done/` items this week across all domains.
2. Count and categorize by domain (email/social/finance).
3. Get Odoo accounting summary via `odoo-mcp`.
4. Detect subscription anomalies.
5. Identify overdue items.
6. Write draft to `/Plans/WEEKLY_AUDIT_DRAFT_<date>.md`.
7. Write `/Updates/weekly_audit_ready_<date>.md`.

**Local Agent Steps** (after receiving update):
1. Read Cloud's audit draft.
2. Add personal financial data (banking, private info).
3. Compare against `Business_Goals.md` targets.
4. Finalize `/Briefings/YYYY-MM-DD_Weekly_Audit.md`.
5. Update `Dashboard.md`.

Output: `<promise>WEEKLY_AUDIT_COMPLETE</promise>`
