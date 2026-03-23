"""
linkedin_watcher.py — Monitors LinkedIn notifications and drafts auto-post content.

This watcher uses Playwright (headless browser) to:
1. Check LinkedIn notifications for new connection requests, messages, comments
2. Create inbox items for each notification
3. On scheduled days, generate LinkedIn post drafts and place them in Pending_Approval/

IMPORTANT SECURITY NOTE:
    LinkedIn does not have an official public API for personal profiles.
    This watcher uses browser automation — use your own account at your own risk.
    Never store your LinkedIn password in code or .env. Use environment variables only.
    Consider LinkedIn's Terms of Service before automating.

Environment variables (via .env):
    VAULT_PATH           — Absolute path to vault root
    LINKEDIN_EMAIL       — Your LinkedIn login email
    LINKEDIN_PASSWORD    — Your LinkedIn password (read from env only, never logged)
    LINKEDIN_COOKIE      — Alternative: paste your li_at session cookie value
    POLL_INTERVAL        — Seconds between polls (default: 300 = 5 minutes)
    DRY_RUN              — If "true", log but don't write (default: false)
    LINKEDIN_POST_DAYS   — Comma-separated weekday numbers to draft posts (default: 0,2,4 = Mon,Wed,Fri)
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PWTimeout

from base_watcher import BaseWatcher

load_dotenv()


class LinkedInNotification:
    """Value object representing a single LinkedIn notification."""
    def __init__(self, notif_id: str, notif_type: str, actor: str, text: str, url: str):
        self.id = notif_id
        self.type = notif_type  # e.g. "connection_request", "comment", "message"
        self.actor = actor
        self.text = text
        self.url = url
        self.seen_at = datetime.now().isoformat()


class LinkedInWatcher(BaseWatcher):
    """
    Playwright-based LinkedIn watcher for notifications and auto-post drafting.
    """

    def __init__(self, vault_path: str, **kwargs):
        super().__init__(vault_path, **kwargs)
        self.email = os.getenv("LINKEDIN_EMAIL", "")
        self.password = os.getenv("LINKEDIN_PASSWORD", "")
        self.li_at_cookie = os.getenv("LINKEDIN_COOKIE", "")
        self.post_days = [
            int(d.strip())
            for d in os.getenv("LINKEDIN_POST_DAYS", "0,2,4").split(",")
        ]
        self._seen_ids: set[str] = self._load_seen_ids()
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._playwright = None

    def on_start(self) -> None:
        self.logger.info("Launching Playwright browser for LinkedIn...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        if self.li_at_cookie:
            context.add_cookies([{
                "name": "li_at",
                "value": self.li_at_cookie,
                "domain": ".linkedin.com",
                "path": "/",
            }])
            self.logger.info("Authenticated via li_at session cookie.")
        else:
            self._login(context.new_page())

        self._page = context.new_page()
        self.logger.info("LinkedIn session established.")

    def on_stop(self) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _login(self, page: Page) -> None:
        """Log in to LinkedIn using email/password."""
        if not self.email or not self.password:
            raise ValueError(
                "LINKEDIN_EMAIL and LINKEDIN_PASSWORD env vars required when li_at cookie not set."
            )
        self.logger.info("Logging in to LinkedIn...")
        page.goto("https://www.linkedin.com/login", timeout=30000)
        page.fill('input[name="session_key"]', self.email)
        page.fill('input[name="session_password"]', self.password)
        page.click('button[type="submit"]')
        page.wait_for_url("**/feed/**", timeout=30000)
        self.logger.info("LinkedIn login successful.")

    def poll(self) -> list[LinkedInNotification]:
        """Fetch new LinkedIn notifications."""
        if self._page is None:
            return []

        notifications = []
        try:
            self._page.goto("https://www.linkedin.com/notifications/", timeout=30000)
            self._page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Scrape notification items
            items = self._page.query_selector_all(
                'li[class*="notification-item"], div[data-urn]'
            )

            for item in items[:20]:  # Limit to 20 most recent
                try:
                    urn = item.get_attribute("data-urn") or item.get_attribute("id") or ""
                    if not urn or urn in self._seen_ids:
                        continue

                    text_el = item.query_selector('[class*="notification-text"], p, span')
                    text = text_el.inner_text().strip() if text_el else ""
                    actor_el = item.query_selector('[class*="actor"], strong, b')
                    actor = actor_el.inner_text().strip() if actor_el else "Unknown"
                    link_el = item.query_selector("a")
                    url = link_el.get_attribute("href") or "" if link_el else ""

                    notif_type = self._classify_notification(text)
                    notif = LinkedInNotification(
                        notif_id=urn,
                        notif_type=notif_type,
                        actor=actor,
                        text=text,
                        url=url,
                    )
                    notifications.append(notif)
                    self._seen_ids.add(urn)
                except Exception as item_err:
                    self.logger.debug(f"Skipping notification item: {item_err}")

        except PWTimeout:
            self.logger.warning("LinkedIn notifications page timed out.")
        except Exception as e:
            raise RuntimeError(f"LinkedIn poll failed: {e}") from e

        self._save_seen_ids()

        # Check if today is a post drafting day
        today_weekday = date.today().weekday()
        if today_weekday in self.post_days:
            self._draft_linkedin_post()

        return notifications

    def _classify_notification(self, text: str) -> str:
        """Classify a notification by its text content."""
        text_lower = text.lower()
        if "connect" in text_lower:
            return "connection_request"
        if "comment" in text_lower:
            return "comment"
        if "message" in text_lower:
            return "message"
        if "like" in text_lower or "react" in text_lower:
            return "reaction"
        if "mention" in text_lower:
            return "mention"
        return "notification"

    def process_item(self, item: LinkedInNotification) -> Optional[str]:
        """Convert a LinkedIn notification to vault markdown."""
        return f"""---
