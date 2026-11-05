"""The Schedule Skyline of the plan page (#236): the skyline of the week and the add ladder of your roster.

The Skyline replaces the team-plan week grid. The design is in docs/adds/README.md, "Schedule Skyline". The module
writes no files. core/skyline.py gives the facts of the week and core/skyline_svg.py draws them.

- ladder_plans(): rung n is the team_plan() plan with n adds, for n = 1 to min(adds left, [skyline] max_adds).
- roster_rungs(): the core.skyline Rungs of these plans. Each stream spot with an add is one lane of its rung. A leg
  is one add: the days from the add day to the last day that the new player holds the spot. Its dots are the days
  that he starts. A leg with [skyline] scarce_teams teams or fewer names its teams as team chips.
- plan_section(): the HTML of the section: the desktop layout (the days from left to right) and the 2 phone panels
  (the days from top to bottom), each in the light theme and the dark theme. A click on a leg opens the Free agents
  page with the filters of the add (grid.fa_link(), #165).
"""

import html
from collections import Counter

from fantasyhoops.adds.grid import add_text, fa_link, slot_text, team_count_at, teams_text
from fantasyhoops.adds.team_plan import UTIL, team_plan
from fantasyhoops.core.skyline import DAYS, Leg, Rung, week_facts
from fantasyhoops.core.skyline_svg import phone_panels, render

MAX_ADDS = 4  # [skyline] max_adds if config.toml does not set it
SCARCE_TEAMS = 5  # [skyline] scarce_teams if config.toml does not set it


def _e(text):
    return html.escape(str(text))


def _words(words, last="and"):
    words = list(words)
    return f" {last} ".join(filter(None, [", ".join(words[:-1]), words[-1]])) if words else ""


def _days(days):
    return _words((f"{d:%a}" for d in days), "&")


def skyline_week(sched, week, cfg):
    """The core.skyline.Week of the fantasy week week (readers.Week), or None if cfg has no [skyline] section."""
    return week_facts(sched, week.start, cfg) if "skyline" in cfg else None


def rung_count(adds_left, cfg):
    """The number of rungs: min(adds left, [skyline] max_adds)."""
    return max(0, min(adds_left, cfg.get("skyline", {}).get("max_adds", MAX_ADDS)))


def ladder_plans(days, games, spots, adds_left, slots, cfg, next_week=None, next_weight=0.0, full=None):
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
            plans.append(team_plan(days, games, spots, n, slots, next_week=next_week, next_weight=next_weight))
    return tuple(plans)


def _num(x):
    """A game count: an int when it is whole, else 1 decimal (a rest game counts less than 1)."""
    x = round(x, 1)
    return int(x) if x == int(x) else x


def _leg(add, week, scarce):
    """The Leg of one TeamAdd in week (a core.skyline.Week), or None if the add day is not a day of the week."""
    if add.day not in week.days:
        return None
    first = week.days.index(add.day)
    last = week.days.index(add.last_day) + 1 if add.last_day in week.days else DAYS
    starts = tuple(d for d in add.starts if d in week.days)
    light = sum(1 for d in starts if week.light[week.days.index(d)])
    return Leg(first, last, len(starts), light, tuple(add.teams), starts, len(add.teams) <= scarce, {}, ())


def roster_rungs(week, plans, cfg):
    """(the Rungs of plans, {id(leg): (rung number, TeamAdd)}) for week.

    Rung n: plans[n - 1]. Its games are the counted started games of the stream spots. Its lanes: the legs of each
    stream spot with an add, in order of the first add day, then the spot. replan: the rung does not keep each add of the rung above. plus_one: the
    start days that the rung has more often than the rung above, light nights first.
    """
    scarce = cfg.get("skyline", {}).get("scarce_teams", SCARCE_TEAMS)
    rungs, adds_of, before = [], {}, None
    for n, plan in enumerate(plans, start=1):
        lanes = {}
        for add in plan.adds:
            leg = _leg(add, week, scarce)
            if leg is not None:
                lanes.setdefault(add.spot, []).append(leg)
                adds_of[id(leg)] = (n, add)
        lanes = tuple(tuple(lanes[s]) for s in sorted(lanes, key=lambda s: (lanes[s][0].first, s)))
        legs = tuple(leg for lane in lanes for leg in lane)
        games = _num(plan.started_games)
        light = sum(leg.light for leg in legs)
        gain, plus_one, replan = 0, (), False
        if before is not None:
            gain = _num(games - before.games)
            more = Counter(d for leg in legs for d in leg.pattern) - Counter(
                d for leg in before.legs for d in leg.pattern
            )
            ranked = sorted(more, key=lambda d: (not week.light[week.days.index(d)], d))
            plus_one = tuple(sorted(ranked[: max(1, round(gain))])) if gain > 0 else ()
            kept = {(a.spot, a.day, a.teams) for a in plan.adds}
            replan = any((a.spot, a.day, a.teams) not in kept for a in plans[n - 2].adds)
        rung = Rung(n, (), legs, games, light, gain, n > 1 and gain <= 0, replan, plus_one, games, lanes)
        rungs.append(rung)
        before = rung
    return tuple(rungs), adds_of


