import re
from contextlib import contextmanager
from datetime import date, timedelta
from html.parser import HTMLParser
from types import SimpleNamespace

from fantasyhoops.adds import page
from fantasyhoops.adds import plan as command
from fantasyhoops.adds.planner import Option, Plan, StreamSpot, TeamRank, TeamWindow
from fantasyhoops.adds.readers import Adds, Player, Week
from fantasyhoops.adds.slots import Day

MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]
DAYS = [Day(d, 5, (), (), ("PG", "Util") if i in (0, 1, 3, 5) else ()) for i, d in enumerate(WEEK)]
DATA = command.LeagueData(roster=[Player("Hurt Guy", "BOS", ("PG",), status="O")], adds=Adds(used=1, limit=5),
                          week=Week(number=12, days=tuple(WEEK)))


def option(name, team, value, positions=("SF",), status=""):
    return Option(Player(name, team, positions, status=status), value)


HOLDER = option("Old Streamer", "MIA", -0.5)
PHI = [option("Phi One", "PHI", 0.31), option("Phi & Two", "PHI", -0.12, ("PG", "SG"), "Q"), option("Phi Three", "PHI", None)]
DAL = [option("Dal One", "DAL", 0.05, ("C",))]
CHI = [option("Chi One", "CHI", -0.40, ("PF",)), option("Chi Two", "CHI", -0.60, ("PF",))]
PLAN = Plan(windows=(
    TeamWindow(0, "PHI", WEEK[0], WEEK[6], (WEEK[0], WEEK[1], WEEK[5]), PHI[0], tuple(PHI)),
    TeamWindow(1, "MIA", None, WEEK[2], (WEEK[0],), HOLDER, ()),
    TeamWindow(1, "DAL", WEEK[3], WEEK[3], (WEEK[3],), DAL[0], tuple(DAL)),
    TeamWindow(1, "CHI", WEEK[5], WEEK[6], (WEEK[5],), CHI[0], tuple(CHI)),
), started_games=6, adds=3)
SPOTS = [StreamSpot(), StreamSpot(HOLDER)]
RANKING = [TeamRank("PHI", (WEEK[0], WEEK[1], WEEK[5]), 6), TeamRank("DAL", (WEEK[3],), 2)]


def render(**kw):
    return page.render(DATA, DAYS, SPOTS, PLAN, RANKING, ["PHI"], WEEK[0], **kw)


def text(html):
    """The visible text of a page, with single spaces."""
    parts = []
    parser = HTMLParser()
    parser.handle_data = parts.append
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parts))


def test_the_page_holds_each_team_window_and_each_option():
    html = render()
    shown = text(html)
    assert "Spot 1 · PHI Mon 1/4 – Sun 1/10" in shown
    assert "Spot 2 · MIA Mon 1/4 – Wed 1/6" in shown and "Old Streamer holds the spot now" in shown
    assert "Spot 2 · DAL Thu 1/7" in shown
    assert "Spot 2 · CHI Sat 1/9 – Sun 1/10" in shown
    for w in PLAN.windows:
        if w.add_day:
            assert f"Latest add day: {page._day(w.add_day)}" in shown
        for o in w.options:
            assert o.player.name in shown
    assert "Phi &amp; Two" in html and "Phi & Two" not in html
    for value in ("+0.31", "-0.12", "+0.05", "-0.40", "-0.60", "—"):
        assert value in shown


def test_the_grid_shows_the_team_of_each_day_and_the_started_games():
    rows = re.findall(r"<tr><th>Spot \d</th>(.*?)</tr>", render())
    cells = [re.findall(r'<td class="(\w+)">(?:<i[^>]*>\+</i>)?([^<]*)</td>', row) for row in rows]
    assert cells[0] == [("on", "PHI"), ("on", "PHI"), ("hold", "PHI"), ("hold", "PHI"), ("hold", "PHI"),
                        ("on", "PHI"), ("hold", "PHI")]
    assert cells[1] == [("on", "MIA"), ("hold", "MIA"), ("hold", "MIA"), ("on", "DAL"), ("empty", "·"),
                        ("on", "CHI"), ("hold", "CHI")]


