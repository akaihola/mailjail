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