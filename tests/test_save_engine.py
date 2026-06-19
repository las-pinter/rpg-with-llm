import json
import pytest
from pathlib import Path
from app.save_engine.manager import SaveGameManager
from app.save_engine.bucket import Bucket
from app.world.model import WorldState
from app.character.model import Character


@pytest.fixture
def temp_data_dir(tmp_path):
    return str(tmp_path)


def test_registration(temp_data_dir):
    manager = SaveGameManager(temp_data_dir)
    bucket = Bucket("test", "1.0", {"type": "object"}, lambda x: x, lambda x: x)
    manager.register_bucket(bucket)
    assert "test" in manager.list_buckets()

    manager.unregister_bucket("test")
    assert "test" not in manager.list_buckets()


def test_default_registration(temp_data_dir):
    manager = SaveGameManager(temp_data_dir)
    manager.register_defaults()
    expected = ["world_state", "character", "narrative_entries", "summary"]
    assert sorted(manager.list_buckets()) == sorted(expected)


def test_roundtrip_save_load(temp_data_dir):
    manager = SaveGameManager(temp_data_dir)
    manager.register_defaults()

    # Create sample data
    world_state = WorldState(character_name="Hero", character_id="hero1")
    character = Character.create_default("Hero", "Fighter")

    buckets_data = {
        "world_state": world_state,
        "character": character,
        "narrative_entries": {
            "entries": [{"id": "e1", "content": "Something happened", "type": "event"}]
        },
        "summary": {"technical_summary": ["Summary 1"], "story_summary": ["Story 1"]},
    }

    slug = "test_save_roundtrip"
    manager.save(slug, buckets_data)

    loaded_buckets = manager.load(slug)

    assert loaded_buckets["world_state"].character_name == "Hero"
    assert loaded_buckets["world_state"].character_id == "hero1"
    assert loaded_buckets["character"].name == "Hero"
    assert loaded_buckets["character"].character_class == "Fighter"
    assert len(loaded_buckets["narrative_entries"]["entries"]) == 1
    assert loaded_buckets["summary"]["story_summary"] == ["Story 1"]


def test_schema_validation_failure(temp_data_dir):
    manager = SaveGameManager(temp_data_dir)
    manager.register_defaults()

    slug = "test_invalid_save"
    # Manually create a file with invalid data for world_state (missing character_name)
    save_folder = Path(temp_data_dir) / "saves" / slug
    save_folder.mkdir(parents=True, exist_ok=True)

    invalid_data = {
        "save_version": "1.0.0",
        "schema_name": "world_state",
        "schema_version": "1.0.0",
        "timestamp": "now",
        "payload": {
            "version": "1.0",
            "character_id": "hero1",
            # missing character_name
        },
    }

    with open(save_folder / "world_state.json", "w") as f:
        json.dump(invalid_data, f)

    # Load should skip this bucket because it fails validation (or just doesn't populate it)
    loaded = manager.load(slug)
    assert "world_state" not in loaded


def test_slug_validation_save(temp_data_dir):
    manager = SaveGameManager(temp_data_dir)
    manager.register_defaults()

    with pytest.raises(ValueError, match="Invalid slug"):
        manager.save("../../../etc/passwd", {})

    with pytest.raises(ValueError, match="Invalid slug"):
        manager.save("subdir/../malicious", {})

    with pytest.raises(ValueError, match="Invalid slug"):
        manager.save("bad\\path", {})


def test_slug_validation_load(temp_data_dir):
    manager = SaveGameManager(temp_data_dir)

    with pytest.raises(ValueError, match="Invalid slug"):
        manager.load("../../../etc/passwd")


def test_unregistered_bucket_save_warning(temp_data_dir, caplog):
    caplog.set_level("WARNING")
    manager = SaveGameManager(temp_data_dir)
    manager.register_defaults()

    # Save a bucket that isn't registered
    manager.save("test_slug", {"nonexistent_bucket": {"foo": "bar"}})

    assert any(
        "Skipping unregistered bucket" in record.message for record in caplog.records
    )


def test_register_bucket_rejects_invalid_slug(temp_data_dir):
    manager = SaveGameManager(temp_data_dir)
    with pytest.raises(ValueError, match="Invalid slug"):
        manager.save("../escape", {})


def test_save_validates_payload(temp_data_dir):
    """Save raises ValueError when serialized data doesn't match the bucket schema."""
    manager = SaveGameManager(temp_data_dir)

    # Register a bucket that requires a "name" field
    bucket = Bucket(
        "test_bucket",
        "1.0",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "value": {"type": "integer"},
            },
            "required": ["name"],
        },
        lambda x: x,
        lambda x: x,
    )
    manager.register_bucket(bucket)

    slug = "test_save_validate"

    # Valid data should pass without error
    manager.save(slug, {"test_bucket": {"name": "foo", "value": 42}})

    # Invalid data (missing required "name") should raise ValueError
    with pytest.raises(ValueError, match="Validation failed for bucket 'test_bucket'"):
        manager.save(slug, {"test_bucket": {"value": 42}})


def test_load_collects_validation_warnings(temp_data_dir, caplog):
    """Load logs a warning and skips the bucket when payload validation fails."""
    caplog.set_level("WARNING")
    manager = SaveGameManager(temp_data_dir)

    # Register a bucket that requires a "name" field
    bucket = Bucket(
        "test_bucket",
        "1.0",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        },
        lambda x: x,
        lambda x: x,
    )
    manager.register_bucket(bucket)

    slug = "test_load_warn"
    save_folder = Path(temp_data_dir) / "saves" / slug
    save_folder.mkdir(parents=True, exist_ok=True)

    # Create a file with invalid payload (missing "name")
    invalid_data = {
        "save_version": "1.0.0",
        "schema_name": "test_bucket",
        "schema_version": "1.0",
        "timestamp": "now",
        "payload": {"foo": "bar"},
    }

    with open(save_folder / "test_bucket.json", "w") as f:
        json.dump(invalid_data, f)

    loaded = manager.load(slug)
    assert "test_bucket" not in loaded
    assert any(
        "Schema validation warnings for bucket 'test_bucket'" in record.message
        for record in caplog.records
    )


def test_validate_payload_function():
    """Test the standalone validate_payload function with various cases."""
    from app.save_engine.schemas import validate_payload

    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    # Valid payload returns empty list
    assert validate_payload({"name": "Alice", "age": 30}, schema) == []

    # Invalid payload (missing required field) returns errors
    errors = validate_payload({"age": 30}, schema)
    assert len(errors) > 0
    assert any("'name' is a required property" in e for e in errors)

    # Invalid payload (wrong type) returns errors
    errors = validate_payload({"name": "Alice", "age": "thirty"}, schema)
    assert len(errors) > 0
    assert any("'thirty' is not of type 'integer'" in e for e in errors)

    # Empty payload against schema with required fields
    errors = validate_payload({}, schema)
    assert len(errors) > 0
    assert any("'name' is a required property" in e for e in errors)
