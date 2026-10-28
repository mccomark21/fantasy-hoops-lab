"""The home page of the site (#120): your roster with the season stats and the fit of each player in the playoff lineup.

The page shows the players in custom-rank order. Each row has the season stats per game, the starts and games of each
playoff week, and a grid of the playoff days. Two rows below the team starts give the Used and vs ideal percents.

The lineup fit uses the rule of scoreCore in draft/team_builder.js: each playoff day, the best lineup of the position
slots and one Util slot, higher rank first (core/lineup.py). The IL players are in the lineup pool, because they will
likely be back by the playoffs. A player with rests_b2b gets no game on the second night of a back-to-back.
The Used and vs ideal rows use the math of renderFooter in draft/board.py, and the percent bands use pctClass.

The module takes its data from the caller and opens no file and no web page. write() writes output/home/index.html.
"""

import html
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from fantasyhoops.core import publish as site
from fantasyhoops.core import tokens
from fantasyhoops.core import common
from fantasyhoops.core.lineup import best_lineup
from fantasyhoops.core.schedule import playoff_schedule

STATS = ["gp", "min", "pts", "reb", "ast", "threes", "stl", "blk"]  # the keys of RosterPlayer.stats, in page order
STAT_LABELS = ["GP", "MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK"]
UTIL = 1  # the Util slots of a lineup (core/lineup.py)
FEW_GAMES = 2  # [flags] avoid_week_games if config.toml has none: a week with this number of games or fewer
S1, NONE = ' class="s1"', ' class="none"'
IL_TITLE = "On IL now. Counts in the playoff starts."
START, SITS, REST, NO_GAME = "s", "b", "r", "n"  # the marks of the day grid
MARK_TEXT = {START: "starts", SITS: "game, sits", REST: "rests on back-to-back", NO_GAME: "no game"}
# The percent bands of pctClass in draft/board.py: (lowest ratio, class, text for a screen reader).
BANDS = [(0.9, "p3", "90% or more"), (0.7, "p2", "70% to 89%"), (0.0, "p1", "less than 70%")]


@dataclass(frozen=True)
class RosterPlayer:
    """One player of your roster.

    team: the ESPN code of his NBA team. positions: his Yahoo positions, for example ("PG", "SG").
    slot: his roster slot today ("PG", ..., "Util", "BN" or "IL"). status: the Yahoo status, for example "Q".
    rank: his custom draft rank (draft/rankings.py), or None if he is not in the rankings.
    rests_b2b: True if he rests on the second night of a back-to-back.
    stats: his season stats to date (STATS keys), or None if ESPN has no stats for him.
    """

    name: str
    team: str
    positions: tuple
    slot: str = ""
    status: str = ""
    status_name: str = ""
    rank: int | None = None
    rests_b2b: bool = False
    stats: dict | None = None

    @property
    def on_il(self):
        return self.slot.startswith("IL")


@dataclass(frozen=True)
class Day:
    """One day of the playoff weeks. teams: the NBA teams that play. b2b: the teams on the second night of a back-to-back."""

    date: date
    week: str
    quality: bool = False
    teams: frozenset = frozenset()
    b2b: frozenset = frozenset()


@dataclass
class Fit:
    """The lineup fit of a roster in the playoff days.

    players: the roster in rank order (the lineup order). marks: one list of day marks for each player.
    started: the starters of each day. holes: the empty slots of each quality day (0 on other days).
    """

    players: list
    days: list
    slots: list
    marks: list = field(default_factory=list)
    started: list = field(default_factory=list)
    holes: list = field(default_factory=list)

    @property
    def weeks(self):
        return list(dict.fromkeys(d.week for d in self.days))

    def _days(self, week):
        return [i for i, d in enumerate(self.days) if week is None or d.week == week]

    def player_week(self, p, week=None):
        """(starts, games, games on quality days) of the player at index p in a week. week None: all weeks.

        A rest night is not a game.
        """
        idx = self._days(week)
        starts = sum(self.marks[p][i] == START for i in idx)
        games = sum(self.marks[p][i] in (START, SITS) for i in idx)
        quality = sum(self.marks[p][i] in (START, SITS) and self.days[i].quality for i in idx)
        return starts, games, quality

    def team_week(self, week=None):
        """(started, games, ideal) of the team in a week (renderFooter in draft/board.py). week None: all weeks.

        games: the games of the players, with no rest nights. ideal: each player with the most games of any NBA team
        that week, at most the starting slots on each game day of the week.
        """
        if week is None:
            parts = [self.team_week(w) for w in self.weeks]
            return tuple(sum(x[i] for x in parts) for i in range(3))
        idx = self._days(week)
        started = sum(self.started[i] for i in idx)
        games = sum(self.player_week(p, week)[1] for p in range(len(self.players)))
        counts = {}
        for i in idx:
            for team in self.days[i].teams:
                counts[team] = counts.get(team, 0) + 1
        game_days = sum(1 for i in idx if self.days[i].teams)
        ideal = min(len(self.players) * max(counts.values(), default=0), (len(self.slots) + UTIL) * game_days)
        return started, games, ideal

    def lost(self):
        """{name: games} of the players who play but get no slot, most first."""
        out = {p.name: sum(m == SITS for m in marks) for p, marks in zip(self.players, self.marks)}
        return dict(sorted(((n, k) for n, k in out.items() if k), key=lambda x: -x[1]))


