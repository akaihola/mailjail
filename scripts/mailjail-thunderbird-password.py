#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "cryptography>=43.0",
# ]
# ///

"""Decrypt a Thunderbird IMAP password for mailjail.

This helper script is intentionally separate from the mailjail service. mailjail
locates the right Thunderbird profile and login entry, then invokes this helper
with profile metadata. The helper's contract is simple:

- Input: profile directory and login origin (logins.json/key4.db are inferred)
- Output: decrypted password on stdout, nothing else
- Exit code 0 on success, non-zero on failure

The decryption follows the NSS key-management scheme used by Thunderbird and
Firefox. Reference: https://github.com/lclevy/firepwd (pure-Python educational
implementation of the same flow).

Flow:
1. Read global-salt and encrypted check-value from key4.db metadata table
2. Verify the master password (empty by default) by decrypting the check-value
3. Unwrap the profile key from key4.db nssPrivate table
4. Decrypt the login blob from logins.json using the profile key
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac as hmac_mod
import json
import sqlite3
import sys
from pathlib import Path

from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# ---------------------------------------------------------------------------
# Minimal ASN.1 DER parser
# ---------------------------------------------------------------------------


class ASN1:
    """Minimal recursive ASN.1 DER parser."""

    __slots__ = ("tag", "value")

    def __init__(self, tag: int, value: bytes | list[ASN1]) -> None:
        self.tag = tag
        self.value = value

    @property
    def children(self) -> list[ASN1]:
        if not isinstance(self.value, list):
            msg = f"ASN1 tag 0x{self.tag:02x} is primitive, not constructed"
            raise ValueError(msg)
        return self.value

    @property
    def data(self) -> bytes:
        if not isinstance(self.value, bytes):
            msg = f"ASN1 tag 0x{self.tag:02x} is constructed, not primitive"
            raise ValueError(msg)
        return self.value

    @staticmethod
    def parse(data: bytes, offset: int = 0) -> tuple[ASN1, int]:
        tag = data[offset]
        offset += 1
        first = data[offset]
        offset += 1
        if first < 0x80:
            length = first
        else:
            width = first & 0x7F
            if width == 0:
                msg = "Indefinite ASN.1 lengths not supported"
                raise ValueError(msg)
            length = int.from_bytes(data[offset : offset + width], "big")
            offset += width
        end = offset + length
        if tag & 0x20:  # Constructed (SEQUENCE, SET, etc.)
            children: list[ASN1] = []
            pos = offset
            while pos < end:
                child, pos = ASN1.parse(data, pos)
                children.append(child)
            return ASN1(tag, children), end
        return ASN1(tag, data[offset:end]), end

    @staticmethod
    def parse_one(data: bytes) -> ASN1:
        node, _ = ASN1.parse(data)
        return node


def _decode_oid(der: bytes) -> str:
    if not der:
        msg = "Empty OID"
        raise ValueError(msg)
    first = der[0]
    parts = [str(first // 40), str(first % 40)]
    value = 0
    for byte in der[1:]:
        value = (value << 7) | (byte & 0x7F)
        if byte < 0x80:
            parts.append(str(value))
            value = 0
    return ".".join(parts)


# ---------------------------------------------------------------------------
# Symmetric decryption helpers
# ---------------------------------------------------------------------------


def _unpad(data: bytes, block_size: int) -> bytes:
    unpadder = padding.PKCS7(block_size * 8).unpadder()
    return unpadder.update(data) + unpadder.finalize()


def _decrypt_3des_cbc(key: bytes, iv: bytes, ct: bytes) -> bytes:
    dec = Cipher(TripleDES(key), modes.CBC(iv)).decryptor()
    return _unpad(dec.update(ct) + dec.finalize(), 8)


def _decrypt_aes_cbc(key: bytes, iv: bytes, ct: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return _unpad(dec.update(ct) + dec.finalize(), 16)


# ---------------------------------------------------------------------------
# NSS PBE decryption (key4.db blobs)
# ---------------------------------------------------------------------------

# Well-known OIDs
OID_PBE_SHA1_3DES = "1.2.840.113549.1.12.5.1.3"
OID_PBES2 = "1.2.840.113549.1.5.13"
OID_DES_EDE3_CBC = "1.2.840.113549.3.7"
OID_AES_256_CBC = "2.16.840.1.101.3.4.1.42"


def _nss_decrypt(global_salt: bytes, master_password: str, blob: bytes) -> bytes:
    """Decrypt an NSS PBE-encrypted blob (from key4.db metadata or nssPrivate)."""
    root = ASN1.parse_one(blob)
    algo_seq = root.children[0].children
    oid = _decode_oid(algo_seq[0].data)
    encrypted = root.children[1].data

    if oid == OID_PBE_SHA1_3DES:
        params = algo_seq[1].children
        entry_salt = params[0].data
        return _nss_legacy_decrypt(
            global_salt, master_password, entry_salt, encrypted,
        )

    if oid == OID_PBES2:
        pbes2_params = algo_seq[1].children
        kdf_params = pbes2_params[0].children[1].children
        entry_salt = kdf_params[0].data
        iterations = int.from_bytes(kdf_params[1].data, "big")
        key_length = 32
        if len(kdf_params) > 2 and kdf_params[2].tag == 0x02:
            key_length = int.from_bytes(kdf_params[2].data, "big")
        iv_bytes = pbes2_params[1].children[1].data
        # NSS quirk: the stored IV is 14 bytes; prepend the DER OCTET STRING
        # header (0x04 0x0e) to form the full 16-byte AES IV.
        # Reference: https://hg.mozilla.org/projects/nss/rev/fc636973ad06
        iv = b"\x04\x0e" + iv_bytes
        return _nss_modern_decrypt(
            global_salt, master_password, entry_salt, iterations, key_length,
            iv, encrypted,
        )

    msg = f"Unsupported NSS encryption OID: {oid}"
    raise ValueError(msg)


def _nss_legacy_decrypt(
    global_salt: bytes,
    master_password: str,
    entry_salt: bytes,
    encrypted: bytes,
) -> bytes:
    """NSS legacy PBE: SHA1-HMAC key derivation + 3DES-CBC.

    Reference: https://github.com/nicoleorbe/PKCS11/blob/master/key3.html
    """
    hp = hashlib.sha1(global_salt + master_password.encode("utf-8")).digest()
    pes = entry_salt + b"\x00" * (20 - len(entry_salt))
    chp = hashlib.sha1(hp + entry_salt).digest()
    k1 = hmac_mod.new(chp, pes + entry_salt, hashlib.sha1).digest()
    tk = hmac_mod.new(chp, pes, hashlib.sha1).digest()
    k2 = hmac_mod.new(chp, tk + entry_salt, hashlib.sha1).digest()
    k = k1 + k2  # 40 bytes
    return _decrypt_3des_cbc(k[:24], k[-8:], encrypted)


def _nss_modern_decrypt(
    global_salt: bytes,
    master_password: str,
    entry_salt: bytes,
    iterations: int,
    key_length: int,
    iv: bytes,
    encrypted: bytes,
) -> bytes:
    """NSS modern PBE: SHA1 + PBKDF2-HMAC-SHA256 + AES-256-CBC."""
    k = hashlib.sha1(global_salt + master_password.encode("utf-8")).digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=key_length,
        salt=entry_salt,
        iterations=iterations,
    )
    key = kdf.derive(k)
    return _decrypt_aes_cbc(key, iv, encrypted)


# ---------------------------------------------------------------------------
# Login blob decryption (logins.json entries)
# ---------------------------------------------------------------------------


def _decrypt_login_blob(encrypted_b64: str, profile_key: bytes) -> str:
    """Decrypt a base64-encoded login blob from logins.json.

    The blob structure (DER):
        SEQUENCE {
            OCTET STRING (key_id, 16 bytes — CKA_ID)
            SEQUENCE {
                OID (des-ede3-cbc or aes256-CBC)
                OCTET STRING (IV)
            }
            OCTET STRING (ciphertext)
        }
    """
    data = base64.b64decode(encrypted_b64)
    root = ASN1.parse_one(data)
    children = root.children
    # children[0] = key_id, children[1] = algo sequence, children[2] = ciphertext
    algo_seq = children[1].children
    oid = _decode_oid(algo_seq[0].data)
    iv = algo_seq[1].data
    ciphertext = children[2].data

    if oid == OID_DES_EDE3_CBC:
        plaintext = _decrypt_3des_cbc(profile_key[:24], iv, ciphertext)
    elif oid == OID_AES_256_CBC:
        plaintext = _decrypt_aes_cbc(profile_key[:32], iv, ciphertext)
    else:
        msg = f"Unsupported login encryption OID: {oid}"
        raise ValueError(msg)

    return plaintext.decode("utf-8")


# ---------------------------------------------------------------------------
# key4.db readers
# ---------------------------------------------------------------------------


def _read_key4_db_metadata(key4_db: Path) -> tuple[bytes, bytes]:
    with sqlite3.connect(str(key4_db)) as conn:
        row = conn.execute(
            "SELECT item1, item2 FROM metadata WHERE id = 'password'",
        ).fetchone()
    if row is None:
        msg = "key4.db missing metadata password entry"
        raise ValueError(msg)
    global_salt, item2 = row
    if not isinstance(global_salt, bytes) or not isinstance(item2, bytes):
        msg = "key4.db metadata types unexpected"
        raise ValueError(msg)
    return global_salt, item2


def _read_nss_private_key(key4_db: Path) -> bytes:
    with sqlite3.connect(str(key4_db)) as conn:
        row = conn.execute("SELECT a11 FROM nssPrivate LIMIT 1").fetchone()
    if row is None or not isinstance(row[0], bytes):
        msg = "key4.db does not contain an NSS private key"
        raise ValueError(msg)
    return row[0]


def _unwrap_profile_key(key4_db: Path, master_password: str = "") -> bytes:
    """Verify the master password and unwrap the profile decryption key."""
    global_salt, item2 = _read_key4_db_metadata(key4_db)

    # Verify master password (_nss_decrypt returns unpadded plaintext)
    check = _nss_decrypt(global_salt, master_password, item2)
    if check != b"password-check":
        msg = "Master password incorrect or unsupported key4.db format"
        raise ValueError(msg)

    # Unwrap the profile key
    wrapped = _read_nss_private_key(key4_db)
    return _nss_decrypt(global_salt, master_password, wrapped)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decrypt a Thunderbird IMAP password for mailjail",
    )
    parser.add_argument(
        "--profile", required=True,
        help="Thunderbird profile directory (logins.json and key4.db inferred)",
    )
    parser.add_argument(
        "--logins-json", default=None,
        help="Override logins.json path (default: <profile>/logins.json)",
    )
    parser.add_argument(
        "--key4-db", default=None,
        help="Override key4.db path (default: <profile>/key4.db)",
    )
    parser.add_argument(
        "--origin", required=True,
        help="Login origin, e.g. imap://mail.gandi.net",
    )
    parser.add_argument("--hostname", default=None, help="Optional host hint")
    parser.add_argument("--encrypted-username", default=None)
    parser.add_argument("--encrypted-password", default=None)
    return parser.parse_args()


def validate_inputs(profile: Path, logins_json: Path, key4_db: Path) -> None:
    if not profile.exists():
        msg = f"Profile not found: {profile}"
        raise FileNotFoundError(msg)
    if not logins_json.exists():
        msg = f"logins.json not found: {logins_json}"
        raise FileNotFoundError(msg)
    if not key4_db.exists():
        msg = f"key4.db not found: {key4_db}"
        raise FileNotFoundError(msg)


def load_matching_login(logins_json: Path, origin: str) -> dict[str, object]:
    with open(logins_json, encoding="utf-8") as f:
        payload = json.load(f)
    for entry in payload.get("logins", []):
        if entry.get("hostname") == origin:
            return entry
    msg = f"No Thunderbird login found for origin: {origin}"
    raise ValueError(msg)


def decrypt_with_local_tooling(
    *,
    profile: Path,
    logins_json: Path,
    key4_db: Path,
    origin: str,
    hostname: str | None,
    encrypted_username: str | None,
    encrypted_password: str | None,
) -> str:
    """Return the decrypted password from Thunderbird's local NSS database."""
    _ = profile, logins_json, origin, hostname, encrypted_username
    if not encrypted_password:
        msg = "Login entry is missing encrypted password"
        raise ValueError(msg)
    profile_key = _unwrap_profile_key(key4_db)
    return _decrypt_login_blob(encrypted_password, profile_key)


def main() -> int:
    args = parse_args()
    profile = Path(args.profile).expanduser()
    logins_json = (
        Path(args.logins_json).expanduser()
        if args.logins_json
        else profile / "logins.json"
    )
    key4_db = (
        Path(args.key4_db).expanduser()
        if args.key4_db
        else profile / "key4.db"
    )

    try:
        validate_inputs(profile, logins_json, key4_db)
        login = load_matching_login(logins_json, args.origin)
        password = decrypt_with_local_tooling(
            profile=profile,
            logins_json=logins_json,
            key4_db=key4_db,
            origin=args.origin,
            hostname=args.hostname,
            encrypted_username=(
                args.encrypted_username or login.get("encryptedUsername")
            ),
            encrypted_password=(
                args.encrypted_password or login.get("encryptedPassword")
            ),
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(password, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
