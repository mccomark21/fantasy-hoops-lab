# Fantasy Hoops Lab

Analysis tools for one Yahoo fantasy basketball league, 2026-27 season.

The project started as custom draft rankings. Now it holds one tool for each part of the season: the draft, the weekly adds and the tools that come later. All tools share one config file, one set of input data and one Python package, `fantasyhoops`.

## League format

| Setting | Value |
|---|---|
| Platform | Yahoo, head-to-head |
| Teams | 14 |
| Draft | Auction, $200 budget |
| Roster | 10 spots: 6 starters (PG, SG, SF, PF, C, Util) and 4 bench |
| Adds | 5 each week |
| Categories | 9 |
| Punted categories | FG%, FT%, TO |
| Ranked categories | PTS, REB, AST, 3PM, BLK, STL |
| Fantasy playoffs | Weeks 19 to 21 |

## Tools

| Tool | Package | Status | Documentation |
|---|---|---|---|
| Draft tools: rankings, draft board, auction simulator, keeper report | `fantasyhoops.draft` | Used for the 2026-27 draft | [docs/draft/](docs/draft/README.md) |
| Weekly adds planner | `fantasyhoops.adds` | Planned | [docs/adds/](docs/adds/README.md) |

The tools publish their pages to one public site on GitHub Pages: `https://mccomark21.github.io/fantasy-hoops-lab/`. The home page links to each tool. The draft board is at `/draft/` and the adds plan is at `/adds/`. The shared publish step is `core/publish.py`.

The terms that more than one tool uses are in the [glossary](docs/glossary.md). Each important decision has an ADR in [docs/adr/](docs/adr/).

## Repo layout

```
config.toml               All settings. [league] applies to all tools.
pyproject.toml            Package metadata, dependencies and pytest settings
src/fantasyhoops/
  core/                   Shared code: paths and config (common), player identity, valuation, NBA schedule, site publish
  fetch/                  Downloads: espn.py (rosters, schedule), rotation.py (rotation log), yahoo.py (positions, prices, ADP)
  draft/                  Draft tools
  adds/                   Weekly adds planner (planned)
tests/
  core/                   Tests for core/
  fetch/                  Tests for fetch/, with saved ESPN JSON in fixtures/
  draft/                  Tests for draft/
data/                     Inputs that all tools share (not tracked by Git)
output/                   Generated files, one folder for each tool (not tracked by Git)
docs/
  glossary.md             Terms that more than one tool uses
  adr/                    Architecture decision records
  draft/                  Draft tools guide and the category weights
  adds/                   Weekly adds planner guide
```

## Getting started

### Prerequisites

- Python 3.11 or later. The code uses `tomllib`.
- Node.js, for the tests of the JavaScript engines on the draft board. Without Node, pytest skips those tests.
- A season projections file. Git does not track CSV files, so a new clone of the repo does not include it.

### Installation

1. Install the package and its dependencies in editable mode:

   ```
   python -m pip install -e ".[test]"
   ```

2. Install the browser that `fetch/yahoo.py` uses:

   ```
   python -m playwright install chromium
   ```

3. Put the season projections in `data/Projections_YYYY-MM-DD.csv`. Use the download date. The tools use the newest file.

### Run a tool

Each tool is a module. Run it with `python -m` from the repo root:

```
python -m fantasyhoops.fetch.espn       # Download NBA rosters and the schedule
python -m fantasyhoops.fetch.rotation   # Add the finished games to the rotation log
python -m fantasyhoops.draft.board      # Write the draft board
```

The rotation log is a record of each check-in and check-out of each NBA player in each regular-season game. `fetch/rotation.py` writes it:

- `data/rotation_log.csv`: one row for each stint, with the score at the check-in and at the check-out.
- `data/rotation_scores.csv`: one row for each play that changes the score.

The log starts at the first game of the season. A run reads only the games that are not in the log, so run it again after each game day. The planning run does not update the log. The run prints each player whose stints are more than 1.5 minutes from his box-score minutes. Other tools read the log with `core/rotation.py`. The close-game settings are in `[rotation]` in `config.toml`.

The full list of draft commands is in [docs/draft/](docs/draft/README.md#usage).

## Configuration

All settings are in [`config.toml`](config.toml). The `[league]` section applies to all tools. The other sections are for the draft tools. A new tool adds its own section.

## Add a tool

1. Make a subpackage in `src/fantasyhoops/`, for example `src/fantasyhoops/adds/`.
2. Put shared logic in `core/`. Put logic that only this tool uses in the subpackage.
3. Write the files of the tool in `output/<tool>/`. See `OUT` in `src/fantasyhoops/draft/__init__.py`.
4. Put the settings in a new section of `config.toml`.
5. Put the tests in `tests/<tool>/`.
6. Add a row to the [Tools](#tools) table and a guide in `docs/<tool>/README.md`.
7. Put the terms that more than one tool uses in [docs/glossary.md](docs/glossary.md).

## Testing

```
python -m pytest
```

The publish tests (`tests/core/test_publish.py`, `tests/draft/test_publish.py`) make temporary Git repos, so they need `git` on the `PATH`.

## Roadmap

Planned work is in [GitHub issues](https://github.com/mccomark21/fantasy-hoops-lab/issues).
