"""Gmail refresh-token exchange and IMAP authentication."""

import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs

import pytest

from mailjail.config import AccountSettings, CredentialError
from mailjail.imap.connection import IMAPPool
from mailjail.registry import _default_pool_factory


def test_refresh_token_exchange() -> None:
    from mailjail.oauth import gmail_access_token

    with patch("mailjail.oauth.urlopen") as request:
        request.return_value.__enter__.return_value.read.return_value = json.dumps(
            {"access_token": "access", "token_type": "Bearer"}
        ).encode()
        assert gmail_access_token("refresh+secret") == "access"
    args, kwargs = request.call_args
    assert args[0].full_url == "https://oauth2.googleapis.com/token"
    assert args[0].get_header("Content-type") == "application/x-www-form-urlencoded"
    form = parse_qs(args[0].data.decode())
    assert form["refresh_token"] == ["refresh+secret"]
    assert form["grant_type"] == ["refresh_token"]
    assert form["client_id"] == [
        "406964657835-aq8lmia8j95dhl1a2bvharmfk3t1hgqj.apps.googleusercontent.com"
    ]
    assert form["client_secret"]
    assert kwargs["timeout"] == 30


@pytest.mark.parametrize(
    "payload",
    [b"bad JSON", b"[]", b"{}", b'{"access_token": ""}', b'{"access_token": 42}'],
)
def test_bad_token_response(payload: bytes) -> None:
    from mailjail.oauth import gmail_access_token

    with patch("mailjail.oauth.urlopen") as request:
        request.return_value.__enter__.return_value.read.return_value = payload
        with pytest.raises(CredentialError, match="Gmail OAuth2"):
            gmail_access_token("refresh")


@pytest.mark.parametrize(
    "error",
    [
        URLError("secret"),
        TimeoutError("secret"),
        HTTPError("url", 400, "secret", {}, None),
    ],
)
def test_exchange_errors_do_not_expose_credentials(error: Exception) -> None:
    from mailjail.oauth import gmail_access_token

    with (
        patch("mailjail.oauth.urlopen", side_effect=error),
        pytest.raises(CredentialError) as caught,
    ):
        gmail_access_token("refresh")
    assert "secret" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_pool_refreshes_on_reconnection_and_uses_xoauth2() -> None:
    with (
        patch("mailjail.imap.connection.MailBox") as mailbox,
        patch(
            "mailjail.imap.connection.gmail_access_token",
            side_effect=["first", "second"],
        ) as refresh,
    ):
        pool = IMAPPool(
            "imap.gmail.com",
            993,
            "u@example.com",
            "",
            size=1,
            oauth2_refresh_token="refresh",
        )
        mailbox.return_value.xoauth2.assert_called_once_with(
            "u@example.com", "first", initial_folder=None
        )
        mailbox.return_value.client.noop.side_effect = [OSError("closed")]
        with pool.connection():
            pass
        assert mailbox.return_value.xoauth2.call_args.args == (
            "u@example.com",
            "second",
        )
        assert refresh.call_count == 2
        mailbox.return_value.login.assert_not_called()


def test_password_login_unchanged() -> None:
    with patch("mailjail.imap.connection.MailBox") as mailbox:
        IMAPPool("mail.example.com", 993, "u", "password", size=1)
        mailbox.return_value.login.assert_called_once_with(
            "u", "password", initial_folder=None
        )
        mailbox.return_value.xoauth2.assert_not_called()


def test_registry_passes_refresh_token() -> None:
    settings = AccountSettings(
        imap_host="imap.gmail.com",
        imap_username="u",
        imap_password="",
        oauth2_refresh_token="private-refresh-value",
    )
    with patch("mailjail.registry.IMAPPool") as pool:
        _default_pool_factory(settings)
    assert pool.call_args.kwargs["oauth2_refresh_token"] == "private-refresh-value"
    assert "private-refresh-value" not in repr(settings)


@pytest.mark.parametrize(
    "overrides",
    [
        {"imap_host": "evil.example"},
        {"imap_ssl": False},
        {"imap_tls_insecure": True},
        {"oauth2_refresh_token": ""},
    ],
)
def test_oauth_settings_require_gmail_verified_tls_and_token(
    overrides: dict[str, object],
) -> None:
    from pydantic import ValidationError

    values = {
        "imap_host": "imap.gmail.com",
        "imap_username": "u",
        "imap_password": "",
        "oauth2_refresh_token": "private-token",
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        AccountSettings.model_validate(values)


def test_failed_authentication_closes_socket() -> None:
    with (
        patch("mailjail.imap.connection.MailBox") as mailbox,
        patch(
            "mailjail.imap.connection.gmail_access_token",
            side_effect=CredentialError("failed"),
        ),
    ):
        with pytest.raises(CredentialError):
            IMAPPool(
                "imap.gmail.com", 993, "u", "", size=1, oauth2_refresh_token="refresh"
            )
        mailbox.return_value.client.shutdown.assert_called_once()
        mailbox.return_value.login.assert_not_called()


def test_pool_initialization_failure_closes_prior_connections() -> None:
    with (
        patch("mailjail.imap.connection.MailBox") as mailbox,
        patch(
            "mailjail.imap.connection.gmail_access_token",
            side_effect=["first", CredentialError("failed")],
        ),
    ):
        with pytest.raises(CredentialError):
            IMAPPool(
                "imap.gmail.com", 993, "u", "", size=2, oauth2_refresh_token="refresh"
            )
        mailbox.return_value.logout.assert_called_once()


def test_invalid_oauth_settings_hide_token_in_error() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as caught:
        AccountSettings(
            imap_host="wrong.example",
            imap_username="u",
            imap_password="",
            oauth2_refresh_token="private-refresh-value",
        )
    assert "private-refresh-value" not in str(caught.value)
