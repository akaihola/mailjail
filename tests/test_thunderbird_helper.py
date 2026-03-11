"""Tests for the Thunderbird helper script contract and NSS decryption."""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import importlib.util
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ---------------------------------------------------------------------------
# Load the helper script as a module (hyphen in filename prevents normal import)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "mailjail-thunderbird-password.py"
)
_spec = importlib.util.spec_from_file_location(
    "mailjail_thunderbird_password", _SCRIPT_PATH,
)
assert _spec is not None and _spec.loader is not None
helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helper)

SCRIPT = _SCRIPT_PATH


# ---------------------------------------------------------------------------
# DER encoding helpers (for building synthetic test fixtures)
# ---------------------------------------------------------------------------


def _der_length(length: int) -> bytes:
    if length < 128:
        return bytes([length])
    encoded = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(encoded)]) + encoded


def _der_tag(tag: int, body: bytes) -> bytes:
    return bytes([tag]) + _der_length(len(body)) + body


def _der_sequence(*items: bytes) -> bytes:
    return _der_tag(0x30, b"".join(items))


def _der_octet_string(data: bytes) -> bytes:
    return _der_tag(0x04, data)


def _der_oid(oid_str: str) -> bytes:
    parts = [int(p) for p in oid_str.split(".")]
    encoded = bytes([parts[0] * 40 + parts[1]])
    for p in parts[2:]:
        if p < 128:
            encoded += bytes([p])
        else:
            chunks: list[int] = []
            v = p
            while v > 0:
                chunks.append(v & 0x7F)
                v >>= 7
            chunks.reverse()
            for i, c in enumerate(chunks):
                encoded += bytes([c | 0x80] if i < len(chunks) - 1 else [c])
    return _der_tag(0x06, encoded)


