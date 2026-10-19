"""Email/query through its query plan and a mock IMAP folder."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from mailjail.models.email import handle_email_query


def run_query(
    pool: MagicMock, *, sort_extension: bool, **args: Any,
) -> tuple[str, dict[str, Any]]:
    pool.has_capability.side_effect = lambda name: sort_extension and name == "SORT"
    return handle_email_query({"accountId": "work", **args}, pool)


@pytest.mark.parametrize("sort, imap_sort", [
    ([{"property": "receivedAt"}], ["ARRIVAL"]),
    ([{"property": "receivedAt", "isAscending": False}], ["REVERSE ARRIVAL"]),
    (
        [{"property": "from"}, {"property": "sentAt", "isAscending": False},
         {"property": "size", "isAscending": True}],
        ["FROM", "REVERSE DATE", "SIZE"],
    ),
])
def test_sort_extension_receives_every_comparator(
    mock_pool: tuple[MagicMock, MagicMock], sort: list[dict], imap_sort: list[str],
) -> None:
    pool, mailbox = mock_pool
    mailbox.uids.return_value = ["7", "3", "5"]

    method, result = run_query(
        pool, sort_extension=True, sort=sort, filter={"inMailbox": "Archive"},
    )

    assert method == "Email/query"
    mailbox.folder.set.assert_called_once_with("Archive")
    assert mailbox.uids.call_args.kwargs == {"sort": imap_sort}
    assert result["ids"] == ["Archive:7", "Archive:3", "Archive:5"]
    assert result["total"] == 3


@pytest.mark.parametrize("sort_extension", [False, True])
def test_no_sort_lists_newest_uid_first(
    mock_pool: tuple[MagicMock, MagicMock], sort_extension: bool,
) -> None:
    pool, mailbox = mock_pool
    mailbox.uids.return_value = ["3", "5", "9"]

    _, result = run_query(pool, sort_extension=sort_extension, sort=None)

    assert mailbox.uids.call_args.kwargs == {"sort": []}
    assert result["ids"] == ["INBOX:9", "INBOX:5", "INBOX:3"]


@pytest.mark.parametrize("is_ascending, ids", [
    (True, ["INBOX:3", "INBOX:5"]),
    (False, ["INBOX:9", "INBOX:5"]),
])
def test_without_sort_extension_uid_order_stands_in_for_arrival(
    mock_pool: tuple[MagicMock, MagicMock], is_ascending: bool, ids: list[str],
) -> None:
    pool, mailbox = mock_pool
    mailbox.uids.return_value = ["3", "5", "9"]

    _, result = run_query(
        pool, sort_extension=False,
        sort=[{"property": "receivedAt", "isAscending": is_ascending}],
        position=0, limit=2,
    )

    assert mailbox.uids.call_args.kwargs == {"sort": []}
    assert result["ids"] == ids
    assert result["total"] == 3


@pytest.mark.parametrize("sort_extension, sort", [
    (False, [{"property": "subject"}]),
    (False, [{"property": "receivedAt", "isAscending": False},
             {"property": "subject"}]),
    (True, [{"property": "hasKeyword", "keyword": "$flagged"}]),
    (True, [{"property": "receivedAt"}, {"property": "unknown"}]),
])
def test_unsupported_sort_fails_before_imap(
    mock_pool: tuple[MagicMock, MagicMock], sort_extension: bool, sort: list[dict],
) -> None:
    pool, _ = mock_pool

    method, result = run_query(pool, sort_extension=sort_extension, sort=sort)

    assert method == "error"
    assert result["type"] == "unsupportedSort"
    pool.connection.assert_not_called()


@pytest.mark.parametrize("filter_, folder, criterion", [
    (None, "INBOX", "(ALL)"),
    ({"inMailbox": "Archive"}, "Archive", "(ALL)"),
    ({"inMailbox": "Archive", "from": "alice"}, "Archive", '(FROM "alice")'),
    (
        {"operator": "AND", "conditions": [
            {"from": "alice"},
            {"operator": "AND", "conditions": [{"inMailbox": "Archive"}]},
        ]},
        "Archive", '((FROM "alice") ((ALL)))',
    ),
    (
        {"operator": "AND", "conditions": [
            {"inMailbox": "Archive", "subject": "hi"},
            {"inMailbox": "Archive"},
            {"operator": "NOT", "conditions": [{"from": "spam"}]},
        ]},
        "Archive", '((SUBJECT "hi") (ALL) NOT ((FROM "spam")))',
    ),
])
def test_folder_and_criterion_come_from_one_filter(
    mock_pool: tuple[MagicMock, MagicMock],
    filter_: dict | None, folder: str, criterion: str,
) -> None:
    pool, mailbox = mock_pool
    mailbox.uids.return_value = ["4"]

    _, result = run_query(pool, sort_extension=False, filter=filter_)

    mailbox.folder.set.assert_called_once_with(folder)
    assert str(mailbox.uids.call_args.args[0]) == criterion
    assert result["ids"] == [f"{folder}:4"]


@pytest.mark.parametrize("filter_", [
    {"operator": "AND", "conditions": [{"inMailbox": "INBOX"},
                                       {"inMailbox": "Archive"}]},
    {"operator": "OR", "conditions": [{"inMailbox": "INBOX"},
                                      {"inMailbox": "Archive"}]},
    {"operator": "OR", "conditions": [{"inMailbox": "Archive"}, {"from": "alice"}]},
    {"operator": "NOT", "conditions": [{"inMailbox": "Archive"}]},
    {"operator": "NOT", "conditions": [
        {"operator": "AND", "conditions": [{"inMailbox": "Archive"}]}]},
    {"operator": "AND", "conditions": [{"from": "alice"}], "inMailbox": "Archive"},
    {"inMailboxOtherThan": ["Trash"]},
    {"header": ["X-Spam", "yes"]},
    {"operator": "XOR", "conditions": [{"from": "alice"}]},
])
def test_unsupported_filter_fails_before_imap(
    mock_pool: tuple[MagicMock, MagicMock], filter_: dict,
) -> None:
    pool, _ = mock_pool

    method, result = run_query(pool, sort_extension=True, filter=filter_)

    assert method == "error"
    assert result["type"] == "unsupportedFilter"
    pool.connection.assert_not_called()
