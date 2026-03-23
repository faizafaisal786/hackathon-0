# Agent Skill: System Health Check

Run a full health check on the AI Employee system and report status.

## Instructions

1. Run `health_monitor.py` to check:
   - Disk space (alert if < 15% free)
   - Memory usage (alert if > 85%)
   - API health (Groq, Gemini)
   - Git sync status (vault synced?)
   - Agent processes running (cloud_agent, ralph_loop)
   - Log error rate (last hour)
2. Check `AI_Employee_Vault/Signals/` for any active alerts from cloud
3. Check `AI_Employee_Vault/Updates/` for pending cloud agent updates
4. Report current pipeline status:
   - Files in each stage (Inbox, Needs_Action, In_Progress, Done)
   - Last 5 completed tasks
   - Any stuck tasks (in same stage > 1 hour)
5. Update `AI_Employee_Vault/Dashboard.md` with health status

## Usage

```
/health-check
```

## Output

Prints a health report and writes summary to Dashboard.md
