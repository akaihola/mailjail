"""Tests for the JMAP executor: policy, result-ref resolution, dispatch, routing."""

from unittest.mock import MagicMock, patch

import pytest

from mailjail.executor import (
    Executor,
    _json_pointer_get,
    resolve_args,
    resolve_result_ref,
)
from mailjail.models.core import JMAPRequest
from mailjail.registry import AccountRegistry

from .conftest import make_account_settings, make_registry_with_pool


def _make_executor(account_id: str = "work") -> tuple[Executor, MagicMock]:
    pool = MagicMock()
    registry = make_registry_with_pool(account_id, pool)
    return Executor(registry=registry), pool


# --- JSON Pointer tests ---


def test_json_pointer_get_simple_key() -> None:
    assert _json_pointer_get({"ids": ["a", "b"]}, "/ids") == ["a", "b"]


def test_json_pointer_get_nested() -> None:
    assert _json_pointer_get({"a": {"b": 42}}, "/a/b") == 42


def test_json_pointer_get_array_index() -> None:
    assert _json_pointer_get({"items": ["x", "y", "z"]}, "/items/1") == "y"


# --- Result reference resolution tests ---


def test_resolve_result_ref_simple() -> None:
    previous = [("Email/query", {"ids": ["INBOX:1", "INBOX:2"]}, "c0")]
    ref = {"resultOf": "c0", "name": "Email/query", "path": "/ids"}
    assert resolve_result_ref(ref, previous) == ["INBOX:1", "INBOX:2"]


def test_resolve_args_replaces_hash_keys() -> None:
    previous = [("Email/query", {"ids": ["INBOX:1"]}, "c0")]
    args = {
        "accountId": "work",
        "#ids": {"resultOf": "c0", "name": "Email/query", "path": "/ids"},
    }
    resolved = resolve_args(args, previous)
    assert resolved["ids"] == ["INBOX:1"]
    assert "#ids" not in resolved


# --- Policy enforcement tests ---


def test_unknown_method_returns_unknown_method_error() -> None:
    executor, _ = _make_executor()
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core"],
            "methodCalls": [["NonExistent/method", {"accountId": "work"}, "c0"]],
        }
    )
    response = executor.execute(request)
    method, args, _ = response.methodResponses[0]
    assert method == "error"
    assert args["type"] == "unknownMethod"


def test_email_set_with_destroy_returns_forbidden() -> None:
    executor, _ = _make_executor()
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
            "methodCalls": [
                ["Email/set", {"accountId": "work", "destroy": ["INBOX:1"]}, "c0"],
            ],
        }
    )
    response = executor.execute(request)
    method, args, _ = response.methodResponses[0]
    assert method == "error"
    assert args["type"] == "forbidden"


def test_multi_call_result_ref_resolved() -> None:
    """Second call's #ids should be resolved from first call's response."""
    executor, _ = _make_executor()

    with (
        patch("mailjail.executor.handle_email_query") as mock_query,
        patch("mailjail.executor.handle_email_get") as mock_get,
    ):
        mock_query.return_value = (
            "Email/query",
            {"accountId": "work", "ids": ["INBOX:5", "INBOX:6"], "total": 2, "position": 0},
        )
        mock_get.return_value = (
            "Email/get",
            {"accountId": "work", "list": [], "notFound": [], "state": "0"},
        )
        request = JMAPRequest.model_validate(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    ["Email/query", {"accountId": "work", "filter": {}}, "c0"],
                    [
                        "Email/get",
                        {
                            "accountId": "work",
                            "#ids": {
                                "resultOf": "c0",
                                "name": "Email/query",
                                "path": "/ids",
                            },
                        },
                        "c1",
                    ],
                ],
            }
        )
        response = executor.execute(request)

    assert len(response.methodResponses) == 2
    get_args, _ = mock_get.call_args[0]
    assert get_args["ids"] == ["INBOX:5", "INBOX:6"]


def test_mailbox_get_dispatches_to_handler() -> None:
    executor, _ = _make_executor()
    with patch("mailjail.executor.handle_mailbox_get") as mock_handler:
        mock_handler.return_value = (
            "Mailbox/get",
            {"accountId": "work", "list": [], "notFound": [], "state": "0"},
        )
        request = JMAPRequest.model_validate(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [["Mailbox/get", {"accountId": "work"}, "c0"]],
            }
        )
        response = executor.execute(request)

    mock_handler.assert_called_once()
    method, _, call_id = response.methodResponses[0]
    assert method == "Mailbox/get"
    assert call_id == "c0"


