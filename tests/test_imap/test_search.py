"""Tests for planning a JMAP Email/query as one IMAP SEARCH or SORT."""

import pytest

from mailjail.imap.search import UnsupportedQuery, plan_query


def search_criterion(filter_cond: dict) -> str:
    return plan_query(filter_cond, [], server_sort=True).criterion


def test_filter_from() -> None:
    result = search_criterion({"from": "alice"})
    assert "FROM" in str(result)
    assert "alice" in str(result)


def test_filter_subject() -> None:
    result = search_criterion({"subject": "invoice"})
    assert "SUBJECT" in str(result)
    assert "invoice" in str(result)


def test_filter_has_keyword_flagged() -> None:
    result = search_criterion({"hasKeyword": "$flagged"})
    assert "FLAGGED" in str(result)


def test_filter_has_keyword_custom() -> None:
    result = search_criterion({"hasKeyword": "needs-reply"})
    assert "KEYWORD" in str(result)
    assert "needs-reply" in str(result)


def test_filter_not_keyword() -> None:
    result = search_criterion({"notKeyword": "agent-triaged"})
    assert "UNKEYWORD" in str(result)
    assert "agent-triaged" in str(result)


def test_filter_after() -> None:
    result = search_criterion({"after": "2026-02-01T00:00:00Z"})
    assert "SINCE" in str(result)
    assert "Feb" in str(result) or "2026" in str(result)


def test_filter_before() -> None:
    result = search_criterion({"before": "2026-03-01T00:00:00Z"})
    assert "BEFORE" in str(result)


def test_filter_in_mailbox_selects_folder_not_search_key() -> None:
    plan = plan_query({"inMailbox": "Archive"}, [], server_sort=True)
    assert (plan.folder, plan.criterion) == ("Archive", "(ALL)")


def test_filter_empty_matches_all() -> None:
    result = search_criterion({})
    assert str(result) == "(ALL)"


def test_filter_compound_and() -> None:
    result = str(
        search_criterion(
            {"operator": "AND", "conditions": [{"from": "alice"}, {"subject": "hi"}]}
        )
    )
    assert "FROM" in result and "SUBJECT" in result and "alice" in result


def test_filter_compound_or() -> None:
    result = str(
        search_criterion(
            {"operator": "OR", "conditions": [{"from": "alice"}, {"from": "bob"}]}
        )
    )
    assert result.startswith("(OR")
    assert "alice" in result and "bob" in result


def test_filter_compound_not() -> None:
    result = str(
        search_criterion({"operator": "NOT", "conditions": [{"from": "spam"}]})
    )
    assert "NOT" in result and "spam" in result


@pytest.mark.parametrize("filter_cond, criterion", [
    ({"operator": "AND", "conditions": []}, "(ALL)"),
    ({"operator": "NOT", "conditions": []}, "(ALL)"),
    ({"operator": "OR", "conditions": []}, "NOT ((ALL))"),
    (
        {"operator": "AND", "conditions": [
            {"from": "a"}, {"operator": "OR", "conditions": []}]},
        '((FROM "a") NOT ((ALL)))',
    ),
])
def test_filter_compound_without_conditions(filter_cond: dict, criterion: str) -> None:
    assert search_criterion(filter_cond) == criterion


def test_filter_compound_unknown_operator_raises() -> None:
    with pytest.raises(UnsupportedQuery, match="unknown"):
        search_criterion({"operator": "XOR", "conditions": []})


def test_filter_compound_nested() -> None:
    result = str(
        search_criterion(
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
    sort = [{"property": "receivedAt", "isAscending": False}]
    plan = plan_query({}, sort, server_sort=True)
    assert (plan.sort, plan.reverse) == (["REVERSE ARRIVAL"], False)


def test_sort_empty_is_newest_uid_first() -> None:
    plan = plan_query({}, [], server_sort=True)
    assert (plan.sort, plan.reverse) == ([], True)


def test_filter_to() -> None:
    result = search_criterion({"to": "bob"})
    assert "TO" in str(result)
    assert "bob" in str(result)


def test_filter_body() -> None:
    result = search_criterion({"body": "hello world"})
    assert "BODY" in str(result)
    assert "hello world" in str(result)
