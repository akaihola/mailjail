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

### 5.1 Config model

- [ ] Replace single-account IMAP fields in `Settings` with a named `accounts`
      table. Each account entry holds: `imap_host`, `imap_port`, `imap_ssl`,
      `imap_username`, `imap_password`, `pool_size`, `drafts_folder`, and
      credential-provider settings. Server-level settings (`server_host`,
      `server_port`) stay global.
- [ ] Add a `primary_account` server-level key (required) that names one of
      the configured accounts for `primaryAccounts` in the JMAP session.
- [ ] Update `load_settings` / TOML parsing to read the new `[accounts.<id>]`
      sections and produce a mapping of account ID → per-account config.
- [ ] Update env-var overlay (`MAILJAIL_*`) to scope per-account overrides
      (e.g. `MAILJAIL_ACCOUNTS_WORK_IMAP_HOST`) or drop env-var support for
      per-account fields – decide during TDD.
- [ ] Credential resolution (`_apply_*_credentials`) must run per account,
      using that account's provider and paths.

### 5.2 Account registry and pool lifecycle

- [ ] Introduce `AccountContext` (or similar) bundling one account's resolved
      config and its `IMAPPool`. Keyed by account ID.
- [ ] Build `AccountRegistry`: holds all `AccountContext` instances, constructed
      at startup from config. Pools created lazily on first use per account.
- [ ] Failures in one account's pool must not affect other accounts.

### 5.3 Session resource

- [ ] `session_resource()` takes the registry (or full config) instead of a
      single `Settings`. Populates `accounts` dict from all configured accounts
      and sets `primaryAccounts` from the `primary_account` config key.
- [ ] Each account advertises its own `accountCapabilities`.

### 5.4 Executor routing

- [ ] Executor receives the `AccountRegistry` instead of a single pool +
      settings pair.
- [ ] On every account-scoped method call, resolve `accountId` to an
      `AccountContext`. Return `accountNotFound` JMAP error if missing or
      omitted.
- [ ] Pass the resolved account's pool and settings into existing handlers
      (`handle_mailbox_get`, `handle_email_query`, `handle_email_get`,
      `handle_email_set`, `handle_email_submission_set`). Handler signatures
      stay largely the same – they already accept pool and settings args.

### 5.5 Handler adjustments

- [ ] Handlers already receive `pool` and `settings` as args, so no deep
      rewiring needed. Verify each handler uses the passed-in `settings`
      (e.g. `drafts_folder`) rather than any global state.
- [ ] `Email/set` create: use the account-specific `drafts_folder`.
- [ ] Intercepted `EmailSubmission/set`: use the account-specific from-address.

### 5.6 DESIGN.md update

- [ ] Update `/home/akaihola/prg/mailjail/DESIGN.md` to document the
      multi-account architecture: config schema, session structure, routing
      rules, pool lifecycle, and error handling for unknown accounts.

### 5.7 Test plan (red/green TDD throughout)

Each implementation step above is driven by writing failing tests first.
Key test scenarios:

- [ ] Config parsing: multi-account TOML produces correct per-account configs;
      missing `primary_account` is an error; credential resolution runs per
      account.
- [ ] Session resource: multiple accounts appear in `accounts`; `primaryAccounts`
      points to the configured primary; each account has correct name and
      capabilities.
- [ ] Executor routing: valid `accountId` dispatches to the right pool;
      missing `accountId` returns `accountNotFound`; unknown `accountId`
      returns `accountNotFound`.
- [ ] Per-account `Mailbox/get`, `Email/query`, `Email/get`: requests with
      different `accountId` values hit different pools/connections.
- [ ] Per-account `Email/set` and `EmailSubmission/set`: drafts go to the
      correct account's drafts folder; from-address matches the account.
- [ ] Pool isolation: a broken pool for one account does not prevent requests
      to other accounts.

### 5.8 Post-implementation

- [ ] Revisit agent skill design once the multi-account server contract is
      stable.
