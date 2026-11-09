"""The Schedule Skyline of the plan page (#236): the skyline of the week and the add ladder of your roster.

The Skyline replaces the team-plan week grid. The design is in docs/adds/README.md, "Schedule Skyline". The module
writes no files. core/skyline.py gives the facts of the week and core/skyline_svg.py draws them.

- ladder_plans(): rung n is the team_plan() plan with n adds, for n = 1 to min(adds left, [skyline] max_adds).
- roster_rungs(): the core.skyline Rungs of these plans. A rung is one row of legs with no overlap, as the ladder of
  the post (owner, 2026-11-05). Each add day starts a leg, and the leg runs to the day before the next add day of the
  rung. The leg holds the adds of its first day. Its dots are the days that a new player of the rung starts. A leg
  with [skyline] scarce_teams teams or fewer names its teams as team chips.
- plan_section(): the HTML of the section: the desktop layout (the days from left to right) and the 2 phone panels
  (the days from top to bottom), each in the light theme and the dark theme. The week number comes from the week
  calendar of config.toml (core/weeks.py). A click on a leg opens the Free agents
  page with the filters of the add (grid.fa_link(), #165).
"""

import html
from collections import Counter

from fantasyhoops.adds.grid import add_text, fa_link, slot_text, team_count_at, teams_text
from fantasyhoops.adds.team_plan import UTIL, team_plan
from fantasyhoops.core.skyline import DAYS, Leg, Rung, week_facts
from fantasyhoops.core.skyline_svg import phone_panels, render, week_dates
from fantasyhoops.core.weeks import week_number

MAX_ADDS = 4  # [skyline] max_adds if config.toml does not set it
SCARCE_TEAMS = 5  # [skyline] scarce_teams if config.toml does not set it


def _e(text):
    return html.escape(str(text))


def _words(words, last="and"):
    words = list(words)
    return f" {last} ".join(filter(None, [", ".join(words[:-1]), words[-1]])) if words else ""


def _days(days):
    return _words((f"{d:%a}" for d in days), "&")


def skyline_weeks(sched, week, cfg):
    """The core.skyline.Week of each 7-day half of the fantasy week week (readers.Week), first half first.

    A long week (14 days, owner, 2026-11-05) has 2 halves. Every other week has 1. () if cfg has no [skyline] section.
    """
    if "skyline" not in cfg:
        return ()
    return tuple(week_facts(sched, week.days[i], cfg) for i in range(0, len(week.days), DAYS))


def rung_count(adds_left, cfg):
    """The number of rungs: min(adds left, [skyline] max_adds)."""
    return max(0, min(adds_left, cfg.get("skyline", {}).get("max_adds", MAX_ADDS)))


def ladder_plans(
    days, games, spots, adds_left, slots, cfg, next_week=None, next_weight=0.0, full=None, light=(), light_weight=1.0
):
    """The TeamPlans of the rungs: item n - 1 is the team_plan() plan with n adds or fewer.

    The arguments are the arguments of team_plan(). full: the plan with adds_left adds, if the run has it already.
    No plans with no stream spots or no days.
    """
    if not spots or not days:
        return ()
    plans = []
    for n in range(1, rung_count(adds_left, cfg) + 1):
        if full is not None and n == adds_left:
            plans.append(full)
        else:
            plans.append(
                team_plan(
                    days,
                    games,
                    spots,
                    n,
                    slots,
                    next_week=next_week,
                    next_weight=next_weight,
                    light=light,
                    light_weight=light_weight,
                )
            )
    return tuple(plans)


def _num(x):
    """A game count: an int when it is whole, else 1 decimal (a rest game counts less than 1)."""
    x = round(x, 1)
    return int(x) if x == int(x) else x


