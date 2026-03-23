# AI Employee — Platinum Tier

> Always-on Cloud + Local AI Employee. Cloud drafts 24/7. Local approves and executes. Full Odoo integration. Git-synced vault.

## Architecture Overview

```
CLOUD VM (24/7)                    LOCAL MACHINE
┌──────────────────┐              ┌──────────────────────┐
│  cloud_agent.py  │◄──Git sync──►│  local_agent.py      │
│  Watchers        │              │  local_approval_      │
│  Email triage    │              │  watcher.py           │
│  Social drafts   │   /Updates/  │  WhatsApp session     │
│  Odoo (read)     │──────────────►  Payments / Banking   │
│  Draft approvals │              │  Final send/post      │
└──────────────────┘              └──────────────────────┘
         │                                    │
         └────────── /Pending_Approval/ ──────┘
                     Human approves here
```

## What's New in Platinum vs Gold

| Feature | Gold | Platinum |
|---------|------|----------|
| Always-on | ❌ Local only | ✅ Cloud 24/7 |
| Multi-agent | ❌ Single | ✅ Cloud + Local |
| Vault sync | ❌ | ✅ Git/Syncthing |
| Claim-by-move | ❌ | ✅ No double-work |
| Odoo on cloud | ❌ | ✅ Docker |
| Domain queues | ❌ | ✅ email/social/finance |
| Docker deploy | ❌ | ✅ Full compose |
| HTTPS Odoo | ❌ | ✅ Nginx + SSL |

## Quick Start

### 1. Local Setup
```bash
cd platinum-tier
pip install -r requirements.txt
cp .env.example .env     # Add your credentials
python local/local_agent.py
python local/local_approval_watcher.py   # In another terminal
```

### 2. Cloud VM Setup (Oracle Cloud Free Tier / AWS / etc.)
```bash
# On cloud VM:
git clone <your-vault-repo> /vault
cd /vault/platinum-tier
cp .env.example .env     # Add cloud credentials (NOT banking/WhatsApp)
docker-compose up -d
```

### 3. Initialize Vault Sync
```bash
export VAULT_REPO_URL=git@github.com:youruser/your-vault.git
chmod +x sync/setup_git_sync.sh
./sync/setup_git_sync.sh
```

### 4. Configure Claude Code MCP
Add to `~/.config/claude-code/mcp.json`:
```json
{
  "servers": [
    { "name": "email", "command": "node", "args": ["mcp-servers/email-mcp/index.js"] },
    { "name": "social", "command": "node", "args": ["mcp-servers/social-mcp/index.js"] },
    { "name": "odoo", "command": "node", "args": ["mcp-servers/odoo-mcp/index.js"] }
  ]
}
```

## Folder Structure

```
platinum-tier/
├── cloud/                  ← Cloud agent code + Docker
│   ├── cloud_agent.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── cloud_sync.sh
├── local/                  ← Local agent code
│   ├── local_agent.py
│   └── local_approval_watcher.py
├── sync/                   ← Vault sync setup
│   ├── setup_git_sync.sh
│   └── syncthing_notes.md
├── watchers/               ← All input watchers
├── mcp-servers/            ← Email, Social, Odoo MCPs
├── error_recovery/         ← Retry + Watchdog
├── accounting/             ← Audit logic
├── .claude/commands/       ← 12 Agent Skills
├── Needs_Action/
│   ├── email/              ← Cloud's domain
│   ├── social/             ← Cloud's domain
│   └── finance/            ← Local's domain
├── Plans/
│   ├── email/
│   └── social/
├── Pending_Approval/       ← Human approves here
├── In_Progress/
│   ├── cloud/              ← Cloud's claimed items
│   └── local/              ← Local's claimed items
├── Updates/                ← Cloud → Local messages
├── Done/
├── Briefings/
├── Accounting/
└── Logs/
```

## Security Model

| Rule | Details |
|------|---------|
| Secrets | `.env` only, never in vault markdown |
| Vault sync | `.md` and `.json` files only |
| Payments | Always HITL, LOCAL only |
| Social post | Always HITL, LOCAL executes |
| Odoo writes | Draft-only from Cloud |
| Claim-by-move | Prevents double-processing |
| Single writer | Only Local writes Dashboard.md |

## Agent Skills Reference (12 Skills)

| Skill | Who | Autonomy |
|-------|-----|----------|
| `/process-inbox` | Both | Auto (domain-scoped) |
| `/claim-task` | Both | Auto |
| `/complete-task` | Both | Auto |
| `/update-dashboard` | Local Only | Auto |
| `/daily-briefing` | Both | Auto |
| `/ceo-briefing` | Cloud drafts + Local | Semi-auto |
| `/weekly-audit` | Cloud drafts + Local | Semi-auto |
| `/create-plan` | Both | Auto |
| `/post-social` | Cloud drafts + Local | Needs Approval |
| `/request-approval` | Both | Needs Human |
| `/ralph-loop` | Both | Autonomous |
| `/cloud-sync` | Both | Auto |
