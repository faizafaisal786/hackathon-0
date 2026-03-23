# Agent Skill: Send Email

Draft and send a professional email using the AI Employee email system.

## Instructions

1. Read the task file provided (or check `AI_Employee_Vault/Approved/` for pending sends)
2. Extract: To, Subject, Body from the task
3. Check `AI_Employee_Vault/Company_Handbook.md` for tone guidelines
4. Draft the email using EXECUTOR agent
5. Score quality with REVIEWER agent (must be ≥ 7.0/10)
6. Write ACTION file to `AI_Employee_Vault/Pending_Approval/` if not pre-approved
7. If file is in `AI_Employee_Vault/Approved/`, call `email_sender.py` to send immediately
8. Log result to `AI_Employee_Vault/Logs/email_YYYY-MM-DD.json`
9. Move task to `AI_Employee_Vault/Done/`

## Usage

```
/send-email
/send-email "Reply to ahmed@client.com about pricing"
```

## Security Rules

- Never send to unknown contacts without approval
- Always log sent emails
- Bulk sends (>5) always require human approval
