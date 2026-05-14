"""Tests for the Character data model and persistence — Phase 4, Task 4.2."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.character.creation import CharacterStorage
from app.character.model import STANDARD_ABILITIES, VALID_CLASSES, Character


def _make_minimal_character(**overrides: object) -> Character:
    """Build a minimally-valid Character for use across tests."""
    defaults: dict[str, object] = {
        "name": "Borin",
        "character_class": "Fighter",
        "abilities": {a: 10 for a in STANDARD_ABILITIES},
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
        assert set(char.abilities.keys()) == STANDARD_ABILITIES

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
            Character(name="   \t  ", character_class="Fighter", abilities=VALID_ABILITIES)

    def test_invalid_class_raises_value_error(self) -> None:
        """An unrecognised character_class must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid character class"):
            Character(name="Test", character_class="Paladin", abilities=VALID_ABILITIES)

    @pytest.mark.parametrize("valid_class", sorted(VALID_CLASSES))
    def test_valid_classes_accepted(self, valid_class: str) -> None:
        """Each class in VALID_CLASSES must be accepted by the constructor."""
        char = Character(name="Test", character_class=valid_class, abilities=VALID_ABILITIES)
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
            Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, level=0)

    def test_level_negative_raises_value_error(self) -> None:
        """A negative level must raise ValueError."""
        with pytest.raises(ValueError, match="Level must be >= 1"):
            Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, level=-5)

    def test_negative_xp_raises_value_error(self) -> None:
        """Negative XP must raise ValueError."""
        with pytest.raises(ValueError, match="XP must be >= 0"):
            Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, xp=-1)

    def test_xp_zero_is_valid(self) -> None:
        """XP == 0 is the standard starting value and must be accepted."""
        char = Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, xp=0)
        assert char.xp == 0

    def test_negative_hp_raises_value_error(self) -> None:
        """Negative HP must raise ValueError."""
        with pytest.raises(ValueError, match="HP must be >= 0"):
            Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, hp=-1, max_hp=10)

    def test_zero_hp_is_valid(self) -> None:
        """HP == 0 (unconscious) must be accepted."""
        char = Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, hp=0, max_hp=10)
        assert char.hp == 0

    def test_zero_max_hp_raises_value_error(self) -> None:
        """max_hp of 0 must raise ValueError."""
        with pytest.raises(ValueError, match="max_hp must be > 0"):
            Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, hp=10, max_hp=0)

    def test_negative_max_hp_raises_value_error(self) -> None:
        """Negative max_hp must raise ValueError."""
        with pytest.raises(ValueError, match="max_hp must be > 0"):
            Character(name="Test", character_class="Fighter", abilities=VALID_ABILITIES, hp=10, max_hp=-5)

    def test_create_default_creates_with_correct_name(self) -> None:
        """create_default must set the name exactly as given."""
        char = Character.create_default("Gromm", "Fighter")
        assert char.name == "Gromm"

    @pytest.mark.parametrize(
        "class_name, expected_abilities",
        [
            ("Fighter", {"STR": 15, "DEX": 13, "CON": 14, "WIS": 12, "INT": 10, "CHA": 8}),
            ("Rogue", {"STR": 8, "DEX": 15, "CON": 13, "INT": 14, "WIS": 12, "CHA": 10}),
            ("Mage", {"STR": 8, "DEX": 13, "CON": 14, "INT": 15, "WIS": 12, "CHA": 10}),
            ("Cleric", {"STR": 13, "DEX": 8, "CON": 14, "INT": 10, "WIS": 15, "CHA": 12}),
        ],
    )
    def test_create_default_abilities_match_expected(self, class_name: str, expected_abilities: dict[str, int]) -> None:
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
    def test_create_default_hp_and_ac(self, class_name: str, expected_hp: int, expected_ac: int) -> None:
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
    def test_create_default_skills(self, class_name: str, expected_skills: list[str]) -> None:
        """Each class must produce the correct skill proficiencies."""
        char = Character.create_default("Test", class_name)
        assert char.skills == expected_skills

    @pytest.mark.parametrize(
        "class_name, expected_inventory",
        [
            ("Fighter", ["Longsword", "Chain Mail", "Shield", "Explorer's Pack"]),
            ("Rogue", ["Shortsword", "Leather Armor", "Thieves' Tools", "Burglar's Pack"]),
            ("Mage", ["Spellbook", "Arcane Focus", "Scholar's Pack"]),
            ("Cleric", ["Mace", "Chain Mail", "Shield", "Priest's Pack"]),
        ],
    )
    def test_create_default_inventory(self, class_name: str, expected_inventory: list[str]) -> None:
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
            "name", "appearance", "personality", "backstory", "hooks",
            "character_class", "level", "xp", "abilities", "skills",
            "hp", "max_hp", "ac", "inventory",
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
            "name", "appearance", "personality", "backstory",
            "character_class", "level", "xp", "abilities", "skills",
            "hp", "max_hp", "ac", "inventory",
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

    def test_from_dict_empty_dict_raises_type_error(self) -> None:
        """An empty dict cannot produce a valid Character (missing required name)."""
        with pytest.raises(TypeError, match="missing.*required.*argument.*name"):
            Character.from_dict({})


