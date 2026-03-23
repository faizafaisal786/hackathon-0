# Personal AI Employee — Platinum Tier
### Hackathon 0: Building Autonomous FTEs in 2026

> **Tier: PLATINUM** | Always-On Cloud + Local Executive

**Tagline:** Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLOUD (24/7 — Google Cloud Run)          │
│  Gmail Watcher → AI Pipeline (Groq/Llama3 FREE)             │
│  Email triage → Draft replies → Pending_Approval/cloud/     │
│                     Git Push ↓                              │
└─────────────────────────────────────────────────────────────┘
                     GitHub Vault Sync
                     (hackathon-0 repo)
┌─────────────────────────────────────────────────────────────┐
│                    LOCAL (Human-in-the-Loop)                 │
│  Git Pull → Review approvals → Approve/Reject               │
│  Local executes: send email, WhatsApp, payments             │
│  Odoo MCP → Accounting, Invoices (local Docker)             │
│  Dashboard.md updated by Local ONLY                         │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack
| Component | Tool | Cost |
|-----------|------|------|
| Brain | Groq/Llama3 (primary) + Claude (fallback) | FREE |
| Memory/GUI | Obsidian (local Markdown) | FREE |
| Cloud Runtime | Google Cloud Run Jobs | FREE |
| Scheduler | Google Cloud Scheduler | FREE |
| Vault Sync | Git / GitHub | FREE |
| Accounting | Odoo 17 Community (Docker) | FREE |
| Email | Gmail API (OAuth) | FREE |
| Social | LinkedIn, Twitter, Facebook, Instagram | Free tier |

---

## Tier Achievements

### Bronze ✅
- Obsidian vault: `Dashboard.md`, `Company_Handbook.md`
- Gmail Watcher (Python, OAuth)
- Filesystem Watcher
- Folder structure: `/Inbox`, `/Needs_Action`, `/Done`
- All AI as Agent Skills (`.claude/commands/`)

### Silver ✅
- Gmail + WhatsApp + LinkedIn + Filesystem Watchers
- Auto LinkedIn posting for business
- Claude reasoning loop → `Plan.md` files
- MCP servers: email-mcp, social-mcp
- Human-in-the-loop approval workflow (`/Pending_Approval` → `/Approved`)
- PM2 process management for always-on watchers

### Gold ✅
- Full cross-domain integration (Personal + Business)
- **Odoo Community (self-hosted Docker)** with JSON-RPC MCP
- Facebook, Instagram, Twitter (X) integration
- Multiple MCP servers (email, social, odoo)
- Weekly CEO Briefing generation
- Error recovery: `retry_handler.py`, `watchdog.py`
- Comprehensive audit logging (`/Logs/`)
- Ralph Wiggum loop (`ralph_loop.py`) for autonomous multi-step tasks
- `ARCHITECTURE.md` + `LESSONS_LEARNED.md`

### Platinum ✅
- **Cloud Run Job** (Google Cloud, free tier) — runs every 5 min via Cloud Scheduler
- Work-Zone Specialization:
  - Cloud: email triage, draft replies, social drafts
  - Local: approvals, WhatsApp, payments, final send
- Vault sync via Git (hackathon-0 repo)
- Claim-by-move rule (`claim_manager.py`) prevents double-work
- Single-writer rule: only Local writes `Dashboard.md`
- Cloud writes → `/Updates/`, `/Signals/`; Local merges → `Dashboard.md`
- Security: `.env`, tokens, credentials never sync to Git
- **Platinum Demo**: Email arrives while Local offline → Cloud drafts → Git push → Local pulls → approves → sends → Done

---

## Quick Setup (5 minutes)

### Prerequisites
```bash
python --version    # 3.13+
node --version      # 24+
docker --version    # latest
claude --version    # Claude Code
```

### 1. Clone & Install
```bash
git clone https://github.com/faizafaisal786/hackathon-0.git
cd hackathon-0/AI_Employee
pip install -r requirements.txt
```

### 2. Environment Setup
```bash
cp .env.example .env
# Edit .env with your API keys:
# GROQ_API_KEY=...       (free at console.groq.com)
# GMAIL_USER=...
# OPENROUTER_API_KEY=... (optional fallback)
```

### 3. Start Odoo (Accounting)
```bash
docker run -d --name odoo-db \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo123 \
  -e POSTGRES_DB=postgres postgres:15

docker run -d --name odoo17 --link odoo-db:db \
  -p 8069:8069 -e HOST=db -e USER=odoo -e PASSWORD=odoo123 \
  -v odoo-data:/var/lib/odoo odoo:17
# Open http://localhost:8069
```

### 4. Run AI Employee
```bash
# Single demo pass
python main.py --demo

# Live interactive mode
python main.py --live

# Start gmail watcher
python gmail_watcher.py
```

