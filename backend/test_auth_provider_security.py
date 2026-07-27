"""Security regressions for Apple/Google identity-token verification."""

import base64
import json

from auth_providers import _normalize_audiences, verify_google_id_token


def _part(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()


def test_audience_allowlist_parses_multiple_clients():
    assert _normalize_audiences("web-client, ios-client ,") == [
        "web-client",
        "ios-client",
    ]


def test_missing_audience_fails_closed():
    token = f"{_part({'alg': 'none'})}.{_part({'sub': 'attacker'})}."
    assert verify_google_id_token(token, None) is None


def test_unsigned_token_is_rejected_for_allowed_audience():
    token = (
        f"{_part({'alg': 'none', 'typ': 'JWT'})}."
        f"{_part({'sub': 'attacker', 'aud': 'web-client'})}."
    )
    assert verify_google_id_token(token, "web-client,ios-client") is None