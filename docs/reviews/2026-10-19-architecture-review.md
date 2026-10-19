# mailjail architecture review, 2026-10-19

Reviewed `main` at `fb824840234c0cd2246ff4583f33c9ad4e67541b`.
All source citations below refer to that commit, not to proposed changes.

## Scope and judgment

Read README.md, DESIGN.md, all tracked docs, all Python source and tests,
then the packaging and Nix module needed to check deployment claims. Applied
Honey and honey-review. The requested codebase-design skill was not installed;
module-depth analysis below uses information hiding, change locality and test
boundaries directly. No security assessment, exploit reproduction, live mail
connection, credential inspection or service restart was performed.

The architecture does not need a framework, plugin registry, async rewrite or
universal repository interface. The plain WSGI app, explicit dispatcher,
small policy module, stdlib MIME composer and injected pool factory are good
choices. The main cost is incomplete boundaries: protocol handlers know raw
IMAP details, account validation opens connections, and public capabilities
promise more than the implementation tests. Some apparent abstraction is only
a second, unused description of data.

The drafts below are proposals for the steward, not filed issues. Estimates
include a failing offline test first where behavior changes, implementation,
documentation and focused validation. They are bounded first steps, not promises
that all JMAP compatibility work fits in an hour.

## Priority and overlap

Do **D1, D2 and D3 first**, in that order. D1 makes the published setup usable.
D2 keeps one failed invocation from losing an entire request and removes IMAP
startup from methods that do not use IMAP. D3 establishes a tested fetch
boundary while fixing missing-message accounting. Each has an observable
result and avoids a broad rewrite.

Ranked by expected benefit per agent hour, with estimates rather than measured
speedups:

1. D1, repair configuration examples and path handling, 0.75–1 hour.
2. D2, contain each invocation and defer IMAP acquisition, 1 hour.
3. D3, share selected-folder fetching and track complete IDs, 1 hour.
4. D4, make pool replacement and shutdown ownership explicit, 1 hour.
5. D5, make query planning own folder and SORT decisions, 1 hour.
6. D6, implement the documented Email/get body controls, 1 hour.
7. D7, make the advertised capability contract testable, 1 hour.
8. D8, remove false change-tracking state, 0.5 hour.
9. D9, centralize identifier parsing and download URL encoding, 1 hour.
10. D10, replace hand-written entity and address formatting, 0.75 hour.
11. D11, remove internal dead scaffolding, 0.5–1 hour.
12. D12, reconcile the API design document, 1 hour.
13. D13, reconcile deployment guidance and archive old instructions, 1 hour.

Tracker checked at the reviewed revision: HAI-1 is this review; HAI-2 concerns
the tracker marker and is completed awaiting acceptance. Gmail OAuth2
`simple-66d04ffc79679ee6` is also completed awaiting acceptance. There are no
other open backlog/scheduled issues to duplicate. D13 overlaps the Gmail
issue's documentation: fold the Gmail troubleshooting correction into its
acceptance follow-up rather than filing another OAuth implementation task.
The historical task-tracking document and marker discussion overlap HAI-2;
leave checker changes to that issue. All other drafts have no open overlap.

## Findings and drafted issues

### D1. Make the documented configuration loadable

Evidence: README.md:48–54 puts `primary_account` after `[server]`, whereas
src/mailjail/config.py:172–175 requires a root key. Config path values at
src/mailjail/config.py:275–276, 285–287 and 307 become `Path` objects without
`expanduser()`. README.md:67 and DESIGN.md:618, 628 use literal `~` paths.
docs/QUICK_START.md:13–25 uses a quoted heredoc containing literal `$HOME`.
The config loader's own example repeats the root-key mistake at
src/mailjail/config.py:136–142.

Change if fixed: copying the setup example reaches account configuration;
operator paths resolve consistently instead of being treated as relative names.

Draft title: **Make config examples and user paths agree with the loader**.
Work: move the root key before the first table in examples; normalize the three
configured user-path fields with `expanduser()` at their consumption points;
replace literal `$HOME` in the quoted example with `~` once supported. Do not
add general environment interpolation. Document accepted path syntax.
Acceptance: parse the README TOML offline and assert its root key; use temporary
HOME/provider fixtures to exercise tilde paths without real credentials; retain
absolute-path behavior. No network calls. No open overlap.

### D2. Give each invocation its own error and connection boundary

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

