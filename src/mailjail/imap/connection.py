"""IMAP connection pool using queue.Queue for thread-safe access."""

import imaplib
import logging
import queue
import ssl as ssl_module
import threading
from collections.abc import Generator
from contextlib import contextmanager, suppress

from imap_tools import MailBox

from mailjail.oauth import gmail_access_token

logger = logging.getLogger(__name__)


def _make_insecure_ssl_context() -> ssl_module.SSLContext:
    """Permissive TLS context for legacy mail servers.

    Allows TLS 1.0+, enables SECLEVEL=0 ciphers (RSA-SHA1 etc.), and
    skips hostname/cert verification. Opt-in per account via
    ``imap_tls_insecure``; do not use against modern servers.
    """
    ctx = ssl_module.SSLContext(ssl_module.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl_module.TLSVersion.TLSv1
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    ctx.check_hostname = False
    ctx.verify_mode = ssl_module.CERT_NONE
    return ctx


# Errors that leave an IMAP connection unusable. Server NO/BAD replies
# (imap_tools ``UnexpectedCommandStatusError``, ``imaplib.IMAP4.error``) and
# the caller's own exceptions leave the protocol stream intact.
_TRANSPORT_ERRORS = (OSError, imaplib.IMAP4.abort)


def _shutdown(mb: MailBox) -> None:
    """Drop an unusable connection without a LOGOUT round trip."""
    with suppress(Exception):
        mb.client.shutdown()


def _logout(mb: MailBox) -> None:
    with suppress(Exception):
        mb.logout()


class IMAPPool:
    """Thread-safe pool of logged-in IMAP connections.

    The queue holds exactly ``size`` slots. A slot is an idle logged-in
    ``MailBox`` or ``None``: capacity whose connection was discarded.
    ``connection()`` is the only checkout/return path. It takes a slot,
    NOOP-validates or (re)creates its connection, and always puts one slot
    back. A connection hit by a transport error (``_TRANSPORT_ERRORS``) is
    shut down and its slot goes back empty, so the next borrow of that slot
    reconnects; any other exception returns the connection for reuse. After
    ``close()``, returned connections are logged out instead of queued.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        size: int = 3,
        ssl: bool = True,
        tls_insecure: bool = False,
        oauth2_refresh_token: str | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._oauth2_refresh_token = oauth2_refresh_token
        self._ssl = ssl
        self._tls_insecure = tls_insecure
        self._ssl_context: ssl_module.SSLContext | None = (
            _make_insecure_ssl_context() if tls_insecure else None
        )
        self._pool: queue.Queue[MailBox | None] = queue.Queue(maxsize=size)
        self._lock = threading.Lock()  # orders slot returns against close()
        self._closed = False
        self._capabilities: frozenset[str] = frozenset()
        try:
            for _ in range(size):
                self._pool.put_nowait(self._make_connection())
        except Exception:
            self.close()
            raise

    def _make_connection(self) -> MailBox:
        """Create and return a logged-in MailBox with initial_folder=None.

        initial_folder=None avoids the implicit SELECT INBOX on login,
        which is important because we explicitly select folders before each operation.
        """
        mb = MailBox(host=self._host, port=self._port, ssl_context=self._ssl_context)
        try:
            if self._oauth2_refresh_token is not None:
                token = gmail_access_token(self._oauth2_refresh_token)
                mb.xoauth2(self._username, token, initial_folder=None)
            else:
                mb.login(self._username, self._password, initial_folder=None)
        except Exception:
            _shutdown(mb)
            raise
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
        """Borrow a validated connection; the class docstring has the slot rules.

        Blocks for up to 30 seconds waiting for a free slot.
        """
        mb = self._checkout()
        slot: MailBox | None = mb
        try:
            yield mb
        except _TRANSPORT_ERRORS:
            logger.warning("IMAP transport error; discarding connection")
            _shutdown(mb)
            slot = None
            raise
        finally:
            self._release(slot)

    def _checkout(self) -> MailBox:
        """Take a slot and return its live connection, reconnecting if needed."""
        if self._closed:
            raise RuntimeError("IMAP pool is closed")
        mb = self._pool.get(timeout=30)
        try:
            if mb is not None:
                try:
                    mb.client.noop()
                    return mb
                except Exception:  # noqa: BLE001 - any failed NOOP means unusable
                    logger.warning("IMAP NOOP failed; reconnecting")
                    _shutdown(mb)
            return self._make_connection()
        except BaseException:
            self._release(None)
            raise

    def _release(self, slot: MailBox | None) -> None:
        """Put one slot back, or log its connection out if the pool is closed."""
        with self._lock:
            if not self._closed:
                self._pool.put_nowait(slot)
                return
        if slot is not None:
            _logout(slot)

    def health_check(self) -> bool:
        """Borrow one connection, whose NOOP is the probe. False on any error."""
        try:
            with self.connection():
                pass
            return True
        except Exception:
            logger.exception("IMAP health check failed")
            return False

    def close(self) -> None:
        """Log out idle connections now and borrowed ones when returned."""
        idle: list[MailBox | None] = []
        with self._lock:
            self._closed = True
            while True:
                try:
                    idle.append(self._pool.get_nowait())
                except queue.Empty:
                    break
        for mb in idle:
            if mb is not None:
                _logout(mb)
