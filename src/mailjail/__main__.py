"""mailjail server entry point."""

import logging
import os
from pathlib import Path

from waitress import serve

from .app import make_app
from .config import DEFAULT_CONFIG_PATH, load_settings
from .executor import Executor
from .registry import AccountRegistry

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    config_path = Path(os.environ.get("MAILJAIL_CONFIG") or DEFAULT_CONFIG_PATH)
    settings = load_settings(config_path)
    registry = AccountRegistry(settings.accounts)
    executor = Executor(registry=registry)
    app = make_app(executor=executor, registry=registry, settings=settings)
    logger.info(
        "mailjail listening on %s:%s (accounts=%s, primary=%s)",
        settings.server_host,
        settings.server_port,
        sorted(settings.accounts),
        settings.primary_account,
    )
    try:
        serve(app, host=settings.server_host, port=settings.server_port, threads=4)
    finally:
        registry.close()


if __name__ == "__main__":
    main()
