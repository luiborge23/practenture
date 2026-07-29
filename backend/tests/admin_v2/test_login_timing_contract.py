"""Deterministic primitive-call contracts for owner credential equalization."""

from __future__ import annotations

import hashlib

import pytest

import admin_v2.service as service_module
from admin_v2.errors import AdminError
from admin_v2.repository import AdminSessionRepository, LoginAttemptDecision
from admin_v2.service import AdminAuthService, _DUMMY_PASSWORD_HASH
from security import is_bcrypt_hash


PASSWORD = "Timing-Contract-Password!"
WRONG = "wrong-password"
BCRYPT_HASH = "$2b$12$kbOCzw.LZxI1pPmcC6cJLuzc1oQGaYrLIFcrNpKHYFaZadqlP9zvy"


class AllowingRepository(AdminSessionRepository):
    def __init__(self):
        pass

    def reserve_login_attempt(self, *args, **kwargs):
        return LoginAttemptDecision(True)


def owner(password_hash):
    return {
        "username": "owner",
        "password_hash": password_hash,
        "role": "owner",
        "status": "active",
    }


def primitive_spy(monkeypatch, user, accepted_hash=None):
    calls = []
    monkeypatch.setattr(service_module.db, "get_user", lambda username: user)

    def verify(plain, hashed):
        calls.append((plain, hashed))
        return hashed == accepted_hash

    monkeypatch.setattr(service_module, "verify_password", verify)
    return calls


def test_unknown_user_invokes_exactly_one_dummy_bcrypt_verification(monkeypatch):
    calls = primitive_spy(monkeypatch, None)

    assert AdminAuthService()._verify_owner_password("missing", WRONG) is None
    assert calls == [(WRONG, _DUMMY_PASSWORD_HASH)]
    assert is_bcrypt_hash(calls[0][1])


def test_wrong_legacy_invokes_sha_check_then_exactly_one_dummy_bcrypt(monkeypatch):
    legacy = hashlib.sha256(PASSWORD.encode()).hexdigest()
    calls = primitive_spy(monkeypatch, owner(legacy))

    assert AdminAuthService()._verify_owner_password("owner", WRONG) is None
    assert calls == [(WRONG, legacy), (WRONG, _DUMMY_PASSWORD_HASH)]


@pytest.mark.parametrize("malformed", ["not-a-hash", "$2b$12$short", None])
def test_malformed_hash_invokes_only_one_dummy_bcrypt(monkeypatch, malformed):
    calls = primitive_spy(monkeypatch, owner(malformed))

    assert AdminAuthService()._verify_owner_password("owner", WRONG) is None
    assert calls == [(WRONG, _DUMMY_PASSWORD_HASH)]


def test_wrong_bcrypt_invokes_only_real_bcrypt_check_not_dummy(monkeypatch):
    calls = primitive_spy(monkeypatch, owner(BCRYPT_HASH))

    assert AdminAuthService()._verify_owner_password("owner", WRONG) is None
    assert calls == [(WRONG, BCRYPT_HASH)]


def test_successful_legacy_migrates_without_dummy_bcrypt(monkeypatch):
    legacy = hashlib.sha256(PASSWORD.encode()).hexdigest()
    user = owner(legacy)
    calls = primitive_spy(monkeypatch, user, accepted_hash=legacy)
    updates = []
    monkeypatch.setattr(service_module, "hash_password", lambda plain: "new-bcrypt")
    monkeypatch.setattr(
        service_module.db,
        "update_user_password",
        lambda username, hashed: updates.append((username, hashed)),
    )

    assert AdminAuthService()._verify_owner_password("owner", PASSWORD) is user
    assert calls == [(PASSWORD, legacy)]
    assert updates == [("owner", "new-bcrypt")]


@pytest.mark.parametrize(
    "stored_hash", [None, "not-a-hash", hashlib.sha256(PASSWORD.encode()).hexdigest()]
)
def test_public_failures_remain_generic_without_account_or_hash_disclosure(
    monkeypatch, stored_hash
):
    user = None if stored_hash is None else owner(stored_hash)
    primitive_spy(monkeypatch, user)
    auth = AdminAuthService(AllowingRepository())

    with pytest.raises(AdminError) as raised:
        auth.login("candidate-owner", WRONG, mfa_code=None, client_signal="test")

    error = raised.value
    assert error.status_code == 401
    assert error.code == "ADMIN_INVALID_CREDENTIALS"
    assert error.message == "Invalid credentials"
    public = f"{error.code} {error.message}"
    assert "candidate-owner" not in public
    assert str(stored_hash) not in public


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (BCRYPT_HASH, True),
        (BCRYPT_HASH.replace("$12$", "$03$"), False),
        (BCRYPT_HASH.replace("$2b$", "$2x$"), False),
        ("$2b$12$" + "A" * 53, False),
        ("$2b$12$short", False),
        (None, False),
    ],
)
def test_bcrypt_hash_classification_is_strict_and_total(value, expected):
    assert is_bcrypt_hash(value) is expected