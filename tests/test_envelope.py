import pytest
from app.save_engine import SaveEnvelope, validate_envelope


def test_serialization_roundtrip():
    payload = {"player_id": 123, "name": "Grubnik"}
    original = SaveEnvelope(
        schema_name="character", schema_version="1.0.0", payload=payload
    )
    data = original.to_dict()
    assert data["save_version"] == "1.0.0"
    assert data["schema_name"] == "character"
    assert data["payload"] == payload

    restored = SaveEnvelope.from_dict(data)
    assert restored.schema_name == "character"
    assert restored.payload == payload
    assert restored.save_version == "1.0.0"


def test_validation_valid():
    # Valid envelope
    data = {
        "save_version": "1.0.0",
        "schema_name": "state",
        "schema_version": "1.0.0",
        "timestamp": "2026-06-17T12:00:00Z",
        "payload": {"some_key": "some_value"},
    }
    errors = validate_envelope(data)
    assert len(errors) == 0


def test_validation_invalid():
    # Missing field
    data = {
        "schema_name": "state",
        "schema_version": "1.0.0",
        "timestamp": "2026-06-17T12:00:00Z",
        "payload": {},
    }
    errors = validate_envelope(data)
    assert any("Missing required field: save_version" in e for e in errors)

    # Bad type
    data = {
        "save_version": 1.0,  # Should be str
        "schema_name": "state",
        "schema_version": "1.0.0",
        "timestamp": "2026-06-17T12:00:00Z",
        "payload": {},
    }
    errors = validate_envelope(data)
    assert any("Field save_version must be str, got float" in e for e in errors)

    # Unknown schema name
    data = {
        "save_version": "1.0.0",
        "schema_name": "unknown_type",
        "schema_version": "1.0.0",
        "timestamp": "2026-06-17T12:00:00Z",
        "payload": {},
    }
    errors = validate_envelope(data)
    assert any("Unknown schema name: unknown_type" in e for e in errors)


def test_edge_cases():
    # Empty payload
    data = {
        "save_version": "1.0.0",
        "schema_name": "state",
        "schema_version": "1.0.0",
        "timestamp": "2026-06-17T12:00:00Z",
        "payload": {},
    }
    assert len(validate_envelope(data)) == 0

    # Large payload
    large_payload = {"data": "x" * 10**6}  # 1MB of 'x's
    data["payload"] = large_payload
    assert len(validate_envelope(data)) == 0

    # Unicode characters
    unicode_payload = {"name": "Grubnik the Goblin", "location": "🍄 Forest"}
    data["payload"] = unicode_payload
    assert len(validate_envelope(data)) == 0


def test_from_dict_filters_extra_keys():
    """Extra keys in the dict must be filtered out, not set as attributes."""
    data = {
        "save_version": "1.0.0",
        "schema_name": "character",
        "schema_version": "1.0.0",
        "timestamp": "2026-06-17T12:00:00Z",
        "payload": {"hp": 100},
        "sneaky_extra": "should_not_exist",
    }
    result = SaveEnvelope.from_dict(data)
    assert result.save_version == "1.0.0"
    assert result.schema_name == "character"
    assert result.payload == {"hp": 100}
    with pytest.raises(AttributeError):
        _ = result.sneaky_extra
