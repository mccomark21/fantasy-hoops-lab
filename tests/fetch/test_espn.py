from fantasyhoops.fetch.espn import parse_season_stats, stats_url

CATEGORIES = [
    {"name": "general", "names": ["gamesPlayed", "avgMinutes", "avgRebounds"]},
    {"name": "offensive", "names": ["avgPoints", "avgAssists", "avgThreePointFieldGoalsMade"]},
    {"name": "defensive", "names": ["avgSteals", "avgBlocks"]},
]


def athlete(name, team, general, offensive, defensive):
    return {
        "athlete": {"displayName": name, "teamShortName": team},
        "categories": [
            {"name": "general", "values": general},
            {"name": "offensive", "values": offensive},
            {"name": "defensive", "values": defensive},
        ],
    }


def test_the_stats_come_from_the_names_of_each_category():
    answer = {
        "categories": CATEGORIES,
        "athletes": [
            athlete("Cooper Flagg", "DAL", [3.0, 30.0, 5.33], [25.0, 6.33, 1.67], [3.67, 1.67]),
            athlete("Derrick White Jr.", "BOS", [4.0, 30.2, 4.0], [12.5, 6.2, 1.8], [1.2, 0.2]),
        ],
    }
    stats = parse_season_stats(answer)
    assert stats["cooper flagg"] == {
        "team": "DAL",
        "gp": 3,
        "min": 30.0,
        "pts": 25.0,
        "reb": 5.33,
        "ast": 6.33,
        "threes": 1.67,
        "stl": 3.67,
        "blk": 1.67,
    }
    assert stats["derrick white"]["gp"] == 4


def test_one_request_gets_all_players_of_the_regular_season():
    url = stats_url(2027)
    assert "statistics/byathlete" in url and "season=2027" in url and "seasontype=2" in url and "limit=1000" in url
