# Skill: Claim Task (Platinum)

Implement the claim-by-move rule to prevent double-work between Cloud and Local agents.

**Usage**: `/claim-task <filepath>`

Steps:
1. Check if the file exists in `/Needs_Action/<domain>/`.
2. Move it to `/In_Progress/<your_agent_id>/` — this atomically claims it.
3. If the move fails (file already gone) → another agent claimed it. STOP.
4. Confirm ownership by checking the file is in your `/In_Progress/` folder.
5. Return the new file path.

**Rule**: First agent to move the file owns it. Never process a file in another agent's `/In_Progress/` folder.

Output: `Claimed: /In_Progress/<agent>/<filename>` or `Already claimed by another agent.`
