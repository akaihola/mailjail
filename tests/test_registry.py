"""Tests for the per-account IMAP pool registry."""

from unittest.mock import MagicMock

import pytest

from mailjail.config import AccountSettings
from mailjail.registry import AccountRegistry


def _settings(username: str = "u@example.com") -> AccountSettings:
    return AccountSettings(imap_username=username, imap_password="x")


def test_get_returns_context_for_known_account() -> None:
    s = _settings()
    factory = MagicMock(return_value=MagicMock(name="pool"))
    registry = AccountRegistry({"work": s}, pool_factory=factory)

    ctx = registry.get("work")

    assert ctx.settings is s
    assert ctx.pool is factory.return_value


def test_get_unknown_account_raises_keyerror() -> None:
    registry = AccountRegistry({"work": _settings()})
    with pytest.raises(KeyError):
        registry.get("ghost")


def test_pool_is_lazy() -> None:
    factory = MagicMock(return_value=MagicMock())
    registry = AccountRegistry({"work": _settings()}, pool_factory=factory)
    assert factory.call_count == 0
    registry.get("work")
    assert factory.call_count == 1


def test_get_returns_same_pool_on_subsequent_calls() -> None:
    factory = MagicMock(return_value=MagicMock())
    registry = AccountRegistry({"work": _settings()}, pool_factory=factory)
    a = registry.get("work")
    b = registry.get("work")
    assert a is b
    assert factory.call_count == 1


def test_close_closes_all_materialised_pools() -> None:
    pool_w = MagicMock()
    pool_p = MagicMock()
    pools = iter([pool_w, pool_p])
    registry = AccountRegistry(
        {"work": _settings("w@x"), "personal": _settings("p@x")},
        pool_factory=lambda _s: next(pools),
    )
    registry.get("work")
    registry.get("personal")

    registry.close()

    pool_w.close.assert_called_once()
    pool_p.close.assert_called_once()


def test_close_does_not_call_unmaterialised_pools() -> None:
    factory = MagicMock(return_value=MagicMock())
    registry = AccountRegistry(
        {"work": _settings("w@x"), "personal": _settings("p@x")},
        pool_factory=factory,
    )
    registry.get("work")  # materialise only one
    registry.close()
    assert factory.call_count == 1


def test_pool_failure_for_one_account_does_not_block_others() -> None:
    pool_p = MagicMock()

    def factory(s: AccountSettings):
        if s.imap_username == "fail@x":
            raise RuntimeError("boom")
        return pool_p

    registry = AccountRegistry(
        {"work": _settings("fail@x"), "personal": _settings("p@x")},
        pool_factory=factory,
    )

    with pytest.raises(RuntimeError):
        registry.get("work")
    # personal still works
    assert registry.get("personal").pool is pool_p


def test_pool_failure_is_retried_on_next_get() -> None:
    attempts = [RuntimeError("boom"), MagicMock(name="pool")]

    def factory(_s: AccountSettings):
        v = attempts.pop(0)
        if isinstance(v, Exception):
            raise v
        return v

    registry = AccountRegistry({"work": _settings()}, pool_factory=factory)
    with pytest.raises(RuntimeError):
        registry.get("work")
    # second call retries and succeeds
    assert registry.get("work").pool is not None
