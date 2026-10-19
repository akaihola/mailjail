# mailjail Tasks

Rules for TASKS.md usage are at the bottom of the file.

## Unverified proposals

## Ordered backlog

## Scheduled

## In Progress

## Completed / Accepted

- [ ] [4] Give each invocation its own error and connection boundary
      <!-- hai:{"id":"simple-63ce8edd-777b-4c86-a23b-7b8e9e0a3671","labels":["steward"],"createdAt":"2026-10-19T11:18:16.133Z","updatedAt":"2026-10-19T12:33:42.915Z"} -->

- [ ] [5] Hide selected-folder fetch mechanics behind one tested operation
      <!-- hai:{"id":"simple-c61887b2-cbca-44a7-979c-01523005c888","labels":["steward"],"createdAt":"2026-10-19T11:18:16.725Z","updatedAt":"2026-10-19T12:32:47.973Z"} -->

- [ ] [3] Make the documented configuration loadable
      <!-- hai:{"id":"simple-ef737507-3adf-4b1e-aa6e-2ad0f53feedd","labels":["steward"],"createdAt":"2026-10-19T11:18:15.537Z","updatedAt":"2026-10-19T12:28:21.440Z"} -->

- [ ] [1] Review mailjail's architecture for deep modules and over-engineering, and
  draft the fixes
      <!-- hai:{"id":"simple-debf051e-7bb3-4704-8414-79b444def535","labels":["steward"],"createdAt":"2026-10-19T08:08:28.055Z","updatedAt":"2026-10-19T11:12:49.423Z"} -->

- [ ] [2] Accept hai-tasks' [~] In Progress marker in the tracker check
      <!-- hai:{"id":"simple-10ef580c-0284-475a-97c0-1bfa866a477f","labels":["steward"],"createdAt":"2026-10-19T11:07:39.393Z","updatedAt":"2026-10-19T11:09:07.669Z"} -->

- [ ] [*] Support OAuth2 token extraction for Gmail. Thunderbird stores Gmail
      credentials as OAuth2 refresh tokens (not IMAP passwords) under
      `oauth://accounts.google.com` in `logins.json`. The existing Thunderbird
      provider only handles password-style logins. Add an OAuth2 path that:
      reads the refresh token, exchanges it for an access token via Google's
      token endpoint, then uses XOAUTH2 SASL when authenticating to
      `imap.gmail.com`. Out of scope for the 2026-04-26 inlining work.
      <!-- hai:{"id":"simple-66d04ffc79679ee6","updatedAt":"2026-10-17T08:52:06.419Z"} -->

- [x] [*] Declare `cryptography` in `pyproject.toml`: `tests/test_thunderbird_helper.py` and `scripts/mailjail-thunderbird-password.py` import it, but a fresh `uv sync` leaves it uninstalled so test collection fails
  <!-- hai:{"id":"simple-7adb73cf-550a-4cc3-8d43-8162f497ba7f","createdAt":"2026-10-07T18:53:10.833Z","updatedAt":"2026-10-16T16:17:14.911Z"} -->

- [x] [*] [Adopt modern task-tracking principles](docs/tasks/adopt-task-tracking-principles.md).
  <!-- hai:{"id":"simple-f4a1c7f6cea0281f","updatedAt":"2026-10-07T18:58:59.942Z"} -->

- [x] [*] Smoke test: agent reads inbox via curl (deferred — needs a live
      IMAP account; instructions in README.md "Smoke test")
  <!-- hai:{"id":"simple-e43509d48ee35e1e","updatedAt":"2026-10-17T07:09:47.352Z"} -->

### Phase 1 — Core service (MVP)

- [x] [*] Project scaffolding (pyproject.toml, src layout, AGENTS.md, .gitignore)
  <!-- hai:{"id":"simple-9645b8358c7c43d0","updatedAt":"2026-10-17T07:09:49.622Z"} -->
- [x] [*] Pydantic models for JMAP core (Request, Response, Invocation, error types)
  <!-- hai:{"id":"simple-75c9979d1421afdb","updatedAt":"2026-10-17T07:09:50.604Z"} -->
- [x] [*] Policy module (`policy.py`) with tests
  <!-- hai:{"id":"simple-1b435fc4daf74561","updatedAt":"2026-10-17T07:09:51.445Z"} -->
- [x] [*] IMAP connection pool (`imap_tools`, `queue.Queue`)
  <!-- hai:{"id":"simple-70d9874c5cef83ff","updatedAt":"2026-10-17T07:09:52.284Z"} -->
- [x] [*] `Mailbox/get` — list folders
  <!-- hai:{"id":"simple-26895e8b8b504998","updatedAt":"2026-10-17T07:09:53.034Z"} -->
- [x] [*] `Email/query` — search with basic filters (from, subject, date, keyword)
  <!-- hai:{"id":"simple-c2d3e3d281772a5f","updatedAt":"2026-10-17T07:09:55.114Z"} -->
