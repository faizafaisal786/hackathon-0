# Skill: CEO Monday Briefing (Platinum)

Cloud drafts the briefing → Local adds private data → Local sends to human.

**Cloud Agent Steps** (Sunday night):
1. Compile week's activity from `/Done/` across all domains.
2. Get Odoo revenue + invoice data via `odoo-mcp`.
3. Get social analytics via `social-mcp`.
4. Identify bottlenecks and top achievements.
5. Draft `/Plans/CEO_BRIEFING_DRAFT_<date>.md`.
6. Write `/Updates/ceo_briefing_ready_<date>.md`.

**Local Agent Steps** (Monday 7AM):
1. Read Cloud's draft.
2. Add private financial data (bank balance, etc.).
3. Finalize `/Briefings/YYYY-MM-DD_Monday_CEO_Briefing.md`:

```
# Monday CEO Briefing — <date>
## Executive Summary
## Revenue (Week + MTD vs Target)
## Top Achievements
## Bottlenecks
## Proactive Suggestions (cost savings, deadlines)
## Action Items for Today (top 3)
---
*Cloud drafted | Local finalized | Platinum AI Employee*
```

4. Update `Dashboard.md`.
5. Output: `<promise>CEO_BRIEFING_COMPLETE</promise>`
