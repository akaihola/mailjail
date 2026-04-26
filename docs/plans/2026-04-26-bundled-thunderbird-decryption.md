# Bundled Thunderbird Decryption Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the NSS decryption logic from the standalone `scripts/mailjail-thunderbird-password.py` helper into a `mailjail.thunderbird` module, gated behind a `mailjail[thunderbird]` extras dependency, so users no longer need to install a separate script.

**Architecture:** The current architecture invokes a subprocess that runs the helper script. We replace `decrypt_thunderbird_login()` with a direct in-process call to `mailjail.thunderbird.decrypt_login()`. The `cryptography` dep is declared as an optional extra so users who don't use Thunderbird auth (himalaya, password-file, etc.) don't pull it in. `mailjail.thunderbird` is imported lazily inside `_apply_thunderbird_credentials()` so a missing `cryptography` only errors when Thunderbird auth is actually configured, with a clear "install `mailjail[thunderbird]`" message.

**Tech Stack:** Python 3.12+, pydantic, cryptography (optional), pytest.

---

## Background context

### Files involved

- `pyproject.toml` — add the optional extra
- `src/mailjail/thunderbird.py` — new module (ported from helper script)
- `src/mailjail/config.py` — replace subprocess call with in-process call; remove helper-related fields
- `tests/test_thunderbird.py` — new (ported from `test_thunderbird_helper.py`)
- `tests/test_config.py` — update Thunderbird tests
- `scripts/mailjail-thunderbird-password.py` — delete
- `tests/test_thunderbird_helper.py` — delete
- `DESIGN.md` — update §9 (credential providers)
- `README.md` — update install instructions
- `TASKS.md` — note completion

### Pre-existing test fixtures we will reuse

`tests/test_thunderbird_helper.py` already builds a synthetic Thunderbird profile with known plaintext (`my-secret-imap-password`) using the `synthetic_profile` fixture (lines 161–206). We port the fixture verbatim into the new test file. The DER encoders, NSS encryption helpers, and well-known constants (`GLOBAL_SALT`, `PROFILE_KEY`, etc.) come along.

### Public surface that must change in `config.py`

Currently exported from `mailjail.config`:

- `decrypt_thunderbird_login(login, helper_cmd) -> str` — **REMOVE**
- `thunderbird_helper_template() -> str` — **REMOVE**
- `DEFAULT_THUNDERBIRD_HELPER_CMD: str` — **REMOVE**
- `read_thunderbird_login(...)` — **KEEP** (still used to find profile + encrypted blobs)
- `ThunderbirdLogin` dataclass — **KEEP**
- `CredentialError` — **KEEP**

`AccountSettings` field changes:

- `thunderbird_helper_cmd: str` — **REMOVE**

This is a breaking change for any user with `thunderbird_helper_cmd` in their TOML; pydantic will reject the unknown field at config load with a clear error. That's acceptable for pre-1.0 software.

---

## Phase 1: Optional dependency wiring

### Task 1: Add the `thunderbird` extras to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml:11-12`

**Step 1: Edit pyproject.toml**

Replace the `[project.optional-dependencies]` block:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.0"]
thunderbird = ["cryptography>=43.0"]
```

**Step 2: Verify `uv sync --extra thunderbird` works**

Run: `cd /home/akaihola/prg/mailjail && uv sync --extra thunderbird`
Expected: lockfile updated; `cryptography` appears in `uv.lock`.

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add thunderbird extra (cryptography>=43.0)"
```

---

## Phase 2: Port decryption module (red/green TDD)

We move the decryption code into `src/mailjail/thunderbird.py` and the corresponding tests into `tests/test_thunderbird.py`. The "red" step is created by writing tests that import from the new module before the module exists.

### Task 2: Write the failing test file

**Files:**
- Create: `tests/test_thunderbird.py`

**Step 1: Create tests/test_thunderbird.py**

This file contains the same synthetic profile fixture and decryption tests as `test_thunderbird_helper.py`, but imports from `mailjail.thunderbird` instead of loading the helper script via `importlib.util`. CLI-related tests (`TestCLI`, `test_invalid_key_db_fails`, `test_missing_origin_fails`) are dropped — there is no longer a CLI.

