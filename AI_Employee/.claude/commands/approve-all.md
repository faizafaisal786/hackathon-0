# Agent Skill: Approve All Pending Tasks

Review and batch-approve all items in Pending_Approval/ folder.

## Instructions

1. List all files in `AI_Employee_Vault/Pending_Approval/cloud/` and `Pending_Approval/local/`
2. For each file:
   - Display the task name and drafted content
   - Show quality score (from file metadata)
   - Ask for approval decision: approve / reject / skip
3. For approved items:
   - Move file to `AI_Employee_Vault/Approved/`
   - Log approval to `AI_Employee_Vault/Logs/`
4. For rejected items:
   - Move file to `AI_Employee_Vault/Rejected/`
   - Add rejection reason to file
5. Update `AI_Employee_Vault/Dashboard.md`
6. Trigger `local_agent.py` to execute approved sends

## Usage

```
/approve-all
/approve-all --auto   (auto-approve items with quality score >= 8.0)
```

## Safety

- Never auto-approve payment actions (always manual)
- Never auto-approve emails to new contacts
- Always log every approval/rejection decision