- [x] [*] `Email/get` — fetch headers, preview, full body
  <!-- hai:{"id":"simple-85cd79f3c0850240","updatedAt":"2026-10-17T07:09:57.238Z"} -->
- [x] [*] `Email/set` update — keyword changes (star, seen, custom)
  <!-- hai:{"id":"simple-a808c4f992e035cb","updatedAt":"2026-10-17T07:09:58.173Z"} -->
- [x] [*] `Email/set` create — save drafts
  <!-- hai:{"id":"simple-32bd743393eff7a3","updatedAt":"2026-10-17T07:09:59.173Z"} -->
- [x] [*] JMAP executor: method dispatch + result references (RFC 8620 §3.7)
  <!-- hai:{"id":"simple-ce03c2978d636627","updatedAt":"2026-10-17T07:10:00.002Z"} -->
- [x] [*] WSGI app (`waitress`): POST /jmap + GET /.well-known/jmap
  <!-- hai:{"id":"simple-7c237eec09eef8d1","updatedAt":"2026-10-17T07:10:01.078Z"} -->
- [x] [*] GET /healthz endpoint
  <!-- hai:{"id":"simple-790661b26fafe15c","updatedAt":"2026-10-17T07:10:01.814Z"} -->
- [x] [*] Integration tests against IMAP mock / fixture
      (covered by `tests/test_app.py` end-to-end through the executor with
      mocked `AccountRegistry` / `IMAPPool`.)
  <!-- hai:{"id":"simple-c5abd301f8c94809","updatedAt":"2026-10-17T07:10:02.614Z"} -->

### Phase 2 — Deployment & integration

- [x] [*] Config file parsing (TOML via stdlib `tomllib`)
  <!-- hai:{"id":"simple-84f0885977e7179e","updatedAt":"2026-10-17T07:10:03.544Z"} -->
- [x] [*] Credential management (password file + env var)
  <!-- hai:{"id":"simple-b309742187e72642","updatedAt":"2026-10-17T07:10:04.732Z"} -->
- [x] [*] NixOS systemd service definition (your user, Home Manager)
  <!-- hai:{"id":"simple-0fe1e9c9f90d22f4","updatedAt":"2026-10-17T07:10:05.470Z"} -->
- [x] [*] Probe IMAP server: PERMANENTFLAGS / SORT / CONDSTORE support
  <!-- hai:{"id":"simple-40093cba3b7e57c4","updatedAt":"2026-10-17T07:10:06.384Z"} -->
- [x] [*] Agent skill file (`~/.claude/skills/mailjail/SKILL.md` with curl examples)
  <!-- hai:{"id":"simple-800e83f2d626c7ff","updatedAt":"2026-10-17T07:10:07.072Z"} -->

### Phase 3 — Robustness

- [x] [*] IMAP connection keepalive and reconnection
  <!-- hai:{"id":"simple-d77e68d6ca0c50b7","updatedAt":"2026-10-17T07:10:07.742Z"} -->
- [x] [*] `Email/changes` (returns cannotCalculateChanges; client must Email/query)
  <!-- hai:{"id":"simple-081daf45241822ec","updatedAt":"2026-10-17T07:10:08.402Z"} -->
- [x] [*] Compound filters (AND/OR/NOT)
  <!-- hai:{"id":"simple-c8d96517950bfbb2","updatedAt":"2026-10-17T07:10:09.358Z"} -->
- [x] [*] SORT support (if server advertises it)
  <!-- hai:{"id":"simple-70d6eace348f21f6","updatedAt":"2026-10-17T07:10:10.255Z"} -->
- [x] [*] Attachment blob download endpoint
  <!-- hai:{"id":"simple-609b95977fc217b4","updatedAt":"2026-10-17T07:10:11.189Z"} -->
- [x] [*] Structured logging
  <!-- hai:{"id":"simple-e39cbb72a2655b05","updatedAt":"2026-10-17T07:10:12.093Z"} -->

### Phase 4 — Polish

- [x] [*] README with setup instructions
  <!-- hai:{"id":"simple-a32fec7b63f75f89","updatedAt":"2026-10-17T07:10:12.718Z"} -->
- [x] [*] Draft reply helper (auto-populate In-Reply-To, References, quoted text)
  <!-- hai:{"id":"simple-735628553312a404","updatedAt":"2026-10-17T07:10:13.386Z"} -->
- [x] [*] Thread view
  <!-- hai:{"id":"simple-fc8d764708787521","updatedAt":"2026-10-17T07:10:14.115Z"} -->
- [x] [*] HTML body → plain text for agent consumption
  <!-- hai:{"id":"simple-3e03d739f0ef478e","updatedAt":"2026-10-17T07:10:14.932Z"} -->

### Phase 5 — Multi-account support

Goal: one `mailjail` server proxies multiple IMAP accounts through a single JMAP
endpoint. Every method call requires an explicit `accountId` matching a configured
account – no `"default"` alias, no implicit fallback. No backward compatibility
with old single-account configs.

