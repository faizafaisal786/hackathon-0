# Skill: Complete Task (Platinum)

Mark a task as done, release it from /In_Progress/, and archive it.

**Usage**: `/complete-task <filename>`

1. Find the file in `/In_Progress/<agent>/` or `/Needs_Action/<domain>/`.
2. Verify all action items resolved.
3. Update frontmatter: `status: done`, `completed: <ISO>`, `completed_by: <agent_id>`.
4. Add `## Completion Summary`.
5. Move to `/Done/<filename>`.
6. If Cloud agent: write update to `/Updates/` — do NOT touch Dashboard.md.
7. If Local agent: update `Dashboard.md` directly.
8. Log to `/Logs/`.