# --- Multi-account routing tests (5.5) ---


def test_missing_account_id_returns_account_not_found() -> None:
    executor, _ = _make_executor()
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core"],
            "methodCalls": [["Mailbox/get", {}, "c0"]],
        }
    )
    response = executor.execute(request)
    method, args, _ = response.methodResponses[0]
    assert method == "error"
    assert args["type"] == "accountNotFound"


def test_unknown_account_id_returns_account_not_found() -> None:
    executor, _ = _make_executor("work")
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core"],
            "methodCalls": [["Mailbox/get", {"accountId": "ghost"}, "c0"]],
        }
    )
    response = executor.execute(request)
    method, args, _ = response.methodResponses[0]
    assert method == "error"
    assert args["type"] == "accountNotFound"


def test_request_routes_to_correct_pool() -> None:
    """Two accounts → each call must use its own pool."""
    pool_work = MagicMock(name="pool_work")
    pool_personal = MagicMock(name="pool_personal")
    settings_work = make_account_settings(imap_username="work@example.com")
    settings_personal = make_account_settings(imap_username="me@example.com")

    from mailjail.config import AccountSettings as _AS  # noqa
    from mailjail.registry import AccountContext, AccountRegistry

    registry = AccountRegistry(
        {"work": settings_work, "personal": settings_personal},
        pool_factory=lambda s: pool_work
        if s.imap_username == "work@example.com"
        else pool_personal,
    )
    registry._contexts["work"] = AccountContext(settings=settings_work, pool=pool_work)
    registry._contexts["personal"] = AccountContext(
        settings=settings_personal, pool=pool_personal
    )
    executor = Executor(registry=registry)

    with patch("mailjail.executor.handle_mailbox_get") as mock_handler:
        mock_handler.side_effect = lambda args, pool: (
            "Mailbox/get",
            {"accountId": args["accountId"], "list": [], "notFound": [], "state": "0"},
        )
        request = JMAPRequest.model_validate(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    ["Mailbox/get", {"accountId": "work"}, "c0"],
                    ["Mailbox/get", {"accountId": "personal"}, "c1"],
                ],
            }
        )
        executor.execute(request)

    pools_used = [call.args[1] for call in mock_handler.call_args_list]
    assert pools_used == [pool_work, pool_personal]


def test_email_submission_set_logs_account_username(caplog) -> None:
    """EmailSubmission/set should receive the account's settings."""
    import logging

    executor, _ = _make_executor("work")
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:submission"],
            "methodCalls": [
                [
                    "EmailSubmission/set",
                    {
                        "accountId": "work",
                        "create": {"sub1": {"emailId": "Drafts:42"}},
                    },
                    "c0",
                ],
            ],
        }
    )
    with caplog.at_level(logging.INFO, logger="mailjail.models.submission"):
        response = executor.execute(request)

    method, body, _ = response.methodResponses[0]
    assert method == "EmailSubmission/set"
    assert body["mailjail:intercepted"] is True
    assert any("test@example.com" in rec.message for rec in caplog.records)


# --- Per-call error and connection boundary ---


def _offline_executor(pool_factory: MagicMock) -> Executor:
    """Executor whose only account has no pool yet; IMAP comes from the factory."""
    registry = AccountRegistry(
        {"work": make_account_settings()}, pool_factory=pool_factory
    )
    return Executor(registry=registry)


def _execute(executor: Executor, method_calls: list[list]) -> list:
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
            "methodCalls": method_calls,
        }
    )
    return executor.execute(request).methodResponses


