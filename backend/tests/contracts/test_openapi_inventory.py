"""Frozen inventory tests for the complete first-party HTTP API surface."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from fastapi.routing import APIRoute

from main import app

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
MANIFEST_PATH = Path(__file__).with_name("openapi_route_manifest.json")


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text())


def _normalize_openapi() -> list[dict]:
    schema = app.openapi()
    operations: list[dict] = []
    for path, path_item in sorted(schema["paths"].items()):
        for method, operation in sorted(path_item.items()):
            if method.upper() not in HTTP_METHODS:
                continue
            request_body = operation.get("requestBody", {})
            request_content = request_body.get("content", {})
            request_schema = request_content.get("application/json", {}).get("schema")
            responses = {}
            for status, response in sorted(operation.get("responses", {}).items()):
                content = response.get("content", {})
                json_schema = content.get("application/json", {}).get("schema")
                first_schema = next(
                    (media.get("schema") for media in content.values() if media.get("schema")),
                    None,
                )
                responses[status] = (
                    json_schema
                    or first_schema
                    or ({} if "application/json" in content else None)
                )
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "operationId": operation.get("operationId"),
                    "security": operation.get("security", []),
                    "requestBodyRequired": request_body.get("required", False),
                    "requestSchema": request_schema,
                    "responses": responses,
                }
            )
    return operations


def _untyped_success_responses(operations: list[dict]) -> list[dict]:
    gaps: list[dict] = []
    for operation in operations:
        success_schemas = [
            schema
            for status, schema in operation["responses"].items()
            if status.startswith("2") and status != "204"
        ]
        if not success_schemas or all(schema in (None, {}) for schema in success_schemas):
            gaps.append({"method": operation["method"], "path": operation["path"]})
    return gaps


def test_openapi_exactly_matches_reviewed_route_manifest() -> None:
    """Any route/schema/security drift requires an explicit manifest review."""
    manifest = _manifest()
    actual = _normalize_openapi()
    assert len(actual) == manifest["operationCount"]
    assert actual == manifest["operations"]


def test_no_duplicate_runtime_method_path_routes() -> None:
    """FastAPI otherwise silently resolves colliding routes by registration order."""
    keys: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted((route.methods or set()) & HTTP_METHODS):
            keys.append((method, route.path))
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    assert duplicates == []


def test_every_openapi_operation_has_a_unique_operation_id() -> None:
    operations = _normalize_openapi()
    operation_ids = [operation["operationId"] for operation in operations]
    assert None not in operation_ids
    duplicates = sorted(
        operation_id
        for operation_id, count in Counter(operation_ids).items()
        if count > 1
    )
    assert duplicates == []


def test_untyped_success_response_debt_cannot_grow_silently() -> None:
    """Existing raw-dict/Response routes are explicit debt for typed-contract tasks."""
    manifest = _manifest()
    assert _untyped_success_responses(_normalize_openapi()) == manifest[
        "knownUntypedSuccessResponses"
    ]


def test_direct_swift_client_success_responses_are_typed() -> None:
    """Every body-bearing route called by NetworkService/AuthManager is typed."""
    direct_swift_routes = {
        ("POST", "/api/auth/refresh"),
        ("POST", "/api/sessions"),
        ("GET", "/api/sessions/{code}"),
        ("PUT", "/api/sessions/{code}/join"),
        ("GET", "/api/sessions/{code}/status"),
        ("POST", "/api/sessions/{code}/end"),
        ("POST", "/api/sessions/{code}/start"),
        ("POST", "/api/sessions/{code}/submit_decision"),
        ("GET", "/api/sessions/{code}/decisions/{round_num}"),
        ("POST", "/api/sessions/{code}/process_round"),
        ("GET", "/api/sessions/{code}/results"),
        ("GET", "/api/sessions/{code}/leaderboard"),
        ("POST", "/api/sessions/{code}/announcements"),
        ("GET", "/api/sessions/{code}/announcements"),
        ("GET", "/api/dashboard/sessions"),
        ("GET", "/api/sessions/{code}/export/grades"),
        ("GET", "/api/sessions/{code}/export/leaderboard"),
        ("GET", "/api/health"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/register"),
        ("GET", "/api/auth/professor-status"),
        ("POST", "/api/professor/redeem"),
        ("POST", "/api/auth/mfa/setup"),
        ("POST", "/api/auth/mfa/verify"),
        ("POST", "/api/auth/mfa/disable"),
        ("GET", "/api/auth/mfa/status"),
        ("POST", "/api/professor/change-password"),
        ("POST", "/api/auth/forgot-password"),
        ("POST", "/api/auth/reset-password"),
        ("POST", "/api/classes/join"),
    }
    operations = {
        (item["method"], item["path"]): item for item in _normalize_openapi()
    }
    assert direct_swift_routes <= operations.keys()
    debt = {
        (item["method"], item["path"])
        for item in _untyped_success_responses(_normalize_openapi())
    }
    assert direct_swift_routes.isdisjoint(debt)


def test_csv_exports_publish_string_response_schemas() -> None:
    operations = {
        (item["method"], item["path"]): item for item in _normalize_openapi()
    }
    for path in (
        "/api/sessions/{code}/export/grades",
        "/api/sessions/{code}/export/leaderboard",
    ):
        assert operations[("GET", path)]["responses"]["200"] == {"type": "string"}


def test_manifest_covers_all_operation_contract_dimensions() -> None:
    for operation in _manifest()["operations"]:
        assert set(operation) == {
            "method",
            "path",
            "operationId",
            "security",
            "requestBodyRequired",
            "requestSchema",
            "responses",
        }
        assert operation["responses"], operation
