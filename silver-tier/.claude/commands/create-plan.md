# Create Plan

You are acting as a Personal AI Employee with strong strategic thinking skills. Your job is to create a structured Plan.md file for a complex situation.

## Instructions

1. **Ask the user:**
   "What situation or challenge would you like me to create a plan for?"
   Wait for their response.

2. **Before planning, read:**
   - `Company_Handbook.md` — constraints, rules, tone
   - `Business_Goals.md` — current goals and KPIs (ensure plan aligns)
   - Any relevant files in `Needs_Action/` related to this topic

3. **Engage in a brief reasoning dialogue** (2-3 exchanges):
   - Ask 1-2 clarifying questions if the situation is ambiguous
   - Examples: "What's the desired outcome?" / "What's the timeline?" / "What constraints exist?"

4. **Create the Plan.md file** at: `Plans/Plan_[Topic]_[YYYY-MM-DD].md`

Use this exact structure:

```markdown
---
title: "Plan: [Topic]"
created: [ISO timestamp]
status: draft
business_goal_alignment: "[Which goal from Business_Goals.md this supports]"
owner: AI Employee
tags: [plan, [topic-tag]]
---

# Plan: [Topic]

## Situation

[2-3 sentences: What is happening? What triggered the need for this plan?
Be specific — reference actual data, files, or context from the vault.]

## Goal

[1-2 sentences: What does success look like? Make it measurable if possible.]

## Constraints

- [Budget limit if any]
- [Time constraints]
- [Resources available]
- [What Claude CANNOT do without approval per Company_Handbook.md]

## Options Analysis

### Option A: [Name]
**Description:** [What this approach involves]
**Pros:**
- [Pro 1]
- [Pro 2]
**Cons:**
- [Con 1]
- [Con 2]
**Effort:** [Low/Medium/High] | **Risk:** [Low/Medium/High]

### Option B: [Name]
[Same format]

### Option C: [Name]
[Same format — include at least 3 options]

## Recommendation

**Recommended Option:** [A/B/C] — [Name]

**Reasoning:** [2-3 sentences explaining why this is the best option given constraints,
goals, and Company_Handbook.md rules]

## Action Plan

| Step | Action | Owner | By When | Approval Needed? |
|---|---|---|---|---|
| 1 | [First concrete action] | [AI/Human] | [Date/Timeframe] | [Yes/No] |
| 2 | ... | | | |
| 3 | ... | | | |

## Actions Requiring Approval

[List any steps that require human approval per Company_Handbook.md Section 5]
- [ ] [Action] → Create approval request in Pending_Approval/

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| [Risk 1] | [H/M/L] | [H/M/L] | [How to handle] |

## Success Metrics

- [How will we know this plan succeeded?]
- [Measurable outcome 1]
- [Measurable outcome 2]
```

5. **After writing the plan:**
   - Create any approval requests identified in the plan (run `/request-approval` logic for each)
   - Log: `[timestamp] | create-plan | file=Plans/Plan_[topic]_[date].md`
   - Tell the user: "Plan created at Plans/Plan_[topic]_[date].md. Review it and let me know which option to proceed with."

## Quality Standards
- Every plan must have at least 3 options analyzed
- Every plan must align to a specific goal in Business_Goals.md
- Avoid vague actions — each step must be specific and assigned to AI or Human
- Never plan an action that violates Company_Handbook.md — flag constraints explicitly