def rank_order(players):
    """The players by rank, highest first. A player with no rank goes last. Equal ranks keep their order."""
    return sorted(players, key=lambda p: (p.rank is None, p.rank or 0))


def lineup_fit(players, days, slots):
    """The Fit of the players in the days: each day, the best lineup, higher rank first. The IL players count."""
    ordered = rank_order(players)
    fit = Fit(ordered, list(days), list(slots), marks=[[] for _ in ordered])
    for day in fit.days:
        playing = []
        for i, p in enumerate(ordered):
            if p.team not in day.teams:
                fit.marks[i].append(NO_GAME)
            elif p.rests_b2b and p.team in day.b2b:
                fit.marks[i].append(REST)
            else:
                fit.marks[i].append(SITS)
                playing.append(i)
        lineup = best_lineup([[s for s in ordered[i].positions if s in slots] for i in playing], slots)
        for j in lineup:
            fit.marks[playing[j]][-1] = START
        fit.started.append(len(lineup))
        fit.holes.append(len(slots) + UTIL - len(lineup) if day.quality else 0)
    return fit


def playoff_days(sched, cfg):
    """A Day for each date of the playoff weeks of config.toml, from data/schedule.csv (core/schedule.py)."""
    _, games = playoff_schedule(sched, cfg)
    by_date = {pd.Timestamp(d.date).date(): d for d in games.itertuples()}
    out = []
    for week in cfg["playoffs"]["weeks"]:
        day, end = pd.Timestamp(week["start"]).date(), pd.Timestamp(week["end"]).date()
        while day <= end:
            g = by_date.get(day)
            out.append(
                Day(day, week["name"], bool(g.quality), frozenset(g.teams), frozenset(g.b2b))
                if g is not None
                else Day(day, week["name"])
            )
            day += timedelta(days=1)
    return out


# The page --------------------------------------------------------------------------------------------------------


def _e(text):
    return html.escape(str(text))


def _plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _week_label(week):
    return week[:1].upper() + week[1:]


def _short_name(name):
    """The name without the first name, for example "Black" for "Anthony Black"."""
    parts = name.split(" ", 1)
    return parts[1] if len(parts) > 1 else name


def _band_style(team):
    color = tokens.TEAM_COLORS.get(team)
    if color is None:
        return "--team:var(--lab-blue);--team-ink:var(--lab-on-blue)"
    return f"--team:{color};--team-ink:{tokens.team_ink(color)}"


def _flag(p):
    if p.on_il:
        return f' <em class="flag" title="{_e(IL_TITLE)}">IL</em>'
    if p.status:
        return f' <em class="flag" title="{_e(p.status_name or p.status)}">{_e(p.status)}</em>'
    return ""


def _letter(d):
    """The first letter of the weekday, for example "M"."""
    return f"{d:%a}"[0]


def _day_text(d):
    return f"{d:%a} {d:%b} {d.day}"


def _mark(day, mark, title=True):
    label = f"{_day_text(day.date)}{', quality day' if day.quality else ''}: {MARK_TEXT[mark]}"
    extra = f' title="{label}"' if title else ""
    return f'<i class="{mark}" role="img" aria-label="{label}"{extra}></i>'


def _day_class(fit, i, base):
    day = fit.days[i]
    first = i == 0 or fit.days[i - 1].week != day.week
    return " ".join(c for c in (base, "q" if day.quality else "", "wk1" if first else "") if c)


def _pct(got, all_):
    """The percent cell: the band class, the meter, the percent and the band text for a screen reader."""
    if not all_:
        return '<span class="pc"><b>–</b></span>'
    ratio = got / all_
    cls, text = next((c, t) for low, c, t in BANDS if ratio >= low)
    meter = '<i class="mtr" aria-hidden="true"><i></i><i></i><i></i></i>'
    return f'<span class="pc {cls}">{meter}<b>{int(100 * ratio + 0.5)}%</b><span class="vh"> ({text})</span></span>'


def _pct_text(got, all_):
    return f"{got}/{all_} · {int(100 * got / all_ + 0.5)}%" if all_ else "–"


def _week_cell(starts, games, quality, classes, few):
    """A week cell of a player: starts/games and the games on quality days."""
    lo = " lo" if starts < games else ""
    shown = f'<span class="few">{games}</span>' if few else str(games)
    few_text = ", 2 or fewer games" if few else ""
    return (
        f'<td class="{classes}{lo}">{starts}<s aria-hidden="true">/{shown}</s>'
        f'<span class="vh"> starts of {_plural(games, "game")}{few_text}</span>'
        f'<small class="qg">{quality} q</small><span class="vh">, {quality} on quality days</span></td>'
    )


def _stat(p, key):
    if not p.stats or p.stats.get(key) is None:
        return None
    v = p.stats[key]
    return str(int(v)) if key == "gp" else f"{v:.1f}"


