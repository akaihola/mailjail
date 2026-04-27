"""Tests for mailjail.thunderbird (in-process NSS decryption)."""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import sqlite3
from pathlib import Path

import pytest
from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from mailjail import thunderbird


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


def _encrypt_aes_cbc(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    padded = _pad_pkcs7(plaintext, 16)
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
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


def _build_aes_login_blob_b64(
    key_id: bytes, iv: bytes, aes_key: bytes, plaintext: bytes,
) -> str:
    """Build a base64-encoded DER login blob (AES-256-CBC)."""
    ciphertext = _encrypt_aes_cbc(aes_key[:32], iv, plaintext)
    blob = _der_sequence(
        _der_octet_string(key_id),
        _der_sequence(
            _der_oid("2.16.840.1.101.3.4.1.42"),  # aes256-CBC
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
ENTRY_SALT_KEY_DES3 = b"\x03" * 20
ENTRY_SALT_KEY_AES = b"\x04" * 20
PROFILE_KEY_DES3 = b"\xaa" * 24  # 24-byte 3DES key
PROFILE_KEY_AES = b"\xbb" * 32  # 32-byte AES-256 key
KEY_ID = b"\xf8" + b"\x00" * 14 + b"\x01"
LOGIN_IV_DES3 = b"\x55" * 8
LOGIN_IV_AES = b"\x66" * 16
LOGIN_PASSWORD = "my-secret-imap-password"
AES_LOGIN_PASSWORD = "another-secret-aes-password"
MASTER_PASSWORD = ""

CKK_DES3 = b"\x00\x00\x00\x15"
CKK_AES = b"\x00\x00\x00\x1f"


def synthetic_profile_factory(tmp_path: Path) -> Path:
    """Build a synthetic Thunderbird profile (used by both test files)."""
    profile = tmp_path / "profile"
    profile.mkdir()

    # Encrypt "password-check" for the metadata table
    item2 = _nss_legacy_encrypt(
        GLOBAL_SALT, MASTER_PASSWORD, ENTRY_SALT_CHECK, b"password-check",
    )

    # Encrypt both profile keys for the nssPrivate table
    a11_des3 = _nss_legacy_encrypt(
        GLOBAL_SALT, MASTER_PASSWORD, ENTRY_SALT_KEY_DES3, PROFILE_KEY_DES3,
    )
    a11_aes = _nss_legacy_encrypt(
        GLOBAL_SALT, MASTER_PASSWORD, ENTRY_SALT_KEY_AES, PROFILE_KEY_AES,
    )

    # Build login blobs (3DES path)
    encrypted_password = _build_login_blob_b64(
        KEY_ID, LOGIN_IV_DES3, PROFILE_KEY_DES3, LOGIN_PASSWORD.encode("utf-8"),
    )
    encrypted_username = _build_login_blob_b64(
        KEY_ID, LOGIN_IV_DES3, PROFILE_KEY_DES3, b"user@example.com",
    )
    # AES-256 login (modern Thunderbird path)
    encrypted_aes_password = _build_aes_login_blob_b64(
        KEY_ID, LOGIN_IV_AES, PROFILE_KEY_AES, AES_LOGIN_PASSWORD.encode("utf-8"),
    )

    # Create key4.db
    key4_db = profile / "key4.db"
    with sqlite3.connect(str(key4_db)) as conn:
        conn.execute("CREATE TABLE metadata (id TEXT, item1 BLOB, item2 BLOB)")
        conn.execute(
            "INSERT INTO metadata VALUES (?, ?, ?)",
            ("password", GLOBAL_SALT, item2),
        )
        conn.execute("CREATE TABLE nssPrivate (a11 BLOB, a100 BLOB, a102 BLOB)")
        conn.execute(
            "INSERT INTO nssPrivate VALUES (?, ?, ?)", (a11_des3, CKK_DES3, KEY_ID),
        )
        conn.execute(
            "INSERT INTO nssPrivate VALUES (?, ?, ?)", (a11_aes, CKK_AES, KEY_ID),
        )

    # Create logins.json
    logins_json = profile / "logins.json"
    logins_json.write_text(json.dumps({
        "logins": [
            {
                "hostname": "imap://mail.example.com",
                "encryptedUsername": encrypted_username,
                "encryptedPassword": encrypted_password,
            },
            {
                "hostname": "imap://aes.example.com",
                "encryptedUsername": encrypted_username,
                "encryptedPassword": encrypted_aes_password,
            },
        ],
    }))

    return profile


@pytest.fixture()
def synthetic_profile(tmp_path: Path) -> Path:
    """Create a synthetic Thunderbird profile with known encrypted values."""
    return synthetic_profile_factory(tmp_path)


def _load_matching_login(logins_json: Path, origin: str) -> dict[str, object]:
    """Test-only lookup of a Thunderbird login entry by exact origin match.

    Production uses the hint-based filter in `config.read_thunderbird_login`;
    this naive equality lookup is just scaffolding for the synthetic fixture.
    """
    with open(logins_json, encoding="utf-8") as f:
        payload = json.load(f)
    for entry in payload.get("logins", []):
        if entry.get("hostname") == origin:
            return entry
    msg = f"No Thunderbird login found for origin: {origin}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# End-to-end tests using synthetic profile
# ---------------------------------------------------------------------------


class TestFullDecryptionFlow:
    def test_unwrap_profile_keys(self, synthetic_profile: Path) -> None:
        key4_db = synthetic_profile / "key4.db"
        profile_keys = thunderbird._unwrap_profile_keys(key4_db)
        assert profile_keys == {
            0x15: PROFILE_KEY_DES3,
            0x1F: PROFILE_KEY_AES,
        }

    def test_decrypt_login_password(self, synthetic_profile: Path) -> None:
        key4_db = synthetic_profile / "key4.db"
        logins_json = synthetic_profile / "logins.json"
        profile_keys = thunderbird._unwrap_profile_keys(key4_db)
        login = _load_matching_login(logins_json, "imap://mail.example.com")
        encrypted = login["encryptedPassword"]
        assert isinstance(encrypted, str)
        decrypted = thunderbird._decrypt_login_blob(encrypted, profile_keys)
        assert decrypted == LOGIN_PASSWORD

    def test_decrypt_login_username(self, synthetic_profile: Path) -> None:
        key4_db = synthetic_profile / "key4.db"
        logins_json = synthetic_profile / "logins.json"
        profile_keys = thunderbird._unwrap_profile_keys(key4_db)
        login = _load_matching_login(logins_json, "imap://mail.example.com")
        encrypted = login["encryptedUsername"]
        assert isinstance(encrypted, str)
        decrypted = thunderbird._decrypt_login_blob(encrypted, profile_keys)
        assert decrypted == "user@example.com"

    def test_decrypt_login_end_to_end(self, synthetic_profile: Path) -> None:
        logins_json = synthetic_profile / "logins.json"
        login = _load_matching_login(logins_json, "imap://mail.example.com")
        encrypted = login.get("encryptedPassword")
        assert isinstance(encrypted, str)
        result = thunderbird.decrypt_login(
            key4_db=synthetic_profile / "key4.db",
            encrypted_password=encrypted,
        )
        assert result == LOGIN_PASSWORD

    def test_decrypt_aes_login_end_to_end(self, synthetic_profile: Path) -> None:
        """Regression: profile has both DES3 and AES keys; AES login picks AES.

        Before the multi-key fix, the code took the first nssPrivate row
        unconditionally (the 3DES key), which produced "Invalid padding bytes"
        when the login blob was AES-256 — exactly the failure mode seen on
        modern Thunderbird profiles that carry both key types.
        """
        logins_json = synthetic_profile / "logins.json"
        login = _load_matching_login(logins_json, "imap://aes.example.com")
        encrypted = login.get("encryptedPassword")
        assert isinstance(encrypted, str)
        result = thunderbird.decrypt_login(
            key4_db=synthetic_profile / "key4.db",
            encrypted_password=encrypted,
        )
        assert result == AES_LOGIN_PASSWORD


# ---------------------------------------------------------------------------
# Unit-level rejection tests
# ---------------------------------------------------------------------------


class TestRejections:
    def test_invalid_base64_blob(self) -> None:
        with pytest.raises(Exception):
            thunderbird._decrypt_login_blob("not-base64!!!", {0x15: b"\x00" * 24})

    def test_non_sequence_blob(self) -> None:
        payload = base64.b64encode(b"\x04\x03abc").decode("ascii")
        with pytest.raises(ValueError, match="primitive"):
            thunderbird._decrypt_login_blob(payload, {0x15: b"\x00" * 24})

    def test_missing_encrypted_password(self) -> None:
        with pytest.raises(ValueError, match="missing encrypted password"):
            thunderbird.decrypt_login(
                key4_db=Path("/tmp"),
                encrypted_password=None,
            )
