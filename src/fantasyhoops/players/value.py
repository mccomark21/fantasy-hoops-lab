"""The Value quadrant of the player card (#189): the value of each ESPN game, the dud rate and the spike rate.

- The value of a game: the per-game value (core/valuation.py) of his box-score line, minus the replacement value of
  the planning run. So 0 is the replacement free agent, as for the Val of the header (players/data.py).
- A dud: a game with a value below 0 (below the replacement free agent).
- A spike: a game with a value at the top-30 level or more. The top-30 level is the Val of the player at rank
  spike_rank by Val on the page.
- The hero line, the normal-range band, the range exits and the state line come from the trend functions of
  players/role.py, with the settings of [players.value] in config.toml in place of [players.role].
- consistency_signal() gives the "Consistency" chip of the header when the duds or the spikes are rate_flag of his
  games or more, from consistency_min_games games (owner decision of 2026-10-30: 10).
value_chart() draws the chart with core/chart.py, as the DESIGN.md "Charts" rules say. attach() adds the "value" block
of each player of the player file. The browser script of the quadrant is core/card_value.py.
read_games() reads data/box_scores.csv, data/rotation_log.csv and data/rotation_scores.csv. The module writes no files.
"""

import math
from dataclasses import dataclass

import pandas as pd

from fantasyhoops.core import chart, common
from fantasyhoops.core.common import name_key
from fantasyhoops.core.identity import yahoo_keys
from fantasyhoops.core.rotation import close_games, read_log, read_scores
from fantasyhoops.players import role
from fantasyhoops.players.categories import BOX_COLUMNS

SECTION = "value"  # the settings of the quadrant: [players.value] in config.toml

# The chart: a 580px viewBox, the plot from L to W - R and from T to H - B (the sample "After + tooltips").
W, H, L, R, T, B = 580, 268, 30, 104, 12, 22
DATE_W = 40  # a date under a game needs this many px. With less room, only every k-th game has a date.
MINUS = "−"


def settings(cfg):
    """[players.value] of config.toml as a dict: the trend settings of role.settings(), spike_rank, rate_flag and
    consistency_min_games."""
    return cfg["players"][SECTION]


@dataclass(frozen=True)
class Game:
    """One ESPN game of a player: the game ID, the date, the opponent, a start, a close game and the stat line."""

    game_id: str
    date: object
    opponent: str
    started: bool
    close: bool
    line: dict


def box_games(box, close, overrides):
    """{Yahoo name key: [Game] by date} of the box-score rows of the games that a player played.

    box: data/box_scores.csv as a table. close: {game_id: True for a close game}. overrides: data/name_overrides.csv.
    The names match as in data.played_players(). Two ESPN IDs with one key: the ID with more games stays.
    """
    if box.empty:
        return {}
    to_yahoo = yahoo_keys(overrides)
    played = box[box.played.astype(str) == "True"]
    out = {}
    for _, rows in played.sort_values("date").groupby("player_id", sort=False):
        key = name_key(rows.iloc[-1].player)
        key = to_yahoo.get(key, key)
        games = [
            Game(
                str(r.game_id),
                pd.Timestamp(r.date).date(),
                str(r.opponent),
                str(r.starter) == "True",
                bool(close.get(str(r.game_id), False)),
                {cat: float(getattr(r, col)) for cat, col in BOX_COLUMNS.items()},
            )
            for r in rows.itertuples()
        ]
        if key not in out or len(games) > len(out[key]):
            out[key] = games
    return out


def read_games(cfg, overrides):
    """box_games() of data/box_scores.csv, with the close games of the rotation log. {} with no box-score file."""
    path = common.DATA / "box_scores.csv"
    if not path.exists():
        return {}
    box = pd.read_csv(path, dtype={"game_id": str, "player_id": str})
    close = {}
    log_path, scores_path = common.DATA / "rotation_log.csv", common.DATA / "rotation_scores.csv"
    if log_path.exists() and scores_path.exists():
        found = close_games(read_log(log_path), read_scores(scores_path), cfg)
        close = dict(zip(found.game_id.astype(str), found.close))
    return box_games(box, close, overrides)