def _der_integer(value: int) -> bytes:
    length = max(1, (value.bit_length() + 8) // 8)
    return _der_tag(0x02, value.to_bytes(length, "big"))


# ---------------------------------------------------------------------------
# Encryption helpers (reverse of the decryption in the helper script)
# ---------------------------------------------------------------------------


def _pad_pkcs7(data: bytes, block_size: int) -> bytes:
    padder = padding.PKCS7(block_size * 8).padder()
    return padder.update(data) + padder.finalize()


def _encrypt_3des_cbc(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    padded = _pad_pkcs7(plaintext, 8)
    enc = Cipher(TripleDES(key), modes.CBC(iv)).encryptor()
    return enc.update(padded) + enc.finalize()


def _nss_legacy_key_iv(
    global_salt: bytes, master_password: str, entry_salt: bytes,
) -> tuple[bytes, bytes]:
    """Derive the 3DES key and IV using NSS legacy SHA1-HMAC chain."""
    hp = hashlib.sha1(global_salt + master_password.encode("utf-8")).digest()
    pes = entry_salt + b"\x00" * (20 - len(entry_salt))
    chp = hashlib.sha1(hp + entry_salt).digest()
    k1 = hmac_mod.new(chp, pes + entry_salt, hashlib.sha1).digest()
    tk = hmac_mod.new(chp, pes, hashlib.sha1).digest()
    k2 = hmac_mod.new(chp, tk + entry_salt, hashlib.sha1).digest()
    k = k1 + k2
    return k[:24], k[-8:]


def _nss_legacy_encrypt(
    global_salt: bytes, master_password: str, entry_salt: bytes, plaintext: bytes,
) -> bytes:
    """Encrypt using the legacy NSS PBE scheme and return a DER-encoded blob."""
    key, iv = _nss_legacy_key_iv(global_salt, master_password, entry_salt)
    ciphertext = _encrypt_3des_cbc(key, iv, plaintext)
    return _der_sequence(
        _der_sequence(
            _der_oid("1.2.840.113549.1.12.5.1.3"),
            _der_sequence(
                _der_octet_string(entry_salt),
                _der_integer(1),
            ),
        ),
        _der_octet_string(ciphertext),
    )


def _build_login_blob_b64(
    key_id: bytes, iv: bytes, profile_key: bytes, plaintext: bytes,
) -> str:
    """Build a base64-encoded DER login blob (3DES)."""
    ciphertext = _encrypt_3des_cbc(profile_key[:24], iv, plaintext)
    blob = _der_sequence(
        _der_octet_string(key_id),
        _der_sequence(
            _der_oid("1.2.840.113549.3.7"),  # des-ede3-cbc
            _der_octet_string(iv),
        ),
        _der_octet_string(ciphertext),
    )
    return base64.b64encode(blob).decode("ascii")


# ---------------------------------------------------------------------------
# Synthetic Thunderbird profile fixture
# ---------------------------------------------------------------------------

GLOBAL_SALT = b"\x01" * 20
ENTRY_SALT_CHECK = b"\x02" * 20
ENTRY_SALT_KEY = b"\x03" * 20
PROFILE_KEY = b"\xaa" * 24  # 24-byte 3DES key
KEY_ID = b"\xf8" + b"\x00" * 14 + b"\x01"
LOGIN_IV = b"\x55" * 8
LOGIN_PASSWORD = "my-secret-imap-password"
MASTER_PASSWORD = ""


@pytest.fixture()
def synthetic_profile(tmp_path: Path) -> Path:
    """Create a synthetic Thunderbird profile with known encrypted values."""
    profile = tmp_path / "profile"
    profile.mkdir()

    # Encrypt "password-check" for the metadata table
    item2 = _nss_legacy_encrypt(
        GLOBAL_SALT, MASTER_PASSWORD, ENTRY_SALT_CHECK, b"password-check",
    )

    # Encrypt the profile key for the nssPrivate table
    a11 = _nss_legacy_encrypt(
        GLOBAL_SALT, MASTER_PASSWORD, ENTRY_SALT_KEY, PROFILE_KEY,
    )

    # Build login blobs
    encrypted_password = _build_login_blob_b64(
        KEY_ID, LOGIN_IV, PROFILE_KEY, LOGIN_PASSWORD.encode("utf-8"),
    )
    encrypted_username = _build_login_blob_b64(
        KEY_ID, LOGIN_IV, PROFILE_KEY, b"user@example.com",
    )

    # Create key4.db
    key4_db = profile / "key4.db"
    with sqlite3.connect(str(key4_db)) as conn:
        conn.execute("CREATE TABLE metadata (id TEXT, item1 BLOB, item2 BLOB)")
        conn.execute(
            "INSERT INTO metadata VALUES (?, ?, ?)",
            ("password", GLOBAL_SALT, item2),
        )
        conn.execute("CREATE TABLE nssPrivate (a11 BLOB, a102 BLOB)")
        conn.execute("INSERT INTO nssPrivate VALUES (?, ?)", (a11, KEY_ID))

    # Create logins.json
    logins_json = profile / "logins.json"
    logins_json.write_text(json.dumps({
        "logins": [{
            "hostname": "imap://mail.example.com",
            "encryptedUsername": encrypted_username,
            "encryptedPassword": encrypted_password,
        }],
    }))

    return profile


# ---------------------------------------------------------------------------
# End-to-end tests using synthetic profile
# ---------------------------------------------------------------------------


class TestFullDecryptionFlow:
    def test_unwrap_profile_key(self, synthetic_profile: Path) -> None:
        key4_db = synthetic_profile / "key4.db"
        profile_key = helper._unwrap_profile_key(key4_db)
        assert profile_key == PROFILE_KEY

    def test_decrypt_login_password(self, synthetic_profile: Path) -> None:
        key4_db = synthetic_profile / "key4.db"
        logins_json = synthetic_profile / "logins.json"
        profile_key = helper._unwrap_profile_key(key4_db)
        login = helper.load_matching_login(logins_json, "imap://mail.example.com")
        decrypted = helper._decrypt_login_blob(login["encryptedPassword"], profile_key)
        assert decrypted == LOGIN_PASSWORD

    def test_decrypt_login_username(self, synthetic_profile: Path) -> None:
        key4_db = synthetic_profile / "key4.db"
        logins_json = synthetic_profile / "logins.json"
        profile_key = helper._unwrap_profile_key(key4_db)
        login = helper.load_matching_login(logins_json, "imap://mail.example.com")
        decrypted = helper._decrypt_login_blob(login["encryptedUsername"], profile_key)
        assert decrypted == "user@example.com"

    def test_decrypt_with_local_tooling(self, synthetic_profile: Path) -> None:
        logins_json = synthetic_profile / "logins.json"
        login = helper.load_matching_login(logins_json, "imap://mail.example.com")
        result = helper.decrypt_with_local_tooling(
            profile=synthetic_profile,
            logins_json=logins_json,
            key4_db=synthetic_profile / "key4.db",
            origin="imap://mail.example.com",
            hostname=None,
            encrypted_username=login.get("encryptedUsername"),
            encrypted_password=login.get("encryptedPassword"),
        )
        assert result == LOGIN_PASSWORD


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_inferred_paths(self, synthetic_profile: Path) -> None:
        """--logins-json and --key4-db should be inferred from --profile."""
        result = subprocess.run(
            [
                "python3", str(SCRIPT),
                "--profile", str(synthetic_profile),
                "--origin", "imap://mail.example.com",
            ],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0
        assert result.stdout == LOGIN_PASSWORD

    def test_explicit_paths_override(self, synthetic_profile: Path) -> None:
        result = subprocess.run(
            [
                "python3", str(SCRIPT),
                "--profile", str(synthetic_profile),
                "--logins-json", str(synthetic_profile / "logins.json"),
                "--key4-db", str(synthetic_profile / "key4.db"),
                "--origin", "imap://mail.example.com",
            ],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0
        assert result.stdout == LOGIN_PASSWORD

    def test_invalid_key_db_fails(self, tmp_path: Path) -> None:
        profile = tmp_path / "profile"
        profile.mkdir()
        (profile / "logins.json").write_text(json.dumps({
            "logins": [{
                "hostname": "imap://mail.example.com",
                "encryptedUsername": "x", "encryptedPassword": "y",
            }],
        }))
        (profile / "key4.db").write_text("not-a-sqlite-db")
        result = subprocess.run(
            [
                "python3", str(SCRIPT),
                "--profile", str(profile),
                "--origin", "imap://mail.example.com",
            ],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 1
        assert result.stderr.strip()

    def test_missing_origin_fails(self, tmp_path: Path) -> None:
        profile = tmp_path / "profile"
        profile.mkdir()
        (profile / "logins.json").write_text(json.dumps({"logins": []}))
        (profile / "key4.db").write_text("placeholder")
        result = subprocess.run(
            [
                "python3", str(SCRIPT),
                "--profile", str(profile),
                "--origin", "imap://mail.example.com",
            ],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 1
        assert "no thunderbird login found" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Unit-level rejection tests
# ---------------------------------------------------------------------------


class TestRejections:
    def test_invalid_base64_blob(self) -> None:
        with pytest.raises(Exception):
            helper._decrypt_login_blob("not-base64!!!", b"\x00" * 24)

    def test_non_sequence_blob(self) -> None:
        payload = base64.b64encode(b"\x04\x03abc").decode("ascii")
        with pytest.raises(ValueError, match="primitive"):
            helper._decrypt_login_blob(payload, b"\x00" * 24)

    def test_missing_encrypted_password(self) -> None:
        with pytest.raises(ValueError, match="missing encrypted password"):
            helper.decrypt_with_local_tooling(
                profile=Path("/tmp"),
                logins_json=Path("/tmp"),
                key4_db=Path("/tmp"),
                origin="imap://x",
                hostname=None,
                encrypted_username=None,
                encrypted_password=None,
            )