def _desk_head(fit, week_names):
    n = len(fit.days)
    first, last = fit.days[0].date, fit.days[-1].date
    span = (
        f"{first:%b} {first.day}–{last.day}"
        if first.month == last.month
        else f"{first:%b} {first.day}–{last:%b} {last.day}"
    )
    top = (
        '<tr class="top"><td colspan="3"></td>'
        f'<th colspan="{len(STATS)}" scope="colgroup" class="l sec">__SEASON__ season · per game</th>'
        f'<th colspan="{len(week_names) + 1}" scope="colgroup" class="fine sec">Playoff starts / games</th>'
        f'<th colspan="{n}" scope="colgroup" class="l sec gdh">Playoff days · {span} · '
        '<i class="qk" aria-hidden="true"></i>quality day</th></tr>'
    )
    cells = ['<th scope="col" class="l">Team</th>', '<th scope="col">Rk</th>', '<th scope="col" class="l">Player</th>']
    cells += [f'<th scope="col"{S1 if i == 0 else ""}>{label}</th>' for i, label in enumerate(STAT_LABELS)]
    cells += [
        f'<th scope="col" class="w{" w1" if i == 0 else ""}">{_week_label(w)}</th>' for i, w in enumerate(week_names)
    ]
    cells.append('<th scope="col" class="w t">T</th>')
    for i, day in enumerate(fit.days):
        d = day.date
        title = f"{d:%A} {d:%B} {d.day}{', quality day' if day.quality else ''}"
        cells.append(
            f'<th scope="col" class="{_day_class(fit, i, "d")}"><abbr title="{title}">{_letter(d)}</abbr>'
            f"<u>{d.day}</u></th>"
        )
    return top, f'<tr class="sub">{"".join(cells)}</tr>', span


def _desk_row(fit, p_idx, few_limit):
    p = fit.players[p_idx]
    cls = ' class="il"' if p.on_il else ""
    rank = p.rank if p.rank is not None else "–"
    pos = "/".join(p.positions)
    cells = [
        f'<td class="band" style="{_band_style(p.team)}">{_e(p.team)}</td>',
        f'<td class="rk">{rank}</td>',
        f'<th class="pl" scope="row"><b>{_e(p.name)}</b>{_flag(p)}<small>{_e(p.team)} · {_e(pos)} · {_e(p.slot)}</small></th>',
    ]
    for i, key in enumerate(STATS):
        v = _stat(p, key)
        cls_n = " ".join(c for c in ("n", "none" if v is None else "", "s1" if i == 0 else "") if c)
        cells.append(f'<td class="{cls_n}">{v if v is not None else "–"}</td>')
    for i, w in enumerate(fit.weeks):
        s, g, q = fit.player_week(p_idx, w)
        cells.append(_week_cell(s, g, q, "w w1" if i == 0 else "w", g <= few_limit))
    s, g, q = fit.player_week(p_idx)
    cells.append(_week_cell(s, g, q, "w t", False))
    for i, day in enumerate(fit.days):
        cells.append(f'<td class="{_day_class(fit, i, "d")}">{_mark(day, fit.marks[p_idx][i])}</td>')
    return f"<tr{cls}>{''.join(cells)}</tr>"


def _lost_text(fit):
    lost = fit.lost()
    total, holes = sum(lost.values()), sum(fit.holes)
    names = ", ".join(f"{_short_name(n)} {k}" for n, k in lost.items())
    first = f"{_plural(total, 'start')} lost to a full lineup ({names})" if total else "No starts lost to a full lineup"
    return f"{first} · {_plural(holes, 'open slot')} on quality days"


def _empty_days(fit):
    return "".join(f'<td class="{_day_class(fit, i, "d")}"></td>' for i in range(len(fit.days)))


def _desk_foot(fit):
    weeks = fit.weeks
    rows = []
    cells = [f'<td class="w{" w1" if i == 0 else ""}">{fit.team_week(w)[0]}</td>' for i, w in enumerate(weeks)]
    cells.append(f'<td class="w t">{fit.team_week()[0]}</td>')
    rows.append(
        '<tr class="tot"><th colspan="3" scope="row" class="lab">Team starts</th>'
        f'<td colspan="{len(STATS)}" class="note s1">{_e(_lost_text(fit))}</td>{"".join(cells)}{_empty_days(fit)}</tr>'
    )
    for label, k, sr in (("Used (started / games)", 1, "games start"), ("vs ideal", 2, "ideal games")):
        parts = [(w, fit.team_week(w)) for w in weeks] + [(None, fit.team_week())]
        cells = []
        for i, (w, t) in enumerate(parts):
            c = "w t" if w is None else ("w w1" if i == 0 else "w")
            cells.append(
                f'<td class="{c}">{_pct(t[0], t[k])}<small class="qg">{t[0]}/{t[k]}</small>'
                f'<span class="vh"> ({t[0]} of {t[k]} {sr})</span></td>'
            )
        total = fit.team_week()
        rows.append(
            f'<tr class="use"><th colspan="{3 + len(STATS)}" scope="row" class="lab2">{label} · '
            f"{_pct_text(total[0], total[k])}</th>{''.join(cells)}{_empty_days(fit)}</tr>"
        )
    return "\n".join(rows)


