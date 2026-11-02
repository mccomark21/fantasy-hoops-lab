import itertools
import os
import subprocess
import sys

import pytest

from fantasyhoops.refresh import run

MODULES = ["fantasyhoops.fetch.espn", "fantasyhoops.fetch.rotation", "fantasyhoops.adds.plan", "fantasyhoops.trade"]


class FakeSteps:
    """A fake run_module(): it records the arguments of each step. It returns code for the module fail_at, else 0."""

    def __init__(self, fail_at=None, code=1):
        self.calls, self.fail_at, self.code = [], fail_at, code

    def __call__(self, args):
        self.calls.append(args)
        return self.code if args[0] == self.fail_at else 0


def clock():
    """A fake clock that moves 10 seconds at each call."""
    ticks = itertools.count(0, 10)
    return lambda: next(ticks)


def test_the_run_calls_the_4_steps_in_order():
    steps = FakeSteps()
    assert run.main([], run=steps, clock=clock()) == 0
    assert steps.calls == [[m] for m in MODULES]


def test_no_publish_reaches_steps_3_and_4():
    steps = FakeSteps()
    assert run.main(["--no-publish"], run=steps, clock=clock()) == 0
    assert steps.calls == [[MODULES[0]], [MODULES[1]], [MODULES[2], "--no-publish"], [MODULES[3], "--no-publish"]]


def test_each_step_prints_one_ok_line_and_the_run_prints_the_total_time(capsys):
    run.main([], run=FakeSteps(), clock=clock())
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if " ... " in line] == [
        "[1/4] NBA rosters and schedule ... ok (10 s)",
        "[2/4] Rotation log ... ok (10 s)",
        "[3/4] Adds plan ... ok (10 s)",
        "[4/4] Trades ... ok (10 s)",
    ]
    assert lines[-1] == "Refresh done. Total time: 1 min 30 s"


def test_a_failed_step_stops_the_run_names_the_step_and_gives_its_command(capsys):
    steps = FakeSteps(fail_at="fantasyhoops.adds.plan", code=2)
    assert run.main(["--no-publish"], run=steps, clock=clock()) == 1
    assert [args[0] for args in steps.calls] == MODULES[:3]  # step 4 does not run
    out = capsys.readouterr().out
    assert "[3/4] Adds plan ... failed (exit code 2)" in out
    assert "To run this step again by itself: python -m fantasyhoops.adds.plan --no-publish" in out
    assert "Refresh done" not in out


def test_the_refresh_command_exits_non_zero_when_a_step_fails(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["refresh"])
    monkeypatch.setattr(run, "run_module", FakeSteps(fail_at="fantasyhoops.fetch.espn"))
    with pytest.raises(SystemExit) as stop:
        run.cli()
    assert stop.value.code == 1


def test_run_module_runs_python_m_from_the_repo_root(monkeypatch):
    seen = {}

    def fake_run(cmd, cwd):
        seen.update(cmd=cmd, cwd=cwd)
        return subprocess.CompletedProcess(cmd, 3)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert run.run_module(["fantasyhoops.trade", "--no-publish"]) == 3
    assert seen == {"cmd": [sys.executable, "-m", "fantasyhoops.trade", "--no-publish"], "cwd": run.ROOT}


def test_python_m_fantasyhoops_refresh_shows_the_help():
    """The second name of the command: python -m fantasyhoops.refresh. --help runs no step."""
    env = {**os.environ, "PYTHONPATH": str(run.ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "-m", "fantasyhoops.refresh", "--help"], capture_output=True, text=True, cwd=run.ROOT, env=env
    )
    assert result.returncode == 0, result.stderr
    assert "--no-publish" in result.stdout
