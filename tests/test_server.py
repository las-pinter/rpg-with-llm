"""Tests for the Flask server — health, save/load, and game endpoints."""

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
        """POST with malformed JSON but correct content-type returns 400."""
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
        """POST with trailing slash in base_url succeeds after stripping."""
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
        """When health() raises, the endpoint returns 500."""
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


# ---------------------------------------------------------------------------
# Game Turn Endpoint
# ---------------------------------------------------------------------------


class TestGameTurnEndpoint:
    """Tests for POST /api/turn."""

    def test_turn_success(self, client):
        """POST with valid input returns proper response structure."""
        resp = client.post(
            "/api/turn",
            json={"input": "I look around the room."},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "narrative" in data
        assert "state_changes" in data
        assert "tool_results" in data
        assert "turn_count" in data
        assert isinstance(data["narrative"], str)
        assert len(data["narrative"]) > 0

    def test_turn_empty_input(self, client):
        """POST with empty input returns 400."""
        resp = client.post("/api/turn", json={"input": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_turn_missing_input(self, client):
        """POST without input field returns 400."""
        resp = client.post("/api/turn", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_turn_non_json_body(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/turn",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "ok" in data

    def test_turn_increments_turn_count(self, client):
        """Each turn should increase turn_count."""
        resp1 = client.post("/api/turn", json={"input": "First turn"})
        resp2 = client.post("/api/turn", json={"input": "Second turn"})
        data1 = resp1.get_json()
        data2 = resp2.get_json()
        # Each request creates a fresh DungeonMaster, so turn counts
        # should be independent (each starts at 1)
        assert data1["turn_count"] == 1
        assert data2["turn_count"] == 1

    def test_turn_with_provider_config(self, client):
        """POST with provider config should use OllamaProvider."""
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.latency_ms = 5.0
        mock_result.model = "llama3.2"
        mock_result.error = None

        with patch("app.server.OllamaProvider") as mock_provider_cls:
            mock_instance = MagicMock()
            mock_provider_cls.return_value = mock_instance
            mock_instance.call.return_value = {
                "content": "<narrative>Test narrative.</narrative>",
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }

            resp = client.post(
                "/api/turn",
                json={
                    "input": "Hello",
                    "provider": {
                        "base_url": "http://localhost:11434",
                        "model": "llama3.2",
                    },
                },
            )

            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            mock_provider_cls.assert_called_once()

    def test_turn_with_state(self, client):
        """POST with state dict should restore world state."""
        resp = client.post(
            "/api/turn",
            json={
                "input": "I explore.",
                "state": {
                    "current_location": "dark_forest",
                    "turn_count": 5,
                    "locations": {},
                    "quests": {},
                    "faction_standings": {},
                    "active_npcs": {},
                    "inventory": [],
                    "dm_notes": {"plot_threads": [], "secrets": [], "future_plans": []},
                },
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True


# ---------------------------------------------------------------------------
# Game Stream Endpoint
# ---------------------------------------------------------------------------


class TestGameStreamEndpoint:
    """Tests for GET /api/game/stream."""

    def test_stream_without_input_returns_400(self, client):
        """GET without input query param returns 400."""
        resp = client.get("/api/game/stream")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_stream_with_input_returns_sse(self, client):
        """GET with input returns SSE response."""
        resp = client.get("/api/game/stream?input=Hello")
        assert resp.status_code == 200
        assert resp.mimetype == "text/event-stream"
        data = resp.get_data(as_text=True)
        # Should have SSE events
        assert "data:" in data
        assert "narrative" in data
        assert "done" in data

    def test_stream_sse_format(self, client):
        """SSE response should have proper event format."""
        resp = client.get("/api/game/stream?input=Look+around")
        raw = resp.get_data(as_text=True)
        lines = [line for line in raw.split("\n") if line.strip()]
        assert len(lines) > 0
        for line in lines:
            assert line.startswith("data: "), f"Bad line: {line!r}"

    def test_stream_includes_narrative(self, client):
        """SSE response should include narrative event."""
        resp = client.get("/api/game/stream?input=Hello")
        data = resp.get_data(as_text=True)
        assert '"type": "narrative"' in data

    def test_stream_includes_done_event(self, client):
        """SSE response should include a done event."""
        resp = client.get("/api/game/stream?input=Hello")
        data = resp.get_data(as_text=True)
        assert '"type": "done"' in data
        assert '"turn_count"' in data