def _mob_row(fit, p_idx, few_limit):
    p = fit.players[p_idx]
    rank = p.rank if p.rank is not None else "–"
    gp = _stat(p, "gp")
    total = fit.player_week(p_idx)
    stats = []
    for key, label in zip(STATS[1:], STAT_LABELS[1:]):
        v = _stat(p, key)
        stats.append(f"<div><dt>{label}</dt><dd{NONE if v is None else ''}>{v or '–'}</dd></div>")
    weeks = []
    for w in fit.weeks + [None]:
        s, g, q = fit.player_week(p_idx, w)
        few = w is not None and g <= few_limit
        shown = f'<span class="few">{g}</span><span class="vh"> games, 2 or fewer</span>' if few else str(g)
        lo = ' class="lo"' if s < g else ""
        label = _week_label(w) if w else "Total"
        weeks.append(f"<div{lo}><dt>{label}</dt><dd><b>{s}</b><s>/{shown}</s><small>{q} q</small></dd></div>")
    head = "".join(
        f'<span class="{_day_class(fit, i, "")}" aria-hidden="true">{_letter(day.date)}<u>{day.date.day}</u></span>'
        for i, day in enumerate(fit.days)
    )
    marks = "".join(
        f'<span class="{_day_class(fit, i, "")}">{_mark(day, fit.marks[p_idx][i], title=False)}</span>'
        for i, day in enumerate(fit.days)
    )
    head = head.replace(' class=""', "")
    marks = marks.replace(' class=""', "")
    return (
        f'<details class="m-p{" il" if p.on_il else ""}">\n'
        f'<summary><span class="band" style="{_band_style(p.team)}">{_e(p.team)}</span>'
        f'<span class="rk"><span class="vh">Rank </span>{rank}</span>'
        f'<span class="nm"><b>{_e(p.name)}</b>{_flag(p)}<small>{_e("/".join(p.positions))} · {_e(p.slot)}</small></span>'
        f'<span class="gp"><span class="vh">, games played </span>{gp or "–"}</span>'
        f'<span class="tg"><span class="vh">, playoff games </span>{total[1]}</span>'
        '<span class="chev" aria-hidden="true"></span></summary>\n'
        '<div class="m-body">\n'
        f'<dl class="m-stats" aria-label="Season per game">{"".join(stats)}</dl>\n'
        f'<dl class="m-weeks" aria-label="Playoff starts / games">{"".join(weeks)}</dl>\n'
        f'<div class="m-grid">{head}{marks}</div>\n'
        "</div>\n</details>"
    )


def _mob_foot(fit):
    weeks = fit.weeks
    starts = "".join(f"<div><dt>{_week_label(w)}</dt><dd>{fit.team_week(w)[0]}</dd></div>" for w in weeks)
    starts += f'<div class="t"><dt>Total</dt><dd>{fit.team_week()[0]}</dd></div>'
    parts = []
    for label, k in (("Used (started / games)", 1), ("vs ideal", 2)):
        cells = "".join(
            f'<div><dt class="vh">{_week_label(w) if w else "Total"}</dt><dd>{_pct(t[0], t[k])}<small>{t[0]}/{t[k]}</small></dd></div>'
            for w, t in [(w, fit.team_week(w)) for w in weeks] + [(None, fit.team_week())]
        )
        parts.append(f'<p class="ul">{label}</p><dl class="u">{cells}</dl>')
    return f'<div class="m-tot"><b>Team starts</b><dl>{starts}</dl>{"".join(parts)}<p>{_e(_lost_text(fit))}</p></div>'


def _title(name):
    """The team name for the page header. A trademark sign goes up as in the sample."""
    return _e(name).replace("™", "<sup>™</sup>")


