"""JMAP session resource (/.well-known/jmap)."""

from typing import Any

from .config import Settings


def session_resource(settings: Settings) -> dict[str, Any]:
    """Build the /.well-known/jmap session object per RFC 8620 §2.

    One ``accounts`` entry per configured account. ``primaryAccounts`` for
    both ``urn:ietf:params:jmap:mail`` and ``urn:ietf:params:jmap:submission``
    point to ``settings.primary_account``.

    urn:ietf:params:jmap:submission is advertised but intercepted:
    EmailSubmission/set retains the draft instead of sending, and always
    returns mailjail:intercepted + mailjail:message in its response.
    """
    accounts: dict[str, Any] = {}
    for account_id, account in settings.accounts.items():
        accounts[account_id] = {
            "name": account.imap_username,
            "isPersonal": True,
            "accountCapabilities": {
                "urn:ietf:params:jmap:mail": {},
                "urn:ietf:params:jmap:submission": {},
            },
        }

    return {
        "capabilities": {
            "urn:ietf:params:jmap:core": {
                "maxSizeUpload": 10_485_760,
                "maxCallsInRequest": 16,
                "maxObjectsInGet": 500,
                "maxObjectsInSet": 100,
            },
            "urn:ietf:params:jmap:mail": {},
            "urn:ietf:params:jmap:submission": {
                "mailjail:intercepted": True,
                "mailjail:message": (
                    "EmailSubmission/set is intercepted: emails are retained "
                    "in Drafts for manual review rather than sent."
                ),
            },
        },
        "accounts": accounts,
        "primaryAccounts": {
            "urn:ietf:params:jmap:mail": settings.primary_account,
            "urn:ietf:params:jmap:submission": settings.primary_account,
        },
        "apiUrl": "/jmap",
        "uploadUrl": "/jmap/upload/{accountId}/",
        "downloadUrl": "/jmap/download/{accountId}/{blobId}/{name}",
        "state": "0",
    }
