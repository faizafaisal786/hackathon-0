# Skill: Create Plan

Create a structured Plan.md for a multi-step task.

**Usage**: `/create-plan <task description>`

1. Read `Company_Handbook.md` for relevant rules.
2. Break the task into ordered steps with checkboxes.
3. Identify which steps need human approval.
4. Save to `/Plans/PLAN_<slug>_<date>.md`:

```markdown
---
created: <ISO>
status: active
task: <description>
---
# Plan: <title>
## Objective
## Steps
- [ ] Step 1 (auto)
- [ ] Step 2 (REQUIRES APPROVAL)
## Risks & Constraints
## Definition of Done
```

5. Add link to plan in `Dashboard.md`.
6. Log to `/Logs/`.

Output: `Plan created: /Plans/PLAN_<name>.md`