Each step below is TDD: write failing tests first, then implement. The
acceptance-test matrix at the end of each section lists the required red/green
tests. Sections are ordered by dependency – implement top-to-bottom.

#### 5.1 Error model (`models/core.py`)

- [x] [*] Add `ACCOUNT_NOT_FOUND = "accountNotFound"` to `JMAPErrorType` in
      `src/mailjail/models/core.py`.
  <!-- hai:{"id":"simple-6dd19b7d50212dfa","updatedAt":"2026-10-17T07:10:15.686Z"} -->

Acceptance tests (`tests/test_models.py`):
- [x] [*] `JMAPErrorType.ACCOUNT_NOT_FOUND` has value `"accountNotFound"`.
  <!-- hai:{"id":"simple-e42b1386bfa6b93a","updatedAt":"2026-10-17T07:10:16.477Z"} -->
- [x] [*] `make_error_invocation(JMAPErrorType.ACCOUNT_NOT_FOUND, ...)` produces
      `("error", {"type": "accountNotFound", ...}, call_id)`.
  <!-- hai:{"id":"simple-3dc9de45ac76acc0","updatedAt":"2026-10-17T07:10:17.167Z"} -->

#### 5.2 Config model (`config.py`)

- [x] [*] Create `AccountSettings(BaseModel)` holding per-account fields:
      `imap_host`, `imap_port`, `imap_ssl`, `imap_username`, `imap_password`,
      `pool_size`, `drafts_folder`, and all credential-provider fields
      (everything currently on `Settings` except `server_host`/`server_port`).
  <!-- hai:{"id":"simple-3a2dec56e6306b1a","updatedAt":"2026-10-17T07:10:17.840Z"} -->
- [x] [*] Reshape `Settings` to keep only `server_host`, `server_port`,
      `primary_account: str`, and `accounts: dict[str, AccountSettings]`.
      Remove the flat IMAP fields from `Settings`.
  <!-- hai:{"id":"simple-1f9ff868059b76ac","updatedAt":"2026-10-17T07:10:18.732Z"} -->
- [x] [*] Update `load_settings` / `_merge_toml_into_data` to parse
      `[accounts.<id>]` TOML sections. Each section maps to one
      `AccountSettings` via the same field names the old `[imap]` section used.
  <!-- hai:{"id":"simple-005abf905995931a","updatedAt":"2026-10-17T07:10:19.454Z"} -->
- [x] [*] Validate that `primary_account` names an account that exists in
      `accounts`; raise on mismatch.
  <!-- hai:{"id":"simple-ef2a854825468a73","updatedAt":"2026-10-17T07:10:20.125Z"} -->
- [x] [*] Drop per-account env-var overrides. Keep only server-level env vars:
      `MAILJAIL_SERVER_HOST`, `MAILJAIL_SERVER_PORT`. Document in DESIGN.md
      that per-account configuration is TOML-only.
  <!-- hai:{"id":"simple-f3dbd79403018d9c","updatedAt":"2026-10-17T07:10:20.740Z"} -->
- [x] [*] Credential resolution (`_apply_mailjail_credentials`,
      `_apply_himalaya_credentials`, `_apply_thunderbird_credentials`) runs
      independently per account during `load_settings`, scoped to that
      account's provider and paths.
  <!-- hai:{"id":"simple-65f161a587f3674e","updatedAt":"2026-10-17T07:10:21.432Z"} -->

Acceptance tests (`tests/test_config.py`):
- [x] [*] Multi-account TOML parses into `Settings` with two `AccountSettings`
      entries, correct fields per account.
  <!-- hai:{"id":"simple-8c8ed0bce0b97d34","updatedAt":"2026-10-17T07:10:22.373Z"} -->
- [x] [*] Missing `primary_account` key raises `ValidationError`.
  <!-- hai:{"id":"simple-e3f43067f175b21b","updatedAt":"2026-10-17T07:10:23.453Z"} -->
- [x] [*] `primary_account` naming a non-existent account raises an error.
  <!-- hai:{"id":"simple-e81050b500320756","updatedAt":"2026-10-17T07:10:24.988Z"} -->
- [x] [*] Each account can use a different credential provider; credentials
      resolve independently (e.g. account `work` uses himalaya, account
      `personal` uses thunderbird).
  <!-- hai:{"id":"simple-5e8c4f3f45c89a89","updatedAt":"2026-10-17T07:10:26.089Z"} -->
- [x] [*] Server-level env vars (`MAILJAIL_SERVER_HOST`, `MAILJAIL_SERVER_PORT`)
      still override TOML values.
  <!-- hai:{"id":"simple-07842d789c26227e","updatedAt":"2026-10-17T07:10:27.392Z"} -->
- [x] [*] Old single-account TOML (no `[accounts.*]` sections) raises a clear
      error pointing to the new schema.
  <!-- hai:{"id":"simple-b31b55f21c418c76","updatedAt":"2026-10-17T07:10:28.833Z"} -->

