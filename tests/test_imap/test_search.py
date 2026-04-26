"""Tests for JMAP filter → IMAP SEARCH translation."""

import pytest

from mailjail.imap.search import jmap_filter_to_imap, jmap_sort_to_imap


def test_filter_from() -> None:
    result = jmap_filter_to_imap({"from": "alice"})
    assert "FROM" in str(result)
    assert "alice" in str(result)


def test_filter_subject() -> None:
    result = jmap_filter_to_imap({"subject": "invoice"})
    assert "SUBJECT" in str(result)
    assert "invoice" in str(result)


def test_filter_has_keyword_flagged() -> None:
    result = jmap_filter_to_imap({"hasKeyword": "$flagged"})
    assert "FLAGGED" in str(result)


def test_filter_has_keyword_custom() -> None:
    result = jmap_filter_to_imap({"hasKeyword": "needs-reply"})
    assert "KEYWORD" in str(result)
    assert "needs-reply" in str(result)


def test_filter_not_keyword() -> None:
    result = jmap_filter_to_imap({"notKeyword": "agent-triaged"})
    assert "UNKEYWORD" in str(result)
    assert "agent-triaged" in str(result)


def test_filter_after() -> None:
    result = jmap_filter_to_imap({"after": "2026-02-01T00:00:00Z"})
    assert "SINCE" in str(result)
    assert "Feb" in str(result) or "2026" in str(result)


def test_filter_before() -> None:
    result = jmap_filter_to_imap({"before": "2026-03-01T00:00:00Z"})
    assert "BEFORE" in str(result)


def test_filter_in_mailbox_ignored() -> None:
    """inMailbox is handled by folder SELECT, not SEARCH — returns ALL."""
    result = jmap_filter_to_imap({"inMailbox": "INBOX"})
    assert str(result) == "(ALL)"


def test_filter_empty_matches_all() -> None:
    result = jmap_filter_to_imap({})
    assert str(result) == "(ALL)"


def test_filter_compound_and() -> None:
    result = str(
        jmap_filter_to_imap(
            {"operator": "AND", "conditions": [{"from": "alice"}, {"subject": "hi"}]}
        )
    )
    assert "FROM" in result and "SUBJECT" in result and "alice" in result


def test_filter_compound_or() -> None:
    result = str(
        jmap_filter_to_imap(
            {"operator": "OR", "conditions": [{"from": "alice"}, {"from": "bob"}]}
        )
    )
    assert result.startswith("(OR")
    assert "alice" in result and "bob" in result


def test_filter_compound_not() -> None:
    result = str(
        jmap_filter_to_imap({"operator": "NOT", "conditions": [{"from": "spam"}]})
    )
    assert "NOT" in result and "spam" in result


def test_filter_compound_unknown_operator_raises() -> None:
    with pytest.raises(ValueError, match="unknown"):
        jmap_filter_to_imap({"operator": "XOR", "conditions": []})


def test_filter_compound_nested() -> None:
    result = str(
        jmap_filter_to_imap(
            {
                "operator": "AND",
                "conditions": [
                    {"from": "alice"},
                    {
                        "operator": "OR",
                        "conditions": [{"subject": "hi"}, {"subject": "hello"}],
                    },
                ],
            }
        )
    )
    assert "FROM" in result and "SUBJECT" in result
    assert "alice" in result and "hi" in result and "hello" in result


def test_sort_received_at_descending() -> None:
    result = jmap_sort_to_imap([{"property": "receivedAt", "isAscending": False}])
    assert result == "REVERSE ARRIVAL"


def test_sort_empty_returns_none() -> None:
    result = jmap_sort_to_imap([])
    assert result is None


def test_filter_to() -> None:
    result = jmap_filter_to_imap({"to": "bob"})
    assert "TO" in str(result)
    assert "bob" in str(result)


def test_filter_body() -> None:
    result = jmap_filter_to_imap({"body": "hello world"})
    assert "BODY" in str(result)
    assert "hello world" in str(result)
