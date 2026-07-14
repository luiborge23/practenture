"""Rate limiting for login attempts and code redemption.

SOTA: 5 failed login attempts → 15-minute lockout.
Uses in-memory dict (sufficient for single-worker gunicorn on t3.micro).
For multi-worker, would need Redis — but we run 1 worker / 4 threads.

Usage:
    from rate_limiter import check_login_rate, record_login_failure, record_login_success

    # Before login:
    locked, retry_after = check_login_rate(username)
    if locked:
        raise HTTPException(429, ...)

    # After login attempt:
    if success:
        record_login_success(username)
    else:
        record_login_failure(username)
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

# ── Configuration ───────────────────────────────────────────────────────────

MAX_ATTEMPTS = 5          # Lock after 5 failures
LOCKOUT_SECONDS = 900      # 15 minutes
WINDOW_SECONDS = 600      # Attempts reset after 10 min of no activity


@dataclass
class _AttemptRecord:
    attempts: int = 0
    first_attempt: float = 0.0
    locked_until: float = 0.0

    @property
    def is_locked(self) -> bool:
        return time.time() < self.locked_until

    @property
    def retry_after(self) -> int:
        if not self.is_locked:
            return 0
        return int(self.locked_until - time.time())


# ── In-memory store ─────────────────────────────────────────────────────────

_login_attempts: dict[str, _AttemptRecord] = defaultdict(_AttemptRecord)
_redeem_attempts: dict[str, _AttemptRecord] = defaultdict(_AttemptRecord)


def _cleanup_stale(store: dict[str, _AttemptRecord]) -> None:
    """Remove entries that are unlocked and have no recent activity."""
    now = time.time()
    stale = [
        key for key, rec in store.items()
        if not rec.is_locked and (now - rec.first_attempt) > WINDOW_SECONDS
    ]
    for key in stale:
        del store[key]


def check_login_rate(username: str) -> tuple[bool, int]:
    """Check if the user is locked out. Returns (is_locked, retry_after_seconds)."""
    _cleanup_stale(_login_attempts)
    rec = _login_attempts[username]
    if rec.is_locked:
        return True, rec.retry_after
    return False, 0


def record_login_failure(username: str) -> None:
    """Record a failed login attempt. Locks after MAX_ATTEMPTS."""
    rec = _login_attempts[username]
    now = time.time()
    if rec.first_attempt == 0.0 or (now - rec.first_attempt) > WINDOW_SECONDS:
        rec.first_attempt = now
        rec.attempts = 0
    rec.attempts += 1
    if rec.attempts >= MAX_ATTEMPTS:
        rec.locked_until = now + LOCKOUT_SECONDS


def record_login_success(username: str) -> None:
    """Clear attempt counter on successful login."""
    if username in _login_attempts:
        del _login_attempts[username]


# ── Code redemption rate limiting (per IP) ──────────────────────────────────

MAX_REDEEM_ATTEMPTS = 10      # Lock after 10 failed redemption attempts
REDEEM_LOCKOUT_SECONDS = 3600  # 1 hour
REDEEM_WINDOW_SECONDS = 3600   # Reset after 1 hour


def check_redeem_rate(ip: str) -> tuple[bool, int]:
    """Check if an IP is locked out from code redemption."""
    _cleanup_stale(_redeem_attempts)
    rec = _redeem_attempts[ip]
    if rec.is_locked:
        return True, rec.retry_after
    return False, 0


def record_redeem_failure(ip: str) -> None:
    """Record a failed code redemption attempt."""
    rec = _redeem_attempts[ip]
    now = time.time()
    if rec.first_attempt == 0.0 or (now - rec.first_attempt) > REDEEM_WINDOW_SECONDS:
        rec.first_attempt = now
        rec.attempts = 0
    rec.attempts += 1
    if rec.attempts >= MAX_REDEEM_ATTEMPTS:
        rec.locked_until = now + REDEEM_LOCKOUT_SECONDS


def record_redeem_success(ip: str) -> None:
    """Clear redemption attempt counter on success."""
    if ip in _redeem_attempts:
        del _redeem_attempts[ip]
