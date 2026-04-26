"""Shared test fixtures."""

from unittest.mock import MagicMock

import pytest

from mailjail.config import AccountSettings
from mailjail.registry import AccountContext, AccountRegistry


@pytest.fixture
def mock_pool():
    """IMAPPool whose context manager yields a mock MailBox."""
    pool = MagicMock()
    mb = MagicMock()
    pool.connection.return_value.__enter__ = MagicMock(return_value=mb)
    pool.connection.return_value.__exit__ = MagicMock(return_value=False)
    return pool, mb


def make_account_settings(
    *,
    imap_username: str = "test@example.com",
    imap_password: str = "secret",
    drafts_folder: str = "Drafts",
) -> AccountSettings:
    return AccountSettings(
        imap_username=imap_username,
        imap_password=imap_password,
        drafts_folder=drafts_folder,
    )


def make_registry_with_pool(
    account_id: str,
    pool: MagicMock,
    *,
    settings: AccountSettings | None = None,
) -> AccountRegistry:
    """Build a registry pre-populated with one mock pool — no lazy creation."""
    settings = settings or make_account_settings()
    registry = AccountRegistry(
        {account_id: settings},
        pool_factory=lambda _s: pool,
    )
    registry._contexts[account_id] = AccountContext(settings=settings, pool=pool)
    return registry


@pytest.fixture
def sample_jmap_request():
    return {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [["Email/query", {"accountId": "work", "filter": {}}, "c0"]],
    }
