"""Stable Admin V2 error contract."""

from __future__ import annotations

from typing import Any
import secrets


class AdminError(Exception):
    """Typed failure rendered by the Admin V2 exception handler."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def error_envelope(
    code: str,
    message: str,
    request_id: str | None,
    field_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "requestId": request_id or f"req_{secrets.token_urlsafe(18)}",
            "fieldErrors": field_errors or [],
        }
    }
