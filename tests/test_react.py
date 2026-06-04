"""Tests for the React SPA route blueprint.

Verifies that the React SPA is served at ``/`` and that client-side
routing paths fall through to ``index.html``, while API paths remain
uncaught (404).
"""

from __future__ import annotations

import pytest

from app.server import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    with app.test_client() as c:
        yield c


class TestReactSpaRoutes:
    """Tests for the React SPA blueprint serving at ``/``."""

    def test_index_returns_html(self, client):
        """GET / returns HTML (not a 404 or JSON)."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"

    def test_index_contains_react_shell(self, client):
        """GET / response contains React SPA shell (div#root)."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b'<div id="root">' in resp.data

    def test_game_returns_html(self, client):
        """GET /game returns HTML for client-side routing."""
        resp = client.get("/game")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    def test_character_returns_html(self, client):
        """GET /character returns HTML for client-side routing."""
        resp = client.get("/character")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    def test_api_path_returns_404(self, client):
        """GET /api/doesnotexist returns 404 (not caught by catch-all)."""
        resp = client.get("/api/doesnotexist")
        assert resp.status_code == 404

    def test_nonexistent_asset_returns_index_html(self, client):
        """GET /assets/some-file-that-doesnt-exist returns index.html
        (catch-all for client-side routing when the file doesn't exist)."""
        resp = client.get("/assets/some-file-that-doesnt-exist")
        # Should return index.html (200) with the React shell
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    def test_existing_asset_returns_file(self, client):
        """GET /assets/index-*.js returns the actual JS asset file."""
        resp = client.get("/assets/index-Bd5gkdAP.js")
        assert resp.status_code == 200
        assert resp.mimetype in (
            "application/javascript",
            "text/javascript",
            "text/plain; charset=utf-8",
        )

    def test_nested_path_returns_html(self, client):
        """GET /some/nested/path returns HTML for client-side routing."""
        resp = client.get("/some/nested/path")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    def test_vite_svg_exists(self, client):
        """GET /vite.svg returns the Vite SVG favicon."""
        resp = client.get("/vite.svg")
        assert resp.status_code == 200
        assert "image/svg+xml" in resp.mimetype

    def test_nonexistent_vite_svg_returns_index(self, client):
        """GET /nonexistent.svg returns index.html (catch-all for client-
        side routing when the file doesn't exist)."""
        resp = client.get("/nonexistent.svg")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data
