import json
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
from fantasyhoops.adds.spots import SpotPlan

MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]
DAYS = [Day(d, 5, (), (), ("PG", "Util") if i in (0, 1, 3, 5) else ()) for i, d in enumerate(WEEK)]
DATA = command.LeagueData(roster=[Player("Hurt Guy", "BOS", ("PG",), status="O")], adds=Adds(used=1, limit=5),
                          week=Week(number=12, days=tuple(WEEK)))


def option(name, team, value, positions=("SF",), status="", recent=None):
    return Option(Player(name, team, positions, status=status), value, recent_value=recent)


HOLDER = option("Old Streamer", "MIA", -0.5)
SPOTS = [StreamSpot(), StreamSpot(HOLDER)]
PHI, CHI = option("Phi & One", "PHI", 0.31), option("Chi One", "CHI", -0.40, ("PF",), "Q")
# PHI plays Mon, Tue and Sat. CHI plays Sat and Sun. MIA plays Mon.
GAMES = {WEEK[0]: {"PHI", "MIA"}, WEEK[1]: {"PHI"}, WEEK[5]: {"PHI", "CHI"}, WEEK[6]: {"CHI"}}
# Row 1: the empty spot, PHI from Mon, then CHI on Sun. Row 2: the spot of Old Streamer, PHI from Tue.
ROW1 = SpotPlan(SPOTS[0], Plan(windows=(
    TeamWindow(0, "PHI", WEEK[0], WEEK[5], (WEEK[0], WEEK[1], WEEK[5]), PHI, (PHI,)),
    TeamWindow(0, "CHI", WEEK[6], WEEK[6], (WEEK[6],), CHI, (CHI,))), started_games=4, adds=2), 4)
ROW2 = SpotPlan(SPOTS[1], Plan(windows=(
    TeamWindow(0, "MIA", None, WEEK[0], (WEEK[0],), HOLDER, ()),
    TeamWindow(0, "PHI", WEEK[1], WEEK[6], (WEEK[1], WEEK[5]), PHI, (PHI,))), started_games=3, adds=1), 2)
RANKING = [TeamRank("PHI", (WEEK[0], WEEK[1], WEEK[5]), 6), TeamRank("DAL", (WEEK[3],), 2)]
OPTIONS = [PHI, CHI, option("Hurt FA", "PHI", 2.0, status="O"), option("Star", "PHI", 2.5, ("C",), recent=2.0),
           option("No Value", "PHI", None)]


def render(**kw):
    return page.render(DATA, DAYS, GAMES, SPOTS, [ROW1, ROW2], OPTIONS, RANKING, ["PHI"], WEEK[0],
                       replacement=0.5, **kw)


def text(html):
    """The visible text of a page, with single spaces. The script and its data are not visible."""
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    parts = []
    parser = HTMLParser()
    parser.handle_data = parts.append
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parts))


def plan_rows(html):
    return re.findall(r"<tr><th>\d</th>(.*?)</tr>", html)


def test_each_row_shows_the_started_games_of_each_day_and_the_add_days():
    rows = plan_rows(render())
    cells = [re.findall(r"<td(?: class=\"on\")?>(?:<b>)?(\d|·|<i>\+</i>)(<i>\+</i>)?", row)[:7] for row in rows]
    assert cells[0] == [("1", "<i>+</i>"), ("1", ""), ("·", ""), ("·", ""), ("·", ""), ("1", ""), ("1", "<i>+</i>")]
    assert cells[1] == [("·", ""), ("1", "<i>+</i>"), ("·", ""), ("·", ""), ("·", ""), ("1", ""), ("·", "")]


def test_each_row_shows_its_adds_its_gain_and_its_moves():
    html = render()
    rows = plan_rows(html)
    assert re.findall(r'<td class="total">([^<]*)</td>', rows[0]) == ["2", "+4"]
    assert re.findall(r'<td class="total">([^<]*)</td>', rows[1]) == ["1", "+2"]
    shown = text(html)
    assert "+Phi &amp; One" in html and "Phi & One" not in html.split("<script")[0]
    assert "+Phi & One (PHI) – Mon, Tue & Sat +Chi One Q (CHI) – Sun" in shown
    assert "+Phi & One (PHI) – Tue & Sat drop Old Streamer" in shown
    assert "An add for today helps only if his game has not started." in shown


