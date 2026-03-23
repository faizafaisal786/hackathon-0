# Gold Tier — Architecture Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  GOLD TIER AI EMPLOYEE                      │
└─────────────────────────────────────────────────────────────┘

EXTERNAL SOURCES
  Gmail API  │  WhatsApp Web  │  Bank APIs  │  File System
      │              │               │             │
      ▼              ▼               ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                   PERCEPTION LAYER (Watchers)               │
│  gmail_watcher  │  whatsapp_watcher  │  finance_watcher     │
│                     filesystem_watcher                       │
└───────────────────────────┬─────────────────────────────────┘
                             │  writes .md files
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   OBSIDIAN VAULT (Local)                    │
│  /Inbox  /Needs_Action  /Plans  /Done  /Logs                │
│  /Pending_Approval  /Approved  /Rejected                    │
│  Dashboard.md  Company_Handbook.md  Business_Goals.md       │
└───────────────────────────┬─────────────────────────────────┘
                             │  reads/writes
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   REASONING LAYER (Claude Code)             │
│  Agent Skills: /process-inbox /weekly-audit /ceo-briefing   │
│  Ralph Wiggum Loop: autonomous multi-step iteration         │
└───────────────────────────┬─────────────────────────────────┘
                             │  MCP calls
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   ACTION LAYER (MCP Servers)                │
│  email-mcp      → Gmail send/draft                         │
│  social-mcp     → Facebook, Instagram, Twitter              │
│  odoo-mcp       → Odoo 19+ JSON-RPC (draft-only)           │
└─────────────────────────────────────────────────────────────┘
         ▲
         │  All sensitive actions → /Pending_Approval first
         │  Human moves to /Approved to execute
```

## Orchestrator Flow

```
orchestrator.py starts
  └─ WatcherManager.start_all()
       ├─ gmail_watcher.py   (background)
       ├─ whatsapp_watcher.py (background)
       ├─ finance_watcher.py  (background)
       └─ filesystem_watcher.py (background)

  Main loop (every 30s):
    ├─ ClaudeTrigger.check_and_trigger()
    │    └─ If new items in /Needs_Action → claude /process-inbox
    ├─ ApprovalWatcher.check()
    │    └─ If file in /Approved → execute MCP action
    └─ WatcherManager.check_and_restart()
         └─ Restart any dead watcher processes

watchdog.py (separate process):
  └─ Monitors orchestrator itself + restarts if it dies
```

## Ralph Wiggum Loop

```
ralph_loop.py "Do X" --max-iterations 10
  │
  ├─ Iteration 1: claude --print "Do X"
  │    └─ Output contains <promise>TASK_COMPLETE</promise>? → EXIT
  │    └─ No → re-inject prompt
  │
  ├─ Iteration 2: same prompt with previous context
  │    └─ Check completion...
  │
  └─ Iteration N (max): Log "incomplete" and exit with code 1
```

## Human-in-the-Loop (HITL) Pattern

```
Claude detects sensitive action needed
  │
  ├─ Creates: /Pending_Approval/APPROVAL_<type>_<date>.md
  │
  └─ STOPS. Waits.

Human reviews file in Obsidian
  ├─ Approve → move to /Approved/
  └─ Reject  → move to /Rejected/

ApprovalWatcher detects file in /Approved
  └─ Calls MCP server to execute action
  └─ Moves file to /Done/
  └─ Logs result
```

## Security Model

| Layer | Protection |
|-------|------------|
| Credentials | `.env` file, never in vault |
| Payments | Always HITL, no auto-approve |
| Social posts | Always HITL |
| Odoo writes | Draft-only by default |
| API calls | Rate limited (RateLimiter) |
| Failures | Retried with exponential backoff |
| Audit | Full JSON log in /Logs/ |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Reasoning Engine | Claude Code (claude-sonnet-4-6) |
| Knowledge Base | Obsidian (local Markdown) |
| Watchers | Python 3.13+ (watchdog, playwright) |
| MCP Servers | Node.js 24+ LTS |
| Accounting | Odoo 19+ Community |
| Orchestration | Python orchestrator.py |
| Autonomy | Ralph Wiggum loop |
| Error Recovery | Exponential backoff + watchdog |