### 5. Test Odoo MCP
```bash
python odoo_mcp.py --test
# Expected: 7/7 tests pass, Mode: LIVE
```

---

## Project Structure

```
AI_Employee/
├── main.py                    # Master pipeline orchestrator
├── gmail_watcher.py           # Gmail sentinel (OAuth)
├── filesystem_watcher.py      # File drop watcher
├── cloud_agent.py             # Cloud zone agent (draft-only)
├── cloud_run_entry.py         # Google Cloud Run entry point
├── local_agent.py             # Local zone agent (approvals + send)
├── odoo_mcp.py                # Odoo accounting MCP server
├── agents.py                  # THINKER→PLANNER→EXECUTOR→REVIEWER
├── ralph_loop.py              # Ralph Wiggum autonomous loop
├── claim_manager.py           # Atomic task claiming
├── channel_dispatcher.py      # Route to email/WhatsApp/social
├── Dockerfile.cloudrun        # Google Cloud Run image
├── deploy_gcp.sh              # One-command GCP deployment
├── requirements.txt           # Full dependencies
├── requirements.cloud.txt     # Minimal cloud deps
└── AI_Employee_Vault/
    ├── Dashboard.md           # Real-time CEO view
    ├── Company_Handbook.md    # Rules of engagement
    ├── Needs_Action/
    │   └── cloud/             # Cloud agent queue
    ├── Plans/
    │   └── cloud/             # Cloud-generated plans
    ├── Pending_Approval/
    │   └── cloud/             # Awaiting local approval
    ├── Approved/              # Ready to execute
    ├── Done/                  # Completed tasks
    ├── Updates/               # Cloud→Local status updates
    ├── Signals/               # Health alerts
    └── Logs/                  # Audit trail
```

---

## Cloud Deployment (Platinum)

### Deploy to Google Cloud Run (FREE)
```bash
cd AI_Employee

# Set required env vars
export GROQ_API_KEY="your_groq_key"
export GIT_TOKEN="your_github_pat"

# Encode Gmail credentials
export GMAIL_CREDENTIALS_B64=$(base64 -w 0 credentials.json)
export GMAIL_TOKEN_B64=$(base64 -w 0 token.json)

# Edit PROJECT_ID in deploy_gcp.sh then:
chmod +x deploy_gcp.sh
./deploy_gcp.sh
```

**Result:** Cloud Run Job executes every 5 min automatically, 24/7, within free tier.

### GitHub Actions CI/CD
Auto-deploys on every push to `master` (see `.github/workflows/deploy-cloudrun.yml`).

Required GitHub Secrets:
- `GCP_PROJECT_ID`
- `GCP_SA_KEY` (service account JSON)
- `GROQ_API_KEY`
- `GIT_TOKEN`
- `GMAIL_CREDENTIALS_B64`
- `GMAIL_TOKEN_B64`

---

## Security Architecture

| What | How |
|------|-----|
| API Keys | `.env` file, never committed (`.gitignore`) |
| Gmail OAuth | `credentials.json` / `token.json` — in `.gitignore` |
| Cloud secrets | Base64-encoded env vars in Cloud Run (not in code) |
| Git sync | Only markdown/state files sync; secrets never leave local |
| Payments | Always require human approval — auto-approve threshold: $0 |
| Audit log | Every action logged to `/Logs/YYYY-MM-DD.json` (90-day retention) |
| HITL | All sensitive actions → `/Pending_Approval/` → human moves to `/Approved/` |

---

## Platinum Demo Flow

```
1. Email arrives (while Local is offline)
       ↓
2. Cloud Run Job triggers (every 5 min)
   Gmail API → fetches email → Needs_Action/cloud/EMAIL_xxx.md
       ↓
3. AI Pipeline (Groq/Llama3 FREE)
   THINKER → PLANNER → EXECUTOR → REVIEWER (8/10 quality)
   Draft reply → Pending_Approval/cloud/ACTION_xxx.md
       ↓
4. Git commit + push → hackathon-0 repo
       ↓
5. Local machine comes online → git pull
   User sees: Pending_Approval/cloud/ACTION_xxx.md
       ↓
6. User approves (moves to Approved/) OR rejects
       ↓
7. Local agent executes → sends email via Gmail MCP
   Logs action → moves task to Done/
       ↓
8. Git push → cloud sees completion
```

---

## Running Tests

```bash
# Test full pipeline
python main.py --demo

# Test Odoo MCP (7/7 tests)
python odoo_mcp.py --test

# Test cloud agent
python cloud_agent.py --test

# Test email sending
python email_sender.py --test
```

---

## Architecture Deep Dive

See `Plans/ARCHITECTURE_AI_Employee.md` for full technical documentation.

See `AI_Employee/LESSONS_LEARNED.md` for retrospective notes.

---

*Built with Claude Code + Obsidian + Groq + Odoo Community*
*Hackathon 0 — Personal AI Employee (Platinum Tier)*
