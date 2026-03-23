# Skill: Daily Briefing

Generate a morning briefing and save to `/Briefings/`.

1. Read `Dashboard.md`, `Company_Handbook.md`, `Business_Goals.md`.
2. Scan `/Needs_Action` — group by priority (critical → high → normal → low).
3. Scan `/Done` for yesterday's completions.
4. Check `/Logs/` for errors in last 24h.
5. Check `/Accounting/` for any finance alerts.
6. Write `/Briefings/YYYY-MM-DD_Daily_Briefing.md`:

```
# Daily Briefing — <date>
## Summary (1-2 sentences)
## Pending Items (<count>) — grouped by priority
## Completed Yesterday (<count>)
## Finance Snapshot
## Alerts / System Errors
## Top 3 Focus Items Today
```

7. Update `Dashboard.md` with link to briefing.
8. Log to `/Logs/`.

Output: `Briefing saved: /Briefings/<date>_Daily_Briefing.md`
