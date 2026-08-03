"""Sign in with Apple token exchange and revocation for account deletion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from urllib import error, parse, request

import jwt


class AppleRevocationError(Exception):
    pass


def validate_apple_revocation_configuration() -> None:
    """Fail startup when Apple login is enabled without revocation credentials."""
    audience = os.environ.get("PRACTENTURE_APPLE_AUDIENCE", "").strip()
    configured = any(
        os.environ.get(name, "").strip()
        for name in (
            "PRACTENTURE_APPLE_TEAM_ID",
            "PRACTENTURE_APPLE_KEY_ID",
            "PRACTENTURE_APPLE_PRIVATE_KEY",
        )
    )
    if not audience and not configured:
        return
    _client_secret()


def _client_secret() -> tuple[str, str]:
    team_id = os.environ.get("PRACTENTURE_APPLE_TEAM_ID", "").strip()
    key_id = os.environ.get("PRACTENTURE_APPLE_KEY_ID", "").strip()
    client_id = os.environ.get("PRACTENTURE_APPLE_AUDIENCE", "").strip()
    private_key = os.environ.get("PRACTENTURE_APPLE_PRIVATE_KEY", "").replace(
        "\\n", "\n"
    )
    if not all((team_id, key_id, client_id, private_key)):
        raise AppleRevocationError(
            "Apple token revocation is not configured for account deletion."
        )
    now = datetime.now(timezone.utc)
    secret = jwt.encode(
        {
            "iss": team_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "aud": "https://appleid.apple.com",
            "sub": client_id,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": key_id},
    )
    return client_id, secret


def _post_form_json(url: str, values: dict[str, str]) -> dict:
    body = parse.urlencode(values).encode()
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            payload = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise AppleRevocationError(
            f"Apple token endpoint rejected the request ({exc.code}): {detail}"
        ) from exc
    except (error.URLError, TimeoutError) as exc:
        raise AppleRevocationError("Apple token endpoint is unavailable.") from exc
    try:
        decoded = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise AppleRevocationError("Apple returned an invalid token response.") from exc
    if not isinstance(decoded, dict):
        raise AppleRevocationError("Apple returned an invalid token response.")
    return decoded


def _post_form_status(url: str, values: dict[str, str]) -> None:
    body = parse.urlencode(values).encode()
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise AppleRevocationError(
            f"Apple token endpoint rejected the request ({exc.code}): {detail}"
        ) from exc
    except (error.URLError, TimeoutError) as exc:
        raise AppleRevocationError("Apple token endpoint is unavailable.") from exc


def exchange_apple_authorization_code(authorization_code: str) -> dict:
    """Exchange a fresh, one-use authorization code for revocable tokens."""
    if not authorization_code.strip():
        raise AppleRevocationError(
            "A fresh Apple authorization code is required for account deletion."
        )
    client_id, client_secret = _client_secret()
    tokens = _post_form_json(
        "https://appleid.apple.com/auth/token",
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": authorization_code,
            "grant_type": "authorization_code",
        },
    )
    if not any(
        isinstance(tokens.get(key), str) and tokens.get(key)
        for key in ("refresh_token", "access_token")
    ):
        raise AppleRevocationError("Apple did not return a token that can be revoked.")
    return tokens


def revoke_apple_tokens(tokens: dict) -> None:
    """Revoke exchanged Apple tokens; successful responses intentionally have no body."""
    client_id, client_secret = _client_secret()
    candidates = (
        ("refresh_token", "refresh_token"),
        ("access_token", "access_token"),
    )
    revoked = False
    for key, hint in candidates:
        token = tokens.get(key)
        if not isinstance(token, str) or not token:
            continue
        _post_form_status(
            "https://appleid.apple.com/auth/revoke",
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "token": token,
                "token_type_hint": hint,
            },
        )
        revoked = True
    if not revoked:
        raise AppleRevocationError("Apple did not return a token that can be revoked.")


def revoke_apple_authorization(authorization_code: str) -> None:
    """Compatibility helper for exchange followed by synchronous revocation."""
    revoke_apple_tokens(exchange_apple_authorization_code(authorization_code))