def _legs(plan, week, scarce, light):
    """[(Leg, the TeamAdds of the leg)] of plan in week: one leg from each add day to the next add day.

    In the second half of a long week, the adds of the first half that still hold a spot on Monday continue: a leg
    starts on Monday with their teams, up to the first add day of the half.
    """
    adds = [a for a in plan.adds if a.day <= week.days[-1] and a.last_day >= week.days[0]]
    days = sorted({a.day for a in adds if a.day in week.days})
    carry = [a for a in adds if a.day < week.days[0]]
    if carry and (not days or days[0] > week.days[0]):
        days.insert(0, week.days[0])
    out = []
    for k, day in enumerate(days):
        first = week.days.index(day)
        last = week.days.index(days[k + 1]) if k + 1 < len(days) else DAYS
        span = set(week.days[first:last])
        here = [a for a in adds if a.day == day] or carry
        # The starts in the leg: each start day of each new player of the rung, with one count for each player.
        starts = [d for a in adds for d in a.starts if d in span and a.day <= d <= a.last_day]
        teams = tuple(sorted({t for a in here for t in a.teams}))
        pattern = tuple(sorted(set(starts)))
        lights = sum(1 for d in starts if light[d])
        out.append((Leg(first, last, len(starts), lights, teams, pattern, len(teams) <= scarce, {}, ()), here))
    return out


def roster_rungs(week, plans, cfg, matchup=None):
    """(the Rungs of plans, {id(leg): (rung number, the TeamAdds of the leg)}) for week.

    Rung n: plans[n - 1]. Its games are the counted started games of the stream spots. Its legs: _legs(). replan:
    the rung does not keep each add of the rung above. plus_one: the start days that the rung has more often than the
    rung above, light nights first. matchup: the Weeks of all halves of a long week, so that the gain days of a rung
    are the same in each half. None: week only.
    """
    scarce = cfg.get("skyline", {}).get("scarce_teams", SCARCE_TEAMS)
    light = {d: lt for w in (matchup or (week,)) for d, lt in zip(w.days, w.light)}
    rungs, adds_of, before = [], {}, None
    for n, plan in enumerate(plans, start=1):
        legs = []
        for leg, here in _legs(plan, week, scarce, light):
            legs.append(leg)
            adds_of[id(leg)] = (n, tuple(here))
        starts = Counter(d for a in plan.adds for d in a.starts if d in light)
        games = _num(plan.started_games)
        gain, plus_one, replan = 0, (), False
        if before is not None:
            gain = _num(games - before[0].games)
            more = starts - before[1]
            ranked = sorted(more, key=lambda d: (not light[d], d))
            plus_one = tuple(sorted(ranked[: max(1, round(gain))])) if gain > 0 else ()
            kept = {(a.spot, a.day, a.teams) for a in plan.adds}
            replan = any((a.spot, a.day, a.teams) not in kept for a in plans[n - 2].adds)
        # The light-night starts of the whole matchup, so that both halves of a long week show the same rung total.
        lights = sum(n for d, n in starts.items() if light[d])
        rung = Rung(
            n,
            tuple(x.first for x in legs[1:]),
            tuple(legs),
            games,
            lights,
            gain,
            n > 1 and gain <= 0,
            replan,
            plus_one,
            games,
        )
        rungs.append(rung)
        before = (rung, starts)
    return tuple(rungs), adds_of


def _said_slots(slots):
    return "any position" if slots == (UTIL,) else _words(slots, "or")


def _leg_href(run, adds_of, count_at, slots):
    """The function (rung, leg) -> (the Free agents link of the adds of leg, its text label) for render().

    A leg with more than one add sets the filters of all its adds: their start days, their slots and their teams.
    """
    index = {d.date for d in run.days}

    def href(rung, leg):
        n, adds = adds_of[id(leg)]
        days = sorted({d for a in adds for d in a.starts if d in index})
        util = any(a.slots == (UTIL,) for a in adds)
        pos = "" if util else ",".join(s for s in slots if any(s in a.slots for a in adds))
        teams = tuple(sorted({t for a in adds for t in a.teams}))
        head = f"{n} add{'s' if n > 1 else ''}, {adds[0].day:%a}: "
        source = head + ", ".join(f"+{slot_text(a.slots)} {teams_text(a.teams, count_at)}" for a in adds)
        said = " and ".join(f"{_said_slots(a.slots)} from {_words(a.teams, 'or')}" for a in adds)
        starts = sorted({d for a in adds for d in a.starts})
        label = (
            f"{n} add{'s' if n > 1 else ''}: on {adds[0].day:%a} add {said}. Starts {_days(starts)}. "
            "Show these free agents."
        )
        return fa_link(days, pos, teams, source), label

    return href


