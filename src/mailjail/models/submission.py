"""EmailSubmission/set handler — intercepts send requests, retains drafts."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..config import AccountSettings

logger = logging.getLogger(__name__)

INTERCEPT_NOTE = (
    "mailjail intercepted this submission: the email was NOT sent. "
    "The draft is retained in your Drafts folder for manual review and sending "
    "from your email client."
)


def handle_email_submission_set(
    args: dict[str, Any],
    settings: AccountSettings,
) -> tuple[str, dict[str, Any]]:
    """Fake EmailSubmission/set: accept the call, return a plausible response.

    No email is actually sent. The draft already stored via Email/set remains
    in the Drafts folder unchanged. The caller receives a JMAP-compliant
    'created' response so it can continue normally.

    Two extension fields are always present so agents can detect the interception
    without prior knowledge:

        mailjail:intercepted  — always True
        mailjail:message      — human/agent-readable explanation

    The referenced ``emailId`` is **not** validated against the account's pool
    or cross-checked for ownership: intercepted submissions never actually send
    anything, so a draft from a different account (or a bogus id) is harmless.
    """
    account_id = args["accountId"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    created: dict[str, Any] = {}
    not_created: dict[str, Any] = {}

    for create_id, submission in (args.get("create") or {}).items():
        email_id = submission.get("emailId")
        if not email_id:
            not_created[create_id] = {
                "type": "invalidArguments",
                "description": "emailId is required for EmailSubmission/set create",
            }
            continue

        submission_id = f"mj-{uuid.uuid4().hex[:16]}"
        created[create_id] = {"id": submission_id, "sendAt": now}
        logger.info(
            "EmailSubmission/set intercepted: account=%r from=%r create_id=%r "
            "emailId=%r → fake submission_id=%r; draft retained in Drafts folder",
            account_id,
            settings.imap_username,
            create_id,
            email_id,
            submission_id,
        )

    return (
        "EmailSubmission/set",
        {
            "accountId": account_id,
            "created": created or None,
            "updated": None,
            "destroyed": None,
            "notCreated": not_created or None,
            "notUpdated": None,
            "notDestroyed": None,
            "mailjail:intercepted": True,
            "mailjail:message": INTERCEPT_NOTE,
        },
    )
