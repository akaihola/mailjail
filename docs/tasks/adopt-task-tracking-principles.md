# Adopt modern task-tracking principles

Status: completed 2026-10-07, pending user acceptance
Requested by: user, 2026-09-18

## Reference principles

Compare the current `TASKS.md` rules in these repositories:

- `/home/agent/prg/kandev-pacer`
- `/home/agent/prg/filemill`
- `/home/agent/prg/kandev-config`
- `/home/agent/prg/syncop`

Adopt their principles, resolving differences rather than copying a tracker
verbatim. Use an Astra- or Fable-class model for the design and migration.

- Separate unverified ideas from reviewed, ordered work. Only a human promotes
  proposals; deduplicate exact proposals and consolidate overlapping ones.
- Give each issue one canonical record and one lifecycle state: proposal,
  backlog, scheduled, in progress, completed, or human-accepted. Define how the
  existing format represents these states and when human-accepted records and
  their obsolete detail files are retired.
- Select only reviewed, unblocked backlog work. Record explicit dependencies,
  keep ordering consistent, and exclude already scheduled or active work.
- Keep simple items concise; link stable identifiers to detailed descriptions
  and acceptance criteria when needed. Keep dependency metadata consistent.
- Commit scheduling on the base branch. Rebase a task worktree before changing
  its state, do implementation there, and record completion after merge.
- Preserve identifiers, text, and wrapping during state moves. Resolve tracker
  conflicts from the base branch, reapply only the current issue's move, and
  check that no issue appears twice. Document maintenance and validation.

## Repository adaptation

Keep the phase-based `TASKS.md`, its `[ ]` / `[~]` / `[x]` meanings, and all
completed phase history. Distinguish lifecycle state from phase membership and
from nested acceptance-test checkboxes. Add explicit proposal, scheduling, and
blocked-work handling without duplicating tasks between phases and a new queue.
Keep the live-inbox smoke test deferred until its live-account prerequisite is
met. Preserve the read/search/flag/draft-only policy; tracker migration must not
access mail, credentials, or change service behavior. Put persistent tracker
rules in tracked documentation, since local `AGENTS.md` is intentionally ignored.

## Done when

Agent instructions identify the authoritative tracker and its review boundary.
The existing mechanism documents the adopted lifecycle, review gate, dependency
selection, and Git workflow. Every prior item retains its meaning and state;
all detailed links resolve and no issue has multiple canonical records. Verify
a sample scheduling/start/completion transition and conflict resolution without
actually starting unrelated work. Record any deliberate differences from the
reference rules.

## Outcome (2026-10-07)

The lifecycle sections, `[ ]` / `[x]` acceptance meaning and the hierarchical
phase history were already in place from the 2026-09-29 and 2026-10-06 tracker
commits. This issue added the remaining rules to `TASKS.md`'s `## Rules`
section (proposal review gate, one-heading invariant, dependency and blocked
handling, scheduling / start / completion Git workflow, conflict resolution),
a structural checker in `scripts/check_tasks_md.py` with tests in
`tests/test_check_tasks_md.py`, and a README pointer naming the tracker and
its review boundary (the local `AGENTS.md` is gitignored).

### Deliberate differences from the reference rules

- `[~]` is not used. The 2026-09-29 commit replaced it with section placement
  (`## In Progress`), matching the reference trackers; this issue keeps that.
- No numbered `[N]` issues or reference-style link block. Detailed issues keep
  `[*]` and link inline to `docs/tasks/<slug>.md`; Hai metadata comments are
  the stable identifiers. Dependencies therefore name a link or Hai id rather
  than `[N]`.
- `- Blocked on: <prerequisite>` is added for prerequisites outside the
  repository (the live-inbox smoke test). The reference rules only model
  issue-to-issue dependencies.
- Completed phase history stays under `### Phase N` subheadings inside
  `## Completed / Accepted`, and Phase 5 step and acceptance-test bullets are
  accepted together with the phase rather than as individual issues.
- Description files are created in the worktree branch (as in filemill), not
  on `main`.
- The live-inbox smoke test completed on `main` on 2026-10-07 while this issue
  was in progress, so no `Blocked on` line was needed for it; the rebase kept
  `main`'s completed record and reapplied only this issue's move.

### Validation evidence

- `python3 scripts/check_tasks_md.py TASKS.md` exits 0 on the migrated file;
  every prior item keeps its text and state, all links resolve, and no issue
  or Hai id appears under two headings.
- `tests/test_check_tasks_md.py` covers section order, duplicate sections,
  issues under two headings, duplicate Hai ids, broken links and misplaced
  acceptance checkboxes.
- A scratch clone exercised the workflow on sample issues without touching
  real work: schedule A on `main`; start A on a branch; schedule B on `main`;
  rebase the branch (conflict in `TASKS.md`); resolve by taking `main`'s file
  and reapplying only A's move; fast-forward merge; record A as
  `- [ ] [*]` completed on `main`. The checker passed after every step.
