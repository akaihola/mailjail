"""JMAP session resource (/.well-known/jmap)."""

from typing import Any

from .config import Settings


def session_resource(settings: Settings) -> dict[str, Any]:
    """Build the /.well-known/jmap session object per RFC 8620 §2.

    urn:ietf:params:jmap:submission is advertised but intercepted:
    EmailSubmission/set retains the draft instead of sending, and always
    returns mailjail:intercepted + mailjail:message in its response.
    """
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
        "accounts": {
            "default": {
                "name": settings.imap_username,
                "isPersonal": True,
                "accountCapabilities": {
                    "urn:ietf:params:jmap:mail": {},
                    "urn:ietf:params:jmap:submission": {},
                },
            }
        },
        "primaryAccounts": {
            "urn:ietf:params:jmap:mail": "default",
            "urn:ietf:params:jmap:submission": "default",
        },
        "apiUrl": "/jmap",
        "uploadUrl": "/jmap/upload/{accountId}/",
        "downloadUrl": "/jmap/download/{accountId}/{blobId}/{name}",
        "state": "0",
    }
