# AI Employee — Gold Tier

> Full cross-domain autonomous AI employee with Odoo accounting, social media integration, Ralph Wiggum loop, and CEO briefings.

## What's Included

| Component | Description |
|-----------|-------------|
| `orchestrator.py` | Master process coordinator |
| `ralph_loop.py` | Autonomous multi-step task loop |
| `watchers/` | Gmail, WhatsApp, Finance, File watchers |
| `mcp-servers/email-mcp/` | Gmail send/draft MCP |
| `mcp-servers/social-mcp/` | Facebook/Instagram/Twitter MCP |
| `mcp-servers/odoo-mcp/` | Odoo 19+ JSON-RPC MCP (draft-only) |
| `error_recovery/` | Retry handler + Watchdog process |
| `accounting/` | Subscription audit + report generation |
| `.claude/commands/` | 11 Agent Skills |

## Folder Structure

```
gold-tier/
├── Inbox/              ← Drop files here
├── Needs_Action/       ← Claude processes these
├── Plans/              ← Multi-step task plans
├── Pending_Approval/   ← Awaiting human approval
├── Approved/           ← Execute these
├── Rejected/           ← Cancelled actions
├── Done/               ← Completed tasks
├── Briefings/          ← Daily/weekly reports
├── Accounting/         ← Financial snapshots
└── Logs/               ← JSON audit trail
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
npm install --prefix mcp-servers/email-mcp
npm install --prefix mcp-servers/social-mcp
npm install --prefix mcp-servers/odoo-mcp
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Configure MCP Servers in Claude Code
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

### 4. Start the System
```bash
# Start orchestrator (runs all watchers + triggers Claude)
python orchestrator.py

# Start watchdog in another terminal
python error_recovery/watchdog.py

# Or run autonomous task loop
python ralph_loop.py "Process all pending items" --max-iterations 5
```

### 5. Use Agent Skills in Claude Code
```
/process-inbox          → Process all pending items
/daily-briefing         → Generate morning briefing
/ceo-briefing           → Monday CEO report
/weekly-audit           → Weekly business audit
/post-social twitter    → Draft tweet (needs approval)
/odoo-sync              → Sync with Odoo accounting
/ralph-loop <task>      → Autonomous task completion
```

## Security

- All credentials in `.env` — never in vault markdown
- All payments and posts require human approval (HITL)
- Odoo MCP is draft-only by default (`ODOO_DRAFT_ONLY=true`)
- Rate limits prevent runaway API calls
- Full JSON audit log in `/Logs/`

## Agent Skills Reference

| Skill | Command | Autonomy |
|-------|---------|----------|
| Process Inbox | `/process-inbox` | Auto |
| Complete Task | `/complete-task <file>` | Auto |
| Update Dashboard | `/update-dashboard` | Auto |
| Daily Briefing | `/daily-briefing` | Auto |
| Weekly Audit | `/weekly-audit` | Auto |
| CEO Briefing | `/ceo-briefing` | Auto |
| Create Plan | `/create-plan <task>` | Auto |
| Post Social | `/post-social <platform>` | Needs Approval |
| Request Approval | `/request-approval <type>` | Needs Approval |
| Odoo Sync | `/odoo-sync` | Auto (read) |
| Ralph Loop | `/ralph-loop <task>` | Autonomous |
