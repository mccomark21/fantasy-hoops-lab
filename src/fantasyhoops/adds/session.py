"""The Yahoo session: Microsoft Edge with the saved sign-in in .auth/yahoo/ (see docs/adr/0001).

This module only opens pages and returns their HTML. It never submits a form or clicks a button.
The readers in adds/readers.py read the HTML. Only one process can use the saved profile at a time.
The list pages, the matchup pages and Transaction Trends come from raw requests with the cookies of Edge, at most
MAX_REQUESTS at a time (#108). The team page comes from Edge, because a script on the page adds data-pos.
Requirement: Microsoft Edge and pip install playwright. Edge is the browser, so "playwright install" is not necessary.
"""

import asyncio
import re
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
# The HTTP status of a page when Yahoo blocks the requests of the session.
# On 2026-10-27, Yahoo gave 999 "Request denied" during spike #95. A check for 429 alone does not find that block (#107).
BLOCK_STATUSES = (999, 429)
# The page kinds that come from raw requests (#108), by the start of the page path, with the class of the element
# that the reader needs. Spike #95 found the same reader results on the raw HTML and on the HTML of Edge.
RAW = {"players": "players", "matchup": "Navtarget", "buzzindex": "Tst-table"}
# Spike #95 read 4 raw pages at a time. Yahoo blocked the session after about 390 loads in 5 minutes. Keep this low.
MAX_REQUESTS = 4
REQUEST_TIMEOUT_MS = 60000


class PageNotReady(RuntimeError):
    """A Yahoo page did not show the element that its reader needs before the timeout."""


class YahooBlocked(RuntimeError):
    """Yahoo blocked the requests of the session. The run stops, because each retry is one more Yahoo load (#107)."""


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


def check_status(response, url):
    """Raise YahooBlocked when the response of the page at url has a block status (BLOCK_STATUSES).

    response: the return value of page.goto(). It is None when the page did not load a new document.
    """
    if response is None or response.status not in BLOCK_STATUSES:
        return
    raise YahooBlocked(
        f"Yahoo blocked the requests of this session. The page {url} gave HTTP {response.status}. "
        "The planning run stopped. Start a new run after the block ends."
    )


def raw_kind(path):
    """The class of the element that the reader of the raw page at path needs, or None for a page from Edge."""
    return next((element for start, element in RAW.items() if path.startswith(start)), None)


def check_raw_status(status, url):
    """Raise YahooBlocked when a raw response of the page at url has a block status (BLOCK_STATUSES)."""
    if status in BLOCK_STATUSES:
        raise YahooBlocked(
            f"Yahoo blocked the requests of this session. The page {url} gave HTTP {status}. "
            "The planning run stopped. Start a new run after the block ends."
        )


def has_element(html, element):
    """True if the HTML has an element with the class element. A text search, because a parse takes too long."""
    return re.search(r"""class=["'][^"']*\b""" + re.escape(element) + r"\b", html) is not None


def raw_fetcher(request):
    """A function urls -> [(status, final URL, HTML)] that reads all urls at the same time with request.

    request: the APIRequestContext of the Edge context (context.request). It sends the cookies of the profile.
    The sync API of Playwright reads one URL at a time. So the function runs the async requests under the sync API
    on its event loop, and the reads overlap. This uses two private names of Playwright (_impl_obj, _sync). If they
    change, the function reads one URL at a time with the sync API.
    """
    impl, run = getattr(request, "_impl_obj", None), getattr(request, "_sync", None)

    async def one(url):
        response = await impl.get(url, timeout=REQUEST_TIMEOUT_MS)
        try:
            return response.status, response.url, await response.text()
        finally:
            await response.dispose()

    async def all_of(urls):
        return await asyncio.gather(*(one(url) for url in urls))

    def serial(url):
        response = request.get(url, timeout=REQUEST_TIMEOUT_MS)
        try:
            return response.status, response.url, response.text()
        finally:
            response.dispose()

    def fetch(urls):
        if impl is None or run is None or len(urls) == 1:
            return [serial(url) for url in urls]
        return run(all_of(list(urls)))

    return fetch