def game_values(games, scale, replacement, cfg):
    """The value of each game: pg_value of the line minus replacement, to 2 decimals."""
    from fantasyhoops.adds.value import line_value

    return [round(line_value(g.line, scale, cfg) - replacement, 2) for g in games]


def spike_level(vals, rank):
    """The top-30 level: the Val at rank (1 = best) of vals. With fewer Vals, the last one. None with no Val."""
    found = sorted((v for v in vals if v is not None), reverse=True)
    return found[min(rank, len(found)) - 1] if found else None


def kind(value, spike):
    """ "dud" below 0, "spike" at spike or more, else "normal"."""
    if value < 0:
        return "dud"
    return "spike" if spike is not None and value >= spike else "normal"


@dataclass(frozen=True)
class Trend:
    """The hero line (roll), the mean, the band (lo, hi; None with no band) and the games of a range exit."""

    roll: list
    mean: float
    lo: float | None
    hi: float | None
    exits: list


def trend(values, sd_league, cfg):
    """The Trend of the game values of one player, with role.rolling(), role.band() and role.exits().

    sd_league: role.league_spread() of the game values of all players. None: no band.
    """
    s = role.settings(cfg, SECTION)
    n = len(values)
    roll = role.rolling(values, s["window"])
    low_high = role.band(values, sd_league, cfg, SECTION)
    lo, hi = low_high or (None, None)
    exits = [i for i, _ in role.exits(roll, low_high, n, cfg, SECTION)]
    return Trend(roll, sum(values) / n if n else 0.0, lo, hi, exits)


def f1(value):
    """A number with 1 decimal and a true minus sign."""
    return f"{value:.1f}".replace("-", MINUS)


def signed(value):
    """A value with a sign and 2 decimals, with a true minus sign: "+1.23", "−0.94"."""
    if value is None:
        return "–"
    return ("+" if value > 0 else MINUS if value < 0 else "") + f"{abs(value):.2f}"


def nice_ticks(lo, hi, count=4):
    """About count round tick values that cover lo to hi: (ticks, first tick, last tick)."""
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    span = hi - lo
    mag = 10 ** math.floor(math.log10(span / count))
    step = next((m * mag for m in (1, 2, 2.5, 5, 10) if span / (m * mag) <= count), 10 * mag)
    a, b = math.floor(lo / step) * step, math.ceil(hi / step) * step
    ticks = [round(a + i * step, 6) for i in range(round((b - a) / step) + 1)]
    return ticks, a, b


def _tick_text(value):
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "0") else text.replace("-", MINUS)


def date_text(day):
    """A game date under the chart, for example "Oct 28"."""
    return f"{day:%b} {day.day}"


def context(game):
    """The context line of a game tooltip, for example "Oct 28 vs SA · start · close game"."""
    text = f"{date_text(game.date)} vs {game.opponent} · {'start' if game.started else 'bench'}"
    return text + (" · close game" if game.close else "")


def _hit(x, y, width, height, index):
    """The hit area of one game column. The card script gives it the tab stop and the aria-label of its tooltip."""
    x, y, width, height = (round(v, 2) for v in (x, y, width, height))
    return f'<rect class="lab-c-hit" x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" data-i="{index}"/>'


