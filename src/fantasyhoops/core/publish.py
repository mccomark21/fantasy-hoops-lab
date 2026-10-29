"""Publish the Fantasy Hoops Lab site to GitHub Pages on the gh-pages branch, and make the shell of each site page.

The site has a home page at /, the folder /adds/ for the adds plan and the folder /trade/ for the trades (#151).
The home page is the roster page of core/home.py (#120). Without it, the home page is a list of the tools.
A publish of one tool replaces its own folder and the home page. It keeps the folders of the other tools in TOOLS.
A publish with keep_home=True keeps the home page that is on gh-pages. The trade run uses it (#151).
A folder on gh-pages with a name that is not in TOOLS goes away at the next publish.
The root and the tool folder get the font file and its license (OFL.txt) in fonts/ (core/tokens.py).
The site menu (#117): a royal-blue side panel on a desktop, and a top bar with a drawer on a phone.
It has a link to each page of the site and the Auto, Light and Dark theme switch.
The page shell (#132): shell() puts site_head() in the <head> of a page, site_menu() first in its <body> and
MENU_SCRIPT last in its <body>. The plan page, the home page and the tool list (home_page()) use shell().
The shared tables (#143): shell() puts TABLE_STYLE in place of __TABLE_CSS__ in a page template. A table with the
class lab-t gets the look of the Roster table: the head, the rows, the team band and the player cell. The Roster
table of the home page and the Free agents and Waiver players tables of the adds page use it. band_style() gives the
team colors of a band.
write_page() writes a page and the font next to it. The plan page and the home page use it.
site_menu() and publish() get the config from the caller. The module does not read config.toml.
"""

import html
import subprocess

from fantasyhoops.core import tokens

BRANCH = "gh-pages"
URL = "https://mccomark21.github.io/fantasy-hoops-lab/"
HOME_LABEL = "Roster"  # the label of the home page in the site menu
# One line on the home page and one item in the site menu for each tool, in the order of the page.
TOOLS = {
    "adds": ("Adds plan", "How to use the 5 adds of the current fantasy week."),
    "trade": ("Trades", "Trades that raise your playoff starts and keep your season value."),
}


def git(repo, *args, data=b""):
    return subprocess.run(["git", *args], cwd=repo, input=data, check=True, capture_output=True).stdout.decode().strip()


def write_blob(repo, data):
    return git(repo, "hash-object", "-w", "--stdin", "--no-filters", data=data)


def make_tree(repo, entries):
    """entries: {name: (mode, type, sha)}. mktree needs the entries in name order."""
    return git(
        repo,
        "mktree",
        data="".join(f"{mode} {kind} {sha}\t{name}\n" for name, (mode, kind, sha) in sorted(entries.items())).encode(),
    )


def published_site(repo):
    """The entries at the root of gh-pages in origin, as {name: (mode, type, sha)}. Empty if the branch does not exist."""
    try:
        git(repo, "fetch", "origin", BRANCH)
    except subprocess.CalledProcessError:
        return {}
    entries = {}
    for line in git(repo, "ls-tree", "FETCH_HEAD").splitlines():
        info, name = line.split("\t")
        mode, kind, sha = info.split()
        entries[name] = (mode, kind, sha)
    return entries


def published_folders(site):
    """The tool folders of the root entries of gh-pages (published_site()): the trees with a name in TOOLS."""
    return {name: e for name, e in site.items() if e[1] == "tree" and name in TOOLS}


def font_folder(repo):
    """The fonts/ folder of the site, as a tree entry (mode, type, sha): the font and its license (OFL.txt)."""
    files = {f.name: ("100644", "blob", write_blob(repo, f.read_bytes())) for f in (tokens.FONT, tokens.LICENSE)}
    return ("040000", "tree", make_tree(repo, files))


def site_head():
    """The shared part of each <head>: the theme script, the font and the tokens, then the menu style."""
    return f"{tokens.HEAD}\n<style>\n{MENU_STYLE}\n</style>"


