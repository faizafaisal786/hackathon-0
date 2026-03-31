<div align="center">

<img src="https://img.shields.io/badge/Tier-PLATINUM-blueviolet?style=for-the-badge&logo=star&logoColor=white" />
<img src="https://img.shields.io/badge/Status-100%25%20Complete-success?style=for-the-badge&logo=checkmarx&logoColor=white" />
<img src="https://img.shields.io/badge/AI-Claude%20%2B%20Groq-orange?style=for-the-badge&logo=anthropic&logoColor=white" />
<img src="https://img.shields.io/badge/Cost-$0%2FMonth-brightgreen?style=for-the-badge&logo=googlepay&logoColor=white" />

<br/><br/>

# 🤖 Digital FTE — Personal AI Employee

### *Your life and business on autopilot. Local-first, agent-driven, human-in-the-loop.*

<br/>

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Powered-FF6B35?style=flat-square&logo=anthropic&logoColor=white)](https://claude.ai)
[![Groq](https://img.shields.io/badge/Groq-Llama3_Free-F55036?style=flat-square&logo=groq&logoColor=white)](https://groq.com)
[![Obsidian](https://img.shields.io/badge/Obsidian-Vault-7C3AED?style=flat-square&logo=obsidian&logoColor=white)](https://obsidian.md)
[![PM2](https://img.shields.io/badge/PM2-7%2F7_Online-2B037A?style=flat-square&logo=pm2&logoColor=white)](https://pm2.keymetrics.io)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<br/>

> **Hackathon 0** — Panaversity · Building Autonomous FTEs in 2026

</div>

---

## ✨ What is this?

A **fully autonomous AI employee** that works **24/7** — monitoring your Gmail, drafting replies, posting to LinkedIn/Twitter/Facebook/Instagram, managing WhatsApp, generating weekly CEO briefings, and handling Odoo accounting — all with a **human-in-the-loop approval gate** so you stay in control.

> Think of it as hiring a senior employee who figures out how to solve problems, works 168 hours/week, and costs **$0/month**.

---

## 🏆 Tier Achievement

<div align="center">

| Tier | Status | Key Feature |
|:----:|:------:|:------------|
| 🥉 **Bronze** | ✅ Complete | Vault + Gmail Watcher + Agent Skills |
| 🥈 **Silver** | ✅ Complete | WhatsApp + LinkedIn + MCP Servers + HITL |
| 🥇 **Gold** | ✅ Complete | Odoo Accounting + Social Media + Ralph Loop |
| 💎 **Platinum** | ✅ **25/25 PASS** | Cloud/Local Split + A2A + Always-On 24/7 |

</div>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               ☁️  CLOUD  (Google Cloud Run — FREE)           │
│                                                             │
│   Gmail API ──► AI Pipeline (Groq/Llama3)                   │
│   THINKER ──► PLANNER ──► EXECUTOR ──► REVIEWER             │
│   Draft reply ──► Pending_Approval/cloud/  ──► Git Push      │
└──────────────────────┬──────────────────────────────────────┘
                       │  GitHub Vault Sync
                       │  (only .md files — secrets never sync)
┌──────────────────────▼──────────────────────────────────────┐
│               🏠  LOCAL  (Human-in-the-Loop)                 │
│                                                             │
│   Git Pull ──► Review ──► Approve / Reject                  │
│   Send Email · WhatsApp · Payments · Dashboard.md           │
│   Odoo MCP ──► Accounting · Invoices (Docker)               │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚡ Tech Stack

<div align="center">

| Layer | Tool | Cost |
|:-----:|:----:|:----:|
| 🧠 Brain | Groq / Llama3-70b + Claude fallback | **FREE** |
| 📁 Memory / GUI | Obsidian (local Markdown) | **FREE** |
| ☁️ Cloud Runtime | Google Cloud Run Jobs | **FREE** |
| 🕐 Scheduler | Google Cloud Scheduler | **FREE** |
| 🔄 Vault Sync | Git / GitHub | **FREE** |
| 💼 Accounting | Odoo 17 Community (Docker) | **FREE** |
| 📧 Email | Gmail API (OAuth) | **FREE** |
| 📱 WhatsApp | Playwright (no Twilio) | **FREE** |
| 📣 Social | LinkedIn · Twitter · Facebook · Instagram | **FREE tier** |
| ⚙️ Process Mgr | PM2 (7 always-on processes) | **FREE** |

</div>

---

## 📊 Live Stats

<div align="center">

| Metric | Value |
|:------:|:-----:|
| ✅ Tasks Completed | **504** |
| 📋 Plans Generated | **281** |
| 💰 Revenue Logged | **PKR 504,944** |
| 🧾 Invoices | **15** |
| 👥 Customers | **8** |
| 🤖 PM2 Processes | **7 / 7 Online** |
| 🏆 Platinum Score | **25 / 25 (100%)** |

</div>

---

## 🚀 Quick Start (5 minutes)

### Prerequisites

```bash
python --version    # 3.13+
node --version      # 24+
docker --version    # latest
claude --version    # Claude Code
pm2 --version       # npm install -g pm2
```

### 1. Clone & Install

```bash
git clone https://github.com/faizafaisal786/hackathon-0.git
cd hackathon-0/AI_Employee
pip install -r requirements.txt
```

### 2. Setup Environment

```bash
cp .env.example .env
# Edit .env — add your free API keys:
# GROQ_API_KEY=...     → free at console.groq.com
# GMAIL_USER=...       → your Gmail address
```

### 3. Start Odoo Accounting (Docker)

```bash
docker run -d --name odoo-db \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo123 \
  -e POSTGRES_DB=postgres postgres:15

docker run -d --name odoo17 --link odoo-db:db \
  -p 8069:8069 odoo:17
# Open → http://localhost:8069
```

### 4. Launch AI Employee

```bash
# Start all 7 background processes (always-on)
pm2 start ecosystem.config.js
pm2 save

# Run demo pipeline
python main.py --demo

# Test Odoo MCP (7/7 tests)
python odoo_mcp.py --test
```

### 5. Verify Platinum (100%)

```bash
python verify_platinum.py
# Expected: 25/25 checks PASSED ✅
```

---

## 📁 Project Structure

```
hackathon-0/
│
├── 📂 AI_Employee/                    # Main platinum-tier engine
│   ├── 🐍 main.py                     # Master pipeline orchestrator
│   ├── 🐍 agents.py                   # THINKER→PLANNER→EXECUTOR→REVIEWER
│   ├── 🐍 gmail_watcher.py            # Gmail sentinel (OAuth)
│   ├── 🐍 whatsapp_watcher.py         # WhatsApp watcher (Playwright)
│   ├── 🐍 filesystem_watcher.py       # File drop watcher
│   ├── 🐍 cloud_agent.py              # Cloud zone agent (draft-only)
│   ├── 🐍 local_agent.py              # Local zone agent (approve + send)
│   ├── 🐍 odoo_mcp.py                 # Odoo accounting MCP (8 tools)
│   ├── 🐍 ralph_loop.py               # Ralph Wiggum autonomous loop
│   ├── 🐍 claim_manager.py            # Atomic task claiming
│   ├── 🐍 briefing_generator.py       # Monday CEO briefing
│   ├── 🐍 a2a_agent.py                # A2A Phase 2 direct messaging
│   ├── 🐍 platinum_demo.py            # End-to-end demo script
│   ├── 🐍 verify_platinum.py          # 25/25 verification checks
│   ├── 🌐 dashboard_ui.html           # Digital FTE web dashboard
│   ├── ⚙️  ecosystem.config.js         # PM2 process manager config
│   └── 📂 AI_Employee_Vault/          # Obsidian vault (live state)
│       ├── 📄 Dashboard.md            # Real-time CEO view
│       ├── 📄 Company_Handbook.md     # Rules of engagement
│       ├── 📂 Needs_Action/cloud/     # Cloud agent queue
│       ├── 📂 Plans/                  # AI-generated plans
│       ├── 📂 Pending_Approval/       # Awaiting human approval
│       ├── 📂 Approved/               # Ready to execute
│       ├── 📂 Done/                   # Completed (504 tasks)
│       ├── 📂 Updates/                # Cloud→Local status
│       ├── 📂 Signals/                # Health alerts
│       └── 📂 Logs/                   # Audit trail (JSON)
│
├── 📂 bronze-tier/                    # Bronze standalone
├── 📂 silver-tier/                    # Silver standalone
├── 📂 gold-tier/                      # Gold standalone
├── 📂 platinum-tier/                  # Platinum standalone
└── 📄 README.md                       # You are here
```

---

## 🔄 Platinum Demo Flow

```
1. 📧 Email arrives (Local is offline)
          ↓
2. ☁️  Cloud Run triggers every 5 min
   Gmail API → Needs_Action/cloud/EMAIL_xxx.md
          ↓
3. 🤖 4-Agent AI Pipeline (Groq — FREE)
   THINKER → PLANNER → EXECUTOR → REVIEWER
   Quality score: 8.5/10
   Draft → Pending_Approval/cloud/ACTION_xxx.md
          ↓
4. 🔄 Git commit + push → GitHub repo
          ↓
5. 🏠 Local machine comes online → git pull
   User sees: Pending_Approval/cloud/ACTION_xxx.md
          ↓
6. ✅ User APPROVES → moves to Approved/
   ❌ Or REJECTS → moves to Rejected/
          ↓
7. 📤 Local Agent executes → sends email via MCP
   Logs → moves task to Done/
          ↓
8. 🔄 Git push → Cloud sees completion
```

---

## 🛡️ Security Architecture

<div align="center">

| What | How | Status |
|:-----|:----|:------:|
| API Keys | `.env` file — never committed | ✅ Safe |
| Gmail OAuth | `credentials.json` — in `.gitignore` | ✅ Safe |
| Cloud Secrets | Base64 env vars in Cloud Run | ✅ Safe |
| Git Sync | Only `.md` state files — secrets excluded | ✅ Safe |
| Payments | Always require human approval ($0 auto) | ✅ Safe |
| Audit Log | Every action → `/Logs/YYYY-MM-DD.json` | ✅ Active |
| WhatsApp | Session never synced to cloud | ✅ Safe |

</div>

---

## 📅 Hackathon Info

> **Panaversity — Hackathon 0: Building Autonomous FTEs in 2026**
>
> Research & Showcase: Every **Wednesday 10:00 PM** (Zoom)
>
> 🔗 [Join Zoom Meeting](https://us06web.zoom.us/j/87188707642?pwd=a9XloCsinvn1JzICbPc2YGUvWTbOTr.1) · Meeting ID: `871 8870 7642` · Passcode: `744832`
>
> 📺 [Watch on YouTube](https://www.youtube.com/@panaversity) *(live + recordings)*

---

## 💡 Human FTE vs Digital FTE

<div align="center">

| Feature | 👤 Human FTE | 🤖 Digital FTE |
|:--------|:------------:|:--------------:|
| Availability | 40 hrs/week | **168 hrs/week** |
| Monthly Cost | $4,000–$8,000 | **$0–$500** |
| Ramp-up Time | 3–6 months | **Instant** |
| Consistency | 85–95% | **99%+** |
| Scaling | Linear | **Exponential** |
| Annual Hours | ~2,000 | **~8,760** |

> 💰 **85–90% cost reduction** — the threshold where a CEO approves without debate.

</div>

---

## 🧪 Running Tests

```bash
# Full pipeline demo
python main.py --demo

# Platinum verification (25/25)
python verify_platinum.py

# Odoo MCP (7/7 tests)
python odoo_mcp.py --test

# A2A round-trip (HTTP + vault)
python a2a_agent.py --test

# Cloud agent test
python cloud_agent.py --test
```

---

<div align="center">

**Built with ❤️ using Claude Code + Obsidian + Groq + Odoo Community**

*Hackathon 0 — Personal AI Employee (Platinum Tier) · Panaversity 2026*

<br/>

[![GitHub stars](https://img.shields.io/github/stars/faizafaisal786/hackathon-0?style=social)](https://github.com/faizafaisal786/hackathon-0/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/faizafaisal786/hackathon-0?style=social)](https://github.com/faizafaisal786/hackathon-0/network)

</div>
