"""Offline tests for selected-folder reads."""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from imap_tools import MailMessage


@pytest.mark.parametrize("headers_only", [False, True])
def test_fetch_materializes_before_returning_connection(
    mock_pool: tuple[MagicMock, MagicMock], sample_message: MailMessage,
    headers_only: bool,
) -> None:
    from mailjail.imap.fetch import fetch_messages

    pool, mailbox = mock_pool
    events: list[str] = []
    mailbox.folder.set.side_effect = lambda folder: events.append(folder)
    pool.connection.return_value.__exit__.side_effect = lambda *args: events.append("released")

    def messages(*args: object, **kwargs: object) -> Iterator[MailMessage]:
        assert events == ["Archive"]
        events.append("consumed")
        yield sample_message

    mailbox.fetch.side_effect = messages
    result = fetch_messages(pool, "Archive", ["42", "43"], headers_only=headers_only)

    assert result == [sample_message]
    assert events == ["Archive", "consumed", "released"]
    assert str(mailbox.fetch.call_args.args[0]) == "(UID 42,43)"
    assert mailbox.fetch.call_args.kwargs == {
        "mark_seen": False, "headers_only": headers_only, "bulk": True,
    }
