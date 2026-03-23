# Skill: Weekly Business Audit

Run a comprehensive weekly business audit every Sunday.

Steps:
1. Read `Business_Goals.md` for current targets and KPIs.
2. Scan `/Done` for tasks completed this week — count and categorize.
3. Scan `/Needs_Action` for overdue items (created > 48h ago, still pending).
4. Read `/Accounting/Current_Month.md` for transactions (if available).
5. Check `/Logs/` for errors and anomalies this week.
6. Identify bottlenecks: tasks that exceeded expected duration.
7. Detect subscription/cost anomalies using patterns in `accounting/audit_logic.py`.
8. Generate `/Briefings/YYYY-MM-DD_Weekly_Audit.md`:

```
# Weekly Audit — <date range>
## Revenue & Finance Summary
## Tasks Completed This Week (<count>)
## Overdue / Stuck Items
## Bottlenecks (tasks that took too long)
## Cost / Subscription Anomalies
## Goal Progress vs Target
## Recommendations for Next Week
```

9. Update `Dashboard.md` with audit link.
10. Log audit completion.

Output: `<promise>WEEKLY_AUDIT_COMPLETE</promise>`
