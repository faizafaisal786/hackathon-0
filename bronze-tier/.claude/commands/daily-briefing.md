# Skill: Daily Briefing

Generate a daily summary report and save it to the vault.

Steps:
1. Read `Dashboard.md` for current status.
2. Read `Company_Handbook.md` for active goals and rules.
3. Scan `/Needs_Action` for all pending items — group by priority.
4. Scan `/Done` for items completed yesterday and today.
5. Check `/Logs/` for any errors or warnings from the last 24 hours.
6. Write a briefing file to `/Briefings/YYYY-MM-DD_Daily_Briefing.md` with this structure:

```
# Daily Briefing — <date>

## Summary
<1-2 sentence overview>

## Pending Items (<count>)
<list by priority>

## Completed Yesterday (<count>)
<list>

## Alerts / Errors
<any issues>

## Suggested Focus Today
<top 3 items to address>
```

7. Update `Dashboard.md` with a link to the briefing.
8. Log the briefing generation in `/Logs/`.

Output: `Briefing saved to /Briefings/<date>_Daily_Briefing.md`
