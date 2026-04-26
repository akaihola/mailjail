"""Tests for the WSGI app routing (multi-account)."""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock

from mailjail.app import make_app
from mailjail.config import AccountSettings, Settings
from mailjail.executor import Executor
from mailjail.registry import AccountContext, AccountRegistry


def _settings(primary: str, account_ids: list[str]) -> Settings:
    return Settings(
        primary_account=primary,
        accounts={
            aid: AccountSettings(imap_username=f"{aid}@example.com", imap_password="x")
            for aid in account_ids
        },
    )


def _registry_with_pools(
    settings: Settings, *, healthy: dict[str, bool]
) -> tuple[AccountRegistry, dict[str, MagicMock]]:
    pools = {aid: MagicMock(name=f"pool_{aid}") for aid in settings.accounts}
    for aid, pool in pools.items():
        pool.health_check.return_value = healthy.get(aid, True)
    registry = AccountRegistry(
        settings.accounts, pool_factory=lambda s: pools[
            next(k for k, v in settings.accounts.items() if v is s)
        ]
    )
    for aid, pool in pools.items():
        registry._contexts[aid] = AccountContext(
            settings=settings.accounts[aid], pool=pool
        )
    return registry, pools


def _call(app, method: str, path: str, body: bytes = b"", content_type: str = "") -> tuple[str, dict]:
    captured: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    result = b"".join(app(environ, start_response))
    return captured["status"], json.loads(result) if result else {}


def test_well_known_jmap_returns_multi_account_session() -> None:
    settings = _settings("work", ["work", "personal"])
    registry, _ = _registry_with_pools(settings, healthy={"work": True, "personal": True})
    executor = Executor(registry=registry)
    app = make_app(executor=executor, registry=registry, settings=settings)

    status, body = _call(app, "GET", "/.well-known/jmap")

    assert status == "200 OK"
    assert set(body["accounts"]) == {"work", "personal"}
    assert body["primaryAccounts"]["urn:ietf:params:jmap:mail"] == "work"


def test_healthz_reports_per_account_status() -> None:
    settings = _settings("work", ["work", "personal"])
    registry, _ = _registry_with_pools(
        settings, healthy={"work": True, "personal": False}
    )
    executor = Executor(registry=registry)
    app = make_app(executor=executor, registry=registry, settings=settings)

    status, body = _call(app, "GET", "/healthz")

    assert status == "200 OK"
    assert body["status"] == "ok"
    assert body["accounts"]["work"] == {"imap": "connected"}
    assert body["accounts"]["personal"] == {"imap": "disconnected"}


def test_healthz_returns_error_when_primary_down() -> None:
    settings = _settings("work", ["work", "personal"])
    registry, _ = _registry_with_pools(
        settings, healthy={"work": False, "personal": True}
    )
    executor = Executor(registry=registry)
    app = make_app(executor=executor, registry=registry, settings=settings)

    status, body = _call(app, "GET", "/healthz")

    assert status == "503 Service Unavailable"
    assert body["status"] == "error"
    assert body["accounts"]["work"] == {"imap": "disconnected"}


def test_post_jmap_routes_through_executor() -> None:
    settings = _settings("work", ["work"])
    registry, pools = _registry_with_pools(settings, healthy={"work": True})
    executor = Executor(registry=registry)
    app = make_app(executor=executor, registry=registry, settings=settings)

    from unittest.mock import patch

    with patch("mailjail.executor.handle_mailbox_get") as mock_handler:
        mock_handler.return_value = (
            "Mailbox/get",
            {"accountId": "work", "list": [], "notFound": [], "state": "0"},
        )
        body = json.dumps(
            {
                "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
                "methodCalls": [["Mailbox/get", {"accountId": "work"}, "c0"]],
            }
        ).encode()
        status, resp = _call(
            app, "POST", "/jmap", body=body, content_type="application/json"
        )

    assert status == "200 OK"
    method, args, call_id = resp["methodResponses"][0]
    assert method == "Mailbox/get"
    assert call_id == "c0"
    mock_handler.assert_called_once()
    assert mock_handler.call_args.args[1] is pools["work"]
