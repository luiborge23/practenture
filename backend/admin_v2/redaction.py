"""Bounded, recursive secret redaction for Admin V2 audit and API logging.

The public function always returns a fresh, JSON-safe value.  It deliberately
handles only known-safe scalar types; arbitrary objects are represented by type
name and are never stringified with ``repr`` or ``str``.
"""

from __future__ import annotations

import math
import re
from heapq import nsmallest
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

REDACTED = "[REDACTED]"
CYCLE_MARKER = "[CYCLE]"
DEPTH_LIMIT_MARKER = "[MAX_DEPTH]"
ITEM_LIMIT_MARKER = "[MAX_ITEMS]"
STRING_LIMIT_MARKER = "[MAX_STRING_LENGTH]"

DEFAULT_MAX_DEPTH = 12
DEFAULT_MAX_ITEMS = 1_000
DEFAULT_MAX_STRING_LENGTH = 4_096

# Compact forms make matching insensitive to case and separators.  Suffix
# matching covers qualified labels such as ``oauthAccessToken`` and
# ``databasePassword`` without treating metadata such as ``tokenCount`` as a
# credential.
_SECRET_EXACT = frozenset(
    {
        "password",
        "currentpassword",
        "newpassword",
        "token",
        "tokens",
        "authorization",
        "cookie",
        "setcookie",
        "secret",
        "mfa",
        "mfacode",
        "mfarecoverycode",
        "mfarecoverycodes",
        "mfarecoveryseed",
        "mfastseed",
        "totpcode",
        "totpseed",
        "backupcode",
        "backupcodes",
        "recoverycode",
        "recoverycodes",
        "privatekey",
        "apikey",
    }
)
_SECRET_SUFFIXES = (
    "password",
    "passwordhash",
    "secret",
    "cookie",
    "accesstoken",
    "refreshtoken",
    "sessiontoken",
    "csrftoken",
    "resettoken",
    "invitationtoken",
    "authorization",
    "clientsecret",
    "signingsecret",
    "webhooksecret",
    "privatekey",
    "apikey",
    "mfacode",
    "mfaseed",
    "mfarecoverycode",
    "mfarecoverycodes",
    "mfarecoveryseed",
    "totpcode",
    "totpseed",
    "backupcode",
    "backupcodes",
    "recoverycode",
    "recoverycodes",
)
_HEADER_VALUE_RE = re.compile(
    r"^\s*(?:bearer\s+\S+|authorization\s*:\s*\S.+|(?:set-)?cookie\s*:\s*\S.*)$",
    re.IGNORECASE | re.DOTALL,
)
_SAFE_TYPE_CHARS_RE = re.compile(r"[^A-Za-z0-9_.-]")
_CAMEL_BOUNDARY_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NON_SECRET_METADATA_SUFFIXES = (
    "count",
    "createdat",
    "enabled",
    "expiresat",
    "expiration",
    "expiry",
    "id",
    "name",
    "type",
    "updatedat",
)


@dataclass
class _State:
    remaining_items: int
    max_depth: int
    max_string_length: int
    active_container_ids: set[int]


def redact_secrets(
    value: Any,
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_items: int = DEFAULT_MAX_ITEMS,
    max_string_length: int = DEFAULT_MAX_STRING_LENGTH,
) -> Any:
    """Return a deterministic, JSON-safe, recursively redacted copy of ``value``.

    ``max_items`` is a global traversal budget rather than a per-container
    limit, preventing a broad tree from multiplying allocations. Containers
    beyond either bound are replaced by stable markers. Secret-valued fields
    are replaced as a whole, so their length and structure are not retained.
    """

    _validate_bound("max_depth", max_depth)
    _validate_bound("max_items", max_items)
    _validate_bound("max_string_length", max_string_length)
    state = _State(max_items, max_depth, max_string_length, set())
    return _sanitize(value, state, depth=0)


