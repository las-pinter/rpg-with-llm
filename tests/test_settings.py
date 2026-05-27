"""Tests for the settings API endpoints — GET and POST /api/settings."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.llm.base import ProviderConfig
from app.llm.config import ConfigError, ConfigManager
from app.server import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------


class TestGetSettings:
    """Tests for GET /api/settings."""

    def test_returns_ok(self, client):
        """GET returns 200 with ok=true."""
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "settings" in data

    def test_returns_default_dm_settings(self, client):
        """GET returns default DM agent settings."""
        resp = client.get("/api/settings")
        settings = resp.get_json()["settings"]
        assert settings["dm_max_tokens"] == 4096
        assert settings["dm_temperature"] == 0.8
        assert settings["dm_timeout"] == 300

    def test_returns_default_npc_settings(self, client):
        """GET returns default NPC agent settings."""
        resp = client.get("/api/settings")
        settings = resp.get_json()["settings"]
        assert settings["npc_max_tokens"] == 1024
        assert settings["npc_temperature"] == 0.8
        assert settings["npc_timeout"] == 300

    def test_returns_default_summarizer_settings(self, client):
        """GET returns default summarizer agent settings."""
        resp = client.get("/api/settings")
        settings = resp.get_json()["settings"]
        assert settings["summarizer_max_tokens"] == 4096
        assert settings["summarizer_temperature"] == 0.3
        assert settings["summarizer_timeout"] == 300

    def test_returns_default_provider_settings(self, client):
        """GET returns default provider settings."""
        resp = client.get("/api/settings")
        settings = resp.get_json()["settings"]
        assert settings["base_url"] == "http://localhost:11434"
        assert settings["model"] == "llama3.2"
        assert settings["provider_type"] == "ollama"
        assert settings["api_key"] is None
        assert settings["timeout"] == 300
        assert settings["max_tokens"] is None
        assert settings["temperature"] is None

    def test_merges_saved_config(self, client, monkeypatch):
        """GET merges saved provider config over defaults."""
        manager = ConfigManager(__file__)  # dummy — we'll mock get_config
        saved_cfg = ProviderConfig(
            base_url="http://other:11434",
            model="other-model",
            provider_type="groq",
            api_key="sk-test",
            timeout=120,
            max_tokens=2048,
            temperature=0.5,
        )

        with patch.object(manager, "get_config", return_value=saved_cfg) as mock_get:
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.get("/api/settings")
            mock_get.assert_called_once_with("default")

        settings = resp.get_json()["settings"]
        # Provider fields should be overridden
        assert settings["base_url"] == "http://other:11434"
        assert settings["model"] == "other-model"
        assert settings["provider_type"] == "groq"
        assert settings["api_key"] == "sk-test"
        assert settings["timeout"] == 120
        assert settings["max_tokens"] == 2048
        assert settings["temperature"] == 0.5

        # Agent-specific fields should remain at defaults
        assert settings["dm_max_tokens"] == 4096
        assert settings["npc_max_tokens"] == 1024
        assert settings["summarizer_max_tokens"] == 4096

    def test_no_saved_config_uses_defaults(self, client, monkeypatch):
        """GET uses hardcoded defaults when no saved config exists."""
        manager = ConfigManager(__file__)

        with patch.object(
            manager, "get_config", side_effect=ConfigError("not found")
        ) as mock_get:
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.get("/api/settings")
            mock_get.assert_called_once_with("default")

        settings = resp.get_json()["settings"]
        assert settings["base_url"] == "http://localhost:11434"
        assert settings["model"] == "llama3.2"
        assert settings["api_key"] is None

    def test_saved_config_with_none_api_key_returns_none(self, client, monkeypatch):
        """GET returns None api_key when saved config has no api_key."""
        manager = ConfigManager(__file__)
        saved_cfg = ProviderConfig(
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        with patch.object(manager, "get_config", return_value=saved_cfg):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.get("/api/settings")

        assert resp.get_json()["settings"]["api_key"] is None

    def test_all_fields_present(self, client):
        """GET returns all expected setting keys."""
        resp = client.get("/api/settings")
        keys = set(resp.get_json()["settings"].keys())
        expected = {
            "dm_max_tokens",
            "dm_temperature",
            "dm_timeout",
            "npc_max_tokens",
            "npc_temperature",
            "npc_timeout",
            "summarizer_max_tokens",
            "summarizer_temperature",
            "summarizer_timeout",
            "base_url",
            "model",
            "provider_type",
            "api_key",
            "timeout",
            "max_tokens",
            "temperature",
        }
        assert keys == expected


# ---------------------------------------------------------------------------
# POST /api/settings
# ---------------------------------------------------------------------------


class TestPostSettings:
    """Tests for POST /api/settings."""

    def test_invalid_json_returns_400(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/settings",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "error" in data

    def test_malformed_json_with_json_content_type_returns_400(self, client):
        """POST with malformed JSON returns 400."""
        resp = client.post(
            "/api/settings",
            data="not json at all",
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False

    def test_partial_update_preserves_defaults(self, client, monkeypatch):
        """POST with partial data updates only provided fields."""
        manager = ConfigManager(__file__)

        with (
            patch.object(manager, "save_config") as mock_save,
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.post("/api/settings", json={"base_url": "http://new:11434"})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        settings = data["settings"]
        # Provided field should be updated
        assert settings["base_url"] == "http://new:11434"
        # Other fields should remain defaults
        assert settings["model"] == "llama3.2"
        assert settings["dm_max_tokens"] == 4096

        # Verify save was called with correct config
        saved_config = mock_save.call_args[0][0]
        assert saved_config.base_url == "http://new:11434"
        assert saved_config.model == "llama3.2"  # from defaults

    def test_update_all_provider_fields(self, client, monkeypatch):
        """POST with all provider fields updates them all."""
        manager = ConfigManager(__file__)

        with (
            patch.object(manager, "save_config") as mock_save,
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.post(
                "/api/settings",
                json={
                    "base_url": "http://new:11434",
                    "model": "new-model",
                    "provider_type": "groq",
                    "api_key": "sk-new",
                    "timeout": 60,
                    "max_tokens": 2048,
                    "temperature": 0.7,
                },
            )

        assert resp.status_code == 200
        saved_config = mock_save.call_args[0][0]
        assert saved_config.base_url == "http://new:11434"
        assert saved_config.model == "new-model"
        assert saved_config.provider_type == "groq"
        assert saved_config.api_key == "sk-new"
        assert saved_config.timeout == 60
        assert saved_config.max_tokens == 2048
        assert saved_config.temperature == 0.7

    def test_update_agent_settings(self, client, monkeypatch):
        """POST updates agent-specific settings."""
        manager = ConfigManager(__file__)

        with (
            patch.object(manager, "save_config"),
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.post(
                "/api/settings",
                json={
                    "dm_max_tokens": 8192,
                    "dm_temperature": 0.9,
                    "dm_timeout": 600,
                    "npc_max_tokens": 2048,
                    "npc_temperature": 0.7,
                    "npc_timeout": 120,
                    "summarizer_max_tokens": 8192,
                    "summarizer_temperature": 0.5,
                    "summarizer_timeout": 600,
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        settings = data["settings"]
        assert settings["dm_max_tokens"] == 8192
        assert settings["dm_temperature"] == 0.9
        assert settings["dm_timeout"] == 600
        assert settings["npc_max_tokens"] == 2048
        assert settings["npc_temperature"] == 0.7
        assert settings["npc_timeout"] == 120
        assert settings["summarizer_max_tokens"] == 8192
        assert settings["summarizer_temperature"] == 0.5
        assert settings["summarizer_timeout"] == 600

    # ------------------------------------------------------------------
    # Validation: max_tokens
    # ------------------------------------------------------------------

    def test_invalid_dm_max_tokens_zero(self, client):
        """POST with dm_max_tokens=0 returns 400."""
        resp = client.post("/api/settings", json={"dm_max_tokens": 0})
        assert resp.status_code == 400
        assert "errors" in resp.get_json()

    def test_invalid_dm_max_tokens_negative(self, client):
        """POST with negative dm_max_tokens returns 400."""
        resp = client.post("/api/settings", json={"dm_max_tokens": -5})
        assert resp.status_code == 400

    def test_invalid_dm_max_tokens_string(self, client):
        """POST with string dm_max_tokens returns 400."""
        resp = client.post("/api/settings", json={"dm_max_tokens": "not-a-number"})
        assert resp.status_code == 400

    def test_invalid_npc_max_tokens_zero(self, client):
        """POST with npc_max_tokens=0 returns 400."""
        resp = client.post("/api/settings", json={"npc_max_tokens": 0})
        assert resp.status_code == 400

    def test_invalid_max_tokens_zero(self, client):
        """POST with max_tokens=0 returns 400."""
        resp = client.post("/api/settings", json={"max_tokens": 0})
        assert resp.status_code == 400

    def test_valid_max_tokens_none(self, client, monkeypatch):
        """POST with max_tokens=None is valid (provider default)."""
        manager = ConfigManager(__file__)

        with (
            patch.object(manager, "save_config") as mock_save,
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.post("/api/settings", json={"max_tokens": None})

        assert resp.status_code == 200
        saved_config = mock_save.call_args[0][0]
        assert saved_config.max_tokens is None

    # ------------------------------------------------------------------
    # Validation: temperature
    # ------------------------------------------------------------------

    def test_invalid_dm_temperature_below_zero(self, client):
        """POST with dm_temperature=-0.1 returns 400."""
        resp = client.post("/api/settings", json={"dm_temperature": -0.1})
        assert resp.status_code == 400

    def test_invalid_dm_temperature_above_two(self, client):
        """POST with dm_temperature=2.1 returns 400."""
        resp = client.post("/api/settings", json={"dm_temperature": 2.1})
        assert resp.status_code == 400

    def test_valid_dm_temperature_zero(self, client, monkeypatch):
        """POST with dm_temperature=0 is valid."""
        manager = ConfigManager(__file__)

        with (
            patch.object(manager, "save_config"),
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.post("/api/settings", json={"dm_temperature": 0})

        assert resp.status_code == 200

    def test_valid_dm_temperature_two(self, client, monkeypatch):
        """POST with dm_temperature=2 is valid (boundary)."""
        manager = ConfigManager(__file__)

        with (
            patch.object(manager, "save_config"),
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.post("/api/settings", json={"dm_temperature": 2})

        assert resp.status_code == 200

    def test_valid_temperature_none(self, client, monkeypatch):
        """POST with temperature=None is valid (provider default)."""
        manager = ConfigManager(__file__)

        with (
            patch.object(manager, "save_config") as mock_save,
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            resp = client.post("/api/settings", json={"temperature": None})

        assert resp.status_code == 200
        saved_config = mock_save.call_args[0][0]
        assert saved_config.temperature is None

    # ------------------------------------------------------------------
    # Validation: timeout
    # ------------------------------------------------------------------

    def test_invalid_dm_timeout_zero(self, client):
        """POST with dm_timeout=0 returns 400."""
        resp = client.post("/api/settings", json={"dm_timeout": 0})
        assert resp.status_code == 400

    def test_invalid_timeout_negative(self, client):
        """POST with timeout=-1 returns 400."""
        resp = client.post("/api/settings", json={"timeout": -1})
        assert resp.status_code == 400

    def test_invalid_timeout_float(self, client):
        """POST with timeout=30.5 returns 400 (must be int)."""
        resp = client.post("/api/settings", json={"timeout": 30.5})
        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # Validation: multiple errors at once
    # ------------------------------------------------------------------

    def test_multiple_validation_errors(self, client):
        """POST with multiple invalid fields returns all errors."""
        resp = client.post(
            "/api/settings",
            json={
                "dm_max_tokens": 0,
                "dm_temperature": 3.0,
                "dm_timeout": -1,
            },
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "errors" in data
        assert len(data["errors"]) >= 3

    def test_error_messages_are_descriptive(self, client):
        """POST validation errors have specific field messages."""
        resp = client.post(
            "/api/settings",
            json={
                "dm_max_tokens": 0,
                "dm_temperature": 3.0,
                "dm_timeout": -5,
            },
        )
        data = resp.get_json()
        assert "positive integer" in data["errors"]["dm_max_tokens"].lower()
        assert "between" in data["errors"]["dm_temperature"].lower()
        assert "positive integer" in data["errors"]["dm_timeout"].lower()

    # ------------------------------------------------------------------
    # ConfigManager validation failure
    # ------------------------------------------------------------------

    def test_save_failure_returns_400(self, client, monkeypatch):
        """POST returns 400 when ConfigManager.save_config raises."""
        manager = ConfigManager(__file__)

        with (
            patch.object(
                manager, "save_config", side_effect=ConfigError("Invalid URL")
            ),
            patch.object(manager, "get_config", side_effect=ConfigError("not found")),
        ):
            monkeypatch.setattr("app.routes.settings._config_manager", manager)
            # Send data that will make ProviderConfig invalid
            resp = client.post(
                "/api/settings",
                json={
                    "base_url": "not-a-url",
                    "model": "",
                },
            )

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "error" in data

    # ------------------------------------------------------------------
    # Round-trip
    # ------------------------------------------------------------------

    def test_round_trip(self, client, tmp_path, monkeypatch):
        """POST then GET returns consistent settings."""
        manager = ConfigManager(tmp_path)
        monkeypatch.setattr("app.routes.settings._config_manager", manager)

        # Update some settings
        resp = client.post(
            "/api/settings",
            json={
                "base_url": "http://roundtrip:11434",
                "model": "roundtrip-model",
                "dm_max_tokens": 8192,
            },
        )
        assert resp.status_code == 200

        # POST response should include both provider and agent changes
        post_settings = resp.get_json()["settings"]
        assert post_settings["base_url"] == "http://roundtrip:11434"
        assert post_settings["model"] == "roundtrip-model"
        assert post_settings["dm_max_tokens"] == 8192

        # GET should reflect persisted provider config; agent-specific
        # fields are NOT persisted and return to defaults.
        resp2 = client.get("/api/settings")
        assert resp2.status_code == 200
        settings = resp2.get_json()["settings"]
        assert settings["base_url"] == "http://roundtrip:11434"
        assert settings["model"] == "roundtrip-model"
        assert settings["dm_max_tokens"] == 4096  # back to default
        assert settings["npc_max_tokens"] == 1024  # unchanged default