def value_chart(games, values, tr, spike, window):
    """(The SVG of the Value chart, the tooltip of each game) for the games, their values and their Trend.

    spike: the top-30 level, or None. A tooltip is a dict: ctx, value, label and rows (DESIGN.md "Tooltips"), and x, y0
    and y1, the column and the top and the bottom of its marks in SVG units.
    """
    n = len(games)
    refs = [(0.0, "replacement")] + ([(spike, "top-30 level")] if spike is not None else [])
    span = values + [r for r in tr.roll if r is not None] + [y for y, _ in refs]
    if tr.lo is not None:
        span += [tr.lo, tr.hi]
    lo, hi = min(span), max(span)
    ticks, t_lo, t_hi = nice_ticks(lo - (hi - lo) * 0.05, hi + (hi - lo) * 0.05)
    step = (W - L - R) / max(n, 1)

    def x(i):
        return L + step * (i + 0.5)

    def y(v):
        return T + (H - T - B) * (1 - (v - t_lo) / (t_hi - t_lo))

    plot = chart.Box(L, T, W - L - R, H - T - B)
    roll_pts = [(x(i), y(v)) for i, v in enumerate(tr.roll) if v is not None]
    boxes = [chart.Box(x(i) - 6, y(v) - 6, 12, 12) for i, v in enumerate(values)]
    boxes += chart.line_boxes(roll_pts, 3)
    boxes += [chart.Box(L, y(v) - 1, W - L - R, 2) for v, _ in refs]
    parts = [chart.label(L - 6, y(t) + 4, _tick_text(t), anchor="end") for t in ticks]
    if tr.lo is not None:
        parts.append(chart.band(L, y(tr.hi), W - L - R, y(tr.lo) - y(tr.hi)))
        text = f"normal range {f1(tr.lo)}–{f1(tr.hi)}"
        spot = chart.band_label(text, chart.Box(L, y(tr.hi), W - L - R, y(tr.lo) - y(tr.hi)), boxes)
        if spot:
            parts.append(chart.label(*spot, text))
    ends = []
    for v, name in refs:
        parts.append(chart.ref_line(L, y(v), W - R, y(v)))
        ends.append((y(v), name, "tick"))
    kinds = [kind(v, spike) for v in values]
    for i, (v, k) in enumerate(zip(values, kinds)):
        mark = {"dud": chart.dud, "spike": chart.spike}.get(k, chart.game_dot)
        parts.append(mark(x(i), y(v)))
    parts.append(chart.hero_line(roll_pts))
    if roll_pts:
        parts.append(chart.hero_dot(*roll_pts[-1]))
        if tr.roll[-1] is not None:
            ends.append((roll_pts[-1][1], f"{window}-game {f1(tr.roll[-1])}", "label"))
    heights = chart.end_labels([e[0] for e in ends], T, H - B)
    parts += [chart.label(W - R + chart.END_DX, h + 4, text, kind) for h, (_, text, kind) in zip(heights, ends)]
    for name in ("dud", "spike"):
        for i, k in enumerate(kinds):
            if k == name:
                spot = chart.point_label(name, x(i), y(values[i]), boxes, plot)
                if spot:
                    parts.append(chart.label(*spot, name))
                    break
    for i in tr.exits:
        text = "▲ out" if tr.roll[i] > tr.hi else "▼ out"
        spot = chart.point_label(text, x(i), y(tr.roll[i]), boxes, plot)
        if spot:
            parts.append(chart.label(*spot, text, kind="exit"))
    every = max(1, math.ceil(DATE_W / step))
    parts += [
        chart.label(x(i), H - 6, date_text(g.date), anchor="middle")
        for i, g in enumerate(games)
        if (n - 1 - i) % every == 0
    ]
    # The crosshair: one hidden line that LabCard.bindCrosshair() moves to the game column of the shown card.
    parts.append(f'<line class="lab-c-cross" x1="0" x2="0" y1="{T}" y2="{H - B}" visibility="hidden"/>')
    tips = []
    for i, (g, v, k) in enumerate(zip(games, values, kinds)):
        avg = tr.roll[i]
        line = g.line
        tip = {
            "ctx": context(g),
            "value": signed(v),
            "label": "value" if k == "normal" else f"value · {k}",
            "rows": [
                ["PTS · REB · AST", " · ".join(f"{line[c]:.0f}" for c in ("pts", "reb", "ast"))],
                ["3PM · STL · BLK", " · ".join(f"{line[c]:.0f}" for c in ("threes", "stl", "blk"))],
                [f"{window}-game avg", f"needs {window} games" if avg is None else signed(round(avg, 2))],
            ],
        }
        ys = [y(v)] + ([] if avg is None else [y(avg)])
        tip.update(x=round(x(i), 2), y0=round(min(ys), 2), y1=round(max(ys), 2))
        tips.append(tip)
        parts.append(_hit(x(i) - step / 2, T, step, H - T - B, i))
    label = "Value of each game above replacement, with duds and spikes marked"
    return chart.chart_svg(W, H, "".join(parts), label), tips


