"""IMAP connection pool using queue.Queue for thread-safe access."""

import logging
import queue
from contextlib import contextmanager
from typing import Generator

from imap_tools import MailBox

logger = logging.getLogger(__name__)


class IMAPPool:
    """Thread-safe pool of logged-in IMAP connections.

    Uses queue.Queue for thread safety. Each borrow validates with NOOP
    and reconnects on failure before yielding to the caller.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        size: int = 3,
        ssl: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._ssl = ssl
        self._pool: queue.Queue[MailBox] = queue.Queue(maxsize=size)
        self._capabilities: frozenset[str] = frozenset()
        for _ in range(size):
            self._pool.put(self._make_connection())

    def _make_connection(self) -> MailBox:
        """Create and return a logged-in MailBox with initial_folder=None.

        initial_folder=None avoids the implicit SELECT INBOX on login,
        which is important because we explicitly select folders before each operation.
        """
        mb = MailBox(host=self._host, port=self._port)
        mb.login(self._username, self._password, initial_folder=None)
        if not self._capabilities:
            try:
                caps = mb.client.capabilities  # imaplib exposes a tuple
                self._capabilities = frozenset(c.upper() for c in caps)
                logger.info(
                    "IMAP server %s:%s capabilities: SORT=%s CONDSTORE=%s",
                    self._host,
                    self._port,
                    "SORT" in self._capabilities,
                    "CONDSTORE" in self._capabilities,
                )
            except Exception:
                logger.debug("Could not read IMAP capabilities", exc_info=True)
        return mb

    @property
    def capabilities(self) -> frozenset[str]:
        """Cached IMAP CAPABILITY set (uppercased). Empty if probe failed."""
        return self._capabilities

    def has_capability(self, name: str) -> bool:
        return name.upper() in self._capabilities

    @contextmanager
    def connection(self) -> Generator[MailBox, None, None]:
        """Borrow a connection from the pool.

        Validates with NOOP before yielding. On any exception during use,
        the connection is replaced with a fresh one before being returned
        to the pool (never return a broken connection).

        Blocks for up to 30 seconds waiting for an available connection.
        """
        mb = self._pool.get(timeout=30)
        healthy = True
        try:
            # Validate connection is still alive
            try:
                mb.client.noop()
            except Exception:
                logger.warning("IMAP NOOP failed; reconnecting")
                try:
                    mb.logout()
                except Exception:
                    pass
                mb = self._make_connection()
            yield mb
        except Exception:
            healthy = False
            raise
        finally:
            if not healthy:
                # Replace broken connection with a fresh one
                try:
                    mb.logout()
                except Exception:
                    pass
                try:
                    mb = self._make_connection()
                except Exception:
                    logger.error("Failed to create replacement IMAP connection")
            self._pool.put(mb)

    def health_check(self) -> bool:
        """Borrow one connection, send NOOP, return it. Return False on any error."""
        try:
            with self.connection() as mb:
                mb.client.noop()
            return True
        except Exception:
            logger.exception("IMAP health check failed")
            return False

    def close(self) -> None:
        """Drain pool and logout all connections."""
        while not self._pool.empty():
            try:
                mb = self._pool.get_nowait()
                mb.logout()
            except Exception:
                pass
