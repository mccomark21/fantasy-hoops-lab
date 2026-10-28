"""The cache of Yahoo pages that do not change during a day (#91). It writes output/adds/cache/.

The cache keeps the HTML of a page by its page path, the path that League.get() takes (adds/session.py).
It keeps two kinds of entries:
- "day": an entry that is good until the end of the day of the read. The entries of one day are in
  output/adds/cache/day/<YYYY-MM-DD>/. The run keeps the team-filtered lists and the market pages in the recent view
  (S_AL14) and the Transaction Trends page of yesterday as "day" entries.
- "kept": an entry that is good for good. The entries are in output/adds/cache/kept/. The run keeps the Transaction
  Trends page of a day up to today - 2 days as a "kept" entry. Yahoo can still change the page of yesterday.
The planning run (plan.py) chooses the pages that go through the cache. It never sends the team page, the matchup
pages, the waiver list, a list in the projected view or the Transaction Trends page of today through the cache.
A page from the cache opens no Yahoo page, so the page count of the timers (adds/timing.py) does not count it.
The cache is only a speed-up. A bad entry is a miss, and a failed write prints a warning. Neither stops the run.
"""

import hashlib
import json
import os
import shutil
import uuid
from datetime import date, datetime, timedelta

from fantasyhoops.core import common

DAY, KEPT = "day", "kept"  # the kinds of entries
RECENT, TRENDS = "recent", "trends"  # the page groups that the cache line counts
KEPT_AGE = 2  # a Transaction Trends page is a "kept" entry from this number of days before today


def cache_dir():
    """The cache folder: output/adds/cache, from common.OUT at the time of the call."""
    return common.OUT / "adds" / "cache"


class PageCache:
    """The page cache of one planning run.

    today: the date of the run. A "day" entry of an earlier date is not used.
    use: False (--no-cache): the run reads each page from Yahoo and writes it over the cached page.
    folder: the cache folder (default: cache_dir() at the time of the call). clock: gives the read time of a new entry.
    hits: the pages from the cache, by page group. recent_time: the earliest read time of a cached recent page.
    """

    def __init__(self, today, use=True, folder=None, clock=datetime.now):
        self.today, self.use, self.folder, self.clock = today, use, folder or cache_dir(), clock
        self.hits = {RECENT: 0, TRENDS: 0}
        self.recent_time = None

    def remove_old_days(self):
        """Delete the "day" entries of the days before today. The run cannot use them again.

        A folder of a later day or a folder whose name is not a date stays.
        """
        days = self.folder / DAY
        if not days.is_dir():
            return
        for entry in days.iterdir():
            try:
                day = date.fromisoformat(entry.name)
            except ValueError:
                continue
            if entry.is_dir() and day < self.today:
                shutil.rmtree(entry, ignore_errors=True)

    def recent(self, yahoo):
        """A reader with get(path) for the pages in the recent view: "day" entries. yahoo: the session.League."""
        return CachedPages(self, yahoo, DAY, RECENT)

    def trends(self, yahoo, day):
        """The reader of the Transaction Trends page of day. yahoo: the session.League.

        Today: yahoo, with no cache. Yesterday: a "day" entry. Up to today - KEPT_AGE days: a "kept" entry.
        """
        if day >= self.today:
            return yahoo
        kind = KEPT if day <= self.today - timedelta(days=KEPT_AGE) else DAY
        return CachedPages(self, yahoo, kind, TRENDS)

    def _file(self, kind, path):
        name = hashlib.sha1(path.encode("utf-8")).hexdigest() + ".json"
        if kind == DAY:
            return self.folder / DAY / f"{self.today:%Y-%m-%d}" / name
        return self.folder / KEPT / name

    def load(self, kind, path, group):
        """The HTML of path from the cache, or None. With use False, always None.

        An entry that is not readable, or that has a wrong shape, another path or a bad read time, is a miss.
        """
        if not self.use:
            return None
        try:
            entry = json.loads(self._file(kind, path).read_text(encoding="utf-8"))
            if not isinstance(entry, dict) or entry.get("path") != path or not isinstance(entry.get("html"), str):
                return None
            read_at = datetime.fromisoformat(entry["read_at"])
        except (OSError, ValueError, TypeError, KeyError):
            return None
        self.hits[group] += 1
        if group == RECENT:
            self.recent_time = read_at if self.recent_time is None else min(self.recent_time, read_at)
        return entry["html"]

    def save(self, kind, path, html):
        """Write the HTML of path in the cache. The write goes to a temporary file with a unique name first, so a
        stopped run leaves no half-written entry. A failed write prints a warning and does not stop the run."""
        file = self._file(kind, path)
        part = file.with_name(f"{file.stem}.{uuid.uuid4().hex}.part")
        entry = {"path": path, "read_at": self.clock().isoformat(timespec="seconds"), "html": html}
        try:
            file.parent.mkdir(parents=True, exist_ok=True)
            part.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
            os.replace(part, file)
        except OSError as error:
            print(f"Warning: the run did not write the page in the cache ({file}): {error}. The run continues.")
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass

    def line(self):
        """The line of the Run time section of the page that says which pages came from the cache. None with no page."""
        parts = []
        if self.hits[RECENT]:
            parts.append(
                f"The recent view: {_pages(self.hits[RECENT])} from the cache of {self.recent_time:%Y-%m-%d %H:%M}."
            )
        if self.hits[TRENDS]:
            parts.append(f"Transaction Trends: {_pages(self.hits[TRENDS])} of earlier days from the cache.")
        return " ".join(parts) or None


def _pages(n):
    return f"{n} page" + ("" if n == 1 else "s")


class CachedPages:
    """A reader with the get() of session.League. get() gives the page from the cache if it has the page.
    Otherwise get() reads the page from Yahoo and writes it in the cache.

    kind: DAY or KEPT. group: RECENT or TRENDS, the count of the cache line that a page from the cache adds to.
    """

    def __init__(self, cache, yahoo, kind, group):
        self.cache, self.yahoo, self.kind, self.group = cache, yahoo, kind, group

    def get(self, path):
        html = self.cache.load(self.kind, path, self.group)
        if html is None:
            html = self.yahoo.get(path)
            self.cache.save(self.kind, path, html)
        return html

    def get_many(self, paths):
        """The HTML of each page of paths. The pages that are not in the cache go to Yahoo together (get_all())."""
        return get_all([(self, path) for path in paths])


def get_all(reads):
    """The HTML of each (reader, path) of reads, in order. A reader is a session.League or CachedPages.

    A page from the cache opens no Yahoo page. The other pages of one League go in one League.get_many(), so its raw
    requests overlap (#108). A reader with no get_many() (for example a fake of a test) reads one page at a time.
    """
    out = [None] * len(reads)
    misses = {}  # id of the League -> (League, [(index, CachedPages or None, path)])
    for n, (reader, path) in enumerate(reads):
        cached = reader if isinstance(reader, CachedPages) else None
        if cached is not None:
            out[n] = cached.cache.load(cached.kind, path, cached.group)
            if out[n] is not None:
                continue
        yahoo = cached.yahoo if cached is not None else reader
        misses.setdefault(id(yahoo), (yahoo, []))[1].append((n, cached, path))
    for yahoo, items in misses.values():
        paths = [path for _, _, path in items]
        many = getattr(yahoo, "get_many", None)
        htmls = many(paths) if many is not None else [yahoo.get(path) for path in paths]
        for (n, cached, path), html in zip(items, htmls):
            out[n] = html
            if cached is not None:
                cached.cache.save(cached.kind, path, html)
    return out
