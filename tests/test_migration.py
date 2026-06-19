"""Unit tests for the migration framework in app.save_engine.migration."""

import json
from pathlib import Path

import pytest

from app.save_engine.bucket import Bucket
from app.save_engine.manager import SaveGameManager
from app.save_engine.migration import (
    MIGRATIONS,
    MigrationError,
    _find_migration_path,
    _parse_version,
    register_migration,
    run_migration,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_data_dir(tmp_path):
    return str(tmp_path)


# ---------------------------------------------------------------------------
# _parse_version
# ---------------------------------------------------------------------------


class TestParseVersion:
    def test_simple_semver(self):
        assert _parse_version("1.0.0") == (1, 0, 0)

    def test_two_part_version(self):
        assert _parse_version("1.2") == (1, 2)

    def test_single_part(self):
        assert _parse_version("5") == (5,)

    def test_large_numbers(self):
        assert _parse_version("999.888.777") == (999, 888, 777)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Empty or blank"):
            _parse_version("")

    def test_blank_string_raises(self):
        with pytest.raises(ValueError, match="Empty or blank"):
            _parse_version("   ")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="Invalid version"):
            _parse_version("1.a.0")

    def test_trailing_dot_raises(self):
        """A trailing dot leaves an empty component, which cannot be parsed."""
        with pytest.raises(ValueError, match="Invalid version"):
            _parse_version("1.0.")


# ---------------------------------------------------------------------------
# register_migration / MIGRATIONS
# ---------------------------------------------------------------------------


class TestRegisterMigration:
    def test_registers_migration(self):
        def my_migrate(payload):
            return payload

        register_migration("test_schema", "1.0.0", "1.1.0", my_migrate)
        assert ("test_schema", "1.0.0") in MIGRATIONS
        to_ver, func = MIGRATIONS[("test_schema", "1.0.0")]
        assert to_ver == "1.1.0"
        assert func is my_migrate


# ---------------------------------------------------------------------------
# _find_migration_path
# ---------------------------------------------------------------------------


class TestFindMigrationPath:
    def test_same_version_returns_empty(self):
        assert _find_migration_path("any", "1.0.0", "1.0.0") == []

    def test_single_step(self):
        register_migration("test_s", "1.0.0", "1.1.0", lambda p: p)
        path = _find_migration_path("test_s", "1.0.0", "1.1.0")
        assert len(path) == 1

    def test_two_steps(self):
        register_migration("test_s", "1.0.0", "1.1.0", lambda p: p)
        register_migration("test_s", "1.1.0", "1.2.0", lambda p: p)
        path = _find_migration_path("test_s", "1.0.0", "1.2.0")
        assert len(path) == 2

    def test_missing_path_raises(self):
        register_migration("test_s", "1.0.0", "1.1.0", lambda p: p)
        with pytest.raises(MigrationError, match="No migration path"):
            _find_migration_path("test_s", "1.0.0", "1.2.0")

    def test_from_newer_than_to_raises(self):
        with pytest.raises(MigrationError, match="from_version is newer"):
            _find_migration_path("test_s", "2.0.0", "1.0.0")

    def test_different_schema_not_found(self):
        register_migration("schema_a", "1.0.0", "1.1.0", lambda p: p)
        with pytest.raises(MigrationError, match="No migration path"):
            _find_migration_path("schema_b", "1.0.0", "1.1.0")


# ---------------------------------------------------------------------------
# run_migration
# ---------------------------------------------------------------------------


