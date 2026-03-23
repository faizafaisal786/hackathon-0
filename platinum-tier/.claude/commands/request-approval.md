# Skill: Request Approval (Platinum HITL)

Create an approval request file. Used by BOTH agents for any sensitive action.

**Usage**: `/request-approval <action_type> <description>`

Steps:
1. Create `/Pending_Approval/APPROVAL_<type>_<timestamp>.md`:

```markdown
---
type: approval_request
action: <action_type>
requested_by: <cloud|local>
status: pending
priority: <high|critical>
created: <ISO>
expires: <ISO + 24h>
---
# Approval Required: <Action>

## What Will Happen
<exact description>

## Details
<all parameters — who, what, amount, etc.>

## Risk: <low|medium|high>
## Reversible: <yes|no>

## ✅ To Approve → move file to /Approved/
## ❌ To Reject  → move file to /Rejected/
```

2. Cloud agent: also write `/Updates/approval_needed_<timestamp>.md`.
3. Local agent: immediately alert user (local_approval_watcher handles this).
4. Log the pending action.
5. STOP — do not proceed until file is in /Approved/.
