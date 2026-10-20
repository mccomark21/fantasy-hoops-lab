import subprocess

import pytest

from fantasyhoops.core.publish import BRANCH, publish


def page(repo, name, text):
    path = repo / "output" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_publish_draft_keeps_adds(repo, remote_pages):
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"))
    publish(repo, "draft", page(repo, "draft/board.html", "<p>board</p>"))
    pages = remote_pages(repo)
    assert pages["adds/index.html"] == "<p>plan</p>"
    assert pages["draft/index.html"] == "<p>board</p>"


def test_publish_adds_keeps_draft(repo, remote_pages):
    window = page(repo, "draft/draft_board_wk20-wk22.html", "<p>wk20</p>")
    publish(repo, "draft", page(repo, "draft/board.html", "<p>board</p>"), [window])
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"))
    assert set(remote_pages(repo)) == {".nojekyll", "index.html", "adds/index.html",
                                       "draft/index.html", "draft/draft_board_wk20-wk22.html"}


def test_publish_replaces_only_its_own_folder(repo, remote_pages):
    publish(repo, "adds", page(repo, "adds/old.html", "<p>old</p>"), [page(repo, "adds/extra.html", "")])
    publish(repo, "adds", page(repo, "adds/new.html", "<p>new</p>"))
    assert set(remote_pages(repo)) == {".nojekyll", "index.html", "adds/index.html"}
    assert remote_pages(repo)["adds/index.html"] == "<p>new</p>"


def test_home_page_links_to_each_tool_on_the_site(repo, remote_pages):
    publish(repo, "draft", page(repo, "draft/board.html", "<p>board</p>"))
    home = remote_pages(repo)["index.html"]
    assert "Fantasy Hoops Lab" in home
    assert 'href="draft/"' in home and 'href="adds/"' not in home
    publish(repo, "adds", page(repo, "adds/plan.html", "<p>plan</p>"))
    home = remote_pages(repo)["index.html"]
    assert 'href="draft/"' in home and 'href="adds/"' in home


def test_old_board_at_the_root_goes_away(repo, remote_pages):
    """Before the site had tool folders, the board was index.html at the root of gh-pages."""
    def git(*args, data=None):
        return subprocess.run(["git", *args], cwd=repo, input=data, check=True, capture_output=True, text=True).stdout.strip()
    blob = git("hash-object", "-w", "--stdin", data="<p>old board</p>")
    tree = git("mktree", data=f"100644 blob {blob}\tdraft_board_wk20-wk22.html\n100644 blob {blob}\tindex.html\n")
    git("push", "origin", f"{git('commit-tree', tree, '-m', 'old')}:refs/heads/{BRANCH}")
    publish(repo, "draft", page(repo, "draft/board.html", "<p>board</p>"))
    pages = remote_pages(repo)
    assert set(pages) == {".nojekyll", "index.html", "draft/index.html"}
    assert "Fantasy Hoops Lab" in pages["index.html"]


def test_unknown_tool_stops_with_an_error(repo):
    with pytest.raises(ValueError, match="draft, adds"):
        publish(repo, "trades", page(repo, "trades/x.html", ""))


def test_each_page_gets_a_nav_bar_with_the_tools_on_the_site(repo, remote_pages):
    publish(repo, "draft", page(repo, "draft/board.html", "<html><body class='x'><p>board</p></body></html>"))
    publish(repo, "adds", page(repo, "adds/plan.html", "<body><p>plan</p></body>"),
            [page(repo, "adds/notes.html", "<body><p>notes</p></body>")])
    pages = remote_pages(repo)
    plan = pages["adds/index.html"]
    assert plan.index("<body>") < plan.index('<nav class="site-nav">') < plan.index("<p>plan</p>")
    assert 'href="../">Home</a>' in plan and 'href="../draft/">Draft board</a>' in plan
    assert 'href="../adds/" aria-current="page">Weekly adds plan</a>' in plan
    assert 'class="site-nav"' in pages["adds/notes.html"]
    # The draft board had its publish before the adds plan was on the site: it has no adds link yet.
    board = pages["draft/index.html"]
    assert "<body class='x'><style>" in board and 'href="../adds/"' not in board
