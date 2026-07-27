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
from typing import Any, Dict, Optional, Sequence, Union

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


def _normalize_audiences(
    expected_audience: Optional[Union[str, Sequence[str]]],
) -> list[str]:
    """Normalize comma-separated client IDs or a sequence into an allowlist."""
    if not expected_audience:
        return []
    raw = expected_audience.split(",") if isinstance(expected_audience, str) else expected_audience
    return [value.strip() for value in raw if value and value.strip()]


def _verify_with_jwt(
    token: str,
    provider: str,
    expected_audience: Optional[Union[str, Sequence[str]]],
) -> Optional[Dict[str, Any]]:
    """Cryptographically verify an RS256 token against an audience allowlist."""
    audiences = _normalize_audiences(expected_audience)
    if not audiences:
        return None

    try:
        import jwt
        from jwt.algorithms import RSAAlgorithm

        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not header.get("kid"):
            return None

        config = _PROVIDER_CONFIGS[provider]
        jwks = _fetch_jwks(config["jwks_url"])
        if not jwks:
            return None
        jwk = _find_key_by_kid(jwks, header["kid"])
        if not jwk:
            return None
        key = RSAAlgorithm.from_jwk(json.dumps(jwk))

        return jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            issuer=config["issuer"],
            audience=audiences,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "verify_iat": True,
            },
        )
    except Exception:
        return None


def verify_id_token(
    token: str,
    provider: str,
    expected_audience: Optional[Union[str, Sequence[str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Return verified provider claims, or None. Never decode unsigned tokens."""
    if provider not in _PROVIDER_CONFIGS:
        return None
    return _verify_with_jwt(token, provider, expected_audience)


def verify_apple_id_token(
    token: str,
    expected_audience: Optional[Union[str, Sequence[str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Verify an Apple Sign In ID token."""
    return verify_id_token(token, "apple", expected_audience)


def verify_google_id_token(
    token: str,
    expected_audience: Optional[Union[str, Sequence[str]]] = None,
) -> Optional[Dict[str, Any]]:
    """Verify a Google Sign In ID token."""
    return verify_id_token(token, "google", expected_audience)
