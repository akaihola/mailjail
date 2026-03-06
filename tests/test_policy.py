"""Tests for the policy module."""

from mailjail.policy import (
    ALLOWED_METHODS,
    BLOCKED_METHODS,
    RESTRICTED_METHODS,
    check_email_set,
)


def test_blocked_methods_not_in_allowed() -> None:
    """Every blocked method must not appear in ALLOWED_METHODS."""
    overlap = BLOCKED_METHODS & ALLOWED_METHODS
    assert overlap == frozenset(), f"Overlap: {overlap}"


def test_blocked_methods_not_in_restricted() -> None:
    """Every blocked method must not appear in RESTRICTED_METHODS."""
    overlap = BLOCKED_METHODS & RESTRICTED_METHODS
    assert overlap == frozenset(), f"Overlap: {overlap}"


def test_email_set_destroy_is_forbidden() -> None:
    violations = check_email_set({"destroy": ["id1"]})
    assert violations, "Expected non-empty violations for destroy"
    assert any("forbidden" in v.lower() or "destroy" in v.lower() for v in violations)


def test_email_set_update_mailboxids_is_forbidden() -> None:
    violations = check_email_set(
        {"update": {"INBOX:1": {"mailboxIds": {"SomeFolder": True}}}}
    )
    assert violations, "Expected violation for mailboxIds update"


def test_email_set_update_keywords_is_allowed() -> None:
    violations = check_email_set({"update": {"INBOX:1": {"keywords/$flagged": True}}})
    assert violations == []


def test_email_set_update_seen_keyword_is_allowed() -> None:
    violations = check_email_set({"update": {"INBOX:1": {"keywords/$seen": False}}})
    assert violations == []


def test_email_set_create_draft_is_allowed() -> None:
    violations = check_email_set(
        {
            "create": {
                "d1": {
                    "mailboxIds": {"Drafts": True},
                    "keywords": {"$draft": True},
                    "from": [{"email": "a@b.com"}],
                    "to": [{"email": "c@d.com"}],
                    "subject": "Hello",
                }
            }
        }
    )
    assert violations == []


def test_email_set_create_without_draft_keyword_is_forbidden() -> None:
    violations = check_email_set(
        {
            "create": {
                "d1": {
                    "mailboxIds": {"Drafts": True},
                    "keywords": {},  # missing $draft
                    "subject": "Hello",
                }
            }
        }
    )
    assert violations, "Expected violation for missing $draft keyword"


def test_allowed_methods_contains_expected() -> None:
    assert "Mailbox/get" in ALLOWED_METHODS
    assert "Email/query" in ALLOWED_METHODS
    assert "Email/get" in ALLOWED_METHODS


def test_email_set_in_restricted() -> None:
    assert "Email/set" in RESTRICTED_METHODS


def test_blocked_contains_submission() -> None:
    assert "EmailSubmission/set" in BLOCKED_METHODS
    assert "Mailbox/set" in BLOCKED_METHODS
    assert "Email/copy" in BLOCKED_METHODS


def test_empty_email_set_has_no_violations() -> None:
    violations = check_email_set({})
    assert violations == []
