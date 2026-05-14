"""Tests for the Flask server health endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.server import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    with app.test_client() as c:
        yield c


class TestHealthEndpoint:
    """Tests for POST /api/health."""

    def test_health_success(self, client):
        """POST with valid config returns 200 with ok=True."""
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.latency_ms = 5.0
        mock_result.model = "llama3.2"
        mock_result.error = None

        with patch("app.server.OllamaProvider.health", return_value=mock_result):
            resp = client.post(
                "/api/health",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["latency_ms"] == 5.0
        assert data["model"] == "llama3.2"
        assert data["error"] is None

    def test_health_failure(self, client):
        """POST with valid config but provider reports failure."""
        mock_result = MagicMock()
        mock_result.ok = False
        mock_result.latency_ms = 100.0
        mock_result.model = "llama3.2"
        mock_result.error = "Connection refused"

        with patch("app.server.OllamaProvider.health", return_value=mock_result):
            resp = client.post(
                "/api/health",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is False
        assert data["latency_ms"] == 100.0
        assert data["model"] == "llama3.2"
        assert data["error"] == "Connection refused"

    def test_health_invalid_json(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/health",
            data="not json at all",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "Invalid JSON body"

    def test_health_missing_fields(self, client):
        """POST with empty JSON body returns 400."""
        resp = client.post("/api/health", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "base_url and model are required"

    def test_health_missing_base_url(self, client):
        """POST missing base_url returns 400."""
        resp = client.post("/api/health", json={"model": "llama3.2"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "base_url and model are required"

    def test_health_missing_model(self, client):
        """POST missing model returns 400."""
        resp = client.post(
            "/api/health",
            json={"base_url": "http://localhost:11434"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "base_url and model are required"

    # ------------------------------------------------------------------
    # Edge cases — input validation
    # ------------------------------------------------------------------

    def test_health_malformed_json_with_json_content_type(self, client):
        """POST with malformed JSON but correct content-type returns 400.

        When Content-Type is application/json but body is not valid
        JSON, ``request.get_json(silent=True)`` returns ``None``
        triggering the second guard clause.
        """
        resp = client.post(
            "/api/health",
            data="not valid json at all",
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "Invalid JSON body"

    def test_health_whitespace_base_url(self, client):
        """POST with whitespace-only base_url returns 400."""
        resp = client.post(
            "/api/health",
            json={"base_url": "   ", "model": "llama3.2"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "base_url and model are required"

    def test_health_whitespace_model(self, client):
        """POST with whitespace-only model returns 400."""
        resp = client.post(
            "/api/health",
            json={"base_url": "http://localhost:11434", "model": "   "},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "base_url and model are required"

    # ------------------------------------------------------------------
    # Edge cases — api_key handling
    # ------------------------------------------------------------------

    def test_health_empty_string_api_key(self, client):
        """POST with empty string api_key succeeds (treated as None)."""
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.latency_ms = 5.0
        mock_result.model = "llama3.2"
        mock_result.error = None

        with patch("app.server.OllamaProvider.health", return_value=mock_result):
            resp = client.post(
                "/api/health",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                    "api_key": "",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_health_null_api_key(self, client):
        """POST with null api_key succeeds (treated as None)."""
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.latency_ms = 5.0
        mock_result.model = "llama3.2"
        mock_result.error = None

        with patch("app.server.OllamaProvider.health", return_value=mock_result):
            resp = client.post(
                "/api/health",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                    "api_key": None,
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    # ------------------------------------------------------------------
    # Edge cases — body structure
    # ------------------------------------------------------------------

    def test_health_extra_unexpected_fields(self, client):
        """POST with unexpected fields ignores them and succeeds."""
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.latency_ms = 5.0
        mock_result.model = "llama3.2"
        mock_result.error = None

        with patch("app.server.OllamaProvider.health", return_value=mock_result):
            resp = client.post(
                "/api/health",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                    "extra_field": "should_be_ignored",
                    "another_one": 42,
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_health_base_url_with_trailing_slash(self, client):
        """POST with trailing slash in base_url succeeds after stripping.

        The :class:`OllamaProvider` constructor strips trailing
        slashes via ``rstrip("/")``.
        """
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.latency_ms = 5.0
        mock_result.model = "llama3.2"
        mock_result.error = None

        with patch("app.server.OllamaProvider.health", return_value=mock_result):
            resp = client.post(
                "/api/health",
                json={
                    "base_url": "http://localhost:11434/",
                    "model": "llama3.2",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    # ------------------------------------------------------------------
    # Robustness — unexpected exceptions
    # ------------------------------------------------------------------

    def test_health_provider_raises_unexpected_exception(self, client):
        """When health() raises, the endpoint returns 500.

        Although :meth:`OllamaProvider.health` guarantees it never
        raises (it catches all exceptions internally), this test
        verifies the endpoint degrades gracefully if the contract is
        broken.
        """
        with patch(
            "app.server.OllamaProvider.health",
            side_effect=RuntimeError("unexpected failure"),
        ):
            resp = client.post(
                "/api/health",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

        assert resp.status_code == 500
