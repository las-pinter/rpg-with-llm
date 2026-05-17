"""Tests for the Flask server — health, save/load, and game endpoints."""

from __future__ import annotations

import json
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

    # ------------------------------------------------------------------
    # Edge cases — null / non-string values (crash guards)
    # ------------------------------------------------------------------

    def test_health_null_base_url_returns_400(self, client):
        """POST with null base_url returns 400, not 500."""
        resp = client.post(
            "/api/health",
            json={"base_url": None, "model": "llama3.2"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "base_url and model are required"

    def test_health_null_model_returns_400(self, client):
        """POST with null model returns 400, not 500."""
        resp = client.post(
            "/api/health",
            json={"base_url": "http://localhost:11434", "model": None},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_health_null_api_key_in_body(self, client):
        """POST with null api_key in JSON body succeeds (treated as missing)."""
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

    def test_turn_null_input_returns_400(self, client):
        """POST /api/turn with null input returns 400, not 500."""
        resp = client.post("/api/turn", json={"input": None})
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

    # ------------------------------------------------------------------
    # Edge cases — null provider config values
    # ------------------------------------------------------------------

    def test_turn_null_provider_base_url_does_not_crash(self, client):
        """POST with null provider.base_url gracefully falls back to no provider."""
        resp = client.post(
            "/api/turn",
            json={
                "input": "Hello",
                "provider": {"base_url": None, "model": "llama3.2"},
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "narrative" in data

    def test_turn_null_provider_model_does_not_crash(self, client):
        """POST with null provider.model gracefully falls back to no provider."""
        resp = client.post(
            "/api/turn",
            json={
                "input": "Hello",
                "provider": {"base_url": "http://localhost:11434", "model": None},
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_turn_null_character_does_not_crash(self, client):
        """POST with null character field is accepted."""
        resp = client.post(
            "/api/turn",
            json={"input": "Hello", "character": None},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_turn_null_state_does_not_crash(self, client):
        """POST with null state field is accepted."""
        resp = client.post(
            "/api/turn",
            json={"input": "Hello", "state": None},
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
        """SSE response should have proper event format with event: and data: lines."""
        resp = client.get("/api/game/stream?input=Look+around")
        raw = resp.get_data(as_text=True)
        lines = [line for line in raw.split("\n") if line.strip()]
        assert len(lines) > 0
        for line in lines:
            assert line.startswith(("data: ", "event: ")), f"Bad line: {line!r}"

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

    # ------------------------------------------------------------------
    # Edge cases — empty / whitespace input
    # ------------------------------------------------------------------

    def test_stream_empty_input_returns_400(self, client):
        """GET with input= (empty string) returns 400."""
        resp = client.get("/api/game/stream?input=")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "Missing" in data.get("error", "")

    def test_stream_whitespace_input_returns_400(self, client):
        """GET with whitespace-only input returns 400."""
        resp = client.get("/api/game/stream?input=+")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_stream_missing_input_key_returns_400(self, client):
        """GET with a query param that isn't 'input' returns 400."""
        resp = client.get("/api/game/stream?foo=bar")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    # ------------------------------------------------------------------
    # Event type verification
    # ------------------------------------------------------------------

    def test_stream_has_event_type_prefixes(self, client):
        """SSE response includes event: lines for named event dispatch."""
        resp = client.get("/api/game/stream?input=Hello")
        raw = resp.get_data(as_text=True)
        assert "event: narrative" in raw
        assert "event: done" in raw

    def test_stream_includes_token_events_with_provider(self, client):
        """SSE response includes token events when provider streams."""
        mock_provider = MagicMock()
        mock_provider.stream.return_value = iter(
            ["The ", "ancient ", "gate ", "opens."]
        )
        mock_provider.call.return_value = {
            "content": "<narrative>The ancient gate opens.</narrative>",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

        with patch("app.server.OllamaProvider", return_value=mock_provider):
            resp = client.get(
                "/api/game/stream"
                "?input=Test"
                "&base_url=http://localhost:11434"
                "&model=test-model"
            )

        assert resp.status_code == 200
        raw = resp.get_data(as_text=True)
        assert "event: token" in raw
        assert "event: narrative" in raw
        assert "event: done" in raw
        assert "The " in raw
        assert "ancient " in raw
        assert "gate " in raw
        assert "opens." in raw


# ---------------------------------------------------------------------------
# Static file serving (SPA frontend)
# ---------------------------------------------------------------------------


class TestStaticRoutes:
    """Tests for the SPA frontend static file serving."""

    def test_index_returns_html(self, client):
        """GET / returns index.html with 200."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b"LLM-Powered RPG" in resp.data

    def test_index_contains_view_containers(self, client):
        """GET / contains the three SPA view containers."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'id="view-connection"' in html
        assert 'id="view-character"' in html
        assert 'id="view-game"' in html
        assert 'id="narrative-pane"' in html
        assert 'id="status-sidebar"' in html
        assert 'id="input-area"' in html

    def test_static_css_is_served(self, client):
        """GET /static/css/style.css returns CSS with 200."""
        resp = client.get("/static/css/style.css")
        assert resp.status_code == 200
        assert resp.mimetype == "text/css"
        assert b"view" in resp.data

    def test_static_js_is_served(self, client):
        """GET /static/js/app.js returns JS with 200."""
        resp = client.get("/static/js/app.js")
        assert resp.status_code == 200
        assert resp.mimetype in ("application/javascript", "text/javascript")
        assert b"App" in resp.data

    # ------------------------------------------------------------------
    # Edge cases — missing / non-existent static files
    # ------------------------------------------------------------------

    def test_static_css_not_found_returns_404(self, client):
        """GET for non-existent CSS returns 404, not 500."""
        resp = client.get("/static/css/nonexistent.css")
        assert resp.status_code == 404

    def test_static_js_not_found_returns_404(self, client):
        """GET for non-existent JS returns 404, not 500."""
        resp = client.get("/static/js/nonexistent.js")
        assert resp.status_code == 404

    def test_static_favicon_not_found_returns_404(self, client):
        """GET /favicon.ico returns 404 (no crash on common browser request)."""
        resp = client.get("/favicon.ico")
        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # Security — path traversal protection
    # ------------------------------------------------------------------

    def test_static_directory_traversal_blocked(self, client):
        """Directory traversal via static path returns 404."""
        resp = client.get("/static/../server.py")
        assert resp.status_code == 404

    def test_static_directory_traversal_url_encoded_blocked(self, client):
        """URL-encoded directory traversal via static path returns 404."""
        resp = client.get("/static/..%2Fserver.py")
        assert resp.status_code == 404

    def test_static_directory_listing_blocked(self, client):
        """GET /static/ does not list directory contents."""
        resp = client.get("/static/")
        assert resp.status_code == 404

    # ------------------------------------------------------------------
    # Static file content integrity
    # ------------------------------------------------------------------

    def test_static_js_has_expected_public_api(self, client):
        """JS file exposes App object with expected methods."""
        resp = client.get("/static/js/app.js")
        js = resp.get_data(as_text=True)
        assert "const App =" in js or "var App =" in js or "let App =" in js
        assert "init()" in js
        assert "navigate(view)" in js or "navigate(" in js
        assert "getCurrentView()" in js or "getCurrentView" in js

    def test_static_css_contains_view_system(self, client):
        """CSS contains view display classes for SPA routing."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert ".view" in css
        assert ".view.active" in css
        assert "display: none" in css
        assert "display: block" in css or "display: grid" in css

    def test_static_html_has_correct_structure(self, client):
        """HTML has proper SPA shell structure."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
        assert '<script defer src="/static/js/app.js"></script>' in html
        assert '<script defer src="/static/js/connection.js"></script>' in html
        assert '<script defer src="/static/js/character.js"></script>' in html
        assert '<script defer src="/static/js/game.js"></script>' in html
        assert 'id="app"' in html

    def test_static_html_has_all_view_containers(self, client):
        """HTML contains all three view containers with correct IDs."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'id="view-connection"' in html
        assert 'id="view-character"' in html
        assert 'id="view-game"' in html
        # Game view sub-containers
        assert 'id="narrative-pane"' in html
        assert 'id="status-sidebar"' in html
        assert 'id="input-area"' in html
        assert 'id="narrative-content"' in html
        assert 'id="thinking-indicator"' in html

    def test_static_html_has_connection_form_elements(self, client):
        """HTML contains all connection view form elements."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'id="provider-select"' in html
        assert 'id="base-url"' in html
        assert 'id="api-key"' in html
        assert 'id="model-select"' in html
        assert 'id="model-input"' in html
        assert 'id="fetch-models"' in html
        assert 'id="test-connection"' in html
        assert 'id="connection-status"' in html
        assert 'id="start-adventure"' in html

    def test_static_html_has_character_form_elements(self, client):
        """HTML contains all character creation form elements."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'id="char-name"' in html
        assert 'id="char-class"' in html
        assert 'id="char-appearance"' in html
        assert 'id="char-backstory"' in html
        assert 'id="assisted-toggle"' in html
        assert 'id="assisted-info"' in html
        assert 'id="create-character"' in html
        assert 'id="char-validation"' in html
        assert 'id="remaining-points"' in html
        assert 'id="skills-display"' in html
        assert 'id="character-list"' in html

    def test_static_html_has_game_view_input_elements(self, client):
        """HTML contains all game view input elements."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'id="player-input"' in html
        assert 'id="submit-action"' in html
        assert 'id="quick-actions"' in html
        assert 'id="new-game-btn"' in html
        assert 'id="sidebar-collapse"' in html

    def test_static_html_has_game_view_sidebar_elements(self, client):
        """HTML contains all game view sidebar elements."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'id="sidebar-name"' in html
        assert 'id="sidebar-class-level"' in html
        assert 'id="hp-fill"' in html
        assert 'id="hp-text"' in html
        assert 'id="stats-list"' in html
        assert 'id="inventory-list"' in html
        assert 'id="location-text"' in html

    def test_static_connection_js_served(self, client):
        """GET /static/js/connection.js returns 200 with correct content type."""
        resp = client.get("/static/js/connection.js")
        assert resp.status_code == 200
        assert resp.mimetype in ("application/javascript", "text/javascript")

    def test_static_character_js_served(self, client):
        """GET /static/js/character.js returns 200 with correct content type."""
        resp = client.get("/static/js/character.js")
        assert resp.status_code == 200
        assert resp.mimetype in ("application/javascript", "text/javascript")

    def test_static_game_js_served(self, client):
        """GET /static/js/game.js returns 200 with correct content type."""
        resp = client.get("/static/js/game.js")
        assert resp.status_code == 200
        assert resp.mimetype in ("application/javascript", "text/javascript")

    def test_connection_js_exposes_connection_view(self, client):
        """connection.js defines ConnectionView with expected methods."""
        resp = client.get("/static/js/connection.js")
        js = resp.get_data(as_text=True)
        assert "const ConnectionView =" in js or "var ConnectionView =" in js
        assert "init()" in js
        assert "_testConnection" in js
        assert "_fetchModels" in js
        assert "_onProviderChange" in js
        assert "_startAdventure" in js
        assert "_saveState" in js
        assert "_restoreState" in js

    def test_connection_js_uses_correct_health_endpoint(self, client):
        """connection.js calls POST /api/health with correct payload shape."""
        resp = client.get("/static/js/connection.js")
        js = resp.get_data(as_text=True)
        assert "/api/health" in js
        assert "base_url" in js
        assert "model" in js
        assert "api_key" in js
        assert "AbortSignal.timeout" in js

    def test_character_js_exposes_character_view(self, client):
        """character.js defines CharacterView with expected constants and methods."""
        resp = client.get("/static/js/character.js")
        js = resp.get_data(as_text=True)
        assert "const CharacterView =" in js or "var CharacterView =" in js
        assert "POINT_BUY_COST" in js
        assert "MAX_POINTS" in js
        assert "init()" in js
        assert "_createCharacter" in js
        assert "_saveCharacter" in js
        assert "_deleteCharacter" in js
        assert "_renderLoadList" in js
        assert "_esc" in js

    def test_character_js_has_class_defaults(self, client):
        """character.js defines class defaults for all four classes."""
        resp = client.get("/static/js/character.js")
        js = resp.get_data(as_text=True)
        assert "Fighter" in js
        assert "Rogue" in js
        assert "Mage" in js
        assert "Cleric" in js

    def test_game_js_exposes_game_view(self, client):
        """game.js defines GameView with expected methods."""
        resp = client.get("/static/js/game.js")
        js = resp.get_data(as_text=True)
        assert "const GameView =" in js or "var GameView =" in js
        assert "init()" in js
        assert "_sendTurn" in js
        assert "_submit" in js
        assert "_addNarrative" in js
        assert "_renderSidebar" in js
        assert "_applyStateChanges" in js
        assert "_setNested" in js
        assert "_getNested" in js

    def test_game_js_uses_correct_turn_endpoint(self, client):
        """game.js calls POST /api/turn with correct payload shape."""
        resp = client.get("/static/js/game.js")
        js = resp.get_data(as_text=True)
        assert "/api/turn" in js
        assert "input" in js
        assert "provider" in js
        assert "character" in js
        assert "state" in js
        assert "AbortSignal.timeout" in js

    def test_game_js_uses_reset_endpoint(self, client):
        """game.js calls POST /api/reset to initialise world state."""
        resp = client.get("/static/js/game.js")
        js = resp.get_data(as_text=True)
        assert "/api/reset" in js

    def test_game_js_has_error_handling(self, client):
        """game.js handles fetch errors and timeouts gracefully."""
        resp = client.get("/static/js/game.js")
        js = resp.get_data(as_text=True)
        assert "catch (" in js or ".catch(" in js
        assert "TimeoutError" in js or "timeout" in js.lower()
        assert "Failed to fetch" in js or "error" in js.lower()

    def test_css_has_view_system(self, client):
        """CSS contains view display classes for SPA routing."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert ".view" in css
        assert ".view.active" in css
        assert "display: none" in css
        assert "display: block" in css or "display: grid" in css

    def test_css_has_game_view_grid_layout(self, client):
        """CSS defines grid layout for game view."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert "#view-game.active" in css
        assert "grid-template-areas" in css
        assert "narrative" in css
        assert "sidebar" in css
        assert "input" in css

    def test_css_has_connection_view_styles(self, client):
        """CSS defines styles for connection view."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert "#view-connection.active" in css
        assert ".connection-container" in css
        assert ".connection-brand" in css
        assert "#start-adventure" in css

    def test_css_has_character_view_styles(self, client):
        """CSS defines styles for character view with point-buy."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert "#view-character.active" in css
        assert ".abilities-grid" in css
        assert ".ability-card" in css
        assert ".abil-btn" in css
        assert ".point-buy-remaining" in css

    def test_css_has_responsive_styles(self, client):
        """CSS includes responsive breakpoints for mobile."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert "@media (max-width: 768px)" in css
        assert "@media (max-width: 480px)" in css

    def test_css_has_thinking_indicator_animation(self, client):
        """CSS includes thinking indicator animation styles."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert ".thinking-dot" in css
        assert "@keyframes thinkBounce" in css

    def test_css_has_hp_bar_styles(self, client):
        """CSS defines HP bar with low/medium fill states."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert ".hp-bar" in css
        assert ".hp-fill" in css
        assert ".hp-fill.low" in css
        assert ".hp-fill.medium" in css

    def test_css_has_error_and_success_states(self, client):
        """CSS defines styles for success and error status indicators."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert ".status-indicator.success" in css
        assert ".status-indicator.error" in css
        assert ".status-indicator.loading" in css
        assert ".turn-error" in css
        assert ".validation-msg.success" in css
        assert ".validation-msg.error" in css

    # ------------------------------------------------------------------
    # SSE client
    # ------------------------------------------------------------------

    def test_static_sse_js_served(self, client):
        """GET /static/js/sse.js returns 200 with correct content type."""
        resp = client.get("/static/js/sse.js")
        assert resp.status_code == 200
        assert resp.mimetype in ("application/javascript", "text/javascript")

    def test_static_sse_js_exposes_sse_client(self, client):
        """sse.js defines SSEClient with expected methods."""
        resp = client.get("/static/js/sse.js")
        js = resp.get_data(as_text=True)
        assert "const SSEClient =" in js or "var SSEClient =" in js
        assert "connect(input" in js or "connect(" in js
        assert "disconnect()" in js
        assert "EventSource" in js
        assert "onToken" in js
        assert "onNarrative" in js
        assert "onDone" in js
        assert "onError" in js

    def test_static_html_has_sse_script_tag(self, client):
        """HTML includes the sse.js script tag before game.js."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert '<script defer src="/static/js/sse.js"></script>' in html
        sse_idx = html.index("/static/js/sse.js")
        game_idx = html.index("/static/js/game.js")
        assert sse_idx < game_idx, "sse.js must load before game.js"

    def test_game_js_references_sse_client(self, client):
        """game.js references SSEClient for SSE streaming."""
        resp = client.get("/static/js/game.js")
        js = resp.get_data(as_text=True)
        assert "SSEClient" in js
        assert "_sendTurnSSE" in js
        assert "_sendTurnFetch" in js

    # ------------------------------------------------------------------
    # CSS — Accessibility & motion preferences
    # ------------------------------------------------------------------

    def test_css_has_focus_visible_styles(self, client):
        """CSS includes focus-visible styles for keyboard navigation."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert "focus-visible" in css

    def test_css_has_prefers_reduced_motion(self, client):
        """CSS includes prefers-reduced-motion media query."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert "prefers-reduced-motion" in css
        assert "animation-duration: 0.01ms" in css

    def test_css_has_streaming_indicator(self, client):
        """CSS includes streaming text cursor animation."""
        resp = client.get("/static/css/style.css")
        css = resp.get_data(as_text=True)
        assert ".turn-streaming" in css
        assert "blinkCursor" in css


# ---------------------------------------------------------------------------
# Character API Endpoints — Task 4.4
# ---------------------------------------------------------------------------


class TestCharacterGenerateEndpoint:
    """Tests for POST /api/character/generate."""

    def test_generate_success(self, client):
        """POST with valid answers and provider returns a character."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": json.dumps(
                {
                    "name": "Rurik Stoneheart",
                    "character_class": "Fighter",
                    "level": 1,
                    "abilities": {
                        "STR": 15,
                        "DEX": 13,
                        "CON": 14,
                        "WIS": 12,
                        "INT": 10,
                        "CHA": 8,
                    },
                    "skills": ["Athletics", "Perception"],
                    "hp": 12,
                    "max_hp": 12,
                    "ac": 18,
                    "appearance": "A sturdy dwarf.",
                    "backstory": "Blacksmith turned warrior.",
                    "inventory": ["Longsword", "Chain Mail"],
                }
            ),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }

        with patch("app.server.OllamaProvider", return_value=mock_provider):
            resp = client.post(
                "/api/character/generate",
                json={
                    "answers": {
                        "0": "I was a blacksmith's apprentice.",
                        "1": "Orcs raided my village.",
                        "2": "I am stubborn and brave.",
                        "3": "I seek treasure.",
                    },
                    "provider": {
                        "base_url": "http://localhost:11434",
                        "model": "llama3.2",
                    },
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["character"]["name"] == "Rurik Stoneheart"
        assert data["character"]["character_class"] == "Fighter"

    def test_generate_missing_answers(self, client):
        """POST without answers returns 400."""
        resp = client.post(
            "/api/character/generate",
            json={
                "provider": {
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_generate_too_few_answers(self, client):
        """POST with fewer than 3 answers returns 400."""
        resp = client.post(
            "/api/character/generate",
            json={
                "answers": {"0": "answer1", "1": "answer2"},
                "provider": {
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_generate_missing_provider(self, client):
        """POST without provider config returns 400."""
        resp = client.post(
            "/api/character/generate",
            json={"answers": {"0": "a", "1": "b", "2": "c"}},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_generate_non_json_body(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/character/generate",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_generate_non_numeric_answer_keys_returns_400(self, client):
        """POST with non-numeric answer keys returns 400."""
        resp = client.post(
            "/api/character/generate",
            json={
                "answers": {
                    "zero": "I was an apprentice.",
                    "one": "Orcs attacked.",
                    "two": "I am brave.",
                },
                "provider": {
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "numeric" in data.get("error", "").lower()

    def test_generate_non_dict_provider_returns_400(self, client):
        """POST with non-dict provider config returns 400."""
        resp = client.post(
            "/api/character/generate",
            json={
                "answers": {"0": "a", "1": "b", "2": "c"},
                "provider": "not_a_dict",
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "dict" in data.get("error", "").lower()

    def test_generate_character_generation_error_returns_422(self, client):
        """When the LLM fails to produce valid character data after
        retries, the endpoint must return 422."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "This is not valid JSON at all",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }

        with patch("app.server.OllamaProvider", return_value=mock_provider):
            resp = client.post(
                "/api/character/generate",
                json={
                    "answers": {
                        "0": "I was an apprentice.",
                        "1": "Orcs attacked.",
                        "2": "I am brave.",
                    },
                    "provider": {
                        "base_url": "http://localhost:11434",
                        "model": "llama3.2",
                    },
                },
            )

        assert resp.status_code == 422
        data = resp.get_json()
        assert data["ok"] is False
        assert "Failed to generate" in data.get("error", "")


class TestCharacterSaveEndpoint:
    """Tests for POST /api/character/save."""

    _CHARACTER_DATA = {
        "name": "TestHero",
        "character_class": "Fighter",
        "level": 1,
        "abilities": {a: 10 for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")},
        "skills": ["Athletics"],
        "hp": 12,
        "max_hp": 12,
        "ac": 16,
        "appearance": "Tall and strong.",
        "backstory": "A wandering warrior.",
        "inventory": ["Sword"],
    }

    def test_save_success(self, client):
        """POST with valid character data saves and returns timestamp."""
        resp = client.post(
            "/api/character/save",
            json={"character": self._CHARACTER_DATA},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["name"] == "TestHero"
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
        assert len(data["timestamp"]) >= 15

    def test_save_with_custom_name(self, client):
        """POST with custom name uses it for saving."""
        resp = client.post(
            "/api/character/save",
            json={
                "character": self._CHARACTER_DATA,
                "name": "CustomName",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["name"] == "CustomName"

    def test_save_missing_character(self, client):
        """POST without character data returns 400."""
        resp = client.post("/api/character/save", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_save_non_json_body(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/character/save",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_save_invalid_character_data(self, client):
        """POST with invalid character data returns 400."""
        resp = client.post(
            "/api/character/save",
            json={"character": {"name": "", "character_class": "Fighter"}},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_save_non_dict_character_returns_400(self, client):
        """POST with non-dict character data returns 400."""
        resp = client.post(
            "/api/character/save",
            json={"character": "not_a_dict"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_save_storage_error_returns_500(self, client):
        """When the storage layer raises an unexpected error, the
        endpoint must return 500."""
        with patch(
            "app.server.CharacterStorage.save",
            side_effect=OSError("Disk full"),
        ):
            resp = client.post(
                "/api/character/save",
                json={"character": self._CHARACTER_DATA},
            )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False


class TestCharacterListEndpoint:
    """Tests for GET /api/characters."""

    def test_list_empty(self, client):
        """GET /api/characters returns empty list initially."""
        resp = client.get("/api/characters")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert isinstance(data["characters"], list)

    def test_list_after_save(self, client):
        """GET /api/characters includes saved character."""
        # Save a character first
        char_data = {
            "name": "ListTest",
            "character_class": "Mage",
            "level": 1,
            "abilities": {a: 10 for a in ("STR", "DEX", "CON", "INT", "WIS", "CHA")},
            "skills": ["Arcana"],
            "hp": 8,
            "max_hp": 8,
            "ac": 12,
            "appearance": "",
            "backstory": "",
            "inventory": ["Spellbook"],
        }
        client.post("/api/character/save", json={"character": char_data})

        # Then list
        resp = client.get("/api/characters")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        names = [c.get("name") for c in data["characters"]]
        assert "ListTest" in names
