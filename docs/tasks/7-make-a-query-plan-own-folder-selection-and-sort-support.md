Steward issue, 2026-10-19. Draft D5 of [1]'s review, `docs/reviews/2026-10-19-architecture-review.md`; its first three drafts are done and accepted. Read the report's section for the evidence and line references.

Evidence: src/mailjail/models/email.py:77–103 takes `inMailbox` only from the
outer filter. src/mailjail/imap/search.py:37–58 recursively translates compound
filters but drops every `inMailbox` at 100–102. Thus nested folder conditions
have no folder-selection effect. SORT uses only the first key at 119–130;
without SORT, the handler reverses UID order regardless of requested property
or direction. tests/test_imap/test_search.py:62–110 checks translation without
the query handler or folder selection.

Change if fixed: clients get the requested supported query or an explicit
unsupported response, instead of a successful result with different semantics.

Draft title: **Plan supported queries before selecting an IMAP folder**.
Work: return folder, search criterion and sort decision from one query-planning
function. Support the existing single-folder subset; explicitly reject
cross-folder/unsupported compound folder combinations and unsupported sort
requests. Document date-only IMAP filtering and any UID-order fallback. Do not
build multi-folder merging or client-side full-message sorting in this issue.
Acceptance: offline query-handler tests cover SORT present/absent, ascending
and descending, secondary sort keys and nested folder conditions. Translator
and selector cannot independently discard different parts of the filter.
No open overlap.

## Decisions, 2026-10-19

- `plan_query()` in `src/mailjail/imap/search.py` is the only entry point. It
  translates the filter and collects `inMailbox` in one recursive pass and
  returns folder, SEARCH criterion and sort decision as one `QueryPlan`. The
  former `jmap_filter_to_imap()`/`jmap_sort_to_imap()` helpers were
  replaced by private helpers that only `plan_query()` calls.
- A filter object with `operator` and any key besides `conditions` fails
  with `unsupportedFilter`. An `OR` without conditions matches no message.
- `inMailbox` counts at the top level and under `AND`. Under `OR`/`NOT`, with
  two different values, or as `inMailboxOtherThan`, it fails with
  `unsupportedFilter`.
- A filter without `inMailbox` still searches INBOX only. This is the
  existing single-folder subset, now documented as a deviation from JMAP.
- Unknown filter properties (e.g. `header`) now fail with `unsupportedFilter`
  instead of being ignored, so the translator drops nothing either.
- With the SORT extension every comparator is sent. Without it, only one
  `receivedAt` comparator is supported, by UID order; the default without a
  sort stays newest UID first.
