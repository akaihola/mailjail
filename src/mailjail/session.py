"""JMAP session resource (/.well-known/jmap)."""

from typing import Any

from .config import Settings


def session_resource(settings: Settings) -> dict[str, Any]:
    """Build the /.well-known/jmap session object per RFC 8620 §2.

    Note: urn:ietf:params:jmap:submission is deliberately absent —
    this service cannot send email.
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
        },
        "accounts": {
            "default": {
                "name": settings.imap_username,
                "isPersonal": True,
                "accountCapabilities": {"urn:ietf:params:jmap:mail": {}},
            }
        },
        "primaryAccounts": {"urn:ietf:params:jmap:mail": "default"},
        "apiUrl": "/jmap",
        "uploadUrl": "/jmap/upload/{accountId}/",
        "downloadUrl": "/jmap/download/{accountId}/{blobId}/{name}",
        "state": "0",
    }
