---
title: Personal AI Employee — Silver Dashboard
tier: silver
updated: 2026-03-13
---

# Personal AI Employee Dashboard — Silver Tier

> Last Updated: {{date}} {{time}}
> Agent Status: 🟢 Online

---

## System Health

| Component | Status | Last Run | Notes |
|---|---|---|---|
| Filesystem Watcher | 🟢 Running | — | Monitors local drop folder |
| Gmail Watcher | 🟡 Needs Config | — | Requires OAuth setup |
| LinkedIn Watcher | 🟡 Needs Config | — | Requires session cookie |
| Email MCP Server | 🔴 Stopped | — | Run: `node mcp-servers/email-mcp/index.js` |
| Scheduler | 🟡 Needs Config | — | Run: `python scheduler.py` |

---

## Inbox

- **Total Items:** 0
- **Oldest Item:** —
- **New Since Last Check:** 0

## Active Tasks (Needs_Action)

| # | Task | Priority | Domain | Age |
|---|---|---|---|---|
| — | No active tasks | — | — | — |

## Pending Approvals

| # | Item | Type | Requested | Waiting For |
|---|---|---|---|---|
| — | No pending approvals | — | — | — |

---

## Plans in Progress

| Plan | Domain | Created | Status |
|---|---|---|---|
| — | — | — | — |

---

## LinkedIn Activity

| Date | Post Type | Status | Engagement |
|---|---|---|---|
| — | — | — | — |

**Next Scheduled Post:** Not scheduled
**Posts This Week:** 0 / 3 target

---

## Email Summary (Last 24h)

- **Received:** 0
- **Triaged:** 0
- **Drafts Created:** 0
- **Sent (via MCP):** 0

---

## Done (Last 7 Days)

| Task | Completed | Domain |
|---|---|---|
| — | — | — |

---

## Upcoming Schedule

| Time | Task | Trigger |
|---|---|---|
| 07:00 Daily | Daily Briefing | Scheduler |
| 09:00 Mon | LinkedIn Post | Scheduler |
| 19:00 Daily | Inbox Sweep | Scheduler |

---

## Logs

- **Last Watcher Log:** `Logs/watcher.log`
- **Last Agent Log:** `Logs/agent.log`
- **Last Approval Log:** `Logs/approvals.log`

---

*Refresh with: `/update-dashboard`*
