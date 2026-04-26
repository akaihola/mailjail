# mailjail Tasks

`[ ]` open · `[~]` in-progress · `[x]` done

---

## Phase 1 — Core service (MVP)

- [x] Project scaffolding (pyproject.toml, src layout, AGENTS.md, .gitignore)
- [x] Pydantic models for JMAP core (Request, Response, Invocation, error types)
- [x] Policy module (`policy.py`) with tests
- [x] IMAP connection pool (`imap_tools`, `queue.Queue`)
- [x] `Mailbox/get` — list folders
- [x] `Email/query` — search with basic filters (from, subject, date, keyword)
- [x] `Email/get` — fetch headers, preview, full body
- [x] `Email/set` update — keyword changes (star, seen, custom)
- [x] `Email/set` create — save drafts
- [x] JMAP executor: method dispatch + result references (RFC 8620 §3.7)
- [x] WSGI app (`waitress`): POST /jmap + GET /.well-known/jmap
- [x] GET /healthz endpoint
- [ ] Integration tests against IMAP mock / fixture ← Phase 2 (requires live IMAP)

## Phase 2 — Deployment & integration

- [x] Config file parsing (TOML via stdlib `tomllib`)
- [x] Credential management (password file + env var)
- [ ] NixOS systemd service definition (your user, Home Manager)
- [ ] Probe IMAP server: PERMANENTFLAGS / SORT / CONDSTORE support
- [ ] Agent skill file (`~/.claude/skills/mailjail/SKILL.md` with curl examples)
- [ ] Smoke test: agent reads inbox via curl

## Phase 3 — Robustness

- [ ] IMAP connection keepalive and reconnection
- [ ] `Email/changes` (if CONDSTORE available)
- [ ] Compound filters (AND/OR/NOT)
- [ ] SORT support (if server advertises it)
- [ ] Attachment blob download endpoint
- [ ] Structured logging

## Phase 4 — Polish

- [ ] README with setup instructions
- [ ] Draft reply helper (auto-populate In-Reply-To, References, quoted text)
- [ ] Thread view
- [ ] HTML body → plain text for agent consumption

## Phase 5 — Multi-account support

Goal: one `mailjail` server proxies multiple IMAP accounts through a single JMAP
endpoint. Every method call requires an explicit `accountId` matching a configured
account – no `"default"` alias, no implicit fallback. No backward compatibility
with old single-account configs.

Each step below is TDD: write failing tests first, then implement. The
acceptance-test matrix at the end of each section lists the required red/green
tests. Sections are ordered by dependency – implement top-to-bottom.

### 5.1 Error model (`models/core.py`)

- [ ] Add `ACCOUNT_NOT_FOUND = "accountNotFound"` to `JMAPErrorType` in
      `src/mailjail/models/core.py`.

Acceptance tests (`tests/test_models.py`):
- [ ] `JMAPErrorType.ACCOUNT_NOT_FOUND` has value `"accountNotFound"`.
- [ ] `make_error_invocation(JMAPErrorType.ACCOUNT_NOT_FOUND, ...)` produces
      `("error", {"type": "accountNotFound", ...}, call_id)`.

### 5.2 Config model (`config.py`)

- [ ] Create `AccountSettings(BaseModel)` holding per-account fields:
      `imap_host`, `imap_port`, `imap_ssl`, `imap_username`, `imap_password`,
      `pool_size`, `drafts_folder`, and all credential-provider fields
      (everything currently on `Settings` except `server_host`/`server_port`).
- [ ] Reshape `Settings` to keep only `server_host`, `server_port`,
      `primary_account: str`, and `accounts: dict[str, AccountSettings]`.
      Remove the flat IMAP fields from `Settings`.
- [ ] Update `load_settings` / `_merge_toml_into_data` to parse
      `[accounts.<id>]` TOML sections. Each section maps to one
      `AccountSettings` via the same field names the old `[imap]` section used.
- [ ] Validate that `primary_account` names an account that exists in
      `accounts`; raise on mismatch.
- [ ] Drop per-account env-var overrides. Keep only server-level env vars:
      `MAILJAIL_SERVER_HOST`, `MAILJAIL_SERVER_PORT`. Document in DESIGN.md
      that per-account configuration is TOML-only.
- [ ] Credential resolution (`_apply_mailjail_credentials`,
      `_apply_himalaya_credentials`, `_apply_thunderbird_credentials`) runs
      independently per account during `load_settings`, scoped to that
      account's provider and paths.

Acceptance tests (`tests/test_config.py`):
- [ ] Multi-account TOML parses into `Settings` with two `AccountSettings`
      entries, correct fields per account.
