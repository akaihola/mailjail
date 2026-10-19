Steward issue, 2026-10-19. Draft D4 of [1]'s review, `docs/reviews/2026-10-19-architecture-review.md`; its first three drafts are done and accepted. Read the report's section for the evidence and line references.

Evidence: src/mailjail/imap/connection.py:132–146 catches every consumer
exception as a broken connection; if replacement fails it still queues `mb`.
health_check at 148–153 performs a second NOOP after borrowing already did one.
Registry writes at src/mailjail/registry.py:86–95 use per-account locks, while
close at 103–108 and materialised at 98–101 use a different lock. That lock
does not synchronize creation with shutdown. Existing registry tests at
tests/test_registry.py:49–109 cover sequential close/retry, not this interleaving.

Change if fixed: a connection's ownership and eligibility for reuse are
explicit, and shutdown cannot miss an in-flight pool initialization.

Draft title: **Define pool borrow, replacement and shutdown invariants**.
Work: keep a single checkout/return path; discard unusable connections on failed
replacement and define how later borrows recover capacity; distinguish transport
failure from caller conversion failure. Synchronize registry publication and
close without holding a global lock across network login. Remove the redundant
health NOOP. Keep queues and per-account initialization locks.
Acceptance: bounded offline tests cover failed NOOP plus failed replacement,
consumer exceptions, recovery on a subsequent borrow, and close racing with a
barrier-controlled factory; no closed connection is queued and every constructed
pool is either published or closed. No open overlap. If recovery needs a larger
redesign, split it before implementation rather than adding background workers.