class TestCharacterPersistence:
    """Tests for CharacterStorage."""

    def test_characters_dir_is_created_automatically(self, tmp_path: Path) -> None:
        """The characters/ subdirectory must exist after construction."""
        store = CharacterStorage(tmp_path)
        assert store.characters_dir.is_dir()

    def test_save_creates_file(self, tmp_path: Path) -> None:
        """Saving a character must create the expected JSON file."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="save_test")
        assert (store.characters_dir / "save_test.json").is_file()

    def test_save_returns_timestamp(self, tmp_path: Path) -> None:
        """The return value of save() must be a timestamp string."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        ts = store.save(char, name="ts_test")
        assert isinstance(ts, str)
        assert len(ts) >= 15

    def test_save_file_contains_valid_json(self, tmp_path: Path) -> None:
        """The contents of the saved JSON file must be parseable."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="json_test")
        with open(store.characters_dir / "json_test.json") as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert data["name"] == "Glimli"
        assert data["character_class"] == "Fighter"

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        """Round-trip: save then load must yield an identical Character."""
        store = CharacterStorage(tmp_path)
        original = Character.create_default("Glimli", "Fighter")
        store.save(original, name="roundtrip")
        restored = store.load("roundtrip")
        assert restored.name == original.name
        assert restored.character_class == original.character_class
        assert restored.level == original.level
        assert restored.xp == original.xp
        assert restored.abilities == original.abilities
        assert restored.skills == original.skills
        assert restored.hp == original.hp
        assert restored.max_hp == original.max_hp
        assert restored.ac == original.ac
        assert restored.inventory == original.inventory
        assert restored.hooks == original.hooks
        assert restored is not original

    def test_save_with_custom_name(self, tmp_path: Path) -> None:
        """Saving with an explicit custom name must use that name for the file."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="custom_save")
        assert store.character_exists("custom_save")
        assert not store.character_exists("Glimli")

    def test_save_with_none_name_uses_character_name(self, tmp_path: Path) -> None:
        """Saving with name=None must use the character's own .name field."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        store.save(char)
        assert store.character_exists("Glimli")

    def test_load_after_multiple_saves(self, tmp_path: Path) -> None:
        """Saving the same character under different names — both must load."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
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
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="list_me")
        entries = store.list_characters()
        assert len(entries) == 1
        meta = entries[0]
        assert "timestamp" in meta
        assert meta["class"] == "Fighter"
        assert meta["level"] == 1

    def test_list_multiple_saves(self, tmp_path: Path) -> None:
        """Multiple saves must all appear in the listing."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="char_a")
        store.save(char, name="char_b")
        store.save(char, name="char_c")
        assert len(store.list_characters()) == 3

    def test_delete_removes_file_from_disk(self, tmp_path: Path) -> None:
        """Deleting a character must remove its JSON file."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="delete_me")
        file_path = store.characters_dir / "delete_me.json"
        assert file_path.is_file()
        store.delete("delete_me")
        assert not file_path.exists()

    def test_delete_removes_from_index(self, tmp_path: Path) -> None:
        """Deleting a character must remove it from the index."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
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
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="check_me")
        assert store.character_exists("check_me") is True

    def test_save_exists_returns_false_when_not_saved(self, tmp_path: Path) -> None:
        """character_exists must return False for a non-existent character."""
        store = CharacterStorage(tmp_path)
        assert store.character_exists("phantom") is False

    def test_loading_nonexistent_file_raises_file_not_found(self, tmp_path: Path) -> None:
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
        char1 = Character.create_default("OldName", "Fighter")
        char2 = Character.create_default("NewName", "Rogue")
        store.save(char1, name="overwrite")
        store.save(char2, name="overwrite")
        loaded = store.load("overwrite")
        assert loaded.name == "NewName"
        assert loaded.character_class == "Rogue"

    def test_overwrite_updates_timestamp(self, tmp_path: Path) -> None:
        """Overwriting a save must produce a newer timestamp."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Test", "Fighter")
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
    def test_save_with_path_traversal_name_raises(self, tmp_path: Path, bad_name: str, match_pattern: str) -> None:
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
    def test_other_operations_validate_name(self, tmp_path: Path, operation: str, bad_name: str) -> None:
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
        char = Character.create_default("Glimli", "Fighter")
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
        char = Character.create_default("Glimli", "Fighter")
        shutil.rmtree(store.characters_dir)
        assert not store.characters_dir.exists()
        store.save(char, name="after_deletion")
        assert store.characters_dir.is_dir()
        assert store.character_exists("after_deletion")

    def test_delete_with_manually_deleted_file_cleans_index(self, tmp_path: Path) -> None:
        """If JSON file is deleted manually, delete() must still clean index."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
        store.save(char, name="manually_gone")
        assert len(store.list_characters()) == 1
        save_path = store.characters_dir / "manually_gone.json"
        save_path.unlink()
        store.delete("manually_gone")
        assert len(store.list_characters()) == 0

    def test_tmp_file_cleaned_up_on_save_failure(self, tmp_path: Path) -> None:
        """If saving fails, temp .tmp file must not linger."""
        store = CharacterStorage(tmp_path)
        char = Character.create_default("Glimli", "Fighter")
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
        char = Character.create_default("Glimli", "Fighter")
        original_rename = os.rename
        tmp_paths: list[Path] = []
        def tracking_rename(src: str, dst: str) -> None:
            src_path = Path(src)
            if src_path.suffix == ".tmp":
                assert src_path.exists(), f"Temp file {src_path} should exist before rename"
                tmp_paths.append(src_path)
            original_rename(src, dst)
        try:
            os.rename = tracking_rename  # type: ignore[assignment]
            store.save(char, name="atomic_test")
            assert len(tmp_paths) >= 1, "No .tmp file was used during save"
        finally:
            os.rename = original_rename
        assert (store.characters_dir / "atomic_test.json").exists()
        assert not (store.characters_dir / "atomic_test.json.tmp").exists()
