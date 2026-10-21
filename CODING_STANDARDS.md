# Coding standards

A reviewer checks each change against these rules. Each rule names something that a reviewer can see in the diff, the PR or the issue.

## Tickets

1. Each ticket gets one branch and one PR. A sub-issue is a ticket too.
2. The PR body contains "Closes #N" for the ticket.
3. Do not merge a ticket locally (for example, a "Merge ticket N" commit) in place of a PR.
4. When the build makes a choice, post a comment on the ticket at that time. Start the comment with "## Decision: <the choice> (YYYY-MM-DD)". Issue #39 has examples.
5. After the PR merges, post a closing comment on the ticket in this shape:

   ```md
   > *Shipped via /ship-it.*

   - <what changed, 2 to 5 bullets>

   PR: <url> · Merge: <sha>
   Deferred: <work left undone, or omit the line>
   ```

## Tests

1. `python -m pytest -q` must pass in CI (`.github/workflows/tests.yml`) before the PR merges.
2. The tests of `src/fantasyhoops/<subpackage>/<module>.py` go in `tests/<subpackage>/test_<module>.py`.
3. A test must not fail when files that Git does not track (`data/`, `output/`, CSV files) are missing. A test that reads them calls `pytest.skip` when they are missing.
4. A test that runs JavaScript in Node skips when `node` is not on PATH.

## Docs

1. The guide for a tool is `docs/<tool>/README.md`.
2. Terms that more than one tool uses go in `docs/glossary.md`.
3. Each decision record goes in `docs/adr/`.
4. History goes in `docs/wiki/`. Each claim there has a date and cites a commit, a PR or an issue.

## Code

1. Each tool is one subpackage, `src/fantasyhoops/<tool>/`. Download scripts go in `src/fantasyhoops/fetch/`.
2. Code that more than one tool uses goes in `src/fantasyhoops/core/`. Code in `core/` does not import from a tool subpackage.
3. Get paths from `fantasyhoops.core.common` (`ROOT`, `DATA`, `OUT`). A tool writes its files in `output/<tool>/`. A download script writes its files in `data/`.
4. Calculations read league settings from `config.toml` with `load_config()`. They do not hard-code a setting. Known exception: the page text in `draft/report.py` names 14 teams and $200.
5. Each module starts with a docstring. The docstring says what the module does and names the files that it writes.
6. A module that a person runs has a `main()` function and an `if __name__ == "__main__":` guard. Run it with `python -m fantasyhoops.<tool>.<module>`.

## Prose

Issues, commits, PR bodies, docs, docstrings and code comments use Simplified Technical English. The key rules:

1. Use the active voice. Use the passive only when the actor is unknown.
2. Write one instruction in each sentence. Use a numbered list for 3 or more steps.
3. Write 20 words or fewer in an instruction. Write 25 words or fewer in a description.
4. Do not use semicolons. Do not use phrasal verbs ("spin up", "dive into"). Use the plain verb.
5. Use one name for one thing in a text.
6. Keep each hedge, unit and exception. Do not add a fact that the source did not give.
7. Do not use marketing adjectives (seamless, robust, powerful).