### D3. Hide selected-folder fetch mechanics behind one tested operation

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

### D4. Make pool lifecycle rules true at one boundary

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

### D5. Make a query plan own folder selection and sort support

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

### D6. Put body selection and truncation in the fetch conversion contract

Evidence: DESIGN.md:193–195 documents three get arguments, but
src/mailjail/models/email.py:177–183 only reads ids and properties.
src/mailjail/imap/fetch.py:134–201 builds all body content before filtering
properties. `bodyStructure` is documented at DESIGN.md:190 but never produced.
`hasAttachment` is omitted from the body-needing set at
src/mailjail/models/email.py:182, despite depending on attachments at
src/mailjail/imap/fetch.py:153.

Change if fixed: get options have one meaning from request to fetch to
serialization, and a requested projection does not silently choose an
inadequate fetch mode.

Draft title: **Implement Email/get body controls through a single options value**.
Work: validate the documented fetch booleans and byte limit at the handler;
pass those options to conversion and derive fetch mode from required data.
Implement UTF-8 byte truncation and accurate `isTruncated`. Explicitly document
`bodyStructure` as unsupported for now rather than adding a MIME tree API.
Acceptance: offline HTML-only and multipart fixtures cover both booleans,
multibyte truncation, default behavior and `hasAttachment` alone. Preserve
non-marking fetches. No open overlap.

### D7. Test advertised capabilities against the implemented subset

Evidence: src/mailjail/session.py:31–37 advertises numerical limits, while
src/mailjail/models/core.py:22–24 has unconstrained call collections and
src/mailjail/executor.py:113–119 iterates them without a count check.
`using` is stored but never consulted. session.py:52 advertises upload although
src/mailjail/app.py:141–219 has no upload route. IMAP capability storage at
src/mailjail/imap/connection.py:85–106 drives only SORT in
src/mailjail/models/email.py:86; CONDSTORE is logged, not implemented, and no
selected-folder PERMANENTFLAGS check exists in the keyword update path at
src/mailjail/models/email_set.py:17–50.

Change if fixed: one small contract test ties session claims to behavior;
clients can distinguish support from mere observation of a server extension.

Draft title: **Make session limits and capability claims executable**.
Work: share constants for the existing call/get/set limits between validation
and session construction; reject unsupported `using` capabilities clearly.
Document the unimplemented upload route and the distinction between CAPABILITY,
selected-folder PERMANENTFLAGS and implemented JMAP features. Keep the policy
allowlist separate and explicit. Do not implement CONDSTORE, upload or a generic
capability framework in this issue.
Acceptance: small offline boundary tests for each advertised count and unknown
capabilities; session tests assert the documented supported subset. No security
probing or limit-stress tests. No open overlap.

### D8. Remove synthetic change-tracking success

Evidence: src/mailjail/models/email.py:130–147 reports no changes for state
`0`, while Email/get always emits state `0` at 229. No persistent change state
or MODSEQ comparison exists. DESIGN.md:265–269 describes conditional tracking.

Change if fixed: polling clients consistently know they must query again;
unsupported synchronization is no longer represented as a successful empty delta.

Draft title: **Always report unsupported Email/changes until state is tracked**.
Work: use the existing cannotCalculateChanges error for every sinceState;
remove the zero-state success branch and stale explanatory prose. Document
constant get state as a compatibility placeholder. Do not introduce state
storage or CONDSTORE machinery.
Acceptance: tests for `0`, another state and absent state all request a fresh
query; D2 ensures this handler needs no pool. No open overlap.

### D9. Centralize identifier grammar and URL construction

Evidence: src/mailjail/imap/fetch.py:11–38 splits email IDs at the first colon
and attachment IDs at every colon. Hand-written UID extraction also appears
at src/mailjail/models/email.py:216. Raw folder names become mailbox IDs at
src/mailjail/models/mailbox.py:60; the download route splits on slash at
src/mailjail/app.py:145–148. A hierarchical folder name therefore needs a
specified URL representation independently of its ID representation.

Change if fixed: folders with delimiters round-trip through get, update and
download; callers stop reimplementing the same parsing rules.

Draft title: **Define and test one folder/UID/blob identifier grammar**.
Work: keep the current externally visible format; parse fixed suffix components
from the right and use the same helpers at all consumers. Specify how to encode
download path components and how a WSGI-decoded path reaches the parser. Avoid
introducing an opaque-ID database. D3 removes its duplicate extraction first.
Acceptance: ordinary, colon-containing and hierarchical folder fixtures
round-trip through helpers and a WSGI download; invalid formats still return
clear errors. No live IMAP and no open overlap.