def render(players, days, cfg, week=None, adds=None, today=None, team_name=None):
    """The HTML of the home page.

    players: RosterPlayer list in any order. days: Day list (playoff_days()). cfg: config.toml.
    week: the number of the current fantasy week, or None. adds: (used, limit) of this week, or None.
    today: the date of the run. team_name: the name in the page header (default "Roster").
    """
    slots = cfg["league"]["slots"]
    few_limit = cfg.get("flags", {}).get("avoid_week_games", FEW_GAMES)
    fit = lineup_fit(players, days, slots)
    week_names = fit.weeks
    top, sub, span = _desk_head(fit, week_names)
    season = cfg["league"].get("espn_season")
    season_text = f"{season - 1}–{str(season)[2:]}" if season else ""
    top = top.replace("__SEASON__", season_text)
    rows = "\n".join(_desk_row(fit, i, few_limit) for i in range(len(fit.players)))
    mob = "\n".join(_mob_row(fit, i, few_limit) for i in range(len(fit.players)))
    first, last = _week_label(week_names[0]), week_names[-1]
    digits = "".join(c for c in last if c.isdigit())
    meta = []
    if week is not None:
        used = f' · <strong class="red">{adds[0]}</strong> of {adds[1]} adds used' if adds else ""
        meta.append(f"<div><dt>This week</dt><dd><strong>Week {week}</strong>{used}</dd></div>")
    meta.append(f"<div><dt>Playoffs</dt><dd><strong>{first}–{digits}</strong> · {span}</dd></div>")
    made = f" Made {today:%a} {today.month}/{today.day}." if today else ""
    caption = (
        "Roster in custom-rank order: season stats per game, playoff starts and games, and the playoff day grid. "
        "IL players count in the starts."
    )
    n_days = len(fit.days)
    desk = (
        '<div class="scroll" tabindex="0" role="region" aria-label="Roster table">\n<table class="desk">\n'
        f'<caption class="vh">{caption}</caption>\n'
        f'<colgroup><col class="c-band"><col class="c-rk"><col class="c-pl"><col class="c-n" span="{len(STATS)}">'
        f'<col class="c-w" span="{len(week_names) + 1}"><col class="c-d" span="{n_days}"></colgroup>\n'
        f"<thead>\n{top}\n{sub}\n</thead>\n<tbody>\n{rows}\n</tbody>\n<tfoot>\n{_desk_foot(fit)}\n</tfoot>\n"
        "</table>\n</div>"
    )
    mobile = (
        f'<section class="mob" aria-label="Roster" style="--days:{n_days}">\n'
        '<div class="m-head" aria-hidden="true"><span>Team</span><span>Rk</span><span>Player · Pos</span>'
        "<span>GP</span><span>Games</span><span></span></div>\n"
        f"{mob}\n{_mob_foot(fit)}\n</section>"
    )
    foot = (
        f"Stats: ESPN, {season_text} regular season to date. Rank: your custom draft rank. "
        "Starts: the best lineup each day, higher rank first. IL players are in the lineup pool, because they will "
        "likely be back by the playoffs. Used: started / the games of your players, with no rest nights. "
        "vs ideal: started / the games of the same number of players with the most games of the week, at most "
        f"{len(slots) + UTIL} starters a day. Both rows use the math of the draft board.{made}"
    )
    return (
        PAGE_HTML.replace("__DAYS1__", str(n_days + 1))
        .replace("__DAYS__", str(n_days))
        .replace("__HEAD__", site.site_head())
        .replace("__MENU__", site.site_menu("home"))
        .replace("__SCRIPT__", site.MENU_SCRIPT)
        .replace("__TITLE__", _title(team_name or "Roster"))
        .replace("__META__", "\n".join(meta))
        .replace("__DESK__", desk)
        .replace("__MOB__", mobile)
        .replace("__FOOT__", foot)
    )


def page_path():
    """The page file: output/home/index.html, from common.OUT at the time of the call."""
    return common.OUT / "home" / "index.html"


def write(text, path=None):
    """Write the page to path (default page_path()) with the font next to it. Return the path."""
    path = path or page_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    tokens.copy_font(path.parent)
    return path


