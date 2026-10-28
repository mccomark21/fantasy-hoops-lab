import re
import subprocess
from pathlib import Path

import pytest

from fantasyhoops.core import publish as site
from fantasyhoops.core import tokens
from fantasyhoops.core.publish import BRANCH, MENU_SCRIPT, home_page, publish, shell, site_head, site_menu, write_page

CFG = {"league": {"teams": 14}}
FIXTURES = Path(__file__).parent / "fixtures"


def page(repo, name, text):
    path = repo / "output" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def git(repo, *args, data=None):
    return subprocess.run(
        ["git", *args], cwd=repo, input=data, check=True, capture_output=True, text=True
    ).stdout.strip()


def push_old_site(repo, files):
    """Put a gh-pages commit in origin with files ({path: text}, one folder level at most), as an old publish did."""
    folders = {}
    for name, text in files.items():
        folder, _, leaf = name.rpartition("/")
        folders.setdefault(folder, {})[leaf] = git(repo, "hash-object", "-w", "--stdin", data=text)

    def tree(entries):
        return git(repo, "mktree", data="".join(f"{m} {k} {s}\t{n}\n" for n, (m, k, s) in sorted(entries.items())))

    root = {n: ("100644", "blob", s) for n, s in folders.pop("", {}).items()}
    for folder, blobs in folders.items():
        root[folder] = ("040000", "tree", tree({n: ("100644", "blob", s) for n, s in blobs.items()}))
    git(repo, "push", "origin", f"{git(repo, 'commit-tree', tree(root), '-m', 'old')}:refs/heads/{BRANCH}")


def test_publish_adds_writes_its_folder_the_home_page_and_the_font(repo, remote_pages):
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert pages["adds/index.html"] == "<p>plan</p>"
    font = tokens.FONT_HREF
    ofl = "fonts/OFL.txt"
    assert set(pages) == {".nojekyll", "index.html", "adds/index.html", font, f"adds/{font}", ofl, f"adds/{ofl}"}
    assert (
        "Copyright 2020 The Archivo Project Authors" in pages[ofl] and "SIL OPEN FONT LICENSE" in pages[f"adds/{ofl}"]
    )
    assert git(repo, "rev-parse", f"FETCH_HEAD:{font}") == git(repo, "hash-object", str(tokens.FONT))