def state(n, tr, cfg):
    """The state line under the chart (DESIGN.md "Thin data"), as HTML: role.state(), and under flag_min games
    "One game moves a rate <n> points."."""
    lead, rest = role.state(n, None if tr.lo is None else (tr.lo, tr.hi), cfg, SECTION)
    text = f"<b>{lead}</b> {rest}" if lead else rest
    if n < role.settings(cfg, SECTION)["flag_min"]:
        text += f" One game moves a rate {round(100 / n)} points."
    return text


def value_block(games, values, sd_league, spike, cfg):
    """The "value" block of a player in the player file: n, consistency_min, rate_flag, duds, spikes, svg, state and
    tips."""
    s = settings(cfg)
    tr = trend(values, sd_league, cfg)
    svg, tips = value_chart(games, values, tr, spike, s["window"])
    kinds = [kind(v, spike) for v in values]
    return {
        "n": len(values),
        "consistency_min": s["consistency_min_games"],
        "rate_flag": s["rate_flag"],
        "duds": kinds.count("dud"),
        "spikes": kinds.count("spike"),
        "svg": svg,
        "state": state(len(values), tr, cfg),
        "tips": tips,
    }


NO_VAL = "No Val in this run: no value chart."
NO_GAMES = "No games in the box scores: no value chart."


def attach(records, games, overrides, scale, replacement, cfg):
    """Add the "value" block to each record of data.player_records(). Return the meta of the quadrant, or None.

    games: read_games(). overrides: data/name_overrides.csv. scale, replacement: the category scale and the
    replacement value of the planning run. With replacement None, each block has only the text of the empty box.
    """
    if replacement is None or scale is None:
        for r in records:
            r["value"] = {"n": 0, "empty": NO_VAL}
        return None
    s = settings(cfg)
    to_yahoo = yahoo_keys(overrides)
    found = {}
    for r in records:
        key = name_key(r["name"])
        mine = games.get(to_yahoo.get(key, key)) or games.get(key)
        if mine:
            found[r["slug"]] = (mine, game_values(mine, scale, replacement, cfg))
    sd = role.league_spread([v for _, v in found.values()])
    spike = spike_level([r["val"] for r in records], s["spike_rank"])
    for r in records:
        if r["slug"] in found:
            r["value"] = value_block(*found[r["slug"]], sd, spike, cfg)
        else:
            r["value"] = {"n": 0, "empty": NO_GAMES}
    return {
        "spike": spike,
        "league_sd": None if sd is None else round(sd, 2),
        **s,
    }


def consistency_signal(record):
    """The Consistency signal of a record with a "value" block, or None.

    From the consistency_min games of the block: the duds (an alert) when they are rate_flag of the games or more,
    else the spikes.
    """
    from fantasyhoops.players.data import Signal

    block = record.get("value") or {}
    n = block.get("n", 0)
    if not n or n < block["consistency_min"]:
        return None
    if block["duds"] >= block["rate_flag"] * n:
        return Signal("Consistency", "value", False, f"Duds: {block['duds']} of {n} games")
    if block["spikes"] >= block["rate_flag"] * n:
        return Signal("Consistency", "value", True, f"Spikes: {block['spikes']} of {n} games")
    return None
