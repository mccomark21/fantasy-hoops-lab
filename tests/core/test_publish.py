import re
import subprocess

import pytest

from fantasyhoops.core import home
from fantasyhoops.core import publish as site
from fantasyhoops.core import tokens
from fantasyhoops.core.common import load_config
from fantasyhoops.core.publish import BRANCH, MENU_SCRIPT, MENU_STYLE, publish, shell, site_head, site_menu, write_page

CFG = load_config()  # the Home page (core/home.py) takes its league facts from config.toml
HOME_MAIN = '<main class="lab-main hm">'  # the main element of the Home page (core/home.py)


def page(repo, name, text):
    path = repo / "output" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def git(repo, *args, data=None):
    """Bytes in and out: text mode on Windows writes CRLF to stdin, and mktree then reads "index.html\r"."""
    data = data.encode() if data is not None else None
    return subprocess.run(["git", *args], cwd=repo, input=data, check=True, capture_output=True).stdout.decode().strip()


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
    icons = set(site.ICON_FILES)
    assert (
        set(pages) == {".nojekyll", "index.html", "adds/index.html", font, f"adds/{font}", ofl, f"adds/{ofl}"} | icons
    )
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
    with pytest.raises(ValueError, match="The tools are: roster, adds, free-agents, trade."):
        publish(repo, tool, page(repo, f"{tool}/x.html", ""), cfg=CFG)


def test_publish_does_not_change_the_pages(repo, remote_pages):
    text = "<html><body class='x'><p>plan</p></body></html>"
    publish(
        repo, "adds", page(repo, "adds/plan.html", text), [page(repo, "adds/notes.html", "<body>n</body>")], cfg=CFG
    )
    pages = remote_pages(repo)
    assert pages["adds/index.html"] == text and pages["adds/notes.html"] == "<body>n</body>"


def test_the_menu_has_home_roster_adds_plan_free_agents_and_trades_only():
    home, adds = site_menu("home", 14), site_menu("adds", 14)
    labels = ["Home", "Roster", "Adds plan", "Free agents", "Trades"]
    assert re.findall(r"<li><a[^>]*>([^<]*)</a></li>", home) == labels
    assert re.findall(r"<li><a[^>]*>([^<]*)</a></li>", adds) == labels
    assert '<a href="free-agents/">Free agents</a>' in home and '<a href="../free-agents/">Free agents</a>' in adds
    free = site_menu("free-agents", 14)
    assert '<a href="../free-agents/" aria-current="page">Free agents</a>' in free
    assert '<a href="trade/">Trades</a>' in home and '<a href="../trade/">Trades</a>' in adds
    trade = site_menu("trade", 14)
    assert '<a href="../trade/" aria-current="page">Trades</a>' in trade and '<a href="../roster/">Roster</a>' in trade
    assert '<a href="./" aria-current="page">Home</a>' in home and '<a href="adds/">Adds plan</a>' in home
    assert '<a href="roster/">Roster</a>' in home and '<a href="../">Home</a>' in adds
    assert '<a href="../roster/">Roster</a>' in adds and '<a href="../adds/" aria-current="page">Adds plan</a>' in adds
    roster = site_menu("roster", 14)
    assert '<a href="../roster/" aria-current="page">Roster</a>' in roster and '<a href="../">Home</a>' in roster
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
    """#117: core/tokens.py is the one source of the colors. The menu uses only var(--...)."""
    for text in (site_menu("home", 14), MENU_STYLE, MENU_SCRIPT):
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", text)


def test_publish_puts_the_home_page_at_the_root(repo, remote_pages):
    """#172: each publish writes the Home page of core/home.py at the root."""
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert HOME_MAIN in pages["index.html"]
    assert pages["adds/index.html"] == "<p>plan</p>"
    rendered = repo / "home.html"
    rendered.write_bytes(home.render(CFG).encode())  # the same bytes as the page of the publish
    assert git(repo, "rev-parse", "FETCH_HEAD:index.html") == git(repo, "hash-object", "--no-filters", str(rendered))


def test_the_menu_takes_the_team_count_from_the_caller_and_reads_no_config():
    """#132: site_menu() gets the team count from its caller. core/publish.py has no load_config()."""
    assert not hasattr(site, "load_config")
    assert "2026–27 · 9-team league" in site_menu("home", 9)
    assert "2026–27 · 12-team league" in shell("__MENU__", "adds", {"league": {"teams": 12}})


def test_the_shell_fills_the_head_the_menu_and_the_menu_script():
    template = "<head>__HEAD__</head><body>__MENU__<main>__X__</main>__SCRIPT__</body>"
    head, menu = f"{site_head()}\n{site.page_meta('adds', 'Fantasy Hoops Lab')}", site_menu("adds", 14)
    assert shell(template, "adds", CFG) == f"<head>{head}</head><body>{menu}<main>__X__</main>{MENU_SCRIPT}</body>"


def test_write_page_writes_the_page_and_the_font_next_to_it(tmp_path):
    path = write_page(tmp_path / "tool" / "index.html", "<p>page</p>")
    assert path == tmp_path / "tool" / "index.html" and path.read_text(encoding="utf-8") == "<p>page</p>"
    fonts = path.parent / "fonts"
    assert (fonts / tokens.FONT.name).read_bytes() == tokens.FONT.read_bytes()
    assert (fonts / tokens.LICENSE.name).read_bytes() == tokens.LICENSE.read_bytes()