Top of file (replaces lines 1–34 of `test_thunderbird_helper.py`):

```python
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
```

Body (DER helpers, NSS encryption helpers, fixture, and tests): **copy verbatim from `tests/test_thunderbird_helper.py:36–248`**, then make these substitutions:

- `helper._unwrap_profile_key` → `thunderbird._unwrap_profile_key`
- `helper.load_matching_login` → `thunderbird.load_matching_login`
- `helper._decrypt_login_blob` → `thunderbird._decrypt_login_blob`
- `helper.decrypt_with_local_tooling(...)` → `thunderbird.decrypt_login(profile=..., logins_json=..., key4_db=..., origin=..., encrypted_password=...)` — note new function name and reduced signature (no `hostname`/`encrypted_username` arguments; those were unused in the helper, see `scripts/mailjail-thunderbird-password.py:375`).

Drop the entire `TestCLI` class (`test_thunderbird_helper.py:256–319`) and the `_SCRIPT_PATH` / `importlib.util` loading dance.

Keep `TestRejections`, but replace `helper.decrypt_with_local_tooling` with `thunderbird.decrypt_login` and adjust `match="missing encrypted password"` to whatever message we choose (see Task 3).

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_thunderbird.py -x 2>&1 | head -20`
Expected: `ImportError: cannot import name 'thunderbird' from 'mailjail'` (or similar).

**Step 3: Commit (failing test)**

```bash
git add tests/test_thunderbird.py
git commit -m "test: add tests for mailjail.thunderbird (failing)"
```

### Task 3: Implement `mailjail.thunderbird`

**Files:**
- Create: `src/mailjail/thunderbird.py`

**Step 1: Create the module**

Port the implementation from `scripts/mailjail-thunderbird-password.py`. Specifically copy:

- `ASN1` class and `_decode_oid` (lines 52–118)
- `_unpad`, `_decrypt_3des_cbc`, `_decrypt_aes_cbc` (lines 126–138)
- OID constants (lines 146–149)
- `_nss_decrypt`, `_nss_legacy_decrypt`, `_nss_modern_decrypt` (lines 152–226)
- `_decrypt_login_blob` (lines 234–264)
- `_read_key4_db_metadata`, `_read_nss_private_key`, `_unwrap_profile_key` (lines 272–308)
- `load_matching_login` (lines 354–361)

Replace the `decrypt_with_local_tooling()` CLI shim with a clean public function. The helper script accepted `profile`, `logins_json`, `origin`, `hostname`, and `encrypted_username` because the CLI surface needed them — but the decryption itself only uses `key4_db` and `encrypted_password`. The in-process API drops all the unused parameters:

```python
def decrypt_login(
    *,
    key4_db: Path,
    encrypted_password: str | None,
) -> str:
    """Return the decrypted Thunderbird IMAP password."""
    if not encrypted_password:
        msg = "Login entry is missing encrypted password"
        raise ValueError(msg)
    profile_key = _unwrap_profile_key(key4_db)
    return _decrypt_login_blob(encrypted_password, profile_key)
