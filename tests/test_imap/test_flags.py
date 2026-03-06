"""Tests for JMAP keyword ↔ IMAP flag mapping."""

from mailjail.imap.flags import (
    imap_flag_to_jmap,
    imap_flags_to_jmap_keywords,
    jmap_keyword_to_imap,
)


def test_seen_keyword_to_imap() -> None:
    assert jmap_keyword_to_imap("$seen") == "\\Seen"


def test_flagged_keyword_to_imap() -> None:
    assert jmap_keyword_to_imap("$flagged") == "\\Flagged"


def test_answered_keyword_to_imap() -> None:
    assert jmap_keyword_to_imap("$answered") == "\\Answered"


def test_draft_keyword_to_imap() -> None:
    assert jmap_keyword_to_imap("$draft") == "\\Draft"


def test_custom_keyword_passes_through() -> None:
    assert jmap_keyword_to_imap("needs-reply") == "needs-reply"


def test_imap_flag_to_jmap_seen() -> None:
    assert imap_flag_to_jmap("\\Seen") == "$seen"


def test_imap_flag_to_jmap_flagged() -> None:
    assert imap_flag_to_jmap("\\Flagged") == "$flagged"


def test_imap_flag_to_jmap_custom_passthrough() -> None:
    assert imap_flag_to_jmap("needs-reply") == "needs-reply"


def test_imap_flags_to_jmap_keywords() -> None:
    result = imap_flags_to_jmap_keywords(("\\Seen", "\\Flagged", "needs-reply"))
    assert result == {"$seen": True, "$flagged": True, "needs-reply": True}


def test_imap_flags_to_jmap_keywords_empty() -> None:
    result = imap_flags_to_jmap_keywords(())
    assert result == {}


def test_imap_flags_to_jmap_keywords_draft() -> None:
    result = imap_flags_to_jmap_keywords(("\\Draft",))
    assert result == {"$draft": True}