def site_menu(current, teams):
    """The site menu, first in the <body> of a page. current: "home" or the name of a tool in TOOLS.

    teams: the number of teams in the league ([league] teams of config.toml).

    The home page is at the root of the site and each tool page is in its own folder, so the links are relative.
    """
    up = "" if current == "home" else "../"
    root = up or "./"
    items = [("home", root, HOME_LABEL)] + [(t, f"{up}{t}/", label) for t, (label, _) in TOOLS.items()]
    here = ' aria-current="page"'
    links = "\n".join(
        f'<li><a href="{href}"{here if name == current else ""}>{html.escape(label)}</a></li>'
        for name, href, label in items
    )
    return MENU.replace("__ROOT__", root).replace("__TEAMS__", str(teams)).replace("__LINKS__", links)


def band_style(team):
    """The style attribute of a team band: the team color (core/tokens.py) and the text color on it.

    A team with no color in tokens.TEAM_COLORS gets lab-blue with lab-on-blue text.
    """
    color = tokens.TEAM_COLORS.get(team)
    if color is None:
        return "--team:var(--lab-blue);--team-ink:var(--lab-on-blue)"
    return f"--team:{color};--team-ink:{tokens.team_ink(color)}"


def shell(template, current, cfg):
    """Fill the site shell of a page template: __HEAD__, __MENU__, __SCRIPT__ and __TABLE_CSS__ (TABLE_STYLE).

    current: the page in the site menu (site_menu()). cfg: the config. [league] teams gives the team count.
    """
    return (
        template.replace("__HEAD__", site_head())
        .replace("__TABLE_CSS__", TABLE_STYLE)
        .replace("__MENU__", site_menu(current, cfg["league"]["teams"]))
        .replace("__SCRIPT__", MENU_SCRIPT)
    )


def write_page(path, text):
    """Write the page text to path, and the font file and its license to fonts/ next to it. Return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    tokens.copy_font(path.parent)
    return path


def home_page(tools, cfg):
    """The home page: the site menu, then one line and one link for each tool on the site. cfg: the config."""
    items = "\n".join(
        f'<li><a href="{t}/">{html.escape(TOOLS[t][0])}</a><span>{html.escape(TOOLS[t][1])}</span></li>'
        for t in TOOLS
        if t in tools
    )
    return shell(HOME, "home", cfg).replace("__TOOLS__", items)


def publish(repo, tool, index, others=(), home=None, *, cfg, keep_home=False):
    """Push the pages of one tool to gh-pages in origin, in the folder /<tool>/. The working tree and the current branch do not change.

    index: the main page of the tool. It goes to /<tool>/index.html.
    others: more pages of the tool. Each one goes to /<tool>/ with its own file name.
    home: the home page for the root of the site (core/home.py). None: a list of the tools (home_page()).
    cfg: the config. home_page() uses [league] teams of it for the list of the tools.
    keep_home: True keeps the index.html at the root of gh-pages. Then home must be None. If gh-pages has no root
    index.html, the home page is the list of the tools. The trade run uses it, because it does not make the roster page.
    The folders of the other tools in TOOLS stay. The home page links to each tool folder on the site.
    Each page carries its own site menu (site_menu()). The publish does not change the pages.
    The branch holds one commit, so each run replaces the last one and the old pages do not stay in the repo.
    """
    if tool not in TOOLS:
        raise ValueError(f"{tool} is not a tool of the site. The tools are: {', '.join(TOOLS)}.")
    if not index.exists():
        raise FileNotFoundError(f"{index} does not exist.")
    if keep_home and home is not None:
        raise ValueError("Give home or keep_home=True, not both.")
    site = published_site(repo)
    folders = published_folders(site)
    fonts = font_folder(repo)
    pages = {"index.html": index.read_bytes(), **{o.name: o.read_bytes() for o in others}}
    entries = {n: ("100644", "blob", write_blob(repo, d)) for n, d in pages.items()}
    folders[tool] = ("040000", "tree", make_tree(repo, {**entries, "fonts": fonts}))
    root = {
        name: ("100644", "blob", write_blob(repo, data))
        for name, data in {
            ".nojekyll": b"",
            "index.html": home.read_bytes() if home else home_page(folders, cfg).encode(),
        }.items()
    }
    old_home = site.get("index.html")
    if keep_home and old_home and old_home[1] == "blob":
        root["index.html"] = old_home
    root["fonts"] = fonts
    commit = git(repo, "commit-tree", make_tree(repo, {**root, **folders}), "-m", f"Publish the {tool} pages")
    git(repo, "push", "--force", "origin", f"{commit}:refs/heads/{BRANCH}")


MENU = """<header class="lab-bar"><a class="lab-name" href="__ROOT__">Fantasy Hoops Lab</a>
<button class="lab-open" type="button" aria-controls="lab-menu" aria-expanded="false">Menu</button></header>
<nav class="lab-menu" id="lab-menu" aria-label="Site">
<button class="lab-close" type="button">Close</button>
<a class="lab-site" href="__ROOT__">Fantasy<br>Hoops Lab<small>2026–27 · Yahoo __TEAMS__-team</small></a>
<ul>
__LINKS__
</ul>
<div class="lab-theme" role="group" aria-labelledby="lab-theme-l">
<span id="lab-theme-l">Theme</span>
<div class="lab-seg"><button type="button" data-set="system" aria-pressed="true">Auto</button>\
<button type="button" data-set="light" aria-pressed="false">Light</button>\
<button type="button" data-set="dark" aria-pressed="false">Dark</button></div>
</div>
</nav>
<div class="lab-scrim" hidden></div>"""

MENU_STYLE = """/* Card Back: the site menu. A royal-blue side panel on a desktop, a top bar with a drawer on a phone. */
:root { --lab-menu-w: 216px; --z-menu: 30; --z-scrim: 20; --z-bar: 10; }
body.lab { margin: 0; background: var(--lab-stock); color: var(--lab-ink); }
body.lab-locked { overflow: hidden; }
.lab-menu {
  position: fixed; inset: 0 auto 0 0; width: var(--lab-menu-w); z-index: var(--z-menu);
  display: flex; flex-direction: column; background: var(--lab-blue); color: var(--lab-on-blue);
  font: 600 14px/1.3 var(--lab-face); padding: 22px 0 18px; overflow-y: auto;
}
.lab-site {
  display: block; color: inherit; text-decoration: none; padding: 0 20px 16px; margin: 0 0 10px;
  font-weight: 900; font-stretch: 68%; text-transform: uppercase; font-size: 24px; line-height: .95;
  border-bottom: 3px solid var(--lab-on-blue);
}
.lab-site small { display: block; margin-top: 7px; font-size: 12px; font-weight: 600; font-stretch: 100%;
  text-transform: none; line-height: 1.2; }
