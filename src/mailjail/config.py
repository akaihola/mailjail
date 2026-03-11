"""Settings and configuration loading for mailjail."""

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any, Literal

from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "mailjail" / "config.toml"
DEFAULT_PASSWORD_PATH = Path.home() / ".config" / "mailjail" / "password"
DEFAULT_HIMALAYA_CONFIG_PATH = Path.home() / ".config" / "himalaya" / "config.toml"
DEFAULT_THUNDERBIRD_DIR = Path.home() / ".thunderbird"
DEFAULT_THUNDERBIRD_HELPER_CMD = (
    "python3 ~/.local/bin/mailjail-thunderbird-password "
    "--profile ${profile} --origin ${origin}"
)

CredentialProvider = Literal[
    "mailjail",
    "env",
    "password-file",
    "himalaya",
    "thunderbird",
    "auto",
]


class Settings(BaseModel):
    server_host: str = "127.0.0.1"
    server_port: int = 8895
    imap_host: str = "mail.example.com"
    imap_port: int = 993
    imap_ssl: bool = True
    imap_username: str
    imap_password: str
    pool_size: int = 3
    drafts_folder: str = "Drafts"
    credential_provider: CredentialProvider = "mailjail"
    himalaya_config_path: str = str(DEFAULT_HIMALAYA_CONFIG_PATH)
    himalaya_account: str = ""
    thunderbird_dir: str = str(DEFAULT_THUNDERBIRD_DIR)
    thunderbird_profile: str | None = None
    thunderbird_helper_cmd: str = DEFAULT_THUNDERBIRD_HELPER_CMD
    thunderbird_hostname_hint: str | None = None
    thunderbird_username_hint: str | None = None


@dataclass(slots=True)
class HimalayaCredentials:
    host: str | None
    login: str | None
    password: str


@dataclass(slots=True)
class ThunderbirdLogin:
    profile: Path
    logins_json: Path
    key4_db: Path
    hostname: str
    encrypted_username: str | None
    encrypted_password: str


class CredentialError(RuntimeError):
    """Raised when credentials cannot be resolved from a configured provider."""


def load_settings(config_path: Path = DEFAULT_CONFIG_PATH) -> Settings:
    """Read TOML config and resolve credentials.

    Merge order for non-secret settings:
    defaults → TOML file (if exists) → MAILJAIL_* env vars.

    Credential providers:
    - ``mailjail`` / ``auto``: explicit TOML password, env var, password file
    - ``himalaya`` / ``auto``: parse Himalaya config (supports auth.raw and auth.cmd)
    - ``thunderbird`` / ``auto``: read Thunderbird profile metadata and invoke a
      configured helper command that returns the decrypted password on stdout
    """
    data: dict[str, Any] = {}

    if config_path.exists():
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
        _merge_toml_into_data(raw, data)

    _merge_env_into_data(data)

    provider = data.get("credential_provider", "mailjail")
    if provider in {"mailjail", "auto", "env", "password-file"}:
        _apply_mailjail_credentials(data)
    if provider in {"himalaya", "auto"} and not data.get("imap_password"):
        _apply_himalaya_credentials(data)
    if provider in {"thunderbird", "auto"} and not data.get("imap_password"):
        _apply_thunderbird_credentials(data)

    return Settings.model_validate(data)


def _merge_toml_into_data(raw: dict[str, Any], data: dict[str, Any]) -> None:
    server = raw.get("server", {})
    imap = raw.get("imap", {}).copy()
    imap_pool = imap.pop("pool", {})
    imap_auth = imap.pop("auth", {})

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

    if "provider" in imap_auth:
        data["credential_provider"] = imap_auth["provider"]
    if "himalaya_config_path" in imap_auth:
        data["himalaya_config_path"] = imap_auth["himalaya_config_path"]
    if "himalaya_account" in imap_auth:
        data["himalaya_account"] = imap_auth["himalaya_account"]
    if "thunderbird_dir" in imap_auth:
        data["thunderbird_dir"] = imap_auth["thunderbird_dir"]
    if "thunderbird_profile" in imap_auth:
        data["thunderbird_profile"] = imap_auth["thunderbird_profile"]
    if "thunderbird_helper_cmd" in imap_auth:
        data["thunderbird_helper_cmd"] = imap_auth["thunderbird_helper_cmd"]
    if "thunderbird_hostname_hint" in imap_auth:
        data["thunderbird_hostname_hint"] = imap_auth["thunderbird_hostname_hint"]
    if "thunderbird_username_hint" in imap_auth:
        data["thunderbird_username_hint"] = imap_auth["thunderbird_username_hint"]


