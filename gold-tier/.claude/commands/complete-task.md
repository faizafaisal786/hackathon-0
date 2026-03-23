# Skill: Complete Task

Mark a task as done and archive it.

**Usage**: `/complete-task <filename>`

1. Read the file from `/Needs_Action/`.
2. Verify all action items are resolved.
3. Update frontmatter: `status: done`, `completed: <ISO timestamp>`.
4. Add `## Completion Summary` with what was done.
5. Move to `/Done/<filename>`.
6. Update `Dashboard.md` (decrement pending, increment completed).
7. Log to `/Logs/YYYY-MM-DD.json`.
