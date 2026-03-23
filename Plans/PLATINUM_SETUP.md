# PLATINUM Setup — Legend Level

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CLOUD VM (Always-On)                  │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Gmail Watcher│  │ FS Watcher   │  │ Ralph Loop   │  │
│  │ (every 5min) │  │ (realtime)   │  │ (continuous) │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │          │
│         ▼                 ▼                  ▼          │
│  ┌─────────────────────────────────────────────────┐    │
│  │              OBSIDIAN VAULT (Git Repo)           │    │
│  │                                                  │    │
│  │  Needs_Action/ → Pending_Approval/ → Done/       │    │
│  └──────────────────────┬──────────────────────────┘    │
│                         │                               │
│                    git push (auto every 30s)             │
└─────────────────────────┼───────────────────────────────┘
                          │
                     GitHub/GitLab
                     (Private Repo)
                          │
                     git pull (auto)
┌─────────────────────────┼───────────────────────────────┐
│                LOCAL PC (Your Machine)                   │
│                         │                               │
│  ┌──────────────────────▼──────────────────────────┐    │
│  │           OBSIDIAN (Local Vault)                 │    │
│  │                                                  │    │
│  │  See tasks → Move to Approved/ or Rejected/      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │         LOCAL APPROVAL WATCHER                   │    │
│  │  Detects approve/reject → git commit + push      │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Files Created

| File | Purpose | Runs On |
|------|---------|---------|
| `setup_git_repo.sh` | Initialize git repo + .gitignore | Local (once) |
| `cloud_setup.sh` | Full VM setup + systemd services | Cloud VM (once) |
| `cloud_sync.sh` | Auto git commit/push every 30s | Cloud VM (always) |
| `ralph_loop.py` | Process tasks through pipeline 24/7 | Cloud VM (always) |
| `local_approval_watcher.py` | Watch approvals + auto git sync | Local PC (always) |

## Deployment Steps

### Step 1: Local — Git Init
```bash
bash setup_git_repo.sh
git remote add origin git@github.com:YOUR_USER/ai-employee-vault.git
git push -u origin main
```

### Step 2: Cloud VM — Get a VM
- DigitalOcean: $4/mo droplet (cheapest)
- AWS EC2: t2.micro (free tier)
- GCP: e2-micro (free tier)
- Azure: B1s (free tier)

### Step 3: Cloud VM — Run Setup
```bash
scp cloud_setup.sh user@YOUR_VM_IP:~/
ssh user@YOUR_VM_IP
bash cloud_setup.sh
```

### Step 4: Local — Start Approval Watcher
```bash
pip install watchdog
python local_approval_watcher.py
```

### Step 5: Done — System is Live
- Cloud VM processes emails and tasks 24/7
- You approve/reject from Obsidian on your PC
- Git syncs everything between cloud and local
- Full audit trail in Logs/

## 4 Always-On Services (Cloud VM)

| Service | What It Does | Restart |
|---------|-------------|---------|
| `ai-gmail-watcher` | Checks Gmail every 5 min | Auto |
| `ai-fs-watcher` | Watches for new files | Auto |
| `ai-git-sync` | Git push/pull every 30s | Auto |
| `ai-ralph-loop` | Processes pipeline every 60s | Auto |

## Status: READY TO DEPLOY
