# Skill: Process Inbox (Platinum)

Process domain-specific queues. Identify which agent should handle each item.

**IMPORTANT**: You are running as the agent indicated by AGENT_ID env var.
- If `AGENT_ID=cloud` → process `/Needs_Action/email/` and `/Needs_Action/social/` only
- If `AGENT_ID=local` → process `/Needs_Action/finance/` and escalations

Steps:
1. Read `Company_Handbook.md` — check work zone ownership rules.
2. For each item in your domain's queue:
   a. **Claim it**: move to `/In_Progress/<agent>/` (claim-by-move rule).
   b. Read the item content.
   c. Analyze and determine action.
   d. For draft actions → write to `/Pending_Approval/`.
   e. For completed analysis → write summary back to item file.
3. Update `/Updates/inbox_update_<timestamp>.md` (Cloud) or `Dashboard.md` (Local).
4. Log to `/Logs/`.

Output: `<promise>INBOX_PROCESSED</promise>`
