"""Tests for the JMAP session resource (multi-account)."""

from mailjail.config import AccountSettings, Settings
from mailjail.session import session_resource


def _settings(primary: str, **accounts: str) -> Settings:
    return Settings(
        primary_account=primary,
        accounts={
            account_id: AccountSettings(
                imap_username=username, imap_password="x"
            )
            for account_id, username in accounts.items()
        },
    )


def test_two_accounts_appear_in_session_resource() -> None:
    settings = _settings("work", work="w@example.com", personal="p@example.com")

    resource = session_resource(settings)

    assert set(resource["accounts"]) == {"work", "personal"}
    assert resource["accounts"]["work"]["name"] == "w@example.com"
    assert resource["accounts"]["personal"]["name"] == "p@example.com"
    caps = resource["accounts"]["work"]["accountCapabilities"]
    assert "urn:ietf:params:jmap:mail" in caps
    assert "urn:ietf:params:jmap:submission" in caps


def test_primary_accounts_uses_settings_primary_account() -> None:
    settings = _settings("personal", work="w@example.com", personal="p@example.com")
    resource = session_resource(settings)
    assert resource["primaryAccounts"]["urn:ietf:params:jmap:mail"] == "personal"
    assert resource["primaryAccounts"]["urn:ietf:params:jmap:submission"] == "personal"


def test_single_account_session_resource() -> None:
    settings = _settings("only", only="me@example.com")
    resource = session_resource(settings)
    assert list(resource["accounts"]) == ["only"]
    assert resource["primaryAccounts"]["urn:ietf:params:jmap:mail"] == "only"
