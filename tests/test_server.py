"""Tests for the Flask server — health, save/load, and game endpoints."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.dm import DungeonMaster
from app.character.creation import CharacterStorage
from app.llm.base import LLMProvider, ModelInfo, _model_cache
from app.save_engine.manager import SaveGameManager
from app.server import app
from app.world.model import WorldState
from app.world.persistence import WorldStorage


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a test client with isolated storage directories."""
    tmp_world_storage = WorldStorage(data_dir=tmp_path)
    tmp_char_storage = CharacterStorage(data_dir=tmp_path)
    tmp_save_manager = SaveGameManager(data_dir=tmp_path)
    tmp_save_manager.register_defaults()
    monkeypatch.setattr("app.routes.saves._storage", tmp_world_storage)
    monkeypatch.setattr("app.routes.saves._save_manager", tmp_save_manager)
    monkeypatch.setattr("app.routes.characters._character_storage", tmp_char_storage)

    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the model cache before each test to avoid cross-test pollution."""
    _model_cache.clear()


class TestHealthEndpoint:
    """Tests for POST /api/health."""

    def test_health_success(self, client):
        """POST with valid config returns 200 with ok=True."""
        mock_result = MagicMock()
        mock_result.ok = True
        mock_result.latency_ms = 5.0
        mock_result.model = "llama3.2"
        mock_result.error = None

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.return_value = mock_result
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

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.return_value = mock_result
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

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.return_value = mock_result
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

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.return_value = mock_result
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

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.return_value = mock_result
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

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.return_value = mock_result
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
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.side_effect = RuntimeError("unexpected failure")
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

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.health.return_value = mock_result
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
# Model List Endpoint
# ---------------------------------------------------------------------------


class TestModelsEndpoint:
    """Tests for POST /api/models."""

    def test_list_models_success(self, client):
        """POST with valid config returns models list."""
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.list_models.return_value = [
                ModelInfo(id="model-1", name="Model 1", provider="ollama"),
                ModelInfo(id="model-2", name="Model 2", provider="ollama"),
            ]

            resp = client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert len(data["models"]) == 2
        assert data["models"][0] == {
            "id": "model-1",
            "name": "Model 1",
            "provider": "ollama",
        }
        assert data["models"][1] == {
            "id": "model-2",
            "name": "Model 2",
            "provider": "ollama",
        }

    def test_list_models_missing_fields(self, client):
        """POST missing base_url (and model) returns 400."""
        resp = client.post("/api/models", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "base_url is required"

    def test_list_models_invalid_json(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/models",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "Invalid JSON body"

    def test_list_models_unknown_provider_type(self, client):
        """POST with unknown provider_type returns error."""
        resp = client.post(
            "/api/models",
            json={
                "base_url": "http://localhost:11434",
                "model": "llama3.2",
                "provider_type": "nonexistent",
            },
        )
        assert resp.status_code == 200  # Returns 200 with error in body
        data = resp.get_json()
        assert data["ok"] is False
        assert "error" in data
        assert "Failed to fetch models" in data["error"]

    def test_list_models_caching(self, client):
        """Subsequent calls with same config should use cache."""
        model_list = [ModelInfo(id="cached-model", provider="ollama")]

        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.list_models.return_value = model_list

            # First call — cache miss
            resp1 = client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

            # Second call — should be cached, provider.list_models not called again
            resp2 = client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        data1 = resp1.get_json()
        data2 = resp2.get_json()
        assert data1["ok"] is True
        assert data2["ok"] is True
        assert data2["models"][0]["id"] == "cached-model"
        # create_provider should only have been called once (first call only)
        mock_create.assert_called_once()

    def test_list_models_cache_isolation(self, client):
        """Different base URLs should not share cache."""
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov

            def side_effect(*args, **kwargs):
                return mock_prov

            mock_create.side_effect = side_effect

            mock_prov.list_models.return_value = [
                ModelInfo(id="model-a", provider="ollama"),
            ]

            # Call with different configs
            client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

            client.post(
                "/api/models",
                json={
                    "base_url": "http://other:11434",
                    "model": "llama3.2",
                },
            )

            # create_provider should be called twice (different cache keys)
            assert mock_create.call_count == 2

    def test_list_models_empty_result(self, client):
        """Provider returning empty list should work."""
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.list_models.return_value = []

            resp = client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["models"] == []

    def test_list_models_provider_exception(self, client):
        """When provider raises, returns 200 with error in body."""
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.list_models.side_effect = RuntimeError("Something broke")

            resp = client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is False
        assert "Something broke" not in data["error"]

    # ------------------------------------------------------------------
    # Edge cases — input validation
    # ------------------------------------------------------------------

    def test_list_models_malformed_json_with_json_content_type(self, client):
        """POST with malformed JSON but correct content-type returns 400."""
        resp = client.post(
            "/api/models",
            data="not valid json at all",
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "Invalid JSON body"

    def test_list_models_null_base_url(self, client):
        """POST with null base_url returns 400."""
        resp = client.post(
            "/api/models",
            json={"base_url": None, "model": "llama3.2"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "base_url is required" in data["error"]

    def test_list_models_null_model(self, client):
        """POST with null model is OK — model is optional for listing."""
        resp = client.post(
            "/api/models",
            json={"base_url": "http://localhost:11434", "model": None},
        )
        # Model is optional; should not return 400 validation error
        assert resp.status_code != 400

    def test_list_models_whitespace_base_url(self, client):
        """POST with whitespace-only base_url returns 400."""
        resp = client.post(
            "/api/models",
            json={"base_url": "   ", "model": "llama3.2"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "base_url is required" in data["error"]

    def test_list_models_whitespace_model(self, client):
        """POST with whitespace-only model is OK — model is optional."""
        resp = client.post(
            "/api/models",
            json={"base_url": "http://localhost:11434", "model": "   "},
        )
        # Model is optional; whitespace model should not cause 400
        assert resp.status_code != 400

    # ------------------------------------------------------------------
    # Edge cases — provider_type handling
    # ------------------------------------------------------------------

    def test_list_models_empty_provider_type_defaults_to_ollama(self, client):
        """POST with empty provider_type defaults to ollama."""
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.list_models.return_value = [
                ModelInfo(id="test-model", provider="ollama"),
            ]

            resp = client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                    "provider_type": "",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        # Verify create_provider was called with provider_type="ollama"
        config_arg = mock_create.call_args[0][0]
        assert config_arg.provider_type == "ollama"

    # ------------------------------------------------------------------
    # Edge cases — cache behaviour
    # ------------------------------------------------------------------

    def test_list_models_cache_isolation_by_provider_type(self, client):
        """Different provider types with same base URL should not share cache."""
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov

            mock_prov.list_models.return_value = [
                ModelInfo(id="ollama-model", provider="ollama"),
            ]

            # First call with ollama (default)
            client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            )

            # Second call with groq but same base URL
            # We need a new mock response for the second call
            mock_prov.list_models.return_value = [
                ModelInfo(id="groq-model", provider="groq"),
            ]

            resp2 = client.post(
                "/api/models",
                json={
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                    "provider_type": "groq",
                },
            )

        # create_provider should be called twice (different provider types)
        assert mock_create.call_count == 2
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2["ok"] is True
        # Should get the groq model (fresh fetch, not cached ollama)
        assert data2["models"][0]["id"] == "groq-model"

    # ------------------------------------------------------------------
    # Edge cases — body structure
    # ------------------------------------------------------------------

    def test_list_models_extra_unexpected_fields(self, client):
        """POST with unexpected fields ignores them and succeeds."""
        with patch("app.routes.health.create_provider") as mock_create:
            mock_prov = MagicMock()
            mock_create.return_value = mock_prov
            mock_prov.list_models.return_value = [
                ModelInfo(id="model-1", provider="ollama"),
            ]

            resp = client.post(
                "/api/models",
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
        assert len(data["models"]) == 1


# ---------------------------------------------------------------------------
# Game Stream Endpoint
# ---------------------------------------------------------------------------


class TestGameStreamEndpoint:
    """Tests for POST /api/game/stream."""

    def test_stream_without_input_returns_400(self, client):
        """POST without input in body returns 400."""
        resp = client.post("/api/game/stream", json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_stream_with_input_returns_sse(self, client):
        """POST with input returns SSE response."""
        resp = client.post("/api/game/stream", json={"input": "Hello"})
        assert resp.status_code == 200
        assert resp.mimetype == "text/event-stream"
        data = resp.get_data(as_text=True)
        # Should have SSE events
        assert "data:" in data
        assert "narrative" in data
        assert "done" in data

    def test_stream_sse_format(self, client):
        """SSE response should have proper event format with event: and data: lines."""
        resp = client.post("/api/game/stream", json={"input": "Look around"})
        raw = resp.get_data(as_text=True)
        lines = [line for line in raw.split("\n") if line.strip()]
        assert len(lines) > 0
        for line in lines:
            assert line.startswith(("data: ", "event: ")), f"Bad line: {line!r}"

    def test_stream_includes_narrative(self, client):
        """SSE response should include narrative event."""
        resp = client.post("/api/game/stream", json={"input": "Hello"})
        data = resp.get_data(as_text=True)
        assert '"type": "narrative"' in data

    def test_stream_includes_done_event(self, client):
        """SSE response should include a done event."""
        resp = client.post("/api/game/stream", json={"input": "Hello"})
        data = resp.get_data(as_text=True)
        assert '"type": "done"' in data
        assert '"turn_count"' in data

    # ------------------------------------------------------------------
    # Edge cases — empty / whitespace input
    # ------------------------------------------------------------------

    def test_stream_empty_input_returns_400(self, client):
        """POST with empty string input returns 400."""
        resp = client.post("/api/game/stream", json={"input": ""})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "Missing" in data.get("error", "")

    def test_stream_whitespace_input_returns_400(self, client):
        """POST with whitespace-only input returns 400."""
        resp = client.post("/api/game/stream", json={"input": "   "})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_stream_missing_input_key_returns_400(self, client):
        """POST with a body that has no 'input' key returns 400."""
        resp = client.post("/api/game/stream", json={"foo": "bar"})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    # ------------------------------------------------------------------
    # Event type verification
    # ------------------------------------------------------------------

    def test_stream_has_event_type_prefixes(self, client):
        """SSE response includes event: lines for named event dispatch."""
        resp = client.post("/api/game/stream", json={"input": "Hello"})
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

        with patch("app.routes.game.create_provider", return_value=mock_provider):
            resp = client.post(
                "/api/game/stream",
                json={
                    "input": "Test",
                    "provider": {
                        "base_url": "http://localhost:11434",
                        "model": "test-model",
                    },
                },
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

    # ------------------------------------------------------------------
    # Impossible action short-circuit
    # ------------------------------------------------------------------

    def test_stream_impossible_action_returns_canned_narrative(self, client):
        """SSE response for impossible action returns narrative WITHOUT
        calling the LLM — no token events should appear."""

        # A Fighter trying to cast a spell is impossible per CLASS_BLACKLIST
        character_data = {
            "name": "Test Fighter",
            "character_class": "Fighter",
            "abilities": {
                "STR": 15,
                "DEX": 13,
                "CON": 14,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            },
            "level": 1,
            "hp": 12,
            "max_hp": 12,
            "ac": 18,
        }

        resp = client.post(
            "/api/game/stream",
            json={
                "input": "I cast fireball",
                "character": character_data,
            },
        )

        assert resp.status_code == 200
        raw = resp.get_data(as_text=True)

        # Must include a narrative event with impossible-action language
        assert "event: narrative" in raw
        assert '"type": "narrative"' in raw
        assert "beyond" in raw.lower() or "cannot" in raw.lower(), (
            "Impossible narrative should contain 'beyond' or 'cannot'"
        )

        # Must include state_update and done events
        assert "event: state_update" in raw
        assert "event: done" in raw

        # Must NOT include token events — LLM was short-circuited
        assert "event: token" not in raw, (
            "Token events should not appear when action is impossible"
        )


# ---------------------------------------------------------------------------
# Token Usage Accumulation
# ---------------------------------------------------------------------------


class TestTokenUsage:
    """Tests for server-side token usage accumulation."""

    def test_token_usage_accumulates_across_llm_calls(self):
        """Token usage should accumulate when _call_llm is called multiple
        times — simulating multiple LLM calls within a single turn."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.call.return_value = {
            "content": "<narrative>Test narrative.</narrative>",
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=WorldState(),
            character=None,
        )

        # First call
        dm._call_llm([{"role": "user", "content": "Hello"}])
        assert dm.token_usage["prompt_tokens"] == 10
        assert dm.token_usage["completion_tokens"] == 5
        assert dm.token_usage["total_tokens"] == 15

        # Second call — should accumulate
        dm._call_llm([{"role": "user", "content": "Again"}])
        assert dm.token_usage["prompt_tokens"] == 20
        assert dm.token_usage["completion_tokens"] == 10
        assert dm.token_usage["total_tokens"] == 30


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

    def test_index_contains_react_shell(self, client):
        """GET / contains the React SPA shell (div#root)."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert b'<div id="root">' in resp.data

    # ------------------------------------------------------------------
    # Edge cases — missing / non-existent static files
    # ------------------------------------------------------------------

    def test_static_css_not_found_returns_react_spa(self, client):
        """GET for non-existent CSS returns React SPA (catch-all), not 404."""
        resp = client.get("/static/css/nonexistent.css")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    def test_static_js_not_found_returns_react_spa(self, client):
        """GET for non-existent JS returns React SPA (catch-all), not 404."""
        resp = client.get("/static/js/nonexistent.js")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    def test_static_favicon_returns_react_spa(self, client):
        """GET /favicon.ico returns React SPA (catch-all for client-side
        routing, since no file favicon.ico exists in the React build)."""
        resp = client.get("/favicon.ico")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    # ------------------------------------------------------------------
    # Security — path traversal protection
    # ------------------------------------------------------------------

    def test_static_directory_traversal_returns_react_spa(self, client):
        """Directory traversal via static path is rejected (security)."""
        resp = client.get("/static/../server.py")
        assert resp.status_code == 404

    def test_static_directory_traversal_url_encoded_returns_react_spa(self, client):
        """URL-encoded directory traversal via static path is rejected
        (security)."""
        resp = client.get("/static/..%2Fserver.py")
        assert resp.status_code == 404

    def test_static_slash_returns_react_spa(self, client):
        """GET /static/ returns React SPA (catch-all for client-side
        routing, since /static/ has no matching static file)."""
        resp = client.get("/static/")
        assert resp.status_code == 200
        assert resp.mimetype == "text/html"
        assert b'<div id="root">' in resp.data

    # ------------------------------------------------------------------
    # HTML structure
    # ------------------------------------------------------------------

    def test_static_html_has_correct_structure(self, client):
        """HTML has proper React SPA shell structure."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html
        assert 'id="root"' in html
        assert '<script type="module" crossorigin src=' in html

    def test_static_html_has_react_root(self, client):
        """HTML contains the React root mount point."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'id="root"' in html
        assert '<div id="root">' in html

    def test_static_html_has_vite_script(self, client):
        """HTML contains a Vite module script entry point."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert "/assets/index-" in html
        assert ".js" in html
        assert 'type="module"' in html

    def test_static_html_has_vite_css_link(self, client):
        """HTML contains a Vite CSS link tag."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert "/assets/index-" in html
        assert ".css" in html
        assert 'rel="stylesheet"' in html

    def test_static_html_has_meta_viewport(self, client):
        """HTML contains viewport meta tag for responsive design."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert 'name="viewport"' in html
        assert 'content="width=device-width, initial-scale=1.0"' in html

    def test_static_html_has_vite_assets(self, client):
        """HTML references Vite asset files."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert "/assets/" in html
        assert "crossorigin" in html

    def test_static_html_has_module_script(self, client):
        """HTML includes a module script tag for the React bundle."""
        resp = client.get("/")
        html = resp.get_data(as_text=True)
        assert '<script type="module" crossorigin src=' in html


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
                    "resources": {
                        "hp": {"value": 12, "max": 12},
                    },
                    "appearance": "A sturdy dwarf.",
                    "backstory": "Blacksmith turned warrior.",
                    "inventory": ["Longsword", "Chain Mail"],
                }
            ),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }

        with patch("app.routes.characters.create_provider", return_value=mock_provider):
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

        with patch("app.routes.characters.create_provider", return_value=mock_provider):
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
        assert "Unable to generate" in data.get("error", "")

    def test_generate_with_name_passes_name_to_creation(self, client):
        """POST with name field must pass it through to the LLM and
        return the character with that name."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": json.dumps(
                {
                    "name": "Thorne Ironveil",
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
                    "resources": {
                        "hp": {"value": 12, "max": 12},
                    },
                    "appearance": "A sturdy dwarf.",
                    "backstory": "Blacksmith turned warrior.",
                    "inventory": ["Longsword", "Chain Mail"],
                }
            ),
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
            },
        }

        with patch(
            "app.routes.characters.create_provider",
            return_value=mock_provider,
        ):
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
                    "name": "Thorne Ironveil",
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["character"]["name"] == "Thorne Ironveil"

        # Verify name was included in the LLM call messages
        messages = mock_provider.call.call_args[0][0]
        all_text = " ".join(m["content"] for m in messages)
        assert "Thorne Ironveil" in all_text

    def test_generate_without_name_still_works(self, client):
        """POST without name field must still generate a character
        (backward compatibility)."""
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
                    "resources": {
                        "hp": {"value": 12, "max": 12},
                    },
                    "appearance": "A sturdy dwarf.",
                    "backstory": "Blacksmith turned warrior.",
                    "inventory": ["Longsword", "Chain Mail"],
                }
            ),
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 10,
                "total_tokens": 20,
            },
        }

        with patch(
            "app.routes.characters.create_provider",
            return_value=mock_provider,
        ):
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