.lab-menu ul { list-style: none; margin: 0; padding: 0; }
.lab-menu li a {
  display: flex; align-items: center; gap: 10px; min-height: 40px; padding: 0 20px;
  color: inherit; text-decoration: none; font-size: 15px;
}
.lab-menu li a::before { content: ""; width: 9px; height: 9px; flex: none; }
.lab-menu li a:hover { background: var(--lab-blue-deep); }
.lab-menu li a[aria-current] { background: var(--lab-stock); color: var(--lab-ink); font-weight: 800; }
.lab-menu li a[aria-current]::before { background: var(--lab-red); }
.lab-menu a:focus-visible, .lab-open:focus-visible { outline: 2px solid var(--lab-on-blue); outline-offset: -4px; }
.lab-menu li a[aria-current]:focus-visible { outline-color: var(--lab-ink); }
.lab-bar, .lab-close { display: none; }
.lab-main { display: block; margin-left: var(--lab-menu-w); min-width: 0; }
@media (max-width: 899px) {
  .lab-bar {
    position: sticky; top: 0; z-index: var(--z-bar); display: flex; align-items: center;
    justify-content: space-between; min-height: 48px;
    padding: 0 max(16px, env(safe-area-inset-right)) 0 max(16px, env(safe-area-inset-left));
    background: var(--lab-blue); color: var(--lab-on-blue); font: 900 18px/1 var(--lab-face);
  }
  .lab-name { color: inherit; text-decoration: none; font-stretch: 68%; text-transform: uppercase; font-size: 20px; }
  .lab-name:focus-visible { outline: 2px solid var(--lab-on-blue); outline-offset: 2px; }
  .lab-open {
    min-height: 40px; padding: 0 14px; border: 2px solid var(--lab-on-blue); border-radius: 0; background: transparent;
    color: inherit; font: 800 14px/1 var(--lab-face); text-transform: uppercase; cursor: pointer;
  }
  .lab-menu { transform: translateX(-100%); visibility: hidden;
    transition: transform .28s cubic-bezier(.16, 1, .3, 1), visibility 0s .28s; }
  .lab-menu.open { transform: none; visibility: visible; transition: transform .28s cubic-bezier(.16, 1, .3, 1); }
  .lab-main { margin-left: 0; }
  .lab-close {
    display: block; align-self: flex-end; margin: -10px 12px 10px 0; min-height: 40px; padding: 0 14px;
    border: 2px solid var(--lab-on-blue); background: transparent; color: var(--lab-on-blue);
    font: 800 14px/1 var(--lab-face); text-transform: uppercase; cursor: pointer;
  }
  .lab-close:focus-visible { outline: 2px solid var(--lab-on-blue); outline-offset: 2px; }
  .lab-scrim { position: fixed; inset: 0; z-index: var(--z-scrim); background: var(--lab-scrim); }
}
.lab-scrim[hidden] { display: none; }
@media (prefers-reduced-motion: reduce) { .lab-menu, .lab-menu.open { transition: none; } }
.lab-theme { margin: auto 0 0; padding: 16px 20px 0; font-size: 12px; font-weight: 600; }
.lab-theme > span { display: block; margin-bottom: 6px; }
.lab-seg { display: flex; border: 2px solid var(--lab-on-blue); }
.lab-seg button {
  flex: 1; min-height: 36px; padding: 0 4px; border: 0; background: transparent; color: var(--lab-on-blue);
  font: 700 13px/1 var(--lab-face); cursor: pointer;
}
.lab-seg button + button { border-left: 2px solid var(--lab-on-blue); }
.lab-seg button:hover { background: var(--lab-blue-deep); }
.lab-seg button[aria-pressed="true"] { background: var(--lab-stock); color: var(--lab-ink); font-weight: 900; }
.lab-seg button:focus-visible { outline: 2px solid var(--lab-on-blue); outline-offset: 2px; position: relative;
  z-index: 1; }"""

TABLE_STYLE = """/* The shared tables (issue 143): the look of the Roster table, for each table with the class lab-t. Below 900px,
   the phone row of the Roster (.m-p) gets the same band, rank and name. The head and row rules use :where(), so that
   a class rule of a page wins over them. */
