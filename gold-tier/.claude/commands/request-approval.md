# Skill: Request Approval (HITL)

Create a Human-in-the-Loop approval request for any sensitive action.

**Usage**: `/request-approval <action_type> <details>`

Action types: `payment`, `email_send`, `social_post`, `file_delete`, `odoo_post`

Steps:
1. Create `/Pending_Approval/APPROVAL_<type>_<date>.md`:

```markdown
---
type: approval_request
action: <action_type>
status: pending
priority: high
created: <ISO>
expires: <ISO + 24h>
---
# Approval Required: <Action Type>

## What Will Happen
<clear description of the action>

## Details
<key parameters — recipient, amount, content, etc.>

## Risk Level
<low / medium / high>

## To Approve → move to /Approved
## To Reject  → move to /Rejected
```

2. Log the pending action to `/Logs/`.
3. Update `Dashboard.md` — increment Pending Approvals count.
4. STOP. Do not proceed until file moves to /Approved.
