import subprocess

import pytest

from fantasyhoops.core.publish import BRANCH


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    """A clone with one commit on main and a bare 'origin'."""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", str(origin), str(work))
    git(work, "config", "user.name", "Test")
    git(work, "config", "user.email", "test@example.com")
    (work / "README.md").write_text("main\n")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "init")
    git(work, "push", "origin", "main")
    return work


@pytest.fixture
def remote_pages():
    """A function that gives the files on gh-pages in origin, as {path: text}."""
    def pages(repo):
        git(repo, "fetch", "origin", BRANCH)
        names = git(repo, "ls-tree", "-r", "--name-only", "FETCH_HEAD").split()
        return {n: git(repo, "show", f"FETCH_HEAD:{n}") for n in names}
    return pages