def _merge_env_into_data(data: dict[str, Any]) -> None:
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
        "MAILJAIL_CREDENTIAL_PROVIDER": "credential_provider",
        "MAILJAIL_HIMALAYA_CONFIG_PATH": "himalaya_config_path",
        "MAILJAIL_HIMALAYA_ACCOUNT": "himalaya_account",
        "MAILJAIL_THUNDERBIRD_DIR": "thunderbird_dir",
        "MAILJAIL_THUNDERBIRD_PROFILE": "thunderbird_profile",
        "MAILJAIL_THUNDERBIRD_HELPER_CMD": "thunderbird_helper_cmd",
        "MAILJAIL_THUNDERBIRD_HOSTNAME_HINT": "thunderbird_hostname_hint",
        "MAILJAIL_THUNDERBIRD_USERNAME_HINT": "thunderbird_username_hint",
    }
    for env_key, field in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            data[field] = val


def _apply_mailjail_credentials(data: dict[str, Any]) -> None:
    password_path = DEFAULT_PASSWORD_PATH
    if password_path.exists():
        password = password_path.read_text().strip()
        if password:
            data["imap_password"] = password


def _apply_himalaya_credentials(data: dict[str, Any]) -> None:
    config_path = Path(data.get("himalaya_config_path", str(DEFAULT_HIMALAYA_CONFIG_PATH)))
    account_name = data.get("himalaya_account", "")
    creds = read_himalaya_credentials(config_path, account_name)
    if not data.get("imap_host") and creds.host:
        data["imap_host"] = creds.host
    if not data.get("imap_username") and creds.login:
        data["imap_username"] = creds.login
    data["imap_password"] = creds.password


def _apply_thunderbird_credentials(data: dict[str, Any]) -> None:
    thunderbird_dir = Path(data.get("thunderbird_dir", str(DEFAULT_THUNDERBIRD_DIR)))
    profile_name = data.get("thunderbird_profile")
    username_hint = data.get("thunderbird_username_hint") or data.get("imap_username")
    hostname_hint = data.get("thunderbird_hostname_hint") or data.get("imap_host")
    helper_cmd = data.get("thunderbird_helper_cmd") or DEFAULT_THUNDERBIRD_HELPER_CMD

    login = read_thunderbird_login(
        thunderbird_dir=thunderbird_dir,
        profile_name=profile_name,
        username_hint=username_hint,
        hostname_hint=hostname_hint,
    )
    password = decrypt_thunderbird_login(login, helper_cmd)

    if not data.get("imap_host"):
        data["imap_host"] = _origin_host(login.hostname)
    data["imap_password"] = password


def read_himalaya_credentials(config_path: Path, account_name: str) -> HimalayaCredentials:
    if not config_path.exists():
        raise CredentialError(f"Himalaya config not found: {config_path}")
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    accounts = raw.get("accounts", {})
    if account_name not in accounts:
        raise CredentialError(
            f"Himalaya account '{account_name}' not found in {config_path}"
        )

    account = accounts[account_name]
    backend = account.get("backend", {})
    auth = backend.get("auth", {})

    password: str | None = None
    if auth.get("raw"):
        password = str(auth["raw"])
    elif auth.get("cmd"):
        password = subprocess.check_output(
            str(auth["cmd"]), shell=True, text=True
        ).strip()

    if not password:
        raise CredentialError(
            f"Himalaya account '{account_name}' has no usable auth.raw or auth.cmd"
        )

    return HimalayaCredentials(
        host=backend.get("host"),
        login=backend.get("login") or account.get("email"),
        password=password,
    )


