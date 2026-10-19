"""Per-account IMAP pool registry with thread-safe lazy initialisation."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from .config import AccountSettings
from .imap.connection import IMAPPool

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AccountContext:
    settings: AccountSettings
    pool: IMAPPool


PoolFactory = Callable[[AccountSettings], IMAPPool]


def _default_pool_factory(settings: AccountSettings) -> IMAPPool:
    return IMAPPool(
        host=settings.imap_host,
        port=settings.imap_port,
        username=settings.imap_username,
        password=settings.imap_password,
        size=settings.pool_size,
        ssl=settings.imap_ssl,
        tls_insecure=settings.imap_tls_insecure,
        oauth2_refresh_token=(
            settings.oauth2_refresh_token.get_secret_value()
            if settings.oauth2_refresh_token is not None
            else None
        ),
    )


class AccountRegistry:
    """Owns one ``IMAPPool`` per configured account.

    Pools are created lazily on the first ``get(account_id)`` call. Construction
    failures are not cached: a subsequent ``get`` retries. Lock granularity is
    per-account so a slow account does not block others.
    """

    def __init__(
        self,
        accounts: dict[str, AccountSettings],
        *,
        pool_factory: PoolFactory = _default_pool_factory,
    ) -> None:
        self._account_settings = dict(accounts)
        self._pool_factory = pool_factory
        self._contexts: dict[str, AccountContext] = {}
        # Guards _contexts writes and _closed: publication and close() are
        # ordered, so close() either sees a new pool or its creator sees close().
        self._global_lock = threading.Lock()
        self._closed = False
        self._account_locks: dict[str, threading.Lock] = {
            account_id: threading.Lock() for account_id in accounts
        }

    def __contains__(self, account_id: str) -> bool:
        return account_id in self._account_settings

    def account_ids(self) -> list[str]:
        return list(self._account_settings)

    def settings_for(self, account_id: str) -> AccountSettings:
        return self._account_settings[account_id]

    def get(self, account_id: str) -> AccountContext:
        """Return the materialised ``AccountContext`` for ``account_id``.

        Raises ``KeyError`` if no such account is configured. Pool construction
        happens once, under a per-account lock; failures do not poison the
        registry — the next call retries. Raises ``RuntimeError`` after
        ``close()``, closing any pool whose login finished after it.
        """
        if account_id not in self._account_settings:
            raise KeyError(account_id)

        cached = self._contexts.get(account_id)
        if cached is not None:
            return cached

        lock = self._account_locks[account_id]
        with lock:
            cached = self._contexts.get(account_id)
            if cached is not None:
                return cached
            if not self._closed:
                settings = self._account_settings[account_id]
                pool = self._pool_factory(settings)  # network login, no global lock
                with self._global_lock:
                    if not self._closed:
                        context = AccountContext(settings=settings, pool=pool)
                        self._contexts[account_id] = context
                        return context
                pool.close()
            raise RuntimeError("account registry is closed")

    def materialised(self) -> dict[str, AccountContext]:
        """Return a copy of currently-materialised contexts (no lazy init)."""
        with self._global_lock:
            return dict(self._contexts)

    def close(self) -> None:
        """Close every materialised pool. Safe to call repeatedly."""
        with self._global_lock:
            self._closed = True
            contexts = list(self._contexts.values())
            self._contexts.clear()
        for ctx in contexts:
            try:
                ctx.pool.close()
            except Exception:
                logger.exception("Error closing pool")
