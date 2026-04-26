# mailjail

A capability-restricted JMAP-shaped HTTP proxy in front of IMAP. Holds the
mail credentials in a locked-down service so an AI agent (Claude Code,
pykoclaw, etc.) can read, search, flag, label and draft email — but cannot
delete, move between folders, or send.

See [DESIGN.md][design] for the full architecture, security model and
JMAP method surface. This file is the operator quick-start.

## Why

IMAP has no permission model: any client with `LOGIN` access can `EXPUNGE`,
move, or rewrite flags on every message in the account. Giving an agent
raw IMAP credentials is therefore equivalent to handing it the keys to the
mailbox. mailjail puts a small, audit-friendly gate in between:

- credentials live in the operator's account (mode 600), never in the
  agent's environment
- the HTTP surface is an explicit allowlist (`Mailbox/get`, `Email/query`,
  `Email/get`, `Email/set` with keyword-only updates, `Thread/get`,
  intercepted `EmailSubmission/set`)
- destructive operations (`Email/set destroy`, `Email/copy`, `Mailbox/set`,
  outgoing mail) are not implemented and return `forbidden`

## Install

```sh
git clone https://github.com/akaihola/mailjail
cd mailjail
uv sync
```

Python 3.12+ is required. Runtime dependencies: `imap_tools`, `waitress`,
`pydantic` (declared in [pyproject.toml](pyproject.toml)).

## Configure

Configuration is TOML, located by default at
`~/.config/mailjail/config.toml`. Each IMAP account is its own
`[accounts.<id>]` section, and `primary_account` selects which account
JMAP clients see as their default.

```toml
server_host = "127.0.0.1"
server_port = 8895
primary_account = "personal"

[accounts.personal]
imap_host = "imap.fastmail.com"
imap_port = 993
imap_ssl = true
imap_username = "me@example.com"
imap_password_file = "~/.config/mailjail/personal.pass"
drafts_folder = "Drafts"
pool_size = 3

[accounts.work]
imap_host = "outlook.office365.com"
imap_port = 993
imap_ssl = true
imap_username = "me@work.example.com"
credential_provider = "himalaya"
credential_account = "work"
drafts_folder = "Drafts"
pool_size = 2
```

Per-account credentials can come from a password file, a himalaya keyring
account, or a Thunderbird profile — see [DESIGN.md §9][design]. Per-account
environment-variable overrides are intentionally **not** supported; the
only env vars honoured are `MAILJAIL_SERVER_HOST` and
`MAILJAIL_SERVER_PORT`.

## Run

```sh
uv run python -m mailjail
```

The service binds `server_host:server_port` (default `127.0.0.1:8895`) and
exposes:

| Method | Path                                            | Purpose                          |
|--------|-------------------------------------------------|----------------------------------|
| GET    | `/.well-known/jmap`                             | session resource (RFC 8620 §2)   |
| POST   | `/jmap`                                         | method calls                     |
| GET    | `/jmap/download/{accountId}/{blobId}/{name}`    | attachment download              |
| GET    | `/healthz`                                      | per-account IMAP health          |

## Smoke test

```sh
# session
xh GET http://127.0.0.1:8895/.well-known/jmap

# list folders for the "personal" account
xh POST http://127.0.0.1:8895/jmap \
  using:='["urn:ietf:params:jmap:core","urn:ietf:params:jmap:mail"]' \
  methodCalls:='[["Mailbox/get",{"accountId":"personal"},"c1"]]'

# search and fetch in one round-trip via result references
xh POST http://127.0.0.1:8895/jmap \
  using:='["urn:ietf:params:jmap:core","urn:ietf:params:jmap:mail"]' \
  methodCalls:='[
    ["Email/query",{"accountId":"personal","filter":{"hasKeyword":"$flagged"},"limit":5},"q"],
    ["Email/get",{"accountId":"personal","#ids":{"resultOf":"q","name":"Email/query","path":"/ids"}},"g"]
  ]'
```

## Tests

```sh
uv run pytest -q
```

The suite is dependency-free (no live IMAP server required); IMAP
behaviour is exercised through `imap_tools` mocks.

## Status

See [TASKS.md](TASKS.md) for the up-to-date implementation plan. The
multi-account core (Phase 5) and the Phase 3/4 robustness items (compound
filters, server-side SORT, capability probing, attachment downloads,
HTML→text rendering, threaded reply headers, Thread/get) are in.
Outstanding work is mostly deployment glue: NixOS systemd unit, agent
SKILL.md, and a smoke test against a live server.

[design]: DESIGN.md