### D10. Use stdlib for formatting already covered by stdlib

Evidence: src/mailjail/imap/fetch.py:45–53 maintains seven HTML entities and
71–72 replaces them sequentially. Numeric and other named entities are left
unconverted; sequential replacement can decode a nested entity twice.
src/mailjail/imap/drafts.py:25–31 manually joins display names and addresses.

Change if fixed: previews decode entities consistently and draft display names
with punctuation serialize correctly without a second escaping implementation.

Draft title: **Use html.unescape and email address formatting**.
Work: replace the entity table/loop with `html.unescape`; use
`email.headerregistry.Address` or `email.utils.formataddr` for draft address
values. Keep the small best-effort tag stripping behavior unless an existing
fixture demands more. No new parsing dependency.
Acceptance: offline tests cover numeric/named/nested entities, Unicode display
names and commas in names; MIME round-trips through stdlib. No open overlap.

### D11. Retire unused scaffolding instead of growing parallel APIs

Evidence: the Email/BodyPart/BodyValue/EmailAddress hierarchy at
src/mailjail/models/email.py:16–58 has no production consumer; real responses
are dictionaries from src/mailjail/imap/fetch.py:134–201. The data model omits
attachments and reply metadata that the dictionaries produce. Registry's
materialised method at src/mailjail/registry.py:98–101 has no caller. The loop
at src/mailjail/imap/drafts.py:138–139 has only `pass`; it reads no APPENDUID.
The `folder` parameter at src/mailjail/models/email_set.py:19 is unused.

Change if fixed: each response has one maintained definition, and the remaining
helpers describe operations that actually occur.

Draft title: **Remove unused internal models and no-op IMAP scaffolding**.
Work: confirm whether the Python model classes are a supported external API
before removing them. If supported, retain them and scope this draft to the
other cuts; do not wire them into runtime solely to justify their existence.
Remove unused materialised(), the no-op APPEND loop and unused private parameter.
Replace numbered handler narration with short contract/limitation descriptions.
Keep `_apply_keyword_update`: hiding raw STORE and its no-expunge requirement
is useful even with one caller. Keep validation, error handling and fixtures.
Acceptance: repository-wide references checked, no supported import removed,
existing suite passes; responses and IMAP calls unchanged. D2 may use
settings_for(), so that method is deliberately excluded. No open overlap.

### D12. Replace copied design implementations with the current contract

Evidence: DESIGN.md:448–505 embeds an obsolete policy implementation;
563–590 embeds a different pool. Actual policy and lifecycle are in
src/mailjail/policy.py:8–74 and src/mailjail/imap/connection.py:38–165.
The discrepancy register below identifies the other stale API claims.

Change if fixed: reviewers read one implementation; users can tell a supported
operation from a design aspiration without reconciling contradictory sections.

Draft title: **Reconcile DESIGN with the supported JMAP subset**.
Work: resolve register entries A1–A14 below; replace copied code with source
pointers and concise invariants. Label planned functionality and historical
phase lists. Record current behavior first, and link D5–D8 as proposed changes
rather than describing them as implemented.
Acceptance: all API statements in the register have an explicit resolution;
method matrix agrees with policy/dispatch and session; no behavior changes.
No open overlap.

### D13. Make deployment instructions describe shipped artifacts

Evidence: docs/nixos-system-example.nix:72 writes an `/etc` config, but
src/mailjail/__main__.py:23 and src/mailjail/config.py:18 default to the user's
home unless MAILJAIL_CONFIG is supplied. The system example supplies none.
docs/home-manager-example.nix:21 requires an absent nix/default.nix.
docs/DEPLOYMENT.md:100–106 names a flake package export, but no flake is shipped.
The remaining deployment discrepancies are enumerated below.

Change if fixed: each advertised setup either points to a usable package/config
or explicitly says it is a template with prerequisites.