#### 5.3 Account registry and pool lifecycle (`registry.py` – new file)

- [x] [*] Create `AccountContext` bundling one `AccountSettings` and its
      `IMAPPool`, keyed by account ID.
  <!-- hai:{"id":"simple-82134639f6a5b7e6","updatedAt":"2026-10-17T07:10:29.640Z"} -->
- [x] [*] Create `AccountRegistry` holding `dict[str, AccountContext]`. Pools
      are created lazily on first `get(account_id)` call (not at construction
      time). Thread-safe lazy init.
  <!-- hai:{"id":"simple-21b51bcd6ae81e7d","updatedAt":"2026-10-17T07:10:30.342Z"} -->
- [x] [*] `AccountRegistry.get(account_id) -> AccountContext` returns the context
      or raises `KeyError`.
  <!-- hai:{"id":"simple-f1629881862b4ca7","updatedAt":"2026-10-17T07:10:30.967Z"} -->
- [x] [*] `AccountRegistry.close()` calls `pool.close()` on every materialised
      pool (for clean shutdown).
  <!-- hai:{"id":"simple-eca94d058e9dde90","updatedAt":"2026-10-17T07:10:31.767Z"} -->
- [x] [*] A failing pool for one account does not prevent `get()` for other
      accounts. Subsequent `get()` for a failed account retries pool creation.
  <!-- hai:{"id":"simple-58f3daceaae97603","updatedAt":"2026-10-17T07:10:32.526Z"} -->

Acceptance tests (`tests/test_registry.py` – new file):
- [x] [*] `get("work")` returns the context for "work"; `get("unknown")` raises
      `KeyError`.
  <!-- hai:{"id":"simple-0de2f8c6b32efdef","updatedAt":"2026-10-17T07:10:33.188Z"} -->
- [x] [*] Pool is not created until the first `get()` call for that account.
  <!-- hai:{"id":"simple-0a8025cdd70f942d","updatedAt":"2026-10-17T07:10:34.017Z"} -->
- [x] [*] Two `get()` calls for the same account return the same pool instance.
  <!-- hai:{"id":"simple-11e8100e119909ef","updatedAt":"2026-10-17T07:10:34.822Z"} -->
- [x] [*] `close()` calls `pool.close()` on all materialised pools.
  <!-- hai:{"id":"simple-5163921b5eece5ef","updatedAt":"2026-10-17T07:10:35.597Z"} -->
- [x] [*] If pool construction fails for account A, account B is still accessible.
  <!-- hai:{"id":"simple-99212232549c4b67","updatedAt":"2026-10-17T07:10:36.391Z"} -->
- [x] [*] After pool construction failure, a retry for the same account
      re-attempts construction.
  <!-- hai:{"id":"simple-449e1fcd402375c5","updatedAt":"2026-10-17T07:10:37.183Z"} -->

#### 5.4 Remove implicit `"default"` fallbacks from handlers

Before wiring the executor, harden every handler so it never silently
supplies a fallback `accountId`. The executor (5.5) will guarantee
`accountId` is present, but defense-in-depth means handlers must not mask
routing bugs.

- [x] [*] `handle_mailbox_get` in `models/mailbox.py:92`: change
      `args.get("accountId", "default")` → `args["accountId"]`.
  <!-- hai:{"id":"simple-21ba486bcd1f1d75","updatedAt":"2026-10-17T07:10:37.803Z"} -->
- [x] [*] `handle_email_query` in `models/email.py:75`: same change.
  <!-- hai:{"id":"simple-b3ff2ec21943b19d","updatedAt":"2026-10-17T07:10:38.595Z"} -->
- [x] [*] `handle_email_get` in `models/email.py:124`: same change.
  <!-- hai:{"id":"simple-c7053eb76cc676a3","updatedAt":"2026-10-17T07:10:40.052Z"} -->
- [x] [*] `handle_email_set` in `models/email_set.py:144`: same change.
  <!-- hai:{"id":"simple-9ba8d4ae3be24765","updatedAt":"2026-10-17T07:10:40.768Z"} -->
- [x] [*] `handle_email_submission_set` in `models/submission.py:32`: same change.
  <!-- hai:{"id":"simple-394d4b45253730b8","updatedAt":"2026-10-17T07:10:42.275Z"} -->

Acceptance tests (update existing tests in `tests/test_executor.py`,
`tests/test_models.py`, `tests/conftest.py`):
- [x] [*] Every handler test fixture includes an explicit `"accountId"` value.
  <!-- hai:{"id":"simple-ef20332876473817","updatedAt":"2026-10-17T07:10:43.038Z"} -->
- [x] [*] Calling any handler with `args` missing `"accountId"` raises `KeyError`
      (not silently returns `"default"`).
  <!-- hai:{"id":"simple-ce6e84e9c2154a94","updatedAt":"2026-10-17T07:10:43.732Z"} -->

#### 5.5 Executor routing (`executor.py`)

