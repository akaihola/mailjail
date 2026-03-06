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
- [ ] NixOS systemd service definition (akaihola user, Home Manager)
- [ ] Probe Gandi IMAP: PERMANENTFLAGS / SORT / CONDSTORE support
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
