"""Tests for the save/load/reset game endpoints."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest

from app.save_engine.manager import SaveGameManager
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
        """POST with valid state and name returns 200 with slug."""
        with (
            patch("app.routes.saves._save_manager.save") as mock_save,
            patch(
                "app.routes.saves._storage._generate_slug", return_value="test-slug"
            ) as mock_gen_slug,
            patch("app.routes.saves._storage._update_index") as mock_upd_index,
        ):
            resp = client.post(
                "/api/save",
                json={
                    "state": {"version": "1.0"},
                    "name": "my_save",
                    "character": {"name": "Hero", "id": "1"},
                },
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["slug"] == "test-slug"

    def test_save_autosave_default_name(self, client):
        """POST with state but no name defaults to a timestamped adventure name."""
        with (
            patch("app.routes.saves._save_manager.save") as mock_save,
            patch(
                "app.routes.saves._storage._generate_slug", return_value="test-slug"
            ) as mock_gen_slug,
            patch("app.routes.saves._storage._update_index") as mock_upd_index,
        ):
            resp = client.post(
                "/api/save",
                json={"state": {"version": "1.0"}},
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["slug"] == "test-slug"
        # Verify default name was passed to _update_index
        metadata = mock_upd_index.call_args[0][1]
        assert metadata["name"].startswith("Adventure - ")

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
        """When save_manager.save raises ValueError, the endpoint returns 400."""
        with (
            patch(
                "app.routes.saves._save_manager.save",
                side_effect=ValueError("Schema validation failed"),
            ),
            patch("app.routes.saves._storage._generate_slug", return_value="test-slug"),
            patch("app.routes.saves._storage._update_index"),
        ):
            resp = client.post(
                "/api/save",
                json={"state": {"version": "1.0"}},
            )

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "Schema validation failed" in data["error"]

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

    def test_save_with_narrative_entries(self, client):
        """POST with narrative_entries passes them to save_manager.save()."""
        with (
            patch("app.routes.saves._save_manager.save") as mock_save,
            patch(
                "app.routes.saves._storage._generate_slug", return_value="test-slug"
            ) as mock_gen_slug,
            patch("app.routes.saves._storage._update_index") as mock_upd_index,
        ):
            resp = client.post(
                "/api/save",
                json={
                    "state": {"version": "1.0"},
                    "name": "test",
                    "narrative_entries": [
                        {
                            "id": "1",
                            "content": "hero enters dungeon",
                            "type": "narrative",
                        }
                    ],
                },
            )

        assert resp.status_code == 200
        buckets_data = mock_save.call_args[0][1]
        assert "narrative_entries" in buckets_data
        assert buckets_data["narrative_entries"]["entries"] == [
            {"id": "1", "content": "hero enters dungeon", "type": "narrative"}
        ]

    def test_save_with_summary(self, client):
        """POST with summary passes summary dict to save_manager.save()."""
        with (
            patch("app.routes.saves._save_manager.save") as mock_save,
            patch(
                "app.routes.saves._storage._generate_slug", return_value="test-slug"
            ) as mock_gen_slug,
            patch("app.routes.saves._storage._update_index") as mock_upd_index,
        ):
            summary_payload = {
                "technical_summary": ["tech_entry"],
                "story_summary": ["story_entry"],
                "meta_summary": ["meta_entry"],
            }
            resp = client.post(
                "/api/save",
                json={
                    "state": {"version": "1.0"},
                    "name": "test",
                    "summary": summary_payload,
                },
            )

        assert resp.status_code == 200
        buckets_data = mock_save.call_args[0][1]
        assert "summary" in buckets_data
        assert buckets_data["summary"] == summary_payload

    def test_save_legacy_embedded_character(self, client):
        """Legacy clients sending only state with _character embedded still work."""
        with (
            patch("app.routes.saves._save_manager.save") as mock_save,
            patch(
                "app.routes.saves._storage._generate_slug", return_value="test-slug"
            ) as mock_gen_slug,
            patch("app.routes.saves._storage._update_index") as mock_upd_index,
        ):
            resp = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "_character": {"name": "LegacyHero", "id": "legacy-1"},
                    },
                    "name": "legacy_test",
                },
            )

        assert resp.status_code == 200
        buckets_data = mock_save.call_args[0][1]
        # Character should be extracted and passed to the character bucket
        assert "character" in buckets_data
        char_obj = buckets_data["character"]
        from app.character.model import Character

        assert isinstance(char_obj, Character)
        assert char_obj.name == "LegacyHero"
        # WorldState should NOT have _character embedded
        assert buckets_data["world_state"]._character is None


# ---------------------------------------------------------------------------
# GET /api/saves
# ---------------------------------------------------------------------------


class TestListSavesEndpoint:
    """Tests for GET /api/saves."""

    def test_list_saves_empty(self, client):
        """GET returns 200 with an empty saves list."""
        with patch("app.routes.saves._storage.list_saves", return_value=[]):
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
        with patch("app.routes.saves._storage.list_saves", return_value=mock_saves):
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
        with patch(
            "app.routes.saves._save_manager.load",
            return_value={"world_state": real_state, "character": None},
        ):
            resp = client.post("/api/load/my_save")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["state"]["current_location"] == "forest"
        assert "character" not in data

    def test_load_success_with_character(self, client):
        """POST returns both state and character when character is present."""
        real_state = WorldState(current_location="forest")
        from app.character.model import Character

        mock_char = Character.from_dict({"name": "Hero", "id": "char-1"})
        with patch(
            "app.routes.saves._save_manager.load",
            return_value={"world_state": real_state, "character": mock_char},
        ):
            resp = client.post("/api/load/my_save")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["state"]["current_location"] == "forest"
        assert data["character"]["name"] == "Hero"

    def test_load_not_found(self, client):
        """POST with a non-existent save returns 404."""
        with patch(
            "app.routes.saves._save_manager.load",
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
            "app.routes.saves._save_manager.load",
            side_effect=ValueError("Save file is corrupt"),
        ):
            resp = client.post("/api/load/corrupted")

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["ok"] is False
        assert "corrupt" in data["error"]

    def test_load_with_unexpected_exception_returns_500(self, client):
        """When save_manager.load raises an unexpected exception, returns 500.

        The load endpoint only handles ``FileNotFoundError`` and
        ``ValueError`` explicitly.  Any other exception type causes a
        500 response.
        """
        with patch(
            "app.routes.saves._save_manager.load",
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


@pytest.fixture
def real_save_manager() -> SaveGameManager:
    """Create a real SaveGameManager in a temporary directory.

    Each test invocation gets its own isolated directory.
    """
    tmp_dir = tempfile.mkdtemp()
    manager = SaveGameManager(tmp_dir)
    manager.register_defaults()
    return manager


@pytest.fixture
def real_storage() -> WorldStorage:
    """Create a real WorldStorage in a temporary directory.

    Each test invocation gets its own isolated directory.
    """
    tmp_dir = tempfile.mkdtemp()
    return WorldStorage(tmp_dir)


class TestSaveLoadIntegration:
    """Integration tests exercising real storage through Flask endpoints.

    These tests replace the module-level ``_save_manager`` and ``_storage``
    singletons with real implementations backed by a temporary directory,
    verifying the full request -> JSON -> persistence -> response round-trip.
    """

    # ------------------------------------------------------------------
    # Save -> List -> Load round-trip
    # ------------------------------------------------------------------

    def test_save_and_load_round_trip(self, client, real_save_manager):
        """Save a state, list it, then load it through real endpoints."""
        with (
            patch("app.routes.saves._save_manager", real_save_manager),
            patch("app.routes.saves._storage", real_save_manager.storage),
        ):
            # --- Save ---------------------------------------------------
            resp = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "hero-1",
                        "character_name": "Hero",
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
            assert isinstance(save_data["slug"], str)
            assert len(save_data["slug"]) > 0

            slug = save_data["slug"]

            # --- List ---------------------------------------------------
            resp = client.get("/api/saves")
            assert resp.status_code == 200
            list_data = resp.get_json()
            assert list_data["ok"] is True
            assert len(list_data["saves"]) == 1
            assert list_data["saves"][0]["turn_count"] == 42

            # --- Load ---------------------------------------------------
            resp = client.post(f"/api/load/{slug}")
            assert resp.status_code == 200
            state = resp.get_json()["state"]
            assert state["current_location"] == "dungeon"
            assert state["turn_count"] == 42
            assert state["inventory"] == ["sword", "shield"]
            assert state["version"] == "1.0"

    # ------------------------------------------------------------------
    # Overwrite
    # ------------------------------------------------------------------

    def test_save_overwrite_with_real_storage(self, client, real_save_manager):
        """Saving twice with the same name; load gets the latest."""
        with (
            patch("app.routes.saves._save_manager", real_save_manager),
            patch("app.routes.saves._storage", real_save_manager.storage),
        ):
            resp1 = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                        "turn_count": 1,
                    },
                    "name": "dup",
                },
            )
            slug1 = resp1.get_json()["slug"]
            resp2 = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                        "turn_count": 99,
                    },
                    "name": "dup",
                },
            )
            slug2 = resp2.get_json()["slug"]

            # Different slugs because each has a unique timestamp
            assert slug1 != slug2

            resp = client.post(f"/api/load/{slug2}")
            assert resp.status_code == 200
            assert resp.get_json()["state"]["turn_count"] == 99

    # ------------------------------------------------------------------
    # List saves
    # ------------------------------------------------------------------

    def test_list_saves_empty_with_real_storage(self, client, real_save_manager):
        """List saves returns empty list when no saves exist."""
        with patch("app.routes.saves._storage", real_save_manager.storage):
            resp = client.get("/api/saves")

            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["saves"] == []

    def test_list_saves_multiple_with_real_storage(self, client, real_save_manager):
        """Multiple saves all appear in the listing."""
        with (
            patch("app.routes.saves._save_manager", real_save_manager),
            patch("app.routes.saves._storage", real_save_manager.storage),
        ):
            client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                    },
                    "name": "save_a",
                },
            )
            client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                    },
                    "name": "save_b",
                },
            )
            client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                    },
                    "name": "save_c",
                },
            )

            resp = client.get("/api/saves")
            assert resp.status_code == 200
            assert len(resp.get_json()["saves"]) == 3

    # ------------------------------------------------------------------
    # Default name
    # ------------------------------------------------------------------

    def test_save_default_name_with_real_storage(self, client, real_save_manager):
        """Save without a name returns a slug."""
        with (
            patch("app.routes.saves._save_manager", real_save_manager),
            patch("app.routes.saves._storage", real_save_manager.storage),
        ):
            resp = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                    }
                },
            )
            slug = resp.get_json()["slug"]
            assert isinstance(slug, str)
            assert len(slug) > 0

            resp = client.get("/api/saves")
            assert len(resp.get_json()["saves"]) == 1

    # ------------------------------------------------------------------
    # Load non-existent
    # ------------------------------------------------------------------

    def test_load_nonexistent_with_real_storage(self, client, real_save_manager):
        """Loading a non-existent save returns 404 with real storage."""
        with (
            patch("app.routes.saves._save_manager", real_save_manager),
            patch("app.routes.saves._storage", real_save_manager.storage),
        ):
            resp = client.post("/api/load/ghost")

            assert resp.status_code == 404
            data = resp.get_json()
            assert data["ok"] is False
            assert "not found" in data["error"]


# ---------------------------------------------------------------------------
# DELETE /api/delete/<name>
# ---------------------------------------------------------------------------


class TestDeleteSaveEndpoint:
    """Tests for DELETE /api/delete/<name>."""

    def test_delete_success(self, client, real_save_manager):
        """Deleting an existing save returns 200 with ok=True."""
        with (
            patch("app.routes.saves._save_manager", real_save_manager),
            patch("app.routes.saves._storage", real_save_manager.storage),
        ):
            # First save something
            resp = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                    },
                    "name": "to_delete",
                },
            )
            slug = resp.get_json()["slug"]

            resp = client.delete(f"/api/delete/{slug}")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

        # Verify it's actually deleted
        with patch("app.routes.saves._storage", real_save_manager.storage):
            resp2 = client.get("/api/saves")
            assert len(resp2.get_json()["saves"]) == 0

    def test_delete_not_found(self, client, real_save_manager):
        """Deleting a non-existent save returns 404."""
        with patch("app.routes.saves._storage", real_save_manager.storage):
            resp = client.delete("/api/delete/ghost")

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["ok"] is False
        assert "not found" in data["error"]

    def test_delete_with_real_storage_round_trip(self, client, real_save_manager):
        """Save, list, delete, list again — save should disappear."""
        with (
            patch("app.routes.saves._save_manager", real_save_manager),
            patch("app.routes.saves._storage", real_save_manager.storage),
        ):
            resp = client.post(
                "/api/save",
                json={
                    "state": {
                        "version": "1.0",
                        "character_id": "h1",
                        "character_name": "H",
                        "turn_count": 5,
                    },
                    "name": "del_test",
                },
            )
            slug = resp.get_json()["slug"]

            # Verify save exists
            resp = client.get("/api/saves")
            assert len(resp.get_json()["saves"]) == 1

            # Delete it
            resp = client.delete(f"/api/delete/{slug}")
            assert resp.status_code == 200
            assert resp.get_json()["ok"] is True

            # Verify save is gone
            resp = client.get("/api/saves")
            assert len(resp.get_json()["saves"]) == 0
