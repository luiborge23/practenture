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


def generate_backup_codes(count: int = 10) -> list:
    """Generate one-time-use backup codes (8 hex chars each)."""
    return [secrets.token_hex(4).upper() for _ in range(count)]
