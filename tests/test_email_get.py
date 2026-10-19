"""Email/get through the real fetch adapter and MIME conversion."""

from unittest.mock import MagicMock

import pytest
from imap_tools import MailMessage

from mailjail.models.email import handle_email_get


def test_missing_uid_is_scoped_to_folder(
    mock_pool: tuple[MagicMock, MagicMock], sample_message: MailMessage,
) -> None:
    pool, mailbox = mock_pool
    mailbox.fetch.side_effect = [iter([sample_message]), iter([])]

    method, result = handle_email_get(
        {"accountId": "work", "ids": ["INBOX:42", "Archive:42", "invalid"]}, pool,
    )

    assert method == "Email/get"
    assert [email["id"] for email in result["list"]] == ["INBOX:42"]
    assert set(result["notFound"]) == {"Archive:42", "invalid"}
    assert result["list"][0]["attachments"][0]["blobId"] == "INBOX:42:0"
    assert result["list"][0]["bodyValues"]["1"]["value"] == "Message body\n"
    assert all(call.kwargs["mark_seen"] is False for call in mailbox.fetch.call_args_list)


@pytest.mark.parametrize("properties, headers_only, expected", [
    (["subject"], True, {"subject": "Offline message"}),
    ([], True, {}),
    (["preview"], False, {"preview": "Message body"}),
    (["attachments"], False, None),
])
def test_property_projection(
    mock_pool: tuple[MagicMock, MagicMock], sample_message: MailMessage,
    properties: list[str], headers_only: bool, expected: dict | None,
) -> None:
    pool, mailbox = mock_pool
    mailbox.fetch.return_value = iter([sample_message])
    _, result = handle_email_get(
        {"accountId": "work", "ids": ["INBOX:42"], "properties": properties}, pool,
    )

    email = result["list"][0]
    assert set(email) == {"id", *properties}
    assert email["id"] == "INBOX:42"
    if expected is not None:
        assert email == {"id": "INBOX:42", **expected}
    else:
        assert email["attachments"][0]["name"] == "report.pdf"
    assert result["notFound"] == []
    assert mailbox.fetch.call_args.kwargs["headers_only"] is headers_only
    assert mailbox.fetch.call_args.kwargs["mark_seen"] is False


def test_unconvertible_message_is_not_found(
    mock_pool: tuple[MagicMock, MagicMock], sample_message: MailMessage,
) -> None:
    pool, mailbox = mock_pool
    sample_message.uid = None
    mailbox.fetch.return_value = iter([sample_message])
    _, result = handle_email_get({"accountId": "work", "ids": ["INBOX:42"]}, pool)
    assert result["list"] == []
    assert result["notFound"] == ["INBOX:42"]
