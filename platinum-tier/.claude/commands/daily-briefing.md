# Skill: Daily Briefing (Platinum)

Generate morning briefing covering both Cloud and Local domains.

Steps:
1. Read `Dashboard.md`, `Company_Handbook.md`, `Business_Goals.md`.
2. Count all pending items across all domains.
3. Check `/In_Progress/cloud/` and `/In_Progress/local/` for active work.
4. Read Odoo snapshot from `/Accounting/Odoo_Snapshot_*.md` (latest).
5. Check `/Logs/` for last 24h errors from BOTH agents.
6. Write `/Briefings/YYYY-MM-DD_Daily_Briefing.md`:

```
# Daily Briefing — <date>
## System Status (Cloud + Local)
## Pending by Domain (email / social / finance)
## Active Work in Progress
## Finance (Odoo snapshot)
## Completed Yesterday
## Alerts / Errors
## Top 3 Focus Items
```

7. Cloud agent: write to `/Updates/briefing_<date>.md`
   Local agent: update `Dashboard.md` with briefing link.

Output: `<promise>DAILY_BRIEFING_COMPLETE</promise>`
