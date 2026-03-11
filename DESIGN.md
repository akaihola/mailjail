# mailjail — Design Document

> A JMAP-shaped HTTP proxy over IMAP that restricts an AI agent to safe email
> operations: read, search, flag, label, and draft — but never delete, move,
> or send.

## 1. Problem

AI agents (Claude Code / pykoclaw) can be tremendously useful for email triage:
reading, searching, summarising, flagging important messages, drafting replies.
But giving an agent raw IMAP credentials is dangerous — IMAP has no permission
model, so any client with LOGIN access can delete, move, or EXPUNGE messages.

We need a **capability-restricted proxy** that:
- Holds the IMAP credentials in a process the agent cannot access
- Exposes only safe operations via HTTP
- Follows a real standard (JMAP) rather than inventing a bespoke API

## 2. Security model

```
┌─────────────────────┐            ┌───────────────────────────────────┐
│  agent user (ai)    │   HTTP     │  owner ($USER)                   │
│                     │───────────▶│  mailjail service                │
│  • curl localhost:  │   :8895    │                                  │
│    8895/jmap        │            │  • owns IMAP credentials         │
│  • cannot read      │            │  • owns service code             │
│    owner's files    │            │  • only exposes safe operations  │
│  • cannot modify    │            │  • runs as systemd user service  │
│    service code     │            │                                  │
└─────────────────────┘            └──────────┬────────────────────────┘
                                              │ IMAPS :993
                                              ▼
                                   ┌──────────────────────┐
                                   │  mail.example.com    │
                                   │  IMAP4rev1 over TLS  │
                                   └──────────────────────┘
```

### Boundaries

| Boundary                  | Mechanism                                              |
|---------------------------|--------------------------------------------------------|
| Credential isolation      | Credentials in `~$USER/.config/mailjail/` (mode 600)   |
| Code integrity            | Service code owned by $USER, agent cannot write        |
| Operation restriction     | HTTP API only exposes safe JMAP methods                |
| No outbound email         | No SMTP configured, no EmailSubmission endpoint        |
| Localhost only            | Binds 127.0.0.1:8895, no Tailscale/external exposure  |

### What the agent CAN do

| Action              | JMAP method                        | IMAP operation                          |
|---------------------|------------------------------------|-----------------------------------------|
| List folders        | `Mailbox/get`                      | `LIST`                                  |
| Search messages     | `Email/query`                      | `SEARCH` / `SORT`                       |
| Fetch message       | `Email/get`                        | `FETCH BODY.PEEK[]`                     |
| Star / unstar       | `Email/set` update `$flagged`      | `STORE +/-FLAGS \Flagged`               |
| Mark unread         | `Email/set` update `$seen`         | `STORE -FLAGS \Seen`                    |
| Add custom keyword  | `Email/set` update keywords        | `STORE +FLAGS $keyword`                 |
| Save draft          | `Email/set` create                 | `APPEND "Drafts" (\Draft)`             |

### What the agent CANNOT do

| Action              | JMAP method          | Why blocked                              |
|---------------------|----------------------|------------------------------------------|
| Delete messages     | `Email/set` destroy  | No endpoint exists                       |
| Move messages       | `Email/set` update mailboxIds | Not implemented               |
| Send email          | `EmailSubmission/*`  | No endpoint, no SMTP                     |
| Copy between folders| `Email/copy`         | Not implemented                          |
| Modify message body | —                    | IMAP doesn't support this anyway         |
| Access credentials  | —                    | Different OS user, file permissions      |

## 3. API design — JMAP-shaped

The service exposes a single endpoint: **`POST /jmap`**

