"""Password hashing utilities — bcrypt with SHA-256 migration path.

SOTA: bcrypt with cost factor 12 is the industry standard for password hashing.
This module provides a transparent migration from legacy SHA-256 hashes:
on login, if the stored hash looks like SHA-256 (64 hex chars), we verify
against SHA-256, then silently re-hash with bcrypt and update the DB.

Usage:
    from security import hash_password, verify_password, is_legacy_hash

    hashed = hash_password(plain_text)
    is_valid = verify_password(plain_text, hashed)
    if is_legacy_hash(hashed):
        # migrate to bcrypt
        new_hash = hash_password(plain_text)
"""

from __future__ import annotations

import hashlib
import re

import bcrypt

# bcrypt cost factor — 12 is the 2024+ SOTA recommendation (t3.micro ~100ms)
_BCRYPT_COST = 12

# SHA-256 hex digest pattern (legacy detection)
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
# A complete, supported bcrypt encoding: revision, valid cost, salt, checksum.
# Keeping this strict prevents bcrypt-looking garbage from bypassing the fixed
# dummy verification performed by privileged authentication callers.
_BCRYPT_PATTERN = re.compile(
    r"^\$2[aby]\$(?:0[4-9]|[12][0-9]|3[01])\$"
    r"[./A-Za-z0-9]{21}[.Oeu][./A-Za-z0-9]{31}$"
)


def hash_password(plain: str) -> str:
    """Hash a password using bcrypt with cost factor 12."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(_BCRYPT_COST)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a stored hash.

    Supports both bcrypt (new) and SHA-256 (legacy) hashes.
    Returns True if the password matches.
    """
    if is_legacy_hash(hashed):
        # Legacy SHA-256 — verify and let caller migrate
        return hashlib.sha256(plain.encode()).hexdigest() == hashed
    # bcrypt hash
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def is_legacy_hash(hashed: object) -> bool:
    """Check if a hash is legacy SHA-256 (64 hex chars)."""
    return isinstance(hashed, str) and bool(_SHA256_PATTERN.fullmatch(hashed))


def is_bcrypt_hash(hashed: object) -> bool:
    """Return whether *hashed* has a complete supported bcrypt encoding."""
    return isinstance(hashed, str) and bool(_BCRYPT_PATTERN.fullmatch(hashed))


def needs_migration(hashed: str) -> bool:
    """Check if a hash should be migrated to bcrypt."""
    return is_legacy_hash(hashed)


# ── Password complexity validation ──────────────────────────────────────────

_MIN_LENGTH = 8
_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"

# Top 50 most common breached passwords (subset of HIBP top 1000)
_COMMON_PASSWORDS = frozenset({
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "shadow", "123123", "654321", "superman", "qazwsx",
    "michael", "football", "password1", "password123", "batman", "welcome",
    "welcome1", "admin", "admin123", "login", "passw0rd", "hello", "charlie",
    "donald", "password!", "pass123", "pass1234", "1q2w3e4r", "111111", "000000",
    "qwerty123", "password12", "1234567890", "abcd1234", "passw0rd!", "Password1",
    "Password!", "Welcome1", "Welcome123",
})


def validate_password_complexity(password: str) -> tuple[bool, str]:
    """Validate password meets complexity requirements.

    Returns (is_valid, error_message). If is_valid=True, error_message is empty.
    """
    if len(password) < _MIN_LENGTH:
        return False, f"Password must be at least {_MIN_LENGTH} characters"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least 1 uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least 1 lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least 1 digit"

    if not any(c in _SPECIAL_CHARS for c in password):
        return False, "Password must contain at least 1 special character"

    if password.lower() in _COMMON_PASSWORDS:
        return False, "Password is too common — choose a stronger password"

    return True, ""