- [x] [*] Change `Executor.__init__` to accept `AccountRegistry` instead of
      `pool: IMAPPool, settings: Settings`.
  <!-- hai:{"id":"simple-d8114146d85d9df4","updatedAt":"2026-10-17T07:10:44.501Z"} -->
- [x] [*] In `_dispatch`, before reaching any handler: extract `accountId` from
      resolved args. If absent or not a string, return `accountNotFound`.
      Call `registry.get(accountId)` – on `KeyError`, return
      `accountNotFound`.
  <!-- hai:{"id":"simple-65a107c3e87c23e7","updatedAt":"2026-10-17T07:10:45.123Z"} -->
- [x] [*] Pass the resolved `AccountContext.pool` and `AccountContext.settings`
      into each handler. Handler signatures remain `(args, pool)` or
      `(args, pool, settings)` – unchanged.
  <!-- hai:{"id":"simple-663c7e94c567731d","updatedAt":"2026-10-17T07:10:45.883Z"} -->
- [x] [*] `EmailSubmission/set` currently takes only `args`; extend its call site
      to also pass the resolved `AccountContext.settings` so it can use the
      account-specific `imap_username` as from-address.
  <!-- hai:{"id":"simple-a394fa4458611dc8","updatedAt":"2026-10-17T07:10:46.668Z"} -->

