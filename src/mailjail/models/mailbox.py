"""Mailbox model and Mailbox/get handler."""

from typing import Any

from pydantic import BaseModel

from ..imap.connection import IMAPPool

# Well-known folder name → JMAP role mapping (case-insensitive last component match)
FOLDER_ROLES: dict[str, str] = {
    "inbox": "inbox",
    "drafts": "drafts",
    "sent": "sent",
    "trash": "trash",
    "junk": "junk",
    "spam": "junk",
    "archive": "archive",
}


class Mailbox(BaseModel):
    id: str
    name: str
    parentId: str | None = None
    role: str | None = None
    totalEmails: int = 0
    unreadEmails: int = 0
    totalThreads: int = 0
    unreadThreads: int = 0
    myRights: dict[str, bool] = {}
    isSubscribed: bool = True


def imap_folder_to_jmap_mailbox(
    folder_info: Any,  # imap_tools FolderInfo
    status: dict[str, int],
) -> Mailbox:
    """Build a Mailbox from a FolderInfo + STATUS dict.

    Sets parentId by splitting on FolderInfo.delim.
    Assigns role from FOLDER_ROLES (case-insensitive last component match).
    """
    name = folder_info.name
    delim = folder_info.delim

    # Compute parentId from hierarchy
    parent_id: str | None = None
    if delim and delim in name:
        parent_part = name.rsplit(delim, 1)[0]
        parent_id = parent_part if parent_part else None

    # Determine role from last component (case-insensitive)
    last_component = name.rsplit(delim, 1)[-1] if (delim and delim in name) else name
    role = FOLDER_ROLES.get(last_component.lower())

    total = status.get("MESSAGES", 0)
    unseen = status.get("UNSEEN", 0)

    return Mailbox(
        id=name,
        name=last_component,
        parentId=parent_id,
        role=role,
        totalEmails=total,
        unreadEmails=unseen,
        totalThreads=total,
        unreadThreads=unseen,
        myRights={
            "mayReadItems": True,
            "mayAddItems": True,
            "mayRemoveItems": False,
            "maySetSeen": True,
            "maySetKeywords": True,
            "mayCreateChild": False,
            "mayRename": False,
            "mayDelete": False,
            "maySubmit": False,
        },
        isSubscribed=True,
    )


def handle_mailbox_get(
    args: dict[str, Any],
    pool: IMAPPool,
) -> tuple[str, dict[str, Any]]:
    """Execute Mailbox/get. Returns ("Mailbox/get", response_dict).

    Lists all folders via mb.folder.list(), fetches STATUS for each,
    filters by args["ids"] if present.
    """
    account_id = args.get("accountId", "default")
    requested_ids: list[str] | None = args.get("ids")

    with pool.connection() as mb:
        folders = mb.folder.list()
        mailboxes: list[dict[str, Any]] = []
        not_found: list[str] = []

        for folder_info in folders:
            folder_name = folder_info.name
            # Skip if filtering by IDs and this folder is not in the list
            if requested_ids is not None and folder_name not in requested_ids:
                continue
            try:
                status = mb.folder.status(folder_name)
            except Exception:
                status = {}
            mailbox = imap_folder_to_jmap_mailbox(folder_info, status)
            mailboxes.append(mailbox.model_dump(exclude_none=True))

        if requested_ids is not None:
            found_ids = {m["id"] for m in mailboxes}
            not_found = [i for i in requested_ids if i not in found_ids]

    return (
        "Mailbox/get",
        {
            "accountId": account_id,
            "list": mailboxes,
            "notFound": not_found,
            "state": "0",
        },
    )
