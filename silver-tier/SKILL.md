---
title: Agent Skills Reference — Silver Tier
tier: silver
---

# Agent Skills Reference

This file documents all available Claude Code Agent Skills (slash commands) for the Silver Tier.
Run these inside the vault folder with `claude` active.

---

## Core Skills (inherited from Bronze)

### `/process-inbox`
**File:** `.claude/commands/process-inbox.md`
**Description:** Reads all files in `Inbox/`, triages them by priority, creates task files in `Needs_Action/`.
**When to run:** Anytime new items appear in Inbox/, or automatically via scheduler.
**Output:** Task files in `Needs_Action/`, updated Dashboard.md

---

### `/complete-task`
**File:** `.claude/commands/complete-task.md`
**Description:** Marks a task as complete, moves the file from `Needs_Action/` to `Done/`, updates Dashboard.
**When to run:** After you or Claude finishes a task.
**Usage:** `/complete-task` — Claude will ask which task to complete.

---

### `/update-dashboard`
**File:** `.claude/commands/update-dashboard.md`
**Description:** Rebuilds `Dashboard.md` by scanning all folders and compiling current state.
**When to run:** Morning, evening, or after any major action.

---

### `/daily-briefing`
**File:** `.claude/commands/daily-briefing.md`
**Description:** Generates a morning briefing with inbox summary, today's priorities, pending approvals.
**When to run:** Automatically at 07:00 via scheduler, or manually any time.
**Output:** Briefing printed in terminal + Dashboard.md updated.

---

## Silver Tier Skills

### `/create-plan`
**File:** `.claude/commands/create-plan.md`
**Description:** Triggers Claude's reasoning loop to create a `Plan.md` for a complex situation.
**When to run:** When a task requires multi-step thinking or strategic decision.
**Usage:** `/create-plan` — Claude will ask for the topic/situation.
**Output:** `Plans/Plan_[Topic]_[date].md`

---

### `/post-linkedin`
**File:** `.claude/commands/post-linkedin.md`
**Description:** Creates a LinkedIn post draft based on current business goals and content strategy.
**When to run:** Monday/Wednesday/Friday mornings, or when you have a specific topic.
**Usage:** `/post-linkedin` — Claude will ask for topic or generate from Business_Goals.md.
**Output:** Draft in `Pending_Approval/LinkedIn_Post_[date].md`
**Note:** Requires your approval before the LinkedIn MCP publishes.

---

### `/request-approval`
**File:** `.claude/commands/request-approval.md`
**Description:** Creates a structured approval request for a sensitive action.
**When to run:** When Claude needs to take an action that requires human sign-off.
**Usage:** `/request-approval` — Claude will ask what action needs approval.
**Output:** File in `Pending_Approval/Approval_[action]_[date].md`

---

## Workflow Quick Reference

```
New Email → Gmail Watcher → Inbox/ → /process-inbox → Needs_Action/
                                                              ↓
                                                    [Claude drafts response]
                                                              ↓
                                                    /request-approval
                                                              ↓
                                                    Pending_Approval/
                                                              ↓
                                                    [You review & move]
                                                              ↓
                                                Approved/ ────────── Rejected/
                                                    ↓
                                          Email MCP sends email
                                                    ↓
                                             /complete-task
                                                    ↓
                                                  Done/
```

---

## MCP Servers Available at Silver Tier

| Server | Location | Capability |
|---|---|---|
| Email MCP | `mcp-servers/email-mcp/` | Send emails via Gmail API |

**Starting MCP servers:**
```bash
node mcp-servers/email-mcp/index.js
```

**Registering with Claude Code:**
Add to your `.claude/settings.json`:
```json
{
  "mcpServers": {
    "email": {
      "command": "node",
      "args": ["mcp-servers/email-mcp/index.js"]
    }
  }
}
```

---

## Scheduler Jobs

Managed by `scheduler.py`. Start with:
```bash
python scheduler.py
```

| Job Name | Schedule | Skill Triggered |
|---|---|---|
| morning-briefing | 07:00 daily | `/daily-briefing` |
| inbox-sweep | 19:00 daily | `/process-inbox` |
| linkedin-draft | Mon 08:00 | `/post-linkedin` |
| weekly-review | Fri 17:00 | `/daily-briefing` (extended) |

---

## Tips for Best Results

1. **Keep Company_Handbook.md updated** — Claude reads it every session. Outdated rules cause wrong behavior.
2. **Review Pending_Approval/ daily** — Approvals older than 48h will be flagged by the scheduler.
3. **Use /create-plan for anything complex** — Don't let Claude jump to action on complex topics. Make it think first.
4. **Check approval rates** — If you're rejecting >20% of drafts, update the handbook with better rules.
5. **LinkedIn post timing** — Approve and publish LinkedIn posts Tuesday/Thursday mornings for best reach.