```

**Update `tests/test_thunderbird.py` to match the tightened signature:**

The test file (committed in Task 2) was written against a wider signature that included `profile`, `logins_json`, `origin`. Update the two call sites:

- In `TestFullDecryptionFlow.test_decrypt_with_local_tooling` — rename the test to `test_decrypt_login_end_to_end` (the old name referred to the deleted CLI helper) AND update the call to `thunderbird.decrypt_login(key4_db=synthetic_profile / "key4.db", encrypted_password=login.get("encryptedPassword"))`.
- In `TestRejections.test_missing_encrypted_password` — update the call to `thunderbird.decrypt_login(key4_db=Path("/tmp"), encrypted_password=None)`.

Module header — keep the imports from the helper script, plus a docstring:

```python
"""In-process Thunderbird NSS decryption for the `thunderbird` credential provider.

Requires the `cryptography` package; install via `pip install mailjail[thunderbird]`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import json
import sqlite3
from pathlib import Path

from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
```

Drop everything CLI-related (`parse_args`, `validate_inputs`, `decrypt_with_local_tooling` shim, `main`, the script preamble).

**Step 2: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_thunderbird.py -v`
Expected: all tests pass (every `TestFullDecryptionFlow` and `TestRejections` test green).

**Step 3: Run the full test suite**

Run: `uv run pytest -q`
Expected: existing `test_thunderbird_helper.py` tests still pass (we haven't deleted it yet); `test_config.py` still passes (`config.py` not touched yet).

**Step 4: Commit (green)**

```bash
git add src/mailjail/thunderbird.py
git commit -m "feat(thunderbird): in-process NSS decryption module"
```

---

## Phase 3: Wire into config.py (red/green TDD)

### Task 4: Write failing test for in-process Thunderbird credential resolution

**Files:**
- Modify: `tests/test_config.py`

**Step 1: Add a new test using the synthetic profile**

We need a test that drives `load_settings()` end-to-end against a real synthetic Thunderbird profile (no shell helper involved). Add this to `test_config.py` (after `test_two_accounts_can_use_different_providers`):

```python
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
```

**Step 2: Refactor `synthetic_profile` fixture into a reusable factory**

In `tests/test_thunderbird.py`, extract the body of the `synthetic_profile` fixture into a module-level function so `test_config.py` can import it:

```python
def synthetic_profile_factory(tmp_path: Path) -> Path:
    """Build a synthetic Thunderbird profile (used by both test files)."""
    # ... existing body of synthetic_profile, returns the profile path
    return profile

@pytest.fixture()
def synthetic_profile(tmp_path: Path) -> Path:
    return synthetic_profile_factory(tmp_path)
```

**Step 3: Run the failing test to verify the breakage**

Run: `uv run pytest tests/test_config.py::test_thunderbird_provider_uses_in_process_decryption -xvs`
Expected: test fails because `_apply_thunderbird_credentials()` still tries to invoke `python3 ~/.local/bin/mailjail-thunderbird-password ...`, which either fails (script missing) or misbehaves.

**Step 4: Commit (failing test)**

```bash
git add tests/test_thunderbird.py tests/test_config.py
git commit -m "test(config): add failing in-process thunderbird test"
```

### Task 5: Update `_apply_thunderbird_credentials()` in `config.py`

**Files:**
- Modify: `src/mailjail/config.py:20-24` (remove `DEFAULT_THUNDERBIRD_HELPER_CMD`)
- Modify: `src/mailjail/config.py:36-52` (drop `thunderbird_helper_cmd` from `AccountSettings`)
- Modify: `src/mailjail/config.py:105-115` (drop `thunderbird_helper_cmd` from `_ACCOUNT_AUTH_TOML_FIELDS`)
- Modify: `src/mailjail/config.py:249-266` (`_apply_thunderbird_credentials`)
- Modify: `src/mailjail/config.py:384-421` (delete `decrypt_thunderbird_login`, `thunderbird_helper_template`)

**Step 1: Replace the subprocess call with an in-process call**

Replace the body of `_apply_thunderbird_credentials()` with:

```python
def _apply_thunderbird_credentials(data: dict[str, Any]) -> None:
    thunderbird_dir = Path(data.get("thunderbird_dir", str(DEFAULT_THUNDERBIRD_DIR)))
    profile_name = data.get("thunderbird_profile")
    username_hint = data.get("thunderbird_username_hint") or data.get("imap_username")
    hostname_hint = data.get("thunderbird_hostname_hint") or data.get("imap_host")

    login = read_thunderbird_login(
        thunderbird_dir=thunderbird_dir,
        profile_name=profile_name,
        username_hint=username_hint,
        hostname_hint=hostname_hint,
    )

    try:
        from mailjail.thunderbird import decrypt_login
    except ImportError as exc:
        raise CredentialError(
            "Thunderbird credential provider requires the 'cryptography' "
            "package. Install with: pip install 'mailjail[thunderbird]'"
        ) from exc

    try:
        password = decrypt_login(
            key4_db=login.key4_db,
            encrypted_password=login.encrypted_password,
        )
    except Exception as exc:
        raise CredentialError(
            f"Thunderbird decryption failed: {exc}"
        ) from exc

    if not data.get("imap_host"):
        data["imap_host"] = _origin_host(login.hostname)
    data["imap_password"] = password
```

**Step 2: Delete obsolete code from `config.py`**

Delete in order:

- `DEFAULT_THUNDERBIRD_HELPER_CMD` constant (lines 21–24)
- `thunderbird_helper_cmd` field on `AccountSettings` (line 50)
- `"thunderbird_helper_cmd"` entry in `_ACCOUNT_AUTH_TOML_FIELDS` tuple (line 112)
- `decrypt_thunderbird_login()` function (lines 384–416)
- `thunderbird_helper_template()` function (lines 419–421)
- The `from string import Template` import (line 12) — no longer used.

**Step 3: Add hard-fail validation for unknown TOML keys**

Today `_build_account()` (`config.py:196–226`) consumes known keys from each section via an explicit allowlist (`_ACCOUNT_TOML_FIELD_MAP`, `_ACCOUNT_AUTH_TOML_FIELDS`). Any unknown key is silently ignored — including legacy `thunderbird_helper_cmd`. The user has decided (no backwards compat) that we hard-fail instead.

Add a strict-keys check at the top of `_build_account()` after extracting `pool_section` and `auth_section`:

```python
def _build_account(account_id: str, section: dict[str, Any]) -> AccountSettings:
    section = dict(section)
    pool_section = section.pop("pool", {}) or {}
    auth_section = section.pop("auth", {}) or {}

    known_section_keys = set(_ACCOUNT_TOML_FIELD_MAP)
    extra_section = set(section) - known_section_keys
    if extra_section:
        raise ConfigError(
            f"Account {account_id!r}: unknown key(s) in [accounts.{account_id}]: "
            f"{sorted(extra_section)}"
        )

    known_pool_keys = {"size"}
    extra_pool = set(pool_section) - known_pool_keys
    if extra_pool:
        raise ConfigError(
            f"Account {account_id!r}: unknown key(s) in "
            f"[accounts.{account_id}.pool]: {sorted(extra_pool)}"
        )

    known_auth_keys = set(_ACCOUNT_AUTH_TOML_FIELDS)
    extra_auth = set(auth_section) - known_auth_keys
    if extra_auth:
        raise ConfigError(
            f"Account {account_id!r}: unknown key(s) in "
            f"[accounts.{account_id}.auth]: {sorted(extra_auth)}"
        )

    # ... rest of function unchanged
```

Add a corresponding test to `tests/test_config.py`:

```python
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
```

**Step 4: Run the previously-failing test**

Run: `uv run pytest tests/test_config.py::test_thunderbird_provider_uses_in_process_decryption tests/test_config.py::test_unknown_thunderbird_helper_cmd_raises -xvs`
Expected: both PASS.

**Step 5: Commit (green)**

```bash
git add src/mailjail/config.py tests/test_config.py
git commit -m "refactor(config): in-process thunderbird; hard-fail unknown TOML keys"
```

### Task 6: Remove obsolete tests in `test_config.py`

**Files:**
- Modify: `tests/test_config.py`

**Step 1: Update the import block (lines 9–17)**

Drop the now-removed names:

```python
from mailjail.config import (
    ConfigError,
    CredentialError,
    load_settings,
    read_himalaya_credentials,
    read_thunderbird_login,
)
```

**Step 2: Delete obsolete tests**

Delete in order:

- `test_decrypt_thunderbird_login_uses_helper` (lines 275–287) — the function it tests no longer exists.
- `test_thunderbird_helper_failure_raises` (lines 290–300) — same reason.
- `test_thunderbird_helper_template_mentions_expected_placeholders` (lines 303–308) — same reason.
- `test_default_thunderbird_helper_cmd_uses_profile_and_origin_only` (lines 311–317) — same reason.
- `_login` factory at the bottom (lines 320–end) — only used by the deleted tests; remove the entire helper.

**Step 3: Update `test_two_accounts_can_use_different_providers`**

Lines 202–238: this test currently sets `thunderbird_helper_cmd = "python3 -c \"print('secret-from-thunderbird')\""` to stub out decryption. With in-process decryption that no longer works. Replace this test with one that uses the synthetic profile factory:

```python
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
```

**Step 4: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass except those in `test_thunderbird_helper.py` (still present, still loading the script — about to be deleted).

**Step 5: Commit**

```bash
git add tests/test_config.py
git commit -m "test(config): drop helper-subprocess tests"
```

---

## Phase 4: Remove old artifacts

### Task 7: Delete the helper script and its test file

**Files:**
- Delete: `scripts/mailjail-thunderbird-password.py`
- Delete: `tests/test_thunderbird_helper.py`

**Step 1: Delete the files**

```bash
git rm scripts/mailjail-thunderbird-password.py tests/test_thunderbird_helper.py
```

**Step 2: Check `scripts/` for other content**

```bash
ls scripts/
```

If the directory is empty, also `git rm -r scripts/` and remove any references to it (none expected).

**Step 3: Run the full test suite**

Run: `uv run pytest -q`
Expected: all tests pass.

**Step 4: Commit**

```bash
git commit -m "chore: remove standalone thunderbird helper script"
```

---

## Phase 5: Documentation

### Task 8: Update `DESIGN.md` §9

**Files:**
- Modify: `DESIGN.md` around lines 600–660

**Step 1: Update the example TOML (lines 621–637)**

Remove the `thunderbird_helper_cmd` line. The `[accounts.personal.auth]` section becomes:

```toml
[accounts.personal.auth]
provider = "thunderbird"
thunderbird_dir = "~/.thunderbird"
# Optional explicit profile name if not using the default Thunderbird profile
# thunderbird_profile = "abcd.default-release"
# Optional hints to choose among multiple Thunderbird logins
# thunderbird_hostname_hint = "mail.personal.example"
# thunderbird_username_hint = "me@personal.example"
```

**Step 2: Update the credential resolution bullet (line 653)**

Change:

> `provider = "thunderbird"` / `"auto"`: discover Thunderbird profile/login metadata, then invoke the configured helper command to decrypt and print the password

to:

> `provider = "thunderbird"` / `"auto"`: discover Thunderbird profile/login metadata and decrypt the password in-process via NSS. Requires the optional `cryptography` dependency — install with `pip install 'mailjail[thunderbird]'`.

**Step 3: Replace the "Thunderbird note" (line 659)**

Change:

> Thunderbird note: mailjail does **not** implement NSS decryption internally. Instead it provides a stable provider interface that discovers the right profile/login and calls a local helper script/tool, keeping NSS-specific logic outside the main service.

to:

> Thunderbird note: NSS decryption (the same scheme Firefox/Thunderbird use to protect `logins.json` with the master password) is implemented in-process in `mailjail.thunderbird`. The `cryptography` library is an *optional* extra so users on other providers (himalaya, password-file) don't pay the dependency cost. Earlier versions of mailjail shelled out to a separate `mailjail-thunderbird-password` helper script — that helper has been removed.

**Step 4: Commit**

```bash
git add DESIGN.md
git commit -m "docs(design): describe in-process thunderbird decryption"
```

### Task 9: Update `README.md`

**Files:**
- Modify: `README.md`

**Step 1: Update the install snippet (lines 28–35)**

Add a note about the optional extra:

```markdown
## Install

```sh
git clone https://github.com/akaihola/mailjail
cd mailjail
uv sync                            # core install
uv sync --extra thunderbird        # add NSS decryption for Thunderbird auth
```

Python 3.12+ is required. Runtime dependencies: `imap_tools`, `waitress`,
`pydantic` (declared in [pyproject.toml](pyproject.toml)). The optional
`thunderbird` extra adds `cryptography>=43.0` for in-process NSS decryption.
```

**Step 2: Update the credential-providers paragraph (lines 69–73)**

Change:

> Per-account credentials can come from a password file, a himalaya keyring account, or a Thunderbird profile — see [DESIGN.md §9][design].

to:

> Per-account credentials can come from a password file, a himalaya keyring
> account, or a Thunderbird profile (in-process NSS decryption — install
> with `--extra thunderbird`). See [DESIGN.md §9][design].

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): document mailjail[thunderbird] extra"
```

### Task 10: Update `TASKS.md`

**Files:**
- Modify: `TASKS.md`

**Step 1: Add a new "Phase 6 — Credential providers (backlog)" section at the bottom**

Append the following block to the end of `TASKS.md`:

```markdown
## Phase 6 — Credential providers (backlog)

- [x] Inline Thunderbird NSS decryption into `mailjail.thunderbird`; gate
      `cryptography` behind the `thunderbird` extra; remove standalone helper
      script (2026-04-26).
- [ ] Support OAuth2 token extraction for Gmail. Thunderbird stores Gmail
      credentials as OAuth2 refresh tokens (not IMAP passwords) under
      `oauth://accounts.google.com` in `logins.json`. The existing Thunderbird
      provider only handles password-style logins. Add an OAuth2 path that:
      reads the refresh token, exchanges it for an access token via Google's
      token endpoint, then uses XOAUTH2 SASL when authenticating to
      `imap.gmail.com`. Out of scope for the 2026-04-26 inlining work.
```

**Step 2: Commit**

```bash
git add TASKS.md
git commit -m "docs(tasks): mark thunderbird-inlining done; add OAuth2 backlog"
```

---

## Phase 6: Verify against a real account

This phase is manual — it verifies the change works against the user's actual Thunderbird profile.

### Task 11: Sync extras and start mailjail

**Step 1: Sync the new extra**

Run: `cd /home/akaihola/prg/mailjail && uv sync --extra thunderbird`
Expected: `cryptography` installed in `.venv`.

**Step 2: Start the service**

Run: `uv run python -m mailjail`
Expected: service binds `127.0.0.1:8895` without errors. Log line should show 3 accounts loaded (account1, account2, account3). Gmail has been dropped from the user's config — see the "Resolved decisions" section.

If the service fails to start because Thunderbird is currently running and holds an exclusive lock on `key4.db`, close Thunderbird (or copy the profile) and retry. Do **not** use `--no-verify`-style workarounds — diagnose the lock first.

### Task 12: Smoke test the JMAP endpoint

**Step 1: Hit the well-known endpoint**

Run:

```bash
xh GET http://127.0.0.1:8895/.well-known/jmap
```

Expected: JSON response with all 3 accounts (account1, account2, account3) under `accounts`.

**Step 2: List folders for the primary account**

Run:

```bash
xh POST http://127.0.0.1:8895/jmap \
  using:='["urn:ietf:params:jmap:core","urn:ietf:params:jmap:mail"]' \
  methodCalls:='[["Mailbox/get",{"accountId":"account1"},"c1"]]'
```

Expected: list of mailbox objects (INBOX, Drafts, Archives, etc.).

**Step 3: Hit `/healthz`**

Run: `xh GET http://127.0.0.1:8895/healthz`
Expected: `200 OK`, all 3 accounts reporting healthy.

If any account reports unhealthy, inspect logs — the most likely failure is an account whose Thunderbird login origin doesn't match the IMAP host (the Gmail-style OAuth2 case has been excluded from this rollout; see the OAuth2 backlog item in TASKS.md).

---

## Rollback

If anything in Phase 2 or 3 breaks badly:

```bash
git reset --hard HEAD~N   # back out the bad commits
```

The plan commits each task independently so individual phases can be reverted without losing earlier progress. The helper script and its tests remain in git history and can be restored with `git checkout` if needed.

---

## Resolved decisions

1. **Gmail OAuth2.** The Gmail account has been dropped from `~/.config/mailjail/config.toml`. OAuth2 token extraction (refresh-token → access-token → XOAUTH2 SASL) is captured as a backlog item in TASKS.md Phase 6. The 2026-04-26 inlining work targets only password-style Thunderbird logins.

2. **Backwards-compatibility shim.** No backwards compat. `thunderbird_helper_cmd` (and any other removed field) will hard-fail at config load via pydantic's strict-unknown-field rejection. No warnings, no silent ignores. Anyone with the old field in their TOML will get a clear ValidationError pointing at the unknown key.
