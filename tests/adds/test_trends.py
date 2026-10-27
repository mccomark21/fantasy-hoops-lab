from datetime import date, timedelta
from pathlib import Path

import pytest

from fantasyhoops.adds.plan import print_plan, with_trends
from fantasyhoops.adds.planner import Option, Plan, StreamSpot, TeamWindow, option_order, schedule_plan
from fantasyhoops.adds.readers import Adds, Player, Week
from fantasyhoops.adds.slots import open_slots_by_day
from fantasyhoops.adds.trends import Trend, read_trends, trend_days, trends_path, week_trends

FIXTURES = Path(__file__).parent / "fixtures"
MON = date(2027, 1, 4)


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def page(rows):
    """A Transaction Trends page with rows of (name, adds, drops)."""
    body = "".join(
        f'<tr><td></td><td><div class="ysf-player-name"><a class="name" title="{n}">{n}</a>'
        f'<span class="D-b"><span class="Fz-xxs">PHI - C</span></span></div></td><td></td><td>FA</td>'
        f"<td>1%</td><td>1%</td><td>{a}</td><td>{d}</td><td>0</td><td>{a + d}</td><td></td></tr>"
        for n, a, d in rows
    )
    return (
        '<table class="Tst-table"><thead><tr><th></th><th>Player</th><th></th><th>Roster Status</th>'
        "<th>% Ros</th><th>% Start</th><th>Adds</th><th>Drops</th><th>Trades</th><th>Total</th><th></th>"
        f"</tr></thead><tbody>{body}</tbody></table>"
    )


def test_read_trends_gives_the_adds_and_drops_of_each_player():
    trends = read_trends(fixture("trends.html"))
    assert len(trends) == 8
    assert trends["Kevin Porter Jr."] == (228, 4315)
    assert trends["Zaccharie Risacher"] == (3273, 175)
    # The link text is short. The title has the full name, the same name as in the free-agent list.
    assert trends["Yanic Konan Niederhäuser"] == (402, 55)


def test_read_trends_finds_the_sorted_column_with_its_sort_icon():
    # With sort=BI_A, the Adds header also has a sort icon, and the last header is "Adds Drops".
    html = fixture("trends.html").replace(">Adds<", ">Adds <", 1)
    assert read_trends(html)["Kevin Porter Jr."] == (228, 4315)


def test_read_trends_needs_the_table():
    with pytest.raises(ValueError):
        read_trends("<html></html>")


def test_week_trends_adds_the_days_and_takes_today_from_the_first_page():
    today = page([("A", 10, 1), ("B", 5, 0)])
    yesterday = page([("A", 100, 2), ("C", 7, 3)])
    trends = week_trends([today, yesterday])
    assert trends["A"] == Trend(adds_today=10, adds_week=110, drops_today=1, drops_week=3)
    # C is not on the page of today: 0 adds today.
    assert trends["C"] == Trend(adds_today=0, adds_week=7, drops_today=0, drops_week=3)
    assert "D" not in trends


def test_trend_days_are_the_days_of_this_week_up_to_today():
    week = Week(number=3, days=tuple(MON + timedelta(days=i) for i in range(7)))
    assert trend_days(week, MON + timedelta(days=2)) == [MON, MON + timedelta(days=1), MON + timedelta(days=2)]
    # On the last day of a week, week is the next week. The days are today and the 6 days before it.
    sunday = MON - timedelta(days=1)
    assert trend_days(week, sunday, next_week=True) == [sunday - timedelta(days=i) for i in range(6, -1, -1)]
    assert "date=2027-01-04" in trends_path(MON) and "sort=BI_A" in trends_path(MON)


def option(name, value, trend=None, team="PHI"):
    return Option(Player(name, team, ("C",)), value, trend=trend)


def test_with_more_adds_an_option_with_the_same_value_comes_first():
    quiet, busy = option("Quiet", 1.0, Trend(50, 100)), option("Busy", 1.0, Trend(10, 900))
    better = option("Better", 2.0)
    off_page = option("Off page", 1.0)
    assert sorted([off_page, quiet, better, busy], key=option_order) == [better, busy, quiet, off_page]
    # The options of a team window use the same order.
    roster = [Player(f"P{i}", "BOS", (pos,)) for i, pos in enumerate(["PG", "SG", "SF", "PF", "PG"])]
    games = {MON: {"PHI", "BOS"}}
    slots = ["PG", "SG", "SF", "PF", "C"]
    days = open_slots_by_day(roster, games, slots)
    plan = schedule_plan(days, games, [StreamSpot()], [off_page, quiet, busy], 5, slots)
    assert [o.player.name for o in plan.windows[0].options] == ["Busy", "Quiet", "Off page"]
    assert (plan.started_games, plan.adds) == (1, 1)


def test_with_trends_gives_none_for_a_player_who_is_not_on_the_pages():
    a, b = option("A", 1.0), option("B", 1.0)
    out = with_trends([a, b], {"A": Trend(3, 9)})
    assert [o.trend for o in out] == [Trend(3, 9), None]


def test_print_plan_shows_the_adds_or_a_dash(capsys):
    on_page, off_page = option("On page", 1.0, Trend(228, 1500)), option("Off page", 0.5)
    window = TeamWindow(
        spot=0, team="PHI", add_day=MON, last_day=MON, started=(MON,), player=on_page, options=(on_page, off_page)
    )
    print_plan(
        Plan(windows=(window,), started_games=1, adds=1), [StreamSpot()], Adds(used=0, limit=5), MON - timedelta(days=1)
    )
    lines = capsys.readouterr().out.splitlines()
    assert next(line for line in lines if "On page" in line).endswith("adds today 228, this week 1500")
    assert next(line for line in lines if "Off page" in line).endswith("adds -")