def _said_slots(slots):
    return "any position" if slots == (UTIL,) else _words(slots, "or")


def _leg_href(run, adds_of, count_at):
    """The function (rung, leg) -> (the Free agents link of the add of leg, its text label) for render()."""
    index = {d.date for d in run.days}

    def href(rung, leg):
        n, add = adds_of[id(leg)]
        days = [d for d in add.starts if d in index]
        pos = "" if add.slots == (UTIL,) else ",".join(add.slots)
        teams = teams_text(add.teams, count_at)
        source = f"{n} add{'s' if n > 1 else ''}, spot {add.spot + 1}, {add.day:%a}: +{slot_text(add.slots)} {teams}"
        label = (
            f"{n} add{'s' if n > 1 else ''}, spot {add.spot + 1}: on {add.day:%a} add {_said_slots(add.slots)} from "
            f"{_words(add.teams, 'or')}. Starts {_days(add.starts)}. Show these free agents."
        )
        return fa_link(days, pos, add.teams, source), label

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
    "your stream spots with n adds. Each stream spot with an add has its own row in the rung. A white block is one "
    "add: from the add day to the last day that the new player holds the spot. A dot marks a day that he starts. A "
    "line between 2 dots marks a back-to-back. With {scarce} teams or fewer, the block names the teams. Else it gives "
    'the count. The number at the left is the started games of your stream spots. "+1" marks a game that the extra '
    "add buys. RE-PLAN: the rung does not keep the adds of the rung above. A click on a block opens the Free agents "
    "page with the filters of the add.</p></details>"
)


def plan_section(run, interactive=True):
    """The Schedule Skyline section of a PlanningRun as HTML.

    run.skyline: the core.skyline.Week of the fantasy week, or None. run.ladder: the TeamPlans of ladder_plans().
    run.record: the saved adds, for the past days. interactive: the Free agents page has a free-agent table, so each
    leg is a link to it (#165). With no rung, the ladder shows the one open spot of core/skyline.py and a line gives
    the reason.
    """
    week, cfg = run.skyline, run.cfg
    plans = tuple(run.ladder or ())
    count_at = team_count_at(cfg)
    rungs, adds_of = roster_rungs(week, plans, cfg) if week is not None else ((), {})
    lines = []
    message = _messages(run, rungs)
    if message:
        lines.append(f'<p class="tp-lede">{_e(message)}</p>')
        rungs = ()
    else:
        tap = " Tap a block to see the free agents who fit it." if interactive else ""
        lines.append(
            f'<p class="tp-lede">Rung n is the best plan with <b>n adds</b>. You have <b>{run.data.adds.left} adds '
            f"left</b>.{tap}</p>"
        )
    figure = ""
    if week is not None:
        no = run.data.week.number
        href = _leg_href(run, adds_of, count_at) if interactive and rungs else None
        drawn = rungs or None  # None: the ladder of one open spot, with no links
        if not rungs:
            lines.append('<p class="muted tp-note">The ladder shows one open spot on each day, not your roster.</p>')
        wide = _themes(lambda t: render(week, no, "page", drawn, href, t))
        tall = _themes(lambda t: "".join(phone_panels(week, no, drawn, href, t)))
        figure = f'<div class="sky"><div class="sky-wide">{wide}</div><div class="sky-tall">{tall}</div></div>'
    light_max = week.light_max if week is not None else cfg.get("quality_games", {}).get("max_games_per_day", 6)
    scarce = cfg.get("skyline", {}).get("scarce_teams", SCARCE_TEAMS)
    return "\n".join(
        [
            '<section id="plan"><h2 class="vh">Schedule Skyline</h2>',
            *lines,
            figure,
            _notes(run, plans),
            LEGEND.format(light_max=light_max, scarce=scarce),
            "</section>",
        ]
    )


CSS = """
/* The Schedule Skyline (issue 236): the desktop layout above 599px, the 2 phone panels below. The page shows the
   copy of the current theme. */
.tp-lede { color: var(--fg); font-size: 14px; margin: 0 0 10px; }
.tp-lede b { font-weight: 800; }
.tp-note { font-size: 12px; margin: 4px 0 0; }
.tp-past { font-size: 12px; margin: 2px 0 0; padding-left: 18px; }
.sky { margin: 0 0 8px; }
.sky svg { display: block; width: 100%; height: auto; }
.sky-tall { display: none; }
.sky-tall svg + svg { margin-top: 12px; }
.sky-dark { display: none; }
:root[data-theme="dark"] .sky-light { display: none; }
:root[data-theme="dark"] .sky-dark { display: block; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .sky-light { display: none; }
  :root:not([data-theme="light"]) .sky-dark { display: block; }
}
@media (max-width: 599px) {
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
