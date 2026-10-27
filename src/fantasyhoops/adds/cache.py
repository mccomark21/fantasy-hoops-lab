"""The cache of Yahoo pages that do not change during a day (#91). It writes output/adds/cache/.

The cache keeps the HTML of a page by its page path, the path that League.get() takes (adds/session.py).
It keeps two kinds of entries:
- "day": the team-filtered lists and the market pages in the recent view (S_AL14). An entry is good until the end
  of the day of the read. The entries of one day are in output/adds/cache/day/<YYYY-MM-DD>/.
- "kept": the Transaction Trends page of a day before today. That page does not change, so the entry is good for
  good. The entries are in output/adds/cache/kept/.
The planning run (plan.py) chooses the pages that go through the cache. It never sends the team page, the matchup
pages, the waiver list, a list in the projected view or the Transaction Trends page of today through the cache.
A page from the cache opens no Yahoo page, so the page count of the timers (adds/timing.py) does not count it.
"""
import hashlib
import json
import os
import shutil
from datetime import datetime

from fantasyhoops.core.common import OUT

CACHE = OUT / "adds" / "cache"
DAY, KEPT = "day", "kept"


class PageCache:
    """The page cache of one planning run.

    today: the date of the run. A "day" entry of an earlier date is not used.
    use: False (--no-cache): the run reads each page from Yahoo and writes it over the cached page.
    folder: the cache folder (default: CACHE at the time of the call). clock: gives the read time of a new entry.
    hits: the pages from the cache, by kind. day_time: the earliest read time of a "day" entry that the run used.
    """

    def __init__(self, today, use=True, folder=None, clock=datetime.now):
        self.today, self.use, self.folder, self.clock = today, use, folder or CACHE, clock
        self.hits = {DAY: 0, KEPT: 0}
        self.day_time = None

    def remove_old_days(self):
        """Delete the "day" entries of the days before today. The run cannot use them again."""
        days = self.folder / DAY
        if not days.is_dir():
            return
        for entry in days.iterdir():
            if entry.is_dir() and entry.name != f"{self.today:%Y-%m-%d}":
                shutil.rmtree(entry, ignore_errors=True)

    def day(self, yahoo):
        """A reader with get(path) that keeps each page until the end of today. yahoo: the session.League."""
        return CachedPages(self, yahoo, DAY)

    def kept(self, yahoo):
        """A reader with get(path) that keeps each page for good. yahoo: the session.League."""
        return CachedPages(self, yahoo, KEPT)

    def _file(self, kind, path):
        name = hashlib.sha1(path.encode("utf-8")).hexdigest() + ".json"
        if kind == DAY:
            return self.folder / DAY / f"{self.today:%Y-%m-%d}" / name
        return self.folder / KEPT / name

    def load(self, kind, path):
        """The HTML of path from the cache, or None. With use False, always None."""
        if not self.use:
            return None
        file = self._file(kind, path)
        try:
            entry = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if entry.get("path") != path:
            return None
        self.hits[kind] += 1
        if kind == DAY:
            read_at = datetime.fromisoformat(entry["read_at"])
            self.day_time = read_at if self.day_time is None else min(self.day_time, read_at)
        return entry["html"]

    def save(self, kind, path, html):
        """Write the HTML of path in the cache. The write goes to a temporary file first, so a stopped run leaves
        no half-written entry."""
        file = self._file(kind, path)
        file.parent.mkdir(parents=True, exist_ok=True)
        part = file.with_suffix(".part")
        entry = {"path": path, "read_at": self.clock().isoformat(timespec="seconds"), "html": html}
        part.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        os.replace(part, file)

    def line(self):
        """The line of the page and the terminal that says which pages came from the cache. None with no page."""
        parts = []
        if self.hits[DAY]:
            parts.append(f"The recent view: {_pages(self.hits[DAY])} from the cache of {self.day_time:%Y-%m-%d %H:%M}.")
        if self.hits[KEPT]:
            parts.append(f"Transaction Trends: {_pages(self.hits[KEPT])} of earlier days from the cache.")
        return " ".join(parts) or None


def _pages(n):
    return f"{n} page" + ("" if n == 1 else "s")


class CachedPages:
    """A reader with the get() of session.League. get() gives the page from the cache if it has the page.
    Otherwise get() reads the page from Yahoo and writes it in the cache."""

    def __init__(self, cache, yahoo, kind):
        self.cache, self.yahoo, self.kind = cache, yahoo, kind

    def get(self, path):
        html = self.cache.load(self.kind, path)
        if html is None:
            html = self.yahoo.get(path)
            self.cache.save(self.kind, path, html)
        return html