Request and response formats follow [RFC 8620](https://www.rfc-editor.org/rfc/rfc8620)
(JMAP core) and [RFC 8621](https://www.rfc-editor.org/rfc/rfc8621) (JMAP mail),
with the subset of methods listed below.

### 3.1 Session / capabilities

`GET /.well-known/jmap` returns session metadata per RFC 8620 §2:

```json
{
  "capabilities": {
    "urn:ietf:params:jmap:core": {
      "maxSizeUpload": 10485760,
      "maxCallsInRequest": 16,
      "maxObjectsInGet": 500,
      "maxObjectsInSet": 100
    },
    "urn:ietf:params:jmap:mail": {}
  },
  "accounts": {
    "default": {
      "name": "user@example.com",
      "isPersonal": true,
      "accountCapabilities": {
        "urn:ietf:params:jmap:mail": {}
      }
    }
  },
  "primaryAccounts": {
    "urn:ietf:params:jmap:mail": "default"
  },
  "apiUrl": "/jmap",
  "uploadUrl": "/jmap/upload/{accountId}/",
  "downloadUrl": "/jmap/download/{accountId}/{blobId}/{name}",
  "state": "0"
}
```

Note: `urn:ietf:params:jmap:submission` is deliberately absent — the service
cannot send email.

### 3.2 Request format

```json
{
  "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
  "methodCalls": [
    ["Email/query", {
      "accountId": "default",
      "filter": { "from": "hetzner", "after": "2026-02-01T00:00:00Z" },
      "sort": [{ "property": "receivedAt", "isAscending": false }],
      "limit": 10
    }, "call-0"],
    ["Email/get", {
      "accountId": "default",
      "#ids": { "resultOf": "call-0", "name": "Email/query", "path": "/ids" },
      "properties": ["from", "subject", "receivedAt", "preview", "keywords", "mailboxIds"]
    }, "call-1"]
  ]
}
```

### 3.3 Supported methods

#### Mailbox/get

Returns list of mailboxes (IMAP folders).

**Properties**: `id`, `name`, `parentId`, `role` (inbox, drafts, sent, trash, junk, archive),
`totalEmails`, `unreadEmails`, `totalThreads`, `unreadThreads`.

**IMAP mapping**: `LIST` + `STATUS` for counts.

#### Email/query

Search and filter messages. Returns ordered list of email IDs.

**Filter properties** (RFC 8621 §4.4.1):
- `inMailbox` — folder ID
- `from`, `to`, `cc`, `bcc` — address substring
- `subject` — subject substring
- `body` — full-text body search (IMAP `BODY` search key)
- `after`, `before` — date range (maps to IMAP `SINCE`/`BEFORE`)
- `hasKeyword`, `notKeyword` — filter by flag/keyword
- `header` — raw header filter

**Sort properties**: `receivedAt`, `from`, `subject`, `size`.

**IMAP mapping**: `SEARCH` or `SORT` (if server supports SORT extension).

#### Email/get

Fetch one or more messages by ID.

**Properties**: `id`, `blobId`, `threadId`, `mailboxIds`, `keywords`,
`from`, `to`, `cc`, `bcc`, `replyTo`, `subject`, `sentAt`, `receivedAt`,
`size`, `preview`, `bodyStructure`, `bodyValues`, `textBody`, `htmlBody`,
`attachments`, `hasAttachment`, `headers`.

**`fetchTextBodyValues`**: When true, include plain text body content.
**`fetchHTMLBodyValues`**: When true, include HTML body content.
**`maxBodyValueBytes`**: Truncate body values to this size.

**IMAP mapping**: `FETCH` with `BODY.PEEK[]` (PEEK to avoid setting \Seen).

#### Email/set (restricted)

Only two operations are permitted:

**1. Create (drafts only)**

```json
["Email/set", {
  "accountId": "default",
  "create": {
    "draft-1": {
      "mailboxIds": { "DRAFTS_FOLDER_ID": true },
      "keywords": { "$draft": true },
      "from": [{ "email": "user@example.com" }],
      "to": [{ "email": "recipient@example.com" }],
      "subject": "Re: Invoice #1234",
      "textBody": [{ "partId": "1", "type": "text/plain" }],
      "bodyValues": { "1": { "value": "Draft body text here..." } },
      "headers": [
        { "name": "In-Reply-To", "value": "<original-message-id>" }
      ]
    }
  }
}, "call-0"]
```

**Validation rules:**
- `mailboxIds` must contain exactly one key, and it must be the Drafts folder
- `keywords` must include `$draft`
- The service composes the message using `email.message.EmailMessage` and
  calls `IMAP APPEND` to the Drafts folder with `\Draft` flag

**2. Update (keywords only)**

```json
["Email/set", {
  "accountId": "default",
  "update": {
    "msg-uid-12345": {
      "keywords/$flagged": true,
      "keywords/$seen": false,
      "keywords/needs-reply": true
    }
  }
}, "call-0"]
```

**Validation rules:**
- Only `keywords/*` patch paths are accepted
- `mailboxIds` changes are rejected (no move/copy)
- Standard JMAP keyword mapping:
  - `$flagged` ↔ IMAP `\Flagged` (star)
  - `$seen` ↔ IMAP `\Seen` (read/unread)
  - `$answered` ↔ IMAP `\Answered`
  - `$draft` ↔ IMAP `\Draft`
  - Any other keyword ↔ IMAP custom keyword (if server supports `PERMANENTFLAGS \*`)

**Explicitly blocked:**
- `destroy` key in Email/set → 403 error
- `mailboxIds` in update → 403 error

#### Email/changes (optional, Phase 2)

Track mailbox changes since a given state string. Useful for polling-based sync.

**IMAP mapping**: `CONDSTORE` / `HIGHESTMODSEQ` if server supports it.

### 3.4 Error responses

Follow JMAP error format (RFC 8620 §3.6.1):

```json
{
  "methodResponses": [
    ["error", {
      "type": "forbidden",
      "description": "Email/set destroy is not permitted by this proxy"
    }, "call-0"]
  ]
}
```

Error types used:
- `forbidden` — operation blocked by policy (destroy, move, send)
- `invalidArguments` — malformed request
- `serverFail` — IMAP backend error
- `notFound` — message ID not found
- `tooLarge` — request exceeds limits

### 3.5 Convenience endpoint (non-JMAP)

For simple agent use (avoid verbose JMAP envelope for common operations):

`GET /healthz` — service health check, returns `{"status": "ok", "imap": "connected"}`

All other operations go through `POST /jmap` with standard JMAP request format.

## 4. Technology stack

```
┌─────────────────────────────────────────────────┐
│  HTTP layer: waitress (WSGI)                    │
│  • Production-grade threaded WSGI server        │
│  • Zero dependencies, pure Python               │
│  • Thread pool matches sync imap_tools perfectly │
│  • Routes: POST /jmap, GET /.well-known/jmap,   │
│    GET /healthz                                  │
├─────────────────────────────────────────────────┤
│  JMAP executor                                  │
│  • Method dispatch (allowlist-based)             │
│  • Result references (RFC 8620 §3.7)            │
│  • Request validation                           │
│  • Policy enforcement (block destroy/move/send) │
├─────────────────────────────────────────────────┤
│  Data models: Pydantic v2                       │
│  • Email, Mailbox, FilterCondition, etc.        │
│  • Request/Response envelope                    │
│  • Strict validation, JSON serialization        │
├─────────────────────────────────────────────────┤
│  IMAP backend: imap_tools                       │
│  • Connection pooling                           │
│  • Search / fetch / flag / append               │
│  • IMAP ↔ JMAP data translation                │
├─────────────────────────────────────────────────┤
│  Draft composer: email.message (stdlib)          │
│  • MIME message construction                    │
│  • Proper headers (In-Reply-To, References)     │
│  • UTF-8 text/plain and text/html               │
└─────────────────────────────────────────────────┘
```

### Dependencies

| Package        | Version  | Purpose                    | License    | Transitive deps |
|----------------|----------|----------------------------|------------|-----------------|
| `imap_tools`   | >=1.9    | IMAP backend               | Apache-2.0 | 0               |
| `waitress`     | >=3.0    | WSGI HTTP server           | ZPL-2.1    | 0               |
| `pydantic`     | >=2.0    | Data models & validation   | MIT        | 4               |
| (stdlib)       | —        | `email.message`, `json`    | —          | —               |

Total: **7 installed packages** (imap_tools, waitress, pydantic + 4 pydantic
transitive deps: annotated-types, pydantic-core, typing-extensions,
typing-inspection). No async runtime, no C extensions required.

### Why waitress?

- **Zero dependencies** — pure Python, nothing to break
- **Threaded** — default 4-worker thread pool, natural match for synchronous
  imap_tools (no `run_in_threadpool` gymnastics needed)
- **Production-grade** — backs the Pyramid framework, used by Mozilla, ~8M
  PyPI downloads/month
- **Cross-platform** — pure Python, no fork(), works on NixOS without issues
- **Minimal** — no middleware, no routing framework, no magic. The WSGI
  callable is a plain function

### Python version

3.12+ (NixOS Python on the target host).

### Packaging

PEP 723 inline script metadata is not suitable for a multi-file project.
Use a standard `pyproject.toml` with `uv` for development:

```toml
[project]
name = "mailjail"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "imap_tools>=1.9",
    "waitress>=3.0",
    "pydantic>=2.0",
]
```

## 5. Project structure

```
mailjail/
├── pyproject.toml
├── DESIGN.md               ← this file
├── README.md
├── CLAUDE.md               ← repo-specific agent instructions
├── src/
│   └── mailjail/
│       ├── __init__.py
│       ├── __main__.py      ← waitress entry point
│       ├── app.py           ← WSGI application, routing
│       ├── config.py        ← Settings (host, port, IMAP server, credentials path)
│       ├── executor.py      ← JMAP request executor (dispatch, result refs, policy)
│       ├── policy.py        ← Allowlist of permitted operations
│       ├── models/
│       │   ├── __init__.py
│       │   ├── core.py      ← JMAP core: Request, Response, Invocation, error types
│       │   ├── mailbox.py   ← Mailbox model + Mailbox/get handler
│       │   ├── email.py     ← Email model + Email/query, Email/get handlers
│       │   └── email_set.py ← Email/set: create (drafts) + update (keywords)
│       ├── imap/
│       │   ├── __init__.py
│       │   ├── connection.py ← Connection pool, login, keepalive
│       │   ├── search.py     ← JMAP filter → IMAP SEARCH translation
│       │   ├── fetch.py      ← IMAP FETCH → JMAP Email translation
│       │   ├── flags.py      ← JMAP keywords ↔ IMAP flags mapping
│       │   └── drafts.py     ← Draft composition + IMAP APPEND
│       └── session.py       ← /.well-known/jmap session resource
└── tests/
    ├── conftest.py
    ├── test_executor.py     ← Policy enforcement tests
    ├── test_policy.py       ← Allowlist unit tests
    ├── test_models.py       ← Pydantic model validation
    └── test_imap/
        ├── test_search.py   ← Filter → SEARCH translation
        ├── test_flags.py    ← Keyword ↔ flag mapping
        └── test_drafts.py   ← Draft composition
```

## 6. Policy enforcement (`policy.py`)

The policy module is the security core. It is deliberately simple and auditable:

```python
"""mailjail operation policy — allowlist-based."""

# Methods that are unconditionally allowed
ALLOWED_METHODS: frozenset[str] = frozenset({
    "Mailbox/get",
    "Email/query",
    "Email/get",
    "Email/changes",       # Phase 2
})

# Methods with restricted sub-operations
RESTRICTED_METHODS: frozenset[str] = frozenset({
    "Email/set",
})

# Permanently blocked — these methods never exist
BLOCKED_METHODS: frozenset[str] = frozenset({
    "Email/copy",
    "EmailSubmission/set",
    "EmailSubmission/get",
    "EmailSubmission/query",
    "EmailSubmission/changes",
    "Identity/get",
    "Identity/set",
    "VacationResponse/get",
    "VacationResponse/set",
    "Mailbox/set",           # no folder create/delete/rename
    "Mailbox/changes",
    "Thread/get",            # Phase 2 maybe
    "Thread/changes",
})


def check_email_set(args: dict) -> list[str]:
    """Validate Email/set arguments. Returns list of violations."""
    violations = []
    if "destroy" in args:
        violations.append("Email/set destroy is forbidden")
    for uid, patch in args.get("update", {}).items():
        for key in patch:
            if not key.startswith("keywords/"):
                violations.append(
                    f"Email/set update only allows keywords/* patches, "
                    f"got '{key}' for message {uid}"
                )
    for create_id, obj in args.get("create", {}).items():
        mailbox_ids = obj.get("mailboxIds", {})
        keywords = obj.get("keywords", {})
        if "$draft" not in keywords:
            violations.append(
                f"Email/set create '{create_id}' must include $draft keyword"
            )
        # Mailbox ID validation (must be Drafts) happens at runtime
        # when we know the actual Drafts folder ID
    return violations
```

## 7. IMAP ↔ JMAP mapping details

### 7.1 Message IDs

JMAP uses opaque string IDs. We map directly: **JMAP email ID = IMAP UID as string**.
Folder-scoped (INBOX UID 42 → ID `"INBOX:42"`).

### 7.2 Mailbox IDs

JMAP mailbox ID = IMAP folder name (URL-encoded if needed).

### 7.3 Keywords ↔ Flags

| JMAP keyword  | IMAP flag       | Notes                        |
|---------------|-----------------|------------------------------|
| `$seen`       | `\Seen`         | Standard                     |
| `$flagged`    | `\Flagged`      | Star                         |
| `$answered`   | `\Answered`     | Standard                     |
| `$draft`      | `\Draft`        | Standard                     |
| `$forwarded`  | `$Forwarded`    | Common convention            |
| (any other)   | (same string)   | Custom keyword, if supported |

### 7.4 Filter → SEARCH translation

| JMAP filter property | IMAP SEARCH key                     |
|----------------------|-------------------------------------|
| `inMailbox`          | `SELECT` the folder first           |
| `from`               | `FROM "value"`                      |
| `to`                 | `TO "value"`                        |
| `subject`            | `SUBJECT "value"`                   |
| `body`               | `BODY "value"`                      |
| `after`              | `SINCE dd-Mon-yyyy`                 |
| `before`             | `BEFORE dd-Mon-yyyy`               |
| `hasKeyword`         | `KEYWORD $value` or `FLAGGED` etc.  |
| `notKeyword`         | `UNKEYWORD $value`                  |
| `minSize`            | `LARGER n`                          |
| `maxSize`            | `SMALLER n`                         |

Compound filters: JMAP `operator: "AND"/"OR"/"NOT"` map to IMAP search
logic operators.

## 8. Connection management

Both imap_tools and waitress are synchronous and threaded — a natural match.
Each waitress worker thread can use an IMAP connection directly without
async/sync bridging.

Connection pooling: maintain a small pool (2-4 connections) using a
`queue.Queue`. Each request borrows a connection, uses it, returns it.
Connections are validated with NOOP before reuse, reconnected if stale.

```python
import queue
from contextlib import contextmanager
from imap_tools import MailBox

class IMAPPool:
    def __init__(self, host: str, user: str, password: str, size: int = 3):
        self._pool: queue.Queue[MailBox] = queue.Queue(maxsize=size)
        for _ in range(size):
            mb = MailBox(host).login(user, password)
            self._pool.put(mb)

    @contextmanager
    def connection(self):
        mb = self._pool.get(timeout=30)
        try:
            mb.client.noop()  # validate connection
            yield mb
        except Exception:
            # reconnect on failure
            mb = MailBox(self._host).login(self._user, self._password)
            raise
        finally:
            self._pool.put(mb)
```

waitress's default thread pool size (4) aligns well with a pool of 3 IMAP
connections — one thread can always serve /healthz without waiting for IMAP.

## 9. Configuration

```toml
# ~/.config/mailjail/config.toml (owned by $USER, mode 600)

[server]
host = "127.0.0.1"
port = 8895

[imap]
host = "mail.example.com"
port = 993
ssl = true
username = "user@example.com"
# password from explicit config, password file, env var, Himalaya, or Thunderbird

[imap.pool]
size = 3
idle_timeout = 300  # seconds

[imap.auth]
provider = "auto"  # mailjail | env | password-file | himalaya | thunderbird | auto
himalaya_config_path = "~/.config/himalaya/config.toml"
himalaya_account = "myaccount"
thunderbird_dir = "~/.thunderbird"
# Optional explicit profile name if not using the default Thunderbird profile
# thunderbird_profile = "abcd.default-release"
# Helper command receives ${profile}, ${logins_json}, ${key4_db}, ${origin}, ${hostname},
# ${encrypted_username}, ${encrypted_password} and must print the decrypted password.
thunderbird_helper_cmd = '''python3 ~/.local/bin/mailjail-thunderbird-password \
  --profile ${profile} --logins-json ${logins_json} --key4-db ${key4_db} \
  --origin ${origin}'''
# Optional hints to choose among multiple Thunderbird logins
# thunderbird_hostname_hint = "mail.example.com"
# thunderbird_username_hint = "user@example.com"

[policy]
# Override default allowed keywords (optional)
# allowed_custom_keywords = ["needs-reply", "agent-triaged", "low-priority"]
```

Credential resolution order:
- `provider = "mailjail"` / `"auto"`: explicit `imap.password`, `MAILJAIL_IMAP_PASSWORD`, then `~/.config/mailjail/password`
- `provider = "himalaya"` / `"auto"`: parse Himalaya config (`auth.raw` or `auth.cmd`)
- `provider = "thunderbird"` / `"auto"`: discover Thunderbird profile/login metadata, then invoke the configured helper command to decrypt and print the password

Thunderbird note: mailjail does **not** implement NSS decryption internally. Instead it provides a stable provider interface that discovers the right profile/login and calls a local helper script/tool, keeping NSS-specific logic outside the main service.

## 10. Deployment

### NixOS / Home Manager (your user)

Add to your Home Manager config (or a separate $USER service
config — depending on Home Manager setup for that user):

```nix
systemd.user.services.mailjail = {
  Unit = {
    Description = "mailjail — JMAP-shaped read-only IMAP proxy";
    After = [ "network.target" ];
  };
  Service = {
    Type = "simple";
    ExecStart = "%h/prg/mailjail/.venv/bin/python -m mailjail";
    WorkingDirectory = "%h/prg/mailjail";
    EnvironmentFile = "-%h/.config/mailjail/env";
    Restart = "on-failure";
    RestartSec = 10;
  };
  Install = {
    WantedBy = [ "default.target" ];
  };
};
```

### Port selection

Port **8895** — chosen to avoid conflicts with common development ports.
Localhost-only, no Tailscale Serve needed (agent and service are on the same
machine).

## 11. Agent integration

A pykoclaw skill at `~/.claude/skills/mailjail/SKILL.md` will teach agents how
to call the API:

```markdown
## Email access via mailjail

You can read, search, flag, and draft emails using the mailjail JMAP proxy
at http://127.0.0.1:8895/jmap.

### Quick examples

List folders:
  curl -s -X POST http://127.0.0.1:8895/jmap -H 'Content-Type: application/json' \
    -d '{"using":["urn:ietf:params:jmap:core","urn:ietf:params:jmap:mail"],
         "methodCalls":[["Mailbox/get",{"accountId":"default"},""]]}'

Search recent from hetzner:
  curl -s -X POST ... -d '{"using":[...],"methodCalls":[
    ["Email/query",{"accountId":"default","filter":{"from":"hetzner"},"limit":5},"q"],
    ["Email/get",{"accountId":"default","#ids":{"resultOf":"q","name":"Email/query","path":"/ids"},
     "properties":["from","subject","receivedAt","preview"]},"g"]]}'

Star a message:
  curl -s -X POST ... -d '{"using":[...],"methodCalls":[
    ["Email/set",{"accountId":"default","update":{"INBOX:42":{"keywords/$flagged":true}}},"s"]]}'

Save a draft:
  curl -s -X POST ... -d '{"using":[...],"methodCalls":[
    ["Email/set",{"accountId":"default","create":{"d1":{
     "mailboxIds":{"Drafts":true},"keywords":{"$draft":true},
     "from":[{"email":"user@example.com"}],"to":[{"email":"recipient@example.com"}],
     "subject":"Re: Topic","textBody":[{"partId":"1","type":"text/plain"}],
     "bodyValues":{"1":{"value":"Draft text..."}}}}},"d"]]}'
```

## 12. Implementation phases

### Phase 1 — Core service (MVP)

- [ ] Project scaffolding (pyproject.toml, src layout, CLAUDE.md)
- [ ] Pydantic models for JMAP core (Request, Response, Invocation)
- [ ] Policy module with tests
- [ ] IMAP connection pool using imap_tools
- [ ] `Mailbox/get` — list folders
- [ ] `Email/query` — search with basic filters (from, subject, date, keyword)
- [ ] `Email/get` — fetch headers, preview, full body
- [ ] `Email/set` update — keyword changes (star, seen, custom)
- [ ] `Email/set` create — save drafts
- [ ] JMAP executor with method dispatch and result references
- [ ] WSGI app (waitress) with POST /jmap and GET /.well-known/jmap
- [ ] GET /healthz endpoint
- [ ] Integration tests against a local IMAP fixture (or mock)

### Phase 2 — Deployment & integration

- [ ] Config file parsing (TOML)
- [ ] Credential management (password file + env var)
- [ ] NixOS systemd service definition (your user)
- [ ] Probe IMAP server for PERMANENTFLAGS / SORT / CONDSTORE support
- [ ] Agent skill file (SKILL.md with curl examples)
- [ ] Smoke test: agent reads inbox via curl

### Phase 3 — Robustness

- [ ] IMAP connection keepalive and reconnection
- [ ] Email/changes (if CONDSTORE available)
- [ ] Compound filters (AND/OR/NOT)
- [ ] SORT support (if server advertises it)
- [ ] Attachment blob download endpoint
- [ ] Rate limiting (optional)
- [ ] Structured logging

### Phase 4 — Polish

- [ ] README with setup instructions
- [ ] Draft reply helper (auto-populate In-Reply-To, References, quoted text)
- [ ] Thread view (group by References/In-Reply-To header chain)
- [ ] HTML body rendering to plain text for agent consumption
- [ ] PyPI publish (if useful to others)

## 13. Open decisions

- [ ] **IMAP server PERMANENTFLAGS**: Do custom keywords work? Must probe before
  relying on them. Fallback: folder-based labeling.
- [ ] **Email client keyword visibility**: Which client does the user use?
  Thunderbird shows IMAP keywords as tags. Apple Mail mostly ignores them.
  Mail provider webmail behaviour unknown.
- [ ] **Authentication on HTTP API**: Currently none (localhost-only).
  Could add a bearer token for defense-in-depth if desired.
- [ ] **Result references**: Full RFC 8620 §3.7 support (JSON pointers into
  previous responses) is powerful but complex. MVP could skip and require
  explicit IDs.

## 14. Reference material

### Studied implementations

| Project | What we take from it |
|---------|---------------------|
| [filiphanes/jmap-proxy-python](https://github.com/filiphanes/jmap-proxy-python) | JMAP↔IMAP translation patterns |
| [miracle2k/jmap-python](https://github.com/miracle2k/jmap-python) | SansIO executor design, result reference resolution |
| [jmapc](https://github.com/smkent/jmapc) | Pydantic data models for JMAP objects |

### Standards

| RFC | Title |
|-----|-------|
| [RFC 8620](https://www.rfc-editor.org/rfc/rfc8620) | JMAP core protocol |
| [RFC 8621](https://www.rfc-editor.org/rfc/rfc8621) | JMAP for Mail |
| [RFC 3501](https://www.rfc-editor.org/rfc/rfc3501) | IMAP4rev1 |
| [RFC 7162](https://www.rfc-editor.org/rfc/rfc7162) | CONDSTORE / QRESYNC extensions |

### Libraries

| Library | Role |
|---------|------|
| [imap_tools](https://github.com/ikvk/imap_tools) | IMAP backend (810 stars, Apache-2.0) |
| [waitress](https://docs.pylonsproject.org/projects/waitress/) | WSGI server (zero deps, threaded, production-grade) |
| [Pydantic v2](https://docs.pydantic.dev/) | Data validation & models |
