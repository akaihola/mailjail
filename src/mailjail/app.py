"""WSGI application and routing for mailjail."""

import json
import logging
from typing import Any, Callable

from pydantic import ValidationError

from .config import Settings
from .executor import Executor
from .models.core import JMAPErrorType, JMAPRequest, make_error_invocation
from .registry import AccountRegistry
from .session import session_resource

logger = logging.getLogger(__name__)


def _json_response(
    start_response: Callable,
    status: str,
    body: Any,
) -> list[bytes]:
    """Serialise body to JSON and call start_response."""
    data = json.dumps(body, default=str).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(data))),
        ],
    )
    return [data]


def _healthz_body(
    registry: AccountRegistry, primary_account: str
) -> tuple[bool, dict[str, Any]]:
    """Return (overall_ok, response_body) for /healthz.

    Probes every configured account's pool (lazily creates if not yet
    materialised). Overall status is ``ok`` iff the primary account's pool
    is healthy; secondary failures degrade per-account status but not
    overall.
    """
    per_account: dict[str, dict[str, str]] = {}
    primary_ok = False
    for account_id in registry.account_ids():
        try:
            ctx = registry.get(account_id)
            ok = ctx.pool.health_check()
        except Exception:
            logger.exception("Health check failed for account %r", account_id)
            ok = False
        per_account[account_id] = {"imap": "connected" if ok else "disconnected"}
        if account_id == primary_account:
            primary_ok = ok
    return primary_ok, {
        "status": "ok" if primary_ok else "error",
        "accounts": per_account,
    }


def make_app(
    executor: Executor,
    registry: AccountRegistry,
    settings: Settings,
) -> Callable:
    """Return a WSGI callable routing:

    POST  /jmap                → executor.execute()
    GET   /.well-known/jmap    → session_resource()
    GET   /healthz             → per-account pool health
    All other routes           → 404
    """

    def app(environ: dict, start_response: Callable) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/.well-known/jmap":
            return _json_response(start_response, "200 OK", session_resource(settings))

        if method == "GET" and path == "/healthz":
            primary_ok, body = _healthz_body(registry, settings.primary_account)
            status_code = "200 OK" if primary_ok else "503 Service Unavailable"
            return _json_response(start_response, status_code, body)

        if method == "POST" and path == "/jmap":
            content_type = environ.get("CONTENT_TYPE", "")
            if "application/json" not in content_type:
                return _json_response(
                    start_response,
                    "415 Unsupported Media Type",
                    {"type": "urn:ietf:params:jmap:error:notRequest"},
                )

            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
                body_bytes = environ["wsgi.input"].read(content_length)
                raw = json.loads(body_bytes)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                return _json_response(
                    start_response,
                    "400 Bad Request",
                    {"type": "invalidArguments", "description": str(exc)},
                )

            try:
                request = JMAPRequest.model_validate(raw)
            except ValidationError as exc:
                return _json_response(
                    start_response,
                    "400 Bad Request",
                    {
                        "type": "invalidArguments",
                        "description": str(exc),
                    },
                )

            try:
                response = executor.execute(request)
            except Exception as exc:
                logger.exception("Executor error")
                inv = make_error_invocation(
                    JMAPErrorType.SERVER_FAIL, str(exc), "unknown"
                )
                return _json_response(
                    start_response,
                    "200 OK",
                    {"methodResponses": [list(inv)]},
                )

            return _json_response(
                start_response,
                "200 OK",
                response.model_dump(),
            )

        return _json_response(
            start_response,
            "404 Not Found",
            {"type": "notFound", "description": f"No route for {method} {path}"},
        )

    return app