def _messages(run, rungs):
    """The reason for a ladder with no rung, or nothing."""
    adds = run.data.adds
    if not run.spots:
        return (
            "No stream spots. All roster spots hold a player, and [adds] stream_spots is 0. There are no adds to plan."
        )
    if not adds.left:
        return f"No adds left this week ({adds.used} of {adds.limit} used). There are no adds to plan."
    if not run.days:
        return "The fantasy week is over. There are no days to plan."
    if not any(r.legs for r in rungs):
        return "No NBA team gives a started game in an open slot."
    return ""


def _themes(make):
    """The light and the dark copy of a drawing. The page CSS shows the copy of the current theme."""
    return f'<div class="sky-light">{make("light")}</div><div class="sky-dark">{make("dark")}</div>'


def _notes(run, plans):
    """The lines under the Skyline: the saved adds of the past days, the past days with no saved plan, an add for
    today and the adds whose teams start on different days."""
    today, record, count_at = run.today, run.record, team_count_at(run.cfg)
    week = list(run.data.week.days)
    notes = []
    past = [a for a in (record.adds if record else ()) if a.day < today]
    if past:
        lines = "".join(f"<li>{_e(add_text(a, count_at))}</li>" for a in past)
        notes.append(f'<p class="muted tp-note">Saved adds of past days:</p><ul class="muted tp-past">{lines}</ul>')
    runs = set(record.runs) if record else set()
    missing = [d for d in week if d < today and d not in runs]
    if missing:
        notes.append(f'<p class="muted tp-note">No saved plan for {_e(_words(f"{d:%a}" for d in missing))}.</p>')
    adds = {(a.spot, a.day, a.teams): a for plan in plans for a in plan.adds}.values()
    if any(a.day == today for a in adds):
        notes.append('<p class="muted tp-note">An add for today helps only if his game has not started.</p>')
    for a in sorted({(a.day, a.teams): a for a in adds if a.mixed}.values(), key=lambda a: a.day):
        notes.append(
            f'<p class="muted tp-note">The teams of the add on {a.day:%a} ({_e(" ".join(a.teams))}) play on '
            "different days. Its dots mark the days that all of them play.</p>"
        )
    return "".join(notes)


LEGEND = (
    '<details class="notes" id="plan-notes"><summary>How to read the Skyline</summary>\n'
    '<p class="legend">The skyline at the top shows the NBA games of each night. A blue night is a light night: '
    "{light_max} or fewer games. The ladder below has one rung for each number of adds. Rung n is the best plan for "
    "your stream spots with n adds. A white block starts on an add day and runs to the next add day of the rung. It "
    "names the teams of the adds of its first day. A dot marks a day that a new player of the rung starts. A "
    "line between 2 dots marks a back-to-back. With {scarce} teams or fewer, the block names the teams. Else it gives "
    'the count. The number at the left is the started games of your stream spots. "+1" marks a game that the extra '
    "add buys. RE-PLAN: the rung does not keep the adds of the rung above. A click on a block opens the Free agents "
    "page with the filters of the add.</p></details>"
)


