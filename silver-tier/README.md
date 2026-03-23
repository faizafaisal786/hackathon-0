# Personal AI Employee — Silver Tier

**Estimated Setup Time:** 20–30 hours
**Tier Level:** Silver (Integrated Automation)
**Prerequisites:** Bronze Tier running successfully

---

## What's New in Silver

| Feature | Bronze | Silver |
|---|---|---|
| File system watcher | Yes | Yes (enhanced) |
| Gmail integration | No | **Yes** |
| LinkedIn monitoring + drafting | No | **Yes** |
| Reasoning loop (Plan.md) | No | **Yes** |
| Email MCP server (send emails) | No | **Yes** |
| Human-in-the-loop approvals | Manual | **Structured workflow** |
| Automated scheduling | No | **Yes (cron-style)** |
| LinkedIn auto-post drafts | No | **Yes** |

---

## Folder Structure

```
silver-tier/
├── .claude/
│   └── commands/               # Agent Skills
│       ├── process-inbox.md
│       ├── complete-task.md
│       ├── update-dashboard.md
│       ├── daily-briefing.md
│       ├── create-plan.md      ← NEW
│       ├── post-linkedin.md    ← NEW
│       └── request-approval.md ← NEW
├── mcp-servers/
│   └── email-mcp/
│       └── index.js            ← Node.js MCP server
├── watchers/
│   ├── base_watcher.py
│   ├── filesystem_watcher.py
│   ├── gmail_watcher.py        ← NEW
│   └── linkedin_watcher.py     ← NEW
├── Inbox/
├── Needs_Action/
├── Done/
├── Plans/                      ← NEW
├── Pending_Approval/           ← NEW
├── Approved/                   ← NEW
├── Rejected/                   ← NEW
├── Logs/
├── orchestrator.py             ← Runs all watchers
├── scheduler.py                ← Cron-style job scheduler
├── Dashboard.md
├── Company_Handbook.md
├── Business_Goals.md           ← NEW
├── SKILL.md
└── requirements.txt
```

---

## Setup Instructions

### Step 1 — Install Python Dependencies

```bash
cd silver-tier
pip install -r requirements.txt
playwright install chromium  # For LinkedIn watcher
```

### Step 2 — Install Node.js MCP Server Dependencies

```bash
cd mcp-servers/email-mcp
npm init -y
npm install @modelcontextprotocol/sdk googleapis dotenv
```

### Step 3 — Configure Environment Variables

Create `silver-tier/.env`:

```env
# Vault
VAULT_PATH=C:/Users/YourName/Desktop/silver-tier

# Filesystem watcher
WATCH_PATH=C:/Users/YourName/Desktop/AI_Inbox
ENABLE_FILESYSTEM=true

# Gmail (requires Google Cloud OAuth setup)
ENABLE_GMAIL=false
GMAIL_LABEL=INBOX
GMAIL_MAX_RESULTS=10

# LinkedIn (requires Playwright session)
ENABLE_LINKEDIN=false
LINKEDIN_COOKIE=          # Paste your li_at cookie value
# OR:
# LINKEDIN_EMAIL=your@email.com
# LINKEDIN_PASSWORD=yourpassword  (use env only, never commit)

# Scheduling
POLL_INTERVAL=120

# Safety
DRY_RUN=false
AUTO_TRIGGER_CLAUDE=false
```

### Step 4 — Set Up Gmail OAuth (if using Gmail watcher)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable **Gmail API**
4. Create **OAuth 2.0 Client ID** (Desktop app type)
5. Download as `credentials.json`
6. Place `credentials.json` in `watchers/` folder
7. Run once manually to complete OAuth:
   ```bash
   cd watchers && python gmail_watcher.py
   ```
   A browser window will open — authorize access.
   `token.json` will be created automatically.

**Important:** Never commit `credentials.json` or `token.json` to git.

### Step 5 — Register MCP Server with Claude Code

Add to your Claude Code settings (`.claude/settings.json` or via `claude config`):

```json
{
  "mcpServers": {
    "email": {
      "command": "node",
      "args": ["C:/path/to/silver-tier/mcp-servers/email-mcp/index.js"]
    }
  }
}
```

