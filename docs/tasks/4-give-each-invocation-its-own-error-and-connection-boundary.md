Steward issue, 2026-10-19. Goal: open-source; mailjail is tier 3.

From draft D2 of `docs/reviews/2026-10-19-architecture-review.md` (the review in mailjail [1]), which ranks it among the first to do. The draft follows as the reviewer wrote it; read the review's other sections only if this one points there.

## Draft

Evidence: src/mailjail/executor.py:113–119 resolves references outside any
per-call exception boundary. Registry lookup at 146 occurs before the handler
try at 157. src/mailjail/app.py:199–211 replaces an executor failure with one
`serverFail` response whose call ID is `unknown`. Registry lookup creates a
whole pool at src/mailjail/registry.py:74–96, even for the pool-free handlers
at src/mailjail/models/thread.py:16–31,
src/mailjail/models/email.py:117–158 and
src/mailjail/models/submission.py:19–79.

Change if fixed: a failed reference or account initialization keeps its call
ID; later independent calls still run. Intercepted submissions and synthetic
threads do not need a mail server merely to answer.

Draft title: **Contain invocation failures and acquire IMAP only when needed**.
Work: put resolution, account validation and dispatch inside one per-call
boundary; distinguish reference/argument failures from backend failures. Use
existing registry membership/settings access for pool-free handlers. Keep the
explicit dispatch chain and policy gate; do not add a generic handler framework.
Acceptance: an offline three-call request has a failed middle call and a valid
last response with original call IDs; a failing pool factory becomes that
call's `serverFail`; pool-free calls never invoke the factory; unknown accounts
still return `accountNotFound`. No open overlap.

## Steward's constraints

- Make no connection to a real mail server or account.

## Done when

The draft's acceptance holds, lint and tests pass, and the change is merged to `main` as the Rules describe. No push or deploy.
