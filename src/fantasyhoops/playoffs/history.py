"""The history file of the Playoffs page (#230): the weekly Totals of your best core at each planning run.

It writes output/adds/playoff_history.json, next to the week files of the planning run (adds/week_file.py). The path
comes from common.OUT. The trade run and the refresh command do not write or remove the file.

The file holds one row for each run date, sorted by date. A second run on the same date replaces the row of that date.
A row is {made, core, weeks: {week: {total, rank}}, total}: the date of the player file, the ids of the best
[playoffs] core players of your roster, and the weekly Total and its rank of 14 for each playoff week (owner
decision 1 of 2026-11-02 on #230). historyRow() of core/starts.js gives the numbers. This module runs it in Node,
so the planning run and the page use the same weekly math. With no Node, the run prints a warning and adds no row.
"""

import json
import shutil
import subprocess

from fantasyhoops.core import common
from fantasyhoops.core.lineup import ENGINE_JS

FILE = "playoff_history.json"
TIMEOUT = 120  # seconds for the Node run

# argv: core/starts.js. stdin: {players, data, opts}. stdout: the historyRow() result.
DRIVER = """
const S = require(process.argv[1]);
let text = "";
process.stdin.on("data", c => (text += c));
process.stdin.on("end", () => {
  const { players, data, opts } = JSON.parse(text);
  process.stdout.write(JSON.stringify(S.historyRow(players, data, opts)));
});
"""


def path():
    """The history file, from common.OUT at the time of the call."""
    return common.OUT / "adds" / FILE


def read():
    """The rows of the history file, sorted by date. [] if the file is missing or bad."""
    try:
        rows = json.loads(path().read_text(encoding="utf-8"))["rows"]
        return sorted((r for r in rows if isinstance(r, dict) and "made" in r), key=lambda r: r["made"])
    except (OSError, ValueError, KeyError, TypeError):
        return []


def write(rows):
    """Write rows to the history file. Return the path."""
    file = path()
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({"rows": rows}, indent=1) + "\n", encoding="utf-8")
    return file


def added(rows, row):
    """The rows with row in place of the row of the same date, sorted by date."""
    return sorted([r for r in rows if r["made"] != row["made"]] + [row], key=lambda r: r["made"])


def engine_data(data):
    """The engine data of core/starts.js from the page data: the slots, the weeks, the bonus and the days."""
    keep = ("slots", "util", "weeks", "quality_bonus")
    days = [{k: d[k] for k in ("date", "week", "quality", "teams", "b2b")} for d in data["days"]]
    return {**{k: data[k] for k in keep}, "days": days}


def compute(data):
    """The history row of the page data (playoffs/page.py page_data()), or None with a warning if Node fails."""
    if shutil.which("node") is None:
        print("Warning: node is not on PATH, so the run adds no row to the Playoffs history.")
        return None
    opts = {
        "n": data["core"],
        "roster_spots": data["roster_spots"],
        "adds": data["adds"],
        "v": data["v"],
        "few": data["weak"]["few"],
        "weak": data["weak"],
    }
    given = {"players": data["players"], "data": engine_data(data), "opts": opts}
    try:
        out = subprocess.run(
            ["node", "-e", DRIVER, str(ENGINE_JS)],
            input=json.dumps(given),
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            timeout=TIMEOUT,
        )
        got = json.loads(out.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Warning: the run adds no row to the Playoffs history ({type(error).__name__}: {error}).")
        return None
    weeks = {w: {"total": round(x["total"], 3), "rank": x["rank"]} for w, x in got["weeks"].items()}
    return {"made": data["made"], "core": got["core"], "weeks": weeks, "total": round(got["total"], 3)}


def record(data):
    """Add the row of this run to the history file. Return the rows of the file after the run."""
    rows = read()
    row = compute(data)
    if row is None:
        return rows
    rows = added(rows, row)
    write(rows)
    return rows


def earlier(rows, made):
    """The rows of the runs before the date made: the trend points before the core on the page now."""
    return [r for r in rows if r["made"] < made]
