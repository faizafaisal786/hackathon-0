# Update Dashboard

You are acting as a Personal AI Employee. Your job is to rebuild the Dashboard.md to reflect the current state of the vault.

## Instructions

1. **Scan the vault folders and collect these counts:**
   - `Inbox/` — count all .md files
   - `Needs_Action/` — count all .md files, list each with priority and title
   - `Pending_Approval/` — count all .md files, list each with type and age
   - `Plans/` — count all .md files, list active plans
   - `Done/` — count .md files modified in last 7 days
   - `Approved/` — count .md files
   - `Rejected/` — count .md files

2. **Check system component status:**
   - Check if `Logs/orchestrator.log` exists and when it was last modified (watcher status)
   - Check if `Logs/gmail_seen_ids.json` exists (Gmail watcher)
   - Check if `Logs/linkedin_seen_ids.json` exists (LinkedIn watcher)
   - Check if `Logs/scheduler.log` exists (Scheduler)

3. **Read the last 5 entries from `Logs/agent.log`** for recent activity summary.

4. **Calculate LinkedIn metrics:**
   - Count LinkedIn post files in Done/ from last 7 days
   - Count files in Pending_Approval/ with "linkedin" in name

5. **Write updated Dashboard.md** using this exact structure:

```markdown
---
title: Personal AI Employee — Silver Dashboard
tier: silver
updated: [YYYY-MM-DD HH:MM]
---

# Personal AI Employee Dashboard — Silver Tier

> Last Updated: [date and time]
> Agent Status: 🟢 Online

---

## System Health

| Component | Status | Last Run | Notes |
|---|---|---|---|
| Filesystem Watcher | [status] | [time] | ... |
| Gmail Watcher | [status] | [time] | ... |
| LinkedIn Watcher | [status] | [time] | ... |
| Email MCP Server | [status] | [time] | ... |
| Scheduler | [status] | [time] | ... |

---

## Inbox

- **Total Items:** [N]
- **Oldest Item:** [filename or "—"]

## Active Tasks (Needs_Action)

| # | Task | Priority | Age |
|---|---|---|---|
[list each task file]

## Pending Approvals

| # | Item | Type | Age |
|---|---|---|---|
[list each pending approval]

---

## Plans in Progress

[list plans]

---

## LinkedIn Activity

- **Posts This Week:** [N] / 3 target
- **Pending Posts:** [N]
- **Last Post:** [date or "None"]

---

## Email Summary (Last 24h)

- **New in Inbox:** [N]
- **Tasks Created:** [N]
- **Archived:** [N]

---

## Done (Last 7 Days)

| Task | Completed | Domain |
|---|---|---|
[list recent done items]

---

*Refresh with: `/update-dashboard`*
```

6. **Log the update:**
   Append to `Logs/agent.log`: `[timestamp] | update-dashboard | completed`