PAGE_STYLE = """/* Card Back roster page (#120): zebra rows, full-height quality-day columns, section rules, IL in the starts. */
.roster {
  color: var(--lab-ink); font: 400 13px/1.25 var(--lab-face); font-variant-numeric: tabular-nums;
  padding-block: 16px 32px; padding-left: max(28px, env(safe-area-inset-left));
  padding-right: max(28px, env(safe-area-inset-right));
}
.vh { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 28px; padding-bottom: 12px;
  border-bottom: 3px solid var(--mark); }
.head h1 { margin: 0; color: var(--mark); font-weight: 900; font-stretch: 66%; font-size: clamp(32px, 4vw, 44px);
  line-height: .9; text-transform: uppercase; text-wrap: balance; }
.head h1 sup { font-size: .35em; font-stretch: 100%; vertical-align: top; }
.meta { display: flex; flex-wrap: wrap; gap: 8px 0; margin: 0 0 0 auto; font-size: 13px; }
.meta div { padding: 0 16px; border-left: 1px solid var(--lab-rule); }
.meta dt { color: var(--lab-mute); font-size: 12px; margin-bottom: 3px; }
.meta dd { margin: 0; }
.meta strong { font-weight: 800; font-size: 15px; }
.red { color: var(--lab-red); }
.flag { font-style: normal; font-size: 11px; font-weight: 800; color: var(--lab-on-red); background: var(--lab-red);
  padding: 1px 4px; vertical-align: 3px; margin-left: 4px; }

/* Desktop table */
.scroll { position: relative; overflow-x: auto; margin-top: 10px; scrollbar-color: var(--mark) var(--zebra); }
.scroll:focus-visible { outline: 2px solid var(--mark); outline-offset: 2px; }
table { border-collapse: collapse; table-layout: fixed; width: 100%; min-width: 1130px; }
col.c-band { width: 44px; } col.c-rk { width: 38px; } col.c-pl { width: 196px; } col.c-n { width: 34px; }
col.c-w { width: 46px; } col.c-d { width: 18px; }
thead th, thead td { font-size: 11px; font-weight: 800; color: var(--mark); text-align: right; padding: 0 6px 6px;
  vertical-align: bottom; border-bottom: 2px solid var(--mark); }
thead .l { text-align: left; }
tr.top th, tr.top td { border-bottom: 0; padding-bottom: 4px; font-size: 12px; }
tr.top th.fine { background: var(--lab-blue); color: var(--lab-on-blue); text-align: center; padding: 5px 0; }
tr.top th.gdh { padding-left: 8px; white-space: nowrap; }
tbody td, tbody th { height: 46px; border-bottom: 1px solid var(--lab-rule); padding: 0 6px; text-align: right;
  vertical-align: middle; font-weight: 400; }
tbody tr:nth-child(even) > * { background: var(--zebra); }
td.band { padding: 0; text-align: center; background: var(--team) !important; color: var(--team-ink); font-weight: 900;
  font-stretch: 70%; font-size: 19px; border-bottom: 1px solid var(--lab-stock); }
td.rk { color: var(--lab-red); font-weight: 900; font-stretch: 75%; font-size: 21px; padding-right: 8px; }
th.pl { text-align: left; padding: 3px 6px 3px 10px; line-height: 1; }
th.pl b { font-weight: 900; font-stretch: 66%; font-size: 20px; text-transform: uppercase; line-height: 1; }
th.pl small { display: block; font-size: 12px; line-height: 1.2; color: var(--lab-mute); margin-top: 2px; }
td.n { font-size: 14px; }
td.n:nth-child(6) { font-weight: 800; }
td.n.none { color: var(--lab-mute); }
td.w { font-size: 14px; font-weight: 700; line-height: 1.1; }
td.w s { text-decoration: none; color: var(--lab-mute); font-weight: 400; }
td.w .qg { display: block; margin-top: 1px; font-size: 11px; font-weight: 600; color: var(--lab-mute); }
td.w.lo { color: var(--lab-red); }
td.w.t { color: var(--mark); font-weight: 900; }
td.w.t.lo { color: var(--lab-red); }

/* Section rules: player | season | playoff weeks | day grid, and between the weeks */
.s1, .w1, .w, .wk1 { border-left: 1px solid var(--vrule); }
tr.top .sec { border-left: 1px solid var(--vrule); }
tr.top th.fine { border-left-color: var(--lab-blue); }

/* Day grid: one column for each day. A quality day is a shaded column, full height, with a solid header block. */
th.d, td.d { padding: 0 !important; text-align: center !important; }
.d.q { background: var(--qcol) !important; }
tbody tr:nth-child(even) > .d.q { background: var(--qcol-z) !important; }
th.d { font-size: 11px; font-weight: 700; color: var(--lab-mute); line-height: 1.15; padding: 2px 0 5px !important; }
th.d abbr { text-decoration: none; display: block; }
th.d u { display: block; text-decoration: none; color: var(--lab-ink); }
thead th.d.q { background: var(--mark) !important; color: var(--lab-stock); }
thead th.d.q u { color: var(--lab-stock); }
.qk { display: inline-block; width: 10px; height: 10px; background: var(--mark); vertical-align: -1px; margin: 0 4px 0 2px; }

.d i, .m-grid i, .legend i.k { display: inline-block; box-sizing: border-box; width: 13px; height: 13px;
  position: relative; vertical-align: middle; }
i.s { background: var(--mark); }
i.b, i.r { border: 1.5px solid var(--mark); }
i.r::after { content: ""; position: absolute; left: -2px; top: 5px; width: 14px; height: 1.5px; background: var(--mark);
  transform: rotate(-45deg); }
i.n::after { content: ""; position: absolute; left: 3px; top: 5.5px; width: 6px; height: 1.5px;
  background: var(--lamp-off); }

tfoot tr.tot th, tfoot tr.tot td { height: 34px; border-bottom: 2px solid var(--mark); border-top: 2px solid var(--mark);
  font-size: 12px; font-weight: 800; color: var(--mark); padding: 0 6px; text-align: right; }
tfoot tr.use th, tfoot tr.use td { height: 34px; padding: 0 6px; text-align: right; font-size: 12px; color: var(--mark);
  border-bottom: 1px solid var(--lab-rule); }
tfoot tr.use:last-child > * { border-bottom: 2px solid var(--mark); }
tfoot tr.use th.lab2 { text-align: left; padding-left: 10px; font-weight: 800; }
tfoot tr.use td.w b { font-weight: 900; font-size: 13px; } tfoot tr.use td.w .qg { font-weight: 600; }
tr.tot .lab { text-align: left; padding-left: 10px; text-transform: uppercase; font-size: 13px; }
tr.tot td.w { background: var(--lab-blue); color: var(--lab-on-blue); font-size: 15px;
  border-left-color: color-mix(in srgb, var(--lab-on-blue) 35%, transparent); }
tr.tot td.note { color: var(--lab-mute); font-weight: 600; text-align: left; padding: 5px 6px 5px 12px; line-height: 1.3;
  font-size: 11px; }

.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; font-size: 12px; color: var(--lab-mute);
  padding-top: 12px; }
.legend > b { color: var(--mark); font-weight: 800; }
.legend i.k { margin-right: 5px; }
.legend .qsw { display: inline-block; width: 13px; height: 20px; background: var(--qcol); border-top: 5px solid var(--mark);
  box-sizing: border-box; vertical-align: middle; margin-right: 5px; }
.legend .flag { margin: 0 5px 0 0; vertical-align: 0; }
.lo-key { color: var(--lab-red); font-weight: 800; margin-right: 5px; }
/* A week with 2 or fewer games: a red box on the games numeral, so the sign is a shape and not only a color. */
.few { display: inline-block; min-width: 1.1em; padding: 0 2px; margin-left: 1px; border: 1.5px solid var(--lab-red);
  color: var(--lab-red); font-weight: 800; text-align: center; line-height: 1.15; }
.few-key { color: var(--lab-mute); margin-right: 5px; }
/* The footer percents: the bands of pctClass in draft/board.py, with a bar meter (3 bars = 90%+, 2 = 70-89%, 1 = less) */
.pc { display: inline-flex; align-items: center; gap: 3px; white-space: nowrap; }
.pc b { font-weight: 900; }
.mtr { display: inline-flex; align-items: flex-end; gap: 1px; height: 10px; }
.mtr i { display: block; width: 3px; background: var(--vrule); }
.mtr i:nth-child(1) { height: 4px; } .mtr i:nth-child(2) { height: 7px; } .mtr i:nth-child(3) { height: 10px; }
.p3 { color: var(--mark); } .p2 { color: var(--lab-ink); }
.p3 .mtr i, .p2 .mtr i:nth-child(-n+2) { background: currentColor; }
.p1 { background: var(--lab-red); color: var(--lab-on-red); padding: 1px 3px; }
.p1 .mtr i:nth-child(1) { background: var(--lab-on-red); }
.p1 .mtr i:nth-child(n+2) { background: color-mix(in srgb, var(--lab-on-red) 35%, transparent); }
.pc-key { display: inline-flex; gap: 8px; margin-right: 5px; }
.q-key { color: var(--lab-mute); font-weight: 600; margin-right: 5px; }
.foot { max-width: 72ch; margin: 10px 0 0; font-size: 12px; line-height: 1.45; color: var(--lab-mute); text-wrap: pretty; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) td.band, :root:not([data-theme="light"]) .m-p .band {
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lab-ink) 22%, transparent); }
}
:root[data-theme="dark"] td.band, :root[data-theme="dark"] .m-p .band {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lab-ink) 22%, transparent); }

/* Phone: one row for each player that opens and closes */
.mob { display: none; }
@media (max-width: 899px) {
  .roster { padding-block: 16px 24px; padding-left: max(16px, env(safe-area-inset-left));
    padding-right: max(16px, env(safe-area-inset-right)); }
  .meta { margin-left: 0; }
  .meta div:first-child { padding-left: 0; border-left: 0; }
  .scroll { display: none; }
  .mob { display: block; margin: 10px -16px 0; }
  .m-head, .m-p summary { display: grid; grid-template-columns: 44px 34px 1fr 30px 46px 26px; align-items: center;
    column-gap: 0; }
  .m-head { font-size: 11px; font-weight: 800; color: var(--mark); padding: 0 0 5px; border-bottom: 2px solid var(--mark); }
  .m-head span { padding: 0 4px; } .m-head span:nth-child(1) { padding-left: 16px; text-align: left; }
  .m-head span:nth-child(2), .m-head span:nth-child(4), .m-head span:nth-child(5) { text-align: right; }
  .m-head span:nth-child(3) { padding-left: 10px; }
  .m-p { border-bottom: 1px solid var(--lab-rule); }
  .m-p:nth-of-type(even) { background: var(--zebra); }
  .m-p summary { list-style: none; cursor: pointer; min-height: 52px; }
  .m-p summary::-webkit-details-marker { display: none; }
  .m-p summary:focus-visible { outline: 2px solid var(--mark); outline-offset: -2px; }
  .m-p .band { align-self: stretch; display: flex; align-items: center; justify-content: center; background: var(--team);
    color: var(--team-ink); font-weight: 900; font-stretch: 70%; font-size: 17px; }
  .m-p .rk { color: var(--lab-red); font-weight: 900; font-stretch: 75%; font-size: 19px; text-align: right;
    padding-right: 4px; }
  .m-p .nm { padding: 6px 4px 6px 10px; line-height: 1; min-width: 0; }
  .m-p .nm b { font-weight: 900; font-stretch: 66%; font-size: 18px; text-transform: uppercase; }
  .m-p .nm small { display: block; font-size: 12px; color: var(--lab-mute); margin-top: 3px; }
  .m-p .gp, .m-p .tg { text-align: right; font-size: 15px; padding-right: 4px; }
  .m-p .tg { font-weight: 800; color: var(--mark); border-left: 1px solid var(--vrule); align-self: stretch; display: flex;
    align-items: center; justify-content: flex-end; }
  .chev { justify-self: center; width: 8px; height: 8px; border-right: 2px solid var(--mark);
    border-bottom: 2px solid var(--mark); transform: translateY(-2px) rotate(45deg);
    transition: transform .2s cubic-bezier(.16, 1, .3, 1); }
  .m-p[open] .chev { transform: translateY(2px) rotate(-135deg); }
  .m-p[open] summary { border-bottom: 1px solid var(--lab-rule); }
  .m-body { padding: 10px 16px 14px 16px; display: grid; gap: 12px; }
  .m-body dl { margin: 0; display: grid; }
  .m-body dt { font-size: 11px; font-weight: 800; color: var(--mark); }
  .m-body dd { margin: 2px 0 0; font-size: 14px; }
  .m-body dd.none { color: var(--lab-mute); }
  .m-body dl > div { padding: 0 6px; text-align: right; }
  .m-body dl > div + div { border-left: 1px solid var(--vrule); }
  .m-stats { grid-template-columns: repeat(7, 1fr); }
  .m-stats > div:first-child, .m-weeks > div:first-child { padding-left: 0; }
  .m-weeks { grid-template-columns: repeat(4, 1fr); }
  .m-weeks dd b { font-size: 16px; font-weight: 700; }
  .m-weeks dd s { text-decoration: none; color: var(--lab-mute); }
  .m-weeks dd small { display: block; font-size: 11px; font-weight: 600; color: var(--lab-mute); }
  .m-weeks .lo dd b { color: var(--lab-red); }
  .m-weeks > div:last-child dd b { font-weight: 900; color: var(--mark); }
  .m-weeks > div.lo:last-child dd b { color: var(--lab-red); }
  .m-grid { display: grid; grid-template-columns: repeat(var(--days), 1fr); }
  .m-grid > span { text-align: center; font-size: 10px; font-weight: 700; color: var(--lab-mute); line-height: 1.1;
    padding: 2px 0; }
  .m-grid > span:nth-child(-n+__DAYS__) { padding-bottom: 3px; }
  .m-grid > span:nth-child(n+__DAYS1__) { padding: 4px 0 5px; }
  .m-grid u { display: block; text-decoration: none; color: var(--lab-ink); }
  .m-grid > .q { background: var(--qcol); }
  .m-p:nth-of-type(even) .m-grid > .q { background: var(--qcol-z); }
  .m-p .m-grid > .q:nth-child(-n+__DAYS__), .m-p:nth-of-type(even) .m-grid > .q:nth-child(-n+__DAYS__) {
    background: var(--mark); color: var(--lab-stock); }
  .m-grid > .q:nth-child(-n+__DAYS__) u { color: var(--lab-stock); }
  .m-grid > .wk1 { border-left: 1px solid var(--vrule); }
  .m-grid i { width: 12px; height: 12px; }
  .m-tot { padding: 10px 16px 4px; border-top: 2px solid var(--mark); border-bottom: 2px solid var(--mark);
    color: var(--mark); }
  .m-tot b { text-transform: uppercase; font-weight: 800; font-size: 13px; }
  .m-tot dl { display: grid; grid-template-columns: repeat(4, 1fr); margin: 6px 0; }
  .m-tot dl > div { text-align: right; padding: 0 6px; } .m-tot dl > div + div { border-left: 1px solid var(--vrule); }
  .m-tot dt { font-size: 11px; font-weight: 800; }
  .m-tot dd { margin: 0; font-size: 18px; font-weight: 900; }
  .m-tot p { margin: 0 0 6px; font-size: 12px; color: var(--lab-mute); font-weight: 600; }
  .m-tot p.ul { margin: 0; padding-top: 6px; border-top: 1px solid var(--vrule); font-size: 11px; font-weight: 800;
    color: var(--mark); }
  .m-tot dl.u { margin-top: 2px; }
  .m-tot dl.u dd b { font-size: 15px; }
  .m-tot dl.u dd small { display: block; font-size: 11px; font-weight: 600; color: var(--lab-mute); }
  .legend { padding-top: 12px; }
}
@media (prefers-reduced-motion: reduce) { .chev { transition: none; } }"""