Draft title: **Reconcile deployment recipes and mark historical plans**.
Work: resolve B1–B11 below; prefer one runnable development recipe and links
from duplicate guides. Add the system service config path environment value;
label absent packaging as future integration. Mark the April plan historical
and annotate superseded statements instead of rewriting its history.
Acceptance: every current snippet names a shipped artifact or an explicit
operator prerequisite; config paths match loader behavior; offline TOML
examples parse. No deployment or real-account verification required.
Overlap: Gmail troubleshooting belongs to the completed OAuth issue's acceptance
follow-up; tracker-marker history belongs to HAI-2.

## Documentation discrepancy register

This is the complete set of contradictions found in the reviewed documents,
grouped where several statements have the same cause. Historical requests are
not treated as promises of current behavior. Deployment state on gogo and
third-party package popularity are not established by source and were not
verified. Security claims are not certified by this architecture review.

### Current API and architecture claims

- **A1. Setup schema and paths.** README.md:48–54 and the loader docstring at
  src/mailjail/config.py:136–142 put the required root key in a table. The
  README password-file path and DESIGN.md:618,628 tilde paths are not expanded.
  Actual behavior is src/mailjail/config.py:172–175,275–287,307. Resolve in D1.
- **A2. Environment scope.** README.md:87–89 says the only honored environment
  variables are the two server overrides. src/mailjail/__main__.py:15,23 also
  reads LOG_LEVEL and MAILJAIL_CONFIG. Narrow the claim to settings overrides.
- **A3. Submission and method policy.** DESIGN.md:47,68 says there is no
  EmailSubmission endpoint; 465–476 blocks EmailSubmission/set and Thread/get.
  Actual policy permits the intercepted submission and synthetic thread get at
  src/mailjail/policy.py:14–24; executor.py:166–180 dispatches both.
- **A4. HTTP policy errors.** DESIGN.md:262–263 promises 403. Actual method
  errors are invocation results from src/mailjail/executor.py:169–176 within
  an HTTP 200 response at src/mailjail/app.py:213–217.
- **A5. Draft mailbox validation.** DESIGN.md:231–233 requires exactly one
  Drafts mailbox ID; its copied policy at 501–502 says runtime validates it.
  src/mailjail/policy.py:67–74 checks the draft keyword, and
  src/mailjail/models/email_set.py:100–125 ignores requested mailboxIds and
  always appends to the configured folder. Document that routing behavior;
  this observation is not a security finding or request to probe the gate.
- **A6. Patch syntax.** DESIGN.md:252 and its copied policy at 488 say only
  `keywords/*`. src/mailjail/policy.py:56 and
  src/mailjail/models/email_set.py:31–38 also accept/normalize the broader
  `keywords` prefix. Record the implemented subset precisely; any gate change
  requires a separately scoped policy review and tests.
- **A7. Query support.** DESIGN.md:178 promises raw header filtering, but
  src/mailjail/imap/search.py:61–105 has no header case and silently ignores
  unknown properties. Compound filters at DESIGN.md:542–543 do not account
  for ignored nested folder conditions. Sort properties at 180 do not disclose
  first-key-only SORT or reversed UID fallback. Source evidence is D5.
- **A8. Get bodies and metadata.** DESIGN.md:190,193–195 promises bodyStructure,
  fetch booleans and byte truncation; none is implemented. Source evidence is
  D6. src/mailjail/imap/fetch.py:149–150 sets both dates from `msg.date`, so
  receivedAt is not an independently obtained arrival timestamp either.
- **A9. Change tracking.** DESIGN.md:265–269 and 777 suggest CONDSTORE-based
  changes. Actual behavior is the state-0 shortcut/error in D8; CONDSTORE only
  appears in a log at src/mailjail/imap/connection.py:90–94.
- **A10. Typed validation.** DESIGN.md:337–339 describes FilterCondition and
  strict model validation. No FilterCondition exists. Method args are
  `dict[str, Any]` at src/mailjail/models/core.py:24 and handler entry points;
  Email models are unused, while Mailbox does use a model. These are not typed
  method schemas. Session upload/limits shown at DESIGN.md:93–97,122 are
  advertised but unimplemented/unenforced as described in D7.
- **A11. Mailbox encoding and health isolation.** DESIGN.md:514 says mailbox
  IDs are URL-encoded if needed, while src/mailjail/models/mailbox.py:60 uses
  raw names. DESIGN.md:593 says a spare thread can always serve health without
  waiting for IMAP. src/mailjail/app.py:105–114 serially initializes and probes
  every account, borrowing the same pools; no health thread is reserved.
