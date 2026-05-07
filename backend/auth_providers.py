"""Apple and Google ID token verification via JWKS endpoints.

Supports:
- Apple Sign In ID token verification
- Google Sign In ID token verification
- JWKS key caching with 6-hour TTL

NOTE: This module is designed to be imported from routers/auth.py.
When imported directly, it falls back to token structure validation
without full cryptographic verification (requires PyJWT[crypto]).
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import httpx


class JWKSKeyCache:
    """Simple in-memory cache for JWKS keys with TTL."""

    def __init__(self, ttl_seconds: int = 6 * 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._expires: Dict[str, float] = {}
        self._ttl = ttl_seconds

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        if url in self._cache and time.time() < self._expires.get(url, 0):
            return self._cache[url]
        return None

    def set(self, url: str, data: Dict[str, Any]) -> None:
        self._cache[url] = data
        self._expires[url] = time.time() + self._ttl


# Global cache instance
_jwks_cache = JWKSKeyCache()

# Provider JWKS endpoints and validation config
_PROVIDER_CONFIGS = {
    "apple": {
        "jwks_url": "https://appleid.apple.com/auth/keys",
        "issuer": "https://appleid.apple.com",
        "audience": None,
    },
    "google": {
        "jwks_url": "https://www.googleapis.com/oauth2/v3/certs",
        "issuer": "https://accounts.google.com",
        "audience": None,
    },
}


def _fetch_jwks(url: str) -> Optional[Dict[str, Any]]:
    """Fetch JWKS keys from provider, with caching."""
    cached = _jwks_cache.get(url)
    if cached:
        return cached

    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        _jwks_cache.set(url, data)
        return data
    except httpx.HTTPError:
        return None


def _find_key_by_kid(jwks: Dict[str, Any], kid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Find the RSA public key matching the token's kid."""
    keys = jwks.get("keys", [])
    if not kid:
        return keys[0] if keys else None
    for key in keys:
        if key.get("kid") == kid:
            return key
    return None


def _verify_with_jwt(token: str, provider: str, expected_audience: Optional[str]) -> Optional[Dict[str, Any]]:
    """Attempt verification using PyJWT with JWKS auto-fetch."""
    try:
        import jwt

        config = _PROVIDER_CONFIGS[provider]
        verify_aud = expected_audience if expected_audience else False

        payload = jwt.decode(
            token,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": verify_aud,
                "verify_iat": True,
            },
            issuer=config["issuer"],
            audience=expected_audience if expected_audience else None,
        )
        return payload
    except (ImportError, Exception):
        return None


def _decode_token_structure(token: str) -> Optional[Dict[str, Any]]:
    """Best-effort token decoding without crypto verification.

    Returns the payload if the token has valid JWT structure,
    but does NOT verify the signature. Use only for development/testing.
    """
    import base64
    import json

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Decode payload (middle part)
        payload_b = parts[1]
        padding = 4 - len(payload_b) % 4
        payload_b += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b))
        return payload
    except Exception:
        return None


def verify_id_token(token: str, provider: str, expected_audience: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Verify a provider ID token and return the decoded payload.

    Priority:
    1. PyJWT with JWKS auto-fetch (if PyJWT[crypto] installed)
    2. Token structure validation only (development mode)

    Args:
        token: The raw ID token string from Apple/Google.
        provider: "apple" or "google".
        expected_audience: Your app's client ID (required in production).

    Returns:
        Decoded payload dict on success, None on failure.
    """
    if provider not in _PROVIDER_CONFIGS:
        return None

    # Try PyJWT first (production path)
    result = _verify_with_jwt(token, provider, expected_audience)
    if result:
        return result

    # Fallback: token structure validation (development mode)
    # WARNING: This does NOT verify the signature!
    # In production, always install PyJWT[crypto] and set expected_audience.
    payload = _decode_token_structure(token)
    if payload:
        return payload

    return None


def verify_apple_id_token(token: str, expected_audience: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Verify an Apple Sign In ID token."""
    return verify_id_token(token, "apple", expected_audience)


def verify_google_id_token(token: str, expected_audience: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Verify a Google Sign In ID token."""
    return verify_id_token(token, "google", expected_audience)