def test_the_page_shows_the_week_and_the_open_slots():
    shown = text(render())
    assert "Week 12: Mon 1/4 to Sun 1/10" in shown and "4 of 5 adds left" in shown and "2 stream spots" in shown
    assert "Out (does not play): Hurt Guy (O)" in shown
    assert re.search(r'<tr class="open"><th>Open</th>(<td[^>]*>2</td><td[^>]*>2</td><td[^>]*>0</td>)', render())


def test_the_free_agent_data_has_market_values_and_the_days_of_each_player():
    data = page.free_agent_data(OPTIONS, DAYS, GAMES, replacement=0.5)
    names = [p["name"] for p in data["players"]]
    # Best value first. An Out player and a player with no value are not in the table.
    assert names == ["Star", "Phi & One", "Chi One"]
    star = data["players"][0]
    assert (star["value"], star["recent"]) == (2.0, 1.5)
    # Chi One plays Sat and Sun. Sat has open PG and Util slots (Util takes all positions), Sun has none.
    chi = data["players"][2]
    assert chi["plays"] == [False, False, False, False, False, True, True]
    assert chi["fits"] == [False, False, False, False, False, True, False]
    assert [d["open"] for d in data["days"]] == [2, 2, 0, 2, 0, 2, 0]
    assert data["rows"] == 10 and data["flag"] == page.FLAG


def test_the_page_holds_the_free_agent_data_as_safe_json():
    html = render()
    raw = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    assert json.loads(raw)["players"][1]["name"] == "Phi & One"
    evil = page.render(DATA, DAYS, GAMES, SPOTS, [], [option("</script><b>", "PHI", 1.0)], today=WEEK[0])
    assert "</script><b>" not in evil and "http" not in evil


def test_the_page_explains_why_there_is_no_plan():
    assert "No adds left this week (5 of 5 used)" in text(page.render(
        command.LeagueData([], Adds(5, 5), DATA.week), DAYS, GAMES, SPOTS, [], today=WEEK[0]))
    assert "No stream spots" in text(page.render(DATA, DAYS, GAMES, [], [], today=WEEK[0]))
    assert "No free agent that the planner read" in text(page.render(DATA, DAYS, GAMES, SPOTS, [], today=WEEK[0]))
    # No options: no free-agent table and no script.
    assert "<script" not in page.render(DATA, DAYS, GAMES, SPOTS, [], today=WEEK[0])


CLAIM = Option(Player("Claim Guy", "CHI", ("C",), clear_day=WEEK[1]), 1.2)


def test_the_page_lists_the_waiver_players_with_the_clear_day():
    html = page.render(DATA, DAYS, GAMES, SPOTS, [ROW1, ROW2], OPTIONS + [CLAIM], RANKING, ["PHI"], WEEK[0],
                       replacement=0.5)
    shown = text(html)
    assert "Waiver players" in shown
    assert "Claim Guy W CHI C Tue 1/5 Wed 1/6 +0.70" in shown
    # The free-agent table holds only the players with status FA.
    raw = re.search(r'<script type="application/json" id="fa-data">(.*?)</script>', html, re.S).group(1)
    assert "Claim Guy" not in [p["name"] for p in json.loads(raw)["players"]]


def test_the_page_has_no_waiver_section_with_no_waiver_players():
    assert "Waiver players" not in text(render())


def test_a_move_marks_a_waiver_claim():
    row = SpotPlan(SPOTS[0], Plan(windows=(TeamWindow(0, "CHI", WEEK[2], WEEK[6], (WEEK[5], WEEK[6]), CLAIM,
                                                      (CLAIM,)),), started_games=2, adds=1), 2)
    shown = text(page.render(DATA, DAYS, GAMES, SPOTS, [row], [CLAIM], today=WEEK[0]))
    assert "+Claim Guy W (CHI) – Sat & Sun" in shown
    assert "W: a waiver claim. It is not sure" in shown


