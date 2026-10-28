import subprocess

import pytest

from fantasyhoops.core import common
from fantasyhoops.core.publish import BRANCH

REAL_OUT = common.OUT  # the real output/ folder, before a fixture changes common.OUT


def output_files(folder):
    """Each file under folder, as {path: (size, modification time)}. No folder gives {}."""
    if not folder.exists():
        return {}
    return {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*") if p.is_file()}


@pytest.fixture(scope="session", autouse=True)
def real_output_unchanged():
    """The session fails if a test adds, changes or removes a file under the real output/ folder (#127)."""
    before = output_files(REAL_OUT)
    yield
    after = output_files(REAL_OUT)
    changed = sorted(str(p) for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    assert not changed, f"The tests changed these files under {REAL_OUT}: {changed}"


@pytest.fixture(autouse=True)
def output_in_tmp(monkeypatch, tmp_path):
    """Each test writes its output files in tmp_path: common.OUT points there (#127)."""
    monkeypatch.setattr(common, "OUT", tmp_path)


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
    """A function that gives the files on gh-pages in origin, as {path: text}. A binary file (the font) has no text."""

    def pages(repo):
        git(repo, "fetch", "origin", BRANCH)
        names = git(repo, "ls-tree", "-r", "--name-only", "FETCH_HEAD").split()
        return {n: "" if n.endswith(".woff2") else git(repo, "show", f"FETCH_HEAD:{n}") for n in names}

    return pages