def _read_profiles_ini(thunderbird_dir: Path) -> ConfigParser:
    profiles_ini = thunderbird_dir / "profiles.ini"
    if not profiles_ini.exists():
        raise CredentialError(f"Thunderbird profiles.ini not found: {profiles_ini}")
    parser = ConfigParser()
    parser.read(profiles_ini)
    return parser


def _find_default_thunderbird_profile(
    thunderbird_dir: Path, profile_name: str | None
) -> Path:
    if profile_name:
        candidate = thunderbird_dir / profile_name
        if candidate.exists():
            return candidate
        raise CredentialError(f"Thunderbird profile not found: {candidate}")

    parser = _read_profiles_ini(thunderbird_dir)
    for section in parser.sections():
        if not section.startswith("Profile"):
            continue
        if parser.get(section, "Default", fallback="0") != "1":
            continue
        path = parser.get(section, "Path", fallback="")
        is_relative = parser.get(section, "IsRelative", fallback="1") == "1"
        if not path:
            continue
        profile_path = thunderbird_dir / path if is_relative else Path(path)
        if profile_path.exists():
            return profile_path

    raise CredentialError("Could not determine default Thunderbird profile")


def read_thunderbird_login(
    *,
    thunderbird_dir: Path,
    profile_name: str | None,
    username_hint: str | None,
    hostname_hint: str | None,
) -> ThunderbirdLogin:
    profile = _find_default_thunderbird_profile(thunderbird_dir, profile_name)
    logins_path = profile / "logins.json"
    key_db_path = profile / "key4.db"
    if not logins_path.exists():
        raise CredentialError(f"Thunderbird logins.json not found: {logins_path}")
    if not key_db_path.exists():
        raise CredentialError(f"Thunderbird key4.db not found: {key_db_path}")

    with open(logins_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    candidates = payload.get("logins", [])
    filtered: list[dict[str, Any]] = []
    for entry in candidates:
        hostname = entry.get("hostname", "")
        if hostname_hint and hostname_hint not in hostname and hostname_hint != _origin_host(hostname):
            continue
        if username_hint and entry.get("encryptedUsername") is None:
            continue
        filtered.append(entry)

    if not filtered:
        raise CredentialError(
            f"No Thunderbird login found for host hint '{hostname_hint or '*'}' in {logins_path}"
        )

    entry = filtered[0]
    return ThunderbirdLogin(
        profile=profile,
        logins_json=logins_path,
        key4_db=key_db_path,
        hostname=entry.get("hostname", ""),
        encrypted_username=entry.get("encryptedUsername"),
        encrypted_password=entry["encryptedPassword"],
    )


def decrypt_thunderbird_login(login: ThunderbirdLogin, helper_cmd: str) -> str:
    mapping = {
        "profile": str(login.profile),
        "logins_json": str(login.logins_json),
        "key4_db": str(login.key4_db),
        "origin": login.hostname,
        "hostname": _origin_host(login.hostname),
        "encrypted_username": login.encrypted_username or "",
        "encrypted_password": login.encrypted_password,
    }
    cmd = Template(helper_cmd).safe_substitute(mapping)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise CredentialError(f"Failed to invoke Thunderbird helper: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise CredentialError(
            "Thunderbird helper failed with exit code "
            f"{result.returncode}: {stderr or 'no stderr output'}"
        )

    password = result.stdout.strip()
    if not password:
        raise CredentialError("Thunderbird helper returned an empty password")
    return password


def thunderbird_helper_template() -> str:
    """Return the default helper command template used for Thunderbird support."""
    return DEFAULT_THUNDERBIRD_HELPER_CMD


def _origin_host(origin: str) -> str:
    value = origin.strip()
    for prefix in ("imap://", "mailbox://", "https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value.split("/", 1)[0].split(":", 1)[0]