- **A12. Implementation status.** DESIGN.md:750–800 retains unchecked completed
  phases; result refs at 812–814 are still an MVP open question despite
  src/mailjail/executor.py:29–104. Thread view at 799 promises References-chain
  grouping but src/mailjail/models/thread.py:1–31 explicitly returns one email
  per thread. Reply helper at 798 promises auto-populated headers and quotes;
  src/mailjail/imap/drafts.py:72–80 only formats supplied threading IDs, never
  fetches the parent or quotes its text. README.md:185's broad capability
  probing claim needs to distinguish CAPABILITY logging from PERMANENTFLAGS
  and implemented changes. The API overview at DESIGN.md:77 and 317 says
  operations use a single POST endpoint, omitting the implemented download
  route at src/mailjail/app.py:145–157. Project tree at DESIGN.md:399–439 omits
  submission, thread, oauth and thunderbird modules and their tests.
- **A13. Dependencies.** DESIGN.md:362–364 says no C extensions are required,
  although pyproject.toml:9 requires Pydantic 2 and uv.lock's pydantic-core
  entry selects its compiled runtime; the optional cryptography extra and dev
  group at pyproject.toml:12–16 also make the unconditional seven-package count
  misleading. Scope that count to the core environment and remove the no-C
  claim. No upstream versions or package counts were researched.
- **A14. Tracker promotion.** README.md:175–176 says only the user promotes
  proposals. TASKS.md's proposal rules also authorize the steward to promote
  aligned proposals. Resolve the wording without changing tracker behavior.

### Deployment and historical documentation

- **B1. Service copy paths.** docs/QUICK_START.md:8 and
  docs/DEPLOYMENT_INDEX.md:57,120 use `cp mailjail.service` from an unstated
  working directory. The tracked artifact is docs/mailjail.service; the clone
  root recipe needs that prefix, as docs/DEPLOYMENT.md:21 already shows.
- **B2. Literal environment path.** docs/QUICK_START.md:13–25 writes literal
  `$HOME/.thunderbird` through a quoted heredoc. config.py:307 does not expand
  variables. D1 covers this.
- **B3. Profile selection.** docs/QUICK_START.md:25,114,
  docs/DEPLOYMENT.md:145,168,180 and all three Nix examples specify `default`.
  config.py:383–408 treats an explicit profile as a directory name, not a
  profiles.ini display-name alias. The examples must say to replace it with a
  real directory or omit it for discovery.
- **B4. Gmail auth.** docs/QUICK_START.md:127 says Gmail needs an app-specific
  password; docs/DEPLOYMENT.md:295 suggests one for its Thunderbird setup.
  config.py:326–330 and imap/connection.py:77–79 implement Thunderbird OAuth2
  instead. Overlap with the completed Gmail issue; do not file a new feature.
- **B5. TLS switch.** docs/DEPLOYMENT.md:290 recommends disabling TLS as a
  troubleshooting step, but connection.py:55 stores `ssl` without using it to
  select a transport; line 74 always constructs MailBox. Document the actual
  transport and remove that ineffective instruction. Choosing/supporting a
  different transport is future scope, not a security experiment here.
- **B6. Config location for system service.** docs/nixos-system-example.nix:72
  writes `/etc/mailjail/config.toml`, while the process defaults to its home
  config. Source and missing override are described in D13.
- **B7. Package availability.** docs/home-manager-example.nix:21 references
  absent nix/default.nix. docs/DEPLOYMENT.md:100–106 presents a flake export
  not supplied by this repository. Its nixpkgs example at 91 is already
  qualified with "when available" and is not a current availability claim.
- **B8. Defaults and credential timing.** docs/DEPLOYMENT.md:309–311 calls
  MemoryMax/CPUQuota mailjail defaults, but these occur only in
  docs/mailjail.service:20–21, not nix/home-manager-module.nix:77–108 or
  src/mailjail/__main__.py:36. docs/DEPLOYMENT.md:332 says Thunderbird
  credentials decrypt on demand; config.py:204,262,319 resolves them at startup.
  Only IMAP pools are lazy, and access-token exchange occurs on connection.
- **B9. Example descriptions.** docs/DEPLOYMENT_INDEX.md:105 calls the
  deprecated Home Manager example an approach not using the official module;
  docs/home-manager-example.nix:17 imports that module. The index's setup
  steps omit installing the environment expected by docs/mailjail.service:8;
  the quick start similarly has no installation step for that interpreter.
