"""Tests for content schema validation in app.schemas.

Tests validate_character_record(), validate_item(), and validate_creature()
against their JSON Schema definitions.
"""

import pytest
from app.schemas import (
    validate_character_record,
    validate_item,
    validate_creature,
)


class TestCharacterRecordSchema:
    """Validation tests for CharacterRecord schema."""

    def test_valid_character_record(self) -> None:
        """A fully populated record should pass with no errors."""
        data = {
            "name": "Test Hero",
            "character_class": "Fighter",
            "level": 3,
            "abilities": {
                "STR": 15,
                "DEX": 13,
                "CON": 14,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            },
            "skills": ["Athletics", "Perception"],
            "resources": {
                "hp": {
                    "value": 28,
                    "max": 28,
                    "short_rest_recovery": "1d10",
                    "long_rest_recovery": "full",
                },
            },
            "inventory": [],
            "equipped_items": [],
            "gold": 15,
            "xp": 0,
            "appearance": "Tall and muscular.",
            "personality": "Brave.",
            "backstory": "A hero emerges.",
            "hooks": ["Save the kingdom"],
            "created_at": "2026-07-17T12:00:00Z",
        }
        assert validate_character_record(data) == []

    def test_missing_required_fields(self) -> None:
        """A record missing required fields should report errors."""
        errors = validate_character_record({"name": "Incomplete"})
        assert len(errors) > 0
        assert any("Missing required" in e for e in errors)

    def test_invalid_ability_score(self) -> None:
        """An ability score > 30 should be rejected."""
        data = {
            "name": "Bad Abilities",
            "character_class": "Fighter",
            "level": 1,
            "abilities": {
                "STR": 99,
                "DEX": 13,
                "CON": 14,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            },
            "skills": [],
            "resources": {
                "hp": {
                    "value": 10,
                    "max": 10,
                    "short_rest_recovery": "1d8",
                    "long_rest_recovery": "full",
                },
            },
            "gold": 0,
            "xp": 0,
        }
        errors = validate_character_record(data)
        assert any("STR" in e for e in errors)

    def test_invalid_character_class(self) -> None:
        """An unknown character class should be rejected."""
        data = {
            "name": "Test",
            "character_class": "Paladin",
            "level": 1,
            "abilities": {
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            "skills": [],
            "resources": {
                "hp": {
                    "value": 10,
                    "max": 10,
                    "short_rest_recovery": "1d8",
                    "long_rest_recovery": "full",
                },
            },
            "gold": 0,
            "xp": 0,
        }
        errors = validate_character_record(data)
        assert any("character_class" in e for e in errors)

    def test_level_out_of_range(self) -> None:
        """A level outside 1-20 should be rejected."""
        data = {
            "name": "Cheater",
            "character_class": "Fighter",
            "level": 99,
            "abilities": {
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            "skills": [],
            "resources": {
                "hp": {
                    "value": 10,
                    "max": 10,
                    "short_rest_recovery": "1d8",
                    "long_rest_recovery": "full",
                },
            },
            "gold": 0,
            "xp": 0,
        }
        errors = validate_character_record(data)
        assert any("level" in e.lower() for e in errors)


class TestItemSchema:
    """Validation tests for Item schema."""

    def test_valid_item(self) -> None:
        """A fully populated item should pass with no errors."""
        data = {
            "id": "item-1",
            "name": "Longsword",
            "quantity": 1,
            "item_type": "WEAPON",
            "properties": {"damage": "1d8"},
            "description": "A sharp blade.",
            "weight": 3.0,
            "value": 15,
        }
        assert validate_item(data) == []

    def test_invalid_item_type(self) -> None:
        """An unknown item type should be rejected."""
        data = {
            "id": "item-2",
            "name": "Mystery Box",
            "quantity": 1,
            "item_type": "INVALID",
            "properties": {},
            "description": "",
            "weight": 1.0,
            "value": 0,
        }
        errors = validate_item(data)
        assert any("item_type" in e.lower() for e in errors)

    def test_missing_required_fields(self) -> None:
        """An item missing required fields should report errors."""
        errors = validate_item({"name": "Partial"})
        assert len(errors) > 0
        assert any("Missing required" in e for e in errors)

    def test_negative_weight(self) -> None:
        """A negative weight should be rejected."""
        data = {
            "id": "item-3",
            "name": "Bugged Item",
            "quantity": 1,
            "item_type": "MISC",
            "properties": {},
            "description": "",
            "weight": -5.0,
            "value": 0,
        }
        errors = validate_item(data)
        assert any("weight" in e.lower() for e in errors)

    def test_zero_quantity(self) -> None:
        """A quantity less than 1 should be rejected."""
        data = {
            "id": "item-4",
            "name": "Empty Stack",
            "quantity": 0,
            "item_type": "MISC",
            "properties": {},
            "description": "",
            "weight": 1.0,
            "value": 0,
        }
        errors = validate_item(data)
        assert any("quantity" in e.lower() for e in errors)


class TestCreatureSchema:
    """Validation tests for Creature schema."""

    def test_valid_creature(self) -> None:
        """A fully populated creature should pass with no errors."""
        data = {
            "id": "goblin-1",
            "name": "Goblin",
            "type": "humanoid",
            "level": 1,
            "abilities": {
                "STR": 8,
                "DEX": 14,
                "CON": 10,
                "INT": 10,
                "WIS": 8,
                "CHA": 8,
            },
            "ac": 15,
            "hp": 7,
        }
        assert validate_creature(data) == []

    def test_invalid_creature_type(self) -> None:
        """An unknown creature type should be rejected."""
        data = {
            "id": "void-1",
            "name": "Void Walker",
            "type": "eldritch",
            "level": 5,
            "abilities": {
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            "ac": 12,
            "hp": 50,
        }
        errors = validate_creature(data)
        assert any("type" in e.lower() for e in errors)

    def test_missing_abilities(self) -> None:
        """A creature missing abilities should report errors."""
        data = {
            "id": "ghost-1",
            "name": "Ghost",
            "type": "undead",
            "level": 3,
            "ac": 10,
            "hp": 30,
        }
        errors = validate_creature(data)
        # Should report each missing ability individually
        assert any("Missing required ability" in e for e in errors)
        assert len(errors) >= 6  # One per ability

    def test_missing_required_ability(self) -> None:
        """A creature missing a specific ability should report errors."""
        data = {
            "id": "cyclops-1",
            "name": "Cyclops",
            "type": "monstrosity",
            "level": 6,
            "abilities": {"STR": 20, "CON": 18},
            "ac": 14,
            "hp": 80,
        }
        errors = validate_creature(data)
        assert any("STR" in e or "DEX" in e for e in errors)
