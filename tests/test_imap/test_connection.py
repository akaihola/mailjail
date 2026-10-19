"""Borrow, replacement and shutdown rules of IMAPPool (offline)."""

import imaplib
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from mailjail.imap.connection import IMAPPool


class FakeServer:
    """Stands in for ``MailBox``: each call is one new logged-in connection."""

    def __init__(self) -> None:
        self.boxes: list[MagicMock] = []
        self.down = False

    def __call__(self, **_kwargs: object) -> MagicMock:
        if self.down:
            raise OSError("connection refused")
        mb = MagicMock(name=f"mb{len(self.boxes)}")
        self.boxes.append(mb)
        return mb


@pytest.fixture
def server() -> Iterator[FakeServer]:
    fake = FakeServer()
    with patch("mailjail.imap.connection.MailBox", side_effect=fake):
        yield fake


def _pool(size: int = 1) -> IMAPPool:
    return IMAPPool("imap.example.com", 993, "u", "p", size=size)


def _idle(pool: IMAPPool) -> list[MagicMock | None]:
    return list(pool._pool.queue)


def test_failed_noop_is_replaced_within_the_same_borrow(server: FakeServer) -> None:
    pool = _pool()
    [stale] = server.boxes
    stale.client.noop.side_effect = OSError("reset")

    with pool.connection() as mb:
        assert mb is server.boxes[1]

    stale.client.shutdown.assert_called_once()
    assert _idle(pool) == [server.boxes[1]]


def test_failed_noop_and_failed_replacement_queue_an_empty_slot(
    server: FakeServer,
) -> None:
    pool = _pool()
    [stale] = server.boxes
    stale.client.noop.side_effect = OSError("reset")
    server.down = True

    with pytest.raises(OSError, match="refused"), pool.connection():
        pytest.fail("body must not run without a connection")

    stale.client.shutdown.assert_called_once()
    assert _idle(pool) == [None]


def test_borrow_after_failed_replacement_reconnects(server: FakeServer) -> None:
    pool = _pool()
    [stale] = server.boxes
    stale.client.noop.side_effect = OSError("reset")
    server.down = True
    with pytest.raises(OSError), pool.connection():
        pass

    server.down = False
    with pool.connection() as mb:
        assert mb is server.boxes[1]

    assert stale.client.noop.call_count == 1
    assert _idle(pool) == [server.boxes[1]]


def test_failed_reconnect_of_empty_slot_keeps_capacity(server: FakeServer) -> None:
    pool = _pool()
    server.boxes[0].client.noop.side_effect = OSError("reset")
    server.down = True
    for _ in range(2):
        with pytest.raises(OSError), pool.connection():
            pass

    assert _idle(pool) == [None]


def test_consumer_exception_returns_connection_for_reuse(
    server: FakeServer,
) -> None:
    pool = _pool()
    [mb] = server.boxes

    with pytest.raises(ValueError), pool.connection():
        raise ValueError("conversion failed")

    mb.client.shutdown.assert_not_called()
    mb.logout.assert_not_called()
    assert _idle(pool) == [mb]
    assert len(server.boxes) == 1


@pytest.mark.parametrize(
    "error", [OSError("broken pipe"), imaplib.IMAP4.abort("socket error: EOF")]
)
def test_transport_error_discards_connection(
    server: FakeServer, error: Exception
) -> None:
    pool = _pool()
    [mb] = server.boxes

    with pytest.raises(type(error)), pool.connection():
        raise error

    mb.client.shutdown.assert_called_once()
    assert _idle(pool) == [None]
    with pool.connection() as fresh:
        assert fresh is server.boxes[1]


def test_health_check_sends_only_the_borrow_noop(server: FakeServer) -> None:
    pool = _pool()
    [mb] = server.boxes

    assert pool.health_check() is True

    mb.client.noop.assert_called_once()


def test_health_check_fails_when_reconnect_fails(server: FakeServer) -> None:
    pool = _pool()
    server.boxes[0].client.noop.side_effect = OSError("reset")
    server.down = True

    assert pool.health_check() is False
    assert _idle(pool) == [None]


def test_close_logs_out_idle_and_later_returned_connections(
    server: FakeServer,
) -> None:
    pool = _pool(size=2)
    borrowed, idle = server.boxes

    with pool.connection() as mb:
        assert mb is borrowed
        pool.close()
        idle.logout.assert_called_once()

    assert _idle(pool) == []
    borrowed.logout.assert_called_once()


def test_borrow_after_close_raises(server: FakeServer) -> None:
    pool = _pool()
    pool.close()

    with pytest.raises(RuntimeError, match="closed"), pool.connection():
        pass