table.lab-t { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
:where(.lab-t) thead th, :where(.lab-t) thead td { font-size: 11px; font-weight: 800; color: var(--mark); text-align: right;
  padding: 0 6px 6px; vertical-align: bottom; border-bottom: 2px solid var(--mark); }
:where(.lab-t) thead .l { text-align: left; }
:where(.lab-t) tbody td, :where(.lab-t) tbody th { height: 46px; border-bottom: 1px solid var(--lab-rule); padding: 0 6px;
  text-align: right; vertical-align: middle; font-weight: 400; }
:where(.lab-t) tbody tr:nth-child(even) > * { background: var(--zebra); }
.lab-t .s1 { border-left: 1px solid var(--vrule); }
.lab-t td.band { padding: 0; text-align: center; background: var(--team) !important; color: var(--team-ink);
  font-weight: 900; font-stretch: 70%; font-size: 19px; border-bottom: 1px solid var(--lab-stock); }
.lab-t td.rk { color: var(--lab-red); font-weight: 900; font-stretch: 75%; font-size: 21px; padding-right: 8px; }
.lab-t th.pl { text-align: left; padding: 3px 6px 3px 10px; line-height: 1; }
.lab-t .pl b { font-weight: 900; font-stretch: 66%; font-size: 20px; text-transform: uppercase; line-height: 1; }
.lab-t .pl small { display: block; font-size: 12px; line-height: 1.2; color: var(--lab-mute); margin-top: 2px; }
.lab-t td.n { font-size: 14px; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .lab-t td.band, :root:not([data-theme="light"]) .m-p .band {
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lab-ink) 22%, transparent); }
}
:root[data-theme="dark"] .lab-t td.band, :root[data-theme="dark"] .m-p .band {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--lab-ink) 22%, transparent); }
/* Phone: the sizes of the phone row of the Roster. */
@media (max-width: 899px) {
  :where(.lab-t) tbody td, :where(.lab-t) tbody th { height: 52px; }
  .lab-t td.band { font-size: 17px; }
  .lab-t td.rk { font-size: 19px; }
  .lab-t .pl b { font-size: 18px; }
  .m-p .band { background: var(--team); color: var(--team-ink); font-weight: 900; font-stretch: 70%; font-size: 17px; }
  .m-p .rk { color: var(--lab-red); font-weight: 900; font-stretch: 75%; font-size: 19px; }
  .m-p .nm b { font-weight: 900; font-stretch: 66%; font-size: 18px; text-transform: uppercase; }
}"""

# The drawer on a phone, then the theme switch. The theme choice stays in localStorage (core/tokens.py).
MENU_SCRIPT = f"""<script>
(() => {{
  const btn = document.querySelector(".lab-open"), nav = document.getElementById("lab-menu");
  const scrim = document.querySelector(".lab-scrim");
  if (!btn || !nav) return;
  const behind = [...document.querySelectorAll(".lab-main, .lab-bar")];
  const set = open => {{
    nav.classList.toggle("open", open); btn.setAttribute("aria-expanded", open);
    document.body.classList.toggle("lab-locked", open);
    scrim.hidden = !open; behind.forEach(el => el.inert = open);
    if (open) nav.querySelector(".lab-close").focus();
  }};
  nav.querySelector(".lab-close").addEventListener("click", () => {{ set(false); btn.focus(); }});
  btn.addEventListener("click", () => set(!nav.classList.contains("open")));
  document.addEventListener("keydown", ev => {{
    if (ev.key === "Escape" && nav.classList.contains("open")) {{ set(false); btn.focus(); }}
  }});
  scrim.addEventListener("click", () => set(false));
}})();
(() => {{
  const root = document.documentElement, btns = [...document.querySelectorAll(".lab-seg button")];
  const show = () => {{
    const t = root.dataset.theme || "system";
    btns.forEach(b => b.setAttribute("aria-pressed", b.dataset.set === t));
  }};
  btns.forEach(b => b.addEventListener("click", () => {{
    const t = b.dataset.set;
    if (t === "system") delete root.dataset.theme; else root.dataset.theme = t;
    try {{
      if (t === "system") localStorage.removeItem("{tokens.THEME_KEY}"); else localStorage.setItem("{tokens.THEME_KEY}", t);
    }} catch (e) {{}}
    show();
  }}));
  show();
}})();
</script>"""

HOME = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fantasy Hoops Lab</title>
__HEAD__
<style>
.home { max-width: 640px; padding: 24px max(28px, env(safe-area-inset-right)) 32px max(28px, env(safe-area-inset-left));
        font: 400 15px/1.45 var(--lab-face); }
.home h1 { margin: 0; padding-bottom: 12px; border-bottom: 3px solid var(--mark); color: var(--mark);
           font-weight: 900; font-stretch: 66%; font-size: clamp(32px, 4vw, 44px); line-height: .9;
           text-transform: uppercase; text-wrap: balance; }
.home p { margin: 12px 0 20px; color: var(--lab-mute); }
.home ul { list-style: none; margin: 0; padding: 0; border-top: 2px solid var(--mark); }
.home li { padding: 12px 0; border-bottom: 1px solid var(--lab-rule); overflow-wrap: anywhere; }
.home a { display: block; color: var(--mark); font-weight: 900; font-stretch: 75%; font-size: 20px;
          text-transform: uppercase; text-underline-offset: 3px; }
.home a:focus-visible { outline: 2px solid var(--mark); outline-offset: 2px; }
.home span { color: var(--lab-mute); }
@media (max-width: 599px) { .home { padding-left: max(16px, env(safe-area-inset-left));
                                     padding-right: max(16px, env(safe-area-inset-right)); } }
</style>
</head>
<body class="lab">
__MENU__
<main class="lab-main home">
<h1>Fantasy Hoops Lab</h1>
<p>Analysis tools for one Yahoo fantasy basketball league, 2026-27 season.</p>
<ul>
__TOOLS__
</ul>
</main>
__SCRIPT__
</body>
</html>
"""
