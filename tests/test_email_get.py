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
        {"accountId": "work", "ids": ["INBOX:42", "Archive:42", "invalid"],
         "fetchTextBodyValues": True}, pool,
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
    (["bodyStructure"], True, {}),
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
    assert set(email) == {"id", *(p for p in properties if p != "bodyStructure")}
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


@pytest.fixture(params=["html", "multipart"])
def body_message(request: pytest.FixtureRequest) -> MailMessage:
    from email.message import EmailMessage

    mime = EmailMessage()
    if request.param == "multipart":
        mime.set_content("Aä🙂Z")
        mime.add_alternative("<p>Aä🙂Z</p>", subtype="html")
        mime.add_attachment(b"data", maintype="application", subtype="pdf",
                            filename="test.pdf")
    else:
        mime.set_content("<p>Aä🙂Z</p>", subtype="html")
    message = MailMessage.from_bytes(mime.as_bytes())
    message.uid = "42"
    return message


@pytest.mark.parametrize("text, html", [(False, False), (True, False),
                                         (False, True), (True, True)])
def test_body_value_selection(
    mock_pool: tuple[MagicMock, MagicMock], body_message: MailMessage,
    text: bool, html: bool,
) -> None:
    pool, mailbox = mock_pool
    mailbox.fetch.return_value = iter([body_message])
    _, result = handle_email_get({
        "accountId": "work", "ids": ["INBOX:42"],
        "properties": ["textBody", "htmlBody", "bodyValues"],
        "fetchTextBodyValues": text, "fetchHTMLBodyValues": html,
    }, pool)
    email = result["list"][0]
    assert email["textBody"] == [{"partId": "1", "type": "text/plain"}]
    assert email["htmlBody"] == [{"partId": "2", "type": "text/html"}]
    assert set(email["bodyValues"]) == ({"1"} if text else set()) | ({"2"} if html else set())
    if text:
        assert "Aä🙂Z" in email["bodyValues"]["1"]["value"]
    if html:
        assert email["bodyValues"]["2"]["value"] == body_message.html
    assert mailbox.fetch.call_args.kwargs["mark_seen"] is False


@pytest.mark.parametrize("limit", [0, 1, 2, 3, 6, 7, 8, 9, 100])
def test_body_value_utf8_limit(
    mock_pool: tuple[MagicMock, MagicMock], body_message: MailMessage, limit: int,
) -> None:
    from mailjail.imap.fetch import html_to_text

    pool, mailbox = mock_pool
    mailbox.fetch.return_value = iter([body_message])
    _, result = handle_email_get({
        "accountId": "work", "ids": ["INBOX:42"],
        "fetchTextBodyValues": True, "fetchHTMLBodyValues": True,
        "maxBodyValueBytes": limit,
    }, pool)
    email = result["list"][0]
    originals = {"1": body_message.text or html_to_text(body_message.html),
                 "2": body_message.html}
    for part, original in originals.items():
        encoded = original.encode("utf-8")
        expected = encoded[:limit].decode("utf-8", errors="ignore") if limit else original
        if part == "1" and limit in (2, 3, 6, 7):
            assert expected == {2: "A", 3: "Aä", 6: "Aä", 7: "Aä🙂"}[limit]
        assert email["bodyValues"][part] == {
            "value": expected, "isTruncated": bool(limit and len(encoded) > limit),
            "isEncodingProblem": False,
        }


@pytest.mark.parametrize("properties, text, headers_only", [
    (["hasAttachment"], False, False),
    (["bodyValues"], False, True),
    (["bodyValues"], True, False),
    (["subject"], True, True),
])
def test_fetch_mode_uses_selected_data(
    mock_pool: tuple[MagicMock, MagicMock], sample_message: MailMessage,
    properties: list[str], text: bool, headers_only: bool,
) -> None:
    pool, mailbox = mock_pool
    mailbox.fetch.return_value = iter([sample_message])
    _, result = handle_email_get({
        "accountId": "work", "ids": ["INBOX:42"], "properties": properties,
        "fetchTextBodyValues": text,
    }, pool)
    assert mailbox.fetch.call_args.kwargs["headers_only"] is headers_only
    assert mailbox.fetch.call_args.kwargs["mark_seen"] is False
    if properties == ["hasAttachment"]:
        assert result["list"] == [{"id": "INBOX:42", "hasAttachment": True}]


@pytest.mark.parametrize("name, value", [
    ("fetchTextBodyValues", "true"), ("fetchTextBodyValues", 1),
    ("fetchTextBodyValues", None), ("fetchHTMLBodyValues", "false"),
    ("fetchHTMLBodyValues", 0), ("fetchHTMLBodyValues", None),
    ("maxBodyValueBytes", -1), ("maxBodyValueBytes", True),
    ("maxBodyValueBytes", 1.5), ("maxBodyValueBytes", "3"),
    ("maxBodyValueBytes", None),
])
def test_invalid_body_options_do_not_fetch(
    mock_pool: tuple[MagicMock, MagicMock], name: str, value: object,
) -> None:
    pool, mailbox = mock_pool
    method, result = handle_email_get({
        "accountId": "work", "ids": ["INBOX:42"], name: value,
    }, pool)
    assert method == "error"
    assert result["type"] == "invalidArguments"
    pool.connection.assert_not_called()
    mailbox.fetch.assert_not_called()


def test_default_body_values_are_empty(
    mock_pool: tuple[MagicMock, MagicMock], body_message: MailMessage,
) -> None:
    pool, mailbox = mock_pool
    mailbox.fetch.return_value = iter([body_message])
    _, result = handle_email_get({"accountId": "work", "ids": ["INBOX:42"]}, pool)
    assert result["list"][0]["bodyValues"] == {}
    assert result["list"][0]["textBody"]
    assert result["list"][0]["htmlBody"]
    assert "bodyStructure" not in result["list"][0]


def test_header_projection_does_not_read_body(
    mock_pool: tuple[MagicMock, MagicMock], sample_message: MailMessage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import PropertyMock

    for name in ("text", "html", "attachments"):
        monkeypatch.setattr(MailMessage, name, PropertyMock(side_effect=AssertionError(name)))
    pool, mailbox = mock_pool
    mailbox.fetch.return_value = iter([sample_message])
    _, result = handle_email_get({
        "accountId": "work", "ids": ["INBOX:42"], "properties": ["subject"],
        "fetchTextBodyValues": True, "fetchHTMLBodyValues": True,
    }, pool)
    assert result["list"] == [{"id": "INBOX:42", "subject": "Offline message"}]
    assert mailbox.fetch.call_args.kwargs["headers_only"] is True


def test_html_values_without_part_projection(
    mock_pool: tuple[MagicMock, MagicMock], body_message: MailMessage,
) -> None:
    pool, mailbox = mock_pool
    mailbox.fetch.return_value = iter([body_message])
    _, result = handle_email_get({
        "accountId": "work", "ids": ["INBOX:42"], "properties": ["bodyValues"],
        "fetchHTMLBodyValues": True,
    }, pool)
    assert result["list"] == [{"id": "INBOX:42", "bodyValues": {
        "2": {"value": body_message.html, "isTruncated": False, "isEncodingProblem": False},
    }}]
    assert mailbox.fetch.call_args.kwargs["headers_only"] is False
