Steward issue, 2026-10-19. Goal: open-source; mailjail is tier 3.

`hai-tasks update` marks an issue it moves to `## In Progress` as `- [~] [N] …`.
`scripts/check_tasks_md.py` accepts only `[ ]` and `[x]` before the issue
reference (`_BULLET` on line 29), so the check fails right after a worker's start
move, and the Rules forbid committing a tracker that fails the check. The paced
worker on [1] stopped there at 11:32 on 2026-10-19; the steward committed its
start move without the marker (`ea473a8`). pi-akaihola fixed the same mismatch
in its own checker (pi-akaihola [3], `557adee`).

**Your own start move:** `hai-tasks update` will write `- [~] [2]`, which the
check rejects until this issue lands. Delete the `[~] ` by hand (and align the
`hai:` comment under the title, two spaces in) before running the check and
committing the start move.

## What to do

1. Let `_BULLET` accept `[~]` as well as `[ ]` and `[x]`.
2. Decide whether `[~]` is valid only under `## In Progress` and enforce that if
   the checker already ties checkbox kinds to sections; otherwise accept it
   anywhere, as `[ ]` is.
3. Add a test, or a fixture run, showing that a tracker with a `[~]` In Progress
   bullet passes and a malformed bullet still fails.

## Acceptance

- `python3 scripts/check_tasks_md.py` passes on a TASKS.md with a `- [~] [N]`
  bullet under `## In Progress`.
- Existing failures (duplicated bullet, misplaced checkbox) still fail.
- Lint and tests pass. Merge to `main` as the Rules describe.
