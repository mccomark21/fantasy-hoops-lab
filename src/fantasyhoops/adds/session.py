"""The Yahoo session: Microsoft Edge with the saved sign-in in .auth/yahoo/ (see docs/adr/0001).

This module only opens pages and returns their HTML. It never submits a form or clicks a button.
The readers in adds/readers.py read the HTML. Only one process can use the saved profile at a time.
Requirement: Microsoft Edge and pip install playwright. Edge is the browser, so "playwright install" is not necessary.
"""
from contextlib import contextmanager

from playwright.sync_api import sync_playwright

from fantasyhoops.core.common import ROOT

PROFILE = ROOT / ".auth" / "yahoo"
SITE = "https://basketball.fantasysports.yahoo.com"
SIGN_IN_MINUTES = 5  # time that you have to sign in by hand when the session has expired


class League:
    """The pages of one Yahoo league. get("players?status=FA") returns the HTML of /nba/<league>/players?status=FA."""

    def __init__(self, page, league):
        self.page = page
        self.base = f"{SITE}/nba/{league}"

    def get(self, path=""):
        url = f"{self.base}/{path}" if path else self.base
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if not self.page.url.startswith(SITE):
            self._sign_in(url)
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # Yahoo pages can keep loading ads. The HTML of the page is ready.
        return self.page.content()

    def _sign_in(self, url):
        """Wait for a manual sign-in in the Edge window, then open url again."""
        print("The Yahoo session has expired. Sign in to Yahoo in the Edge window.")
        print(f"The planner continues after the sign-in. You have {SIGN_IN_MINUTES} minutes.")
        self.page.wait_for_url(f"{SITE}/**", timeout=SIGN_IN_MINUTES * 60000)
        print("Sign-in complete. Edge keeps the new session in .auth/yahoo/.")
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)


@contextmanager
def open_league(league):
    """Open Edge with the saved Yahoo profile and give a League. Edge closes at the end of the with block.

    Edge opens in a visible window. Yahoo blocked an automated sign-in in October 2026, and a visible window
    lets you sign in by hand when the session has expired.
    """
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            yield League(page, league)
        finally:
            context.close()
