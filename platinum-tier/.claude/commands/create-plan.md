# Skill: Create Plan (Platinum)

Create a multi-step plan with cloud/local ownership for each step.

**Usage**: `/create-plan <task> --domain <email|social|finance|cross>`

Steps:
1. Read `Company_Handbook.md` — identify which agent owns which steps.
2. Break task into ordered steps with clear ownership:
   - `[CLOUD]` steps — safe for autonomous execution
   - `[LOCAL]` steps — require local machine / human oversight
   - `[APPROVAL]` steps — require human sign-off
3. Save to `/Plans/<domain>/PLAN_<slug>_<date>.md`:

```markdown
---
created: <ISO>
status: active
domain: <domain>
assigned_cloud: <steps>
assigned_local: <steps>
---
# Plan: <title>
## Objective
## Steps
- [ ] [CLOUD] Step 1
- [ ] [CLOUD] Step 2 (draft only)
- [ ] [LOCAL/APPROVAL] Step 3 — needs human approval
- [ ] [LOCAL] Step 4 — execute after approval
## Definition of Done
```

4. Write update to `/Updates/` (if Cloud) or Dashboard (if Local).