class TestCharacterCreateEndpoint:
    """Tests for POST /api/character/create."""

    def test_create_success(self, client):
        """POST with valid name and class creates and returns a character."""
        resp = client.post(
            "/api/character/create",
            json={
                "name": "TestHero",
                "character_class": "Fighter",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["character"]["name"] == "TestHero"
        assert data["character"]["character_class"] == "Fighter"
        assert data["character"]["id"] != ""
        assert isinstance(data["character"]["id"], str)

    def test_create_with_all_fields(self, client):
        """POST with appearance and backstory includes them."""
        resp = client.post(
            "/api/character/create",
            json={
                "name": "Zara",
                "character_class": "Rogue",
                "appearance": "Elven with silver hair",
                "backstory": "Grew up in the Crescent Woods.",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["character"]["name"] == "Zara"
        assert data["character"]["character_class"] == "Rogue"
        assert data["character"]["appearance"] == "Elven with silver hair"
        assert data["character"]["backstory"] == "Grew up in the Crescent Woods."

    def test_create_missing_name(self, client):
        """POST without name returns 400."""
        resp = client.post(
            "/api/character/create",
            json={"character_class": "Fighter"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "name" in data["error"].lower()

    def test_create_empty_name(self, client):
        """POST with empty name returns 400."""
        resp = client.post(
            "/api/character/create",
            json={"name": "", "character_class": "Fighter"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "name" in data["error"].lower()

    def test_create_invalid_class(self, client):
        """POST with invalid character_class returns 400."""
        resp = client.post(
            "/api/character/create",
            json={"name": "Test", "character_class": "Paladin"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "Invalid character class" in data["error"]

    def test_create_non_json_body(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/character/create",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_create_missing_character_class(self, client):
        """POST without character_class returns 400."""
        resp = client.post(
            "/api/character/create",
            json={"name": "Test"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_create_storage_error_returns_500(self, client):
        """When the storage layer raises an unexpected error, returns 500."""
        with patch(
            "app.routes.characters.CharacterStorage.save",
            side_effect=OSError("Disk full"),
        ):
            resp = client.post(
                "/api/character/create",
                json={
                    "name": "TestHero",
                    "character_class": "Fighter",
                },
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

    def test_list_after_create(self, client):
        """GET /api/characters includes created character."""
        # Create a character first
        client.post(
            "/api/character/create",
            json={"name": "ListTest", "character_class": "Mage"},
        )

        # Then list
        resp = client.get("/api/characters")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        names = [c.get("name") for c in data["characters"]]
        assert "ListTest" in names
        # Each entry must have a non-empty id
        for entry in data["characters"]:
            assert "id" in entry
            assert entry["id"] != ""

    def test_list_preserves_existing_fields(self, client):
        """Character list entries must include name, class, level, timestamp."""
        client.post(
            "/api/character/create",
            json={"name": "FieldTest", "character_class": "Cleric"},
        )
        resp = client.get("/api/characters")
        assert resp.status_code == 200
        entries = resp.get_json()["characters"]
        assert len(entries) >= 1
        entry = entries[0]
        assert entry["name"] == "FieldTest"
        assert entry["class"] == "Cleric"
        assert entry["level"] == 1
        assert "timestamp" in entry


# ---------------------------------------------------------------------------
# GET /api/character/id/<id> and DELETE /api/character/id/<id>
# ---------------------------------------------------------------------------


class TestCharacterIdEndpoint:
    """Tests for GET/DELETE /api/character/id/<id>."""

    def test_load_by_id_success(self, client):
        """GET /api/character/id/<id> returns the full character."""
        # Create a character first
        resp = client.post(
            "/api/character/create",
            json={
                "name": "IDHero",
                "character_class": "Mage",
                "appearance": "Tall figure in robes",
                "backstory": "A wandering mage seeking knowledge.",
            },
        )
        assert resp.status_code == 200
        char_id = resp.get_json()["character"]["id"]
        assert char_id != ""
        assert isinstance(char_id, str)

        # Load by id
        resp = client.get(f"/api/character/id/{char_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["character"]["id"] == char_id
        assert data["character"]["name"] == "IDHero"
        assert data["character"]["character_class"] == "Mage"
        assert data["character"]["appearance"] == "Tall figure in robes"
        assert data["character"]["backstory"] == "A wandering mage seeking knowledge."

    def test_load_by_id_not_found(self, client):
        """GET /api/character/id/<nonexistent> returns 404."""
        resp = client.get("/api/character/id/nonexistent-uuid")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False
        assert "not found" in data["error"].lower() or "not found" in data["error"]

    def test_delete_by_id_success(self, client):
        """DELETE /api/character/id/<id> removes the character."""
        # Create a character
        resp = client.post(
            "/api/character/create",
            json={"name": "DeleteID", "character_class": "Rogue"},
        )
        assert resp.status_code == 200
        char_id = resp.get_json()["character"]["id"]

        # Delete by id
        resp = client.delete(f"/api/character/id/{char_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        # Verify it's gone
        resp = client.get(f"/api/character/id/{char_id}")
        assert resp.status_code == 404

    def test_delete_by_id_not_found(self, client):
        """DELETE /api/character/id/<nonexistent> returns 404."""
        resp = client.delete("/api/character/id/nonexistent-uuid")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False
        assert "not found" in data["error"].lower() or "not found" in data["error"]


# ---------------------------------------------------------------------------
# GET /api/character/<id>/sheet
# ---------------------------------------------------------------------------


class TestCharacterSheetEndpoint:
    """Tests for GET /api/character/<id>/sheet."""

    def test_get_sheet_success(self, client):
        """GET /api/character/<id>/sheet returns derived sheet."""
        # Create a character first
        resp = client.post(
            "/api/character/create",
            json={
                "name": "SheetHero",
                "character_class": "Fighter",
            },
        )
        assert resp.status_code == 200
        char_id = resp.get_json()["character"]["id"]
        assert char_id != ""

        # Get the derived sheet
        resp = client.get(f"/api/character/{char_id}/sheet")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "sheet" in data

        sheet = data["sheet"]
        # Sheet must contain key derived fields
        assert "ability_modifiers" in sheet
        assert "proficiency_bonus" in sheet
        assert "ac" in sheet
        assert "initiative" in sheet
        assert "skill_modifiers" in sheet
        assert "saving_throw_modifiers" in sheet
        assert "passive_perception" in sheet
        assert "hit_dice" in sheet

        # Fighter-specific checks
        assert sheet["hit_dice"] == "1d10"
        assert sheet["proficiency_bonus"] == 2
        # Fighter with STR 15 → modifier +2, chain mail AC 16 + shield +2 = 18
        assert sheet["ac"] >= 10

    def test_get_sheet_not_found(self, client):
        """GET /api/character/<nonexistent>/sheet returns 404."""
        resp = client.get("/api/character/nonexistent-uuid/sheet")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False
        assert "not found" in data["error"].lower()

    def test_get_sheet_computed_values(self, client):
        """GET /api/character/<id>/sheet returns correct derived values."""
        # Create a Mage
        resp = client.post(
            "/api/character/create",
            json={
                "name": "WiseMage",
                "character_class": "Mage",
            },
        )
        assert resp.status_code == 200
        char_id = resp.get_json()["character"]["id"]

        resp = client.get(f"/api/character/{char_id}/sheet")
        assert resp.status_code == 200
        sheet = resp.get_json()["sheet"]

        # Mage has INT 15 → modifier +2
        assert sheet["ability_modifiers"]["INT"] == 2
        # Mage proficiency bonus at level 1
        assert sheet["proficiency_bonus"] == 2
        # Mage hit dice
        assert sheet["hit_dice"] == "1d6"
        # Skill modifiers should be present
        assert "arcana" in sheet["skill_modifiers"]
        assert "investigation" in sheet["skill_modifiers"]
        # Saving throws — Mage proficient in INT and WIS
        assert sheet["saving_throw_modifiers"]["INT"] >= 2
        assert sheet["saving_throw_modifiers"]["WIS"] >= 2

    def test_get_sheet_after_generated_character(self, client):
        """GET /api/character/<id>/sheet works for LLM-generated characters."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": json.dumps(
                {
                    "name": "LLMSheetHero",
                    "character_class": "Rogue",
                    "level": 1,
                    "abilities": {
                        "STR": 8,
                        "DEX": 15,
                        "CON": 13,
                        "INT": 14,
                        "WIS": 12,
                        "CHA": 10,
                    },
                    "skills": ["Stealth", "Sleight of Hand", "Perception"],
                    "resources": {
                        "hp": {"value": 9, "max": 9},
                    },
                    "appearance": "Shadowy figure.",
                    "backstory": "Spy turned adventurer.",
                    "inventory": ["Shortsword", "Leather Armor"],
                }
            ),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }

        with patch("app.routes.characters.create_provider", return_value=mock_provider):
            resp = client.post(
                "/api/character/generate",
                json={
                    "answers": {
                        "0": "Grew up in the slums.",
                        "1": "Stole from the wrong person.",
                        "2": "Fled to start a new life.",
                    },
                    "provider": {
                        "base_url": "http://localhost:11434",
                        "model": "llama3.2",
                    },
                },
            )

        assert resp.status_code == 200
        char_id = resp.get_json()["character"]["id"]

        resp = client.get(f"/api/character/{char_id}/sheet")
        assert resp.status_code == 200
        sheet = resp.get_json()["sheet"]
        # Rogue with DEX 15 → modifier +2
        assert sheet["ability_modifiers"]["DEX"] == 2
        assert sheet["hit_dice"] == "1d8"
        # Stealth should be proficient
        assert sheet["skill_modifiers"]["stealth"] >= 2


# ---------------------------------------------------------------------------
# GET /api/story/<name>
# ---------------------------------------------------------------------------


class TestStoryEndpoint:
    """Tests for GET /api/story/<name>."""

    def test_get_story_endpoint_returns_story(self, client):
        """GET /api/story/<slug> returns condensed story summaries."""
        state = {
            "version": "1.0",
            "story_summary": [
                "[Turn 1] You enter the dark forest.",
                "[Turn 4] A goblin appears!",
            ],
        }
        resp = client.post(
            "/api/save",
            json={"state": state, "name": "story_test_save"},
        )
        assert resp.status_code == 200
        slug = resp.get_json()["slug"]

        resp = client.get(f"/api/story/{slug}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["story"] == [
            "[Turn 1] You enter the dark forest.",
            "[Turn 4] A goblin appears!",
        ]

    def test_get_story_endpoint_fallback_to_old_save(self, client):
        """GET /api/story/<slug> falls back to story_summary without json file."""
        state = {
            "version": "1.0",
            "story_summary": [
                "[Turn 2] The dragon awakens.",
            ],
        }
        resp = client.post(
            "/api/save",
            json={"state": state, "name": "old_save_test"},
        )
        assert resp.status_code == 200
        slug = resp.get_json()["slug"]

        # Delete story_summary.json to simulate an old save (pre-Task 4.1)
        saves_dir = Path("data/saves") / slug
        story_file = saves_dir / "story_summary.json"
        if story_file.exists():
            os.remove(story_file)

        # Now the endpoint should fall back to loading WorldState from summary.json
        resp = client.get(f"/api/story/{slug}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["story"] == ["[Turn 2] The dragon awakens."]

    def test_get_story_endpoint_404(self, client):
        """GET /api/story/<nonexistent> returns 404."""
        resp = client.get("/api/story/nonexistent_save")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False
        assert "not found" in data["error"].lower()
