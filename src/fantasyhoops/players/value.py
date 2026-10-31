"""The Value quadrant of the player card (#189): the value of each ESPN game, the dud rate and the spike rate.

- The value of a game: the per-game value (core/valuation.py) of his box-score line, minus the replacement value of
  the planning run. So 0 is the replacement free agent, as for the Val of the header (players/data.py).
- A dud: a game with a value below 0 (below the replacement free agent).
- A spike: a game with a value at the top-30 level or more. The top-30 level is the Val of the player at rank
  SPIKE_RANK by Val on the page.
- The hero line is the window-game average. The normal-range band is the mean of his games plus or minus
  band_sd standard deviations of a window-game average. The standard deviation mixes his own spread with the league
  spread (league_sd()), which counts as prior_games games. A band needs band_min games. A range exit needs flag_min.
  The values are in [players.value] in config.toml (settings()).
- consistency_signal() gives the "Consistency" chip of the header when the duds or the spikes are RATE_FLAG of his
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

SPIKE_RANK = 30  # a spike: a game at the Val of the player at this rank, or more
RATE_FLAG = 0.4  # a dud rate or a spike rate of this share or more gives the Consistency signal
# The stat keys of core/valuation.py and their columns in data/box_scores.csv.
BOX_COLUMNS = {"pts": "pts", "reb": "reb", "ast": "ast", "threes": "fg3m", "stl": "stl", "blk": "blk"}

# The chart: a 580px viewBox, the plot from L to W - R and from T to H - B (the sample "After + tooltips").
W, H, L, R, T, B = 580, 268, 30, 104, 12, 22
DATE_W = 40  # a date under a game needs this many px. With less room, only every k-th game has a date.
MINUS = "−"


@dataclass(frozen=True)
class Settings:
    """[players.value] of config.toml: window, band_min, flag_min, prior_games, band_sd, consistency_min_games."""

    window: int = 3
    band_min: int = 3
    flag_min: int = 5
    prior_games: float = 4
    band_sd: float = 2
    consistency_min_games: int = 10


DEFAULT = Settings()  # the agent defaults of the first sample, the values of config.toml today


def settings(cfg):
    """The Settings of [players.value] in cfg."""
    return Settings(**cfg["players"]["value"])


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


def spike_level(vals, rank=SPIKE_RANK):
    """The top-30 level: the Val at rank (1 = best) of vals. With fewer Vals, the last one. None with no Val."""
    found = sorted((v for v in vals if v is not None), reverse=True)
    return found[min(rank, len(found)) - 1] if found else None


def kind(value, spike):
    """ "dud" below 0, "spike" at spike or more, else "normal"."""
    if value < 0:
        return "dud"
    return "spike" if spike is not None and value >= spike else "normal"


def rolling(values, window=DEFAULT.window):
    """The window-game average at each game. None until the game that completes the first window."""
    return [None if i < window - 1 else sum(values[i - window + 1 : i + 1]) / window for i in range(len(values))]


def league_sd(series):
    """The pooled spread of the games around the mean of each player. series: the game values of each player.

    Only players with 2 or more games count. None if no player has 2 games.
    """
    ss, df = 0.0, 0
    for values in series:
        if len(values) >= 2:
            mean = sum(values) / len(values)
            ss += sum((v - mean) ** 2 for v in values)
            df += len(values) - 1
    return math.sqrt(ss / df) if df else None


@dataclass(frozen=True)
class Trend:
    """The hero line (roll), the mean, the band (lo, hi; None with no band) and the games of a range exit."""

    roll: list
    mean: float
    lo: float | None
    hi: float | None
    exits: list


def trend(values, sd_league, s=DEFAULT):
    """The Trend of the game values of one player. s: the Settings.

    The band: mean +- band_sd x sd / sqrt(window). sd^2 = (his squared deviations + prior_games x sd_league^2) /
    (games - 1 + prior_games). With no sd_league, his own spread only. No band under band_min games.
    A range exit: a point of the hero line outside the band, from flag_min games.
    """
    window, band_min, flag_min = s.window, s.band_min, s.flag_min
    n = len(values)
    roll = rolling(values, window)
    mean = sum(values) / n if n else 0.0
    lo = hi = None
    if n >= band_min:
        ss = sum((v - mean) ** 2 for v in values)
        if sd_league is None:
            var = ss / (n - 1)
        else:
            var = (ss + s.prior_games * sd_league**2) / (n - 1 + s.prior_games)
        half = s.band_sd * math.sqrt(var) / math.sqrt(window)
        lo, hi = mean - half, mean + half
    exits = []
    if lo is not None and n >= flag_min:
        exits = [i for i, r in enumerate(roll) if r is not None and not lo <= r <= hi]
    return Trend(roll, mean, lo, hi, exits)


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


def value_chart(games, values, tr, spike, window=DEFAULT.window):
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


def state(n, tr, s=DEFAULT):
    """The state line under the chart (DESIGN.md "Thin data"), as HTML. s: the Settings."""
    band_min, flag_min = s.band_min, s.flag_min
    if n < band_min:
        text = f"<b>Too few games for a range:</b> {n} of {band_min}."
    else:
        width = f"Range = mean ± {f1((tr.hi - tr.lo) / 2)}"
        prior = ", mostly the league prior" if n - 1 <= s.prior_games else ""
        if n < flag_min:
            text = f"<b>Too few games for a flag:</b> {n} of {flag_min}. {width}{prior}."
        else:
            text = f"{width}{prior} at {n} games."
    if n < flag_min:
        text += f" One game moves a rate {round(100 / n)} points."
    return text


def value_block(games, values, sd_league, spike, s=DEFAULT):
    """The "value" block of a player in the player file: n, consistency_min, duds, spikes, svg, state and tips."""
    tr = trend(values, sd_league, s)
    svg, tips = value_chart(games, values, tr, spike, s.window)
    kinds = [kind(v, spike) for v in values]
    return {
        "n": len(values),
        "consistency_min": s.consistency_min_games,
        "duds": kinds.count("dud"),
        "spikes": kinds.count("spike"),
        "svg": svg,
        "state": state(len(values), tr, s),
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
    sd = league_sd([v for _, v in found.values()])
    spike = spike_level([r["val"] for r in records])
    for r in records:
        if r["slug"] in found:
            r["value"] = value_block(*found[r["slug"]], sd, spike, s)
        else:
            r["value"] = {"n": 0, "empty": NO_GAMES}
    return {
        "spike": spike,
        "spike_rank": SPIKE_RANK,
        "league_sd": None if sd is None else round(sd, 2),
        "window": s.window,
        "band_min": s.band_min,
        "flag_min": s.flag_min,
        "prior_games": s.prior_games,
        "band_sd": s.band_sd,
        "consistency_min_games": s.consistency_min_games,
        "rate_flag": RATE_FLAG,
    }


def consistency_signal(record):
    """The Consistency signal of a record with a "value" block, or None.

    From consistency_min games (of the block): the duds (an alert) when they are RATE_FLAG of the games or more, else the spikes.
    """
    from fantasyhoops.players.data import Signal

    block = record.get("value") or {}
    n = block.get("n", 0)
    if n < block.get("consistency_min", DEFAULT.consistency_min_games):
        return None
    if block["duds"] >= RATE_FLAG * n:
        return Signal("Consistency", "value", False, f"Duds: {block['duds']} of {n} games")
    if block["spikes"] >= RATE_FLAG * n:
        return Signal("Consistency", "value", True, f"Spikes: {block['spikes']} of {n} games")
    return None