- [ ] Missing `primary_account` key raises `ValidationError`.
- [ ] `primary_account` naming a non-existent account raises an error.
- [ ] Each account can use a different credential provider; credentials
      resolve independently (e.g. account `work` uses himalaya, account
      `personal` uses thunderbird).
- [ ] Server-level env vars (`MAILJAIL_SERVER_HOST`, `MAILJAIL_SERVER_PORT`)
      still override TOML values.
- [ ] Old single-account TOML (no `[accounts.*]` sections) raises a clear
      error pointing to the new schema.

### 5.3 Account registry and pool lifecycle (`registry.py` – new file)

- [ ] Create `AccountContext` bundling one `AccountSettings` and its
      `IMAPPool`, keyed by account ID.
- [ ] Create `AccountRegistry` holding `dict[str, AccountContext]`. Pools
      are created lazily on first `get(account_id)` call (not at construction
      time). Thread-safe lazy init.
- [ ] `AccountRegistry.get(account_id) -> AccountContext` returns the context
      or raises `KeyError`.
- [ ] `AccountRegistry.close()` calls `pool.close()` on every materialised
      pool (for clean shutdown).
- [ ] A failing pool for one account does not prevent `get()` for other
      accounts. Subsequent `get()` for a failed account retries pool creation.

Acceptance tests (`tests/test_registry.py` – new file):
- [ ] `get("work")` returns the context for "work"; `get("unknown")` raises
      `KeyError`.
- [ ] Pool is not created until the first `get()` call for that account.
- [ ] Two `get()` calls for the same account return the same pool instance.
- [ ] `close()` calls `pool.close()` on all materialised pools.
- [ ] If pool construction fails for account A, account B is still accessible.
- [ ] After pool construction failure, a retry for the same account
      re-attempts construction.

### 5.4 Remove implicit `"default"` fallbacks from handlers

Before wiring the executor, harden every handler so it never silently
supplies a fallback `accountId`. The executor (5.5) will guarantee
`accountId` is present, but defense-in-depth means handlers must not mask
routing bugs.

- [ ] `handle_mailbox_get` in `models/mailbox.py:92`: change
      `args.get("accountId", "default")` → `args["accountId"]`.
- [ ] `handle_email_query` in `models/email.py:75`: same change.
- [ ] `handle_email_get` in `models/email.py:124`: same change.
- [ ] `handle_email_set` in `models/email_set.py:144`: same change.
- [ ] `handle_email_submission_set` in `models/submission.py:32`: same change.

Acceptance tests (update existing tests in `tests/test_executor.py`,
`tests/test_models.py`, `tests/conftest.py`):
- [ ] Every handler test fixture includes an explicit `"accountId"` value.
- [ ] Calling any handler with `args` missing `"accountId"` raises `KeyError`
      (not silently returns `"default"`).

### 5.5 Executor routing (`executor.py`)

- [ ] Change `Executor.__init__` to accept `AccountRegistry` instead of
      `pool: IMAPPool, settings: Settings`.
- [ ] In `_dispatch`, before reaching any handler: extract `accountId` from
      resolved args. If absent or not a string, return `accountNotFound`.
      Call `registry.get(accountId)` – on `KeyError`, return
      `accountNotFound`.
- [ ] Pass the resolved `AccountContext.pool` and `AccountContext.settings`
      into each handler. Handler signatures remain `(args, pool)` or
      `(args, pool, settings)` – unchanged.
- [ ] `EmailSubmission/set` currently takes only `args`; extend its call site
      to also pass the resolved `AccountContext.settings` so it can use the
      account-specific `imap_username` as from-address.

