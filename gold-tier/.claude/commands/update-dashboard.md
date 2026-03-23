# Skill: Update Dashboard

Refresh `Dashboard.md` with live vault statistics.

1. Count pending `.md` files in `/Needs_Action` → update Pending.
2. Count `/Done` files modified today → update Completed Today.
3. Read last 5 log entries from `/Logs/<today>.json` → update Recent Actions table.
4. Check `/Briefings/` for latest briefing link.
5. Update `last_updated` in frontmatter.
6. Preserve all other sections unchanged.

Output: `Dashboard updated at <timestamp>.`
