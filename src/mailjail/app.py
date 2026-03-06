"""WSGI application and routing for mailjail."""

import json
import logging
from typing import Any, Callable

from pydantic import ValidationError

from .config import Settings
from .executor import Executor
from .imap.connection import IMAPPool
from .models.core import JMAPErrorType, JMAPRequest, make_error_invocation
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


def make_app(
    executor: Executor,
    pool: IMAPPool,
    settings: Settings,
) -> Callable:
    """Return a WSGI callable routing:

    POST  /jmap                → executor.execute()
    GET   /.well-known/jmap    → session_resource()
    GET   /healthz             → pool.health_check()
    All other routes           → 404
    """

    def app(environ: dict, start_response: Callable) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")

        # /.well-known/jmap — session resource
        if method == "GET" and path == "/.well-known/jmap":
            return _json_response(start_response, "200 OK", session_resource(settings))

        # /healthz — health check
        if method == "GET" and path == "/healthz":
            imap_ok = pool.health_check()
            status_code = "200 OK" if imap_ok else "503 Service Unavailable"
            body = {
                "status": "ok" if imap_ok else "error",
                "imap": "connected" if imap_ok else "disconnected",
            }
            return _json_response(start_response, status_code, body)

        # POST /jmap — JMAP API endpoint
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

            # JMAP spec: always return 200, errors are in methodResponses
            return _json_response(
                start_response,
                "200 OK",
                response.model_dump(),
            )

        # 404 for everything else
        return _json_response(
            start_response,
            "404 Not Found",
            {"type": "notFound", "description": f"No route for {method} {path}"},
        )

    return app
