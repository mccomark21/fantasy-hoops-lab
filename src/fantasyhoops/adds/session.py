"""The Yahoo session: Microsoft Edge with the saved sign-in in .auth/yahoo/ (see docs/adr/0001).

This module only opens pages and returns their HTML. It never submits a form or clicks a button.
The readers in adds/readers.py read the HTML. Only one process can use the saved profile at a time.
Requirement: Microsoft Edge and pip install playwright. Edge is the browser, so "playwright install" is not necessary.
"""

from contextlib import contextmanager

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from fantasyhoops.core.common import ROOT

PROFILE = ROOT / ".auth" / "yahoo"
SITE = "https://basketball.fantasysports.yahoo.com"
SIGN_IN_MINUTES = 5  # time that you have to sign in by hand when the session has expired
WAIT_SECONDS = 10  # default of [adds] page_wait in config.toml

# The elements that the readers of each page kind need, by the start of the page path (#74).
# Each page kind has required elements and optional elements. A required element that does not appear raises
# PageNotReady. An optional element gets SCORE_WAIT_SECONDS after the required elements appear, and then get()
# reads the page as it is.
# The team page path is the team ID, so a path that starts with a digit is a team page.
# Each selector names table rows, because a table can be in the page before its rows are.
READY = [
    ("players", ("div.players table tbody tr",), ()),  # readers.read_free_agents() and read_waiver_players()
    # readers.read_week() needs the day links. matchup.read_matchup() reads the score table if the page has one.
    # The next-week page on the last day of a week and the page before the first games have no score table.
    ("matchup", ("a.Navtarget[href]",), ("table.Datatable tbody tr",)),
    ("buzzindex", ("table.Tst-table tbody tr",), ()),  # trends.read_trends()
]
# readers.read_roster() reads data-pos. A script on the page adds data-pos about 0.1 s after the table appears.
TEAM_READY = (("table#statTable0 tbody tr[data-pos]",), ())
# In the live check of 2026-10-21, the score table appeared 0.1 s or less after the day links.
# A page with no score table uses the full wait, so the wait is short: 5 times the time of that check (#93).
# The wait was 2 s before #93.
SCORE_WAIT_SECONDS = 0.5


class PageNotReady(RuntimeError):
    """A Yahoo page did not show the element that its reader needs before the timeout."""


class UnknownPage(ValueError):
    """No page kind in READY matches the page path, so get() does not know which element to wait for."""


def ready_selectors(path):
    """(required selectors, optional selectors) of the elements that the readers of the page at path need.

    A path that matches no page kind raises UnknownPage. Add the page kind and its elements to READY.
    """
    for start, required, optional in READY:
        if path.startswith(start):
            return required, optional
    if path[:1].isdigit():
        return TEAM_READY
    raise UnknownPage(
        f"No page kind matches the Yahoo page path {path!r}. "
        "Add the page kind and the elements that its reader needs to READY in adds/session.py."
    )


class League:
    """The pages of one Yahoo league. get("players?status=FA") returns the HTML of /nba/<league>/players?status=FA.

    wait_seconds: the time that get() waits for the element that the reader of the page needs.
    pages: the calls of get() that opened a page, for the run time of each sub-step (adds/timing.py, #89).
    A sign-in opens the page again, but the page counts one time.
    """

    def __init__(self, page, league, wait_seconds=WAIT_SECONDS):
        self.page = page
        self.base = f"{SITE}/nba/{league}"
        self.wait_seconds = wait_seconds
        self.pages = 0

    def get(self, path):
        url = f"{self.base}/{path}"
        try:
            required, optional = ready_selectors(path)
        except UnknownPage as error:
            raise UnknownPage(f"{error} URL: {url}") from None
        self.pages += 1
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if not self.page.url.startswith(SITE):
            self._sign_in(url)
        # Do not wait for networkidle. Yahoo pages keep loading ads, so that wait used its full timeout on each page.
        for selector in required:
            try:
                self.page.wait_for_selector(selector, state="attached", timeout=self.wait_seconds * 1000)
            except PlaywrightTimeout:
                raise PageNotReady(
                    f"The Yahoo page {url} did not show the element {selector} in {self.wait_seconds} s. "
                    "The reader of this page needs that element."
                ) from None
        for selector in optional:
            try:
                self.page.wait_for_selector(selector, state="attached", timeout=int(SCORE_WAIT_SECONDS * 1000))
            except PlaywrightTimeout:
                pass  # The page has no such element. The reader gets the page as it is.
        return self.page.content()

    def _sign_in(self, url):
        """Wait for a manual sign-in in the Edge window, then open url again."""
        print("The Yahoo session has expired. Sign in to Yahoo in the Edge window.")
        print(f"The planner continues after the sign-in. You have {SIGN_IN_MINUTES} minutes.")
        self.page.wait_for_url(f"{SITE}/**", timeout=SIGN_IN_MINUTES * 60000)
        print("Sign-in complete. Edge keeps the new session in .auth/yahoo/.")
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)


@contextmanager
def open_league(league, wait_seconds=WAIT_SECONDS):
    """Open Edge with the saved Yahoo profile and give a League. Edge closes at the end of the with block.

    wait_seconds: see League.

    Edge opens in a visible window. Yahoo blocked an automated sign-in in October 2026, and a visible window
    lets you sign in by hand when the session has expired.
    """
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            yield League(page, league, wait_seconds)
        finally:
            context.close()