Or run interactively:
```bash
claude mcp add email node mcp-servers/email-mcp/index.js
```

### Step 6 — Configure Your Business Files

**Edit these files before first run:**
- `Company_Handbook.md` — Fill in your business name, industry, tone rules
- `Business_Goals.md` — Fill in your actual goals, KPIs, target audience
- Review `Dashboard.md` — Initial state is fine

### Step 7 — Start the System

**Terminal 1 — Orchestrator (all watchers):**
```bash
cd silver-tier
python orchestrator.py
```

**Terminal 2 — Scheduler:**
```bash
cd silver-tier
python scheduler.py
```

**Terminal 3 — Claude Code:**
```bash
cd silver-tier
claude
```

---

## Daily Workflow

### Morning (automated at 07:00 via scheduler):
1. Scheduler runs `/daily-briefing`
2. Claude scans all folders and delivers morning briefing

### Throughout the day:
1. Gmail Watcher deposits new emails → `Inbox/`
2. LinkedIn Watcher deposits notifications → `Inbox/`
3. Use `/process-inbox` to triage
4. Claude creates tasks in `Needs_Action/`
5. Claude creates draft emails or posts → `Pending_Approval/`
6. You review `Pending_Approval/` and move to `Approved/` or `Rejected/`
7. Claude executes approved actions via Email MCP

### When you need strategic thinking:
```
/create-plan
```
Claude will reason through the situation, analyze options, and create a Plan.md.

### For LinkedIn posting (automated Mon/Wed/Fri via scheduler):
- Draft appears in `Pending_Approval/LinkedIn_Post_[date].md`
- Review, edit if needed, move to `Approved/`
- Claude uses LinkedIn MCP (or gives you copy-paste instructions) to publish

---

## Approval Workflow

```
Claude proposes action
        │
        ▼
Pending_Approval/Approval_[type]_[date].md
        │
        ├─── You move to Approved/   ──► Claude executes
        │
        └─── You move to Rejected/  ──► Claude notes rejection, may ask for guidance
```

Approvals older than 48 hours are flagged in the daily briefing.

---

## MCP Server Usage

The Email MCP server lets Claude send emails directly. It ALWAYS:
1. Checks for an approval file in `Approved/` before sending
2. Logs all sent emails to `Logs/email_sent.log`
3. Respects `DRY_RUN=true` mode (logs without sending)

Claude will use it like:
```
Claude: I found an approved email in Approved/. Sending now via email MCP...
```

---

## Security Checklist

- [ ] `credentials.json` added to `.gitignore`
- [ ] `token.json` added to `.gitignore`
- [ ] `.env` added to `.gitignore`
- [ ] `DRY_RUN=true` during initial testing
- [ ] Review `Company_Handbook.md` approval rules before enabling `AUTO_TRIGGER_CLAUDE=true`
- [ ] LinkedIn cookie stored in env only, never in code

---

## Troubleshooting

**Gmail authentication fails:**
```bash
rm watchers/token.json
python watchers/gmail_watcher.py  # Re-authenticate
```

**LinkedIn playwright fails:**
- Try updating playwright: `playwright install chromium`
- Check if LinkedIn changed their HTML structure (update selectors in `linkedin_watcher.py`)
- Consider using the `li_at` cookie method instead of email/password

**Email MCP not available in Claude:**
- Verify MCP registration: `claude mcp list`
- Check Node.js is installed: `node --version`
- Test server directly: `node mcp-servers/email-mcp/index.js`

**Scheduler not running jobs:**
- Check `Logs/scheduler.log` for errors
- Verify system time is correct
- Ensure `VAULT_PATH` is set correctly in `.env`

---

## Next Steps — Upgrade to Gold Tier

When Silver is running smoothly, move to **Gold Tier** for:
- Full cross-domain integration
- Odoo accounting system
- Facebook/Instagram/Twitter posting
- Ralph Wiggum autonomous loop
- Weekly CEO briefing generation

See `../gold-tier/README.md` to continue.