Acceptance tests (`tests/test_executor.py`):
- [ ] Request with valid `accountId` dispatches to the correct pool (mock
      two registries, assert the right pool's methods are called).
- [ ] Request with missing `accountId` returns `("error",
      {"type": "accountNotFound", ...}, call_id)`.
- [ ] Request with unknown `accountId` returns `accountNotFound`.
- [ ] Two method calls in one request with different valid `accountId` values
      each use their own pool.
- [ ] Result-reference resolution still works across calls to different
      accounts.

### 5.6 Handler adjustments

- [ ] `handle_email_set_create` (`models/email_set.py`): already receives
      `settings` – verify it uses `settings.drafts_folder` and
      `settings.imap_username`. No code change expected; add test.
- [ ] `handle_email_submission_set` (`models/submission.py`): add `settings`
      parameter. Use `settings.imap_username` for logging the intercepted
      from-address. Do NOT validate that the referenced `emailId` belongs to
      the same account – intercepted submissions are fake anyway, and
      cross-account draft references are harmless because no email is sent.
      Add a code comment documenting this decision.

Acceptance tests:
- [ ] `Email/set` create for account `work` appends to `work`'s
      `drafts_folder` using `work`'s pool, with from-address
      `work`'s `imap_username` (`tests/test_imap/test_drafts.py`).
- [ ] `EmailSubmission/set` for account `work` logs `work`'s `imap_username`
      as the intercepted from-address (`tests/test_executor.py`).

### 5.7 Session resource (`session.py`)

- [ ] Change `session_resource(settings)` →
      `session_resource(settings, registry)` (or accept the full `Settings`
      with its `accounts` dict – whichever is simpler).
- [ ] Build `"accounts"` dict by iterating `settings.accounts`: each key is
      the account ID, value has `name` (from `imap_username`), `isPersonal`,
      and `accountCapabilities` with `urn:ietf:params:jmap:mail` and
      `urn:ietf:params:jmap:submission`.
- [ ] Set `"primaryAccounts"` for both `urn:ietf:params:jmap:mail` and
      `urn:ietf:params:jmap:submission` to `settings.primary_account`.

Acceptance tests (`tests/test_session.py` – new file):
- [ ] Session with two accounts: both appear in `"accounts"` with correct
      `name` and `accountCapabilities`.
- [ ] `"primaryAccounts"` values equal `settings.primary_account`.
- [ ] Single-account config: the one account appears, and
      `"primaryAccounts"` points to it.

### 5.8 Bootstrap and app layer (`__main__.py`, `app.py`)

- [ ] `main()` in `__main__.py`: call `load_settings()`, construct
      `AccountRegistry` from `settings.accounts`, construct `Executor` with
      the registry, pass `settings` and `registry` to `make_app`. Remove the
      single `IMAPPool` construction.
- [ ] `make_app` signature: accept `executor`, `registry`, and `settings`
      (drop bare `pool` parameter).
- [ ] `/.well-known/jmap` route: call `session_resource(settings, registry)`.
- [ ] `/healthz` route: iterate all accounts in the registry. Report
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
- [ ] On SIGTERM / `KeyboardInterrupt`, call `registry.close()` to drain
      all pools.

Acceptance tests (`tests/test_app.py` – new file):
- [ ] `GET /.well-known/jmap` returns multi-account session JSON with correct
      structure.
- [ ] `GET /healthz` returns per-account health status; overall `"ok"` when
      primary is healthy even if a secondary is not.
- [ ] `GET /healthz` returns `"error"` when primary account's pool is down.
- [ ] `POST /jmap` routes through executor; a valid request with a known
      `accountId` succeeds.

### 5.9 DESIGN.md update

Update `/home/akaihola/prg/mailjail/DESIGN.md` so it reflects the
multi-account architecture. Specific sections to revise:

- [ ] **§3.1 Session / capabilities**: replace the single-account
      `"default"` example JSON with a multi-account example; document
      `primaryAccounts` sourcing from `primary_account` config key.
- [ ] **§3.2 Request format**: update `"accountId": "default"` examples to
      use a named account (e.g. `"work"`).
- [ ] **§3.3 Supported methods / Email/set create + update**: note that
      `accountId` is required and validated; `accountNotFound` is returned
      for unknown accounts.
- [ ] **§3.4 Error responses**: add `accountNotFound` to the error type
      table.
- [ ] **§3.5 /healthz**: document the new per-account health response shape.
- [ ] **§5 Project structure**: add `registry.py` and `tests/test_registry.py`,
      `tests/test_session.py`, `tests/test_app.py`.
- [ ] **§8 Connection management**: describe per-account lazy pools, thread-safe
      init, isolation guarantees, and shutdown via `registry.close()`.
- [ ] **§9 Configuration**: replace single-account `[imap]` TOML example with
      `[accounts.<id>]` schema; add `primary_account` key; document that
      per-account env-var overrides are not supported (server-level only).
- [ ] **§11 Agent integration**: update curl examples to use a named
      `accountId`.
- [ ] **§12 Implementation phases**: add Phase 5 summary.

Acceptance tests:
- [ ] Skim-read DESIGN.md after all edits; verify no remaining `"default"`
      account references exist outside of historical/comparison context.

### 5.10 Post-implementation

- [ ] Revisit agent skill design once the multi-account server contract is
      stable.
- [ ] Update any existing NixOS / systemd config (Phase 2 work) to match
      the new config schema if it has already been deployed.