class League:
    """The pages of one Yahoo league. get("players?status=FA") returns the HTML of /nba/<league>/players?status=FA.

    wait_seconds: the time that Edge waits for the element that the reader of the page needs.
    fetch: a function urls -> [(status, final URL, HTML)], for example raw_fetcher(). With fetch, the page kinds of
    RAW come from raw requests (#108). None: all pages come from Edge.
    pages: the pages that the League opened, for the run time of each sub-step (adds/timing.py, #89). A raw read is
    one page. A sign-in opens the page again, but the page counts one time.
    """

    def __init__(self, page, league, wait_seconds=WAIT_SECONDS, fetch=None):
        self.page = page
        self.base = f"{SITE}/nba/{league}"
        self.wait_seconds = wait_seconds
        self.fetch = fetch
        self.pages = 0

    def get(self, path):
        """The HTML of the page at path."""
        return self.get_many([path])[0]

    def get_many(self, paths):
        """The HTML of each page of paths, in the order of paths. The raw pages go MAX_REQUESTS at a time."""
        out = [None] * len(paths)
        raw = []
        for n, path in enumerate(paths):
            if self.fetch is not None and raw_kind(path) is not None:
                raw.append(n)
            else:
                out[n] = self._browser_get(path)
        for start in range(0, len(raw), MAX_REQUESTS):
            batch = raw[start : start + MAX_REQUESTS]
            for n, html in zip(batch, self._raw_get([paths[n] for n in batch])):
                out[n] = html
        return out

    def _raw_get(self, paths):
        """The HTML of the raw pages of paths (MAX_REQUESTS or fewer), read at the same time."""
        urls = [f"{self.base}/{path}" for path in paths]
        self.pages += len(urls)
        results = self.fetch(urls)
        for url, (status, _, _) in zip(urls, results):
            check_raw_status(status, url)  # a block stops the run before a sign-in or a second read
        out = []
        for path, url, (status, final, html) in zip(paths, urls, results):
            if not final.startswith(SITE):
                # The session has expired. The sign-in uses Edge. Then the raw request reads the page again.
                self._browser_sign_in(url)
                ((status, final, html),) = self.fetch([url])
                check_raw_status(status, url)
                if not final.startswith(SITE):
                    raise PageNotReady(f"The raw request of the Yahoo page {url} went to {final} after the sign-in.")
            element = raw_kind(path)
            if not has_element(html, element):
                raise PageNotReady(
                    f"The raw HTML of the Yahoo page {url} has no element with the class {element}. "
                    "The reader of this page needs that element."
                )
            out.append(html)
        return out

    def _browser_sign_in(self, url):
        """Open url in Edge. If Edge goes to the Yahoo sign-in, wait for a manual sign-in.

        Edge does not open url again after the sign-in, because the raw request reads the page again.
        """
        check_status(self.page.goto(url, wait_until="domcontentloaded", timeout=60000), url)
        if not self.page.url.startswith(SITE):
            self._wait_for_sign_in()

    def _wait_for_sign_in(self):
        """Wait for a manual sign-in in the Edge window."""
        print("The Yahoo session has expired. Sign in to Yahoo in the Edge window.")
        print(f"The planner continues after the sign-in. You have {SIGN_IN_MINUTES} minutes.")
        self.page.wait_for_url(f"{SITE}/**", timeout=SIGN_IN_MINUTES * 60000)
        print("Sign-in complete. Edge keeps the new session in .auth/yahoo/.")

    def _browser_get(self, path):
        """The HTML of the page at path from Edge, after the element that its reader needs appears."""
        url = f"{self.base}/{path}"
        try:
            required, optional = ready_selectors(path)
        except UnknownPage as error:
            raise UnknownPage(f"{error} URL: {url}") from None
        self.pages += 1
        check_status(self.page.goto(url, wait_until="domcontentloaded", timeout=60000), url)
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
        self._wait_for_sign_in()
        check_status(self.page.goto(url, wait_until="domcontentloaded", timeout=60000), url)


@contextmanager
def open_league(league, wait_seconds=WAIT_SECONDS):
    """Open Edge with the saved Yahoo profile and give a League. Edge closes at the end of the with block.

    wait_seconds: see League. The League reads the page kinds of RAW with raw requests of the Edge context.

    Edge opens in a visible window. Yahoo blocked an automated sign-in in October 2026, and a visible window
    lets you sign in by hand when the session has expired.
    """
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            yield League(page, league, wait_seconds, raw_fetcher(context.request))
        finally:
            context.close()
