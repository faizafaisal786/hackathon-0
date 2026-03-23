# Skill: Cloud Sync Status Check

Check vault sync status between Local and Cloud agents.

Steps:
1. Run `git -C <vault_path> status` — check for uncommitted changes.
2. Run `git log --oneline -5` — show last 5 sync commits.
3. Check `/Updates/` folder — any pending cloud updates not yet merged?
4. Check `/In_Progress/cloud/` — any items the cloud is currently working on?
5. Check `/In_Progress/local/` — any items local is currently working on?
6. Report sync health:
   - Last sync time
   - Unmerged updates count
   - Items in progress by each agent
   - Any conflicts detected

If there are unmerged `/Updates/`, run `/update-dashboard` to merge them.

Output: Sync status report.