Acceptance tests (`tests/test_executor.py`):
- [x] [*] Request with valid `accountId` dispatches to the correct pool (mock
      two registries, assert the right pool's methods are called).
  <!-- hai:{"id":"simple-a016ad09c3a633a3","updatedAt":"2026-10-17T07:10:47.556Z"} -->
- [x] [*] Request with missing `accountId` returns `("error",
      {"type": "accountNotFound", ...}, call_id)`.
  <!-- hai:{"id":"simple-d5ddbda2ef1ad4be","updatedAt":"2026-10-17T07:10:48.229Z"} -->
- [x] [*] Request with unknown `accountId` returns `accountNotFound`.
  <!-- hai:{"id":"simple-5d1e104dc2ff0d2c","updatedAt":"2026-10-17T07:10:48.977Z"} -->
- [x] [*] Two method calls in one request with different valid `accountId` values
      each use their own pool.
  <!-- hai:{"id":"simple-e6e1021b4d0f89d5","updatedAt":"2026-10-17T07:10:49.890Z"} -->
- [x] [*] Result-reference resolution still works across calls to different
      accounts.
  <!-- hai:{"id":"simple-c4e060dc3a164101","updatedAt":"2026-10-17T07:10:50.741Z"} -->

#### 5.6 Handler adjustments

- [x] [*] `handle_email_set_create` (`models/email_set.py`): already receives
      `settings` – verify it uses `settings.drafts_folder` and
      `settings.imap_username`. No code change expected; add test.
  <!-- hai:{"id":"simple-2c3bf2a211d3bf20","updatedAt":"2026-10-17T07:10:51.779Z"} -->
- [x] [*] `handle_email_submission_set` (`models/submission.py`): add `settings`
      parameter. Use `settings.imap_username` for logging the intercepted
      from-address. Do NOT validate that the referenced `emailId` belongs to
      the same account – intercepted submissions are fake anyway, and
      cross-account draft references are harmless because no email is sent.
      Add a code comment documenting this decision.
  <!-- hai:{"id":"simple-9e533881b7452696","updatedAt":"2026-10-17T07:10:52.769Z"} -->

Acceptance tests:
- [x] [*] `Email/set` create for account `work` appends to `work`'s
      `drafts_folder` using `work`'s pool, with from-address
      `work`'s `imap_username` (`tests/test_imap/test_drafts.py`).
  <!-- hai:{"id":"simple-8ebd857da6592a44","updatedAt":"2026-10-17T07:10:53.673Z"} -->
- [x] [*] `EmailSubmission/set` for account `work` logs `work`'s `imap_username`
      as the intercepted from-address (`tests/test_executor.py`).
  <!-- hai:{"id":"simple-991cb104cdc4fd4b","updatedAt":"2026-10-17T07:10:54.824Z"} -->

#### 5.7 Session resource (`session.py`)

- [x] [*] Change `session_resource(settings)` →
      `session_resource(settings, registry)` (or accept the full `Settings`
      with its `accounts` dict – whichever is simpler).
  <!-- hai:{"id":"simple-dc554356dd362df2","updatedAt":"2026-10-17T07:10:55.811Z"} -->
- [x] [*] Build `"accounts"` dict by iterating `settings.accounts`: each key is
      the account ID, value has `name` (from `imap_username`), `isPersonal`,
      and `accountCapabilities` with `urn:ietf:params:jmap:mail` and
      `urn:ietf:params:jmap:submission`.
  <!-- hai:{"id":"simple-360ee36c7da55004","updatedAt":"2026-10-17T07:10:57.034Z"} -->
- [x] [*] Set `"primaryAccounts"` for both `urn:ietf:params:jmap:mail` and
      `urn:ietf:params:jmap:submission` to `settings.primary_account`.
  <!-- hai:{"id":"simple-bf24b4d91330c72d","updatedAt":"2026-10-17T07:10:57.744Z"} -->

Acceptance tests (`tests/test_session.py` – new file):
- [x] [*] Session with two accounts: both appear in `"accounts"` with correct
      `name` and `accountCapabilities`.
  <!-- hai:{"id":"simple-533d7e997179753d","updatedAt":"2026-10-17T07:10:59.035Z"} -->
- [x] [*] `"primaryAccounts"` values equal `settings.primary_account`.
  <!-- hai:{"id":"simple-9b1cc04a1bac6c81","updatedAt":"2026-10-17T07:10:59.911Z"} -->
- [x] [*] Single-account config: the one account appears, and
      `"primaryAccounts"` points to it.
  <!-- hai:{"id":"simple-aa397c25da575491","updatedAt":"2026-10-17T07:11:00.842Z"} -->

#### 5.8 Bootstrap and app layer (`__main__.py`, `app.py`)

- [x] [*] `main()` in `__main__.py`: call `load_settings()`, construct
      `AccountRegistry` from `settings.accounts`, construct `Executor` with
      the registry, pass `settings` and `registry` to `make_app`. Remove the
      single `IMAPPool` construction.
  <!-- hai:{"id":"simple-d63271568024e82c","updatedAt":"2026-10-17T07:11:02.608Z"} -->
- [x] [*] `make_app` signature: accept `executor`, `registry`, and `settings`
      (drop bare `pool` parameter).
  <!-- hai:{"id":"simple-69758e8e33937f2e","updatedAt":"2026-10-17T07:11:03.871Z"} -->
- [x] [*] `/.well-known/jmap` route: call `session_resource(settings, registry)`.
  <!-- hai:{"id":"simple-4c306b67ff0bc2cd","updatedAt":"2026-10-17T07:11:04.918Z"} -->
- [x] [*] `/healthz` route: iterate all accounts in the registry. Report
      per-account status. Overall status is `"ok"` only if at least the
      primary account's pool is healthy. Response shape:
      ```json
      {
        "status": "ok",
        "accounts": {
          "work":     {"imap": "connected"},
          "personal": {"imap": "disconnected"}
        }
      }
      ```
  <!-- hai:{"id":"simple-d05a94e54e3dcb33","updatedAt":"2026-10-17T07:11:06.465Z"} -->
- [x] [*] On SIGTERM / `KeyboardInterrupt`, call `registry.close()` to drain
      all pools.
  <!-- hai:{"id":"simple-9a38f902a582495d","updatedAt":"2026-10-17T07:11:07.519Z"} -->

Acceptance tests (`tests/test_app.py` – new file):
- [x] [*] `GET /.well-known/jmap` returns multi-account session JSON with correct
      structure.
  <!-- hai:{"id":"simple-e395e6aa8c21166f","updatedAt":"2026-10-17T07:11:08.308Z"} -->
- [x] [*] `GET /healthz` returns per-account health status; overall `"ok"` when
      primary is healthy even if a secondary is not.
  <!-- hai:{"id":"simple-5e4c4d6bb782063b","updatedAt":"2026-10-17T07:11:09.742Z"} -->
- [x] [*] `GET /healthz` returns `"error"` when primary account's pool is down.
  <!-- hai:{"id":"simple-d4798ca092f5d919","updatedAt":"2026-10-17T07:11:10.727Z"} -->
- [x] [*] `POST /jmap` routes through executor; a valid request with a known
      `accountId` succeeds.
  <!-- hai:{"id":"simple-7c3176d73df6acbb","updatedAt":"2026-10-17T07:11:12.017Z"} -->

#### 5.9 DESIGN.md update

Update `/home/akaihola/prg/mailjail/DESIGN.md` so it reflects the
multi-account architecture. Specific sections to revise:

- [x] [*] **§3.1 Session / capabilities**: replace the single-account
      `"default"` example JSON with a multi-account example; document
      `primaryAccounts` sourcing from `primary_account` config key.
  <!-- hai:{"id":"simple-ce90e6731cc86253","updatedAt":"2026-10-17T07:11:12.885Z"} -->
- [x] [*] **§3.2 Request format**: update `"accountId": "default"` examples to
      use a named account (e.g. `"work"`).
  <!-- hai:{"id":"simple-51588c46d18286de","updatedAt":"2026-10-17T07:11:13.721Z"} -->
- [x] [*] **§3.3 Supported methods / Email/set create + update**: note that
      `accountId` is required and validated; `accountNotFound` is returned
      for unknown accounts.
  <!-- hai:{"id":"simple-b2f20df1af1aff65","updatedAt":"2026-10-17T07:11:15.362Z"} -->
- [x] [*] **§3.4 Error responses**: add `accountNotFound` to the error type
      table.
  <!-- hai:{"id":"simple-cbd52837f471c302","updatedAt":"2026-10-17T07:11:16.172Z"} -->
- [x] [*] **§3.5 /healthz**: document the new per-account health response shape.
  <!-- hai:{"id":"simple-c52cf6a4d3bb02ae","updatedAt":"2026-10-17T07:11:17.082Z"} -->
- [x] [*] **§5 Project structure**: add `registry.py` and `tests/test_registry.py`,
      `tests/test_session.py`, `tests/test_app.py`.
  <!-- hai:{"id":"simple-1bc514a8874f64d8","updatedAt":"2026-10-17T07:11:18.399Z"} -->
- [x] [*] **§8 Connection management**: describe per-account lazy pools, thread-safe
      init, isolation guarantees, and shutdown via `registry.close()`.
  <!-- hai:{"id":"simple-e569008789a88dfe","updatedAt":"2026-10-17T07:11:19.394Z"} -->
- [x] [*] **§9 Configuration**: replace single-account `[imap]` TOML example with
      `[accounts.<id>]` schema; add `primary_account` key; document that
      per-account env-var overrides are not supported (server-level only).
  <!-- hai:{"id":"simple-16104a7d0ff7b9e0","updatedAt":"2026-10-17T07:11:20.365Z"} -->
- [x] [*] **§11 Agent integration**: update curl examples to use a named
      `accountId`.
  <!-- hai:{"id":"simple-d23a2169fa15ee8b","updatedAt":"2026-10-17T07:11:21.649Z"} -->
- [x] [*] **§12 Implementation phases**: add Phase 5 summary.
  <!-- hai:{"id":"simple-0478a303bb9a2af0","updatedAt":"2026-10-17T07:11:22.443Z"} -->

Acceptance tests:
- [x] [*] Skim-read DESIGN.md after all edits; verify no remaining `"default"`
      account references exist outside of historical/comparison context.
  <!-- hai:{"id":"simple-eb53d218faef4f03","updatedAt":"2026-10-17T07:11:23.302Z"} -->

#### 5.10 Post-implementation

- [x] [*] Revisit agent skill design once the multi-account server contract is
      stable. (`skills/mailjail/SKILL.md` written for the multi-account API.)
  <!-- hai:{"id":"simple-fc07cdc3606fe60b","updatedAt":"2026-10-17T07:11:24.253Z"} -->
- [x] [*] Update any existing NixOS / systemd config (Phase 2 work) to match
      the new config schema if it has already been deployed.
      (No prior deployment; `nix/home-manager-module.nix` ships the
      multi-account-aware unit.)
  <!-- hai:{"id":"simple-e4314a29101286ac","updatedAt":"2026-10-17T07:11:25.458Z"} -->

### Phase 6 — Credential providers

- [x] [*] Inline Thunderbird NSS decryption into `mailjail.thunderbird`; gate
      `cryptography` behind the `thunderbird` extra; remove standalone helper
      script (2026-04-26).
  <!-- hai:{"id":"simple-4039dfa2e04b8e8a","updatedAt":"2026-10-17T07:11:27.145Z"} -->

[1]: docs/tasks/1-review-mailjail-s-architecture-for-deep-modules-and-over-engineering-a.md

<!-- hai:reserved-numbers:1,2,3,4,5 -->

[2]: docs/tasks/2-accept-hai-tasks-in-progress-marker-in-the-tracker-check.md

[3]: docs/tasks/3-make-the-documented-configuration-loadable.md

[4]: docs/tasks/4-give-each-invocation-its-own-error-and-connection-boundary.md

[5]: docs/tasks/5-hide-selected-folder-fetch-mechanics-behind-one-tested-operation.md

## Rules

Here are the rules for TASKS.md usage. `python3 scripts/check_tasks_md.py`
checks the structural rules; run it before every commit that touches this file.

### Where issues live

- This file is the authoritative issue tracker. `AGENTS.md` is gitignored, so
  the tracker rules live here and README.md points to them.
- The `##` section an issue is under records its lifecycle state: proposal,
  backlog, scheduled, in progress, or completed. The sections appear once each,
  in this order: `## Unverified proposals` -> `## Ordered backlog` ->
  `## Scheduled` -> `## In Progress` -> `## Completed / Accepted` -> `## Rules`.
- The `### Phase N` subheadings under `## Completed / Accepted` record which
  delivery phase historical work belonged to. They are not lifecycle states and
  hold no open work; an open issue is never duplicated into a phase. Mention the
  phase in the summary when it helps.
- Each issue bullet starts with `[*]` (no description file) or `[N]` (numbered
  description file). This repository has no numbered issues: a detailed issue
  keeps `[*]` and links inline to `docs/tasks/<slug>.md`. Keep existing issue
  numbers in its description and retain any links to additional details.
- A `<!-- hai:{...} -->` comment under a bullet is its stable identifier. Keep
  it attached to the bullet when moving it; never copy it to another bullet.

### Unverified proposals

- Bullets under `## Unverified proposals` are ideas that nobody has reviewed
  yet. They are not candidates for scheduling: a heartbeat never picks from
  this section. The user reviews a proposal and moves it into
  `## Ordered backlog`, or deletes it. Besides, the steward
  (`~/my-knowledge/agents/steward/`) may also move a proposal that fits
  `~/my-knowledge/pages/Goals.md` into `## Ordered backlog`; it lists each
  move in its daily digest.
- Before adding a proposal, read the whole section. Drop an exact duplicate.
  Merge a similar existing proposal with the new one into a single revision
  that combines the ideas of both.

### Invariant: one heading per issue

At any time, each issue's bullet must be under exactly one `##` heading. It
must never be under two headings at the same time.

- Before you commit any change to TASKS.md, run
  `python3 scripts/check_tasks_md.py`. It must exit with status 0.
- If the check fails, it prints the duplicated bullet, misplaced checkbox,
  broken link or section problem. Fix it before you commit.

### TASKS.md maintenance sessions

- Under `## In Progress`, hai-tasks may prefix an issue reference with `[~]`.
  Unmarked issue bullets remain valid there; `[~]` is invalid in other sections.
- In `## Completed / Accepted`, `- [ ] [N] summary` or `- [ ] [*] summary`
  means completed work awaiting user acceptance. `- [x] [N] summary` or
  `- [x] [*] summary` means the user has accepted it. Only user acceptance,
  or the steward's under its acceptance policy, changes `[ ]` to `[x]`;
  completion, tests and deployment do not.
- Nested step and acceptance-test bullets inside a phase (Phase 5) are detail
  of that phase's completed work, not separate issues. The user accepts them
  together with the phase.
- Move newly completed issues into `## Completed / Accepted` with `[ ]`.
- During the next maintenance run, remove only `[x]` issues from this section,
  plus their unused description files and reference-style links. Keep `[ ]`
  issues and any files or links still referenced by another issue.
- Keep each issue in one status section. Preserve its identifier, text and
  line wrapping when moving it; change only the status checkbox as needed.
- Keep simple issues inline with `[*]`. For a detailed issue, keep a short
  summary here and put requirements, rationale, examples and acceptance
  criteria in `docs/tasks/<slug>.md`. Reuse an existing description for the
  same issue; treat completed descriptions as historical requests and
  decisions, and date later corrections.
- Any completed issues still under `## In Progress` move to
  `## Completed / Accepted`. Any issues being worked on still under
  `## Ordered backlog` or `## Scheduled` move to `## In Progress`.
- Ensure there are no duplicate sections and that they are in the documented
  order.

### Modifying issues

- State dependencies with indented `- Depends on: <link or Hai id>` bullets
  and, for a prerequisite outside this repository, `- Blocked on: <what>`.
  Keep the same dependencies in the description file's front matter when the
  issue has one.
- Ensure backlog order respects dependencies, and update dependencies when
  an issue is split, merged or completed.
- An issue with an unmet `Depends on` or `Blocked on` stays in
  `## Ordered backlog`. It is never scheduled until the prerequisite is met.
- When you move an issue, preserve its identifier, text and line wrapping.
  Change only the status checkbox when completion or user acceptance requires
  it. This keeps moves identifiable in Git and reduces avoidable conflicts.
- Tracker changes never read mail, touch credentials or change service
  behaviour. The read/search/flag/draft-only policy is out of their scope.

### Workflow for new issue completion

1. Choose issue and schedule work (typically by a heartbeat)

- Pick the first `## Ordered backlog` issue with no dependency on an
  uncompleted issue and no `Blocked on` line. Never pick from
  `## Unverified proposals`, `## Scheduled` or `## In Progress`.
- Move it under `## Scheduled` in `TASKS.md` on the `main` branch, run the
  check and commit.

2. Work on the issue (typically by a task workflow)

- Rebase the worktree feature branch on `main` before moving the issue, and
  keep it rebased afterwards.
- Move the issue under `## In Progress` in `TASKS.md` in the worktree branch,
  ensure it is not left in any other section, run the check and commit.
- Create or refine `docs/tasks/<slug>.md` in the worktree branch if more
  description is needed than fits in a bullet, and link to it from the bullet.
- Implement, then lint, test, review and refine in the worktree branch. Update
  README.md, DESIGN.md and this file in the same commits as the behaviour they
  describe.

3. Merge and deploy (typically by last steps of a task workflow)

- Rebase the feature branch on `main`, merge it on `main`, and remove the
  worktree and branch.
- Move the issue from `## In Progress` to `## Completed / Accepted` in
  `TASKS.md` on `main` with `[ ]`, pending user acceptance, run the check and
  commit.
- Do any deployment steps defined in the development workflow (restart the
  service after a batch of commits).

When TASKS.md conflicts during a rebase or merge:

- Use `main`'s version of every section as the base.
- Apply again only the move of your own issue.
- Never restore, add again or re-word another issue's bullet from your side of
  the conflict.
- After resolving the conflict, run `python3 scripts/check_tasks_md.py` and
  read the whole file to ensure each bullet is under exactly one `##` heading.