source: linkedin
notification_id: "{item.id}"
type: {item.type}
actor: "{item.actor}"
received: {item.seen_at}
status: unread
priority: unset
tags: [inbox, linkedin, {item.type}]
---

# LinkedIn {item.type.replace('_', ' ').title()}: {item.actor}

**Type:** {item.type}
**From:** {item.actor}
**Received:** {item.seen_at}
**URL:** {item.url}

---

## Notification Text

{item.text}

---

## Action Required

> Claude: Review this LinkedIn notification per Company_Handbook.md social media rules.
> - Connection request: Draft a welcome message if relevant to business.
> - Comment: Draft a thoughtful reply.
> - Message: Triage as email (P0-P4) and create task in Needs_Action/ if required.
"""

    def get_item_filename(self, item: LinkedInNotification) -> str:
        date_prefix = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        safe_actor = item.actor.replace(" ", "_")[:30]
        return f"linkedin_{date_prefix}_{item.type}_{safe_actor}.md"

    def _draft_linkedin_post(self) -> None:
        """Create a LinkedIn post draft in Pending_Approval/."""
        pending_path = self.vault_path / "Pending_Approval"
        pending_path.mkdir(parents=True, exist_ok=True)

        today = datetime.now()
        filename = f"LinkedIn_Post_{today.strftime('%Y-%m-%d')}.md"
        target = pending_path / filename

        if target.exists():
            self.logger.info(f"LinkedIn post draft for today already exists: {filename}")
            return

        content = f"""---
type: linkedin_post_draft
created: {today.isoformat()}
status: pending_approval
scheduled_publish: {today.strftime('%Y-%m-%d')} 10:00
tags: [pending_approval, linkedin, post]
---

# LinkedIn Post Draft — {today.strftime('%B %d, %Y')}

> Claude: Generate a LinkedIn post following Company_Handbook.md social media rules.
> Reference Business_Goals.md for current content pillars and target audience.
> Use the post format: Hook → Value → CTA → Hashtags.

---

## Draft Post

[Claude will generate this post using /post-linkedin skill]

---

## Approval Instructions

To approve: Move this file to `Approved/`
To reject: Move this file to `Rejected/` and add a comment below explaining why.

**Rejection reason (if applicable):**

---

## Post Metadata

- **Platform:** LinkedIn
- **Draft created:** {today.isoformat()}
- **Scheduled for:** {today.strftime('%Y-%m-%d')} 10:00 AM
- **Content pillar:** [To be determined by Claude]
"""
        if not self.dry_run:
            target.write_text(content, encoding="utf-8")
            self.logger.info(f"LinkedIn post draft created: {filename}")
        else:
            self.logger.info(f"[DRY RUN] Would create LinkedIn post draft: {filename}")

    def _load_seen_ids(self) -> set[str]:
        state_file = self.logs_path / "linkedin_seen_ids.json"
        if state_file.exists():
            try:
                return set(json.loads(state_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return set()

    def _save_seen_ids(self) -> None:
        state_file = self.logs_path / "linkedin_seen_ids.json"
        if not self.dry_run:
            state_file.write_text(json.dumps(list(self._seen_ids)))


if __name__ == "__main__":
    vault = os.getenv("VAULT_PATH", str(Path(__file__).parent.parent))
    interval = int(os.getenv("POLL_INTERVAL", "300"))
    dry_run = os.getenv("DRY_RUN", "false").lower() == "true"

    watcher = LinkedInWatcher(
        vault_path=vault,
        poll_interval_seconds=interval,
        dry_run=dry_run,
    )
    watcher.run()
