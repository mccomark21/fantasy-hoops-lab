"""Publish the Fantasy Hoops Lab site to GitHub Pages on the gh-pages branch, and make the site menu.

The site has a home page at / and the folder /adds/ for the adds plan.
A publish of one tool replaces its own folder and the home page. It keeps the folders of the other tools in TOOLS.
A folder on gh-pages with a name that is not in TOOLS goes away at the next publish.
The root and the tool folder get the font file in fonts/ (core/tokens.py).
The site menu (#117): a royal-blue side panel on a desktop, and a top bar with a drawer on a phone.
It has a link to each page of the site and the Auto, Light and Dark theme switch.
Each page puts site_head() in its <head>, site_menu() first in its <body> and MENU_SCRIPT last in its <body>.
"""

import html
import subprocess

from fantasyhoops.core import tokens
from fantasyhoops.core.common import load_config

BRANCH = "gh-pages"
URL = "https://mccomark21.github.io/fantasy-hoops-lab/"
HOME_LABEL = "Roster"  # the label of the home page in the site menu
# One line on the home page and one item in the site menu for each tool, in the order of the page.
TOOLS = {
    "adds": ("Adds plan", "How to use the 5 adds of the current fantasy week."),
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


def published_folders(repo):
    """Tool folders on gh-pages in origin, as {name: (mode, type, sha)}. Empty if the branch does not exist."""
    try:
        git(repo, "fetch", "origin", BRANCH)
    except subprocess.CalledProcessError:
        return {}
    entries = {}
    for line in git(repo, "ls-tree", "FETCH_HEAD").splitlines():
        info, name = line.split("\t")
        mode, kind, sha = info.split()
        if kind == "tree" and name in TOOLS:
            entries[name] = (mode, kind, sha)
    return entries


def font_folder(repo):
    """The fonts/ folder of the site, as a tree entry (mode, type, sha)."""
    font = write_blob(repo, tokens.FONT.read_bytes())
    return ("040000", "tree", make_tree(repo, {tokens.FONT.name: ("100644", "blob", font)}))


def site_head():
    """The shared part of each <head>: the theme script, the font and the tokens, then the menu style."""
    return f"{tokens.HEAD}\n<style>\n{MENU_STYLE}\n</style>"


def site_menu(current):
    """The site menu, first in the <body> of a page. current: "home" or the name of a tool in TOOLS.

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
    teams = load_config()["league"]["teams"]
    return MENU.replace("__ROOT__", root).replace("__TEAMS__", str(teams)).replace("__LINKS__", links)


def home_page(tools):
    """The home page: the site menu, then one line and one link for each tool on the site."""
    items = "\n".join(
        f'<li><a href="{t}/">{html.escape(TOOLS[t][0])}</a><span>{html.escape(TOOLS[t][1])}</span></li>'
        for t in TOOLS
        if t in tools
    )
    return (
        HOME.replace("__HEAD__", site_head())
        .replace("__MENU__", site_menu("home"))
        .replace("__SCRIPT__", MENU_SCRIPT)
        .replace("__TOOLS__", items)
    )


def publish(repo, tool, index, others=()):
    """Push the pages of one tool to gh-pages in origin, in the folder /<tool>/. The working tree and the current branch do not change.

    index: the main page of the tool. It goes to /<tool>/index.html.
    others: more pages of the tool. Each one goes to /<tool>/ with its own file name.
    The folders of the other tools in TOOLS stay. The home page links to each tool folder on the site.
    Each page carries its own site menu (site_menu()). The publish does not change the pages.
    The branch holds one commit, so each run replaces the last one and the old pages do not stay in the repo.
    """
    if tool not in TOOLS:
        raise ValueError(f"{tool} is not a tool of the site. The tools are: {', '.join(TOOLS)}.")
    if not index.exists():
        raise FileNotFoundError(f"{index} does not exist.")
    folders = published_folders(repo)
    fonts = font_folder(repo)
    pages = {"index.html": index.read_bytes(), **{o.name: o.read_bytes() for o in others}}
    entries = {n: ("100644", "blob", write_blob(repo, d)) for n, d in pages.items()}
    folders[tool] = ("040000", "tree", make_tree(repo, {**entries, "fonts": fonts}))
    root = {
        name: ("100644", "blob", write_blob(repo, data))
        for name, data in {".nojekyll": b"", "index.html": home_page(folders).encode()}.items()
    }
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
