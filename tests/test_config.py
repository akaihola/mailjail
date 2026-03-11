"""Tests for mailjail credential providers."""

from __future__ import annotations

from pathlib import Path

import pytest

from mailjail.config import (
    CredentialError,
    decrypt_thunderbird_login,
    load_settings,
    read_himalaya_credentials,
    read_thunderbird_login,
    thunderbird_helper_template,
)


HIMALAYA_CONFIG = """
[accounts.testuser]
email = "user@example.com"

[accounts.testuser.backend]
host = "mail.example.com"
login = "user@example.com"

[accounts.testuser.backend.auth]
raw = "secret-from-himalaya"
"""

MAILJAIL_CONFIG_HIMALAYA = """
[imap]
username = "user@example.com"

[imap.auth]
provider = "himalaya"
himalaya_config_path = "{himalaya_path}"
himalaya_account = "testuser"
"""

MAILJAIL_CONFIG_THUNDERBIRD = """
[imap]
username = "user@example.com"

[imap.auth]
provider = "thunderbird"
thunderbird_dir = "{thunderbird_dir}"
thunderbird_helper_cmd = '''python3 -c "print('secret-from-thunderbird')"'''
"""

PROFILES_INI = """
[Profile0]
Name=default-release
IsRelative=1
Path=abcd.default-release
Default=1
"""

LOGINS_JSON = r'''
{
  "logins": [
    {
      "hostname": "imap://mail.example.com",
      "encryptedUsername": "encrypted-user",
      "encryptedPassword": "encrypted-pass"
    }
  ]
}
'''


def test_read_himalaya_credentials_raw(tmp_path: Path) -> None:
    config_path = tmp_path / "himalaya.toml"
    config_path.write_text(HIMALAYA_CONFIG)

    creds = read_himalaya_credentials(config_path, "testuser")

    assert creds.host == "mail.example.com"
    assert creds.login == "user@example.com"
    assert creds.password == "secret-from-himalaya"


def test_load_settings_uses_himalaya_provider(tmp_path: Path) -> None:
    himalaya_path = tmp_path / "himalaya.toml"
    himalaya_path.write_text(HIMALAYA_CONFIG)

    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        MAILJAIL_CONFIG_HIMALAYA.format(himalaya_path=himalaya_path)
    )

    settings = load_settings(config_path)

    assert settings.credential_provider == "himalaya"
    assert settings.imap_password == "secret-from-himalaya"
    assert settings.imap_host == "mail.example.com"
    assert settings.imap_username == "user@example.com"


def test_read_thunderbird_login(tmp_path: Path) -> None:
    thunderbird_dir = tmp_path / ".thunderbird"
    profile_dir = thunderbird_dir / "abcd.default-release"
    profile_dir.mkdir(parents=True)
    (thunderbird_dir / "profiles.ini").write_text(PROFILES_INI)
    (profile_dir / "logins.json").write_text(LOGINS_JSON)
    (profile_dir / "key4.db").write_text("sqlite-placeholder")

    login = read_thunderbird_login(
        thunderbird_dir=thunderbird_dir,
        profile_name=None,
        username_hint="user@example.com",
        hostname_hint="mail.example.com",
    )

    assert login.profile == profile_dir
    assert login.hostname == "imap://mail.example.com"
    assert login.encrypted_password == "encrypted-pass"


def test_decrypt_thunderbird_login_uses_helper(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    logins_json = profile_dir / "logins.json"
    key4_db = profile_dir / "key4.db"
    logins_json.write_text("{}")
    key4_db.write_text("placeholder")

    login = read_thunderbird_login_from_values(
        profile=profile_dir,
        logins_json=logins_json,
        key4_db=key4_db,
        hostname="imap://mail.example.com",
        encrypted_username="enc-user",
        encrypted_password="enc-pass",
    )

    password = decrypt_thunderbird_login(
        login,
        "python3 -c \"print('secret-from-helper')\"",
    )

    assert password == "secret-from-helper"


def test_load_settings_uses_thunderbird_provider(tmp_path: Path) -> None:
    thunderbird_dir = tmp_path / ".thunderbird"
    profile_dir = thunderbird_dir / "abcd.default-release"
    profile_dir.mkdir(parents=True)
    (thunderbird_dir / "profiles.ini").write_text(PROFILES_INI)
    (profile_dir / "logins.json").write_text(LOGINS_JSON)
    (profile_dir / "key4.db").write_text("sqlite-placeholder")

    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        MAILJAIL_CONFIG_THUNDERBIRD.format(thunderbird_dir=thunderbird_dir)
    )

    settings = load_settings(config_path)

    assert settings.credential_provider == "thunderbird"
    assert settings.imap_password == "secret-from-thunderbird"


def test_thunderbird_helper_failure_raises(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    logins_json = profile_dir / "logins.json"
    key4_db = profile_dir / "key4.db"
    logins_json.write_text("{}")
    key4_db.write_text("placeholder")

    login = read_thunderbird_login_from_values(
        profile=profile_dir,
        logins_json=logins_json,
        key4_db=key4_db,
        hostname="imap://mail.example.com",
        encrypted_username="enc-user",
        encrypted_password="enc-pass",
    )

    with pytest.raises(CredentialError, match="Thunderbird helper failed"):
        decrypt_thunderbird_login(login, "python3 -c \"import sys; sys.exit(2)\"")


def test_thunderbird_helper_template_mentions_expected_placeholders() -> None:
    template = thunderbird_helper_template()
    assert "${profile}" in template
    assert "${origin}" in template
    assert "${logins_json}" not in template
    assert "${key4_db}" not in template


def test_default_thunderbird_helper_cmd_uses_profile_and_origin_only() -> None:
    from mailjail.config import DEFAULT_THUNDERBIRD_HELPER_CMD

    assert DEFAULT_THUNDERBIRD_HELPER_CMD == (
        "python3 ~/.local/bin/mailjail-thunderbird-password "
        "--profile ${profile} --origin ${origin}"
    )


def test_decrypt_thunderbird_login_works_with_helper_ignoring_extra_placeholders(
    tmp_path: Path,
) -> None:
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    logins_json = profile_dir / "logins.json"
    key4_db = profile_dir / "key4.db"
    logins_json.write_text("{}")
    key4_db.write_text("placeholder")

    login = read_thunderbird_login_from_values(
        profile=profile_dir,
        logins_json=logins_json,
        key4_db=key4_db,
        hostname="imap://mail.example.com",
        encrypted_username="enc-user",
        encrypted_password="enc-pass",
    )

    password = decrypt_thunderbird_login(
        login,
        "python3 -c \"print('secret-from-helper')\" --unused ${logins_json} ${key4_db}",
    )

    assert password == "secret-from-helper"


def read_thunderbird_login_from_values(
    *,
    profile: Path,
    logins_json: Path,
    key4_db: Path,
    hostname: str,
    encrypted_username: str | None,
    encrypted_password: str,
):
    from mailjail.config import ThunderbirdLogin

    return ThunderbirdLogin(
        profile=profile,
        logins_json=logins_json,
        key4_db=key4_db,
        hostname=hostname,
        encrypted_username=encrypted_username,
        encrypted_password=encrypted_password,
    )
