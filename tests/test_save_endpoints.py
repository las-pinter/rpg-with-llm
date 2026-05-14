"""Tests for the save/load/reset game endpoints."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest

from app.server import app
from app.world.model import WorldState
from app.world.persistence import WorldStorage


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/save
# ---------------------------------------------------------------------------


class TestSaveEndpoint:
    """Tests for POST /api/save."""

    def test_save_success(self, client):
        """POST with valid state and name returns 200 with metadata."""
        with patch("app.server._storage.save", return_value="20260514_120000_000000"):
            resp = client.post(
                "/api/save",
                json={"state": {"version": "1.0"}, "name": "my_save"},
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["name"] == "my_save"
        assert data["timestamp"] == "20260514_120000_000000"

    def test_save_autosave_default_name(self, client):
        """POST with state but no name defaults to 'autosave'."""
        with patch("app.server._storage.save", return_value="20260514_120000_000000"):
            resp = client.post(
                "/api/save",
                json={"state": {"version": "1.0"}},
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["name"] == "autosave"

    def test_save_missing_state(self, client):
        """POST without 'state' returns 400."""
        resp = client.post("/api/save", json={"name": "my_save"})

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "state" in data["error"]

    def test_save_invalid_json(self, client):
        """POST with non-JSON body returns 400."""
        resp = client.post(
            "/api/save",
            data="not json",
            content_type="text/plain",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "Invalid JSON body"

    def test_save_storage_error(self, client):
        """When storage.save raises, the endpoint returns 500."""
        with patch(
            "app.server._storage.save",
            side_effect=ValueError("Invalid save name"),
        ):
            resp = client.post(
                "/api/save",
                json={"state": {"version": "1.0"}},
            )

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False
        assert "Invalid save name" in data["error"]

    def test_save_with_non_dict_state_returns_500(self, client):
        """POST with non-dict state value returns 500.

        When ``state`` is a string (or any non-dict), ``from_dict()``
        raises an ``AttributeError`` which propagates as a 500.
        """
        resp = client.post(
            "/api/save",
            json={"state": "not-a-dict", "name": "test"},
        )

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False
        # The error message varies by type -- just verify we got one
        assert isinstance(data.get("error"), str)
        assert len(data["error"]) > 0

    def test_save_with_null_state_returns_500(self, client):
        """POST with null state value returns 500.

        When ``state`` is ``None``, ``from_dict()`` raises an
        ``AttributeError`` which propagates as a 500.
        """
        resp = client.post(
            "/api/save",
            json={"state": None, "name": "test"},
        )

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False
        assert isinstance(data.get("error"), str)
        assert len(data["error"]) > 0

    def test_save_malformed_json_with_json_content_type(self, client):
        """POST with malformed JSON but correct content-type returns 400.

        When Content-Type is application/json but body is not valid
        JSON, ``request.get_json(silent=True)`` returns ``None``
        triggering the second guard clause.
        """
        resp = client.post(
            "/api/save",
            data="not valid json at all",
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert data["error"] == "Invalid JSON body"


# ---------------------------------------------------------------------------
# GET /api/saves
# ---------------------------------------------------------------------------


class TestListSavesEndpoint:
    """Tests for GET /api/saves."""

    def test_list_saves_empty(self, client):
        """GET returns 200 with an empty saves list."""
        with patch("app.server._storage.list_saves", return_value=[]):
            resp = client.get("/api/saves")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["saves"] == []

    def test_list_saves_with_data(self, client):
        """GET returns 200 with save metadata."""
        mock_saves = [
            {"name": "save1", "timestamp": "20260514_120000_000000"},
            {"name": "save2", "timestamp": "20260514_130000_000000"},
        ]
        with patch("app.server._storage.list_saves", return_value=mock_saves):
            resp = client.get("/api/saves")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["saves"] == mock_saves


# ---------------------------------------------------------------------------
# POST /api/load/<name>
# ---------------------------------------------------------------------------


class TestLoadEndpoint:
    """Tests for POST /api/load/<name>."""

    def test_load_success(self, client):
        """POST with a valid save name returns the state dict."""
        real_state = WorldState(current_location="forest")
        with patch("app.server._storage.load", return_value=real_state):
            resp = client.post("/api/load/my_save")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["state"]["current_location"] == "forest"

    def test_load_not_found(self, client):
        """POST with a non-existent save returns 404."""
        with patch(
            "app.server._storage.load",
            side_effect=FileNotFoundError("Save 'ghost' not found"),
        ):
            resp = client.post("/api/load/ghost")

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False
        assert "not found" in data["error"]

    def test_load_corrupt(self, client):
        """POST with a corrupt save file returns 400."""
        with patch(
            "app.server._storage.load",
            side_effect=ValueError("Save file is corrupt"),
        ):
            resp = client.post("/api/load/corrupted")

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "corrupt" in data["error"]

    def test_load_with_unexpected_exception_returns_500(self, client):
        """When storage.load raises an unexpected exception, returns 500.

        The load endpoint only handles ``FileNotFoundError`` and
        ``ValueError`` explicitly.  Any other exception type is
        caught by Flask's default error handler (since
        ``app.testing`` is ``False`` by default), which returns a
        500 response.
        """
        with patch(
            "app.server._storage.load",
            side_effect=PermissionError("Access denied"),
        ):
            resp = client.post("/api/load/my_save")

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/reset
# ---------------------------------------------------------------------------


class TestResetEndpoint:
    """Tests for POST /api/reset."""

    def test_reset_returns_fresh_state(self, client):
        """POST returns 200 with a fresh default world state."""
        resp = client.post("/api/reset")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert "state" in data

        # Verify it's a well-formed default world state
        state = data["state"]
        assert state["version"] == "1.0"
        assert state["current_location"] == "starting_village"
        assert state["turn_count"] == 0
        assert state["inventory"] == []
        assert state["locations"] == {}
        assert state["quests"] == {}


# ---------------------------------------------------------------------------
# Integration tests -- real WorldStorage through Flask endpoints
# ---------------------------------------------------------------------------


class TestSaveLoadIntegration:
    """Integration tests exercising real storage through Flask endpoints.

    These tests replace the module-level ``_storage`` singleton with a
    real :class:`WorldStorage` backed by a temporary directory, verifying
    the full request -> JSON -> persistence -> response round-trip.
    """

    @pytest.fixture
    def real_storage(self) -> WorldStorage:
        """Create a real WorldStorage in a temporary directory.

        Each test invocation gets its own isolated directory.
        """
        tmp_dir = tempfile.mkdtemp()
        return WorldStorage(tmp_dir)

    # ------------------------------------------------------------------
    # Save -> List -> Load round-trip
    # ------------------------------------------------------------------

    def test_save_and_load_round_trip(self, client, real_storage):
        """Save a state, list it, then load it through real endpoints."""
        with patch("app.server._storage", real_storage):
            # --- Save ---------------------------------------------------
            resp = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "current_location": "dungeon",
                        "turn_count": 42,
                        "inventory": ["sword", "shield"],
                    },
                    "name": "integration_test",
                },
            )
            assert resp.status_code == 200
            save_data = resp.get_json()
            assert save_data["ok"] is True
            assert save_data["name"] == "integration_test"
            assert isinstance(save_data["timestamp"], str)
            assert len(save_data["timestamp"]) > 0

            # --- List ---------------------------------------------------
            resp = client.get("/api/saves")
            assert resp.status_code == 200
            list_data = resp.get_json()
            assert list_data["ok"] is True
            assert len(list_data["saves"]) == 1
            assert list_data["saves"][0]["turn_count"] == 42

            # --- Load ---------------------------------------------------
            resp = client.post("/api/load/integration_test")
            assert resp.status_code == 200
            state = resp.get_json()["state"]
            assert state["current_location"] == "dungeon"
            assert state["turn_count"] == 42
            assert state["inventory"] == ["sword", "shield"]
            assert state["version"] == "1.0"

    # ------------------------------------------------------------------
    # Overwrite
    # ------------------------------------------------------------------

    def test_save_overwrite_with_real_storage(self, client, real_storage):
        """Saving twice with the same name overwrites; load gets latest."""
        with patch("app.server._storage", real_storage):
            client.post(
                "/api/save",
                json={"state": {"version": "1.0", "turn_count": 1}, "name": "dup"},
            )
            client.post(
                "/api/save",
                json={"state": {"version": "1.0", "turn_count": 99}, "name": "dup"},
            )

            resp = client.post("/api/load/dup")
            assert resp.status_code == 200
            assert resp.get_json()["state"]["turn_count"] == 99

    # ------------------------------------------------------------------
    # List saves
    # ------------------------------------------------------------------

    def test_list_saves_empty_with_real_storage(self, client, real_storage):
        """List saves returns empty list when no saves exist."""
        with patch("app.server._storage", real_storage):
            resp = client.get("/api/saves")

            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["saves"] == []

    def test_list_saves_multiple_with_real_storage(self, client, real_storage):
        """Multiple saves all appear in the listing."""
        with patch("app.server._storage", real_storage):
            client.post("/api/save", json={"state": {}, "name": "save_a"})
            client.post("/api/save", json={"state": {}, "name": "save_b"})
            client.post("/api/save", json={"state": {}, "name": "save_c"})

            resp = client.get("/api/saves")
            assert resp.status_code == 200
            assert len(resp.get_json()["saves"]) == 3

    # ------------------------------------------------------------------
    # Default name
    # ------------------------------------------------------------------

    def test_save_default_name_with_real_storage(self, client, real_storage):
        """Save without a name defaults to 'autosave' with real storage."""
        with patch("app.server._storage", real_storage):
            resp = client.post("/api/save", json={"state": {}})
            assert resp.get_json()["name"] == "autosave"

            resp = client.get("/api/saves")
            assert len(resp.get_json()["saves"]) == 1

    # ------------------------------------------------------------------
    # Load non-existent
    # ------------------------------------------------------------------

    def test_load_nonexistent_with_real_storage(self, client, real_storage):
        """Loading a non-existent save returns 404 with real storage."""
        with patch("app.server._storage", real_storage):
            resp = client.post("/api/load/ghost")

            assert resp.status_code == 404
            data = resp.get_json()
            assert data["ok"] is False
            assert "not found" in data["error"]
