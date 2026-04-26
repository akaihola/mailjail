"""Thread/get handler.

Phase 4: minimal implementation that mirrors the Phase 1 simplification in
``imap.fetch.imap_message_to_jmap_email`` where ``threadId == emailId``.
Each thread therefore always contains exactly one email — its id is the
emailId. Real conversation grouping (References / In-Reply-To walking) is
out of scope for this proxy.
"""

from typing import Any

from ..imap.connection import IMAPPool


def handle_thread_get(
    args: dict[str, Any],
    pool: IMAPPool,  # noqa: ARG001 — pool unused in the simplified mapping
) -> tuple[str, dict[str, Any]]:
    """Return one-element threads for each requested threadId."""
    account_id = args["accountId"]
    ids: list[str] = args.get("ids") or []
    threads = [{"id": tid, "emailIds": [tid]} for tid in ids]
    return (
        "Thread/get",
        {
            "accountId": account_id,
            "list": threads,
            "notFound": [],
            "state": "0",
        },
    )
