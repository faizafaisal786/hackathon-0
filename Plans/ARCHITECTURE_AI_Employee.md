# Enterprise AI Employee — System Architecture

**Version:** 2.0 (Enterprise Upgrade)
**Architect:** Claude AI Systems Architect
**Date:** 2026-02-17
**Base System:** Obsidian Vault File-Based State Machine

---

## 1. Architecture Diagram

```
                        ┌─────────────────────────────────┐
                        │        INPUT LAYER               │
                        │  (Multi-Channel Ingestion)       │
                        └──────────┬──────────────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
     ┌──────▼──────┐      ┌───────▼───────┐     ┌────────▼────────┐
     │ gmail_       │      │ whatsapp_     │     │ filesystem_     │
     │ watcher.py   │      │ watcher.py    │     │ watcher.py      │
     │ (Gmail API)  │      │ (Twilio WH)   │     │ (watchdog)      │
     └──────┬───────┘      └───────┬───────┘     └────────┬────────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │        INBOX/            │  ← Landing Zone
                    │  (Raw incoming tasks)    │
                    └────────────┬─────────────┘
                                 │
                          watcher.py (5s poll)
                                 │
                                 ▼
                    ┌──────────────────────────┐
                    │     NEEDS_ACTION/        │  ← Queue
                    │  (Awaiting AI analysis)  │
                    └────────────┬─────────────┘
                                 │
                       claude_runner.py (AI Brain)
                                 │
                    ┌────────────┴─────────────┐
                    │                          │
                    ▼                          ▼
      ┌──────────────────────┐  ┌──────────────────────────┐
      │      Plans/          │  │   PENDING_APPROVAL/      │
      │  PLAN_*.md           │  │   ACTION_*.md            │
      │  (Audit trail)       │  │   (Awaiting human OK)    │
      └──────────────────────┘  └────────────┬─────────────┘
                                             │
                                ┌────────────┤ HUMAN-IN-THE-LOOP
                                │            │ (Obsidian UI / CLI)
                                │            │
                         ┌──────▼──┐    ┌────▼──────┐
                         │APPROVED/│    │REJECTED/  │
                         │         │    │           │
                         └────┬────┘    └─────┬─────┘
                              │               │
                     executor.py         log + archive
                              │               │
            ┌─────────────────┼───────────────┘
            │                 │
            │    ┌────────────┼────────────┐
            │    │            │            │
            │    ▼            ▼            ▼
            │  Email       WhatsApp    LinkedIn
            │  (SMTP)      (Twilio)    (API)
            │
            ▼
      ┌──────────────────────────┐
      │         DONE/            │  ← Archive
      │   (Completed + stamped)  │
      └────────────┬─────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
        ▼          ▼          ▼
   Logs/       Briefings/   Dashboard.md
   YYYY-MM-    Monday_      (Live status)
   DD.json     CEO.md
```

---

## 2. Folder Structure (Enterprise)

```
Obsidian Vaults/                          ← VAULT ROOT
│
├── AI_Employee/                          ← APPLICATION CODE
│   ├── main.py                           # Master orchestrator (--demo/--live/--status)
│   ├── watcher.py                        # Inbox → Needs_Action (5s poll)
│   ├── claude_runner.py                  # AI Brain: analyze + plan + draft
│   ├── executor.py                       # Approved → Send + Done
│   ├── workflow.py                       # State machine + stage definitions
│   ├── email_sender.py                   # Gmail SMTP sender
│   ├── whatsapp_sender.py               # Twilio WhatsApp sender
│   ├── linkedin_sender.py               # LinkedIn API publisher
│   ├── .env                              # Secrets (NEVER committed)
│   │
│   └── AI_Employee_Vault/                ← DATA VAULT (State Machine Folders)
│       ├── Inbox/                        # Stage 0: Raw incoming
│       ├── Needs_Action/                 # Stage 1: Queued for AI
│       ├── Plans/                        # Stage 2: PLAN_*.md audit trail
│       ├── Pending_Approval/             # Stage 3: ACTION_*.md awaiting human
│       ├── Approved/                     # Stage 4: Human said YES
│       ├── Rejected/                     # Stage 4b: Human said NO
│       ├── Done/                         # Stage 5: Completed archive
│       ├── Logs/                         # Daily JSON audit logs
│       ├── Briefings/                    # CEO weekly reports
│       ├── WhatsApp_Sent/                # WhatsApp simulation files
│       ├── LinkedIn_Posts/               # LinkedIn simulation files
│       └── WORKFLOW.md                   # Architecture reference
│
├── Needs_Action/                         ← ROOT-LEVEL pipeline (ralph_loop.py)
├── Pending_Approval/
├── Approved/
├── Rejected/
├── Done/
├── Plans/
├── Logs/
├── Briefings/
│
├── ralph_loop.py                         # Always-on loop processor (cloud/local)
├── filesystem_watcher.py                 # OS-level file watcher (watchdog)
├── gmail_watcher.py                      # Gmail API poller
├── local_approval_watcher.py             # Watches for human approval actions
│
├── Dashboard.md                          # Live pipeline status
├── Company_Handbook.md                   # Business rules for AI
├── cloud_setup.sh                        # VM deployment script
└── cloud_sync.sh                         # Git sync to cloud
```