class TestRunMigration:
    def test_register_and_run_single(self):
        def add_bar(payload):
            payload["bar"] = True
            return payload

        register_migration("test_r", "1.0.0", "2.0.0", add_bar)
        result = run_migration("test_r", {"foo": 1}, "1.0.0", "2.0.0")
        assert result == {"foo": 1, "bar": True}

    def test_same_version_no_op(self):
        result = run_migration("test_r", {"foo": 1}, "1.0.0", "1.0.0")
        assert result == {"foo": 1}

    def test_migration_chain(self):
        def add_bar(payload):
            payload["bar"] = "yes"
            return payload

        def add_baz(payload):
            payload["baz"] = 42
            return payload

        register_migration("test_chain", "1.0.0", "1.1.0", add_bar)
        register_migration("test_chain", "1.1.0", "1.2.0", add_baz)

        result = run_migration("test_chain", {"foo": 1}, "1.0.0", "1.2.0")
        assert result == {"foo": 1, "bar": "yes", "baz": 42}

    def test_migration_idempotent(self):
        def add_bar(payload):
            payload["bar"] = True
            return payload

        register_migration("test_idem", "1.0.0", "2.0.0", add_bar)
        first = run_migration("test_idem", {"foo": 1}, "1.0.0", "2.0.0")
        second = run_migration("test_idem", first, "1.0.0", "2.0.0")
        assert first == second

    def test_missing_path_raises(self):
        with pytest.raises(MigrationError, match="No migration path"):
            run_migration("test_missing", {"foo": 1}, "1.0.0", "2.0.0")

    def test_character_example_migration_adds_alignment(self):
        """The pre-registered character v1.0.0 -> v1.1.0 migration must work."""
        result = run_migration(
            "character",
            {"id": "hero", "name": "Hero"},
            "1.0.0",
            "1.1.0",
        )
        assert result["alignment"] == "neutral"

    def test_character_migration_preserves_existing_alignment(self):
        """If alignment already exists, the migration must not overwrite it."""
        result = run_migration(
            "character",
            {"id": "hero", "name": "Hero", "alignment": "chaotic"},
            "1.0.0",
            "1.1.0",
        )
        assert result["alignment"] == "chaotic"


# ---------------------------------------------------------------------------
# Integration: load() triggers migration
# ---------------------------------------------------------------------------


class TestMigrationWithManager:
    """These tests verify that SaveGameManager.load() triggers migrations."""

    def test_load_triggers_migration(self, temp_data_dir):
        """Create a save file with old version, load it, verify migration ran."""
        manager = SaveGameManager(temp_data_dir)

        # Register a character bucket with v1.1.0 and identity deserializer
        # so we can inspect the migration result directly.
        bucket = Bucket(
            "character",
            "1.1.0",
            {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                },
                "required": ["id", "name"],
            },
            lambda x: x,
            lambda x: x,
        )
        manager.register_bucket(bucket)

        # Ensure the migration is registered (it's already registered at
        # import time in migration.py, but we register again to be explicit).
        register_migration(
            "character", "1.0.0", "1.1.0", lambda p: {**p, "alignment": "neutral"}
        )

        # Create a save file manually with v1.0.0 (no alignment field)
        slug = "test_migrate_char"
        save_folder = Path(temp_data_dir) / "saves" / slug
        save_folder.mkdir(parents=True, exist_ok=True)

        old_data = {
            "save_version": "1.0.0",
            "schema_name": "character",
            "schema_version": "1.0.0",
            "timestamp": "now",
            "payload": {
                "id": "hero1",
                "name": "Hero",
                # no alignment field
            },
        }

        with open(save_folder / "character.json", "w") as f:
            json.dump(old_data, f)

        loaded = manager.load(slug)
        assert "character" in loaded
        assert loaded["character"].get("alignment") == "neutral"

    def test_load_skips_migration_when_versions_match(self, temp_data_dir):
        """When envelope version == bucket version, no migration runs."""
        manager = SaveGameManager(temp_data_dir)

        bucket = Bucket(
            "test_match",
            "1.0.0",
            {"type": "object"},
            lambda x: x,
            lambda x: x,
        )
        manager.register_bucket(bucket)

        slug = "test_version_match"
        save_folder = Path(temp_data_dir) / "saves" / slug
        save_folder.mkdir(parents=True, exist_ok=True)

        data = {
            "save_version": "1.0.0",
            "schema_name": "test_match",
            "schema_version": "1.0.0",
            "timestamp": "now",
            "payload": {"foo": "bar"},
        }

        with open(save_folder / "test_match.json", "w") as f:
            json.dump(data, f)

        loaded = manager.load(slug)
        assert loaded["test_match"] == {"foo": "bar"}
