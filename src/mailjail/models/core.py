"""JMAP core models: Request, Response, Invocation, error types."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel

Invocation = tuple[str, dict[str, Any], str]


class JMAPErrorType(StrEnum):
    FORBIDDEN = "forbidden"
    INVALID_ARGUMENTS = "invalidArguments"
    SERVER_FAIL = "serverFail"
    NOT_FOUND = "notFound"
    TOO_LARGE = "tooLarge"
    UNKNOWN_METHOD = "unknownMethod"


class JMAPRequest(BaseModel):
    using: list[str]
    methodCalls: list[tuple[str, dict[str, Any], str]]


class JMAPResponse(BaseModel):
    methodResponses: list[tuple[str, dict[str, Any], str]]


def make_error_invocation(
    type_: JMAPErrorType, description: str, call_id: str
) -> Invocation:
    """Build an error invocation triple."""
    return ("error", {"type": str(type_), "description": description}, call_id)
