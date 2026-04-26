---
name: mailjail
description: Read, search, flag, label and draft email through the local mailjail JMAP proxy. Use when the user asks anything about their inbox, recent mail, drafting a reply, triaging, starring/unstarring or labelling messages. Never attempt to delete, move, or send — the proxy will refuse.
---

# mailjail

`mailjail` is a JMAP-shaped HTTP proxy that holds the user's IMAP
credentials so this agent can work with their mail without ever seeing
the password. It listens on `http://127.0.0.1:8895` (override with
`$MAILJAIL_URL`).

The proxy is a strict allowlist:

| You CAN                                           | You CANNOT                            |
|---------------------------------------------------|---------------------------------------|
| List folders (`Mailbox/get`)                      | Delete a message                      |
| Search (`Email/query`, with AND/OR/NOT filters)   | Move messages between folders         |
| Fetch headers, body, preview (`Email/get`)        | Send mail (submission is intercepted) |
| Star / unstar / mark unread / add custom keywords | Create, rename, or remove folders     |
| Save a draft (`Email/set` create with `$draft`)   | Modify message contents in place      |
| Group messages by thread (`Thread/get`)           | Read another OS user's files          |

Submitted email never leaves the machine — `EmailSubmission/set` is
intercepted, the draft is retained, and the response carries
`mailjail:intercepted: true`.

## Discover the available accounts

```sh
xh GET http://127.0.0.1:8895/.well-known/jmap
```

The `accounts` map gives every configured `accountId`; `primaryAccounts`
tells you which one to default to. **Every JMAP method call must include
`accountId`** — there is no implicit default and unknown accounts return
`accountNotFound`.

## Patterns

### Get the most recent flagged messages

```sh
xh POST http://127.0.0.1:8895/jmap \
  using:='["urn:ietf:params:jmap:core","urn:ietf:params:jmap:mail"]' \
  methodCalls:='[
    ["Email/query", {
        "accountId": "personal",
        "filter": {"hasKeyword": "$flagged"},
        "sort": [{"property": "receivedAt", "isAscending": false}],
        "limit": 20
    }, "q"],
    ["Email/get", {
        "accountId": "personal",
        "#ids": {"resultOf": "q", "name": "Email/query", "path": "/ids"},
        "properties": ["from","subject","receivedAt","preview"]
    }, "g"]
  ]'
```

### Search with compound filters

```json
{"operator": "AND", "conditions": [
  {"from": "boss@example.com"},
  {"operator": "OR", "conditions": [
    {"subject": "urgent"},
    {"hasKeyword": "$flagged"}
  ]},
  {"operator": "NOT", "conditions": [{"hasKeyword": "agent-triaged"}]}
]}
```

### Mark a thread `$seen` and add a custom keyword

```json
["Email/set", {
    "accountId": "personal",
    "update": {
        "INBOX:1234": {"keywords/$seen": true, "keywords/agent-triaged": true}
    }
}, "u"]
```

`Email/set update` is locked to keyword changes only. Touching
`mailboxIds`, supplying `destroy`, or omitting the `keywords/` prefix
returns `forbidden`.

### Save a draft reply

```json
["Email/set", {
    "accountId": "personal",
    "create": {
        "draft1": {
            "keywords": {"$draft": true, "$seen": true},
            "from": [{"email": "me@example.com"}],
            "to":   [{"email": "alice@example.com"}],
            "subject": "Re: Lunch",
            "inReplyTo":  ["msg-id-of-original@host"],
            "references": ["root@host", "msg-id-of-original@host"],
            "textBody": [{"partId": "1", "type": "text/plain"}],
            "bodyValues": {"1": {"value": "Sounds good — see you Friday."}}
        }
    }
}, "c"]
```

`inReplyTo` and `references` are converted to RFC 5322 `In-Reply-To` /
`References` headers automatically. The created email's id appears in the
response under `created.draft1.id` and lives in the account's drafts
folder (e.g. `Drafts:42`). The user reviews and sends it manually from
their MUA — agents must not attempt `EmailSubmission/set`.

### Download an attachment

`Email/get` with `properties` including `"attachments"` returns each
attachment's `blobId`. Fetch the bytes with:

```sh
xh GET "http://127.0.0.1:8895/jmap/download/personal/INBOX:1234:0/invoice.pdf" \
  --download
```

## Errors you'll see

| `type`             | What it means                                                |
|--------------------|--------------------------------------------------------------|
| `accountNotFound`  | `accountId` missing or not in the session resource           |
| `forbidden`        | Method or sub-operation is not on the allowlist (e.g. delete)|
| `unknownMethod`    | Method name not implemented by this proxy                    |
| `serverFail`       | IMAP error or unexpected exception — surface verbatim to user|

## Health & observability

```sh
xh GET http://127.0.0.1:8895/healthz
```

Returns per-account IMAP connectivity. The overall `status` is `ok`
only if the primary account's pool is healthy.
