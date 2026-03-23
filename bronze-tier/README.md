# Personal AI Employee — Bronze Tier

**Estimated Setup Time:** 8–12 hours
**Tier Level:** Bronze (Foundation)

---

## Overview

The Bronze Tier establishes the foundation of your Personal AI Employee system. You get:

- An Obsidian vault as the shared "brain" between you and Claude
- A file system Watcher that feeds work into the vault automatically
- Claude Code Agent Skills that read, reason, and write back to the vault
- A simple three-folder workflow: **Inbox → Needs_Action → Done**

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Claude Code | Latest | `npm i -g @anthropic-ai/claude-code` |
| Obsidian | 1.5+ | Optional for viewing, vault works without it |
| Git | Any | For version control of your vault |

---

## Folder Structure

```
bronze-tier/
├── .claude/
│   └── commands/           # Agent Skills (Claude slash commands)
│       ├── process-inbox.md
│       ├── complete-task.md
│       ├── update-dashboard.md
│       └── daily-briefing.md
├── Inbox/                  # Drop zone — watcher deposits items here
├── Needs_Action/           # Tasks awaiting your attention or Claude action
├── Done/                   # Completed tasks archive
├── Logs/                   # Watcher and agent activity logs
├── Dashboard.md            # Your live command center
├── Company_Handbook.md     # Rules Claude follows for your business
├── SKILL.md                # Agent Skills documentation
├── filesystem_watcher.py   # File system monitor
└── requirements.txt        # Python dependencies
```

---

## Setup Instructions

### Step 1 — Install Python Dependencies

```bash
cd bronze-tier
pip install -r requirements.txt
```

### Step 2 — Configure Your Vault Path

Open `filesystem_watcher.py` and update the `VAULT_PATH` variable at the top:

```python
VAULT_PATH = "/path/to/your/bronze-tier"  # Change this
```

Or set environment variable:
```bash
export VAULT_PATH="C:/Users/YourName/Desktop/bronze-tier"
```

### Step 3 — Start the Watcher

```bash
python filesystem_watcher.py
```

The watcher will:
- Monitor a designated drop folder (default: `~/Desktop/AI_Inbox/`)
- Copy new files into `Inbox/` with a timestamp prefix
- Log all activity to `Logs/watcher.log`

### Step 4 — Open Claude Code in the Vault

```bash
cd bronze-tier
claude
```

You now have access to all Agent Skills via slash commands.

### Step 5 — Test the System

1. Drop a `.txt` file into `~/Desktop/AI_Inbox/`
2. Watch it appear in `Inbox/`
3. In Claude Code, run: `/process-inbox`
4. Claude will read the file, reason about it, and create a task in `Needs_Action/`

---

## Available Agent Skills

| Skill | Command | Description |
|---|---|---|
| Process Inbox | `/process-inbox` | Reads all Inbox items, triages into Needs_Action |
| Complete Task | `/complete-task` | Marks a task done, moves file to Done/ |
| Update Dashboard | `/update-dashboard` | Refreshes Dashboard.md with current state |
| Daily Briefing | `/daily-briefing` | Generates morning summary of all active work |

---

## Workflow

```
External World
     │
     ▼
[filesystem_watcher.py]
     │  (detects new file)
     ▼
  Inbox/
     │
     ▼  /process-inbox
  Needs_Action/
     │
     ▼  /complete-task
   Done/
```

---

## Company Handbook

Before running Claude, review `Company_Handbook.md`. This file tells Claude:
- What business you run
- How to prioritize tasks
- What tone to use in communications
- What Claude is and is NOT allowed to do without approval

**Edit the Handbook to match your actual business before use.**

---

## Dashboard

`Dashboard.md` is your live command center. Claude updates it automatically when you run `/update-dashboard`. It shows:
- Active tasks count
- Inbox status
- Recent completions
- System health

Open it in Obsidian to see it rendered beautifully.

---

## Security Notes

- No credentials are stored in the vault
- The watcher only reads from a designated folder — it does not access arbitrary paths
- All Claude actions are logged to `Logs/`
- Claude does not send emails or post to social media at this tier — Bronze is read/write to vault only

---

## Troubleshooting

**Watcher not detecting files:**
```bash
# Check that watchdog is installed
pip show watchdog
# Verify the watch path exists
ls ~/Desktop/AI_Inbox/
```

**Claude not finding vault:**
```bash
# Make sure you launched Claude from inside the vault folder
cd bronze-tier && claude
```

**Tasks not moving to Needs_Action:**
- Check `Logs/watcher.log` for errors
- Ensure `Company_Handbook.md` is readable (Claude uses it for context)

---

## Next Steps — Upgrade to Silver Tier

When Bronze is running smoothly, move to **Silver Tier** for:
- Gmail integration (real email triage)
- LinkedIn auto-posting for business growth
- Human-in-the-loop approval workflow
- Automated daily scheduling via cron

See `../silver-tier/README.md` to continue.
