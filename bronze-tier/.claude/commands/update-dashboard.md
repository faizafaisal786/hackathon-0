# Skill: Update Dashboard

Refresh the `Dashboard.md` file with current vault statistics.

Steps:
1. Count all `.md` files in `/Inbox` → update "Total Items".
2. Count all `.md` files in `/Needs_Action` with `status: pending` → update "Pending Action".
3. Count all `.md` files in `/Done` modified today → update "Completed Today".
4. Read the last 5 log entries from `/Logs/<today>.json` → update "Recent AI Actions" table.
5. Write the updated stats back to `Dashboard.md` — preserve all other sections.
6. Add a `last_updated` timestamp in the frontmatter.

Keep the Dashboard clean and concise. Do not remove existing content — only update the stats sections.

Output: `Dashboard updated at <timestamp>.`
