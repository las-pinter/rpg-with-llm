"""Tests for the World State File Persistence Layer -- Phase 3, Task 3.2."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from app.server import app as flask_app
from app.world.model import (
    DMNotes,
    FactionStanding,
    Location,
    Quest,
    WorldState,
)
from app.world.persistence import WorldStorage

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage() -> WorldStorage:
    """Create a WorldStorage backed by a temporary directory."""
    tmp_dir = tempfile.mkdtemp()
    return WorldStorage(tmp_dir)


@pytest.fixture
def sample_world() -> WorldState:
    """A non-trivial WorldState for save/load round-trip tests."""
    tavern = Location(
        id="tavern",
        name="The Rusty Nail",
        description="A warm, smoky tavern.",
        exits={"out": "town_square"},
        tags=["safe_zone"],
    )
    quest = Quest(
        id="q_main",
        name="Find the Artifact",
        description="Locate the hidden artifact.",
        status="active",
        objectives=["Enter the cave", "Retrieve the orb"],
    )
    guild = FactionStanding(
        faction_id="adventurers",
        name="Adventurers' Guild",
        standing=50,
    )
    notes = DMNotes(
        plot_threads=["The mayor is a shapeshifter"],
        secrets=["Trapdoor behind the throne"],
    )
    return WorldState(
        version="1.0",
        character_id="hero_42",
        current_location="tavern",
        locations={"tavern": tavern},
        quests={"q_main": quest},
        faction_standings={"adventurers": guild},
        inventory=["rusty_sword"],
        dm_notes=notes,
        turn_count=7,
    )


@pytest.fixture
def client():
    """Create a Flask test client (storage patched per-test as needed)."""
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# TestWorldStorage
# ---------------------------------------------------------------------------


class TestWorldStorage:
    """Test suite for WorldStorage."""

    # ------------------------------------------------------------------
    # Automatic directory creation
    # ------------------------------------------------------------------

    def test_saves_dir_is_created_automatically(self) -> None:
        """The saves/ subdirectory must exist after construction."""
        with tempfile.TemporaryDirectory() as tmp:
            store = WorldStorage(tmp)
            assert store.saves_dir.is_dir()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def test_save_creates_file(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving a WorldState must create the expected JSON file."""
        storage.save(sample_world, name="test_save")
        save_path = storage.saves_dir / "test_save.json"
        assert save_path.is_file()

    def test_save_returns_timestamp(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """The save ID returned must be a timestamp string."""
        save_id = storage.save(sample_world, name="ts_test")
        # Format: YYYYMMDD_HHMMSS_ffffff (22 chars with microseconds)
        assert len(save_id) == 22
        assert save_id[8] == "_"
        assert save_id[:8].isdigit()
        assert save_id[9:15].isdigit()
        assert save_id[15] == "_"
        assert save_id[16:].isdigit()

    def test_save_file_contains_valid_json(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """The contents of the save file must be parseable JSON."""
        storage.save(sample_world, name="json_test")
        save_path = storage.saves_dir / "json_test.json"
        with open(save_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "version" in data
        assert "turn_count" in data
        assert data["turn_count"] == 7

    # ------------------------------------------------------------------
    # Round-trip (save + load)
    # ------------------------------------------------------------------

    def test_load_returns_identical_world_state(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Round-trip: save then load must yield an identical WorldState."""
        storage.save(sample_world, name="roundtrip")
        restored = storage.load("roundtrip")

        assert restored.version == sample_world.version
        assert restored.character_id == sample_world.character_id
        assert restored.current_location == sample_world.current_location
        assert restored.turn_count == sample_world.turn_count
        assert restored.inventory == sample_world.inventory

        # Nested objects
        assert restored.locations["tavern"].name == "The Rusty Nail"
        assert restored.locations["tavern"].exits == {"out": "town_square"}
        assert restored.locations["tavern"].tags == ["safe_zone"]
        assert restored.quests["q_main"].objectives == [
            "Enter the cave",
            "Retrieve the orb",
        ]
        assert restored.faction_standings["adventurers"].standing == 50
        assert restored.dm_notes.plot_threads == ["The mayor is a shapeshifter"]
        assert restored.dm_notes.secrets == ["Trapdoor behind the throne"]

        # Different object identity
        assert restored is not sample_world

    def test_load_after_multiple_saves(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving twice under different names -- both must load correctly."""
        storage.save(sample_world, name="save_one")
        storage.save(sample_world, name="save_two")

        loaded_one = storage.load("save_one")
        loaded_two = storage.load("save_two")

        assert loaded_one.turn_count == 7
        assert loaded_two.turn_count == 7

    # ------------------------------------------------------------------
    # List saves
    # ------------------------------------------------------------------

    def test_list_saves_empty_initially(self, storage: WorldStorage) -> None:
        """No saves means list_saves returns an empty list."""
        assert storage.list_saves() == []

    def test_list_saves_after_saving(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """After saving, list_saves must return metadata including the save."""
        storage.save(sample_world, name="autosave")
        saves = storage.list_saves()
        assert len(saves) == 1

        meta = saves[0]
        assert "timestamp" in meta
        assert meta["turn_count"] == 7

    def test_list_saves_multiple_entries(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Multiple saves must all appear in the listing."""
        storage.save(sample_world, name="save_a")
        storage.save(sample_world, name="save_b")
        storage.save(sample_world, name="save_c")

        saves = storage.list_saves()
        assert len(saves) == 3

    def test_list_saves_metadata_fields(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Each entry in list_saves must have the expected metadata keys."""
        storage.save(sample_world, name="meta_test")
        saves = storage.list_saves()
        assert len(saves) == 1

        meta = saves[0]
        assert "timestamp" in meta
        assert "character_name" in meta
        assert "level" in meta
        assert "turn_count" in meta
        assert meta["turn_count"] == 7

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def test_delete_removes_file(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Deleting a save must remove its JSON file."""
        storage.save(sample_world, name="delete_me")
        save_path = storage.saves_dir / "delete_me.json"
        assert save_path.is_file()

        storage.delete("delete_me")
        assert not save_path.exists()

    def test_delete_removes_index_entry(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Deleting a save must also remove it from the index."""
        storage.save(sample_world, name="gone_soon")
        assert len(storage.list_saves()) == 1

        storage.delete("gone_soon")
        assert len(storage.list_saves()) == 0

    def test_delete_non_existent_raises_error(self, storage: WorldStorage) -> None:
        """Deleting a save that doesn't exist must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            storage.delete("does_not_exist")

    # ------------------------------------------------------------------
    # Save exists
    # ------------------------------------------------------------------

    def test_save_exists_returns_true_when_save_present(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """save_exists must return True for a saved game."""
        storage.save(sample_world, name="check_me")
        assert storage.save_exists("check_me") is True

    def test_save_exists_returns_false_when_save_absent(
        self, storage: WorldStorage
    ) -> None:
        """save_exists must return False for a non-existent save."""
        assert storage.save_exists("non_existent") is False

    # ------------------------------------------------------------------
    # Load errors
    # ------------------------------------------------------------------

    def test_load_non_existent_raises_error(self, storage: WorldStorage) -> None:
        """Loading a non-existent save must raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            storage.load("ghost_save")

    def test_load_corrupt_file_raises_error(self, storage: WorldStorage) -> None:
        """Loading a corrupt (invalid JSON) file must raise ValueError."""
        bad_file = storage.saves_dir / "corrupt.json"
        bad_file.write_text("this is not json", encoding="utf-8")

        with pytest.raises(ValueError, match="corrupt|invalid JSON"):
            storage.load("corrupt")

    def test_load_file_with_non_dict_json_raises_error(
        self, storage: WorldStorage
    ) -> None:
        """Loading a JSON file that isn't a dict must raise ValueError."""
        bad_file = storage.saves_dir / "not_a_dict.json"
        bad_file.write_text('"just a string"', encoding="utf-8")

        with pytest.raises(ValueError, match="corrupt|expected a JSON object"):
            storage.load("not_a_dict")

    # ------------------------------------------------------------------
    # Atomic write pattern
    # ------------------------------------------------------------------

    def test_atomic_write_tmp_file_is_used(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """During save, tmp files are created before final files."""
        original_rename = os.rename
        original_replace = os.replace
        tmp_paths: list[Path] = []

        def tracking_rename(src: str, dst: str) -> None:
            src_path = Path(src)
            if src_path.suffix == ".tmp":
                assert src_path.exists(), (
                    f"Temp file {src_path} should exist before rename"
                )
                tmp_paths.append(src_path)
            original_rename(src, dst)

        def tracking_replace(src: str, dst: str) -> None:
            src_path = Path(src)
            if src_path.suffix == ".tmp":
                assert src_path.exists(), (
                    f"Temp file {src_path} should exist before replace"
                )
                tmp_paths.append(src_path)
            original_replace(src, dst)

        try:
            os.rename = tracking_rename  # type: ignore[assignment]
            os.replace = tracking_replace  # type: ignore[assignment]
            storage.save(sample_world, name="atomic_test")
            assert len(tmp_paths) >= 1, "No tmp file was used during save"
        finally:
            os.rename = original_rename
            os.replace = original_replace

        # Confirm the final file exists and tmp file is gone
        assert (storage.saves_dir / "atomic_test.json").exists()
        assert not (storage.saves_dir / "atomic_test.json.tmp").exists()

    # ------------------------------------------------------------------
    # Auto-save mechanism
    # ------------------------------------------------------------------

    def test_should_auto_save_returns_false_when_no_interval(
        self, sample_world: WorldState
    ) -> None:
        """Without an interval, should_auto_save must return False."""
        store = WorldStorage(tempfile.mkdtemp(), auto_save_interval=None)
        store.save(sample_world, name="initial")
        assert store.should_auto_save(10) is False

    def test_should_auto_save_returns_false_before_first_save(
        self,
    ) -> None:
        """Without any save made, should_auto_save must return False."""
        store = WorldStorage(tempfile.mkdtemp(), auto_save_interval=5)
        assert store.should_auto_save(10) is False

    def test_should_auto_save_returns_true_after_interval(
        self, sample_world: WorldState
    ) -> None:
        """After saving, should_auto_save returns True when interval passed."""
        store = WorldStorage(tempfile.mkdtemp(), auto_save_interval=5)
        store.save(sample_world, name="first")
        assert store.should_auto_save(12) is True

    def test_should_auto_save_returns_false_before_interval(
        self, sample_world: WorldState
    ) -> None:
        """should_auto_save returns False when interval hasn't passed."""
        store = WorldStorage(tempfile.mkdtemp(), auto_save_interval=10)
        store.save(sample_world, name="first")
        assert store.should_auto_save(8) is False

    def test_should_auto_save_exact_boundary(self, sample_world: WorldState) -> None:
        """At exact interval boundary, should_auto_save returns True."""
        store = WorldStorage(tempfile.mkdtemp(), auto_save_interval=3)
        store.save(sample_world, name="first")
        assert store.should_auto_save(10) is True

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_save_with_special_chars_in_name(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Save names with safe characters must work."""
        storage.save(sample_world, name="player_save_001")
        assert storage.save_exists("player_save_001")

    def test_overwrite_existing_save(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with an existing name must overwrite without error."""
        ws1 = WorldState(turn_count=1)
        ws2 = WorldState(turn_count=2)

        storage.save(ws1, name="overwrite")
        storage.save(ws2, name="overwrite")

        loaded = storage.load("overwrite")
        assert loaded.turn_count == 2

    def test_index_is_rebuilt_on_corrupt_index(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """A corrupt index file must not break save operations."""
        storage.save(sample_world, name="survivor")

        idx_path = storage.saves_dir / "index.json"
        idx_path.write_text("{{{corrupt}}", encoding="utf-8")

        storage.save(sample_world, name="new_after_corrupt")

        saves = storage.list_saves()
        assert len(saves) == 1

    def test_tmp_file_cleaned_up_on_failure(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """If saving fails, the temp file must not linger."""
        original_mode = storage.saves_dir.stat().st_mode
        try:
            storage.saves_dir.chmod(0o444)
            with pytest.raises((PermissionError, OSError)):
                storage.save(sample_world, name="fail")
        finally:
            storage.saves_dir.chmod(original_mode)

        tmp_files = list(storage.saves_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Temp files left behind: {tmp_files}"

    # ------------------------------------------------------------------
    # Name validation — path traversal prevention (Bug 1)
    # ------------------------------------------------------------------

    def test_save_with_parent_dir_reference_raises_error(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with '..' in name must raise ValueError."""
        with pytest.raises(ValueError, match="(parent directory|path separator)"):
            storage.save(sample_world, name="../../tmp/evil")

    def test_save_with_slash_in_name_raises_error(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with '/' in name must raise ValueError."""
        with pytest.raises(ValueError, match="path separator"):
            storage.save(sample_world, name="my/save")

    def test_save_with_backslash_in_name_raises_error(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with '\\\\' in name must raise ValueError."""
        with pytest.raises(ValueError, match="path separator"):
            storage.save(sample_world, name="my\\\\save")

    def test_save_with_empty_name_raises_error(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with empty name must raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            storage.save(sample_world, name="")

    def test_load_with_parent_dir_reference_raises_error(
        self, storage: WorldStorage
    ) -> None:
        """Loading with '..' in name must raise ValueError."""
        with pytest.raises(ValueError, match="(parent directory|path separator)"):
            storage.load("../../tmp/evil")

    def test_delete_with_parent_dir_reference_raises_error(
        self, storage: WorldStorage
    ) -> None:
        """Deleting with '..' in name must raise ValueError."""
        with pytest.raises(ValueError, match="(parent directory|path separator)"):
            storage.delete("../../tmp/evil")

    def test_save_exists_with_parent_dir_reference_raises_error(
        self, storage: WorldStorage
    ) -> None:
        """save_exists with '..' in name must raise ValueError."""
        with pytest.raises(ValueError, match="(parent directory|path separator)"):
            storage.save_exists("../../tmp/evil")

    def test_save_with_long_name_raises_error(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with name > 200 chars must raise ValueError."""
        with pytest.raises(ValueError, match="too long"):
            storage.save(sample_world, name="a" * 201)

    # ------------------------------------------------------------------
    # Bug 4: saves/ dir auto-recreated if deleted at runtime
    # ------------------------------------------------------------------

    def test_saves_dir_auto_recreated_when_deleted(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """If saves/ directory is deleted, save() must recreate it."""
        import shutil

        shutil.rmtree(storage.saves_dir)
        assert not storage.saves_dir.exists()

        # Save must recreate the directory
        storage.save(sample_world, name="after_deletion")
        assert storage.saves_dir.is_dir()
        assert storage.save_exists("after_deletion")

    # ------------------------------------------------------------------
    # Bug 5: delete() with already-deleted file — no crash, index cleaned
    # ------------------------------------------------------------------

    def test_delete_with_manually_deleted_file_cleans_index(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """If save file is manually deleted, delete() must clean the index."""
        storage.save(sample_world, name="manually_gone")
        assert len(storage.list_saves()) == 1

        # Manually delete the file
        save_path = storage.saves_dir / "manually_gone.json"
        save_path.unlink()

        # delete() should succeed and clean the index
        storage.delete("manually_gone")
        assert len(storage.list_saves()) == 0

    # ------------------------------------------------------------------
    # Bug 6: Index metadata populated correctly
    # ------------------------------------------------------------------

    def test_index_metadata_character_name_is_populated(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """character_name in index must use world_state.character_name field."""
        sample_world.character_name = "Sir Hero"
        sample_world.character_id = "hero_42"
        storage.save(sample_world, name="meta_char")
        saves = storage.list_saves()
        assert len(saves) == 1
        assert saves[0]["character_name"] == "Sir Hero"

    def test_index_metadata_character_name_default_when_none(
        self, storage: WorldStorage
    ) -> None:
        """When character_id is None, character_name must be 'Unknown'."""
        ws = WorldState()
        storage.save(ws, name="meta_no_char")
        saves = storage.list_saves()
        assert len(saves) == 1
        assert saves[0]["character_name"] == "Unknown"

    def test_index_metadata_level_is_populated(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """level in index must be populated from turn_count."""
        storage.save(sample_world, name="meta_level")
        saves = storage.list_saves()
        assert len(saves) == 1
        assert saves[0]["level"] == 7

    # ------------------------------------------------------------------
    # Embedded character save/load (Bug 8)
    # ------------------------------------------------------------------

    def test_save_embeds_character_in_state(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with character data embeds _character key in the JSON file."""
        char_data = {"name": "Test Hero", "class": "Mage", "level": 5}
        sample_world._character = char_data
        sample_world.character_name = "Test Hero"
        storage.save(sample_world, name="char_embed")

        save_path = storage.saves_dir / "char_embed.json"
        with open(save_path) as f:
            raw_data = json.load(f)

        assert "_character" in raw_data
        assert raw_data["_character"]["name"] == "Test Hero"
        assert raw_data["_character"]["class"] == "Mage"
        assert raw_data["_character"]["level"] == 5
        assert raw_data["character_name"] == "Test Hero"

    def test_load_extracts_embedded_character(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Loading a save with embedded _character preserves the data."""
        char_data = {"name": "Load Hero", "class": "Warrior", "level": 3}
        sample_world._character = char_data
        sample_world.character_name = "Load Hero"
        storage.save(sample_world, name="char_load")

        loaded = storage.load("char_load")
        assert loaded._character is not None
        assert loaded._character["name"] == "Load Hero"
        assert loaded._character["class"] == "Warrior"
        assert loaded._character["level"] == 3
        assert loaded.character_name == "Load Hero"

    def test_load_falls_back_to_companion_character(self, client, monkeypatch) -> None:
        """Load falls back to old .char.json companion file when _character
        is absent (backward compatibility)."""
        tmp_dir = Path(tempfile.mkdtemp())
        saves_dir = tmp_dir / "saves"
        saves_dir.mkdir(parents=True)

        storage = WorldStorage(tmp_dir)
        monkeypatch.setattr("app.server._storage", storage)

        # Create a state file WITHOUT _character (old format)
        save_name = "backward_compat"
        state_path = saves_dir / f"{save_name}.json"
        with open(state_path, "w") as f:
            json.dump(
                {
                    "version": "1.0",
                    "turn_count": 5,
                    "character_id": "old_hero",
                },
                f,
            )

        # Create companion .char.json file in the location
        # _load_companion_character looks for (Path("data") / "saves").
        companion_dir = tmp_dir / "data" / "saves"
        companion_dir.mkdir(parents=True)
        save_key = hashlib.sha256(save_name.encode("utf-8")).hexdigest()
        char_data = {"name": "Old Hero", "class": "Fighter", "level": 3}
        char_path = companion_dir / f"{save_key}.char.json"
        with open(char_path, "w") as f:
            json.dump(char_data, f)

        monkeypatch.chdir(tmp_dir)

        # Load via Flask endpoint — should find companion character
        resp = client.post("/api/load/backward_compat")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["character"]["name"] == "Old Hero"
        assert data["character"]["class"] == "Fighter"
        assert data["character"]["level"] == 3

    def test_delete_cleans_up_companion_file(self, client, monkeypatch) -> None:
        """Deleting a save also removes the orphan .char.json companion file."""
        tmp_dir = Path(tempfile.mkdtemp())
        saves_dir = tmp_dir / "saves"
        saves_dir.mkdir(parents=True)

        storage = WorldStorage(tmp_dir)
        monkeypatch.setattr("app.server._storage", storage)

        # Save a game (creates the state file properly)
        save_name = "cleanup_companion"
        ws = WorldState(turn_count=5, _character={"name": "Hero"})
        storage.save(ws, name=save_name)

        # Create companion file in the legacy location
        companion_dir = tmp_dir / "data" / "saves"
        companion_dir.mkdir(parents=True)
        save_key = hashlib.sha256(save_name.encode("utf-8")).hexdigest()
        char_path = companion_dir / f"{save_key}.char.json"
        with open(char_path, "w") as f:
            json.dump({"name": "Legacy Hero"}, f)
        assert char_path.exists()

        monkeypatch.chdir(tmp_dir)

        # Delete via Flask endpoint — companion file should be removed
        resp = client.delete(f"/api/delete/{save_name}")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        assert not char_path.exists(), "Companion file should be cleaned up"

    def test_world_state_character_round_trip(self) -> None:
        """WorldState.from_dict(to_dict()) preserves _character and
        character_name."""
        char_data = {"name": "Round Trip Hero", "class": "Rogue"}
        ws = WorldState(
            character_name="Round Trip Hero",
            _character=char_data,
            turn_count=10,
        )

        d = ws.to_dict()
        assert d["_character"] == char_data
        assert d["character_name"] == "Round Trip Hero"
        assert d["turn_count"] == 10

        ws2 = WorldState.from_dict(d)
        assert ws2._character == char_data
        assert ws2.character_name == "Round Trip Hero"
        assert ws2.turn_count == 10
