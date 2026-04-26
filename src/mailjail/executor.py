"""JMAP request executor: result-ref resolution, method dispatch, policy enforcement."""

import logging
from typing import Any

from .models.core import (
    Invocation,
    JMAPErrorType,
    JMAPRequest,
    JMAPResponse,
    make_error_invocation,
)
from .models.email import handle_email_get, handle_email_query
from .models.email_set import handle_email_set
from .models.mailbox import handle_mailbox_get
from .models.submission import handle_email_submission_set
from .policy import (
    ALLOWED_METHODS,
    BLOCKED_METHODS,
    RESTRICTED_METHODS,
    check_email_set,
)
from .registry import AccountRegistry

logger = logging.getLogger(__name__)


def _json_pointer_get(obj: Any, pointer: str) -> Any:
    """Resolve a JSON Pointer (RFC 6901) against obj.

    Raises KeyError or IndexError on miss.
    The pointer must start with '/'.
    """
    if not pointer.startswith("/"):
        raise ValueError(f"JSON Pointer must start with '/': {pointer!r}")

    parts = pointer[1:].split("/")
    current = obj
    for part in parts:
        # Unescape RFC 6901 tokens (~1 → '/', ~0 → '~')
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(
                f"Cannot traverse {type(current).__name__} with key {part!r}"
            )
    return current


def resolve_result_ref(
    ref: dict[str, Any],
    previous_responses: list[Invocation],
) -> Any:
    """Resolve a JMAP result reference dict (RFC 8620 §3.7).

    ref = {"resultOf": call_id, "name": method_name, "path": json_pointer}

    Finds the invocation in previous_responses matching call_id + name,
    then applies path as a JSON pointer to the response args dict.
    """
    call_id = ref["resultOf"]
    method_name = ref["name"]
    path = ref["path"]

    for method, args, resp_call_id in previous_responses:
        if resp_call_id == call_id and method == method_name:
            return _json_pointer_get(args, path)

    raise KeyError(
        f"No previous response found for resultOf={call_id!r} name={method_name!r}"
    )


def resolve_args(
    args: dict[str, Any],
    previous_responses: list[Invocation],
) -> dict[str, Any]:
    """Recursively walk args; for any key starting with '#', treat the value as
    a result reference and replace the key (without '#') with the resolved value.

    Recurses into nested dicts and lists so that result references inside
    'create' objects (e.g. '#emailId' inside create.sub1) are resolved too.
    """
    result: dict[str, Any] = {}
    for key, value in args.items():
        if key.startswith("#"):
            resolved_key = key[1:]
            result[resolved_key] = resolve_result_ref(value, previous_responses)
        else:
            result[key] = _resolve_value(value, previous_responses)
    return result


def _resolve_value(value: Any, previous_responses: list[Invocation]) -> Any:
    """Recursively resolve result references inside nested dicts and lists."""
    if isinstance(value, dict):
        return resolve_args(value, previous_responses)
    if isinstance(value, list):
        return [_resolve_value(item, previous_responses) for item in value]
    return value


class Executor:
    """Execute JMAP method calls in order, resolving result references."""

    def __init__(self, registry: AccountRegistry) -> None:
        self._registry = registry

    def execute(self, request: JMAPRequest) -> JMAPResponse:
        """Execute all method calls in order; resolve result refs; return JMAPResponse."""
        responses: list[Invocation] = []
        for method, args, call_id in request.methodCalls:
            resolved_args = resolve_args(args, responses)
            invocation = self._dispatch(method, resolved_args, call_id)
            responses.append(invocation)
        return JMAPResponse(methodResponses=responses)

    def _dispatch(self, method: str, args: dict[str, Any], call_id: str) -> Invocation:
        """Route method to handler; enforce policy; return Invocation."""
        if method in BLOCKED_METHODS:
            return make_error_invocation(
                JMAPErrorType.FORBIDDEN,
                f"{method} is not permitted by this proxy",
                call_id,
            )

        if method not in ALLOWED_METHODS and method not in RESTRICTED_METHODS:
            return make_error_invocation(
                JMAPErrorType.UNKNOWN_METHOD,
                f"Unknown method: {method}",
                call_id,
            )

        account_id = args.get("accountId")
        if not isinstance(account_id, str) or not account_id:
            return make_error_invocation(
                JMAPErrorType.ACCOUNT_NOT_FOUND,
                "accountId is required and must be a non-empty string",
                call_id,
            )
        try:
            context = self._registry.get(account_id)
        except KeyError:
            return make_error_invocation(
                JMAPErrorType.ACCOUNT_NOT_FOUND,
                f"Unknown accountId: {account_id!r}",
                call_id,
            )

        pool = context.pool
        settings = context.settings

        try:
            if method == "Mailbox/get":
                name, result = handle_mailbox_get(args, pool)
            elif method == "Email/query":
                name, result = handle_email_query(args, pool)
            elif method == "Email/get":
                name, result = handle_email_get(args, pool)
            elif method == "Email/set":
                violations = check_email_set(args)
                if violations:
                    return make_error_invocation(
                        JMAPErrorType.FORBIDDEN,
                        "; ".join(violations),
                        call_id,
                    )
                name, result = handle_email_set(args, pool, settings)
            elif method == "EmailSubmission/set":
                name, result = handle_email_submission_set(args, settings)
            else:
                # Should not reach here given the checks above
                return make_error_invocation(
                    JMAPErrorType.UNKNOWN_METHOD,
                    f"Unhandled method: {method}",
                    call_id,
                )
            return (name, result, call_id)
        except Exception as exc:
            logger.exception("Handler error for method %s call_id %s", method, call_id)
            return make_error_invocation(
                JMAPErrorType.SERVER_FAIL,
                str(exc),
                call_id,
            )
