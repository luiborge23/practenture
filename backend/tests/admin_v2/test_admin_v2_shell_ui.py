"""Focused contracts for the additive Admin Console V2 browser shell."""
from pathlib import Path

from fastapi.testclient import TestClient

from main import app

BACKEND = Path(__file__).resolve().parents[2]


def test_shell_references_only_local_versioned_assets_and_is_not_cached():
    with TestClient(app) as client:
        response = client.get("/admin-v2")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert 'href="/static/admin_v2/admin-v2.css?v=2"' in response.text
    assert 'src="/static/admin_v2/admin-v2.js?v=4"' in response.text
    assert "http://" not in response.text
    assert "https://" not in response.text
    assert "localStorage" not in response.text


def test_shell_assets_exist_and_are_served_with_expected_types():
    expected = {
        "admin-v2.css": "text/css",
        "admin-v2.js": "javascript",
    }
    with TestClient(app) as client:
        for name, media_type in expected.items():
            path = BACKEND / "static" / "admin_v2" / name
            assert path.is_file(), name
            response = client.get(f"/static/admin_v2/{name}")
            assert response.status_code == 200
            assert media_type in response.headers["content-type"]


def test_operations_view_uses_the_canonical_operations_api_namespace():
    script = (BACKEND / "static" / "admin_v2" / "admin-v2.js").read_text(encoding="utf-8")
    for path in ("/operations/health", "/operations/backups", "/operations/restore-drills"):
        assert f'request("{path}")' in script
    for obsolete_path in ('request("/health")', 'request("/backups")', 'request("/restore-drills")'):
        assert obsolete_path not in script


def test_shell_has_accessible_landmarks_and_no_inline_executable_code():
    html = (BACKEND / "templates" / "admin_v2.html").read_text(encoding="utf-8")
    for marker in ("<header", "<nav", "<main", "<aside", "<form", "aria-live="):
        assert marker in html
    assert "<script>" not in html
    assert "style=" not in html
    assert "localStorage" not in html
    assert "sessionStorage" not in html
    assert "Delete all" not in html


def test_legacy_admin_surface_remains_available():
    with TestClient(app) as client:
        legacy = client.get("/admin")
        owner = client.get("/owner", follow_redirects=False)
    assert legacy.status_code == 200
    assert owner.status_code == 308
    assert owner.headers["location"] == "/admin"
