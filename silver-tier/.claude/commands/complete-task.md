# Complete Task

You are acting as a Personal AI Employee. Your job is to mark a task as complete and archive it.

## Instructions

1. **Ask the user:** "Which task would you like to mark as complete?" — then list all files currently in `Needs_Action/`.

2. **Once the user specifies a task:**
   - Read the task file from `Needs_Action/`
   - Ask: "Was this task completed successfully, or should it be noted as incomplete/cancelled?"
   - Ask: "Any notes or outcomes to record?"

3. **Update the task file:**
   Add to the frontmatter:
   ```yaml
   completed: [ISO timestamp]
   outcome: [success|incomplete|cancelled]
   completion_notes: "[user's notes]"
   status: done
   ```

4. **Move the file:**
   - Move from `Needs_Action/[filename].md` to `Done/[filename].md`
   - If the Needs_Action file referenced an Inbox file, also move the inbox file to Done/

5. **Check for email approval:**
   - If the task file contains a "Draft response" section, ask: "Would you like to send the draft email now?"
   - If yes, confirm the email details, then check for an approval file in `Approved/`
   - If approved, use the email MCP tool to send

6. **Update Dashboard.md:**
   - Decrement Needs_Action count by 1
   - Add entry to "Done (Last 7 Days)" table
   - Update "Last Updated" timestamp

7. **Log the completion:**
   Append to `Logs/agent.log`:
   `[timestamp] | complete-task | file=[filename] | outcome=[outcome]`

8. **Confirm to user:**
   "Task '[title]' has been marked as [outcome] and moved to Done/."
