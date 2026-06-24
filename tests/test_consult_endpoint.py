"""Tests for POST /api/game/consult endpoint.

The consultation endpoint is a stateless Q&A — it never touches game state.
It returns 200 with {"ok": true, "answer": "..."} for valid input, or 400
when the input is missing/empty.  Optional fields (character, state, provider)
are all accepted without error.
"""

from __future__ import annotations

import pytest

from app.server import app


@pytest.fixture
def client():
    """Flask test client — no monkeypatching needed (consult is stateless)."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestConsultEndpoint:
    """Tests for POST /api/game/consult."""

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_consult_returns_answer(self, client):
        """Valid input returns 200 with ok=true and a non-empty answer."""
        response = client.post(
            "/api/game/consult",
            json={"input": "What do I see?"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_consult_answer_is_string(self, client):
        """The answer field is always a string."""
        response = client.post(
            "/api/game/consult",
            json={"input": "What do I see?"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data["answer"], str)

    # ------------------------------------------------------------------
    # Input validation — missing / empty / whitespace
    # ------------------------------------------------------------------

    def test_consult_missing_input_returns_400(self, client):
        """Missing 'input' key returns 400."""
        response = client.post(
            "/api/game/consult",
            json={},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        assert "error" in data

    def test_consult_empty_input_returns_400(self, client):
        """Empty string input returns 400."""
        response = client.post(
            "/api/game/consult",
            json={"input": ""},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False

    def test_consult_whitespace_input_returns_400(self, client):
        """Whitespace-only input returns 400."""
        response = client.post(
            "/api/game/consult",
            json={"input": "   "},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        assert "error" in data

    def test_consult_null_input_returns_400(self, client):
        """Null input value returns 400."""
        response = client.post(
            "/api/game/consult",
            json={"input": None},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False

    # ------------------------------------------------------------------
    # Optional fields — character, state, provider
    # ------------------------------------------------------------------

    def test_consult_with_character_snapshot(self, client):
        """Request with character data returns 200."""
        response = client.post(
            "/api/game/consult",
            json={
                "input": "Check my stats?",
                "character": {
                    "name": "Hero",
                    "class": "Fighter",
                    "level": 5,
                },
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "answer" in data

    def test_consult_with_world_state_snapshot(self, client):
        """Request with world state data returns 200."""
        response = client.post(
            "/api/game/consult",
            json={
                "input": "Where am I?",
                "state": {
                    "current_location": "Dark Cave",
                    "turn_count": 3,
                    "active_npcs": ["Goblin"],
                    "established_facts": ["It is dark"],
                },
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "answer" in data

    def test_consult_with_provider_config(self, client):
        """Request with provider config returns 200.

        Even if the provider is unreachable, the agent returns a canned
        "unavailable" message — never a 500.
        """
        response = client.post(
            "/api/game/consult",
            json={
                "input": "Hello?",
                "provider": {
                    "base_url": "http://localhost:11434",
                    "model": "test-model",
                },
            },
        )
        # Endpoint should never crash — 200 with answer (possibly unavailable)
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "answer" in data

    def test_consult_with_save_slug(self, client):
        """Request with save_slug returns 200 (handles missing log gracefully)."""
        response = client.post(
            "/api/game/consult",
            json={
                "input": "What happened last session?",
                "save_slug": "test-slug-12345",
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "answer" in data

    def test_consult_with_all_optionals(self, client):
        """Request with all optional fields at once returns 200."""
        response = client.post(
            "/api/game/consult",
            json={
                "input": "Give me a full status report.",
                "character": {"name": "Gorstag", "class": "Barbarian", "level": 3},
                "state": {
                    "current_location": "Goblin Fortress",
                    "turn_count": 7,
                    "active_npcs": ["Goblin King", "Goblin Shaman"],
                    "established_facts": ["The king wants tribute"],
                },
                "save_slug": "gorstag-20260615",
                "provider": {
                    "base_url": "http://localhost:11434",
                    "model": "llama3.2",
                },
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert "answer" in data

    # ------------------------------------------------------------------
    # Input validation — malformed body
    # ------------------------------------------------------------------

    def test_consult_non_json_body_returns_400(self, client):
        """Non-JSON body with text/plain returns 400."""
        response = client.post(
            "/api/game/consult",
            data="not json at all",
            content_type="text/plain",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False

    def test_consult_malformed_json_with_json_content_type(self, client):
        """Malformed JSON with application/json returns 400."""
        response = client.post(
            "/api/game/consult",
            data="not valid json at all",
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["ok"] is False
        assert "error" in data

    # ------------------------------------------------------------------
    # Response structure
    # ------------------------------------------------------------------

    def test_consult_response_has_expected_keys(self, client):
        """Successful response always contains ``ok`` and ``answer``."""
        response = client.post(
            "/api/game/consult",
            json={"input": "Who are you?"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert set(data.keys()) == {"ok", "answer"}

    def test_consult_error_response_has_expected_keys(self, client):
        """Error response always contains ``ok`` and ``error``."""
        response = client.post(
            "/api/game/consult",
            json={},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert set(data.keys()) == {"ok", "error"}
