# Skill: Complete Task

Mark a task as done and move it to the `/Done` folder.

**Usage**: `/complete-task <filename>`

Steps:
1. Read the specified file from `/Needs_Action/`.
2. Verify the task is actually resolved (check all checkboxes are ticked or a resolution note exists).
3. Update the file's frontmatter:
   - `status: done`
   - `completed: <current ISO timestamp>`
4. Add a `## Completion Summary` section with:
   - What was done
   - Any follow-up items created
5. Move the file to `/Done/<filename>`.
6. Update `Dashboard.md`:
   - Decrement "Pending Action"
   - Increment "Completed Today"
7. Log the completion in `/Logs/YYYY-MM-DD.json`.

Output confirmation: `Task <filename> moved to /Done.`
