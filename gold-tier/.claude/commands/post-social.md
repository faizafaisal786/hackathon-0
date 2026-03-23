# Skill: Post Social Media

Draft and schedule a social media post. ALWAYS requires human approval before publishing.

**Usage**: `/post-social <platform> <message>`

Platforms: `facebook`, `instagram`, `twitter`, `all`

Steps:
1. Draft the post content (professional, engaging, on-brand per `Company_Handbook.md`).
2. Create an approval file `/Pending_Approval/SOCIAL_<platform>_<date>.md`:

```markdown
---
type: approval_request
action: social_post
platform: <platform>
status: pending
created: <ISO>
expires: <ISO + 24h>
---
# Social Post Approval Required

## Draft Content
<post text>

## Platform: <platform>

## To Approve
Move this file to /Approved

## To Reject
Move this file to /Rejected
```

3. Log draft creation to `/Logs/`.
4. Do NOT call the social MCP until the file is in `/Approved`.

Output: `Approval request created: /Pending_Approval/SOCIAL_<platform>_<date>.md`
