from datetime import date

import pandas as pd

from fantasyhoops import draft
from fantasyhoops.adds import bench, page, timing
from fantasyhoops.adds import cache as page_cache
from fantasyhoops.core import common, home
from fantasyhoops.core.common import ROOT, name_key, weeks
from fantasyhoops.draft import auction
from fantasyhoops.draft.benchmark import CATS
from fantasyhoops.draft.category_data import load_benchmark


def test_weeks_returns_names_in_order():
    cfg = {"playoffs": {"weeks": [{"name": "wk19"}, {"name": "wk20"}, {"name": "wk21"}]}}
    assert weeks(cfg) == ["wk19", "wk20", "wk21"]


def test_name_key_removes_accents_and_case():
    assert name_key("Nikola Jokić") == "nikola jokic"


def test_name_key_removes_suffixes_and_punctuation():
    assert name_key("Jaren Jackson Jr.") == "jaren jackson"
    assert name_key("Gary Trent III") == "gary trent"
    assert name_key("De'Aaron Fox") == "deaaron fox"


def test_name_key_turns_hyphen_into_space():
    assert name_key("Shai Gilgeous-Alexander") == "shai gilgeous alexander"


def test_the_output_files_go_under_common_out_with_no_other_patch(tmp_path, capsys):
    # The autouse fixture of tests/conftest.py points common.OUT at tmp_path. This test patches no other path.
    assert common.OUT == tmp_path
    page.write("<p>plan</p>")
    home.write("<p>home</p>")
    timings = timing.Timings()
    with timings.step("schedule read"):
        pass
    timings.window([], 0)
    page_cache.PageCache(date(2027, 1, 4)).save(page_cache.DAY, "players?a", "<p>a</p>")
    bench.append(bench.bench_path(), [])
    auction.write_benchmark(pd.DataFrame([{f"bench_{c}": 1.0 for c in CATS}]))
    capsys.readouterr()
    assert (tmp_path / "adds" / "adds_plan.html").read_text(encoding="utf-8") == "<p>plan</p>"
    assert (tmp_path / "home" / "index.html").read_text(encoding="utf-8") == "<p>home</p>"
    assert "schedule read" in (tmp_path / "adds" / "timings.csv").read_text(encoding="utf-8")
    assert any((tmp_path / "adds" / "cache" / "day").rglob("*.json"))
    assert (tmp_path / "adds" / "bench.csv").exists()
    assert load_benchmark() == {c: 1.0 for c in CATS}  # it reads output/draft/category_benchmark.csv by default
    assert (tmp_path / "draft" / "category_benchmark.csv").exists()


def test_the_default_output_paths_do_not_change(monkeypatch):
    monkeypatch.setattr(common, "OUT", ROOT / "output")
    out = ROOT / "output"
    assert page.page_path() == out / "adds" / "adds_plan.html"
    assert timing.timings_path() == out / "adds" / "timings.csv"
    assert page_cache.cache_dir() == out / "adds" / "cache"
    assert page_cache.PageCache(date(2027, 1, 4)).folder == out / "adds" / "cache"
    assert bench.bench_path() == out / "adds" / "bench.csv"
    assert home.page_path() == out / "home" / "index.html"
    assert draft.out_dir() == out / "draft"
