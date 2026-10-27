# Decision: the chief of staff pushes wiki commits

## Decision

On 2026-10-26, the owner allowed the chief of staff to push commits to `main` without asking, if the commits change only `docs/wiki/`.

## Scope

- A commit that changes only files in `docs/wiki/` can go to `main` without the owner.
- All other pushes still need the owner.

## Why

Unpushed wiki commits made each PR merge need a rebase.

Related: [index](index.md), [Wiki location](decision-wiki-location.md).