def test_the_command_prints_the_waiver_players_and_uses_one_after_his_clear_day(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue. The waiver player clears on Mon, so the plan adds him on Tue.
    claim = Option(Player("Phi Claim", "PHI", ("SF",), clear_day=WEEK[0]), 0.3)
    run_command(monkeypatch, tmp_path, [], publish=False, options=[claim])
    out = capsys.readouterr().out
    assert "Waiver players (a claim is not sure, and it uses an add):" in out
    assert "Phi Claim (PHI) SF  clears Mon 01/04, first plan day Tue 01/05" in out
    assert "Spot 1: PHI Tue 01/05 to Tue 01/05" in out
    assert "1. Phi Claim W (waiver claim, not sure)" in out
    assert command.free_agent_path(None, 25, status="W").startswith("players?status=W&")


def test_the_command_writes_the_page_and_publishes_it(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=True)
    path = tmp_path / "adds_plan.html"
    assert published == [(command.ROOT, "adds", path)]
    out = capsys.readouterr().out
    assert f"Wrote the plan page: {path}" in out
    assert "Plan page: best plan for one roster spot: +2 started games with 1 add." in out
    assert command.URL in out and command.URL.endswith("/adds/")
    assert "+Phi One (PHI) – Mon & Tue" in text(path.read_text(encoding="utf-8"))
    assert "Aggressive plan: the same as the schedule plan." in out


def test_the_command_prints_the_comparison_and_shows_the_plans_for_one_roster_spot(monkeypatch, tmp_path, capsys):
    # PHI plays Mon and Tue, BOS plays Mon. The schedule plan takes 2 games of the weak PHI player. The aggressive
    # plan takes 1 game of the better BOS player: 9 above an empty slot (-10) is more than 2 x 4.
    options = [option("Phi Weak", "PHI", -6.0), option("Bos Good", "BOS", -1.0)]
    run_command(monkeypatch, tmp_path, [], publish=False, options=options)
    out = capsys.readouterr().out
    assert "Schedule plan: 2 started games with 1 add" in out
    assert "Aggressive plan: 1 started game with 1 add" in out
    lines = [line.split() for line in out[out.index("Comparison:"):].splitlines()[1:6]]
    assert lines == [["Schedule", "Aggressive"], ["Adds", "1", "1"], ["Started", "games", "2", "1"],
                     ["Blended", "value", "-12.00", "-1.00"], ["Value", "above", "an", "empty", "slot", "+8.00", "+9.00"]]
    # Each row of the page has different players: the PHI player first (2 games), then the BOS player (1 game).
    shown = text((tmp_path / "adds_plan.html").read_text(encoding="utf-8"))
    assert "Comparison" not in shown and "Aggressive" not in shown
    assert "+Phi Weak (PHI) – Mon & Tue" in shown and "+Bos Good (BOS) – Mon" in shown
    assert "  1. +2 started games with 1 add" in out and "  2. +1 started games with 1 add" in out


def test_the_command_does_not_publish_with_no_publish(monkeypatch, tmp_path, capsys):
    published = []
    run_command(monkeypatch, tmp_path, published, publish=False)
    assert published == []
    assert (tmp_path / "adds_plan.html").exists()
    assert "did not publish" in capsys.readouterr().out


def run_command(monkeypatch, tmp_path, published, publish, options=None):
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
    monkeypatch.setattr(command, "season_values", lambda cfg: {})
    monkeypatch.setattr(command, "stream_spots", lambda roster, cfg, values=None: [StreamSpot()])
    monkeypatch.setattr(command, "read_team_free_agents", lambda yahoo, teams, view=None: [])
    monkeypatch.setattr(command, "read_market_free_agents", lambda yahoo, view=None: [])
    monkeypatch.setattr(command, "read_waiver_list", lambda yahoo, today, view=None: [])
    monkeypatch.setattr(command, "read_week_trends", lambda yahoo, days: {})
    options = options or [option("Phi One", "PHI", 0.3)]
    monkeypatch.setattr(command, "value_options", lambda fas, cfg, recent=(): options)
    monkeypatch.setattr(command, "empty_slot_value", lambda cfg: -10.0)
    monkeypatch.setattr(page, "PAGE", tmp_path / "adds_plan.html")
    monkeypatch.setattr(command.site, "publish", lambda *args: published.append(args))
    command.main(today=WEEK[0], publish=publish)
