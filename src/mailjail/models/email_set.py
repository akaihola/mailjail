"""Email/set handler: keyword updates and draft creation."""

import logging
from typing import Any

from imap_tools import MailBox

from ..config import AccountSettings
from ..imap.connection import IMAPPool
from ..imap.drafts import append_draft, compose_draft
from ..imap.fetch import email_id_to_folder_uid
from ..imap.flags import jmap_keyword_to_imap

logger = logging.getLogger(__name__)


def _apply_keyword_update(
    mb: MailBox,
    folder: str,
    uid: str,
    keyword_patches: dict[str, bool],
) -> str | None:
    """Apply +/- STORE operations for each keyword patch.

    Uses mb.client.uid('STORE', ...) directly to avoid expunge() side-effect
    from mb.flag().

    Returns an error string if the operation fails, or None on success.
    """
    # folder must already be SELECTed before calling this function
    for patch_key, value in keyword_patches.items():
        # Normalise "keywords/$flagged" → "$flagged"
        if patch_key.startswith("keywords/"):
            keyword = patch_key[len("keywords/") :]
        elif patch_key.startswith("keywords"):
            keyword = patch_key[len("keywords") :]
        else:
            keyword = patch_key

        imap_flag = jmap_keyword_to_imap(keyword)
        store_op = "+FLAGS" if value else "-FLAGS"
        flag_str = f"({imap_flag})"

        try:
            typ, data = mb.client.uid("STORE", uid, store_op, flag_str)
            if typ != "OK":
                return f"STORE failed for UID {uid}: {data}"
        except Exception as exc:
            return f"STORE error for UID {uid}: {exc}"

    return None


def handle_email_set_update(
    update: dict[str, Any],  # {email_id: {keyword_patches}}
    pool: IMAPPool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply keyword updates. Returns (updated_map, not_updated_map).

    Groups updates by folder, acquires one connection per folder.
    """
    updated: dict[str, Any] = {}
    not_updated: dict[str, Any] = {}

    # Group by folder: {folder: {uid: (email_id, patches)}}
    folder_updates: dict[str, dict[str, tuple[str, dict[str, Any]]]] = {}
    for email_id, patches in update.items():
        try:
            folder, uid = email_id_to_folder_uid(email_id)
        except ValueError as exc:
            not_updated[email_id] = {"type": "notFound", "description": str(exc)}
            continue
        folder_updates.setdefault(folder, {})[uid] = (email_id, patches)

    for folder, uid_map in folder_updates.items():
        with pool.connection() as mb:
            mb.folder.set(folder)
            for uid, (email_id, patches) in uid_map.items():
                error = _apply_keyword_update(mb, folder, uid, patches)
                if error:
                    not_updated[email_id] = {
                        "type": "serverFail",
                        "description": error,
                    }
                else:
                    updated[email_id] = None  # null = success per JMAP spec

    return updated, not_updated


def handle_email_set_create(
    create: dict[str, Any],  # {create_id: email_object}
    pool: IMAPPool,
    settings: AccountSettings,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create draft messages. Returns (created_map, not_created_map).

    Validates: must have $draft keyword.
    """
    created: dict[str, Any] = {}
    not_created: dict[str, Any] = {}

    for create_id, obj in create.items():
        keywords = obj.get("keywords", {})
        if "$draft" not in keywords:
            not_created[create_id] = {
                "type": "invalidArguments",
                "description": f"create '{create_id}' must have $draft keyword",
            }
            continue

        try:
            message_bytes = compose_draft(obj, from_address=settings.imap_username)
        except Exception as exc:
            not_created[create_id] = {
                "type": "serverFail",
                "description": f"Failed to compose draft: {exc}",
            }
            continue

        try:
            with pool.connection() as mb:
                email_id = append_draft(mb, settings.drafts_folder, message_bytes)
            created[create_id] = {"id": email_id}
        except Exception as exc:
            not_created[create_id] = {
                "type": "serverFail",
                "description": f"Failed to append draft: {exc}",
            }

    return created, not_created


def handle_email_set(
    args: dict[str, Any],
    pool: IMAPPool,
    settings: AccountSettings,
) -> tuple[str, dict[str, Any]]:
    """Top-level Email/set handler.

    Policy check is done by the executor before calling this function.
    Returns ("Email/set", response_dict).
    """
    account_id = args["accountId"]

    created: dict[str, Any] = {}
    not_created: dict[str, Any] = {}
    updated: dict[str, Any] = {}
    not_updated: dict[str, Any] = {}

    if "update" in args and args["update"]:
        updated, not_updated = handle_email_set_update(args["update"], pool)

    if "create" in args and args["create"]:
        created, not_created = handle_email_set_create(args["create"], pool, settings)

    return (
        "Email/set",
        {
            "accountId": account_id,
            "created": created or None,
            "updated": updated or None,
            "destroyed": None,
            "notCreated": not_created or None,
            "notUpdated": not_updated or None,
            "notDestroyed": None,
        },
    )
