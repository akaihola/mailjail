"""Settings and configuration loading for mailjail."""

import os
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "mailjail" / "config.toml"
DEFAULT_PASSWORD_PATH = Path.home() / ".config" / "mailjail" / "password"


class Settings(BaseModel):
    server_host: str = "127.0.0.1"
    server_port: int = 8895
    imap_host: str = "mail.gandi.net"
    imap_port: int = 993
    imap_ssl: bool = True
    imap_username: str
    imap_password: str
    pool_size: int = 3
    drafts_folder: str = "Drafts"


def load_settings(config_path: Path = DEFAULT_CONFIG_PATH) -> Settings:
    """Read TOML config + password file; env vars override.

    Merge order: defaults → TOML file (if exists) → MAILJAIL_* env vars
    → password file content.
    """
    data: dict[str, Any] = {}

    # Load TOML file if present
    if config_path.exists():
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
        # Flatten nested TOML structure
        server = raw.get("server", {})
        imap = raw.get("imap", {})
        imap_pool = imap.pop("pool", {})

        if "host" in server:
            data["server_host"] = server["host"]
        if "port" in server:
            data["server_port"] = server["port"]
        if "host" in imap:
            data["imap_host"] = imap["host"]
        if "port" in imap:
            data["imap_port"] = imap["port"]
        if "ssl" in imap:
            data["imap_ssl"] = imap["ssl"]
        if "username" in imap:
            data["imap_username"] = imap["username"]
        if "password" in imap:
            data["imap_password"] = imap["password"]
        if "drafts_folder" in imap:
            data["drafts_folder"] = imap["drafts_folder"]
        if "size" in imap_pool:
            data["pool_size"] = imap_pool["size"]

    # Environment variable overrides (MAILJAIL_ prefix)
    env_map = {
        "MAILJAIL_SERVER_HOST": "server_host",
        "MAILJAIL_SERVER_PORT": "server_port",
        "MAILJAIL_IMAP_HOST": "imap_host",
        "MAILJAIL_IMAP_PORT": "imap_port",
        "MAILJAIL_IMAP_SSL": "imap_ssl",
        "MAILJAIL_IMAP_USERNAME": "imap_username",
        "MAILJAIL_IMAP_PASSWORD": "imap_password",
        "MAILJAIL_POOL_SIZE": "pool_size",
        "MAILJAIL_DRAFTS_FOLDER": "drafts_folder",
    }
    for env_key, field in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            data[field] = val

    # Password file takes precedence over env var and TOML
    password_path = DEFAULT_PASSWORD_PATH
    if password_path.exists():
        password = password_path.read_text().strip()
        if password:
            data["imap_password"] = password

    return Settings.model_validate(data)