def test_publish_replaces_only_its_own_folder(repo, remote_pages):
    publish(repo, "adds", page(repo, "adds/old.html", "<p>old</p>"), [page(repo, "adds/extra.html", "")], cfg=CFG)
    publish(repo, "adds", page(repo, "adds/new.html", "<p>new</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert "adds/extra.html" not in pages
    assert pages["adds/index.html"] == "<p>new</p>"


def test_draft_folder_goes_away_at_the_next_adds_publish(repo, remote_pages):
    """The owner took the draft board off the site on 2026-10-28 (#117)."""
    push_old_site(
        repo,
        {
            "index.html": "<p>old home</p>",
            "draft/index.html": "<p>board</p>",
            "draft/draft_board_wk20-wk22.html": "<p>wk20</p>",
            "adds/index.html": "<p>old plan</p>",
        },
    )
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert not [n for n in pages if n.startswith("draft/")]
    assert pages["adds/index.html"] == "<p>plan</p>"
    assert 'href="draft/"' not in pages["index.html"]


def test_old_board_at_the_root_goes_away(repo, remote_pages):
    """Before the site had tool folders, the board was index.html at the root of gh-pages."""
    push_old_site(repo, {"draft_board_wk20-wk22.html": "<p>old board</p>", "index.html": "<p>old board</p>"})
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert "draft_board_wk20-wk22.html" not in pages
    assert "Fantasy Hoops Lab" in pages["index.html"]


@pytest.mark.parametrize("tool", ["draft", "trades"])
def test_unknown_tool_stops_with_an_error(repo, tool):
    with pytest.raises(ValueError, match="The tools are: adds."):
        publish(repo, tool, page(repo, f"{tool}/x.html", ""), cfg=CFG)


def test_publish_does_not_change_the_pages(repo, remote_pages):
    text = "<html><body class='x'><p>plan</p></body></html>"
    publish(
        repo, "adds", page(repo, "adds/plan.html", text), [page(repo, "adds/notes.html", "<body>n</body>")], cfg=CFG
    )
    pages = remote_pages(repo)
    assert pages["adds/index.html"] == text and pages["adds/notes.html"] == "<body>n</body>"


def test_the_menu_has_roster_and_adds_plan_only():
    home, adds = site_menu("home", 14), site_menu("adds", 14)
    assert re.findall(r"<li><a[^>]*>([^<]*)</a></li>", home) == ["Roster", "Adds plan"]
    assert '<a href="./" aria-current="page">Roster</a>' in home and '<a href="adds/">Adds plan</a>' in home
    assert '<a href="../">Roster</a>' in adds and '<a href="../adds/" aria-current="page">Adds plan</a>' in adds
    assert "Draft board" not in home + adds and "Keeper report" not in home + adds


def test_the_menu_has_the_auto_light_and_dark_switch():
    menu = site_menu("adds", 14)
    assert re.findall(r'data-set="(\w+)" aria-pressed="\w+">(\w+)<', menu) == [
        ("system", "Auto"),
        ("light", "Light"),
        ("dark", "Dark"),
    ]
    assert 'aria-controls="lab-menu" aria-expanded="false">Menu</button>' in menu
    assert f'localStorage.setItem("{tokens.THEME_KEY}", t)' in MENU_SCRIPT and "catch (e)" in MENU_SCRIPT


def test_the_head_sets_the_saved_theme_before_the_tokens_and_loads_the_font():
    head = site_head()
    assert head.index(f'localStorage.getItem("{tokens.THEME_KEY}")') < head.index("<style>")
    assert f'<link rel="preload" href="{tokens.FONT_HREF}" as="font"' in head
    assert "font-family: Archivo" in head and f"url({tokens.FONT_HREF})" in head
    assert ':root[data-theme="dark"]' in head and ':root:not([data-theme="light"])' in head


def test_each_token_has_a_light_and_a_dark_value():
    assert set(tokens.LIGHT) == set(tokens.DARK)
    assert tokens.LIGHT["lab-blue"] == "#1d4f91" and tokens.DARK["lab-stock"] == "#0e1a2e"


def test_the_site_css_has_no_colors_outside_the_token_file():
    """#117: core/tokens.py is the one source of the colors. The menu and the home page use only var(--...)."""
    for text in (home_page({"adds"}, CFG).replace(tokens.HEAD, ""), site_menu("home", 14), MENU_SCRIPT):
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", text)


def test_home_page_shows_the_menu_and_links_to_each_tool_on_the_site():
    home = home_page({"adds"}, CFG)
    assert home.index('<body class="lab">') < home.index('<nav class="lab-menu"') < home.index('<main class="lab-main')
    assert '<a href="adds/">Adds plan</a>' in home
    assert home.rstrip().endswith("</script>\n</body>\n</html>")
    assert "<span>How to use" in home and "<span>How to use" not in home_page(set(), CFG)


def test_publish_puts_the_home_page_at_the_root(repo, remote_pages):
    """The roster page of core/home.py (#120) replaces the list of the tools."""
    home = page(repo, "home/index.html", "<p>roster</p>")
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"), home=home, cfg=CFG)
    pages = remote_pages(repo)
    assert pages["index.html"] == "<p>roster</p>"
    assert pages["adds/index.html"] == "<p>plan</p>"


def test_the_menu_takes_the_team_count_from_the_caller_and_reads_no_config():
    """#132: site_menu() gets the team count from its caller. core/publish.py has no load_config()."""
    assert not hasattr(site, "load_config")
    assert "2026–27 · Yahoo 9-team" in site_menu("home", 9)
    assert "2026–27 · Yahoo 12-team" in shell("__MENU__", "adds", {"league": {"teams": 12}})


def test_the_shell_fills_the_head_the_menu_and_the_menu_script():
    template = "<head>__HEAD__</head><body>__MENU__<main>__X__</main>__SCRIPT__</body>"
    head, menu = site_head(), site_menu("adds", 14)
    assert shell(template, "adds", CFG) == f"<head>{head}</head><body>{menu}<main>__X__</main>{MENU_SCRIPT}</body>"


def test_write_page_writes_the_page_and_the_font_next_to_it(tmp_path):
    path = write_page(tmp_path / "tool" / "index.html", "<p>page</p>")
    assert path == tmp_path / "tool" / "index.html" and path.read_text(encoding="utf-8") == "<p>page</p>"
    fonts = path.parent / "fonts"
    assert (fonts / tokens.FONT.name).read_bytes() == tokens.FONT.read_bytes()
    assert (fonts / tokens.LICENSE.name).read_bytes() == tokens.LICENSE.read_bytes()


def test_the_tool_list_is_the_html_before_the_page_shell():
    """#132: fixtures/tools_before_132.html is home_page({"adds"}) before shell(), with 14 teams in config.toml."""
    assert home_page({"adds"}, CFG) == (FIXTURES / "tools_before_132.html").read_text(encoding="utf-8")
