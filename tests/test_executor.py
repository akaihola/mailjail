"""Tests for the JMAP executor: policy enforcement, result-ref resolution, dispatch."""

from unittest.mock import MagicMock, patch

from mailjail.config import Settings
from mailjail.executor import (
    Executor,
    _json_pointer_get,
    resolve_args,
    resolve_result_ref,
)
from mailjail.models.core import JMAPRequest


def _make_settings() -> Settings:
    return Settings(imap_username="test@example.com", imap_password="secret")


def _make_executor() -> tuple[Executor, MagicMock]:
    pool = MagicMock()
    settings = _make_settings()
    executor = Executor(pool=pool, settings=settings)
    return executor, pool


# --- JSON Pointer tests ---


def test_json_pointer_get_simple_key() -> None:
    obj = {"ids": ["a", "b", "c"]}
    result = _json_pointer_get(obj, "/ids")
    assert result == ["a", "b", "c"]


def test_json_pointer_get_nested() -> None:
    obj = {"a": {"b": 42}}
    result = _json_pointer_get(obj, "/a/b")
    assert result == 42


def test_json_pointer_get_array_index() -> None:
    obj = {"items": ["x", "y", "z"]}
    result = _json_pointer_get(obj, "/items/1")
    assert result == "y"


# --- Result reference resolution tests ---


def test_resolve_result_ref_simple() -> None:
    previous = [("Email/query", {"ids": ["INBOX:1", "INBOX:2"]}, "c0")]
    ref = {"resultOf": "c0", "name": "Email/query", "path": "/ids"}
    result = resolve_result_ref(ref, previous)
    assert result == ["INBOX:1", "INBOX:2"]


def test_resolve_args_replaces_hash_keys() -> None:
    previous = [("Email/query", {"ids": ["INBOX:1"]}, "c0")]
    args = {
        "accountId": "default",
        "#ids": {"resultOf": "c0", "name": "Email/query", "path": "/ids"},
    }
    resolved = resolve_args(args, previous)
    assert "ids" in resolved
    assert resolved["ids"] == ["INBOX:1"]
    assert "#ids" not in resolved


# --- Policy enforcement tests ---


def test_blocked_method_returns_forbidden() -> None:
    executor, _ = _make_executor()
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
            "methodCalls": [
                ["EmailSubmission/set", {"accountId": "default"}, "c0"],
            ],
        }
    )
    response = executor.execute(request)
    assert len(response.methodResponses) == 1
    method, args, call_id = response.methodResponses[0]
    assert method == "error"
    assert args["type"] == "forbidden"
    assert call_id == "c0"


def test_unknown_method_returns_unknown_method_error() -> None:
    executor, _ = _make_executor()
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core"],
            "methodCalls": [
                ["NonExistent/method", {"accountId": "default"}, "c0"],
            ],
        }
    )
    response = executor.execute(request)
    method, args, call_id = response.methodResponses[0]
    assert method == "error"
    assert args["type"] == "unknownMethod"


def test_email_set_with_destroy_returns_forbidden() -> None:
    executor, _ = _make_executor()
    request = JMAPRequest.model_validate(
        {
            "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
            "methodCalls": [
                [
                    "Email/set",
                    {"accountId": "default", "destroy": ["INBOX:1"]},
                    "c0",
                ],
            ],
        }
    )
    response = executor.execute(request)
    method, args, call_id = response.methodResponses[0]
    assert method == "error"
    assert args["type"] == "forbidden"


def test_multi_call_result_ref_resolved() -> None:
    """Second call's #ids should be resolved from first call's response."""
    executor, pool = _make_executor()

    # Mock Email/query handler to return known IDs
    with (
        patch("mailjail.executor.handle_email_query") as mock_query,
        patch("mailjail.executor.handle_email_get") as mock_get,
    ):
        mock_query.return_value = (
            "Email/query",
            {
                "accountId": "default",
                "ids": ["INBOX:5", "INBOX:6"],
                "total": 2,
                "position": 0,
            },
        )
        mock_get.return_value = (
            "Email/get",
            {"accountId": "default", "list": [], "notFound": [], "state": "0"},
        )

        request = JMAPRequest.model_validate(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    ["Email/query", {"accountId": "default", "filter": {}}, "c0"],
                    [
                        "Email/get",
                        {
                            "accountId": "default",
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
    # Check that Email/get was called with the resolved IDs
    # handle_email_get(args, pool) — args is the first positional arg
    get_args, _ = mock_get.call_args[0]  # positional args: (args, pool)
    assert get_args["ids"] == ["INBOX:5", "INBOX:6"]


def test_mailbox_get_dispatches_to_handler() -> None:
    executor, pool = _make_executor()
    with patch("mailjail.executor.handle_mailbox_get") as mock_handler:
        mock_handler.return_value = (
            "Mailbox/get",
            {"accountId": "default", "list": [], "notFound": [], "state": "0"},
        )
        request = JMAPRequest.model_validate(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [
                    ["Mailbox/get", {"accountId": "default"}, "c0"],
                ],
            }
        )
        response = executor.execute(request)

    mock_handler.assert_called_once()
    method, args, call_id = response.methodResponses[0]
    assert method == "Mailbox/get"
    assert call_id == "c0"
