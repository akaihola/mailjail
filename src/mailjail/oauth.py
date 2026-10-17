"""Exchange Thunderbird's Google refresh tokens without persisting access tokens."""

import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mailjail.config import CredentialError

# Tokens issued to Thunderbird must be refreshed with its public desktop identity.
# https://github.com/mozilla/releases-comm-central/blob/master/mailnews/base/src/OAuth2Providers.sys.mjs
_THUNDERBIRD_CLIENT_ID = (
    "406964657835-aq8lmia8j95dhl1a2bvharmfk3t1hgqj.apps.googleusercontent.com"
)
_THUNDERBIRD_CLIENT_SECRET = "kSmqreRr0qwBWJgbf5Y-PjSU"


def gmail_access_token(refresh_token: str) -> str:
    """Refresh for each new IMAP connection, including pool reconnections."""
    request = Request(
        "https://oauth2.googleapis.com/token",
        data=urlencode(
            {
                "client_id": _THUNDERBIRD_CLIENT_ID,
                "client_secret": _THUNDERBIRD_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("ascii"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except (URLError, OSError, ValueError):
        raise CredentialError("Gmail OAuth2 token exchange failed") from None
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not isinstance(token, str) or not token:
        raise CredentialError("Gmail OAuth2 response has no valid access token")
    return token
