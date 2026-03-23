# Skill: Process Inbox

Read **all** files in `/Needs_Action` with `status: pending`.

For each file:
1. Read file + `Company_Handbook.md` rules.
2. Classify: email / file_drop / whatsapp / finance / social / system_alert.
3. Add `## Claude's Analysis` section with findings + next steps.
4. If sensitive action needed → create `APPROVAL_REQUIRED_<name>.md` in `/Pending_Approval/`.
5. Update frontmatter: `status: in_progress`.
6. Update `Dashboard.md` stats.
7. Log to `/Logs/YYYY-MM-DD.json`.

After all items: output `<promise>INBOX_PROCESSED</promise>`
