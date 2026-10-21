from datetime import date

from fantasyhoops.adds.plan import print_plan
from fantasyhoops.adds.planner import Option, Plan, StreamSpot, TeamWindow
from fantasyhoops.adds.readers import Adds, Player

MON = date(2027, 1, 4)


def test_each_window_option_shows_its_games_next_week(capsys):
    first, second = Option(Player("First", "PHI", ("SF",)), 1.0), Option(Player("Second", "PHI", ("C",)), 0.5)
    window = TeamWindow(spot=0, team="PHI", add_day=MON, last_day=MON, started=(MON,), player=first,
                        options=(first, second))
    plan = Plan(windows=(window,), started_games=1, adds=1, value=1.0, next_games=2.0, next_value=2.0)
    print_plan(plan, [StreamSpot()], Adds(used=0, limit=5), MON, next_week={"PHI": 4})
    lines = capsys.readouterr().out.splitlines()
    assert "next week 4 games" in next(line for line in lines if "First" in line)
    assert "next week 4 games" in next(line for line in lines if "Second" in line)
    assert any("Next week: the last players in the stream spots have 4 games" in line for line in lines)
