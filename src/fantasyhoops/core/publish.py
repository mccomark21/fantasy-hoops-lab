"""Publish the Fantasy Hoops Lab site to GitHub Pages on the gh-pages branch.

The site has a home page at / and one folder for each tool: /draft/, /adds/.
A publish of one tool replaces its own folder and the home page. It keeps the folders of the other tools.
Each page of a tool gets a bar at the top with links to the home page and to the other tools.
"""

import html
import re
import subprocess

BRANCH = "gh-pages"
URL = "https://mccomark21.github.io/fantasy-hoops-lab/"
# One line on the home page for each tool, in the order of the page.
TOOLS = {
    "draft": ("Draft board", "Auction values and playoff schedules for the 2026-27 draft."),
    "adds": ("Weekly adds plan", "How to use the 5 adds of the current fantasy week."),
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


def home_page(tools):
    """The home page: one line and one link for each tool on the site."""
    items = "\n".join(
        f'<li><a href="{t}/">{html.escape(TOOLS[t][0])}</a><span>{html.escape(TOOLS[t][1])}</span></li>'
        for t in TOOLS
        if t in tools
    )
    return HOME.replace("__TOOLS__", items)


def nav_bar(tool, tools):
    """The bar at the top of each page of a tool: a link to the home page and to each tool on the site."""
    current = ' aria-current="page"'
    links = ['<a href="../">Home</a>'] + [
        f'<a href="../{t}/"{current if t == tool else ""}>{html.escape(TOOLS[t][0])}</a>' for t in TOOLS if t in tools
    ]
    return f'{NAV_STYLE}<nav class="site-nav">{" · ".join(links)}</nav>'


def with_nav_bar(data, tool, tools):
    """The page with the nav bar after its <body> tag. A page with no <body> tag does not change."""
    text = data.decode("utf-8")
    return re.sub(r"<body[^>]*>", lambda m: m.group(0) + nav_bar(tool, tools), text, count=1).encode("utf-8")


def publish(repo, tool, index, others=()):
    """Push the pages of one tool to gh-pages in origin, in the folder /<tool>/. The working tree and the current branch do not change.

    index: the main page of the tool. It goes to /<tool>/index.html.
    others: more pages of the tool. Each one goes to /<tool>/ with its own file name.
    The folders of the other tools on gh-pages stay. The home page links to each tool folder on the site.
    Each page gets the nav bar. The pages of the other tools keep the nav bar of their last publish.
    The branch holds one commit, so each run replaces the last one and the old pages do not stay in the repo.
    """
    if tool not in TOOLS:
        raise ValueError(f"{tool} is not a tool of the site. The tools are: {', '.join(TOOLS)}.")
    if not index.exists():
        raise FileNotFoundError(f"{index} does not exist.")
    folders = published_folders(repo)
    tools = {*folders, tool}
    pages = {"index.html": index.read_bytes(), **{o.name: o.read_bytes() for o in others}}
    pages = {n: with_nav_bar(d, tool, tools) if n.endswith(".html") else d for n, d in pages.items()}
    folders[tool] = (
        "040000",
        "tree",
        make_tree(repo, {n: ("100644", "blob", write_blob(repo, d)) for n, d in pages.items()}),
    )
    root = {
        name: ("100644", "blob", write_blob(repo, data))
        for name, data in {".nojekyll": b"", "index.html": home_page(folders).encode()}.items()
    }
    commit = git(repo, "commit-tree", make_tree(repo, {**root, **folders}), "-m", f"Publish the {tool} pages")
    git(repo, "push", "--force", "origin", f"{commit}:refs/heads/{BRANCH}")


NAV_STYLE = """<style>
.site-nav { padding: 8px 16px; font: 14px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif;
            background: #fafaf9; color: #78716c; border-bottom: 1px solid #e7e5e4; overflow-wrap: anywhere; }
.site-nav a { color: #7c3aed; font-weight: 600; text-decoration: none; }
.site-nav a[aria-current] { color: #1c1917; }
@media (prefers-color-scheme: dark) {
  .site-nav { background: #1c1917; color: #a8a29e; border-color: #44403c; }
  .site-nav a { color: #a78bfa; }
  .site-nav a[aria-current] { color: #f5f5f4; }
}
</style>"""

HOME = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fantasy Hoops Lab</title>
<style>
:root { --bg: #fafaf9; --fg: #1c1917; --muted: #78716c; --line: #e7e5e4; --q: #7c3aed; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #1c1917; --fg: #f5f5f4; --muted: #a8a29e; --line: #44403c; --q: #a78bfa; }
}
body { margin: 0; padding: 24px 16px; background: var(--bg); color: var(--fg);
       font: 14px/1.4 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 640px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
p { margin: 0 0 16px; color: var(--muted); }
ul { list-style: none; margin: 0; padding: 0; border: 1px solid var(--line); border-radius: 8px; }
li { padding: 12px; overflow-wrap: anywhere; }
li + li { border-top: 1px solid var(--line); }
a { display: block; font-weight: 600; color: var(--q); }
span { color: var(--muted); }
</style>
</head>
<body>
<main>
<h1>Fantasy Hoops Lab</h1>
<p>Analysis tools for one Yahoo fantasy basketball league, 2026-27 season.</p>
<ul>
__TOOLS__
</ul>
</main>
</body>
</html>
"""
