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
uv sync                            # core install
uv sync --extra thunderbird        # add NSS decryption for Thunderbird auth
```

Python 3.12+ is required. Runtime dependencies: `imap_tools`, `waitress`,
`pydantic` (declared in [pyproject.toml](pyproject.toml)). The optional
`thunderbird` extra adds `cryptography>=43.0` for in-process NSS decryption.
`uv sync` also installs the `dev` dependency group (`pytest`, `pytest-mock`,
`cryptography`) needed to run the tests; pass `--no-dev` to skip it.

## Configure

Configuration is TOML, located by default at
`~/.config/mailjail/config.toml`. Each IMAP account is its own
`[accounts.<id>]` section, and `primary_account` selects which account
JMAP clients see as their default.

```toml
[server]
host = "127.0.0.1"
port = 8895

primary_account = "personal"

[accounts.personal]
host = "imap.fastmail.com"
port = 993
ssl = true
username = "me@example.com"
drafts_folder = "Drafts"

[accounts.personal.pool]
size = 3

[accounts.personal.auth]
provider = "mailjail"
password_file = "~/.config/mailjail/personal.pass"

[accounts.work]
host = "outlook.office365.com"
port = 993
ssl = true
username = "me@work.example.com"
drafts_folder = "Drafts"

[accounts.work.pool]
size = 2

[accounts.work.auth]
provider = "himalaya"
himalaya_account = "work"
```

Per-account credentials can come from a password file, a himalaya keyring
account, or a Thunderbird profile (in-process NSS decryption — install
with `--extra thunderbird`). See [DESIGN.md §9][design]. Per-account
environment-variable overrides are intentionally **not** supported; the
only env vars honoured are `MAILJAIL_SERVER_HOST` and
`MAILJAIL_SERVER_PORT`.

Thunderbird Gmail accounts are supported through OAuth2. Set `host` to
`imap.gmail.com`, `username` to the Gmail address, and `provider` to
`thunderbird` in the account's auth section. For example:

```toml
[accounts.gmail]
host = "imap.gmail.com"
username = "me@gmail.com"
drafts_folder = "[Gmail]/Drafts"

[accounts.gmail.auth]
provider = "thunderbird"
```

Include `gmail` in your existing configuration and choose `primary_account`
as usual. Thunderbird must already have authorized that account. Mailjail
matches the stored OAuth2 login by its decrypted username, decrypts its refresh
token, and exchanges it with Google before each new IMAP connection. Connections
use XOAUTH2 over verified TLS. Access tokens stay in memory. Revoked tokens
require signing in again through Thunderbird and restarting mailjail. Multiple
matching logins require narrowing the profile or removing obsolete saved logins
in Thunderbird. Password-based accounts continue to use IMAP LOGIN.

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

Run against the deployed service with plain `curl` (what the agent user
has). Account ids come from the session resource.

```sh
J='Content-Type: application/json'
U='["urn:ietf:params:jmap:core","urn:ietf:params:jmap:mail"]'

# session: accountIds and capabilities
curl -s http://127.0.0.1:8895/.well-known/jmap

# list folders for an account
curl -s http://127.0.0.1:8895/jmap -H "$J" -d '{"using":'"$U"',
  "methodCalls":[["Mailbox/get",{"accountId":"personal"},"c1"]]}'

# read the inbox: newest five messages, query + fetch in one round-trip
curl -s http://127.0.0.1:8895/jmap -H "$J" -d '{"using":'"$U"',
  "methodCalls":[
    ["Email/query",{"accountId":"personal","filter":{"inMailbox":"INBOX"},
      "sort":[{"property":"receivedAt","isAscending":false}],"limit":5},"q"],
    ["Email/get",{"accountId":"personal",
      "#ids":{"resultOf":"q","name":"Email/query","path":"/ids"},
      "properties":["id","subject","from","receivedAt","keywords","preview"]},"g"]
  ]}'
```

Expected: the session lists the configured accounts, `Mailbox/get` returns
the folder tree with `totalEmails` counts, and `Email/get` returns five
`INBOX:<uid>` emails with headers. `/healthz` reports per-account IMAP
state if something is off. Last verified 2026-10-07 against the live
service on gogo.

## Tests

```sh
uv run pytest -q
```

The suite is dependency-free (no live IMAP server required); IMAP
behaviour is exercised through `imap_tools` mocks.

## Status

Issues are tracked in [TASKS.md](TASKS.md). Proposals that nobody has
reviewed go under its `## Unverified proposals` section; only the user
promotes them to `## Ordered backlog`, and agents schedule work only from
there. The rules at the bottom of TASKS.md govern every state move, and
`python3 scripts/check_tasks_md.py` checks the file before a commit.
The checker accepts hai-tasks' `[~]` marker only under `## In Progress`;
unmarked issue bullets remain valid there. Acceptance checkboxes `[ ]` and
`[x]` belong only under `## Completed / Accepted`.

See [TASKS.md](TASKS.md) for the up-to-date implementation plan. The
multi-account core (Phase 5) and the Phase 3/4 robustness items (compound
filters, server-side SORT, capability probing, attachment downloads,
HTML→text rendering, threaded reply headers, Thread/get) are in.
The service is deployed on gogo and smoke-tested against live IMAP
accounts; see [TASKS.md](TASKS.md) for what remains.

[design]: DESIGN.md
