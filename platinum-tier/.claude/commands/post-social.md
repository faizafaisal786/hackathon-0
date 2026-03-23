# Skill: Post Social Media (Platinum)

Draft a social post — CLOUD drafts, LOCAL executes after approval.

**Usage**: `/post-social <platform> "<message>"`

**Cloud Agent Steps**:
1. Draft post content (on-brand, professional, within character limits).
2. Create `/Pending_Approval/SOCIAL_<platform>_<date>.md` with full content.
3. Write `/Updates/social_pending_<date>.md` to notify Local agent.
4. STOP. Never call social MCP directly.

**Local Agent Steps** (after human moves to /Approved):
1. Read the approved file.
2. Call `social-mcp` with the approved content.
3. Log result.
4. Move file to `/Done/`.
5. Update `Dashboard.md`.

**Platform limits**:
- Twitter/X: 280 chars
- LinkedIn: 3000 chars (optimal: 150-300)
- Facebook: 63,206 chars (optimal: 40-80)
- Instagram: 2200 chars + image required
