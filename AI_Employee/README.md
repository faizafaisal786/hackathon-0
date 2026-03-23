# AI Employee — Personal Autonomous FTE (Platinum Tier)

> **Hackathon:** Building Autonomous FTEs in 2026
> **Tier:** PLATINUM — Always-On, 4-Agent Pipeline
> **Stack:** Claude Code · Obsidian · Groq (Free) · Python

A fully autonomous AI agent that manages personal and business operations 24/7.
It monitors emails, drafts social media posts, sends WhatsApp messages, and generates
weekly CEO briefings — all with a human-in-the-loop approval gate.

---

## Architecture

```
INPUT LAYER
  Gmail Watcher → filesystem_watcher → local_approval_watcher
        │
        ▼
  Obsidian Vault (File-Based State Machine)
  ┌──────────────────────────────────────────────────────┐
  │  Inbox → Needs_Action → Pending_Approval → Approved  │
  │                                        ↘             │
  │                                      Rejected        │
  │                                         ↓            │
  │                                        Done          │
  └──────────────────────────────────────────────────────┘
        │
        ▼
  4-AGENT PIPELINE (PLATINUM)
  THINKER → PLANNER → EXECUTOR → REVIEWER
        │
        ▼
  CHANNELS: Email · WhatsApp · LinkedIn · Facebook · Instagram · Twitter/X
```

---

## Hackathon Tier Status

| Tier | Requirements | Status |
|------|-------------|--------|
| **Bronze** | Vault, Watcher, Claude R/W, Folder Structure | ✅ Complete |
| **Silver** | Multi-Watcher, LinkedIn, HITL Approval, Scheduling | ✅ Complete |
| **Gold** | Cross-domain, Social Media, Ralph Loop, CEO Briefing | ✅ Complete |
| **Platinum** | 4-Agent Pipeline, Memory, Self-Improvement, Cloud Scripts | ✅ Complete |

---

## Features

### Core Pipeline
- **Inbox → Done** in 4 automated stages
- **Human-in-the-loop** approval before any external action
- **Ralph Wiggum Loop** — continuous autonomous iteration until task complete
- **4-Agent Pipeline**: Thinker → Planner → Executor → Reviewer

### Communication Channels
| Channel | Mode | Description |
|---------|------|-------------|
| Email | Live / Simulation | Gmail SMTP or demo mode |
| WhatsApp | Live / wa.me link | Twilio API or one-click link |
| LinkedIn | Live / Copy-ready | UGC API or markdown file |
| Facebook | Copy-ready | AI-generated post ready to paste |
| Instagram | Copy-ready | Caption + hashtags + image idea |
| Twitter/X | Live / Copy-ready | Tweepy API or ready-to-post file |

### Intelligence
- **Memory System** — learns from past task outcomes
- **Self-Improvement** — auto-improves prompts every 10 passes
- **CEO Weekly Briefing** — auto-generates every Monday
- **Groq (Free)** as primary AI backend (llama-3.3-70b-versatile)
- **Gemini (Free)** as secondary fallback

### Security
- All credentials in `.env` (never in code, never committed)
- HITL gate: AI cannot send anything without human approval
- Company_Handbook.md defines business rules for the AI
- Full audit trail in `Logs/YYYY-MM-DD.json`
- Simulation fallback — never crashes without credentials

---

## Quick Start

### 1. Install Dependencies
```bash
cd AI_Employee
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env — minimum: set GROQ_API_KEY (free at console.groq.com)
```

### 3. Run Demo (Auto-approves everything)
```bash
python main.py --demo
```

### 4. Run Interactive (Human approves each task)
```bash
python main.py --live
```

### 5. Always-On Loop (Platinum)
```bash
python ralph_loop.py
```

### 6. Check Pipeline Status
```bash
python main.py --status
```

---

## Project Structure

