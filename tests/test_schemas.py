"""Comprehensive tests for schema validation in save_engine.

Tests validate_entity_schema() against all 10 registered schemas,
covering valid data, invalid data (missing required fields, wrong types,
extra properties), edge cases (empty dict, None, empty strings), unknown
schema names, and SchemaError handling.
"""

import pytest

from app.save_engine.schemas import (
    SCHEMA_REGISTRY,
    validate_entity_schema,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Valid entity data for each of the 10 schemas
#
# Each object includes only properties defined in its schema and respects
# type constraints, required fields, and additionalProperties: False.
# ═══════════════════════════════════════════════════════════════════════════════

VALID_ENTITIES = {
    "npc": {
        "id": "npc_1",
        "name": "Goblin",
        "faction": "monsters",
        "health": 30,
        "personality": "greedy",
        "stats": {
            "strength": 8,
            "dexterity": 14,
            "intelligence": 10,
            "wisdom": 8,
            "charisma": 6,
        },
    },
    "item": {
        "id": "item_1",
        "name": "Sword",
        "type": "weapon",
        "properties": {"damage": "1d8"},
        "quantity": 1,
    },
    "place": {
        "id": "place_1",
        "name": "Dungeon",
        "description": "Dark cave",
        "exits": [],
        "tags": ["dark"],
    },
    "enemy": {
        "id": "enemy_1",
        "name": "Orc",
        "stats": {"health": 10, "attack": 5, "defense": 3},
        "loot": [],
        "abilities": [],
    },
    "spell": {
        "id": "spell_1",
        "name": "Fireball",
        "school": "evocation",
        "level": 3,
        "effects": [],
    },
    "quest": {
        "id": "quest_1",
        "name": "Save the village",
        "description": "Go to village",
        "status": "not_started",
        "objectives": [],
    },
    "book_note": {
        "id": "note_1",
        "title": "Ancient Text",
        "content": "Lorem ipsum",
        "type": "book",
    },
    "injury": {
        "id": "injury_1",
        "name": "Broken Leg",
        "effect": "slow",
        "duration": 5,
        "severity": 2.5,
    },
    "flag_event": {
        "id": "flag_1",
        "name": "VillageSaved",
        "type": "event",
        "value": True,
        "turn": 10,
    },
    "other": {
        "id": "other_1",
        "note": "anything goes",
    },
}

# List of schema names that disallow extra properties (additionalProperties: False)
STRICT_SCHEMAS = [
    "npc",
    "item",
    "place",
    "enemy",
    "spell",
    "quest",
    "book_note",
    "injury",
    "flag_event",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateEntitySchema:
    """Tests for validate_entity_schema()."""

    # ── 1. Valid data for all 10 schemas ──────────────────────────────────────

    @pytest.mark.parametrize("entity_type", list(VALID_ENTITIES.keys()))
    def test_valid_data_returns_empty_errors(self, entity_type):
        """Valid data should produce an empty error list for every schema."""
        data = VALID_ENTITIES[entity_type]
        errors = validate_entity_schema(data, entity_type)
        assert errors == [], (
            f"Expected no errors for valid {entity_type!r}, "
            f"got {len(errors)} error(s): {errors}"
        )

    # ── 2. Missing required fields ───────────────────────────────────────────

    @pytest.mark.parametrize(
        "entity_type,missing_field",
        [
            ("npc", "id"),
            ("npc", "name"),
            ("npc", "faction"),
            ("npc", "health"),
            ("item", "id"),
            ("item", "name"),
            ("item", "type"),
            ("place", "id"),
            ("place", "name"),
            ("enemy", "id"),
            ("enemy", "name"),
            ("spell", "id"),
            ("spell", "name"),
            ("spell", "level"),
            ("quest", "id"),
            ("quest", "name"),
            ("book_note", "id"),
            ("book_note", "title"),
            ("injury", "id"),
            ("injury", "name"),
            ("flag_event", "id"),
            ("flag_event", "name"),
            ("other", "id"),
        ],
    )
    def test_missing_required_field_returns_errors(self, entity_type, missing_field):
        """A missing required field should produce at least one error."""
        valid = dict(VALID_ENTITIES[entity_type])
        valid.pop(missing_field, None)
        errors = validate_entity_schema(valid, entity_type)
        assert len(errors) > 0, (
            f"Expected errors for {entity_type!r} missing required field "
            f"{missing_field!r}, got none"
        )

    # ── 3. Wrong types / invalid values ──────────────────────────────────────

    @pytest.mark.parametrize(
        "entity_type,field,bad_value",
        [
            # NPC
            ("npc", "health", -1),  # health minimum is 0
            ("npc", "health", 3.14),  # health should be integer, not float
            ("npc", "health", "weak"),  # health should be integer
            # Item
            ("item", "type", "invalid_type"),  # not in enum
            ("item", "quantity", -1),  # quantity minimum is 1
            ("item", "quantity", "many"),  # quantity should be integer
            ("item", "quantity", 0),  # quantity minimum is 1
            # Place
            ("place", "exits", "north"),  # exits should be array
            # Spell
            ("spell", "level", "high"),  # level should be integer
            ("spell", "level", 3.5),  # float is not integer
            # Quest
            ("quest", "status", "active"),  # not in enum
            ("quest", "status", "done"),  # not in enum
            # Book note
            ("book_note", "title", 42),  # title should be string
            # Injury
            ("injury", "duration", "long"),  # duration should be integer
            ("injury", "severity", "severe"),  # severity should be number
            # Flag event
            ("flag_event", "turn", "now"),  # turn should be integer
            (
                "flag_event",
                "value",
                {"bad": "object"},
            ),  # value must be string/number/boolean
        ],
    )
    def test_invalid_type_or_value_returns_errors(self, entity_type, field, bad_value):
        """A field with an invalid type or out-of-range value should produce errors."""
        valid = dict(VALID_ENTITIES[entity_type])
        valid[field] = bad_value
        errors = validate_entity_schema(valid, entity_type)
        assert len(errors) > 0, (
            f"Expected errors for {entity_type!r} with "
            f"{field!r}={bad_value!r}, got none"
        )

    # ── 4. Additional properties (where forbidden) ───────────────────────────

    @pytest.mark.parametrize("entity_type", STRICT_SCHEMAS)
    def test_additional_property_rejected_for_strict_schema(self, entity_type):
        """Extra properties should be rejected when additionalProperties is False."""
        valid = dict(VALID_ENTITIES[entity_type])
        valid["_extra_spy_field"] = "should not be allowed"
        errors = validate_entity_schema(valid, entity_type)
        assert len(errors) > 0, (
            f"Expected errors for {entity_type!r} with extra property, got none"
        )

    def test_other_schema_allows_additional_properties(self):
        """The 'other' schema explicitly allows additional properties."""
        data = dict(VALID_ENTITIES["other"])
        data["anything_extra"] = "this is fine"
        data["another_field"] = 99
        errors = validate_entity_schema(data, "other")
        assert errors == [], (
            f"Expected no errors for 'other' with extra properties, got: {errors}"
        )

    # ── 5. Unknown schema name ───────────────────────────────────────────────

    def test_unknown_schema_returns_error_message(self):
        """An unrecognised schema name should return a descriptive error."""
        errors = validate_entity_schema({}, "nonexistent_schema_xyz")
        assert len(errors) > 0, "Expected errors for unknown schema, got none"
        assert "unknown" in errors[0].lower(), (
            f"Error message should mention 'unknown', got: {errors[0]}"
        )

    def test_unknown_schema_for_empty_string_name(self):
        """An empty string schema name is also unknown."""
        errors = validate_entity_schema({"id": "x"}, "")
        assert len(errors) > 0, "Expected errors for empty schema name, got none"
        assert "unknown" in errors[0].lower(), (
            f"Error message should mention 'unknown', got: {errors[0]}"
        )

    # ── 6. Edge cases ────────────────────────────────────────────────────────

    @pytest.mark.parametrize("entity_type", list(VALID_ENTITIES.keys()))
    def test_empty_dict_returns_errors(self, entity_type):
        """An empty dict missing all required fields should produce errors."""
        errors = validate_entity_schema({}, entity_type)
        assert len(errors) > 0, (
            f"Expected errors for empty dict on {entity_type!r}, got none"
        )

    @pytest.mark.parametrize("entity_type", list(VALID_ENTITIES.keys()))
    def test_none_data_returns_errors(self, entity_type):
        """Passing None as data should produce validation errors."""
        errors = validate_entity_schema(None, entity_type)
        assert len(errors) > 0, (
            f"Expected errors for None data on {entity_type!r}, got none"
        )

    @pytest.mark.parametrize(
        "entity_type,field",
        [
            ("npc", "name"),
            ("item", "name"),
            ("place", "name"),
            ("enemy", "name"),
            ("spell", "name"),
            ("quest", "name"),
            ("book_note", "title"),
            ("injury", "name"),
            ("flag_event", "name"),
            ("other", "name"),
        ],
    )
    def test_empty_string_field_is_accepted(self, entity_type, field):
        """Empty string should be a valid value for string-typed fields."""
        valid = dict(VALID_ENTITIES[entity_type])
        if field in valid:
            valid[field] = ""
            errors = validate_entity_schema(valid, entity_type)
            assert errors == [], (
                f"Expected no errors for {entity_type!r} with empty {field!r}, "
                f"got: {errors}"
            )

    def test_zero_health_is_valid_for_npc(self):
        """Health can be zero (minimum inclusive)."""
        data = dict(VALID_ENTITIES["npc"])
        data["health"] = 0
        errors = validate_entity_schema(data, "npc")
        assert errors == [], f"Expected no errors for npc with health=0, got: {errors}"

    def test_empty_array_fields_are_valid(self):
        """Empty arrays for list-type fields should be accepted."""
        # NPC with empty stats (still has required stats sub-fields)
        data = dict(VALID_ENTITIES["enemy"])
        data["loot"] = []
        data["abilities"] = []
        errors = validate_entity_schema(data, "enemy")
        assert errors == [], (
            f"Expected no errors for enemy with empty arrays, got: {errors}"
        )

    # ── 7. SchemaError handling ──────────────────────────────────────────────

    def test_schema_error_is_caught(self):
        """A SchemaError (invalid schema definition) should be caught.

        We register a deliberately broken schema containing an invalid keyword
        value, then verify the error is returned as a 'Schema error' message.
        """
        # An invalid $schema value can trigger SchemaError in some validators.
        bad_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"x": {"type": "string", "minLength": -1}},
        }
        SCHEMA_REGISTRY["__test_bad_schema__"] = bad_schema
        try:
            errors = validate_entity_schema({"x": "hello"}, "__test_bad_schema__")
            assert len(errors) > 0, "Expected errors from a bad schema, got none"
            assert "schema error" in errors[0].lower(), (
                f"Expected 'Schema error:' prefix, got: {errors[0]}"
            )
        finally:
            del SCHEMA_REGISTRY["__test_bad_schema__"]

    # ── 8. Additional edge: None for required field ──────────────────────────

    @pytest.mark.parametrize(
        "entity_type,field",
        [
            ("npc", "name"),
            ("item", "name"),
            ("spell", "level"),
        ],
    )
    def test_null_value_for_required_field_returns_errors(self, entity_type, field):
        """Setting a required field to None should produce a validation error."""
        valid = dict(VALID_ENTITIES[entity_type])
        valid[field] = None
        errors = validate_entity_schema(valid, entity_type)
        assert len(errors) > 0, (
            f"Expected errors for {entity_type!r} with {field!r}=None, got none"
        )

    # ── 9. Integration: registry contains exactly 10 schemas ─────────────────

    def test_registry_contains_expected_schemas(self):
        """The SCHEMA_REGISTRY should contain all 10 entity types."""
        expected = {
            "npc",
            "item",
            "place",
            "enemy",
            "spell",
            "quest",
            "book_note",
            "injury",
            "flag_event",
            "other",
        }
        assert set(SCHEMA_REGISTRY.keys()) == expected, (
            f"Registry keys mismatch. Expected {expected}, "
            f"got {set(SCHEMA_REGISTRY.keys())}"
        )


if __name__ == "__main__":
    pytest.main([__file__])
