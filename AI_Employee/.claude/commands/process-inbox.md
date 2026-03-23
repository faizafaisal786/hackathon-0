# Agent Skill: Process Inbox

Process all tasks in the AI Employee Vault Inbox folder.

## Instructions

1. Read all `.md` files from `AI_Employee_Vault/Inbox/`
2. For each file, analyze the task:
   - Detect channel (Email, WhatsApp, LinkedIn, etc.)
   - Detect priority (urgent/normal/low)
   - Detect required action (reply, post, payment, research)
3. Run the 4-agent pipeline: THINKER → PLANNER → EXECUTOR → REVIEWER
4. Move task to `AI_Employee_Vault/Needs_Action/` with proper zone (cloud/local)
5. Create a `PLAN_*.md` file in `AI_Employee_Vault/Plans/`
6. If action requires human approval, write to `AI_Employee_Vault/Pending_Approval/`
7. Update `AI_Employee_Vault/Dashboard.md` with current pipeline status

## Usage

```
/process-inbox
```

## Success Criteria

- All Inbox files processed
- Plans created for each task
- Tasks routed to correct zone (cloud/local)
- Dashboard.md updated