```
Obsidian Vaults/
│
├── AI_Employee/                    ← Application Code
│   ├── main.py                     # 4-stage pipeline orchestrator
│   ├── ralph_loop.py               # Always-on daemon loop (PLATINUM)
│   ├── claude_runner.py            # AI Brain: analyze + plan + draft
│   ├── executor.py                 # Approved → Send via channel
│   ├── channel_dispatcher.py       # Single source: detect + dispatch
│   ├── email_sender.py             # Gmail SMTP
│   ├── whatsapp_sender.py          # Twilio WhatsApp
│   ├── linkedin_sender.py          # LinkedIn UGC API
│   ├── twitter_sender.py           # Twitter/X API (Tweepy)
│   ├── social_media_sender.py      # Facebook, Instagram (copy-ready)
│   ├── briefing_generator.py       # Weekly CEO Briefing
│   ├── memory_manager.py           # Task memory & learning
│   ├── self_improvement.py         # Auto prompt optimization
│   ├── agents.py                   # 4-agent PLATINUM pipeline
│   ├── config.py                   # All settings
│   ├── workflow.py                 # State machine engine
│   ├── state_machine.py            # File-based state transitions
│   ├── run_pipeline.py             # Pipeline stage runners
│   ├── dashboard.py                # Dashboard.md updater
│   ├── .env.example                # Credentials template
│   └── requirements.txt            # Dependencies
│
├── AI_Employee_Vault/              ← Data Vault (State Machine)
│   ├── Inbox/                      # Stage 0: Raw incoming
│   ├── Needs_Action/               # Stage 1: Queued for AI
│   ├── Plans/                      # Audit trail (PLAN_*.md)
│   ├── Pending_Approval/           # Stage 3: Awaiting human
│   ├── Approved/                   # Human said YES
│   ├── Rejected/                   # Human said NO
│   ├── Done/                       # Completed (archive)
│   ├── Logs/                       # Daily JSON audit logs
│   ├── Briefings/                  # Weekly CEO reports
│   ├── LinkedIn_Posts/             # LinkedIn simulation files
│   ├── WhatsApp_Sent/              # WhatsApp simulation files
│   └── Twitter_Posts/              # Twitter copy-ready files
│
├── Dashboard.md                    ← Live Pipeline Status
├── Company_Handbook.md             ← AI Business Rules
├── gmail_watcher.py                ← Gmail API poller
├── filesystem_watcher.py           ← OS file watcher (watchdog)
├── local_approval_watcher.py       ← Approval detector (Platinum)
├── cloud_setup.sh                  ← Cloud VM setup script
└── cloud_sync.sh                   ← Git auto-sync (30s)
```

---

## Adding a Task

Drop any `.md` file into `AI_Employee/AI_Employee_Vault/Inbox/`:

**Email task:**
```markdown
# Task: Reply to Client
**Type:** EMAIL
**To:** client@example.com
**Subject:** Project Update

Write a professional update about milestone 2 completion.
```

**Twitter task:**
```markdown
# Task: Post Launch Announcement
**Type:** TWITTER
**Author:** AI Employee Team
**Topic:** Product Launch
**Hashtags:** #AI #Launch #Automation

Announce the launch of our AI Employee system. Highlight 85% cost savings.
```

**LinkedIn task:**
```markdown
# Task: Weekly LinkedIn Post
**Type:** LINKEDIN
**Author:** AI Employee Team
**Topic:** Automation Insights

Write about how AI automation is transforming small businesses in 2026.
```

The Ralph Loop picks it up, generates a draft, and moves it to `Pending_Approval/`. You review and approve (or reject) from Obsidian.

---

## Platinum Cloud Deployment

### Step 1: Initialize Git Repo (Local)
```bash
bash setup_git_repo.sh
git remote add origin git@github.com:YOUR_USER/ai-employee-vault.git
git push -u origin main
```

### Step 2: Provision Cloud VM
- **Oracle Cloud Free Tier** (recommended — always free)
- **AWS EC2 t2.micro** (free tier 12 months)
- **GCP e2-micro** (always free)

### Step 3: Deploy to VM
```bash
scp cloud_setup.sh user@YOUR_VM_IP:~/
ssh user@YOUR_VM_IP "bash cloud_setup.sh"
```

### Step 4: Start Local Approval Watcher
```bash
python local_approval_watcher.py
```

### Step 5: System is Live 24/7
Cloud VM processes tasks → Git syncs state → You approve in Obsidian → Cloud executes.

---

## CEO Weekly Briefing

Auto-generated every Monday by the Ralph Loop. Contains:
- Tasks completed this week (by channel)
- Success rate and quality scores
- Bottlenecks (tasks that took longest)
- Channel performance breakdown
- Recommendations for next week

Saved to: `AI_Employee_Vault/Briefings/Briefing_YYYY-MM-DD.md`

Manual generation:
```bash
python briefing_generator.py
```

---

## Security

| Concern | Solution |
|---------|----------|
| API credentials | `.env` file, gitignored |
| Email sending | Human approval required |
| Payment actions | Hardcoded block in Company_Handbook |
| Over $100 transactions | Mandatory human approval |
| Audit trail | Immutable JSON logs |
| No credentials? | Auto-simulation, never crashes |

---

## Judging Criteria Compliance

| Criterion | Implementation |
|-----------|---------------|
| **Functionality (30%)** | All 6 channels work (live + simulation), full 4-stage pipeline |
| **Innovation (25%)** | 4-agent PLATINUM pipeline, memory system, self-improvement |
| **Practicality (20%)** | Obsidian vault = real dashboard, wa.me links, copy-ready posts |
| **Security (15%)** | HITL gate, .env isolation, audit logs, Company_Handbook rules |
| **Documentation (10%)** | This README + architecture doc in Plans/ |

---

## Submission

- **Tier:** PLATINUM (4-agent pipeline, memory, self-improvement, cloud scripts)
- **Demo:** `python main.py --demo`
- **Always-On:** `python ralph_loop.py`
- **Submit Form:** https://forms.gle/JR9T1SJq5rmQyGkGA

---

*Built for Hackathon 0: Building Autonomous FTEs in 2026 | Powered by Claude Code + Groq*
