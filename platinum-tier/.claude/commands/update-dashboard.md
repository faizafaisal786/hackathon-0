# Skill: Update Dashboard (Platinum — LOCAL ONLY)

**ONLY run this skill as the LOCAL agent.** Cloud writes to /Updates/ instead.

Steps:
1. Read all files in `/Updates/` — these are cloud agent's contributions.
2. Count items per domain in `/Needs_Action/email/`, `/social/`, `/finance/`.
3. Count items per agent in `/In_Progress/cloud/` and `/In_Progress/local/`.
4. Count `/Done/` items modified today.
5. Read last 5 log entries from today's JSON log.
6. Merge all data into `Dashboard.md`:
   - Update Cross-Domain Inbox Summary table
   - Update Recent Actions table
   - Update last_updated frontmatter
7. Move processed `/Updates/` files to `/Done/`.
8. Log the dashboard update.

**Never run from the Cloud agent** — single-writer rule applies.
