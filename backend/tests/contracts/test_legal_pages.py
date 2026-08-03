"""Contracts for dedicated public legal and support documents."""

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_public_documents_are_distinct_html_pages() -> None:
    expected = {
        "/privacy": ("Privacy Policy", "Information we collect"),
        "/terms": ("Terms of Service", "Acceptable use"),
        "/support": ("Support", "What to include"),
    }
    bodies: list[str] = []
    for path, markers in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["cache-control"] == "public, max-age=300"
        assert response.headers["x-robots-tag"] == "index, follow"
        assert response.text.startswith("<!doctype html>")
        assert all(marker in response.text for marker in markers)
        assert "August 2, 2026" in response.text
        bodies.append(response.text)
    assert len(set(bodies)) == 3


def test_documents_cross_link_and_publish_support_contact() -> None:
    for path in ("/privacy", "/terms", "/support"):
        body = client.get(path).text
        assert 'href="/privacy"' in body
        assert 'href="/terms"' in body
        assert 'href="/support"' in body
        assert "platform-support@practenture.com" in body
    assert 'href="mailto:platform-support@practenture.com"' in client.get(
        "/support"
    ).text


def test_documents_do_not_load_tracking_or_third_party_assets() -> None:
    for path in ("/privacy", "/terms", "/support"):
        body = client.get(path).text
        assert "<script" not in body
        assert "https://" not in body
        assert "http://" not in body
