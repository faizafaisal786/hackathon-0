# Skill: Ralph Loop (Autonomous Task Completion)

Run a task autonomously until completion using the Ralph Wiggum pattern.

**Usage**: `/ralph-loop <task description>`

This skill is for multi-step tasks that require several Claude iterations.

Steps:
1. Read the task description carefully.
2. Check `Company_Handbook.md` for relevant rules.
3. Create a plan file in `/Plans/` with all required steps.
4. Execute each step in order:
   - Read relevant files.
   - Take action (write files, update status, create approvals).
   - Tick off completed steps in the plan.
5. After every step, check: are all steps complete?
   - YES → output `<promise>TASK_COMPLETE</promise>` and stop.
   - NO → continue to next step.
6. If you encounter an action requiring human approval, create the approval file and output `<promise>WAITING_FOR_APPROVAL</promise>`.
7. Never exceed 10 steps without checking in.

Output when done: `<promise>TASK_COMPLETE</promise>`