- **B10. Hardening descriptions are not uniform.**
  docs/DEPLOYMENT.md:326 calls ProtectHome=true read-only, but the official
  module explicitly uses the different `read-only` value at
  nix/home-manager-module.nix:94; docs/mailjail.service:16 uses yes.
  docs/DEPLOYMENT_INDEX.md:175–180 generalizes credential location/mode and
  resource quotas across setups even though config.py:284–333 supports other
  credential sources and the official module specifies no quota. Correct the
  descriptions per shipped unit. Runtime isolation and file access were not
  tested and remain for the separate security/deployment review.
- **B11. Historical plan is not current instructions.**
  docs/plans/2026-04-26-bundled-thunderbird-decryption.md:7 describes an old
  subprocess as current; 52 says Pydantic rejects unknown TOML fields, but
  config.py:209–246 does the rejection explicitly. The plan's 58–72 puts dev
  dependencies in an optional extra; pyproject.toml:14–16 uses a dependency
  group. Its private single-key names and copied helper APIs at 114–120,
  147–181 are superseded by thunderbird.py:281–307's multi-key API. The plan's
  655–661 and 738 says Gmail is deferred, now implemented. Mark these as dated
  rollout assumptions. Preserve decisions and historical examples.
  docs/tasks/adopt-task-tracking-principles.md:18 says only a human promotes
  proposals and 36 mentions retained `[~]` meanings, while its own outcome
  later records the then-current adaptation. Annotate history against today's
  rules if this page remains discoverable as instructions; HAI-2 owns marker
  changes. Task descriptions for HAI-1/HAI-2 are requests, not API claims.

### Additional implementation notes worth retaining

APPEND's docstring at src/mailjail/imap/drafts.py:122–123 promises a before/after
UIDNEXT comparison, but 126–128,155–157 only reads the value before APPEND.
D11 removes the no-op response scan; a separate future reliability change
should define what happens when APPENDUID is absent, rather than expanding this
review into an IMAP integration project. Likewise structured logging is listed
as a phase item at DESIGN.md:782, but __main__.py:14–17 configures ordinary text
logging, not structured event output. Label the intended meaning explicitly.

## Honey cut list

Estimates count source lines removed before replacement/tests, not net savings.
These are review suggestions, not edits made in this issue.

1. src/mailjail/models/email.py:16–58: retire the unused internal Email model
   hierarchy if it is not a supported Python API; one dictionary conversion is
   already the runtime definition, about 43 lines. See D11's API check.
2. src/mailjail/models/email.py:65–74,165–174: cut numbered narration that repeats
   the implementation; retain concise input/output and non-marking-read contracts,
   about 16 lines before replacement. D11.
3. src/mailjail/imap/fetch.py:45–53,71–72: cut the hand-maintained entity table
   and replacement loop; stdlib handles it, 11 lines before replacement. D10.
4. src/mailjail/registry.py:98–101: cut unused materialised(), 4 lines. D11.
5. src/mailjail/imap/drafts.py:138–139: cut the no-op response loop, 2 lines. D11.
6. src/mailjail/models/email_set.py:19: cut the unused private folder parameter
   and its call argument, one signature line. D11.

Total candidate removals: about 77 lines across six findings, before replacement,
conditional on the public API check. No speculative plugin, new dependency or
stdlib replacement of the NSS machinery is recommended. Cryptography and
protocol-specific parsing are substantive behavior; a separate security review
must judge their guarantees. The pool factory, recursive result refs, small
flag map and MIME helper functions earn their existence through real callers
and test boundaries.

## Validation

After rebasing to the reviewed main revision:

```bash
PYTHONPATH="$PWD/src" timeout 120 uv run --project /home/agent/prg/mailjail --no-sync pytest -q "$PWD/tests"
python3 scripts/check_tasks_md.py
```

151 tests passed in 0.77 seconds; tracker checker passed. Used the existing uv
project environment to avoid changing dependencies or the lockfile. All tests
use mocks/synthetic local profiles. The first run before picking up HAI-2 had
141 passes and one tracker-marker failure; rebasing picked up its independent
checker fix and the final baseline passed. No production code or tests changed.

All 134 file/line citations resolve within the reviewed tree; all 13 findings
have draft titles, work and acceptance. Whitespace validation passed with
`git diff --check`. These checks validate evidence locations and formatting,
not the proposed fixes.