---

## 3. File Responsibilities

### LAYER 1 — Input Watchers (Ingestion)

| File | Role | Trigger | Output |
|------|------|---------|--------|
| `filesystem_watcher.py` | OS file watcher | New .md file in vault root | Copy → `Needs_Action/` |
| `gmail_watcher.py` | Email poller | New Gmail (every 60s) | Write → `Inbox/` or `Needs_Action/` |
| `watcher.py` | Internal shuttle | Files in `Inbox/` (every 5s) | Move → `Needs_Action/` |
| `local_approval_watcher.py` | Approval detector | File moved to `Approved/` or `Rejected/` | Triggers executor |

### LAYER 2 — AI Brain (Analysis + Planning)

| File | Role | Input | Output |
|------|------|-------|--------|
| `claude_runner.py` | AI task analyzer | `Needs_Action/*.md` | `Plans/PLAN_*.md` + `Pending_Approval/ACTION_*.md` |
| `workflow.py` | State machine engine | Stage enum + transitions | Validates moves, logs transitions |

**Brain Logic:**
1. Parse task file → extract channel, recipient, priority, body
2. Detect channel: Email / WhatsApp / LinkedIn / General
3. Generate structured PLAN (audit record)
4. Generate ACTION file (the actual deliverable for human review)
5. Move ACTION → `Pending_Approval/`

### LAYER 3 — Human Gate (Approval)

| Component | Mechanism | Action |
|-----------|-----------|--------|
| Obsidian UI | Human reads `Pending_Approval/ACTION_*.md` | Drag to `Approved/` or `Rejected/` |
| CLI mode | `main.py --live` prompts y/n | Script moves file |
| Demo mode | `main.py --demo` auto-approves | Bypasses human (hackathon only) |

**Rule:** NOTHING executes without passing through this gate (except demo mode).

### LAYER 4 — Executor (Send + Complete)

| File | Role | Input | Channels |
|------|------|-------|----------|
| `executor.py` | Master executor | `Approved/*.md` | Dispatches to channel sender |
| `email_sender.py` | Email via SMTP | ACTION file with `EMAIL` | Gmail SMTP (port 587 TLS) |
| `whatsapp_sender.py` | WhatsApp via Twilio | ACTION file with `WHATSAPP` | Twilio REST API / Simulation |
| `linkedin_sender.py` | LinkedIn post | ACTION file with `LINKEDIN` | LinkedIn UGC API / Simulation |

**Executor Logic:**
1. Read approved ACTION file
2. Detect channel from filename (`EMAIL`, `WHATSAPP`, `LINKEDIN`)
3. Parse channel-specific fields (recipient, subject, body, hashtags)
4. Send via real API (if credentials exist) OR simulate (write to local file)
5. Move to `Done/`
6. Append to `Logs/YYYY-MM-DD.json`

### LAYER 5 — Pipeline Orchestrators

| File | Role | Mode | Loop |
|------|------|------|------|
| `main.py` | Full 4-stage pipeline | `--demo` / `--live` / `--status` | Single pass |
| `ralph_loop.py` | Always-on daemon | Cloud VM (systemd) | Infinite loop (60s interval) |

### LAYER 6 — Reporting + Observability

| File | Role | Schedule | Consumer |
|------|------|----------|----------|
| `Dashboard.md` | Live pipeline counts | Updated every loop pass | CEO / Obsidian |
| `Briefings/Monday_CEO.md` | Weekly executive summary | Every Monday | CEO |
| `Logs/YYYY-MM-DD.json` | Daily audit trail | On every action | Compliance / Debug |

---

## 4. Data Flow — Complete Lifecycle

### Flow A: Email Reply

