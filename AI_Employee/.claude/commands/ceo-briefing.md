# Agent Skill: Generate CEO Briefing

Generate the Monday Morning CEO Briefing — weekly business audit report.

## Instructions

1. Read `AI_Employee_Vault/Business_Goals.md` for current targets and KPIs
2. Scan `AI_Employee_Vault/Done/` for all tasks completed this week
3. Scan `AI_Employee_Vault/Logs/` for email, WhatsApp, social media activity
4. Scan `AI_Employee_Vault/Rejected/` for failed or rejected tasks
5. Calculate metrics:
   - Tasks completed vs pending
   - Emails sent / replied
   - Social posts published
   - Response time averages
6. Identify bottlenecks (tasks delayed > 48 hours)
7. Generate proactive suggestions (cost savings, missed opportunities)
8. Write full briefing to `AI_Employee_Vault/Briefings/Briefing_YYYY-MM-DD.md`
9. Update `AI_Employee_Vault/Dashboard.md` with briefing summary

## Output Format

```markdown
# Monday Morning CEO Briefing — [Date]
## Executive Summary
## Revenue & Tasks
## Bottlenecks
## Proactive Suggestions
## Next Week Priorities
```

## Usage

```
/ceo-briefing
/ceo-briefing "2026-03-10"
```
