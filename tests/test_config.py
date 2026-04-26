"""Tests for multi-account config loading and credential providers."""

from __future__ import annotations

from pathlib import Path

import pytest

from mailjail.config import (
    ConfigError,
    load_settings,
    read_himalaya_credentials,
    read_thunderbird_login,
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


# --- Multi-account TOML parsing ---


MULTI_ACCOUNT_TOML = '''
primary_account = "work"

[server]
host = "0.0.0.0"
port = 9000

[accounts.work]
host = "mail.work.example"
username = "user@work.example"
password = "work-secret"

[accounts.work.pool]
size = 5

[accounts.personal]
host = "mail.personal.example"
username = "me@personal.example"
password = "personal-secret"
drafts_folder = "INBOX/Drafts"
'''


def test_load_settings_parses_multiple_accounts(tmp_path: Path) -> None:
    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(MULTI_ACCOUNT_TOML)

    settings = load_settings(config_path)

    assert settings.server_host == "0.0.0.0"
    assert settings.server_port == 9000
    assert settings.primary_account == "work"
    assert set(settings.accounts) == {"work", "personal"}

    work = settings.accounts["work"]
    assert work.imap_host == "mail.work.example"
    assert work.imap_username == "user@work.example"
    assert work.imap_password == "work-secret"
    assert work.pool_size == 5

    personal = settings.accounts["personal"]
    assert personal.imap_username == "me@personal.example"
    assert personal.drafts_folder == "INBOX/Drafts"


def test_load_settings_missing_primary_account_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        '''
[accounts.work]
username = "u@example.com"
password = "p"
'''
    )
    with pytest.raises(ConfigError, match="primary_account"):
        load_settings(config_path)


def test_load_settings_primary_account_unknown_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        '''
primary_account = "ghost"

[accounts.work]
username = "u@example.com"
password = "p"
'''
    )
    with pytest.raises(Exception, match="primary_account"):
        load_settings(config_path)


def test_load_settings_legacy_imap_section_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        '''
[imap]
host = "old"
username = "u"
password = "p"
'''
    )
    with pytest.raises(ConfigError, match="legacy single-account"):
        load_settings(config_path)


def test_load_settings_server_env_overrides_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(MULTI_ACCOUNT_TOML)
    monkeypatch.setenv("MAILJAIL_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("MAILJAIL_SERVER_PORT", "1234")

    settings = load_settings(config_path)

    assert settings.server_host == "127.0.0.1"
    assert settings.server_port == 1234


def test_per_account_env_vars_are_not_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MAILJAIL_IMAP_* must not leak across accounts in multi-account mode."""
    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(MULTI_ACCOUNT_TOML)
    monkeypatch.setenv("MAILJAIL_IMAP_PASSWORD", "leaked")

    settings = load_settings(config_path)

    assert settings.accounts["work"].imap_password == "work-secret"
    assert settings.accounts["personal"].imap_password == "personal-secret"


# --- Credential providers (per account) ---


def test_account_can_use_himalaya_provider(tmp_path: Path) -> None:
    himalaya_path = tmp_path / "himalaya.toml"
    himalaya_path.write_text(HIMALAYA_CONFIG)

    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        f'''
primary_account = "work"

[accounts.work]
username = "user@example.com"

[accounts.work.auth]
provider = "himalaya"
himalaya_config_path = "{himalaya_path}"
himalaya_account = "testuser"
'''
    )

    settings = load_settings(config_path)
    work = settings.accounts["work"]

    assert work.credential_provider == "himalaya"
    assert work.imap_password == "secret-from-himalaya"
    assert work.imap_host == "mail.example.com"
    assert work.imap_username == "user@example.com"


def test_two_accounts_can_use_different_providers(tmp_path: Path) -> None:
    from tests.test_thunderbird import synthetic_profile_factory

    himalaya_path = tmp_path / "himalaya.toml"
    himalaya_path.write_text(HIMALAYA_CONFIG)

    thunderbird_dir = tmp_path / ".thunderbird"
    thunderbird_dir.mkdir()
    profile_dir = synthetic_profile_factory(thunderbird_dir)
    profile_dir.rename(thunderbird_dir / "abcd.default-release")
    (thunderbird_dir / "profiles.ini").write_text(PROFILES_INI)

    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        f'''
primary_account = "work"

[accounts.work]
username = "user@example.com"

[accounts.work.auth]
provider = "himalaya"
himalaya_config_path = "{himalaya_path}"
himalaya_account = "testuser"

[accounts.personal]
username = "user@example.com"

[accounts.personal.auth]
provider = "thunderbird"
thunderbird_dir = "{thunderbird_dir}"
'''
    )

    settings = load_settings(config_path)
    assert settings.accounts["work"].imap_password == "secret-from-himalaya"
    assert settings.accounts["personal"].imap_password == "my-secret-imap-password"


def test_unknown_thunderbird_helper_cmd_raises(tmp_path: Path) -> None:
    """Legacy `thunderbird_helper_cmd` must hard-fail (no silent ignore)."""
    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        '''
primary_account = "p"

[accounts.p]
username = "user@example.com"
password = "pw"

[accounts.p.auth]
provider = "mailjail"
thunderbird_helper_cmd = "/old/script"
'''
    )
    with pytest.raises(ConfigError, match="thunderbird_helper_cmd"):
        load_settings(config_path)


def test_thunderbird_provider_uses_in_process_decryption(tmp_path: Path) -> None:
    """load_settings() should decrypt Thunderbird credentials in-process,
    without invoking any external helper command."""
    from tests.test_thunderbird import synthetic_profile_factory  # see Task 4 step 2

    profile_dir = synthetic_profile_factory(tmp_path)
    thunderbird_dir = profile_dir.parent
    profile_dir.rename(thunderbird_dir / "abcd.default-release")
    (thunderbird_dir / "profiles.ini").write_text(PROFILES_INI)

    config_path = tmp_path / "mailjail.toml"
    config_path.write_text(
        f'''
primary_account = "personal"

[accounts.personal]
username = "user@example.com"

[accounts.personal.auth]
provider = "thunderbird"
thunderbird_dir = "{thunderbird_dir}"
'''
    )

    settings = load_settings(config_path)
    assert settings.accounts["personal"].imap_password == "my-secret-imap-password"


# --- Direct credential helper tests (unchanged) ---


def test_read_himalaya_credentials_raw(tmp_path: Path) -> None:
    config_path = tmp_path / "himalaya.toml"
    config_path.write_text(HIMALAYA_CONFIG)

    creds = read_himalaya_credentials(config_path, "testuser")

    assert creds.host == "mail.example.com"
    assert creds.login == "user@example.com"
    assert creds.password == "secret-from-himalaya"


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


