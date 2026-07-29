"""Security contracts for recursive Admin V2 log/audit redaction."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from admin_v2.redaction import (
    CYCLE_MARKER,
    DEPTH_LIMIT_MARKER,
    ITEM_LIMIT_MARKER,
    REDACTED,
    STRING_LIMIT_MARKER,
    redact_secrets,
)


@pytest.mark.parametrize(
    ("key", "secret"),
    [
        ("password", "password-value-never-log"),
        ("current-password", "current-password-never-log"),
        ("new_password", "new-password-never-log"),
        ("accessToken", "access-token-never-log"),
        ("REFRESH_TOKEN", "refresh-token-never-log"),
        ("session.token", "session-token-never-log"),
        ("csrf-token", "csrf-token-never-log"),
        ("resetToken", "reset-token-never-log"),
        ("invitation_token", "invitation-token-never-log"),
        ("Authorization", "authorization-never-log"),
        ("set-cookie", "cookie-never-log"),
        ("clientSecret", "client-secret-never-log"),
        ("mfa_seed", "mfa-seed-never-log"),
        ("TOTPCode", "totp-code-never-log"),
        ("backup-code", "backup-code-never-log"),
        ("recovery_code", "recovery-code-never-log"),
        ("privateKey", "private-key-never-log"),
        ("api-key", "api-key-never-log"),
        ("token", "generic-token-never-log"),
    ],
)
def test_secret_key_formats_are_redacted_recursively(key: str, secret: str):
    payload = {"safe": [{"deeper": ({key: secret},)}]}

    result = redact_secrets(payload)
    serialized = json.dumps(result)

    assert result["safe"][0]["deeper"][0][key] == REDACTED
    assert secret not in serialized


@pytest.mark.parametrize(
    "value",
    [
        "Bearer header-token-never-log",
        "bearer lower-case-token-never-log",
        "Authorization: Basic credentials-never-log",
        "Cookie: session=cookie-value-never-log",
        "Set-Cookie: refresh=cookie-value-never-log; HttpOnly",
    ],
)
def test_token_like_header_and_cookie_strings_are_redacted_without_secret_key(value: str):
    result = redact_secrets({"nested": [{"headerValue": value}]})

    assert result == {"nested": [{"headerValue": REDACTED}]}
    assert value not in json.dumps(result)


@pytest.mark.parametrize(
    "key",
    [
        "tokenCount",
        "token_count",
        "accessTokenExpiresAt",
        "passwordUpdatedAt",
        "sessionId",
        "invitationId",
        "recoveryAttempts",
        "apiKeyCount",
    ],
)
def test_clear_metrics_ids_and_metadata_are_not_false_positive_secrets(key: str):
    assert redact_secrets({key: 7}) == {key: 7}


def test_safe_values_and_dict_order_are_preserved_as_json_safe_values():
    payload = {
        "id": "usr_123",
        "timestamp": datetime(2026, 7, 28, 12, 30, tzinfo=timezone.utc),
        "day": date(2026, 7, 28),
        "clock": time(12, 30),
        "uuid": UUID("12345678-1234-5678-1234-567812345678"),
        "decimal": Decimal("12.50"),
        "enabled": True,
        "attempts": 3,
        "ratio": 1.5,
        "missing": None,
        "message": "ordinary safe text",
    }

    result = redact_secrets(payload)

    assert list(result) == list(payload)
    assert result == {
        "id": "usr_123",
        "timestamp": "2026-07-28T12:30:00+00:00",
        "day": "2026-07-28",
        "clock": "12:30:00",
        "uuid": "12345678-1234-5678-1234-567812345678",
        "decimal": "12.50",
        "enabled": True,
        "attempts": 3,
        "ratio": 1.5,
        "missing": None,
        "message": "ordinary safe text",
    }
    json.dumps(result)


def test_input_is_not_mutated_and_tuple_and_set_are_deterministic_lists():
    payload = {
        "items": ["first", {"password": "do-not-mutate"}],
        "tuple": (3, 1, 2),
        "set": {"z", "a", "m"},
    }
    original_items = list(payload["items"])
    original_nested = dict(payload["items"][1])
    original_tuple = payload["tuple"]
    original_set = set(payload["set"])

    first = redact_secrets(payload)
    second = redact_secrets(payload)

    assert first == second
    assert first["tuple"] == [3, 1, 2]
    assert first["set"] == ["a", "m", "z"]
    assert payload["items"] == original_items
    assert payload["items"][1] == original_nested
    assert payload["tuple"] == original_tuple
    assert payload["set"] == original_set


def test_secret_collections_are_replaced_whole_without_traversal_or_shape_leak():
    secret = ["prefix-never-log", {"nested": "suffix-never-log"}]

    result = redact_secrets({"refreshToken": secret})

    assert result == {"refreshToken": REDACTED}
    assert "prefix-never-log" not in json.dumps(result)
    assert "suffix-never-log" not in json.dumps(result)


def test_cycles_terminate_without_treating_shared_noncyclic_values_as_cycles():
    cycle: list[object] = ["safe"]
    cycle.append(cycle)
    shared = {"id": "shared-id"}

    result = redact_secrets({"cycle": cycle, "left": shared, "right": shared})

    assert result["cycle"] == ["safe", CYCLE_MARKER]
    assert result["left"] == {"id": "shared-id"}
    assert result["right"] == {"id": "shared-id"}
    json.dumps(result)


def test_max_depth_bounds_hostile_nesting_but_still_redacts_secret_at_boundary():
    payload = {"level1": {"level2": {"password": "boundary-secret-never-log"}}}

    result = redact_secrets(payload, max_depth=2)

    assert result == {"level1": {"level2": DEPTH_LIMIT_MARKER}}
    assert "boundary-secret-never-log" not in json.dumps(result)


def test_max_items_bounds_wide_payload_without_copying_the_remainder():
    payload: dict[str, object] = {f"field{i}": i for i in range(100)}
    payload["password"] = "unvisited-secret-never-log"

    result = redact_secrets(payload, max_items=3)

    assert result == {
        "field0": 0,
        "field1": 1,
        "field2": 2,
        "__truncated__": ITEM_LIMIT_MARKER,
    }
    assert len(result) == 4
    assert "unvisited-secret-never-log" not in json.dumps(result)


def test_oversized_scalars_are_replaced_whole_to_bound_serialized_output():
    result = redact_secrets(
        {"text": "x" * 20, "number": 10**100},
        max_string_length=8,
    )

    assert result == {
        "text": STRING_LIMIT_MARKER,
        "number": STRING_LIMIT_MARKER,
    }


class DangerousObject:
    def __repr__(self) -> str:
        raise AssertionError("repr must never be called because it may expose secrets")


def test_unknown_objects_use_a_bounded_type_only_marker_without_repr():
    result = redact_secrets({"value": DangerousObject()})

    assert result == {"value": "[UNSUPPORTED:DangerousObject]"}
    json.dumps(result)


@pytest.mark.parametrize("invalid", [-1, True, 1.5, "10", None])
def test_bounds_reject_invalid_values(invalid):
    with pytest.raises((TypeError, ValueError)):
        redact_secrets({}, max_depth=invalid)
    with pytest.raises((TypeError, ValueError)):
        redact_secrets({}, max_items=invalid)
