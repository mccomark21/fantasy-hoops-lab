from datetime import date
from types import SimpleNamespace

from fantasyhoops.adds import home as adds_home
from fantasyhoops.adds import page, timing
from fantasyhoops.adds import plan as command
from fantasyhoops.adds.readers import Player
from tests.adds.test_plan import run_command


def test_the_roster_players_get_the_rank_the_rest_flag_and_the_stats_by_name():
    roster = [
        Player("Coby White", "CHA", ("PG", "SG"), "IL", "O", "Out"),
        Player("Derrick White Jr.", "BOS", ("PG", "SG"), "PG"),
    ]
    players = adds_home.roster_players(
        roster, {"coby white": 77}, {"coby white": 1}, {"derrick white": {"gp": 4, "pts": 12.5}}
    )
    assert [(p.name, p.rank, p.rests_b2b, p.on_il, p.stats) for p in players] == [
        ("Coby White", 77, True, True, None),
        ("Derrick White Jr.", None, False, False, {"gp": 4, "pts": 12.5}),
    ]
    assert players[0].status == "O" and players[0].positions == ("PG", "SG")


def test_a_failed_home_page_prints_the_error_and_gives_none(monkeypatch, capsys):
    def fail(cfg, sched):
        raise RuntimeError("no rankings")

    monkeypatch.setattr(adds_home, "read_ranks", fail)
    assert adds_home.build_home(SimpleNamespace(roster=[]), {}, None, date(2026, 10, 28)) is None
    captured = capsys.readouterr()
    assert "The run did not make the home page." in captured.out
    assert "RuntimeError: no rankings" in captured.err


def test_the_home_page_gets_the_record_of_the_team_page(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(adds_home, "read_ranks", lambda cfg, sched: {})
    monkeypatch.setattr(adds_home, "read_risk", lambda roster, cfg: {})
    monkeypatch.setattr(adds_home, "season_stats", lambda season: {})
    monkeypatch.setattr(adds_home.home, "playoff_days", lambda sched, cfg: [])
    monkeypatch.setattr(adds_home.home, "render", lambda *args, **kw: seen.update(kw) or "page")
    monkeypatch.setattr(adds_home.home, "write", lambda text: tmp_path / "index.html")
    data = SimpleNamespace(roster=[], week=SimpleNamespace(number=2), adds=SimpleNamespace(used=1, limit=5))
    cfg = {"league": {"espn_season": 2027}, "adds": {"team_name": "TradeMark™"}}
    assert adds_home.build_home(SimpleNamespace(**vars(data), record="4-2-1"), cfg, None, date(2026, 10, 28))
    assert seen["record"] == "4-2-1" and seen["team_name"] == "TradeMark™"


def test_the_run_builds_the_home_page_and_publishes_it_with_the_plan_page(monkeypatch, tmp_path):
    published, calls = [], []
    home_page = tmp_path / "home" / "index.html"

    def build(data, cfg, sched, today):
        calls.append((data.week.number, today))
        return home_page

    run_command(monkeypatch, tmp_path, published, publish=True, home=build)
    assert calls == [(12, date(2027, 1, 4))]
    assert published == [(command.ROOT, "adds", page.page_path(), home_page, {"free-agents": page.free_agents_path()})]
    rows = timing.timings_path().read_text(encoding="utf-8")
    assert "home page" in rows


def test_no_publish_also_skips_the_home_page(monkeypatch, tmp_path):
    calls = []
    run_command(monkeypatch, tmp_path, [], publish=False, home=lambda *args: calls.append(args))
    assert calls == []