LEGEND = """<div class="legend" aria-label="Key"><b>Key</b>
<span><i class="k s"></i>Starts</span>
<span><i class="k b"></i>Game, sits</span>
<span><i class="k r"></i>Rests on back-to-back</span>
<span><i class="k n"></i>No game</span>
<span><span class="qsw"></span>Quality day</span>
<span><em class="flag">IL</em>On IL now, counts in the starts</span>
<span><span class="lo-key">2/4</span>Starts lost</span>
<span><span class="q-key">2 q</span>Games on quality days</span>
<span><span class="pc-key"><span class="pc p3"><i class="mtr"><i></i><i></i><i></i></i><b>90%</b></span>\
<span class="pc p2"><i class="mtr"><i></i><i></i><i></i></i><b>70%</b></span>\
<span class="pc p1"><i class="mtr"><i></i><i></i><i></i></i><b>69%</b></span></span>\
Used and vs ideal: 90% or more, 70% to 89%, less than 70%</span>
<span><span class="few-key">/<span class="few">2</span></span>2 or fewer games in the week</span>
</div>"""

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Roster · Fantasy Hoops Lab</title>
__HEAD__
<style>
__STYLE__
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main roster">
<header class="head">
<h1>__TITLE__</h1>
<dl class="meta">
__META__
</dl>
</header>
__DESK__
__MOB__
__LEGEND__
<p class="foot">__FOOT__</p>
</main>
__SCRIPT__
</body>
</html>
""".replace("__STYLE__", PAGE_STYLE).replace("__LEGEND__", LEGEND)
