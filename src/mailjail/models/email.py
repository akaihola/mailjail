"""Email model and Email/query + Email/get handlers."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..imap.connection import IMAPPool
from ..imap.fetch import (
    email_id_to_folder_uid,
    folder_uid_to_email_id,
    imap_message_to_jmap_email,
)
from ..imap.search import jmap_filter_to_imap, jmap_sort_to_imap


class EmailAddress(BaseModel):
    name: str = ""
    email: str


class BodyPart(BaseModel):
    partId: str | None = None
    blobId: str | None = None
    type: str
    name: str | None = None
    disposition: str | None = None
    charset: str | None = None


class BodyValue(BaseModel):
    value: str
    isEncodingProblem: bool = False
    isTruncated: bool = False


class Email(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    blobId: str = ""
    threadId: str = ""
    mailboxIds: dict[str, bool] = {}
    keywords: dict[str, bool] = {}
    from_: list[EmailAddress] = Field(default_factory=list, alias="from")
    to: list[EmailAddress] = Field(default_factory=list)
    cc: list[EmailAddress] = Field(default_factory=list)
    bcc: list[EmailAddress] = Field(default_factory=list)
    replyTo: list[EmailAddress] = Field(default_factory=list)
    subject: str = ""
    sentAt: str | None = None
    receivedAt: str | None = None
    size: int = 0
    preview: str = ""
    textBody: list[BodyPart] = Field(default_factory=list)
    htmlBody: list[BodyPart] = Field(default_factory=list)
    bodyValues: dict[str, BodyValue] = Field(default_factory=dict)
    hasAttachment: bool = False
    headers: list[dict[str, str]] = Field(default_factory=list)


def handle_email_query(
    args: dict[str, Any],
    pool: IMAPPool,
) -> tuple[str, dict[str, Any]]:
    """Execute Email/query.

    1. Extract inMailbox (default 'INBOX'), filter_cond, sort, limit, position.
    2. Acquire connection; mb.folder.set(folder).
    3. Build criterion via jmap_filter_to_imap(filter_cond).
    4. Call mb.uids(criterion) → list of uid strings.
    5. Apply position + limit slicing.
    6. Map uids to email IDs via folder_uid_to_email_id.
    7. Return ("Email/query", {"accountId":..., "ids":[...], "total":..., "position":...})
    """
    account_id = args["accountId"]
    filter_cond = args.get("filter", {})
    sort_spec = args.get("sort") or []
    limit = args.get("limit", 256)
    position = args.get("position", 0)

    # Extract folder from filter or default to INBOX
    folder = filter_cond.get("inMailbox", "INBOX")
    criterion = jmap_filter_to_imap(filter_cond)

    server_sort: str | None = None
    if sort_spec and pool.has_capability("SORT"):
        server_sort = jmap_sort_to_imap(sort_spec)

    with pool.connection() as mb:
        mb.folder.set(folder)
        if server_sort is not None:
            uid_list = list(mb.uids(criterion, sort=server_sort))
        else:
            uid_list = list(mb.uids(criterion))

    total = len(uid_list)

    if server_sort is None:
        # Client-side fallback: natural UID order, newest first.
        uid_list = list(reversed(uid_list))

    # Apply pagination
    sliced = uid_list[position : position + limit]
    ids = [folder_uid_to_email_id(folder, uid) for uid in sliced]

    return (
        "Email/query",
        {
            "accountId": account_id,
            "ids": ids,
            "total": total,
            "position": position,
        },
    )


def handle_email_changes(
    args: dict[str, Any],
    pool: IMAPPool,  # noqa: ARG001 — handler is intentionally state-less
) -> tuple[str, dict[str, Any]]:
    """Email/changes — always reports the cache as invalid.

    The proxy does not maintain CONDSTORE/MODSEQ state. Per RFC 8620 §5.2,
    when the server cannot compute the delta from ``sinceState`` it returns
    a ``cannotCalculateChanges`` error in the response. Clients that see
    this fall back to a fresh ``Email/query`` — which is the only correct
    behaviour we can offer without persistent per-account state.

    The state is always reported as ``"0"`` so a client whose cached state
    happens to equal ``"0"`` gets an empty (no-changes) response without
    needing to refetch.
    """
    account_id = args["accountId"]
    since_state = args.get("sinceState")
    if since_state == "0":
        return (
            "Email/changes",
            {
                "accountId": account_id,
                "oldState": "0",
                "newState": "0",
                "hasMoreChanges": False,
                "created": [],
                "updated": [],
                "destroyed": [],
            },
        )
    # Signal "you must refetch with Email/query".
    return (
        "error",
        {
            "type": "cannotCalculateChanges",
            "description": (
                "mailjail does not track per-message MODSEQ; "
                "re-issue Email/query for fresh results"
            ),
        },
    )


def handle_email_get(
    args: dict[str, Any],
    pool: IMAPPool,
) -> tuple[str, dict[str, Any]]:
    """Execute Email/get.

    1. Extract ids list (already resolved from result refs by executor).
    2. Extract properties list (None = all).
    3. Group ids by folder (parse folder:uid).
    4. For each folder group: acquire connection, mb.folder.set(folder),
       fetch messages with mark_seen=False.
    5. Map each MailMessage to JMAP Email via imap_message_to_jmap_email.
    6. Return ("Email/get", {"accountId":..., "list":[...], "notFound":[...], "state":"0"})
    """
    from imap_tools import AND

    account_id = args["accountId"]
    ids: list[str] = args.get("ids", [])
    properties: list[str] | None = args.get("properties")

    # Determine if body content is needed
    body_props = {"textBody", "htmlBody", "bodyValues", "preview", "attachments"}
    headers_only = properties is not None and not (body_props & set(properties))

    # Group ids by folder
    folder_uids: dict[str, list[str]] = {}
    not_found: list[str] = []

    for email_id in ids:
        try:
            folder, uid = email_id_to_folder_uid(email_id)
        except ValueError:
            not_found.append(email_id)
            continue
        folder_uids.setdefault(folder, []).append(uid)

    email_list: list[dict[str, Any]] = []

    for folder, uids in folder_uids.items():
        with pool.connection() as mb:
            mb.folder.set(folder)
            criteria = AND(uid=uids)
            # CRITICAL: always mark_seen=False to avoid marking messages as read
            for msg in mb.fetch(
                criteria, mark_seen=False, headers_only=headers_only, bulk=True
            ):
                try:
                    jmap_email = imap_message_to_jmap_email(msg, folder, properties)
                    email_list.append(jmap_email)
                except ValueError:
                    # msg.uid was None or other conversion error
                    pass

        # Check for IDs we requested but didn't receive
        fetched_uids = {
            e["id"].split(":")[1] for e in email_list if ":" in e.get("id", "")
        }
        for uid in uids:
            eid = folder_uid_to_email_id(folder, uid)
            if uid not in fetched_uids:
                not_found.append(eid)

    return (
        "Email/get",
        {
            "accountId": account_id,
            "list": email_list,
            "notFound": not_found,
            "state": "0",
        },
    )
