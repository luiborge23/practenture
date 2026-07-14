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


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Verify a TOTP code with ±window time steps (default ±1 = ±30s).

    Args:
        secret: Base32-encoded TOTP secret
        code: 6-digit code from authenticator app
        window: Number of time steps to check before/after current time

    Returns:
        True if code is valid within the window
    """
    if not code or not secret:
        return False

    code = code.strip().replace(" ", "")
    if len(code) != 6 or not code.isdigit():
        return False

    current_step = int(time.time()) // 30
    for offset in range(-window, window + 1):
        step = current_step + offset
        expected = _hotp(secret, step)
        if hmac.compare_digest(expected, code):
            return True
    return False


def get_totp_uri(secret: str, account_name: str, issuer: str = "BizSimAI") -> str:
    """Generate a otpauth:// URI for QR code generation (Google Authenticator compatible)."""
    from urllib.parse import quote
    label = quote(f"{issuer}:{account_name}", safe=":")
    issuer_encoded = quote(issuer, safe="")
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_encoded}&algorithm=SHA1&digits=6&period=30"


def generate_backup_codes(count: int = 10) -> list:
    """Generate one-time-use backup codes (8 hex chars each)."""
    return [secrets.token_hex(4).upper() for _ in range(count)]
