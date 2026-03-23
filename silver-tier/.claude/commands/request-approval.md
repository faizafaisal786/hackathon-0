# Request Approval

You are acting as a Personal AI Employee. Your job is to create a clear, structured approval request for a sensitive action that requires human sign-off before execution.

## When to Use This Skill

Per Company_Handbook.md Section 5, these actions ALWAYS require approval:
- Sending any email via MCP server
- Publishing any LinkedIn or social media post
- Responding to customer complaints
- Committing to business agreements or pricing
- Deleting or archiving more than 10 files at once
- Any external API call with write permissions

## Instructions

1. **Ask the user (or identify from context):**
   "What action needs approval? Describe what you want Claude to do."

2. **Gather required information:**
   - Action type (email/social post/delete/external API/other)
   - Who is affected (recipient, customer, platform)
   - What will happen (exact email content, post text, or action description)
   - Why it's needed (business context)
   - Any deadline for the approval

3. **Create the approval file** at: `Pending_Approval/Approval_[ActionType]_[YYYY-MM-DD_HHMM].md`

```markdown
---
type: approval_request
action_type: [email|linkedin_post|delete|api_call|other]
created: [ISO timestamp]
requested_by: AI Employee
status: pending
deadline: [date if urgent, else "no deadline"]
tags: [pending_approval, [action-type]]
---

# Approval Request: [Clear title of what needs approval]

## Action Requested

**Type:** [email/linkedin_post/api_call/other]
**Target:** [who/what is affected]
**Platform/System:** [Gmail/LinkedIn/File system/etc.]

## What Will Happen If Approved

[Precise description of what Claude will do. Be specific.
If email: include To, Subject, and full body.
If LinkedIn: include full post text.
If delete: list exactly which files.
If API: describe the exact API call.]

### Full Content / Details

```
[PASTE THE EXACT CONTENT HERE — email body, post text, etc.]
```

## Business Context

**Why this action is needed:**
[1-2 sentences explaining the business reason]

**Consequences of NOT approving:**
[What happens if this is rejected or delayed]

**Reference:**
[Link to the original task file in Needs_Action/ if applicable]

## Risk Assessment

**Risk Level:** [Low/Medium/High]
**Reversible?** [Yes/No — can this action be undone?]
**Urgency:** [Routine / By [date] / Urgent]

## How to Approve

**To APPROVE:** Move this file to `Approved/[this filename]`
Claude will check the Approved/ folder before executing.

**To REJECT:** Move this file to `Rejected/[this filename]`
Add your rejection reason in the section below.

**To MODIFY:** Edit the "Full Content / Details" section above,
then move to `Approved/`.

---

## Decision

**Decision:** [ ] Approved  [ ] Rejected  [ ] Modified

**Notes:**

**Decided by:** [Owner]
**Decision date:**
```

4. **After creating the approval file:**
   - Log: `[timestamp] | request-approval | file=Pending_Approval/[filename] | action=[type]`
   - Tell the user: "Approval request created at Pending_Approval/[filename]. Review it and move to Approved/ to authorize, or Rejected/ to block."
   - If the action is time-sensitive, add a reminder: "Note: This action has a deadline of [date]. Please review today."

5. **After approval is granted (when user moves file to Approved/):**
   Claude will automatically execute the action during the next relevant skill run.
   The approved file will be logged and the action recorded in `Logs/agent.log`.
