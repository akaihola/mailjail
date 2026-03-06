"""Tests for draft composition (compose_draft only — no IMAP connection needed)."""

import email
import email.message


from mailjail.imap.drafts import compose_draft


def test_compose_draft_returns_bytes() -> None:
    result = compose_draft(
        {
            "from": [{"email": "a@b.com"}],
            "to": [{"email": "c@d.com"}],
            "subject": "Hello",
            "textBody": [{"partId": "1", "type": "text/plain"}],
            "bodyValues": {"1": {"value": "Body text"}},
        },
        from_address="a@b.com",
    )
    assert isinstance(result, bytes)


def test_compose_draft_parseable_by_email_library() -> None:
    result = compose_draft(
        {
            "from": [{"email": "a@b.com"}],
            "to": [{"email": "c@d.com"}],
            "subject": "Hello",
            "textBody": [{"partId": "1", "type": "text/plain"}],
            "bodyValues": {"1": {"value": "Body text"}},
        },
        from_address="a@b.com",
    )
    msg = email.message_from_bytes(result)
    assert msg["From"] is not None
    assert msg["To"] is not None
    assert msg["Subject"] is not None


def test_compose_draft_correct_headers() -> None:
    result = compose_draft(
        {
            "from": [{"email": "a@b.com", "name": "Alice"}],
            "to": [{"email": "c@d.com", "name": "Charlie"}],
            "subject": "Test Subject",
            "textBody": [{"partId": "1", "type": "text/plain"}],
            "bodyValues": {"1": {"value": "Hello there"}},
        },
        from_address="a@b.com",
    )
    msg = email.message_from_bytes(result)
    assert "a@b.com" in msg["From"]
    assert "c@d.com" in msg["To"]
    assert msg["Subject"] == "Test Subject"


def test_compose_draft_in_reply_to_header() -> None:
    result = compose_draft(
        {
            "from": [{"email": "a@b.com"}],
            "to": [{"email": "c@d.com"}],
            "subject": "Re: Original",
            "textBody": [{"partId": "1", "type": "text/plain"}],
            "bodyValues": {"1": {"value": "Reply body"}},
            "headers": [{"name": "In-Reply-To", "value": "<abc@x.example.com>"}],
        },
        from_address="a@b.com",
    )
    msg = email.message_from_bytes(result)
    assert msg["In-Reply-To"] == "<abc@x.example.com>"


def test_compose_draft_plain_text_content_type() -> None:
    result = compose_draft(
        {
            "from": [{"email": "a@b.com"}],
            "to": [{"email": "c@d.com"}],
            "subject": "Hello",
            "textBody": [{"partId": "1", "type": "text/plain"}],
            "bodyValues": {"1": {"value": "Plain text body"}},
        },
        from_address="a@b.com",
    )
    msg = email.message_from_bytes(result)
    assert "text/plain" in msg.get_content_type()


def test_compose_draft_mime_version_present() -> None:
    result = compose_draft(
        {
            "from": [{"email": "a@b.com"}],
            "to": [{"email": "c@d.com"}],
            "subject": "Hello",
            "textBody": [{"partId": "1", "type": "text/plain"}],
            "bodyValues": {"1": {"value": "Body"}},
        },
        from_address="a@b.com",
    )
    msg = email.message_from_bytes(result)
    assert msg["MIME-Version"] == "1.0"
