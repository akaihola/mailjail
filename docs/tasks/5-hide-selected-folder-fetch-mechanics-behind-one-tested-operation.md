Steward issue, 2026-10-19. Goal: open-source; mailjail is tier 3.

From draft D3 of `docs/reviews/2026-10-19-architecture-review.md` (the review in mailjail [1]), which ranks it among the first to do. The draft follows as the reviewer wrote it; read the review's other sections only if this one points there.

## Draft

Evidence: src/mailjail/models/email.py:199–212 and
src/mailjail/app.py:49–61 both borrow, select, build UID criteria and fetch with
`mark_seen=False`. The get handler at 215–220 compares UIDs from the accumulated
results across folders, losing folder identity. A returned UID in one folder
can therefore mask an absent UID in another. tests/test_app.py:106–134 patches
the handler itself; no test currently exercises download or get conversion.

Change if fixed: reads share one IMAP boundary, and `notFound` reflects complete
requested email IDs. Future FETCH changes need one adapter test rather than
WSGI and handler mocks of the same low-level sequence.

Draft title: **Share folder-scoped fetching and fix missing-ID accounting**.
Work: add one concrete fetch operation to the existing IMAP module, owning
selection, criteria and non-marking reads; migrate Email/get and attachment
retrieval. Return materialized results or consume the iterator before returning
the connection. Compute found full IDs per request, not UID fragments.
Acceptance: offline fixtures cover identical UIDs in two folders with one
missing, property projections, missing attachments and `mark_seen=False` on
both callers. At least one WSGI download test crosses the actual adapter.
No broad backend protocol or extra base class. No open overlap.

## Steward's constraints

- Make no connection to a real mail server or account.

## Done when

The draft's acceptance holds, lint and tests pass, and the change is merged to `main` as the Rules describe. No push or deploy.