```
Step 1: gmail_watcher.py detects new email from client@example.com
        → Writes EMAIL_client_reply.md to Inbox/

Step 2: watcher.py picks up file (5s)
        → Moves to Needs_Action/EMAIL_client_reply.md

Step 3: claude_runner.py analyzes
        → Parses: Channel=Email, To=client@example.com, Subject, Body
        → Creates: Plans/PLAN_EMAIL_client_reply.md (audit)
        → Creates: Pending_Approval/ACTION_EMAIL_client_reply.md (draft)

Step 4: Human opens Obsidian, reads the draft reply
        → Reviews, optionally edits
        → Drags file to Approved/ folder

Step 5: executor.py detects approved file
        → Calls email_sender.send_email(to, subject, body)
        → Gmail SMTP sends the email
        → Moves ACTION file to Done/
        → Logs: {"task": "ACTION_EMAIL_client_reply", "channel": "Email", "status": "Email sent successfully"}

Step 6: Dashboard.md updates. Monday_CEO.md includes this in weekly summary.
```

### Flow B: WhatsApp Client Update

```
Step 1: CEO drops WHATSAPP_ahmed_update.md in vault root
        → filesystem_watcher.py copies to Needs_Action/

Step 2: claude_runner.py → detects Channel=WhatsApp
        → Drafts professional WhatsApp message
        → ACTION_WHATSAPP_ahmed_update.md → Pending_Approval/

Step 3: Human approves (Obsidian drag or CLI y/n)

Step 4: executor.py → whatsapp_sender.py
        → If Twilio configured: sends real WhatsApp via API
        → If no credentials: simulates, saves to WhatsApp_Sent/

Step 5: Logged + archived in Done/
```

### Flow C: LinkedIn Post

```
Step 1: Task file with LINKEDIN in name lands in Needs_Action/
Step 2: claude_runner.py drafts post with hashtags
Step 3: Human reviews post content, approves
Step 4: linkedin_sender.py publishes via LinkedIn UGC API (or simulates)
Step 5: Saved to LinkedIn_Posts/, logged in Logs/
```

### State Machine Transitions

```
                          ┌─────────┐
                          │  INBOX  │
                          └────┬────┘
                               │ watcher.py (auto)
                               ▼
                       ┌───────────────┐
                       │ NEEDS_ACTION  │
                       └───────┬───────┘
                               │ claude_runner.py (auto)
                               ▼
                    ┌──────────────────────┐
                    │  PENDING_APPROVAL    │
                    └──────────┬───────────┘
                               │ HUMAN DECISION
                    ┌──────────┴───────────┐
                    ▼                      ▼
            ┌──────────────┐       ┌──────────────┐
            │   APPROVED   │       │   REJECTED   │
            └──────┬───────┘       └──────┬───────┘
                   │ executor.py          │ log only
                   │ (send via channel)   │
                   ▼                      ▼
            ┌──────────────────────────────────┐
            │              DONE                │
            │  (archived + stamped + logged)   │
            └──────────────────────────────────┘
```

---

## 5. Security Layer

### 5.1 Environment Variable Protection

```
AI_Employee/.env (NEVER in git)
───────────────────────────────
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx     ← Gmail App Password (not regular password)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=+14155238886
LINKEDIN_ACCESS_TOKEN=AQVxxxxxxx
LINKEDIN_PERSON_ID=xxxxxxxxx
```

**Rules enforced in code:**
- Each sender module has `load_env()` that reads `.env` from its own directory
- If credentials missing or contain `your_`, falls back to **DEMO/SIMULATION mode**
- No secrets are ever written to .md files, logs, or plans

### 5.2 Human-in-the-Loop Gate

```
┌───────────────────────────────────────────────────┐
│              SECURITY CHECKPOINT                  │
│                                                   │
│  AI CAN:                                          │
│  ✓ Read incoming tasks                            │
│  ✓ Analyze content                                │
│  ✓ Draft responses                                │
│  ✓ Create plans                                   │
│                                                   │
│  AI CANNOT (without human approval):              │
│  ✗ Send any email                                 │
│  ✗ Send any WhatsApp message                      │
│  ✗ Publish any LinkedIn post                      │
│  ✗ Execute any external action                    │
│  ✗ Make any payment                               │
│                                                   │
│  COMPANY RULES (Company_Handbook.md):             │
│  • Always polite on WhatsApp                      │
│  • Never auto-process payments                    │
│  • Email requires approval before send            │
│  • Over $100 → mandatory human approval           │
└───────────────────────────────────────────────────┘
```

### 5.3 Audit Trail

Every action is logged to `Logs/YYYY-MM-DD.json`:

