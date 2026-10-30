import functools
import html
import http.server
import json
import re
import subprocess
import threading
from datetime import date

import pytest

from fantasyhoops.core import common
from fantasyhoops.core.publish import BRANCH

REAL_OUT = common.OUT  # the real output/ folder, before a fixture changes common.OUT


def output_files(folder):
    """Each file under folder, as {path: (size, modification time)}. No folder gives {}."""
    if not folder.exists():
        return {}
    return {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*") if p.is_file()}


@pytest.fixture(scope="session", autouse=True)
def real_output_unchanged():
    """The session fails if a test adds, changes or removes a file under the real output/ folder (#127)."""
    before = output_files(REAL_OUT)
    yield
    after = output_files(REAL_OUT)
    changed = sorted(str(p) for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    assert not changed, f"The tests changed these files under {REAL_OUT}: {changed}"


@pytest.fixture(autouse=True)
def output_in_tmp(monkeypatch, tmp_path):
    """Each test writes its output files in tmp_path: common.OUT points there (#127)."""
    monkeypatch.setattr(common, "OUT", tmp_path)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    """A clone with one commit on main and a bare 'origin'."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", str(origin), str(work))
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.com")
    (work / "README.md").write_text("main\n")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "init")
    git(work, "push", "origin", "main")
    return work


@pytest.fixture
def remote_pages():
    """A function that gives the files on gh-pages in origin, as {path: text}. A binary file (the font, a PNG icon) has no text."""

    def pages(repo):
        git(repo, "fetch", "origin", BRANCH)
        names = git(repo, "ls-tree", "-r", "--name-only", "FETCH_HEAD").split()
        return {n: "" if n.endswith((".woff2", ".png")) else git(repo, "show", f"FETCH_HEAD:{n}") for n in names}

    return pages


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def player_records_of(page):
    """A player record for each name link of the HTML text page (#186), in the shape of players/data.py."""
    names = dict(re.findall(r'<a class="lab-pname" href="#player=([a-z-]+)" data-player="[a-z-]+">([^<]*)</a>', page))
    return [
        {
            "slug": s,
            "name": html.unescape(n),
            "team": "PHI",
            "pos": "PG",
            "owner": None,
            "mine": False,
            "val": 1.5,
            "games": 5,
            "signals": [],
        }
        for s, n in names.items()
    ]


class ModalSite:
    """A local web site in a folder and a Chromium page from Playwright, for the player modal tests (#186).

    The player file needs a web server: a page cannot fetch a file:// URL.
    """

    def __init__(self, root, url, page):
        self.root, self.url, self.page = root, url, page

    def open(self, folder, text, records=None, hash=""):
        """Write text as /<folder>/index.html and the player file at /players/. Open the page. Return the page.

        records: the players of the file. None: a record for each name link of text (player_records_of()).
        """
        from fantasyhoops.core import profile
        from fantasyhoops.players.page import player_file

        found = player_records_of(text) if records is None else records
        content = json.dumps(player_file(found, date(2026, 10, 30), "Projections_2026-10-12.csv"))
        for name, data in ((f"{folder}/index.html", text), (f"players/{profile.DATA_FILE}", content)):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data, encoding="utf-8")
        self.page.goto(f"{self.url}{folder}/{hash}")
        return self.page

    def check_modal(self):
        """check_modal() on the open page."""
        return check_modal(self.page)


@pytest.fixture
def modal_site(tmp_path):
    """A ModalSite at 1440 x 900. The test skips if Chromium is not installed."""
    from playwright.sync_api import Error, sync_playwright

    root = tmp_path / "site"
    root.mkdir()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_QuietHandler, directory=str(root)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Error as e:
                pytest.skip(f"Chromium for Playwright is not installed: {str(e).splitlines()[0]}")
            try:
                yield ModalSite(
                    root,
                    f"http://127.0.0.1:{server.server_address[1]}/",
                    browser.new_page(viewport={"width": 1440, "height": 900}),
                )
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


def check_modal(pg):
    """Check the player modal on a page with name links (#186): the hash, Back, Esc, Close, the backdrop, the focus
    and the fit at 1440 x 900. Return the slug of the first shown name link."""
    from fantasyhoops.core import chart

    link = pg.locator("a.lab-pname:visible").first
    slug, name = link.get_attribute("data-player"), link.inner_text()
    dialog = pg.locator("#lab-pmodal")

    def open_it():
        pg.locator(f'a.lab-pname[data-player="{slug}"]:visible').first.click()
        dialog.wait_for(state="visible")
        pg.locator("#lab-pm-name").wait_for()

    def closed_on_the_name():
        assert not pg.evaluate("document.getElementById('lab-pmodal').open")
        assert pg.evaluate("document.activeElement.dataset.player") == slug
        assert pg.evaluate("location.hash") == ""

    open_it()
    assert pg.evaluate("location.hash") == f"#player={slug}"
    assert pg.locator("#lab-pm-name").inner_text().lower() == name.lower()
    assert pg.locator("#lab-pmodal .lc-q").count() == 4
    assert pg.locator("#lab-pm-full").get_attribute("href") == f"../players/#{slug}"
    assert pg.evaluate("document.activeElement.id") == "lab-pm-close"
    # The focus stays in the modal: Shift+Tab from the first control goes to the last, Tab from the last to the first.
    pg.keyboard.press("Shift+Tab")
    assert pg.evaluate("document.getElementById('lab-pmodal').contains(document.activeElement)")
    for _ in range(12):
        pg.keyboard.press("Tab")
        assert pg.evaluate("document.getElementById('lab-pmodal').contains(document.activeElement)")
    fit = pg.evaluate(
        "(() => { const d = document.getElementById('lab-pmodal'); return [d.scrollHeight, d.clientHeight]; })()"
    )
    assert fit[0] <= fit[1], fit  # at 1440 x 900 the card fits with no scroll
    assert chart.style_problems(pg.content()) == []
    pg.keyboard.press("Escape")
    pg.wait_for_function("!document.getElementById('lab-pmodal').open")
    closed_on_the_name()
    open_it()
    pg.go_back()
    pg.wait_for_function("!document.getElementById('lab-pmodal').open")
    closed_on_the_name()
    open_it()
    pg.locator("#lab-pm-close").click()
    pg.wait_for_function("!document.getElementById('lab-pmodal').open")
    closed_on_the_name()
    open_it()
    pg.mouse.click(4, 4)  # the backdrop
    pg.wait_for_function("!document.getElementById('lab-pmodal').open")
    closed_on_the_name()
    # A copied link opens the modal on load. Close removes the hash in place.
    pg.goto(pg.url.split("#")[0] + f"#player={slug}")
    dialog.wait_for(state="visible")
    pg.locator("#lab-pm-name").wait_for()
    pg.locator("#lab-pm-close").click()
    assert not pg.evaluate("document.getElementById('lab-pmodal').open") and pg.evaluate("location.hash") == ""
    return slug
