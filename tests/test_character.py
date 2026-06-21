"""Tests for the Character data model and persistence — Phase 4, Task 4.2."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.character.creation import (
    AssistedCreation,
    CharacterGenerationError,
    CharacterStorage,
    _convert_legacy_character,
)
from app.character.items import Item, ItemType
from app.character.model import (
    STANDARD_ABILITIES,
    VALID_CLASSES,
    Character,
    CharacterRecord,
    DerivedSheet,
)
from app.character.resources import ResourceData


def _make_minimal_character(**overrides: object) -> Character:
    """Build a minimally-valid Character for use across tests."""
    defaults: dict[str, object] = {
        "name": "Borin",
        "character_class": "Fighter",
        "abilities": {a: 10 for a in STANDARD_ABILITIES},
    }
    defaults.update(overrides)
    return Character(**defaults)  # type: ignore[arg-type]


def _make_char(**overrides: object) -> Character:
    """Build a Character with defaults (name=Test, Fighter, all-10 abilities)."""
    defaults: dict[str, object] = {
        "name": "Test",
        "character_class": "Fighter",
        "abilities": VALID_ABILITIES,
    }
    defaults.update(overrides)
    return Character(**defaults)  # type: ignore[arg-type]


VALID_ABILITIES = {a: 10 for a in STANDARD_ABILITIES}


class TestCharacterModel:
    """Tests for the Character dataclass."""

    def test_name_appearance_personality_backstory_are_stored(self) -> None:
        """All four identity/narrative fields must be stored verbatim."""
        char = Character(
            name="Zara Moonshadow",
            appearance="Elven, silver hair, green eyes",
            personality="Curious and reckless",
            backstory="Grew up in the Crescent Woods.",
            abilities=VALID_ABILITIES,
        )
        assert char.name == "Zara Moonshadow"
        assert char.appearance == "Elven, silver hair, green eyes"
        assert char.personality == "Curious and reckless"
        assert char.backstory == "Grew up in the Crescent Woods."

    def test_hooks_defaults_to_empty_list(self) -> None:
        """hooks must default to an empty list."""
        char = _make_minimal_character()
        assert char.hooks == []

    def test_skills_defaults_to_empty_list(self) -> None:
        """skills must default to an empty list."""
        char = _make_minimal_character()
        assert char.skills == []

    def test_inventory_defaults_to_empty_list(self) -> None:
        """inventory must default to an empty list."""
        char = _make_minimal_character()
        assert char.inventory == []

    def test_abilities_contains_all_six_keys(self) -> None:
        """abilities dict must have exactly STR, DEX, CON, INT, WIS, CHA."""
        char = _make_minimal_character()
        assert set(char.abilities.keys()) == set(STANDARD_ABILITIES)

    def test_level_defaults_to_one(self) -> None:
        """level must default to 1."""
        char = _make_minimal_character()
        assert char.level == 1

    def test_xp_defaults_to_zero(self) -> None:
        """xp must default to 0."""
        char = _make_minimal_character()
        assert char.xp == 0

    def test_hp_and_max_hp_stored_correctly(self) -> None:
        """hp and max_hp must be stored as provided."""
        char = _make_minimal_character(hp=15, max_hp=20)
        assert char.hp == 15
        assert char.max_hp == 20

    def test_ac_stored_correctly(self) -> None:
        """ac must be stored as provided."""
        char = _make_minimal_character(ac=16)
        assert char.ac == 16

    def test_empty_name_raises_value_error(self) -> None:
        """An empty-string name must raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            Character(name="", character_class="Fighter", abilities=VALID_ABILITIES)

    def test_whitespace_only_name_raises_value_error(self) -> None:
        """A name composed only of whitespace must raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            _make_char(name="   \t  ")

    def test_invalid_class_raises_value_error(self) -> None:
        """An unrecognised character_class must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid character class"):
            _make_char(character_class="Paladin")

    @pytest.mark.parametrize("valid_class", sorted(VALID_CLASSES))
    def test_valid_classes_accepted(self, valid_class: str) -> None:
        """Each class in VALID_CLASSES must be accepted by the constructor."""
        char = _make_char(character_class=valid_class)
        assert char.character_class == valid_class

    def test_missing_ability_score_raises_value_error(self) -> None:
        """Omitting one of the six abilities must raise ValueError."""
        incomplete = {a: 10 for a in STANDARD_ABILITIES if a != "CHA"}
        with pytest.raises(ValueError, match="Missing ability"):
            Character(name="Test", character_class="Fighter", abilities=incomplete)

    def test_extra_ability_keys_silently_accepted(self) -> None:
        """Extra keys beyond the standard six must be silently accepted."""
        with_extra = {**VALID_ABILITIES, "LUCK": 12}
        char = Character(name="Test", character_class="Fighter", abilities=with_extra)
        assert "LUCK" in char.abilities

    def test_ability_score_below_3_raises_value_error(self) -> None:
        """An ability score of 2 must raise ValueError."""
        bad = dict(VALID_ABILITIES)
        bad["STR"] = 2
        with pytest.raises(ValueError, match="out of range"):
            Character(name="Test", character_class="Fighter", abilities=bad)

    def test_ability_score_above_18_raises_value_error(self) -> None:
        """An ability score of 19 must raise ValueError."""
        bad = dict(VALID_ABILITIES)
        bad["DEX"] = 19
        with pytest.raises(ValueError, match="out of range"):
            Character(name="Test", character_class="Fighter", abilities=bad)

    def test_ability_score_at_boundary_3_is_valid(self) -> None:
        """Ability score of 3 is at the lower boundary and must be accepted."""
        boundary = dict(VALID_ABILITIES)
        boundary["STR"] = 3
        char = Character(name="Test", character_class="Fighter", abilities=boundary)
        assert char.abilities["STR"] == 3

    def test_ability_score_at_boundary_18_is_valid(self) -> None:
        """Ability score of 18 is at the upper boundary and must be accepted."""
        boundary = dict(VALID_ABILITIES)
        boundary["INT"] = 18
        char = Character(name="Test", character_class="Fighter", abilities=boundary)
        assert char.abilities["INT"] == 18

    def test_abilities_non_dict_raises_value_error(self) -> None:
        """Passing a non-dict for abilities must raise ValueError."""
        with pytest.raises(ValueError, match="Abilities must be a dictionary"):
            Character(name="Test", character_class="Fighter", abilities="not_a_dict")  # type: ignore[arg-type]

    def test_level_zero_raises_value_error(self) -> None:
        """Level 0 must raise ValueError."""
        with pytest.raises(ValueError, match="Level must be >= 1"):
            _make_char(level=0)

    def test_level_negative_raises_value_error(self) -> None:
        """A negative level must raise ValueError."""
        with pytest.raises(ValueError, match="Level must be >= 1"):
            _make_char(level=-5)

    def test_negative_xp_raises_value_error(self) -> None:
        """Negative XP must raise ValueError."""
        with pytest.raises(ValueError, match="XP must be >= 0"):
            _make_char(xp=-1)

    def test_xp_zero_is_valid(self) -> None:
        """XP == 0 is the standard starting value and must be accepted."""
        char = _make_char(xp=0)
        assert char.xp == 0

    def test_negative_hp_raises_value_error(self) -> None:
        """Negative HP must raise ValueError."""
        with pytest.raises(ValueError, match="HP must be >= 0"):
            _make_char(hp=-1, max_hp=10)

    def test_zero_hp_is_valid(self) -> None:
        """HP == 0 (unconscious) must be accepted."""
        char = _make_char(hp=0, max_hp=10)
        assert char.hp == 0

    def test_zero_max_hp_raises_value_error(self) -> None:
        """max_hp of 0 must raise ValueError."""
        with pytest.raises(ValueError, match="max_hp must be > 0"):
            _make_char(hp=10, max_hp=0)

    def test_negative_max_hp_raises_value_error(self) -> None:
        """Negative max_hp must raise ValueError."""
        with pytest.raises(ValueError, match="max_hp must be > 0"):
            _make_char(hp=10, max_hp=-5)

    def test_create_default_creates_with_correct_name(self) -> None:
        """create_default must set the name exactly as given."""
        char = Character.create_default("Gromm", "Fighter")
        assert char.name == "Gromm"

    @pytest.mark.parametrize(
        "class_name, expected_abilities",
        [
            (
                "Fighter",
                {
                    "STR": 15,
                    "DEX": 13,
                    "CON": 14,
                    "WIS": 12,
                    "INT": 10,
                    "CHA": 8,
                },
            ),
            (
                "Rogue",
                {
                    "STR": 8,
                    "DEX": 15,
                    "CON": 13,
                    "INT": 14,
                    "WIS": 12,
                    "CHA": 10,
                },
            ),
            (
                "Mage",
                {
                    "STR": 8,
                    "DEX": 13,
                    "CON": 14,
                    "INT": 15,
                    "WIS": 12,
                    "CHA": 10,
                },
            ),
            (
                "Cleric",
                {
                    "STR": 13,
                    "DEX": 8,
                    "CON": 14,
                    "INT": 10,
                    "WIS": 15,
                    "CHA": 12,
                },
            ),
        ],
    )
    def test_create_default_abilities_match_expected(
        self,
        class_name: str,
        expected_abilities: dict[str, int],
    ) -> None:
        """Each class must produce the correct ability score array."""
        char = Character.create_default("Test", class_name)
        assert char.abilities == expected_abilities

    @pytest.mark.parametrize(
        "class_name, expected_hp, expected_ac",
        [
            ("Fighter", 12, 18),
            ("Rogue", 9, 14),
            ("Mage", 8, 12),
            ("Cleric", 10, 16),
        ],
    )
    def test_create_default_hp_and_ac(
        self,
        class_name: str,
        expected_hp: int,
        expected_ac: int,
    ) -> None:
        """Each class must produce the correct HP and AC values."""
        char = Character.create_default("Test", class_name)
        assert char.hp == expected_hp
        assert char.max_hp == expected_hp
        assert char.ac == expected_ac

    @pytest.mark.parametrize(
        "class_name, expected_skills",
        [
            ("Fighter", ["Athletics", "Perception"]),
            ("Rogue", ["Stealth", "Sleight of Hand", "Perception"]),
            ("Mage", ["Arcana", "Investigation"]),
            ("Cleric", ["Religion", "Medicine"]),
        ],
    )
    def test_create_default_skills(
        self,
        class_name: str,
        expected_skills: list[str],
    ) -> None:
        """Each class must produce the correct skill proficiencies."""
        char = Character.create_default("Test", class_name)
        assert char.skills == expected_skills

    @pytest.mark.parametrize(
        "class_name, expected_inventory",
        [
            ("Fighter", ["Longsword", "Chain Mail", "Shield", "Explorer's Pack"]),
            (
                "Rogue",
                [
                    "Shortsword",
                    "Leather Armor",
                    "Thieves' Tools",
                    "Burglar's Pack",
                ],
            ),
            ("Mage", ["Spellbook", "Arcane Focus", "Scholar's Pack"]),
            ("Cleric", ["Mace", "Chain Mail", "Shield", "Priest's Pack"]),
        ],
    )
    def test_create_default_inventory(
        self,
        class_name: str,
        expected_inventory: list[str],
    ) -> None:
        """Each class must start with the correct equipment."""
        char = Character.create_default("Test", class_name)
        assert char.inventory == expected_inventory

    def test_create_default_level_and_xp(self) -> None:
        """create_default must set level=1 and xp=0 for all classes."""
        for cls_name in VALID_CLASSES:
            char = Character.create_default("Test", cls_name)
            assert char.level == 1
            assert char.xp == 0

    def test_create_default_invalid_class_raises_value_error(self) -> None:
        """create_default with an invalid class must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid character class"):
            Character.create_default("Test", "Barbarian")

    def test_to_dict_returns_dict_with_all_fields(self) -> None:
        """to_dict must return every dataclass field as a dict key."""
        char = Character.create_default("Lirael", "Mage")
        data = char.to_dict()
        assert isinstance(data, dict)
        for field_name in (
            "name",
            "appearance",
            "personality",
            "backstory",
            "hooks",
            "character_class",
            "level",
            "xp",
            "abilities",
            "skills",
            "hp",
            "max_hp",
            "ac",
            "inventory",
            "gold",
        ):
            assert field_name in data, f"Field {field_name!r} missing from to_dict()"

    def test_to_dict_abilities_are_correct_values(self) -> None:
        """The abilities sub-dict in to_dict must be intact."""
        char = Character.create_default("Korg", "Fighter")
        data = char.to_dict()
        assert data["abilities"]["STR"] == 15
        assert data["abilities"]["DEX"] == 13

    def test_from_dict_round_trips_correctly(self) -> None:
        """from_dict(to_dict()) must produce an identical character."""
        original = Character.create_default("Elara", "Rogue")
        restored = Character.from_dict(original.to_dict())
        for field_name in (
            "name",
            "appearance",
            "personality",
            "backstory",
            "character_class",
            "level",
            "xp",
            "abilities",
            "skills",
            "hp",
            "max_hp",
            "ac",
            "inventory",
            "gold",
        ):
            assert getattr(restored, field_name) == getattr(original, field_name), (
                f"Field {field_name!r} differs after round-trip"
            )
        assert restored.hooks == original.hooks
        assert restored is not original

    def test_from_dict_with_extra_fields_forward_compatibility(self) -> None:
        """Extra keys in the dict must be silently ignored."""
        data = Character.create_default("Fenris", "Cleric").to_dict()
        data["favourite_color"] = "red"
        data["version"] = 2
        char = Character.from_dict(data)
        assert char.name == "Fenris"
        assert char.character_class == "Cleric"

    def test_from_dict_missing_optional_fields_uses_defaults(self) -> None:
        """Omitting optional fields must result in their default values."""
        data: dict[str, object] = {
            "name": "Ash",
            "character_class": "Fighter",
            "abilities": VALID_ABILITIES,
            "hp": 12,
            "max_hp": 12,
            "ac": 16,
        }
        char = Character.from_dict(data)
        assert char.appearance == ""
        assert char.personality == ""
        assert char.backstory == ""
        assert char.hooks == []
        assert char.skills == []
        assert char.inventory == []
        assert char.level == 1
        assert char.xp == 0

    def test_from_dict_minimal_only_name_and_class(self) -> None:
        """from_dict with only name and class must create a valid character."""
        data: dict[str, object] = {
            "name": "Min",
            "character_class": "Mage",
            "abilities": VALID_ABILITIES,
            "hp": 8,
            "max_hp": 8,
            "ac": 10,
        }
        char = Character.from_dict(data)
        assert char.name == "Min"
        assert char.character_class == "Mage"

    def test_from_dict_string_numbers_coerced_to_int(self) -> None:
        """String representations of numbers must be coerced to int."""
        data: dict[str, object] = {
            "name": "Coerce",
            "character_class": "Fighter",
            "abilities": VALID_ABILITIES,
            "level": "3",
            "xp": "150",
            "hp": "25",
            "max_hp": "25",
            "ac": "17",
        }
        char = Character.from_dict(data)
        assert char.level == 3
        assert isinstance(char.level, int)
        assert char.xp == 150
        assert isinstance(char.xp, int)
        assert char.hp == 25
        assert isinstance(char.hp, int)
        assert char.max_hp == 25
        assert isinstance(char.max_hp, int)
        assert char.ac == 17
        assert isinstance(char.ac, int)

    def test_from_dict_none_numeric_fields_use_defaults(self) -> None:
        """None values for numeric fields must fall back to their defaults."""
        data: dict[str, object] = {
            "name": "NullField",
            "character_class": "Fighter",
            "abilities": VALID_ABILITIES,
            "level": None,
            "xp": None,
            "hp": None,
            "max_hp": None,
            "ac": None,
        }
        char = Character.from_dict(data)
        assert char.level == 1
        assert char.xp == 0

    def test_from_dict_with_non_numeric_string_falls_back(self) -> None:
        """Non-numeric strings for int fields must fall back to defaults."""
        data: dict[str, object] = {
            "name": "BadData",
            "character_class": "Fighter",
            "abilities": VALID_ABILITIES,
            "level": "abc",
            "xp": "xyz",
        }
        char = Character.from_dict(data)
        assert char.level == 1
        assert char.xp == 0

    def test_from_dict_empty_dict_raises_value_error(self) -> None:
        """An empty dict cannot produce a valid Character (missing required name)."""
        with pytest.raises(ValueError):
            Character.from_dict({})

    def test_from_dict_missing_abilities_uses_defaults(self) -> None:
        """Omitting abilities entirely must default to all scores of 10."""
        data: dict[str, object] = {
            "name": "NoAbilities",
            "character_class": "Fighter",
            "hp": 10,
            "max_hp": 10,
            "ac": 10,
        }
        char = Character.from_dict(data)
        for abil in STANDARD_ABILITIES:
            assert char.abilities[abil] == 10, (
                f"Ability {abil} should default to 10 when abilities dict is missing"
            )

    def test_from_dict_incomplete_abilities_fills_missing(self) -> None:
        """Partial abilities must preserve given values and default missing to 10."""
        data: dict[str, object] = {
            "name": "PartialAbilities",
            "character_class": "Rogue",
            "abilities": {"STR": 15, "DEX": 14},
            "hp": 9,
            "max_hp": 9,
            "ac": 14,
        }
        char = Character.from_dict(data)
        assert char.abilities["STR"] == 15
        assert char.abilities["DEX"] == 14
        for abil in STANDARD_ABILITIES:
            if abil not in ("STR", "DEX"):
                assert char.abilities[abil] == 10, (
                    f"Ability {abil} should default to 10 when not provided"
                )

    def test_character_gold_default(self) -> None:
        """gold must default to 0."""
        char = _make_minimal_character()
        assert char.gold == 0

    def test_character_gold_serialization(self) -> None:
        """gold must survive to_dict/from_dict round-trip."""
        original = Character.create_default("Glimli", "Fighter")
        assert original.gold == 10  # Fighters get 10gp
        data = original.to_dict()
        assert "gold" in data
        assert data["gold"] == 10
        restored = Character.from_dict(data)
        assert restored.gold == 10

    def test_character_gold_custom_value(self) -> None:
        """gold can be set to any non-negative integer."""
        char = _make_minimal_character(gold=50)
        assert char.gold == 50
        char2 = _make_minimal_character(gold=0)
        assert char2.gold == 0


class TestCharacterPersistence:
    """Tests for CharacterStorage."""

    def test_characters_dir_is_created_automatically(self, tmp_path: Path) -> None:
        """The characters/ subdirectory must exist after construction."""
        store = CharacterStorage(tmp_path)
        assert store.characters_dir.is_dir()

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """Saving a character must create the expected JSON file."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="save_test")
        assert (store.characters_dir / "save_test.json").is_file()

    def test_save_returns_timestamp(self, tmp_path: Path) -> None:
        """The return value of save() must be a timestamp string."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        ts = store.save(char, name="ts_test")
        assert isinstance(ts, str)
        assert len(ts) >= 15

    def test_save_file_contains_valid_json(self, tmp_path: Path) -> None:
        """The contents of the saved JSON file must be parseable."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="json_test")
        with open(store.characters_dir / "json_test.json") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert data["name"] == "Glimli"
        assert data["character_class"] == "Fighter"
        # New format must NOT include legacy flat fields
        assert "hp" not in data
        assert "max_hp" not in data
        assert "ac" not in data
        # New format must include record-specific fields
        assert "inventory" in data
        assert "resources" in data
        assert "equipped_items" in data

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """Round-trip: save then load must yield an identical CharacterRecord."""
        store = CharacterStorage(tmp_path)
        original = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(original, name="roundtrip")
        restored = store.load("roundtrip")
        assert restored.name == original.name
        assert restored.character_class == original.character_class
        assert restored.level == original.level
        assert restored.xp == original.xp
        assert restored.abilities == original.abilities
        assert restored.skills == original.skills
        assert restored.gold == original.gold
        # Compare inventory items
        assert len(restored.inventory) == len(original.inventory)
        for r_item, o_item in zip(restored.inventory, original.inventory):
            assert r_item.name == o_item.name
            assert r_item.item_type == o_item.item_type
            assert r_item.weight == o_item.weight
            assert r_item.value == o_item.value
        # Compare resources
        assert restored.resources.keys() == original.resources.keys()
        for key in original.resources:
            assert restored.resources[key].value == original.resources[key].value
        assert restored.equipped_items == original.equipped_items
        assert restored.hooks == original.hooks
        assert restored is not original

    def test_save_with_custom_name(self, tmp_path: Path) -> None:
        """Saving with an explicit custom name must use that name for the file."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="custom_save")
        assert store.character_exists("custom_save")
        assert not store.character_exists("Glimli")

    def test_save_with_none_name_uses_character_name(self, tmp_path: Path) -> None:
        """Saving with name=None must use the character's own .name field."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char)
        assert store.character_exists("Glimli")

    def test_load_after_multiple_saves(self, tmp_path: Path) -> None:
        """Saving the same character under different names — both must load."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="save_one")
        store.save(char, name="save_two")
        one = store.load("save_one")
        two = store.load("save_two")
        assert one.name == "Glimli"
        assert two.name == "Glimli"
        assert one is not two

    def test_list_empty_directory_returns_empty_list(self, tmp_path: Path) -> None:
        """No saves means list_characters returns an empty list."""
        store = CharacterStorage(tmp_path)
        assert store.list_characters() == []

    def test_list_contains_saved_character(self, tmp_path: Path) -> None:
        """After saving, list_characters must include the metadata entry."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="list_me")
        entries = store.list_characters()
        assert len(entries) == 1
        meta = entries[0]
        assert "timestamp" in meta
        assert meta["class"] == "Fighter"
        assert meta["level"] == 1
        assert meta["name"] == "list_me"

    def test_list_multiple_saves(self, tmp_path: Path) -> None:
        """Multiple saves must all appear in the listing."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="char_a")
        store.save(char, name="char_b")
        store.save(char, name="char_c")
        assert len(store.list_characters()) == 3

    def test_delete_removes_file_from_disk(self, tmp_path: Path) -> None:
        """Deleting a character must remove its JSON file."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="delete_me")
        file_path = store.characters_dir / "delete_me.json"
        assert file_path.is_file()
        store.delete("delete_me")
        assert not file_path.exists()

    def test_delete_removes_from_index(self, tmp_path: Path) -> None:
        """Deleting a character must remove it from the index."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="gone_soon")
        assert len(store.list_characters()) == 1
        store.delete("gone_soon")
        assert len(store.list_characters()) == 0

    def test_delete_nonexistent_raises_file_not_found(self, tmp_path: Path) -> None:
        """Deleting a character that doesn't exist must raise FileNotFoundError."""
        store = CharacterStorage(tmp_path)
        with pytest.raises(FileNotFoundError, match="not found"):
            store.delete("does_not_exist")

    def test_save_exists_returns_true_when_saved(self, tmp_path: Path) -> None:
        """character_exists must return True for a saved character."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="check_me")
        assert store.character_exists("check_me") is True

    def test_save_exists_returns_false_when_not_saved(self, tmp_path: Path) -> None:
        """character_exists must return False for a non-existent character."""
        store = CharacterStorage(tmp_path)
        assert store.character_exists("phantom") is False

    def test_loading_nonexistent_file_raises_file_not_found(
        self,
        tmp_path: Path,
    ) -> None:
        """Loading a non-existent character must raise FileNotFoundError."""
        store = CharacterStorage(tmp_path)
        with pytest.raises(FileNotFoundError, match="not found"):
            store.load("ghost")

    def test_loading_corrupt_json_raises_value_error(self, tmp_path: Path) -> None:
        """Loading a file with invalid JSON must raise ValueError."""
        store = CharacterStorage(tmp_path)
        bad_file = store.characters_dir / "corrupt.json"
        bad_file.write_text("this is not json", encoding="utf-8")
        with pytest.raises(ValueError, match="corrupt|invalid JSON"):
            store.load("corrupt")

    def test_loading_non_dict_json_raises_value_error(self, tmp_path: Path) -> None:
        """Loading valid JSON that is not a dict must raise ValueError."""
        store = CharacterStorage(tmp_path)
        bad_file = store.characters_dir / "not_a_dict.json"
        bad_file.write_text('"just a string"', encoding="utf-8")
        with pytest.raises(ValueError, match="corrupt|expected a JSON object"):
            store.load("not_a_dict")

    def test_overwrite_existing_save_updates_data(self, tmp_path: Path) -> None:
        """Saving again with the same name must overwrite the data."""
        store = CharacterStorage(tmp_path)
        char1 = CharacterRecord.create_default("OldName", "Fighter")
        char2 = CharacterRecord.create_default("NewName", "Rogue")
        store.save(char1, name="overwrite")
        store.save(char2, name="overwrite")
        loaded = store.load("overwrite")
        assert loaded.name == "NewName"
        assert loaded.character_class == "Rogue"

    def test_overwrite_updates_timestamp(self, tmp_path: Path) -> None:
        """Overwriting a save must produce a newer timestamp."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Test", "Fighter")
        ts1 = store.save(char, name="ts_update")
        ts2 = store.save(char, name="ts_update")
        assert ts2 >= ts1

    @pytest.mark.parametrize(
        "bad_name, match_pattern",
        [
            ("my/save", "path separator"),
            ("my\\save", "path separator"),
            ("../../tmp/evil", "(parent directory|path separator)"),
            ("..", "(parent directory|path separator)"),
            ("foo/../bar", "path separator"),
        ],
    )
    def test_save_with_path_traversal_name_raises(
        self,
        tmp_path: Path,
        bad_name: str,
        match_pattern: str,
    ) -> None:
        """Saving with path separators or parent refs must raise ValueError."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        with pytest.raises(ValueError, match=match_pattern):
            store.save(char, name=bad_name)

    def test_save_with_empty_name_raises_value_error(self, tmp_path: Path) -> None:
        """Saving with an empty name must raise ValueError."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        with pytest.raises(ValueError, match="non-empty"):
            store.save(char, name="")

    def test_save_with_whitespace_name_raises_value_error(self, tmp_path: Path) -> None:
        """Saving with a whitespace-only name must raise ValueError."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        with pytest.raises(ValueError, match="non-empty"):
            store.save(char, name="   ")

    def test_save_with_long_name_raises_value_error(self, tmp_path: Path) -> None:
        """Saving with a name > 200 characters must raise ValueError."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        with pytest.raises(ValueError, match="too long"):
            store.save(char, name="a" * 201)

    @pytest.mark.parametrize(
        "operation, bad_name",
        [
            ("load", "a" * 201),
            ("load", "../escape"),
            ("delete", "a" * 201),
            ("delete", "../escape"),
            ("character_exists", "a" * 201),
            ("character_exists", "../escape"),
        ],
    )
    def test_other_operations_validate_name(
        self,
        tmp_path: Path,
        operation: str,
        bad_name: str,
    ) -> None:
        """load, delete, and character_exists must also validate names."""
        store = CharacterStorage(tmp_path)
        with pytest.raises(ValueError):
            if operation == "load":
                store.load(bad_name)
            elif operation == "delete":
                store.delete(bad_name)
            elif operation == "character_exists":
                store.character_exists(bad_name)

    def test_index_is_rebuilt_on_corrupt_index(self, tmp_path: Path) -> None:
        """A corrupt index file must not break subsequent save operations."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="survivor")
        idx_path = store.characters_dir / "index.json"
        idx_path.write_text("{{{corrupt}}}", encoding="utf-8")
        store.save(char, name="new_after_corrupt")
        entries = store.list_characters()
        assert len(entries) >= 1

    def test_characters_dir_auto_recreated_when_deleted(self, tmp_path: Path) -> None:
        """If characters/ directory is deleted, save() must recreate it."""
        import shutil

        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        shutil.rmtree(store.characters_dir)
        assert not store.characters_dir.exists()
        store.save(char, name="after_deletion")
        assert store.characters_dir.is_dir()
        assert store.character_exists("after_deletion")

    def test_delete_with_manually_deleted_file_cleans_index(
        self,
        tmp_path: Path,
    ) -> None:
        """If JSON file is deleted manually, delete() must still clean index."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        store.save(char, name="manually_gone")
        assert len(store.list_characters()) == 1
        save_path = store.characters_dir / "manually_gone.json"
        save_path.unlink()
        store.delete("manually_gone")
        assert len(store.list_characters()) == 0

    def test_tmp_file_cleaned_up_on_save_failure(self, tmp_path: Path) -> None:
        """If saving fails, temp .tmp file must not linger."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        original_mode = store.characters_dir.stat().st_mode
        try:
            store.characters_dir.chmod(0o444)
            with pytest.raises((PermissionError, OSError)):
                store.save(char, name="fail")
        finally:
            store.characters_dir.chmod(original_mode)
        tmp_files = list(store.characters_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Temporary files left behind: {tmp_files}"

    def test_atomic_write_uses_tmp_file(self, tmp_path: Path) -> None:
        """During save, a .tmp file must be used before renaming to final path."""
        store = CharacterStorage(tmp_path)
        char = CharacterRecord.create_default("Glimli", "Fighter")
        original_replace = os.replace
        tmp_paths: list[Path] = []

        def tracking_replace(src: str, dst: str) -> None:
            src_path = Path(src)
            if src_path.suffix == ".tmp":
                assert src_path.exists(), (
                    f"Temp file {src_path} should exist before rename"
                )
                tmp_paths.append(src_path)
            original_replace(src, dst)

        try:
            os.replace = tracking_replace  # type: ignore[assignment]
            store.save(char, name="atomic_test")
            assert len(tmp_paths) >= 1, "No .tmp file was used during save"
        finally:
            os.replace = original_replace
        assert (store.characters_dir / "atomic_test.json").exists()
        assert not (store.characters_dir / "atomic_test.json.tmp").exists()

    # ------------------------------------------------------------------
    # Legacy format handling
    # ------------------------------------------------------------------

    def test_save_accepts_character_with_deprecation(self, tmp_path: Path) -> None:
        """save() accepts Character but shows deprecation warning."""
        store = CharacterStorage(tmp_path)
        char = _make_char()
        with pytest.warns(DeprecationWarning, match="Character is deprecated"):
            store.save(char, name="DeprecatedGuy")
        assert store.character_exists("DeprecatedGuy")

    def test_load_legacy_format_raises_error(self, tmp_path: Path) -> None:
        """Loading an old Character file raises ValueError with migration message."""
        store = CharacterStorage(tmp_path)
        legacy_data: dict[str, object] = {
            "name": "Gimli",
            "character_class": "Fighter",
            "level": 1,
            "hp": 12,
            "max_hp": 12,
            "ac": 16,
            "abilities": {
                "STR": 15,
                "DEX": 13,
                "CON": 14,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            },
            "skills": ["Athletics"],
            "inventory": ["Longsword", "Chain Mail"],
        }
        path = store.characters_dir / "Gimli.json"
        with open(path, "w") as f:
            json.dump(legacy_data, f)
        store._update_index(
            "Gimli",
            {
                "id": "test-id",
                "name": "Gimli",
                "timestamp": "1",
                "class": "Fighter",
                "level": 1,
            },
        )

        with pytest.raises(ValueError, match="legacy"):
            store.load("Gimli")

    def test_convert_legacy_character(self) -> None:
        """_convert_legacy_character converts old format to new."""
        old: dict[str, object] = {
            "name": "Gimli",
            "character_class": "Fighter",
            "level": 1,
            "hp": 12,
            "max_hp": 12,
            "ac": 16,
            "abilities": {
                "STR": 15,
                "DEX": 13,
                "CON": 14,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            },
            "skills": ["Athletics"],
            "inventory": ["Longsword", "Chain Mail"],
        }
        converted = _convert_legacy_character(old)
        # Legacy fields must be removed
        assert "ac" not in converted
        assert "hp" not in converted
        assert "max_hp" not in converted
        # New fields must be added
        assert "equipped_items" in converted
        assert converted["equipped_items"] == []
        assert "resources" in converted
        assert "hp" in converted["resources"]
        assert converted["resources"]["hp"]["value"] == 12
        assert converted["resources"]["hp"]["max"] == 12
        # Inventory must be list of dicts
        assert len(converted["inventory"]) == 2
        assert isinstance(converted["inventory"][0], dict)
        assert converted["inventory"][0]["name"] == "Longsword"

    def test_load_legacy_by_id_raises_error(self, tmp_path: Path) -> None:
        """load_by_id on a legacy file must raise ValueError."""
        store = CharacterStorage(tmp_path)
        legacy_data: dict[str, object] = {
            "id": "legacy-id-123",
            "name": "Gimli",
            "character_class": "Fighter",
            "level": 1,
            "hp": 12,
            "max_hp": 12,
            "ac": 16,
            "abilities": {
                "STR": 15,
                "DEX": 13,
                "CON": 14,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            },
            "skills": ["Athletics"],
            "inventory": ["Longsword", "Chain Mail"],
        }
        path = store.characters_dir / "Gimli_with_id.json"
        with open(path, "w") as f:
            json.dump(legacy_data, f)

        with pytest.raises(ValueError, match="legacy"):
            store.load_by_id("legacy-id-123")


# ---------------------------------------------------------------------------
# Assisted Creation — Task 4.4
# ---------------------------------------------------------------------------


def _make_mock_llm(response_text: str) -> MagicMock:
    """Create a mock LLM provider that returns *response_text* as content."""
    mock = MagicMock()
    mock.call.return_value = {
        "content": response_text,
        "finish_reason": "stop",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }
    return mock


_VALID_CHARACTER_JSON = json.dumps(
    {
        "name": "Rurik Stoneheart",
        "character_class": "Fighter",
        "level": 1,
        "abilities": {"STR": 15, "DEX": 13, "CON": 14, "WIS": 12, "INT": 10, "CHA": 8},
        "skills": ["Athletics", "Perception"],
        "hp": 12,
        "max_hp": 12,
        "ac": 18,
        "appearance": "Stocky dwarf with a braided beard and a scar over one eye.",
        "backstory": (
            "A blacksmith's apprentice who took up arms when orcs raided his village."
        ),
        "inventory": ["Longsword", "Chain Mail", "Shield", "Explorer's Pack"],
    }
)

_VALID_ANSWERS: dict[int, str] = {
    0: "I was a blacksmith's apprentice in a small mountain village.",
    1: "Orcs raided our village and I was the only one who fought back.",
    2: "My strength is my stubbornness; my flaw is that I never back down.",
    3: "I seek redemption for the comrades I couldn't save.",
    4: "My old master would say I was always too hot-headed.",
}


class TestAssistedCreation:
    """Tests for the AssistedCreation class."""

    def test_assisted_creation_requires_at_least_3_answers(self) -> None:
        """Fewer than 3 answers must raise ValueError."""
        mock_llm = _make_mock_llm("{}")
        creation = AssistedCreation(mock_llm)

        with pytest.raises(ValueError, match="At least 3 answers"):
            creation.generate_character({0: "answer1", 1: "answer2"})

    def test_assisted_creation_generates_character(self) -> None:
        """With valid answers and a mock LLM returning valid JSON,
        a Character must be created."""
        mock_llm = _make_mock_llm(_VALID_CHARACTER_JSON)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS)

        assert isinstance(char, Character)
        assert char.name == "Rurik Stoneheart"
        assert char.character_class == "Fighter"
        assert char.abilities["STR"] == 15
        assert char.abilities["DEX"] == 13
        assert "Athletics" in char.skills
        assert char.hp == 12
        assert char.ac == 18

    def test_assisted_creation_retries_on_bad_json(self) -> None:
        """If the first LLM response is invalid JSON, the system must
        retry once.  If the second response is valid, a Character is
        returned."""
        mock_llm = MagicMock()
        mock_llm.call.side_effect = [
            {
                "content": "This is not JSON at all",
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 3,
                    "total_tokens": 8,
                },
            },
            {
                "content": _VALID_CHARACTER_JSON,
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        ]
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS)

        assert isinstance(char, Character)
        assert char.name == "Rurik Stoneheart"
        assert mock_llm.call.call_count == 2

    def test_assisted_creation_fails_after_two_bad_responses(self) -> None:
        """Two invalid LLM responses must raise CharacterGenerationError."""
        mock_llm = MagicMock()
        mock_llm.call.return_value = {
            "content": "not valid json",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }
        creation = AssistedCreation(mock_llm)

        with pytest.raises(CharacterGenerationError, match="Failed to generate"):
            creation.generate_character(_VALID_ANSWERS)

    def test_assisted_creation_validates_class(self) -> None:
        """If the LLM returns an invalid class, CharacterGenerationError
        must be raised."""
        bad_json = json.dumps(
            {
                "name": "Bad Class",
                "character_class": "Paladin",
                "level": 1,
                "abilities": {a: 10 for a in STANDARD_ABILITIES},
                "skills": [],
                "hp": 10,
                "max_hp": 10,
                "ac": 10,
                "appearance": "",
                "backstory": "",
            }
        )
        mock_llm = _make_mock_llm(bad_json)
        creation = AssistedCreation(mock_llm)

        with pytest.raises(CharacterGenerationError, match="Failed to generate"):
            creation.generate_character(_VALID_ANSWERS)

    def test_assisted_creation_validates_ability_range(self) -> None:
        """If the LLM returns an ability score out of range,
        CharacterGenerationError must be raised."""
        bad_json = json.dumps(
            {
                "name": "OP Hero",
                "character_class": "Fighter",
                "level": 1,
                "abilities": {
                    "STR": 99,
                    "DEX": 13,
                    "CON": 14,
                    "WIS": 12,
                    "INT": 10,
                    "CHA": 8,
                },
                "skills": ["Athletics"],
                "hp": 12,
                "max_hp": 12,
                "ac": 18,
                "appearance": "",
                "backstory": "",
            }
        )
        mock_llm = _make_mock_llm(bad_json)
        creation = AssistedCreation(mock_llm)

        with pytest.raises(CharacterGenerationError, match="Failed to generate"):
            creation.generate_character(_VALID_ANSWERS)

    def test_assisted_creation_extracts_json_from_markdown_block(self) -> None:
        """The LLM might wrap JSON in ```json ... ``` fences.
        The parser must still extract the JSON."""
        wrapped = "```json\n" + _VALID_CHARACTER_JSON + "\n```"
        mock_llm = _make_mock_llm(wrapped)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS)
        assert char.name == "Rurik Stoneheart"
        assert char.character_class == "Fighter"

    def test_assisted_creation_uses_all_seven_questions(self) -> None:
        """QUESTIONS must have exactly 7 entries."""
        assert len(AssistedCreation.QUESTIONS) == 7

    def test_assisted_creation_questions_are_non_empty(self) -> None:
        """Every question in QUESTIONS must be a non-empty string."""
        for q in AssistedCreation.QUESTIONS:
            assert isinstance(q, str) and len(q) > 20

    def test_assisted_creation_with_empty_name_triggers_retry(self) -> None:
        """An empty or null name in the LLM response must trigger a retry,
        then raise CharacterGenerationError if the second attempt also
        has an empty name."""
        bad_json = json.dumps(
            {
                "name": "",
                "character_class": "Fighter",
                "level": 1,
                "abilities": {a: 10 for a in STANDARD_ABILITIES},
                "skills": [],
                "hp": 10,
                "max_hp": 10,
                "ac": 10,
                "appearance": "",
                "backstory": "",
                "inventory": [],
            }
        )
        mock_llm = _make_mock_llm(bad_json)
        creation = AssistedCreation(mock_llm)

        with pytest.raises(CharacterGenerationError, match="Failed to generate"):
            creation.generate_character(_VALID_ANSWERS)

    def test_assisted_creation_with_missing_numeric_fields_triggers_retry(
        self,
    ) -> None:
        """If hp/max_hp/ac are missing from the JSON, validation must
        return None and trigger a retry."""
        bad_json = json.dumps(
            {
                "name": "NoHP",
                "character_class": "Fighter",
                "level": 1,
                "abilities": {a: 10 for a in STANDARD_ABILITIES},
                "skills": [],
                "inventory": [],
                "appearance": "",
                "backstory": "",
            }
        )
        mock_llm = _make_mock_llm(bad_json)
        creation = AssistedCreation(mock_llm)

        with pytest.raises(CharacterGenerationError, match="Failed to generate"):
            creation.generate_character(_VALID_ANSWERS)

    def test_assisted_creation_with_non_dict_abilities_triggers_retry(
        self,
    ) -> None:
        """If abilities is not a dict, validation must return None and retry."""
        bad_json = json.dumps(
            {
                "name": "BadAbilities",
                "character_class": "Fighter",
                "level": 1,
                "abilities": "not_a_dict",
                "skills": [],
                "hp": 10,
                "max_hp": 10,
                "ac": 10,
                "appearance": "",
                "backstory": "",
                "inventory": [],
            }
        )
        mock_llm = _make_mock_llm(bad_json)
        creation = AssistedCreation(mock_llm)

        with pytest.raises(CharacterGenerationError, match="Failed to generate"):
            creation.generate_character(_VALID_ANSWERS)

    def test_assisted_creation_non_list_skills_and_inventory_use_defaults(
        self,
    ) -> None:
        """When skills and inventory are not lists in the LLM response,
        they should default to empty lists rather than failing."""
        resilient_json = json.dumps(
            {
                "name": "Resilient",
                "character_class": "Mage",
                "level": 1,
                "abilities": {a: 10 for a in STANDARD_ABILITIES},
                "skills": "not_a_list",
                "inventory": None,
                "hp": 8,
                "max_hp": 8,
                "ac": 12,
                "appearance": "",
                "backstory": "",
            }
        )
        mock_llm = _make_mock_llm(resilient_json)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS)
        assert char.skills == []
        assert char.inventory == []

    def test_assisted_creation_extracts_json_from_text_prefix(self) -> None:
        """The LLM might return plain text before the JSON block.
        The parser must still extract the JSON using the regex fallback."""
        prefixed = "Here is your character:\n" + _VALID_CHARACTER_JSON
        mock_llm = _make_mock_llm(prefixed)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS)
        assert char.name == "Rurik Stoneheart"
        assert char.character_class == "Fighter"

    def test_assisted_creation_with_character_constructor_error_retries(
        self,
    ) -> None:
        """If the Character constructor raises ValueError (e.g. negative
        level), the error must be caught and a retry triggered."""
        bad_json = json.dumps(
            {
                "name": "BadLevel",
                "character_class": "Fighter",
                "level": -1,
                "abilities": {a: 10 for a in STANDARD_ABILITIES},
                "skills": [],
                "hp": 10,
                "max_hp": 10,
                "ac": 10,
                "appearance": "",
                "backstory": "",
                "inventory": [],
            }
        )
        mock_llm = _make_mock_llm(bad_json)
        creation = AssistedCreation(mock_llm)

        with pytest.raises(CharacterGenerationError, match="Failed to generate"):
            creation.generate_character(_VALID_ANSWERS)

    def test_assisted_creation_with_abilities_includes_stat_references(
        self,
    ) -> None:
        """When abilities are passed, the LLM system prompt includes them
        and the generated backstory should reflect extreme stats."""
        abilities = {
            "STR": 18,
            "DEX": 10,
            "CON": 14,
            "INT": 10,
            "WIS": 10,
            "CHA": 10,
        }
        strong_json = json.dumps(
            {
                "name": "Grom Ironfist",
                "character_class": "Fighter",
                "level": 1,
                "abilities": abilities,
                "skills": ["Athletics", "Perception"],
                "hp": 14,
                "max_hp": 14,
                "ac": 18,
                "appearance": (
                    "A towering figure with broad shoulders and corded muscle. "
                    "His arms are thick as tree trunks from years of lifting "
                    "heavy stone."
                ),
                "backstory": (
                    "Born in a small farming village, Grom was always the biggest "
                    "and strongest. By age twelve he could lift a horse. When a "
                    "flood destroyed his village, he single-handedly held back a "
                    "falling barn door long enough to save three children, earning "
                    "a reputation as the strongest man in the county."
                ),
                "inventory": ["Longsword", "Chain Mail", "Shield", "Explorer's Pack"],
            }
        )
        mock_llm = _make_mock_llm(strong_json)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS, abilities=abilities)

        assert isinstance(char, Character)
        assert char.name == "Grom Ironfist"
        assert char.abilities["STR"] == 18
        assert (
            "strongest" in char.backstory.lower()
            or "strength" in char.backstory.lower()
        )

    def test_assisted_creation_without_abilities_still_works(
        self,
    ) -> None:
        """When no abilities are passed, generation must still succeed
        using default ability values in the prompt."""
        mock_llm = _make_mock_llm(_VALID_CHARACTER_JSON)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS)

        assert isinstance(char, Character)
        assert char.name == "Rurik Stoneheart"

    def test_assisted_creation_abilities_passed_to_user_message(self) -> None:
        """When abilities are provided, they must appear in the user message
        sent to the LLM."""
        abilities = {"STR": 3, "DEX": 18, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        mock_llm = _make_mock_llm(_VALID_CHARACTER_JSON)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS, abilities=abilities)

        # Verify the call was made (LLM was invoked)
        assert mock_llm.call.called
        assert isinstance(char, Character)
        assert char.name == "Rurik Stoneheart"

    # ------------------------------------------------------------------
    # Name integration — Task 1 of Campfire campaign
    # ------------------------------------------------------------------

    def test_assisted_creation_passes_name_to_llm(self) -> None:
        """The player's name must appear in the LLM call messages when
        provided."""
        mock_llm = _make_mock_llm(_VALID_CHARACTER_JSON)
        creation = AssistedCreation(mock_llm)

        creation.generate_character(_VALID_ANSWERS, name="Thorne Ironveil")

        assert mock_llm.call.called
        messages = mock_llm.call.call_args[0][0]
        all_text = " ".join(m["content"] for m in messages)
        assert "Thorne Ironveil" in all_text

    def test_assisted_creation_uses_provided_name(self) -> None:
        """When a name is provided, the LLM response with that name must
        produce a character with that same name."""
        named_json = json.dumps(
            {
                "name": "Thorne Ironveil",
                "character_class": "Fighter",
                "level": 1,
                "abilities": {a: 10 for a in STANDARD_ABILITIES},
                "skills": [],
                "hp": 10,
                "max_hp": 10,
                "ac": 10,
                "appearance": "",
                "backstory": "",
                "inventory": [],
            }
        )
        mock_llm = _make_mock_llm(named_json)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS, name="Thorne Ironveil")

        assert char.name == "Thorne Ironveil"

    def test_assisted_creation_without_name_generates_one(self) -> None:
        """Without a provided name, the LLM-generated name from the
        response must be used."""
        mock_llm = _make_mock_llm(_VALID_CHARACTER_JSON)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS)

        assert char.name == "Rurik Stoneheart"
        assert isinstance(char, Character)

    def test_assisted_creation_empty_name_treated_as_none(self) -> None:
        """An empty-string name must behave identically to no name —
        backward compatible."""
        mock_llm = _make_mock_llm(_VALID_CHARACTER_JSON)
        creation = AssistedCreation(mock_llm)

        char = creation.generate_character(_VALID_ANSWERS, name="")

        assert char.name == "Rurik Stoneheart"
        assert isinstance(char, Character)

    def test_assisted_creation_name_included_in_prompt_system_message(
        self,
    ) -> None:
        """The player name must appear in the system message, not the
        user message, to verify the prompt formatting is correct."""
        mock_llm = _make_mock_llm(_VALID_CHARACTER_JSON)
        creation = AssistedCreation(mock_llm)

        creation.generate_character(_VALID_ANSWERS, name="Thorne Ironveil")

        assert mock_llm.call.called
        messages = mock_llm.call.call_args[0][0]
        system_content = next(m["content"] for m in messages if m["role"] == "system")
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "Thorne Ironveil" in system_content
        assert "Thorne Ironveil" not in user_content


# ---------------------------------------------------------------------------
# CharacterRecord — Task 1.4
# ---------------------------------------------------------------------------


def _make_minimal_record(**overrides: object) -> CharacterRecord:
    """Build a minimally-valid CharacterRecord for use across tests."""
    defaults: dict[str, object] = {
        "name": "Borin",
        "character_class": "Fighter",
        "abilities": {a: 10 for a in STANDARD_ABILITIES},
    }
    defaults.update(overrides)
    return CharacterRecord(**defaults)  # type: ignore[arg-type]


class TestCharacterRecord:
    """Tests for the CharacterRecord dataclass."""

    def test_create_with_all_fields(self) -> None:
        """CharacterRecord must store all player-choice fields."""
        record = CharacterRecord(
            name="Zara Moonshadow",
            character_class="Rogue",
            level=3,
            xp=900,
            abilities={
                "STR": 10,
                "DEX": 16,
                "CON": 13,
                "INT": 14,
                "WIS": 12,
                "CHA": 10,
            },
            skills=["Stealth", "Perception", "Sleight of Hand"],
            gold=50,
            inventory=[
                Item(name="Shortsword", item_type=ItemType.WEAPON, weight=2.0),
            ],
            equipped_items=["bow_id"],
            resources={"hp": ResourceData(value=20, max=20)},
            appearance="Elven, silver hair",
            personality="Curious",
            backstory="Grew up in the woods.",
            hooks=["Find the lost artifact"],
        )
        assert record.name == "Zara Moonshadow"
        assert record.character_class == "Rogue"
        assert record.level == 3
        assert record.xp == 900
        assert record.abilities["DEX"] == 16
        assert "Stealth" in record.skills
        assert record.gold == 50
        assert len(record.inventory) == 1
        assert isinstance(record.inventory[0], Item)
        assert record.inventory[0].name == "Shortsword"
        assert record.equipped_items == ["bow_id"]
        assert "hp" in record.resources
        assert isinstance(record.resources["hp"], ResourceData)
        assert record.resources["hp"].value == 20
        assert record.appearance == "Elven, silver hair"
        assert record.personality == "Curious"
        assert record.backstory == "Grew up in the woods."
        assert record.hooks == ["Find the lost artifact"]

    def test_defaults(self) -> None:
        """CharacterRecord must have sensible defaults for all fields."""
        record = CharacterRecord(
            name="TestHero",
            abilities={a: 10 for a in STANDARD_ABILITIES},
        )
        assert isinstance(record.id, str) and len(record.id) > 0
        assert record.name == "TestHero"
        assert record.character_class == "Fighter"
        assert record.level == 1
        assert record.xp == 0
        assert record.abilities == {a: 10 for a in STANDARD_ABILITIES}
        assert record.skills == []
        assert record.gold == 0
        assert record.inventory == []
        assert record.equipped_items == []
        assert record.resources == {}
        assert record.appearance == ""
        assert record.personality == ""
        assert record.backstory == ""
        assert record.hooks == []

    def test_does_not_store_ac_hp_max_hp(self) -> None:
        """CharacterRecord must NOT have ac, hp, or max_hp fields."""
        record = _make_minimal_record()
        assert not hasattr(record, "ac")
        assert not hasattr(record, "hp")
        assert not hasattr(record, "max_hp")

    def test_inventory_is_list_of_items(self) -> None:
        """CharacterRecord.inventory must be a list[Item], not list[str]."""
        record = _make_minimal_record()
        assert record.inventory == []
        record.inventory.append(Item(name="Test Sword", item_type=ItemType.WEAPON))
        assert len(record.inventory) == 1
        assert isinstance(record.inventory[0], Item)

    def test_resources_is_dict_of_resource_data(self) -> None:
        """CharacterRecord.resources must be a dict[str, ResourceData]."""
        record = _make_minimal_record()
        assert record.resources == {}
        record.resources["hp"] = ResourceData(value=15, max=15)
        assert isinstance(record.resources["hp"], ResourceData)

    @pytest.mark.parametrize("class_name", sorted(VALID_CLASSES))
    def test_create_default_for_each_class(self, class_name: str) -> None:
        """CharacterRecord.create_default must work for all four classes."""
        record = CharacterRecord.create_default("TestHero", class_name)
        assert record.name == "TestHero"
        assert record.character_class == class_name
        assert record.level == 1
        assert record.xp == 0
        assert len(record.abilities) == 6
        assert all(a in record.abilities for a in STANDARD_ABILITIES)
        assert len(record.skills) >= 1
        assert record.gold >= 0
        assert len(record.inventory) >= 1
        assert all(isinstance(item, Item) for item in record.inventory)
        assert "hp" in record.resources
        assert isinstance(record.resources["hp"], ResourceData)
        assert record.resources["hp"].value > 0
        assert record.resources["hp"].max is not None  # max can be int or str
        if isinstance(record.resources["hp"].max, int):
            assert record.resources["hp"].max > 0

    @pytest.mark.parametrize(
        "class_name, expected_abilities",
        [
            (
                "Fighter",
                {"STR": 15, "DEX": 13, "CON": 14, "WIS": 12, "INT": 10, "CHA": 8},
            ),
            (
                "Rogue",
                {"STR": 8, "DEX": 15, "CON": 13, "INT": 14, "WIS": 12, "CHA": 10},
            ),
            (
                "Mage",
                {"STR": 8, "DEX": 13, "CON": 14, "INT": 15, "WIS": 12, "CHA": 10},
            ),
            (
                "Cleric",
                {"STR": 13, "DEX": 8, "CON": 14, "INT": 10, "WIS": 15, "CHA": 12},
            ),
        ],
    )
    def test_create_default_abilities(
        self,
        class_name: str,
        expected_abilities: dict[str, int],
    ) -> None:
        """Each class must produce the correct ability score array."""
        record = CharacterRecord.create_default("Test", class_name)
        assert record.abilities == expected_abilities

    @pytest.mark.parametrize(
        "class_name, expected_skills",
        [
            ("Fighter", ["Athletics", "Perception"]),
            ("Rogue", ["Stealth", "Sleight of Hand", "Perception"]),
            ("Mage", ["Arcana", "Investigation"]),
            ("Cleric", ["Religion", "Medicine"]),
        ],
    )
    def test_create_default_skills(
        self,
        class_name: str,
        expected_skills: list[str],
    ) -> None:
        """Each class must produce the correct skill proficiencies."""
        record = CharacterRecord.create_default("Test", class_name)
        assert record.skills == expected_skills

    @pytest.mark.parametrize(
        "class_name, expected_gold",
        [
            ("Fighter", 10),
            ("Rogue", 15),
            ("Mage", 20),
            ("Cleric", 10),
        ],
    )
    def test_create_default_gold(self, class_name: str, expected_gold: int) -> None:
        """Each class must start with the correct gold."""
        record = CharacterRecord.create_default("Test", class_name)
        assert record.gold == expected_gold

    def test_create_default_level_and_xp(self) -> None:
        """create_default must set level=1 and xp=0 for all classes."""
        for cls_name in VALID_CLASSES:
            record = CharacterRecord.create_default("Test", cls_name)
            assert record.level == 1
            assert record.xp == 0

    def test_create_default_invalid_class_raises_value_error(self) -> None:
        """create_default with an invalid class must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid character class"):
            CharacterRecord.create_default("Test", "Barbarian")

    def test_to_dict_returns_dict_with_all_fields(self) -> None:
        """to_dict must return a dictionary with all expected keys."""
        record = CharacterRecord.create_default("Lirael", "Mage")
        data = record.to_dict()
        assert isinstance(data, dict)
        for field_name in (
            "id",
            "name",
            "appearance",
            "personality",
            "backstory",
            "hooks",
            "character_class",
            "level",
            "xp",
            "abilities",
            "skills",
            "gold",
            "inventory",
            "equipped_items",
            "resources",
        ):
            assert field_name in data, f"Field {field_name!r} missing from to_dict()"
        # AC, HP, max_hp must NOT appear
        assert "ac" not in data
        assert "hp" not in data
        assert "max_hp" not in data

    def test_to_dict_serializes_items(self) -> None:
        """Inventory items in to_dict must be serialized dicts, not Item objects."""
        record = CharacterRecord.create_default("Korg", "Fighter")
        data = record.to_dict()
        assert isinstance(data["inventory"], list)
        if data["inventory"]:
            assert isinstance(data["inventory"][0], dict)
            assert "name" in data["inventory"][0]
            assert "item_type" in data["inventory"][0]

    def test_to_dict_serializes_resources(self) -> None:
        """Resources in to_dict must be serialized dicts."""
        record = CharacterRecord.create_default("Korg", "Fighter")
        data = record.to_dict()
        assert isinstance(data["resources"], dict)
        if data["resources"]:
            hp_data = data["resources"].get("hp", {})
            assert isinstance(hp_data, dict)
            assert "value" in hp_data
            assert "max" in hp_data

    def test_to_dict_abilities_are_correct_values(self) -> None:
        """The abilities sub-dict in to_dict must be intact."""
        record = CharacterRecord.create_default("Korg", "Fighter")
        data = record.to_dict()
        assert data["abilities"]["STR"] == 15
        assert data["abilities"]["DEX"] == 13

    def test_from_dict_round_trips_correctly(self) -> None:
        """from_dict(to_dict()) must produce an identical character record."""
        original = CharacterRecord.create_default("Elara", "Rogue")
        restored = CharacterRecord.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.character_class == original.character_class
        assert restored.level == original.level
        assert restored.xp == original.xp
        assert restored.abilities == original.abilities
        assert restored.skills == original.skills
        assert restored.gold == original.gold
        assert len(restored.inventory) == len(original.inventory)
        for r_item, o_item in zip(restored.inventory, original.inventory):
            assert r_item.name == o_item.name
            assert r_item.item_type == o_item.item_type
            assert r_item.weight == o_item.weight
            assert r_item.value == o_item.value
        assert restored.resources.keys() == original.resources.keys()
        for key in original.resources:
            assert restored.resources[key].value == original.resources[key].value
            assert restored.resources[key].max == original.resources[key].max
        assert restored.equipped_items == original.equipped_items
        assert restored.hooks == original.hooks
        assert restored is not original

    def test_from_dict_with_extra_fields_forward_compatibility(self) -> None:
        """Extra keys in the dict must be silently ignored."""
        data = CharacterRecord.create_default("Fenris", "Cleric").to_dict()
        data["favourite_color"] = "red"
        data["version"] = 2
        record = CharacterRecord.from_dict(data)
        assert record.name == "Fenris"
        assert record.character_class == "Cleric"

    def test_from_dict_missing_optional_fields_uses_defaults(self) -> None:
        """Omitting optional fields must result in their default values."""
        data: dict[str, object] = {
            "name": "Ash",
            "character_class": "Fighter",
            "abilities": {a: 10 for a in STANDARD_ABILITIES},
        }
        record = CharacterRecord.from_dict(data)
        assert record.appearance == ""
        assert record.personality == ""
        assert record.backstory == ""
        assert record.hooks == []
        assert record.skills == []
        assert record.inventory == []
        assert record.equipped_items == []
        assert record.resources == {}
        assert record.level == 1
        assert record.xp == 0
        assert record.gold == 0

    def test_from_dict_minimal_only_name_and_class(self) -> None:
        """from_dict with only name and class must create a valid record."""
        data: dict[str, object] = {
            "name": "Min",
            "character_class": "Mage",
            "abilities": {a: 10 for a in STANDARD_ABILITIES},
        }
        record = CharacterRecord.from_dict(data)
        assert record.name == "Min"
        assert record.character_class == "Mage"

    def test_from_dict_restores_item_objects(self) -> None:
        """Items from from_dict must be Item instances, not plain dicts."""
        original = CharacterRecord.create_default("Glimli", "Fighter")
        restored = CharacterRecord.from_dict(original.to_dict())
        for item in restored.inventory:
            assert isinstance(item, Item)
            assert isinstance(item.item_type, ItemType)

    def test_from_dict_restores_resource_data_objects(self) -> None:
        """Resources from from_dict must be ResourceData instances."""
        original = CharacterRecord.create_default("Glimli", "Fighter")
        restored = CharacterRecord.from_dict(original.to_dict())
        for key in restored.resources:
            assert isinstance(restored.resources[key], ResourceData)

    def test_from_dict_string_numbers_coerced_to_int(self) -> None:
        """String representations of numbers must be coerced to int."""
        data: dict[str, object] = {
            "name": "Coerce",
            "character_class": "Fighter",
            "abilities": {a: 10 for a in STANDARD_ABILITIES},
            "level": "3",
            "xp": "150",
            "gold": "25",
        }
        record = CharacterRecord.from_dict(data)
        assert record.level == 3
        assert isinstance(record.level, int)
        assert record.xp == 150
        assert isinstance(record.xp, int)
        assert record.gold == 25
        assert isinstance(record.gold, int)

    def test_from_dict_empty_dict_raises_value_error(self) -> None:
        """An empty dict cannot produce a valid record (missing required name)."""
        with pytest.raises(ValueError):
            CharacterRecord.from_dict({})

    def test_from_dict_missing_abilities_uses_defaults(self) -> None:
        """Omitting abilities entirely must default to all scores of 10."""
        data: dict[str, object] = {
            "name": "NoAbilities",
            "character_class": "Fighter",
        }
        record = CharacterRecord.from_dict(data)
        for abil in STANDARD_ABILITIES:
            assert record.abilities[abil] == 10, (
                f"Ability {abil} should default to 10 when abilities dict is missing"
            )

    # --- Validation tests ---

    def test_empty_name_raises_value_error(self) -> None:
        """An empty-string name must raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            CharacterRecord(
                name="",
                character_class="Fighter",
                abilities={a: 10 for a in STANDARD_ABILITIES},
            )

    def test_whitespace_only_name_raises_value_error(self) -> None:
        """A name composed only of whitespace must raise ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            _make_minimal_record(name="   \t  ")

    def test_invalid_class_raises_value_error(self) -> None:
        """An unrecognised character_class must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid character class"):
            _make_minimal_record(character_class="Paladin")

    @pytest.mark.parametrize("valid_class", sorted(VALID_CLASSES))
    def test_valid_classes_accepted(self, valid_class: str) -> None:
        """Each class in VALID_CLASSES must be accepted by the constructor."""
        record = _make_minimal_record(character_class=valid_class)
        assert record.character_class == valid_class

    def test_missing_ability_score_raises_value_error(self) -> None:
        """Omitting one of the six abilities must raise ValueError."""
        incomplete = {a: 10 for a in STANDARD_ABILITIES if a != "CHA"}
        with pytest.raises(ValueError, match="Missing ability"):
            CharacterRecord(
                name="Test",
                character_class="Fighter",
                abilities=incomplete,
            )

    def test_ability_score_below_3_raises_value_error(self) -> None:
        """An ability score of 2 must raise ValueError."""
        bad = {a: 10 for a in STANDARD_ABILITIES}
        bad["STR"] = 2
        with pytest.raises(ValueError, match="out of range"):
            CharacterRecord(name="Test", character_class="Fighter", abilities=bad)

    def test_ability_score_above_18_raises_value_error(self) -> None:
        """An ability score of 19 must raise ValueError."""
        bad = {a: 10 for a in STANDARD_ABILITIES}
        bad["DEX"] = 19
        with pytest.raises(ValueError, match="out of range"):
            CharacterRecord(name="Test", character_class="Fighter", abilities=bad)

    def test_level_zero_raises_value_error(self) -> None:
        """Level 0 must raise ValueError."""
        with pytest.raises(ValueError, match="Level must be >= 1"):
            _make_minimal_record(level=0)

    def test_negative_xp_raises_value_error(self) -> None:
        """Negative XP must raise ValueError."""
        with pytest.raises(ValueError, match="XP must be >= 0"):
            _make_minimal_record(xp=-1)


# ---------------------------------------------------------------------------
# DerivedSheet — Task 1.4
# ---------------------------------------------------------------------------


class TestDerivedSheet:
    """Tests for the DerivedSheet dataclass."""

    def test_defaults(self) -> None:
        """DerivedSheet must have sensible defaults."""
        sheet = DerivedSheet()
        assert sheet.ability_modifiers == {}
        assert sheet.proficiency_bonus == 2
        assert sheet.ac == 10
        assert sheet.initiative == 0
        assert sheet.speed == 30
        assert sheet.skill_modifiers == {}
        assert sheet.saving_throw_modifiers == {}
        assert sheet.passive_perception == 10
        assert sheet.attack_bonus == {}
        assert sheet.encumbrance == {}
        assert sheet.hit_dice == ""
        assert sheet.resistances == []
        assert sheet.vulnerabilities == []
        assert sheet.formulas == {}

    def test_to_dict_returns_all_fields(self) -> None:
        """to_dict must return a dict with all fields."""
        sheet = DerivedSheet(
            ability_modifiers={"STR": 3, "DEX": 1},
            proficiency_bonus=3,
            ac=18,
            initiative=2,
            skill_modifiers={"Athletics": 5, "Perception": 3},
            saving_throw_modifiers={"STR": 5, "CON": 4},
            passive_perception=13,
            attack_bonus={"Longsword": 5},
            encumbrance={"current": 45.0, "max": 150.0},
            hit_dice="1d10",
            resistances=["fire"],
            vulnerabilities=["cold"],
            formulas={"hp": "12+CON", "ac": "10+DEX"},
        )
        data = sheet.to_dict()
        assert isinstance(data, dict)
        assert data["ability_modifiers"]["STR"] == 3
        assert data["proficiency_bonus"] == 3
        assert data["ac"] == 18
        assert data["initiative"] == 2
        assert data["skill_modifiers"]["Athletics"] == 5
        assert data["saving_throw_modifiers"]["STR"] == 5
        assert data["passive_perception"] == 13
        assert data["attack_bonus"]["Longsword"] == 5
        assert data["encumbrance"]["current"] == 45.0
        assert data["hit_dice"] == "1d10"
        assert data["resistances"] == ["fire"]
        assert data["vulnerabilities"] == ["cold"]
        assert data["formulas"]["hp"] == "12+CON"

    def test_to_dict_round_trip_with_constructor(self) -> None:
        """to_dict output must be usable to reconstruct via constructor."""
        original = DerivedSheet(
            ac=15,
            proficiency_bonus=4,
            ability_modifiers={"STR": 2, "DEX": 3},
        )
        data = original.to_dict()
        restored = DerivedSheet(**data)
        assert restored.ac == 15
        assert restored.proficiency_bonus == 4
        assert restored.ability_modifiers == {"STR": 2, "DEX": 3}

    def test_no_from_dict_method(self) -> None:
        """DerivedSheet must NOT have a from_dict method — it's never persisted."""
        assert not hasattr(DerivedSheet, "from_dict")

    def test_default_ac_is_10(self) -> None:
        """Default AC must be 10."""
        assert DerivedSheet().ac == 10

    def test_default_proficiency_bonus_is_2(self) -> None:
        """Default proficiency bonus must be 2 for level 1."""
        assert DerivedSheet().proficiency_bonus == 2
