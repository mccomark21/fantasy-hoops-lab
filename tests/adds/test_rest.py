from datetime import date, timedelta

import pandas as pd

from fantasyhoops.adds.planner import Option, counted_games
from fantasyhoops.adds.readers import Player
from fantasyhoops.adds.rest import games_text, rest_names, second_nights, with_rests

MON = date(2027, 1, 4)
WEEK = [MON + timedelta(days=i) for i in range(7)]


def schedule(games):
    """A schedule with one row for each team in each game, from {day: teams}."""
    return pd.DataFrame([{"date": pd.Timestamp(d), "team": t} for d, teams in games.items() for t in teams])


def test_a_second_night_is_a_game_on_the_day_after_a_game_of_the_same_team():
    # PHI plays Sun (before the window), Mon and Tue. ATL plays Mon and Wed. The window is Mon to Wed.
    sched = schedule({MON - timedelta(days=1): ["PHI"], WEEK[0]: ["PHI", "ATL"], WEEK[1]: ["PHI"], WEEK[2]: ["ATL"]})
    assert second_nights(sched, WEEK[:3]) == {WEEK[0]: {"PHI"}, WEEK[1]: {"PHI"}, WEEK[2]: set()}


def test_rest_names_are_the_name_keys_of_the_players_with_rests_b2b():
    risk = pd.DataFrame({"name": ["LeBron James", "Nikola Jokić", "Kyrie Irving"], "rests_b2b": [1, 0, 1]})
    assert rest_names(risk) == {"lebron james", "kyrie irving"}


def test_a_player_on_the_rest_list_gets_a_lower_count_on_each_second_night():
    nights = {WEEK[0]: {"PHI"}, WEEK[1]: {"PHI", "ATL"}, WEEK[2]: set()}
    rester, other = Option(Player("LeBron James", "PHI", ("SF",)), 1.0), Option(Player("Joel", "PHI", ("C",)), 1.0)
    away = Option(Player("Kyrie Irving", "DAL", ("PG",)), 1.0)
    out = with_rests([rester, other, away], {"lebron james", "kyrie irving"}, nights, 0.5)
    assert out[0].rest_games == ((WEEK[0], 0.5), (WEEK[1], 0.5))
    assert [counted_games(out[0].rest_games, [d]) for d in WEEK[:3]] == [0.5, 0.5, 1.0]
    assert out[1] == other and out[2] == away  # not on the list, or no second night


def test_games_text_shows_a_fraction_only_when_there_is_one():
    assert [games_text(n) for n in (2, 2.0, 1.5, 1.75, 0.1 + 0.2)] == ["2", "2", "1.5", "1.75", "0.3"]
    assert [games_text(n, sign=True) for n in (2, 0, -1.5)] == ["+2", "+0", "-1.5"]


def test_a_rest_chance_of_0_changes_nothing():
    rester = Option(Player("LeBron James", "PHI", ("SF",)), 1.0)
    assert with_rests([rester], {"lebron james"}, {WEEK[0]: {"PHI"}}, 0.0) == [rester]