def plan_section(run, interactive=True):
    """The Schedule Skyline section of a PlanningRun as HTML.

    run.skyline: the core.skyline.Week of each 7-day half of the fantasy week (skyline_weeks()), or (). A long week
    has 2 halves: 2 Skylines, one above the other, each with its own date line. A leg that crosses the seam continues
    in the second half. run.ladder: the TeamPlans of ladder_plans(). run.record: the saved adds, for the past days.
    interactive: the Free agents page has a free-agent table, so each leg is a link to it (#165). With no rung, the
    ladder shows the one open spot of core/skyline.py and a line gives the reason.
    """
    cfg = run.cfg
    weeks = run.skyline or ()
    weeks = weeks if isinstance(weeks, tuple) else (weeks,)
    plans = tuple(run.ladder or ())
    count_at = team_count_at(cfg)
    halves, adds_of = [], {}
    for week in weeks:
        rungs, found = roster_rungs(week, plans, cfg, weeks)
        halves.append(rungs)
        adds_of.update(found)
    lines = []
    message = _messages(run, [r for rungs in halves for r in rungs])
    if message:
        lines.append(f'<p class="tp-lede">{_e(message)}</p>')
        halves = [() for _ in weeks]
    else:
        tap = " Tap a block to see the free agents who fit it." if interactive else ""
        lines.append(
            f'<p class="tp-lede">Rung n is the best plan with <b>n adds</b>. You have <b>{run.data.adds.left} adds '
            f"left</b>.{tap}</p>"
        )
    figures = []
    if weeks:
        # The week number of the calendar of config.toml ([weeks]), else the number of the Yahoo page.
        no = week_number(run.data.week.start, cfg, run.data.week.number)
        slots = cfg.get("league", {}).get("slots", ["PG", "SG", "SF", "PF", "C"])
        href = _leg_href(run, adds_of, count_at, slots) if interactive and any(halves) else None
        if not any(halves):
            lines.append('<p class="muted tp-note">The ladder shows one open spot on each day, not your roster.</p>')
        for k, (week, rungs) in enumerate(zip(weeks, halves), start=1):
            drawn = rungs or None  # None: the ladder of one open spot, with no links
            wide = _themes(lambda t: render(week, no, "page", drawn, href, t))
            tall = _themes(lambda t: "".join(phone_panels(week, no, drawn, href, t)))
            if len(weeks) > 1:
                figures.append(f'<p class="sky-dates">Week {no}, part {k} of {len(weeks)}: {_e(week_dates(week))}</p>')
            figures.append(
                f'<div class="sky"><div class="sky-wide">{wide}</div><div class="sky-tall">{tall}</div></div>'
            )
    light_max = weeks[0].light_max if weeks else cfg.get("quality_games", {}).get("max_games_per_day", 6)
    scarce = cfg.get("skyline", {}).get("scarce_teams", SCARCE_TEAMS)
    return "\n".join(
        [
            '<section id="plan"><h2 class="vh">Schedule Skyline</h2>',
            *lines,
            *figures,
            _notes(run, plans),
            LEGEND.format(light_max=light_max, scarce=scarce),
            "</section>",
        ]
    )


CSS = """
/* The Schedule Skyline (issue 236): the desktop layout from 1210px, the 2 phone panels below. The page shows the
   copy of the current theme. The desktop layout is wider than the sheet: 914px or more at 1210px, so that its
   text of 13 units is 11px or more. 288px: the menu (216px), the side padding of the sheet and a scrollbar. */
.tp-lede { color: var(--fg); font-size: 14px; margin: 0 0 10px; }
.tp-lede b { font-weight: 800; }
.tp-note { font-size: 12px; margin: 4px 0 0; }
.tp-past { font-size: 12px; margin: 2px 0 0; padding-left: 18px; }
.sky { margin: 0 0 8px; }
.sky-dates { color: var(--fg); font-size: 14px; font-weight: 800; margin: 12px 0 4px; }
.sky svg { display: block; width: 100%; height: auto; }
.sky-wide { width: min(1080px, calc(100vw - 288px)); }
.sky-tall { display: none; max-width: 520px; }
.sky-tall svg + svg { margin-top: 12px; }
.sky-dark { display: none; }
:root[data-theme="dark"] .sky-light { display: none; }
:root[data-theme="dark"] .sky-dark { display: block; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .sky-light { display: none; }
  :root:not([data-theme="light"]) .sky-dark { display: block; }
}
@media (max-width: 1209px) {
  .sky-wide { display: none; }
  .sky-tall { display: block; }
}
/* A leg link: an ink frame on hover, a 2px ink outline on focus. */
.sky a { cursor: pointer; }
.sky a:hover .leg-box { stroke: var(--lab-ink) !important; stroke-width: 2px !important; }
.sky a:focus { outline: none; }
.sky a:focus-visible { outline: 2px solid var(--lab-ink); outline-offset: 2px; }
.sky a:focus-visible .leg-box { stroke: var(--lab-ink) !important; stroke-width: 4px !important; }
"""
