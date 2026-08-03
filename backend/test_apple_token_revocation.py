from __future__ import annotations

import json
from urllib.parse import parse_qs

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

import apple_token_revocation
from apple_token_revocation import AppleRevocationError, revoke_apple_authorization


class _Response:
    def __init__(self, payload: dict | bytes | None = None) -> None:
        self._payload = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload or {}).encode("utf-8")
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def _configure_apple(monkeypatch) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private_key = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.setenv("PRACTENTURE_APPLE_TEAM_ID", "TEAM123456")
    monkeypatch.setenv("PRACTENTURE_APPLE_KEY_ID", "KEY1234567")
    monkeypatch.setenv("PRACTENTURE_APPLE_PRIVATE_KEY", private_key)
    monkeypatch.setenv("PRACTENTURE_APPLE_AUDIENCE", "com.practenture.app")


def test_revoke_apple_authorization_exchanges_code_and_revokes_tokens(monkeypatch) -> None:
    _configure_apple(monkeypatch)
    requests = []
    responses = iter(
        [
            _Response({"access_token": "access-token", "refresh_token": "refresh-token"}),
            _Response(b""),
            _Response(b""),
        ]
    )

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return next(responses)

    monkeypatch.setattr(apple_token_revocation.request, "urlopen", fake_urlopen)
    revoke_apple_authorization("fresh-authorization-code")

    assert [request.full_url for request, _ in requests] == [
        "https://appleid.apple.com/auth/token",
        "https://appleid.apple.com/auth/revoke",
        "https://appleid.apple.com/auth/revoke",
    ]
    exchange = parse_qs(requests[0][0].data.decode("utf-8"))
    assert exchange["code"] == ["fresh-authorization-code"]
    assert exchange["client_id"] == ["com.practenture.app"]
    assert exchange["grant_type"] == ["authorization_code"]
    assert exchange["client_secret"][0]

    revocations = [parse_qs(request.data.decode("utf-8")) for request, _ in requests[1:]]
    assert revocations[0]["token"] == ["refresh-token"]
    assert revocations[0]["token_type_hint"] == ["refresh_token"]
    assert revocations[1]["token"] == ["access-token"]
    assert revocations[1]["token_type_hint"] == ["access_token"]
    assert all(timeout == 15 for _, timeout in requests)


def test_revoke_apple_authorization_fails_closed_when_configuration_missing(
    monkeypatch,
) -> None:
    for name in (
        "PRACTENTURE_APPLE_TEAM_ID",
        "APPLE_TEAM_ID",
        "PRACTENTURE_APPLE_KEY_ID",
        "APPLE_KEY_ID",
        "PRACTENTURE_APPLE_PRIVATE_KEY",
        "APPLE_PRIVATE_KEY",
        "PRACTENTURE_APPLE_AUDIENCE",
        "APPLE_AUDIENCE",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(AppleRevocationError, match="not configured"):
        revoke_apple_authorization("fresh-authorization-code")


def test_startup_validation_rejects_incomplete_apple_revocation_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PRACTENTURE_APPLE_AUDIENCE", "com.practenture.app")
    monkeypatch.delenv("PRACTENTURE_APPLE_TEAM_ID", raising=False)
    monkeypatch.delenv("PRACTENTURE_APPLE_KEY_ID", raising=False)
    monkeypatch.delenv("PRACTENTURE_APPLE_PRIVATE_KEY", raising=False)

    with pytest.raises(AppleRevocationError, match="not configured"):
        apple_token_revocation.validate_apple_revocation_configuration()


def test_startup_validation_accepts_complete_apple_revocation_configuration(
    monkeypatch,
) -> None:
    _configure_apple(monkeypatch)
    apple_token_revocation.validate_apple_revocation_configuration()


def test_revoke_apple_authorization_rejects_missing_code(monkeypatch) -> None:
    _configure_apple(monkeypatch)
    with pytest.raises(AppleRevocationError, match="authorization code"):
        revoke_apple_authorization("")
