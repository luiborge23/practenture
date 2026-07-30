"""SOTA Phase 2: TOTP-based Multi-Factor Authentication.

Implements RFC 6238 TOTP (Time-based One-Time Password) using only Python stdlib.
No external dependencies — works with Python 3.10+.

Based on:
- RFC 6238 (TOTP)
- RFC 4226 (HOTP)
- Google Authenticator compatible (30s window, 6 digits, SHA-1)
"""

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from typing import Optional

_SECRET_PREFIX = "enc-v1$"


def _secret_encryption_key() -> bytes | None:
    """Derive an AES-256 key from a stable server secret when configured."""
    material = (
        os.environ.get("PRACTENTURE_MFA_ENCRYPTION_KEY")
        or os.environ.get("PRACTENTURE_JWT_SECRET")
        or os.environ.get("SECRET_KEY")
    )
    return hashlib.sha256(material.encode("utf-8")).digest() if material else None


def protect_totp_secret(secret: str) -> str:
    """Encrypt a TOTP seed at rest using AES-GCM.

    Development environments without a configured application secret retain the
    legacy plaintext format; production already requires a JWT secret.
    """
    key = _secret_encryption_key()
    if key is None or secret.startswith(_SECRET_PREFIX):
        return secret
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, secret.encode("ascii"), b"practenture-mfa-v1")
    token = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return f"{_SECRET_PREFIX}{token}"


def reveal_totp_secret(stored: str) -> str:
    """Decrypt a versioned TOTP seed while accepting legacy plaintext rows."""
    if not stored.startswith(_SECRET_PREFIX):
        return stored
    key = _secret_encryption_key()
    if key is None:
        raise ValueError("MFA encryption key is unavailable")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = base64.urlsafe_b64decode(stored[len(_SECRET_PREFIX):].encode("ascii"))
    if len(raw) <= 12:
        raise ValueError("Invalid encrypted MFA secret")
    return AESGCM(key).decrypt(raw[:12], raw[12:], b"practenture-mfa-v1").decode("ascii")


def generate_totp_secret() -> str:
    """Generate a random 20-byte base32-encoded TOTP secret."""
    raw = os.urandom(20)
    return base64.b32encode(raw).decode("utf-8").rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    """Generate HOTP value for a given counter (RFC 4226)."""
    # Decode base32 secret
    padding = 8 - len(secret_b32) % 8
    if padding != 8:
        secret_b32 = secret_b32 + "=" * padding
    key = base64.b32decode(secret_b32, casefold=True)

    # Counter as 8-byte big-endian
    msg = struct.pack(">Q", counter)

    # HMAC-SHA1
    h = hmac.new(key, msg, hashlib.sha1).digest()

    # Dynamic truncation
    offset = h[-1] & 0x0F
    truncated = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF

    return str(truncated)[-digits:].zfill(digits)


def resolve_totp_counter(
    secret: str,
    code: str,
    window: int = 1,
    *,
    at_time: float | None = None,
) -> int | None:
    """Return the newest RFC 6238 counter matching ``code`` within ``window``.

    Newest-first selection is deterministic even if adjacent counters happen to
    generate the same six-digit value.
    """
    if not code or not secret or window < 0:
        return None

    secret = reveal_totp_secret(secret)

    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return None

    current_step = int(time.time() if at_time is None else at_time) // 30
    for offset in range(window, -window - 1, -1):
        step = current_step + offset
        if step >= 0 and hmac.compare_digest(_hotp(secret, step), code):
            return step
    return None


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify a TOTP code with ±window time steps (default ±1 = ±30s)."""
    return resolve_totp_counter(secret, code, window) is not None


def get_totp_uri(secret: str, account_name: str, issuer: str = "Practenture") -> str:
    """Generate a otpauth:// URI for QR code generation (Google Authenticator compatible)."""
    from urllib.parse import quote
    label = quote(f"{issuer}:{account_name}", safe=":")
    issuer_encoded = quote(issuer, safe="")
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_encoded}&algorithm=SHA1&digits=6&period=30"


_BACKUP_HASH_PREFIX = "sha256$"


def normalize_backup_code(code: str) -> str:
    """Return the canonical representation used for recovery-code checks."""
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def hash_backup_code(code: str) -> str:
    """Hash a recovery code before persistence.

    Recovery codes are bearer credentials.  Storing only a one-way digest keeps
    a database read from immediately disclosing every remaining code.
    """
    digest = hashlib.sha256(normalize_backup_code(code).encode("ascii")).hexdigest()
    return f"{_BACKUP_HASH_PREFIX}{digest}"


def backup_code_matches(stored: str, candidate: str) -> bool:
    """Compare hashed codes and legacy plaintext codes in constant time."""
    normalized = normalize_backup_code(candidate)
    if not normalized or not isinstance(stored, str):
        return False
    expected = hash_backup_code(normalized)
    if stored.startswith(_BACKUP_HASH_PREFIX):
        return hmac.compare_digest(stored, expected)
    return hmac.compare_digest(normalize_backup_code(stored), normalized)


def generate_backup_codes(count: int = 10) -> list[str]:
    """Generate 10 one-time recovery codes with 48 bits of entropy each."""
    codes = []
    for _ in range(count):
        raw = secrets.token_hex(6).upper()
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:]}")
    return codes