def test_the_page_shows_the_main_numbers_and_the_ranking():
    shown = text(render())
    assert "6 started games" in shown and "3 adds used" in shown and "4 of 5 adds left" in shown
    assert "Week 12: Mon 1/4 to Sun 1/10" in shown
    assert "Out (does not play): Hurt Guy (O)" in shown
    assert "*PHI" in shown and "DAL" in shown


def test_the_page_has_no_scripts_and_no_parts_of_later_tickets_without_data():
    html = render()
    assert "<script" not in html and "http" not in html
    for part in ("Recent", "Blend", "Trend", "Aggressive", "Comparison", "Contingency", 'class="warning"', 'class="drop"'):
        assert part not in html


def test_the_page_shows_the_optional_fields_when_they_exist():
    o = SimpleNamespace(player=PHI[0].player, projected_value=0.31, recent_value=0.75, blended_value=0.52,
                        trend="+1,204 today")
    w = SimpleNamespace(**{**vars(PLAN.windows[0]), "options": (o,), "player": o}, drop="Drop Quickley: +2 games")
    plan = SimpleNamespace(windows=(w,), started_games=3, adds=1, blended_value=1.5)
    aggressive = Plan(windows=PLAN.windows[2:], started_games=2, adds=2)
    html = page.render(DATA, DAYS, SPOTS, plan, today=WEEK[0], aggressive=aggressive,
                       warnings=["Dal One has a higher value than a core player."],
                       contingencies=["Phi & Two out on Tue: move Bench Guy to PG."])
    shown = text(html)
    for part in ("Recent", "+0.75", "Blend", "+0.52", "+1,204 today", "Drop Quickley: +2 games", "+1.5",
                 "Aggressive plan", "Comparison", "Dal One has a higher value", "Contingency plans", "move Bench Guy"):
        assert part in shown


def test_the_page_explains_why_there_is_no_plan():
    assert "No adds left this week (5 of 5 used)" in text(page.render(
        command.LeagueData([], Adds(5, 5), DATA.week), DAYS, SPOTS, None, today=WEEK[0]))
    assert "No stream spots" in text(page.render(DATA, DAYS, [], None, today=WEEK[0]))
    assert "Stream spots by day" not in text(page.render(DATA, [], SPOTS, None, today=WEEK[0]))


def test_the_command_writes_the_page_and_publishes_it(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=True)
    path = tmp_path / "adds_plan.html"
    assert published == [(command.ROOT, "adds", path)]
    out = capsys.readouterr().out
    assert f"Wrote the plan page: {path}" in out
    assert "Plan page: 2 started games with 1 add." in out
    assert command.URL in out and command.URL.endswith("/adds/")
    assert "Spot 1 · PHI" in text(path.read_text(encoding="utf-8"))


def test_the_command_does_not_publish_with_no_publish(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=False)
    assert published == []
    assert (tmp_path / "adds_plan.html").exists()
    assert "did not publish" in capsys.readouterr().out


def run_command(monkeypatch, tmp_path, published, publish):
    """Run plan.main() with no Yahoo session, no schedule file and site.publish replaced."""
    @contextmanager
    def no_yahoo(league):
        yield None

    import pandas as pd
    sched = pd.DataFrame({"date": [str(WEEK[0]), str(WEEK[0]), str(WEEK[1])], "team": ["PHI", "BOS", "PHI"]})
    cfg = {"league": {"slots": ["PG", "SG", "SF", "PF", "C"], "roster_spots": 10},
           "adds": {"league": 1, "team": 1}}
    monkeypatch.setattr(command, "load_config", lambda: cfg)
    monkeypatch.setattr(command, "read_schedule", lambda: sched)
    monkeypatch.setattr(command, "open_league", no_yahoo)
    monkeypatch.setattr(command, "read_league", lambda yahoo, cfg, today: command.LeagueData(
        roster=[], adds=Adds(4, 5), week=Week(12, tuple(WEEK[:2]))))
    monkeypatch.setattr(command, "stream_spots", lambda roster, cfg: [StreamSpot()])
    monkeypatch.setattr(command, "read_team_free_agents", lambda yahoo, teams: [])
    monkeypatch.setattr(command, "value_options", lambda fas, cfg: [option("Phi One", "PHI", 0.3)])
    monkeypatch.setattr(page, "PAGE", tmp_path / "adds_plan.html")
    monkeypatch.setattr(command.site, "publish", lambda *args: published.append(args))
    command.main(today=WEEK[0], publish=publish)
