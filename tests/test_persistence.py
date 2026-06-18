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

    def test_save_creates_folder(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving a WorldState must create the expected folder."""
        slug = storage.save(sample_world, name="test_save")
        save_folder = storage.saves_dir / slug
        assert save_folder.is_dir()
        assert (save_folder / "state.json").exists()
        # character.json is only created if _character is set
        if sample_world._character:
            assert (save_folder / "character.json").exists()
        assert (save_folder / "narrative_entries.json").exists()
        assert (save_folder / "summary.json").exists()

    def test_save_returns_slug(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """The save ID returned must be a slug containing timestamp."""
        slug = storage.save(sample_world, name="ts_test")
        # Slug format: {slugified_name}-{YYYYMMDD_HHMMSS_ffffff}-{rand_hex}
        # e.g. "ts-test-20260531_120000_123456-abcd"
        assert slug.startswith("ts-test-")
        # Remove the random suffix first, then extract timestamp
        without_rand = slug.rsplit("-", 1)[0]
        ts_part = without_rand.rsplit("-", 1)[1] if "-" in without_rand else ""
        assert len(ts_part) == 22
        assert ts_part[8] == "_"
        assert ts_part[:8].isdigit()
        assert ts_part[9:15].isdigit()
        assert ts_part[15] == "_"
        assert ts_part[16:].isdigit()

    def test_save_file_contains_valid_json(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """The contents of the save file must be parseable JSON."""
        slug = storage.save(sample_world, name="json_test")
        state_path = storage.saves_dir / slug / "state.json"
        with open(state_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert "save_version" in data
        # Since it's wrapped in SaveEnvelope, the actual state is in payload
        payload = data.get("payload", {})
        assert payload["turn_count"] == 7

    # ------------------------------------------------------------------
    # Round-trip (save + load)
    # ------------------------------------------------------------------

    def test_load_returns_identical_world_state(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Round-trip: save then load must yield an identical WorldState."""
        slug = storage.save(sample_world, name="roundtrip")
        restored = storage.load(slug)

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
        slug_one = storage.save(sample_world, name="save_one")
        slug_two = storage.save(sample_world, name="save_two")

        loaded_one = storage.load(slug_one)
        loaded_two = storage.load(slug_two)

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
        slug = storage.save(sample_world, name="autosave")
        saves = storage.list_saves()
        assert len(saves) == 1

        meta = saves[0]
        assert "id" in meta
        assert meta["id"] == slug
        assert "name" in meta
        assert meta["name"] == "autosave"
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
        assert "id" in meta
        assert "name" in meta
        assert "timestamp" in meta
        assert "character_name" in meta
        assert "level" in meta
        assert "turn_count" in meta
        assert meta["turn_count"] == 7

    def test_list_saves_backward_compat_old_index(self, storage: WorldStorage) -> None:
        """Old index entries without id/name must get them from the key."""
        import json

        idx_path = storage.saves_dir / "index.json"
        idx_path.write_text(
            json.dumps({"saves": {"old-key": {"timestamp": "123", "turn_count": 1}}})
        )
        saves = storage.list_saves()
        assert len(saves) == 1
        assert saves[0]["id"] == "old-key"
        assert saves[0]["name"] == "old-key"
        assert saves[0]["timestamp"] == "123"

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def test_delete_removes_folder(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Deleting a save must remove its folder."""
        slug = storage.save(sample_world, name="delete_me")
        save_folder = storage.saves_dir / slug
        assert save_folder.is_dir()

        storage.delete(slug)
        assert not save_folder.exists()

    def test_delete_removes_index_entry(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Deleting a save must also remove it from the index."""
        slug = storage.save(sample_world, name="gone_soon")
        assert len(storage.list_saves()) == 1

        storage.delete(slug)
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
        slug = storage.save(sample_world, name="check_me")
        assert storage.save_exists(slug) is True

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
        """Loading a corrupt (invalid JSON) state file must raise ValueError."""
        bad_folder = storage.saves_dir / "corrupt"
        bad_folder.mkdir()
        with open(bad_folder / "state.json", "w") as f:
            f.write("this is not json")

        with pytest.raises(ValueError, match="corrupt|invalid JSON"):
            storage.load("corrupt")

    def test_load_file_with_non_dict_json_raises_error(
        self, storage: WorldStorage
    ) -> None:
        """Loading a JSON file that isn't a dict must raise ValueError."""
        bad_folder = storage.saves_dir / "not_a_dict"
        bad_folder.mkdir()
        with open(bad_folder / "state.json", "w") as f:
            f.write('"just a string"')

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
            slug = storage.save(sample_world, name="atomic_test")
            assert len(tmp_paths) >= 1, "No tmp file was used during save"
        finally:
            os.rename = original_rename
            os.replace = original_replace

        # Confirm the final folder exists and contains a state.json file
        save_folder = storage.saves_dir / slug
        assert save_folder.is_dir()
        assert (save_folder / "state.json").exists()
        assert not (storage.saves_dir / f"{slug}.json.tmp").exists()

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
        slug = storage.save(sample_world, name="player_save_001")
        assert storage.save_exists(slug)

    def test_overwrite_existing_save(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Saving with the same name twice creates separate slug files."""
        ws1 = WorldState(turn_count=1)
        ws2 = WorldState(turn_count=2)

        slug1 = storage.save(ws1, name="overwrite")
        slug2 = storage.save(ws2, name="overwrite")

        # Different slugs because they contain unique timestamps
        assert slug1 != slug2

        loaded = storage.load(slug2)
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

    def test_save_exists_with_parent_dir_reference(self, storage: WorldStorage) -> None:
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
        slug = storage.save(sample_world, name="after_deletion")
        assert storage.saves_dir.is_dir()
        assert storage.save_exists(slug)

    # ------------------------------------------------------------------
    # Bug 5: delete() with already-deleted file — no crash, index cleaned
    # ------------------------------------------------------------------

    def test_delete_with_manually_deleted_file_cleans_index(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """If save file is manually deleted, delete() must clean the index."""
        slug = storage.save(sample_world, name="manually_gone")
        assert len(storage.list_saves()) == 1

        # Manually delete the folder
        save_path = storage.saves_dir / slug
        if save_path.exists():
            import shutil

            shutil.rmtree(save_path)

        # delete() should succeed and clean the index
        storage.delete(slug)
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
        """Saving with character data embeds _character key in the JSON file.
        Duplicate flat fields are removed when _character is present."""
        char_data = {"name": "Test Hero", "class": "Mage", "level": 5}
        sample_world._character = char_data
        sample_world.character_name = "Test Hero"
        slug = storage.save(sample_world, name="char_embed")

        save_folder = storage.saves_dir / slug
        with open(save_folder / "state.json") as f:
            envelope = json.load(f)
        payload = envelope.get("payload", {})
        assert "_character" in payload
        assert payload["_character"]["name"] == "Test Hero"
        assert payload["_character"]["class"] == "Mage"
        assert payload["_character"]["level"] == 5
        # Duplicate flat fields removed by to_dict() when _character is present
        # (inventory and gold are world-level runtime state, NOT redundant)
        assert "character_name" not in payload
        assert "character_id" not in payload
        assert "inventory" in payload
        assert "gold" in payload

    def test_load_extracts_embedded_character(
        self, storage: WorldStorage, sample_world: WorldState
    ) -> None:
        """Loading a save with embedded _character preserves the data."""
        char_data = {"name": "Load Hero", "class": "Warrior", "level": 3}
        sample_world._character = char_data
        sample_world.character_name = "Load Hero"
        slug = storage.save(sample_world, name="char_load")

        loaded = storage.load(slug)
        assert loaded._character is not None
        assert loaded._character["name"] == "Load Hero"
        assert loaded._character["class"] == "Warrior"
        assert loaded._character["level"] == 3
        # character_name loaded from saved file — removed by to_dict()
        # when _character is present, defaults to "" in from_dict
        assert loaded.character_name == ""

    def test_world_state_character_round_trip(self) -> None:
        """WorldState.from_dict(to_dict()) preserves _character and
        removes duplicate flat fields."""
        char_data = {"name": "Round Trip Hero", "class": "Rogue", "inventory": []}
        ws = WorldState(
            character_id="hero_42",
            character_name="Round Trip Hero",
            inventory=["sword"],
            gold=100,
            _character=char_data,
            turn_count=10,
        )

        d = ws.to_dict()
        assert d["_character"] == char_data
        # character_name and character_id are redundant with _character
        # and removed; inventory and gold are world-level state, preserved
        assert "character_name" not in d
        assert "character_id" not in d
        assert "inventory" in d
        assert d["inventory"] == ["sword"]
        assert "gold" in d
        assert d["gold"] == 100
        assert d["turn_count"] == 10

        ws2 = WorldState.from_dict(d)
        assert ws2._character == char_data
        # character_name defaulted to "" since it was removed
        assert ws2.character_name == ""
        assert ws2.inventory == ["sword"]
        assert ws2.gold == 100
        assert ws2.turn_count == 10

    def test_world_state_to_dict_without_character_preserves_fields(
        self,
    ) -> None:
        """When _character is None, to_dict() keeps all flat fields."""
        ws = WorldState(
            character_id="hero_42",
            character_name="Sir Hero",
            inventory=["sword"],
            gold=100,
            _character=None,
            turn_count=5,
        )

        d = ws.to_dict()
        assert d["_character"] is None
        assert d["character_name"] == "Sir Hero"
        assert d["character_id"] == "hero_42"
        assert d["inventory"] == ["sword"]
        assert d["gold"] == 100
        assert d["turn_count"] == 5
