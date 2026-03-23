# Skill: Ralph Loop (Platinum Autonomous)

Run a multi-agent task autonomously with cloud/local coordination.

**Usage**: `/ralph-loop <task> --agent <cloud|local>`

Steps:
1. Read `Company_Handbook.md` — identify agent boundaries.
2. Create plan in `/Plans/<domain>/PLAN_<slug>.md` with [CLOUD] and [LOCAL] labels.
3. Execute only your agent's steps:
   - Skip [CLOUD] steps if you are Local agent
   - Skip [LOCAL] and [APPROVAL] steps if you are Cloud agent
4. After each step: tick checkbox, update plan file.
5. Check: are all YOUR steps done?
   - YES → output `<promise>MY_STEPS_COMPLETE</promise>`
   - NO → continue
6. If a step needs the other agent → write to `/Updates/` or `/Pending_Approval/`.
7. Never exceed 10 iterations.

The other agent will pick up remaining steps from the plan file.

Output when your steps done: `<promise>MY_STEPS_COMPLETE</promise>`
