---
title: Agent Skills Reference — Gold Tier
tier: gold
---

# Agent Skills Reference — Gold Tier

All Silver Tier skills are available plus these Gold additions.

---

## Inherited from Silver

- `/process-inbox` — Triage Inbox/ items
- `/complete-task` — Mark task done, archive
- `/update-dashboard` — Rebuild Dashboard.md
- `/daily-briefing` — Morning briefing
- `/create-plan` — Reasoning loop Plan.md
- `/post-linkedin` — LinkedIn post draft
- `/request-approval` — HITL approval request

---

## Gold Tier Skills

### `/post-social`
**File:** `.claude/commands/post-social.md`
**Description:** Creates content for Facebook, Instagram, and/or Twitter/X.
**Usage:** `/post-social` — Claude asks which platform(s) and topic.
**Output:** Drafts in `Pending_Approval/Social_[platform]_[date].md`
**Requires approval:** Yes

---

### `/ralph-loop`
**File:** `.claude/commands/ralph-loop.md`
**Description:** Starts the autonomous multi-step task completion loop.
Claude will work through a backlog or complex task without prompting.
**Usage:** `/ralph-loop` — Claude describes what it will do and asks for confirmation.
**Safety:** Max 10 iterations, logs every action, stops on ambiguity.
**Stop:** Create `Needs_Action/STOP_RALPH.md` to halt the loop.

---

### `/weekly-audit`
**File:** `.claude/commands/weekly-audit.md`
**Description:** Comprehensive weekly business and accounting audit.
Pulls data from Odoo, reviews all vault activity, generates audit report.
**When to run:** Automated Monday 06:00 via scheduler.
**Output:** `Briefings/Weekly_Audit_[date].md`

---

### `/ceo-briefing`
**File:** `.claude/commands/ceo-briefing.md`
**Description:** Generates the weekly executive summary for the business owner.
Synthesizes financial data, task performance, social media, and recommendations.
**When to run:** Monday morning after weekly-audit completes.
**Output:** `Briefings/CEO_Briefing_[date].md`

---

### `/odoo-sync`
**File:** `.claude/commands/odoo-sync.md`
**Description:** Syncs Odoo data into vault files. Reads invoices, expenses, contacts.
**Usage:** `/odoo-sync` — Claude syncs and reports what changed.
**Output:** Updated files in `Accounting/`

---

## MCP Servers at Gold Tier

| Server | File | Capabilities |
|---|---|---|
| Email MCP | `mcp-servers/email-mcp/index.js` | Send Gmail emails |
| Social MCP | `mcp-servers/social-mcp/index.js` | Post to FB/IG/Twitter |
| Odoo MCP | `mcp-servers/odoo-mcp/index.js` | Read/write Odoo data |

**Register all servers in Claude Code:**
```json
{
  "mcpServers": {
    "email": {
      "command": "node",
      "args": ["mcp-servers/email-mcp/index.js"]
    },
    "social": {
      "command": "node",
      "args": ["mcp-servers/social-mcp/index.js"]
    },
    "odoo": {
      "command": "node",
      "args": ["mcp-servers/odoo-mcp/index.js"]
    }
  }
}
```

---

## Ralph Loop Architecture

```
/ralph-loop
     │
     ▼
[Scan Inbox/ + Needs_Action/]
     │
     ▼
[Identify next highest-priority task]
     │
     ▼
[Execute task (if no approval needed)]
     │
     ├── Approval needed → Pending_Approval/ → STOP, wait for human
     │
     ├── Confidence < 70% → NEEDS_GUIDANCE file → STOP
     │
     ├── STOP_RALPH.md detected → STOP immediately
     │
     └── Task complete → Log → Next iteration (max 10)
```

---

## Gold Tier Scheduler Jobs

| Job | Schedule | Description |
|---|---|---|
| Daily Briefing | 07:00 daily | Morning summary |
| Inbox Sweep | 19:00 daily | Evening processing |
| LinkedIn Draft | Mon/Wed/Fri 08:00 | LinkedIn content |
| Social Posts | Tue/Thu 08:00 | FB/IG/Twitter drafts |
| Weekly Audit | Mon 06:00 | Accounting + business audit |
| CEO Briefing | Mon 08:00 | After weekly audit |
| Odoo Sync | Sun 22:00 | Pre-week accounting sync |
| Check Approvals | Every 4h | Flag stale approvals |
