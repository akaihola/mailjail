# Review mailjail's architecture for deep modules and over-engineering, and draft the fixes

Steward issue, 2026-10-19 (spare quota, steward decisions D48 and D53:
whole-repository architecture review). Goal: open-source; mailjail is tier 3.
`main` took 27 commits since 2026-09-19 and has never had a whole-repository
review.

## Work

1. Read `README.md`, `DESIGN.md`, `docs/`, then `src/` and `tests/`.
2. Apply the `honey` principles with `honey-review` (speculative
   generality, hand-rolled stdlib, single-caller abstractions, dead code,
   narration) and `codebase-design` for deep modules: where a seam would
   make the IMAP layer, the JMAP method surface or the capability checks
   smaller to change and easier to test.
3. Check `README.md`, `DESIGN.md` and `docs/` against the code: list every
   statement the code contradicts.
4. Write `docs/reviews/2026-10-19-architecture-review.md`: findings ranked
   by benefit per hour, each with file and line evidence and a drafted
   issue (title, work, acceptance, about an agent hour each). Mark drafts
   that overlap open issues in `TASKS.md` instead of duplicating them.

## Ground rules

- Architecture only. Don't probe for vulnerabilities or write exploit
  reproductions: a security review waits for Antti's choice of model.
- Read-only apart from the report and this issue's tracker moves. Don't
  file the drafts; the steward files them. Don't connect to a mail server.

## Acceptance

- Every finding cites code on `main` and says what changes if it is fixed.
- The report names the three drafts it would do first, and why.
