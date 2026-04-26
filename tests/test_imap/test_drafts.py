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


def test_email_set_create_uses_account_drafts_folder_and_username() -> None:
    """5.6 acceptance: Email/set create routes to per-account drafts folder
    using the account's imap_username as the From address."""
    from unittest.mock import MagicMock, patch

    from mailjail.config import AccountSettings
    from mailjail.models.email_set import handle_email_set

    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = MagicMock()
    pool.connection.return_value.__exit__.return_value = False

    settings = AccountSettings(
        imap_username="work@example.com",
        imap_password="x",
        drafts_folder="Work/Drafts",
    )

    args = {
        "accountId": "work",
        "create": {
            "d1": {
                "keywords": {"$draft": True},
                "from": [{"email": "work@example.com"}],
                "to": [{"email": "c@d.com"}],
                "subject": "S",
                "textBody": [{"partId": "1", "type": "text/plain"}],
                "bodyValues": {"1": {"value": "Body"}},
            }
        },
    }

    with (
        patch("mailjail.models.email_set.compose_draft") as mock_compose,
        patch("mailjail.models.email_set.append_draft") as mock_append,
    ):
        mock_compose.return_value = b"raw rfc822"
        mock_append.return_value = "Work/Drafts:42"
        handle_email_set(args, pool, settings)

    assert mock_compose.call_args.kwargs["from_address"] == "work@example.com"
    assert mock_append.call_args.args[1] == "Work/Drafts"