@pytest.mark.parametrize(
    ("middle_call", "error_type", "factory_calls"),
    [
        pytest.param(
            [
                "Email/get",
                {
                    "accountId": "work",
                    "#ids": {"resultOf": "nope", "name": "Email/query", "path": "/ids"},
                },
                "c1",
            ],
            "invalidResultReference",
            0,
            id="unresolvable-reference",
        ),
        pytest.param(
            ["Mailbox/get", {"accountId": "work"}, "c1"],
            "serverFail",
            1,
            id="failing-pool-factory",
        ),
    ],
)
def test_failed_middle_call_keeps_call_ids_and_later_calls_run(
    middle_call: list, error_type: str, factory_calls: int
) -> None:
    factory = MagicMock(side_effect=ConnectionError("IMAP unreachable"))
    executor = _offline_executor(factory)

    responses = _execute(
        executor,
        [
            ["Thread/get", {"accountId": "work", "ids": ["INBOX:1"]}, "c0"],
            middle_call,
            [
                "Thread/get",
                {
                    "accountId": "work",
                    "#ids": {
                        "resultOf": "c0",
                        "name": "Thread/get",
                        "path": "/list/0/emailIds",
                    },
                },
                "c2",
            ],
        ],
    )

    assert [call_id for _, _, call_id in responses] == ["c0", "c1", "c2"]
    method, body, _ = responses[1]
    assert method == "error"
    assert body["type"] == error_type
    method, body, _ = responses[2]
    assert method == "Thread/get"
    assert body["list"] == [{"id": "INBOX:1", "emailIds": ["INBOX:1"]}]
    assert factory.call_count == factory_calls


@pytest.mark.parametrize(
    "ref",
    [
        pytest.param("c0", id="not-an-object"),
        pytest.param({"resultOf": "c0", "name": "Thread/get"}, id="no-path"),
        pytest.param(
            {"resultOf": "c0", "name": "Thread/get", "path": "list"}, id="relative-path"
        ),
        pytest.param(
            {"resultOf": "c0", "name": "Thread/get", "path": "/list/9"},
            id="index-out-of-range",
        ),
        pytest.param(
            {"resultOf": "c0", "name": "Thread/get", "path": "/list/x"},
            id="non-numeric-index",
        ),
        pytest.param(
            {"resultOf": "c0", "name": "Thread/get", "path": 5}, id="int-path"
        ),
    ],
)
def test_malformed_result_reference_returns_invalid_result_reference(
    ref: object,
) -> None:
    executor = _offline_executor(MagicMock())

    responses = _execute(
        executor,
        [
            ["Thread/get", {"accountId": "work", "ids": []}, "c0"],
            ["Thread/get", {"accountId": "work", "#ids": ref}, "c1"],
        ],
    )

    method, body, call_id = responses[1]
    assert (method, body["type"], call_id) == ("error", "invalidResultReference", "c1")


def test_pool_free_methods_never_invoke_pool_factory() -> None:
    factory = MagicMock(side_effect=AssertionError("pool factory must not run"))
    executor = _offline_executor(factory)

    responses = _execute(
        executor,
        [
            ["Thread/get", {"accountId": "work", "ids": ["INBOX:1"]}, "c0"],
            ["Email/changes", {"accountId": "work", "sinceState": "x"}, "c1"],
            [
                "EmailSubmission/set",
                {"accountId": "work", "create": {"s1": {"emailId": "Drafts:1"}}},
                "c2",
            ],
        ],
    )

    factory.assert_not_called()
    assert [(method, call_id) for method, _, call_id in responses] == [
        ("Thread/get", "c0"),
        ("error", "c1"),
        ("EmailSubmission/set", "c2"),
    ]
    assert responses[1][1]["type"] == "cannotCalculateChanges"
    assert responses[2][1]["mailjail:intercepted"] is True


def test_unknown_account_on_pool_free_method_returns_account_not_found() -> None:
    factory = MagicMock()
    executor = _offline_executor(factory)

    responses = _execute(
        executor,
        [
            [
                "EmailSubmission/set",
                {"accountId": "ghost", "create": {"s1": {"emailId": "Drafts:1"}}},
                "c0",
            ],
        ],
    )

    method, body, call_id = responses[0]
    assert (method, body["type"], call_id) == ("error", "accountNotFound", "c0")
    factory.assert_not_called()


def test_forbidden_email_set_never_invokes_pool_factory() -> None:
    factory = MagicMock()
    executor = _offline_executor(factory)

    responses = _execute(
        executor, [["Email/set", {"accountId": "work", "destroy": ["INBOX:1"]}, "c0"]]
    )

    assert responses[0][1]["type"] == "forbidden"
    factory.assert_not_called()