```json
{
  "audit_date": "2026-02-17",
  "system": "AI Employee Vault",
  "version": "1.0",
  "total_events": 5,
  "events": [
    {
      "id": "EVT-001",
      "timestamp": "2026-02-17T09:15:32",
      "actor": "ralph_loop",
      "action": "NEEDS_TO_PENDING",
      "category": "pipeline",
      "details": "EMAIL_client_reply.md moved to Pending_Approval",
      "severity": "INFO",
      "result": "SUCCESS"
    }
  ]
}
```

**Audit guarantees:**
- Every file movement is logged with timestamp, actor, action
- Event IDs are sequential (`EVT-001`, `EVT-002`, ...)
- Severity levels: `INFO`, `WARNING`, `ERROR`
- Immutable once written (append-only log)

### 5.4 Simulation Fallback

All channel senders have **dual mode**:

| Mode | When | What Happens |
|------|------|-------------|
| **LIVE** | Real credentials in `.env` | Sends via actual API (SMTP/Twilio/LinkedIn) |
| **SIMULATION** | No credentials or `your_` placeholder | Writes to local file, prints `[DEMO MODE]` |

This means the system **never crashes** due to missing credentials — it gracefully degrades.

### 5.5 File-Based Security Benefits

| Advantage | Explanation |
|-----------|-------------|
| No database to breach | State lives in filesystem folders |
| No API keys in code | `.env` file, gitignored |
| Approval is physical | Human must physically move/drag a file |
| Full audit trail | JSON logs + markdown stamps on every file |
| Rollback = undo move | Move file back to previous folder |
| Offline capable | Works without internet (simulation mode) |

---

## 6. Deployment Modes

### Mode 1: Local (Hackathon Demo)
```bash
python AI_Employee/main.py --demo    # Auto-approves, runs all 4 stages
```

### Mode 2: Local Interactive
```bash
python AI_Employee/main.py --live    # Human approves each task via CLI
```

### Mode 3: Always-On Daemon (Cloud)
```bash
# On cloud VM (systemd service)
python ralph_loop.py                 # Infinite loop, 60s intervals
# + filesystem_watcher.py            # Watchdog for new files
# + gmail_watcher.py                 # Gmail polling
```

### Mode 4: Pipeline Status Check
```bash
python AI_Employee/main.py --status  # Show counts per folder
```

---

## 7. Component Interaction Matrix

```
                  watcher  brain  executor  email  whatsapp  linkedin  ralph  dashboard
watcher.py          —       →        ·        ·       ·         ·        ·       ·
claude_runner.py    ·       —        ·        ·       ·         ·        ·       ·
executor.py         ·       ·        —        →       →         →        ·       ·
email_sender.py     ·       ·        ·        —       ·         ·        ·       ·
whatsapp_sender.py  ·       ·        ·        ·       —         ·        ·       ·
linkedin_sender.py  ·       ·        ·        ·       ·         —        ·       ·
ralph_loop.py       ·       ·        ·        ·       ·         ·        —       →
main.py             →       →        →        ·       ·         ·        ·       →

→ = calls/uses     · = no direct dependency
```

**Key insight:** Modules are loosely coupled. `executor.py` is the only file that imports channel senders. `main.py` orchestrates the sequence but each stage can run independently.

---

## 8. Summary

| Layer | Components | Purpose |
|-------|-----------|---------|
| **Input** | gmail_watcher, filesystem_watcher, watcher | Multi-channel ingestion into Inbox/Needs_Action |
| **Brain** | claude_runner, workflow | AI analysis, plan creation, draft generation |
| **Gate** | Obsidian UI / CLI approval | Human reviews, edits, approves or rejects |
| **Execute** | executor, email_sender, whatsapp_sender, linkedin_sender | Send via real APIs or simulate |
| **Archive** | Done/, Logs/, Briefings/, Dashboard | Audit trail, reporting, CEO visibility |
| **Orchestration** | main.py (single pass), ralph_loop.py (daemon) | Pipeline coordination, always-on processing |
| **Security** | .env, Company_Handbook, human gate, audit logs | Credentials isolation, approval enforcement, compliance |

**Architecture Philosophy:**
- Files ARE the database (Obsidian-native)
- Folders ARE the states (physical state machine)
- Moving a file = changing its state
- Human drags a file = approval granted
- Every action logged = full compliance
- No credentials in code = secure by default
- Simulation fallback = never crashes

---

**Status:** Production-ready architecture. Enterprise-grade security. Hackathon-demo friendly.
