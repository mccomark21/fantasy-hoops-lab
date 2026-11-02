"""The refresh run (#220): run the 4 tools of the README in order, to get fresh data and pages.

Run it with: refresh (in the venv), or python -m fantasyhoops.refresh. Add --no-publish to write the pages and not
publish them.
The steps:
1. fantasyhoops.fetch.espn: the NBA rosters and the schedule.
2. fantasyhoops.fetch.rotation: the new games, minutes and usage.
3. fantasyhoops.adds.plan: the Adds, Players and Playoffs pages. It publishes.
4. fantasyhoops.trade: the Trades page. It publishes.
Each step runs as python -m <module> from the repo root, so it writes the files that its own module names.
This module writes no files. The run stops at the first step that fails. It names the step and gives its command.
"""

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass

from fantasyhoops.core.common import ROOT
from fantasyhoops.core.console import use_utf8_output


@dataclass(frozen=True)
class Step:
    """One step of the run: the label in the terminal, the module to run, and if it takes --no-publish."""

    label: str
    module: str
    publishes: bool = False


STEPS = (
    Step("NBA rosters and schedule", "fantasyhoops.fetch.espn"),
    Step("Rotation log", "fantasyhoops.fetch.rotation"),
    Step("Adds plan", "fantasyhoops.adds.plan", publishes=True),
    Step("Trades", "fantasyhoops.trade", publishes=True),
)


def step_args(step, publish):
    """The arguments after python -m: the module, and --no-publish for a step that publishes when publish is False."""
    return [step.module] + (["--no-publish"] if step.publishes and not publish else [])


def run_module(args):
    """Run python -m <args> from the repo root. Return the exit code."""
    return subprocess.run([sys.executable, "-m", *args], cwd=ROOT).returncode


def seconds_text(seconds):
    """A time for the terminal, for example "48 s" or "3 min 12 s"."""
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} min {rest} s" if minutes else f"{rest} s"


def main(argv=None, run=None, clock=time.monotonic):
    """Run the steps in order. Return 0 when all steps pass, or 1 at the first step that fails.

    run takes the arguments after python -m and returns the exit code (default run_module()). clock gives the time
    in seconds.
    """
    run = run or run_module
    parser = argparse.ArgumentParser(
        prog="refresh", description="Get fresh data and pages: run the 4 tools of the README in order."
    )
    parser.add_argument("--no-publish", action="store_true", help="Write the pages, but do not publish them.")
    args = parser.parse_args(argv)
    publish = not args.no_publish

    start = clock()
    for number, step in enumerate(STEPS, 1):
        name = f"[{number}/{len(STEPS)}] {step.label}"
        command = " ".join(["python", "-m", *step_args(step, publish)])
        print(name, flush=True)
        step_start = clock()
        code = run(step_args(step, publish))
        if code != 0:
            print(f"{name} ... failed (exit code {code})")
            print(f"The refresh stopped. To run this step again by itself: {command}")
            return 1
        print(f"{name} ... ok ({seconds_text(clock() - step_start)})", flush=True)
    print(f"Refresh done. Total time: {seconds_text(clock() - start)}")
    return 0


def cli():
    """The refresh command of pyproject.toml, and the body of python -m fantasyhoops.refresh."""
    use_utf8_output()
    sys.exit(main())


if __name__ == "__main__":
    use_utf8_output()
    sys.exit(main())
