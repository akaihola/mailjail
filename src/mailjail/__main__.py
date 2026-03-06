"""mailjail server entry point."""

import logging

from waitress import serve

from .app import make_app
from .config import load_settings
from .executor import Executor
from .imap.connection import IMAPPool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    settings = load_settings()
    pool = IMAPPool(
        host=settings.imap_host,
        port=settings.imap_port,
        username=settings.imap_username,
        password=settings.imap_password,
        size=settings.pool_size,
        ssl=settings.imap_ssl,
    )
    executor = Executor(pool=pool, settings=settings)
    app = make_app(executor=executor, pool=pool, settings=settings)
    logger.info(
        "mailjail listening on %s:%s", settings.server_host, settings.server_port
    )
    serve(app, host=settings.server_host, port=settings.server_port, threads=4)


if __name__ == "__main__":
    main()