def _validate_bound(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _compact_key(key: str) -> str:
    return "".join(character for character in key.casefold() if character.isalnum())


def _key_words(key: str) -> tuple[str, ...]:
    separated = _CAMEL_BOUNDARY_RE.sub(" ", key)
    return tuple(part.casefold() for part in re.findall(r"[A-Za-z0-9]+", separated))


def _is_secret_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    compact = _compact_key(key)
    if compact in _SECRET_EXACT or any(
        compact.endswith(suffix) for suffix in _SECRET_SUFFIXES
    ):
        return True
    # Match qualified/header/confirmation forms while explicitly sparing
    # clearly non-secret metrics and metadata (for example tokenCount).
    if compact.endswith(_NON_SECRET_METADATA_SUFFIXES):
        return False
    words = set(_key_words(key))
    if words & {"password", "secret", "token", "tokens", "authorization", "cookie"}:
        return True
    if words & {"mfa", "totp"} and words & {"code", "codes", "seed"}:
        return True
    if words & {"backup", "recovery"} and words & {"code", "codes"}:
        return True
    return ({"private", "key"} <= words) or ({"api", "key"} <= words)


def _is_token_like_string(value: str) -> bool:
    return bool(_HEADER_VALUE_RE.fullmatch(value))


def _safe_type_name(value: Any) -> str:
    # Reading the actual type avoids arbitrary __getattribute__, __str__, and
    # __repr__ methods on the value. Limit even hostile dynamically named types.
    try:
        name = object.__getattribute__(type(value), "__name__")
    except Exception:
        name = "object"
    if not isinstance(name, str):
        name = "object"
    name = _SAFE_TYPE_CHARS_RE.sub("_", name)[:64] or "object"
    return name


def _unsupported_marker(value: Any) -> str:
    return f"[UNSUPPORTED:{_safe_type_name(value)}]"


def _safe_string(value: str, state: _State) -> str:
    if _is_token_like_string(value):
        return REDACTED
    if len(value) > state.max_string_length:
        return STRING_LIMIT_MARKER
    return value


def _safe_key(key: Any, state: _State) -> str:
    if isinstance(key, str):
        return _safe_string(key, state)
    if key is None:
        return "null"
    if isinstance(key, bool):
        return "true" if key else "false"
    if isinstance(key, int):
        return str(key)
    if isinstance(key, float):
        return key.hex() if math.isfinite(key) else f"[{key.__class__.__name__.upper()}]"
    if isinstance(key, (datetime, date, time, UUID, Decimal)):
        return str(key)
    return _unsupported_marker(key)


def _consume_item(state: _State) -> bool:
    if state.remaining_items <= 0:
        return False
    state.remaining_items -= 1
    return True


def _sanitize(value: Any, state: _State, depth: int) -> Any:
    if depth >= state.max_depth:
        return DEPTH_LIMIT_MARKER

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        # Native JSON integers have no size bound. Avoid returning an integer
        # that could force a serializer to allocate an attacker-sized string.
        if value.bit_length() > state.max_string_length * 4:
            return STRING_LIMIT_MARKER
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return f"[{value.__class__.__name__.upper()}]"
    if isinstance(value, str):
        return _safe_string(value, state)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return _safe_string(str(value), state)
    if isinstance(value, Enum):
        return _sanitize(value.value, state, depth)

    if isinstance(value, dict):
        return _sanitize_dict(value, state, depth)
    if isinstance(value, (list, tuple)):
        return _sanitize_sequence(value, state, depth)
    if isinstance(value, (set, frozenset)):
        return _sanitize_set(value, state, depth)

    return _unsupported_marker(value)


def _enter_container(value: Any, state: _State) -> bool:
    identity = id(value)
    if identity in state.active_container_ids:
        return False
    state.active_container_ids.add(identity)
    return True


def _leave_container(value: Any, state: _State) -> None:
    state.active_container_ids.remove(id(value))


def _truncation_key(result: dict[str, Any]) -> str:
    key = "__truncated__"
    suffix = 2
    while key in result:
        key = f"__truncated_{suffix}__"
        suffix += 1
    return key


def _sanitize_dict(value: dict[Any, Any], state: _State, depth: int) -> Any:
    if not _enter_container(value, state):
        return CYCLE_MARKER
    try:
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if not _consume_item(state):
                result[_truncation_key(result)] = ITEM_LIMIT_MARKER
                break
            key = _safe_key(raw_key, state)
            # Preserve every secret field as the same marker and do not inspect
            # its value, which prevents retaining collection shape or length.
            sanitized = (
                REDACTED
                if _is_secret_key(raw_key)
                else _sanitize(raw_value, state, depth + 1)
            )
            # JSON object keys must be unique. Preserve the first value rather
            # than silently replacing it after safe key normalization.
            if key in result:
                collision_key = f"{key}#2"
                index = 3
                while collision_key in result:
                    collision_key = f"{key}#{index}"
                    index += 1
                key = collision_key
            result[key] = sanitized
        return result
    finally:
        _leave_container(value, state)


def _sanitize_sequence(value: list[Any] | tuple[Any, ...], state: _State, depth: int) -> Any:
    if not _enter_container(value, state):
        return CYCLE_MARKER
    try:
        result: list[Any] = []
        for item in value:
            if not _consume_item(state):
                result.append(ITEM_LIMIT_MARKER)
                break
            result.append(_sanitize(item, state, depth + 1))
        return result
    finally:
        _leave_container(value, state)


def _stable_set_key(value: Any, depth: int = 0) -> tuple[Any, ...]:
    """Build a bounded key without invoking user-controlled stringification."""

    if depth >= 4:
        return (99, _safe_type_name(value))
    if value is None:
        return (0, "")
    if isinstance(value, bool):
        return (1, value)
    if isinstance(value, int):
        return (2, value)
    if isinstance(value, float):
        return (3, value.hex())
    if isinstance(value, str):
        return (4, value)
    if isinstance(value, (datetime, date, time)):
        return (5, value.isoformat())
    if isinstance(value, UUID):
        return (6, str(value))
    if isinstance(value, Decimal):
        return (7, str(value))
    if isinstance(value, tuple):
        return (8, tuple(_stable_set_key(item, depth + 1) for item in value[:16]))
    if isinstance(value, frozenset):
        children = nsmallest(
            16, (_stable_set_key(item, depth + 1) for item in value)
        )
        return (9, tuple(children))
    return (99, _safe_type_name(value))


def _sanitize_set(value: set[Any] | frozenset[Any], state: _State, depth: int) -> Any:
    if not _enter_container(value, state):
        return CYCLE_MARKER
    try:
        result: list[Any] = []
        # Select at most one item beyond the remaining budget. Unlike sorting
        # the full set, nsmallest bounds temporary allocation for hostile sets.
        # The output remains a list because JSON has no set or tuple type.
        selected = nsmallest(
            min(len(value), state.remaining_items + 1),
            value,
            key=_stable_set_key,
        )
        for item in selected:
            if not _consume_item(state):
                result.append(ITEM_LIMIT_MARKER)
                break
            result.append(_sanitize(item, state, depth + 1))
        return result
    finally:
        _leave_container(value, state)


__all__ = [
    "CYCLE_MARKER",
    "DEPTH_LIMIT_MARKER",
    "ITEM_LIMIT_MARKER",
    "REDACTED",
    "STRING_LIMIT_MARKER",
    "redact_secrets",
]