def test_a_trade_publish_writes_the_home_page_and_keeps_the_other_folders(repo, remote_pages):
    """#172: the trade run makes no Roster page. Its publish keeps /roster/ and writes the Home page."""
    push_old_site(
        repo, {"index.html": "<p>old</p>", "roster/index.html": "<p>roster</p>", "adds/index.html": "<p>plan</p>"}
    )
    publish(repo, "trade", page(repo, "trade/index.html", "<p>trades</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert HOME_MAIN in pages["index.html"] and pages["roster/index.html"] == "<p>roster</p>"
    assert pages["trade/index.html"] == "<p>trades</p>" and pages["adds/index.html"] == "<p>plan</p>"
    assert ".nojekyll" in pages and tokens.FONT_HREF in pages


# The pages of the site after each publish of #172: the Home page and the folder of each tool.
ALL_PAGES = {"index.html", "roster/index.html", "adds/index.html", "free-agents/index.html", "trade/index.html"}


def planning_publish(repo):
    """The publish of a planning run: /adds/, /free-agents/ and /roster/ (#165, #172)."""
    free = page(repo, "adds/free_agents.html", "<p>free agents</p>")
    roster = page(repo, "roster/index.html", "<p>roster</p>")
    plan = page(repo, "adds/plan.html", "<p>plan</p>")
    publish(repo, "adds", plan, cfg=CFG, more_tools={"free-agents": free, "roster": roster})


def test_a_planning_run_publish_writes_its_folders_and_keeps_the_trade_folder(repo, remote_pages):
    """#151, #165, #172: trade is in TOOLS, so the planning run publish keeps /trade/."""
    publish(repo, "trade", page(repo, "trade/index.html", "<p>trades</p>"), cfg=CFG)
    planning_publish(repo)
    pages = remote_pages(repo)
    assert ALL_PAGES | set(site.ICON_FILES) <= set(pages)
    assert HOME_MAIN in pages["index.html"] and pages["adds/index.html"] == "<p>plan</p>"
    assert pages["free-agents/index.html"] == "<p>free agents</p>" and pages["trade/index.html"] == "<p>trades</p>"
    assert pages["roster/index.html"] == "<p>roster</p>"
    for folder in ("free-agents", "roster"):
        assert f"{folder}/{tokens.FONT_HREF}" in pages and f"{folder}/fonts/OFL.txt" in pages


def test_a_trade_publish_keeps_the_roster_the_adds_and_the_free_agents_folders(repo, remote_pages):
    """#165, #172: roster and free-agents are in TOOLS, so the trade publish keeps their folders."""
    planning_publish(repo)
    publish(repo, "trade", page(repo, "trade/index.html", "<p>trades</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert ALL_PAGES | set(site.ICON_FILES) <= set(pages)
    assert HOME_MAIN in pages["index.html"] and pages["adds/index.html"] == "<p>plan</p>"
    assert pages["free-agents/index.html"] == "<p>free agents</p>" and pages["trade/index.html"] == "<p>trades</p>"
    assert pages["roster/index.html"] == "<p>roster</p>"


def test_more_tools_must_be_tools_of_the_site(repo):
    plan = page(repo, "adds/plan.html", "<p>plan</p>")
    with pytest.raises(ValueError, match="not a tool of the site"):
        publish(repo, "adds", plan, cfg=CFG, more_tools={"draft": plan})
    with pytest.raises(FileNotFoundError):
        publish(repo, "adds", plan, cfg=CFG, more_tools={"free-agents": repo / "output" / "missing.html"})


def head_tags(text):
    """The <link> and <meta> tags in the <head> of a page: {rel or name or property: [href or content, ...]}."""
    head = text.split("</head>")[0]
    tags = {}
    for tag in re.findall(r"<(?:link|meta) [^>]*>", head):
        attrs = dict(re.findall(r'(\w[\w:-]*)="([^"]*)"', tag))
        key = attrs.get("rel") or attrs.get("name") or attrs.get("property")
        tags.setdefault(key, []).append(attrs.get("href") or attrs.get("content"))
    return tags


@pytest.mark.parametrize("current", ["home", *site.TOOLS])
def test_each_page_head_has_the_icon_links_and_the_preview_tags(current):
    """#166: the icon links are relative to the page, and og:url and og:image are absolute URLs."""
    tags = head_tags(shell("<head><title>A &amp; B</title>__HEAD__</head>", current, CFG))
    up = "" if current == "home" else "../"
    assert tags["icon"] == [f"{up}icon.svg", f"{up}icon-32.png"]
    assert tags["apple-touch-icon"] == [f"{up}apple-touch-icon.png"]
    assert tags["theme-color"] == [tokens.LIGHT["lab-blue"], tokens.DARK["lab-blue"]]
    assert tags["og:title"] == ["A &amp; B"] and tags["og:type"] == ["website"]
    description = site.HOME_DESCRIPTION if current == "home" else site.TOOLS[current][1]
    assert tags["og:description"] == [description] and tags["description"] == [description]
    assert tags["og:url"] == [site.URL if current == "home" else f"{site.URL}{current}/"]
    assert tags["og:image"] == ["https://mccomark21.github.io/fantasy-hoops-lab/card.png"]
    assert tags["twitter:card"] == ["summary_large_image"]


def test_a_page_with_no_title_gets_the_site_name_as_og_title():
    assert head_tags(shell("<head>__HEAD__</head>", "home", CFG))["og:title"] == ["Fantasy Hoops Lab"]


def test_publish_puts_the_icons_and_the_share_card_at_the_root(repo, remote_pages):
    publish(repo, "trade", page(repo, "trade/index.html", "<p>trades</p>"), cfg=CFG)
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"), cfg=CFG)
    pages = remote_pages(repo)
    assert "trade/index.html" in pages and set(site.ICON_FILES) <= set(pages)
    for name, source in site.ICON_FILES.items():
        assert git(repo, "rev-parse", f"FETCH_HEAD:{name}") == git(repo, "hash-object", str(source))
    assert pages["icon.svg"].startswith("<svg") and site.CARD in site.ICON_FILES
