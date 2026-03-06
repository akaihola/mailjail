"""Shared test fixtures."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_pool():
    """IMAPPool whose context manager yields a mock MailBox."""
    pool = MagicMock()
    mb = MagicMock()
    pool.connection.return_value.__enter__ = MagicMock(return_value=mb)
    pool.connection.return_value.__exit__ = MagicMock(return_value=False)
    return pool, mb


@pytest.fixture
def sample_jmap_request():
    return {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [["Email/query", {"accountId": "default", "filter": {}}, "c0"]],
    }
