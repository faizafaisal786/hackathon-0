# Skill: Process Inbox

Read all files in the `/Needs_Action` folder of this vault.

For each `.md` file with `status: pending` in its frontmatter:

1. Read the file content carefully.
2. Check `Company_Handbook.md` for relevant rules.
3. Based on the file type and content, determine the best action:
   - **file_drop**: Summarize the file and list next steps.
   - **email**: Draft a reply suggestion (do NOT send without approval).
   - **task**: Create a checklist and assign a priority.
4. Update the file's frontmatter: set `status: in_progress`.
5. Add a `## Claude's Analysis` section with your findings and suggested actions.
6. If action requires human approval, create a file in `/Needs_Action/` with prefix `APPROVAL_REQUIRED_`.
7. Update `Dashboard.md` — increment "Pending Action" count.
8. Log your action in `/Logs/YYYY-MM-DD.json`.

When all items are processed, output: `<promise>INBOX_PROCESSED</promise>`
