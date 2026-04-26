"""Tests for JMAP core models."""

import pytest
from pydantic import ValidationError

from mailjail.models.core import (
    JMAPErrorType,
    JMAPRequest,
    JMAPResponse,
    make_error_invocation,
)


def test_jmap_request_parses_valid_request() -> None:
    data = {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [
            ["Email/query", {"accountId": "default"}, "c0"],
        ],
    }
    req = JMAPRequest.model_validate(data)
    assert req.using == ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"]
    assert len(req.methodCalls) == 1
    assert req.methodCalls[0] == ("Email/query", {"accountId": "default"}, "c0")


def test_jmap_request_rejects_non_3tuple_method_calls() -> None:
    data = {
        "using": ["urn:ietf:params:jmap:core"],
        "methodCalls": [
            ["Email/query", {"accountId": "default"}],  # missing call_id
        ],
    }
    with pytest.raises(ValidationError):
        JMAPRequest.model_validate(data)


def test_jmap_request_rejects_empty_method_calls_entry() -> None:
    data = {
        "using": ["urn:ietf:params:jmap:core"],
        "methodCalls": [
            ["Email/query"],  # only one element
        ],
    }
    with pytest.raises(ValidationError):
        JMAPRequest.model_validate(data)


def test_jmap_response_serialises_correctly() -> None:
    resp = JMAPResponse(
        methodResponses=[
            ("Email/query", {"ids": ["INBOX:1"]}, "c0"),
        ]
    )
    dumped = resp.model_dump()
    assert "methodResponses" in dumped
    assert len(dumped["methodResponses"]) == 1
    assert dumped["methodResponses"][0][0] == "Email/query"


def test_make_error_invocation_returns_correct_tuple() -> None:
    inv = make_error_invocation(JMAPErrorType.FORBIDDEN, "no destroy allowed", "c0")
    assert inv[0] == "error"
    assert inv[1]["type"] == "forbidden"
    assert inv[1]["description"] == "no destroy allowed"
    assert inv[2] == "c0"


def test_make_error_invocation_unknown_method() -> None:
    inv = make_error_invocation(JMAPErrorType.UNKNOWN_METHOD, "no such method", "c1")
    assert inv[0] == "error"
    assert inv[1]["type"] == "unknownMethod"
    assert inv[2] == "c1"


def test_jmap_error_type_values() -> None:
    assert JMAPErrorType.FORBIDDEN == "forbidden"
    assert JMAPErrorType.INVALID_ARGUMENTS == "invalidArguments"
    assert JMAPErrorType.SERVER_FAIL == "serverFail"
    assert JMAPErrorType.NOT_FOUND == "notFound"
    assert JMAPErrorType.TOO_LARGE == "tooLarge"
    assert JMAPErrorType.UNKNOWN_METHOD == "unknownMethod"
    assert JMAPErrorType.ACCOUNT_NOT_FOUND == "accountNotFound"


def test_make_error_invocation_account_not_found() -> None:
    inv = make_error_invocation(
        JMAPErrorType.ACCOUNT_NOT_FOUND, "no such account", "c2"
    )
    assert inv == (
        "error",
        {"type": "accountNotFound", "description": "no such account"},
        "c2",
    )
