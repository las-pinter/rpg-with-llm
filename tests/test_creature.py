"""Tests for the Creature model — Task 1.3 of the Character Sheet Overhaul."""

from __future__ import annotations

import json

import pytest

from app.world.creature import Creature, _validate_creature

# ---------------------------------------------------------------------------
# Sample creature data
# ---------------------------------------------------------------------------

SAMPLE_GOBLIN_DATA: dict[str, object] = {
    "id": "goblin_test_001",
    "name": "Goblin",
    "ac": 15,
    "hp": 7,
    "max_hp": 7,
    "abilities": {
        "str": 8,
        "dex": 14,
        "con": 10,
        "int": 10,
        "wis": 8,
        "cha": 8,
    },
    "skills": ["stealth"],
    "resistances": [],
    "vulnerabilities": [],
    "immunities": [],
    "actions": [
        {
            "name": "Scimitar",
            "description": "Melee Weapon Attack",
            "damage": "1d6+2",
            "attack_bonus": 4,
        },
    ],
    "xp_value": 50,
    "cr": 0.25,
    "size": "Small",
    "movement": {"walk": 30},
    "saving_throws": {
        "str": False,
        "dex": False,
        "con": False,
        "int": False,
        "wis": False,
        "cha": False,
    },
    "senses": ["darkvision 60 ft"],
    "languages": ["Common", "Goblin"],
    "special_abilities": [
        {
            "name": "Nimble Escape",
            "description": "Disengage or Hide as a bonus action.",
        },
    ],
}

SAMPLE_DRAGON_DATA: dict[str, object] = {
    "id": "dragon_test_001",
    "name": "Young Red Dragon",
    "ac": 18,
    "hp": 178,
    "max_hp": 178,
    "abilities": {
        "str": 18,
        "dex": 10,
        "con": 18,
        "int": 14,
        "wis": 11,
        "cha": 18,
    },
    "skills": ["perception", "stealth"],
    "resistances": [],
    "vulnerabilities": [],
    "immunities": ["fire"],
    "actions": [
        {
            "name": "Bite",
            "description": "Melee Weapon Attack",
            "damage": "2d10+6",
            "attack_bonus": 10,
        },
        {
            "name": "Fire Breath",
            "description": "The dragon exhales fire in a 30-foot cone.",
            "damage": "16d6",
            "attack_bonus": 0,
        },
    ],
    "xp_value": 3900,
    "cr": 10,
    "size": "Large",
    "movement": {"walk": 40, "fly": 80, "climb": 40},
    "saving_throws": {
        "str": True,
        "dex": True,
        "con": True,
        "int": False,
        "wis": False,
        "cha": False,
    },
    "senses": ["darkvision 60 ft", "passive Perception 14"],
    "languages": ["Common", "Draconic"],
    "special_abilities": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_creature(**overrides: object) -> Creature:
    """Build a Creature with sensible defaults for quick test setup."""
    defaults: dict[str, object] = {
        "name": "Test Creature",
        "ac": 12,
        "hp": 10,
        "max_hp": 10,
        "abilities": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
    }
    defaults.update(overrides)
    return Creature(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Creature creation
# ---------------------------------------------------------------------------


class TestCreatureCreation:
    """Creature dataclass must store all fields correctly."""

    def test_all_fields_stored(self) -> None:
        creature = Creature(
            id="test-id",
            name="Goblin Scout",
            ac=14,
            hp=9,
            max_hp=9,
            abilities={"str": 10, "dex": 14, "con": 12, "int": 8, "wis": 10, "cha": 8},
            skills=["stealth", "perception"],
            resistances=[],
            vulnerabilities=[],
            immunities=[],
            actions=[
                {
                    "name": "Dagger",
                    "description": "Melee Weapon Attack",
                    "damage": "1d4+2",
                    "attack_bonus": 4,
                },
            ],
            xp_value=25,
            cr=0.125,
            size="Small",
            movement={"walk": 30},
            saving_throws={"dex": True, "str": False},
            senses=["darkvision 60 ft"],
            languages=["Common", "Goblin"],
            special_abilities=[
                {
                    "name": "Nimble Escape",
                    "description": "Hide/disengage as bonus action.",
                },
            ],
        )
        assert creature.id == "test-id"
        assert creature.name == "Goblin Scout"
        assert creature.ac == 14
        assert creature.hp == 9
        assert creature.max_hp == 9
        assert creature.abilities == {
            "str": 10,
            "dex": 14,
            "con": 12,
            "int": 8,
            "wis": 10,
            "cha": 8,
        }
        assert creature.skills == ["stealth", "perception"]
        assert creature.resistances == []
        assert creature.vulnerabilities == []
        assert creature.immunities == []
        assert len(creature.actions) == 1
        assert creature.actions[0]["name"] == "Dagger"
        assert creature.xp_value == 25
        assert creature.cr == 0.125
        assert creature.size == "Small"
        assert creature.movement == {"walk": 30}
        assert creature.saving_throws == {"dex": True, "str": False}
        assert creature.senses == ["darkvision 60 ft"]
        assert creature.languages == ["Common", "Goblin"]
        assert creature.special_abilities[0]["name"] == "Nimble Escape"

    def test_id_is_uuid_string(self) -> None:
        creature = _make_creature()
        assert isinstance(creature.id, str)
        assert len(creature.id) == 36
        assert creature.id.count("-") == 4

    def test_unique_ids(self) -> None:
        c1 = _make_creature()
        c2 = _make_creature()
        assert c1.id != c2.id

    def test_create_from_sample_data(self) -> None:
        creature = Creature(**SAMPLE_GOBLIN_DATA)  # type: ignore[arg-type]
        assert creature.name == "Goblin"
        assert creature.ac == 15
        assert creature.hp == 7
        assert creature.cr == 0.25
        assert creature.size == "Small"

    def test_create_high_cr_creature(self) -> None:
        creature = Creature(**SAMPLE_DRAGON_DATA)  # type: ignore[arg-type]
        assert creature.name == "Young Red Dragon"
        assert creature.cr == 10.0
        assert creature.hp == 178
        assert creature.xp_value == 3900

    def test_cr_as_float_accepts_fractional(self) -> None:
        """CR can be fractional like 0.125, 0.25, 0.5."""
        creature = _make_creature(cr=0.5)
        assert creature.cr == 0.5

    def test_cr_as_int(self) -> None:
        creature = _make_creature(cr=5)
        assert creature.cr == 5.0


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestCreatureDefaults:
    """Optional fields must fall back to sensible defaults."""

    def test_name_defaults_to_empty_string(self) -> None:
        creature = Creature()
        assert creature.name == ""

    def test_ac_defaults_to_10(self) -> None:
        creature = Creature()
        assert creature.ac == 10

    def test_hp_defaults_to_1(self) -> None:
        creature = Creature()
        assert creature.hp == 1

    def test_max_hp_defaults_to_1(self) -> None:
        creature = Creature()
        assert creature.max_hp == 1

    def test_abilities_default_to_all_10(self) -> None:
        creature = Creature()
        expected = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        assert creature.abilities == expected

    def test_skills_default_to_empty_list(self) -> None:
        creature = Creature()
        assert creature.skills == []

    def test_resistances_default_to_empty_list(self) -> None:
        creature = Creature()
        assert creature.resistances == []

    def test_actions_default_to_empty_list(self) -> None:
        creature = Creature()
        assert creature.actions == []

    def test_xp_value_defaults_to_zero(self) -> None:
        creature = Creature()
        assert creature.xp_value == 0

    def test_cr_defaults_to_zero(self) -> None:
        creature = Creature()
        assert creature.cr == 0.0

    def test_size_defaults_to_medium(self) -> None:
        creature = Creature()
        assert creature.size == "Medium"

    def test_movement_defaults_to_walk_30(self) -> None:
        creature = Creature()
        assert creature.movement == {"walk": 30}

    def test_senses_default_to_empty_list(self) -> None:
        creature = Creature()
        assert creature.senses == []

    def test_languages_default_to_empty_list(self) -> None:
        creature = Creature()
        assert creature.languages == []

    def test_special_abilities_default_to_empty_list(self) -> None:
        creature = Creature()
        assert creature.special_abilities == []

    def test_saving_throws_default_to_empty_dict(self) -> None:
        creature = Creature()
        assert creature.saving_throws == {}

    def test_default_abilities_are_independent(self) -> None:
        """Each Creature must get its own abilities dict, not a shared reference."""
        c1 = _make_creature()
        c2 = _make_creature()
        c1.abilities["str"] = 18
        assert c2.abilities["str"] == 10

    def test_default_movement_is_independent(self) -> None:
        c1 = _make_creature()
        c2 = _make_creature()
        c1.movement["fly"] = 60
        assert "fly" not in c2.movement


# ---------------------------------------------------------------------------
# get_ability_modifier
# ---------------------------------------------------------------------------


class TestGetAbilityModifier:
    """get_ability_modifier must compute the correct D&D 5e modifier."""

    def test_score_10_returns_0(self) -> None:
        creature = _make_creature(
            abilities={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("str") == 0
        assert creature.get_ability_modifier("dex") == 0

    def test_score_14_returns_plus_2(self) -> None:
        creature = _make_creature(
            abilities={"str": 14, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("str") == 2

    def test_score_8_returns_minus_1(self) -> None:
        creature = _make_creature(
            abilities={"str": 10, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("dex") == -1

    def test_score_3_returns_minus_4(self) -> None:
        """Score 3 → (3-10)//2 = -4 (floor division matches D&D round-down)."""
        creature = _make_creature(
            abilities={"str": 3, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("str") == -4

    def test_score_18_returns_plus_4(self) -> None:
        creature = _make_creature(
            abilities={"str": 18, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("str") == 4

    def test_score_20_returns_plus_5(self) -> None:
        creature = _make_creature(
            abilities={"str": 20, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("str") == 5

    def test_score_1_returns_minus_5(self) -> None:
        """Score 1 → (1-10)//2 = -9//2 = -5 (floor division)."""
        creature = _make_creature(
            abilities={"str": 1, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("str") == -5

    def test_score_30_returns_plus_10(self) -> None:
        creature = _make_creature(
            abilities={"str": 30, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert creature.get_ability_modifier("str") == 10

    def test_different_abilities_independent(self) -> None:
        creature = _make_creature(
            abilities={
                "str": 8,
                "dex": 12,
                "con": 14,
                "int": 10,
                "wis": 16,
                "cha": 18,
            }
        )
        assert creature.get_ability_modifier("str") == -1
        assert creature.get_ability_modifier("dex") == 1
        assert creature.get_ability_modifier("con") == 2
        assert creature.get_ability_modifier("int") == 0
        assert creature.get_ability_modifier("wis") == 3
        assert creature.get_ability_modifier("cha") == 4

    def test_unknown_ability_uses_default_10(self) -> None:
        """If the ability key doesn't exist, treat score as 10 → modifier 0."""
        creature = _make_creature(abilities={"str": 14})
        assert creature.get_ability_modifier("unknown") == 0

    def test_uses_creature_own_abilities_not_global(self) -> None:
        c1 = _make_creature(
            abilities={"str": 18, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        c2 = _make_creature(
            abilities={"str": 8, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        )
        assert c1.get_ability_modifier("str") == 4
        assert c2.get_ability_modifier("str") == -1


# ---------------------------------------------------------------------------
# to_dict / from_dict — serialisation round-trip
# ---------------------------------------------------------------------------


class TestCreatureSerialization:
    """Creature.to_dict() and .from_dict() must round-trip correctly."""

    def test_to_dict_returns_all_fields(self) -> None:
        creature = _make_creature(
            name="Orc Warrior",
            ac=13,
            hp=15,
            max_hp=15,
            abilities={"str": 16, "dex": 11, "con": 14, "int": 8, "wis": 10, "cha": 9},
            skills=["intimidation"],
            actions=[
                {
                    "name": "Greataxe",
                    "description": "Melee Attack",
                    "damage": "1d12+3",
                    "attack_bonus": 5,
                }
            ],
            xp_value=100,
            cr=0.5,
            size="Medium",
            movement={"walk": 30},
        )
        data = creature.to_dict()
        assert isinstance(data, dict)
        assert data["name"] == "Orc Warrior"
        assert data["ac"] == 13
        assert data["hp"] == 15
        assert data["cr"] == 0.5
        assert data["abilities"]["str"] == 16
        assert data["actions"][0]["name"] == "Greataxe"
        assert data["xp_value"] == 100
        assert data["size"] == "Medium"

    def test_from_dict_reconstructs_creature(self) -> None:
        creature = Creature.from_dict(SAMPLE_GOBLIN_DATA)  # type: ignore[arg-type]
        assert creature.id == "goblin_test_001"
        assert creature.name == "Goblin"
        assert creature.ac == 15
        assert creature.hp == 7
        assert creature.abilities["dex"] == 14
        assert creature.skills == ["stealth"]
        assert creature.cr == 0.25
        assert creature.size == "Small"
        assert creature.movement == {"walk": 30}
        assert creature.senses == ["darkvision 60 ft"]
        assert creature.languages == ["Common", "Goblin"]
        assert creature.special_abilities[0]["name"] == "Nimble Escape"

    def test_round_trip_preserves_all_fields(self) -> None:
        original = _make_creature(
            name="Hobgoblin Captain",
            ac=17,
            hp=39,
            max_hp=39,
            abilities={
                "str": 15,
                "dex": 14,
                "con": 14,
                "int": 12,
                "wis": 10,
                "cha": 13,
            },
            skills=["perception", "intimidation"],
            resistances=[],
            vulnerabilities=[],
            immunities=[],
            actions=[
                {
                    "name": "Longsword",
                    "description": "Melee Attack",
                    "damage": "1d8+2",
                    "attack_bonus": 4,
                },
                {
                    "name": "Javelin",
                    "description": "Ranged Attack",
                    "damage": "1d6+2",
                    "attack_bonus": 4,
                },
            ],
            xp_value=200,
            cr=1,
            size="Medium",
            movement={"walk": 30},
            saving_throws={"str": True, "dex": True},
            senses=["darkvision 60 ft"],
            languages=["Common", "Goblin"],
            special_abilities=[
                {
                    "name": "Martial Advantage",
                    "description": "Extra damage when ally is nearby.",
                },
            ],
        )
        restored = Creature.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.ac == original.ac
        assert restored.hp == original.hp
        assert restored.max_hp == original.max_hp
        assert restored.abilities == original.abilities
        assert restored.skills == original.skills
        assert restored.resistances == original.resistances
        assert restored.vulnerabilities == original.vulnerabilities
        assert restored.immunities == original.immunities
        assert restored.actions == original.actions
        assert restored.xp_value == original.xp_value
        assert restored.cr == original.cr
        assert restored.size == original.size
        assert restored.movement == original.movement
        assert restored.saving_throws == original.saving_throws
        assert restored.senses == original.senses
        assert restored.languages == original.languages
        assert restored.special_abilities == original.special_abilities

    def test_round_trip_default_creature(self) -> None:
        """Even a default-constructed Creature must survive serialization."""
        original = Creature()
        restored = Creature.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == ""
        assert restored.ac == 10
        assert restored.abilities == {
            "str": 10,
            "dex": 10,
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
        }

    def test_round_trip_goblin_sample(self) -> None:
        original = Creature(**SAMPLE_GOBLIN_DATA)  # type: ignore[arg-type]
        restored = Creature.from_dict(original.to_dict())
        assert restored.name == "Goblin"
        assert restored.ac == 15
        assert restored.hp == 7
        assert restored.cr == 0.25
        assert restored.skills == ["stealth"]

    def test_round_trip_dragon_sample(self) -> None:
        original = Creature(**SAMPLE_DRAGON_DATA)  # type: ignore[arg-type]
        restored = Creature.from_dict(original.to_dict())
        assert restored.name == "Young Red Dragon"
        assert restored.hp == 178
        assert restored.cr == 10
        assert restored.movement["fly"] == 80

    def test_to_dict_is_json_serializable(self) -> None:
        creature = Creature(**SAMPLE_GOBLIN_DATA)  # type: ignore[arg-type]
        dumped = json.dumps(creature.to_dict())
        loaded = json.loads(dumped)
        restored = Creature.from_dict(loaded)
        assert restored.name == "Goblin"
        assert restored.ac == 15
        assert restored.cr == 0.25

    def test_from_dict_extra_fields_forward_compat(self) -> None:
        """Unknown keys must be silently ignored."""
        data = _make_creature().to_dict()
        data["unknown_field"] = "ignored"
        data["version"] = 2
        creature = Creature.from_dict(data)
        assert creature.name == "Test Creature"
        assert creature.ac == 12

    def test_from_dict_missing_fields_use_defaults(self) -> None:
        """Omitting optional fields must result in their default values."""
        data: dict[str, object] = {"name": "Minimal", "ac": 15, "hp": 10, "max_hp": 10}
        creature = Creature.from_dict(data)
        assert creature.name == "Minimal"
        assert creature.ac == 15
        assert creature.hp == 10
        assert creature.max_hp == 10
        # Defaults for omitted fields
        assert creature.abilities == {
            "str": 10,
            "dex": 10,
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
        }
        assert creature.skills == []
        assert creature.cr == 0.0
        assert creature.size == "Medium"

    def test_from_dict_with_partial_abilities(self) -> None:
        """Partial abilities dict is allowed (uses defaults for missing keys only
        if the entire abilities key is missing — otherwise the partial dict is used
        as-is)."""
        creature = Creature.from_dict({"abilities": {"str": 18}})
        assert creature.abilities == {"str": 18}  # partial, no default merge


# ---------------------------------------------------------------------------
# _validate_creature
# ---------------------------------------------------------------------------


class TestValidateCreature:
    """_validate_creature must return errors for invalid data."""

    def test_valid_data_returns_empty_list(self) -> None:
        errors = _validate_creature(dict(SAMPLE_GOBLIN_DATA))  # type: ignore[arg-type]
        assert errors == []

    def test_valid_dragon_data_returns_empty_list(self) -> None:
        errors = _validate_creature(dict(SAMPLE_DRAGON_DATA))  # type: ignore[arg-type]
        assert errors == []

    def test_cr_below_zero(self) -> None:
        errors = _validate_creature({"cr": -1})
        assert any("CR" in e and "0" in e for e in errors)

    def test_cr_above_30(self) -> None:
        errors = _validate_creature({"cr": 31})
        assert any("CR" in e and "30" in e for e in errors)

    def test_cr_at_boundaries(self) -> None:
        valid: dict[str, object] = {
            "cr": 0,
            "hp": 1,
            "max_hp": 1,
            "abilities": {
                "str": 10,
                "dex": 10,
                "con": 10,
                "int": 10,
                "wis": 10,
                "cha": 10,
            },
            "ac": 10,
        }
        assert _validate_creature({**valid, "cr": 0}) == []
        assert _validate_creature({**valid, "cr": 30}) == []

    def test_cr_fractional_valid(self) -> None:
        valid: dict[str, object] = {
            "hp": 1,
            "max_hp": 1,
            "abilities": {
                "str": 10,
                "dex": 10,
                "con": 10,
                "int": 10,
                "wis": 10,
                "cha": 10,
            },
            "ac": 10,
        }
        assert _validate_creature({**valid, "cr": 0.125}) == []
        assert _validate_creature({**valid, "cr": 0.25}) == []

    def test_cr_not_a_number(self) -> None:
        errors = _validate_creature({"cr": "high"})
        assert any("CR" in e for e in errors)

    def test_negative_hp(self) -> None:
        errors = _validate_creature({"hp": -5, "max_hp": 10})
        assert any("HP" in e and "negative" in e for e in errors)

    def test_hp_zero_is_valid(self) -> None:
        """HP of 0 is allowed (creature is unconscious/dead)."""
        errors = _validate_creature({"hp": 0, "max_hp": 10})
        assert all("HP" not in e or "negative" not in e for e in errors)

    def test_max_hp_zero(self) -> None:
        errors = _validate_creature({"hp": 0, "max_hp": 0})
        assert any("max_hp" in e and "positive" in e for e in errors)

    def test_max_hp_negative(self) -> None:
        errors = _validate_creature({"hp": 0, "max_hp": -1})
        assert any("max_hp" in e and "positive" in e for e in errors)

    def test_missing_abilities(self) -> None:
        errors = _validate_creature({"abilities": {"str": 10}})
        assert any("Missing" in e for e in errors)

    def test_missing_all_abilities(self) -> None:
        errors = _validate_creature({})
        # CR, HP, max_hp, AC, and abilities errors
        missing_errors = [e for e in errors if "Missing" in e]
        assert len(missing_errors) >= 1

    def test_ability_score_too_low(self) -> None:
        abilities = {"str": 2, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        errors = _validate_creature({"abilities": abilities})
        assert any("str" in e and "3" in e for e in errors)

    def test_ability_score_too_high(self) -> None:
        abilities = {"str": 19, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
        errors = _validate_creature({"abilities": abilities})
        assert any("str" in e and "18" in e for e in errors)

    def test_ability_scores_at_boundaries(self) -> None:
        """Scores of 3 and 18 are valid."""
        abilities = {"str": 3, "dex": 18, "con": 10, "int": 10, "wis": 10, "cha": 10}
        errors = _validate_creature({"abilities": abilities})
        assert all("str" not in e for e in errors)
        assert all("dex" not in e for e in errors)

    def test_ability_score_not_an_int(self) -> None:
        abilities = {
            "str": "high",
            "dex": 10,
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
        }
        errors = _validate_creature({"abilities": abilities})
        assert any("str" in e for e in errors)

    def test_abilities_not_a_dict(self) -> None:
        errors = _validate_creature({"abilities": "not_a_dict"})
        assert any("dict" in e for e in errors)

    def test_negative_ac(self) -> None:
        errors = _validate_creature({"ac": -1})
        assert any("AC" in e and "negative" in e for e in errors)

    def test_ac_zero_is_valid(self) -> None:
        """AC of 0 is technically allowed (though unusual)."""
        errors = _validate_creature({"ac": 0})
        assert all("AC" not in e for e in errors)

    def test_multiple_errors_returned(self) -> None:
        """Multiple validation issues must all be reported."""
        errors = _validate_creature(
            {
                "cr": 35,
                "hp": -1,
                "max_hp": 0,
                "abilities": {
                    "str": 1,
                    "dex": 10,
                    "con": 10,
                    "int": 10,
                    "wis": 10,
                    "cha": 10,
                },
                "ac": -1,
            }
        )
        assert len(errors) >= 4  # CR, HP, max_hp, ability, AC

    def test_valid_creature_with_no_optional_fields(self) -> None:
        """Minimal valid creature data must pass."""
        data: dict[str, object] = {
            "cr": 0,
            "hp": 1,
            "max_hp": 1,
            "abilities": {
                "str": 10,
                "dex": 10,
                "con": 10,
                "int": 10,
                "wis": 10,
                "cha": 10,
            },
            "ac": 10,
        }
        errors = _validate_creature(data)
        assert errors == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestCreatureEdgeCases:
    """Boundary and edge-case values must be handled correctly."""

    def test_zero_hp_creature(self) -> None:
        creature = _make_creature(hp=0, max_hp=10)
        assert creature.hp == 0

    def test_high_cr_creature(self) -> None:
        creature = _make_creature(cr=30)
        assert creature.cr == 30

    def test_multiple_movement_types(self) -> None:
        creature = _make_creature(
            movement={"walk": 30, "swim": 20, "climb": 30, "fly": 60}
        )
        assert creature.movement["swim"] == 20
        assert creature.movement["fly"] == 60

    def test_large_number_of_actions(self) -> None:
        actions = [
            {
                "name": f"Attack {i}",
                "description": f"Attack number {i}",
                "damage": "1d6",
                "attack_bonus": 5,
            }
            for i in range(20)
        ]
        creature = _make_creature(actions=actions)
        assert len(creature.actions) == 20

    def test_empty_special_abilities(self) -> None:
        creature = _make_creature(special_abilities=[])
        assert creature.special_abilities == []

    def test_various_sizes(self) -> None:
        for size in ("Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"):
            creature = _make_creature(size=size)
            assert creature.size == size

    def test_no_skills(self) -> None:
        creature = _make_creature(skills=[])
        assert creature.skills == []

    def test_multiple_languages(self) -> None:
        creature = _make_creature(
            languages=["Common", "Elvish", "Dwarvish", "Draconic"]
        )
        assert len(creature.languages) == 4

    def test_saving_throws_with_proficiencies(self) -> None:
        creature = _make_creature(saving_throws={"str": True, "con": True})
        assert creature.saving_throws["str"] is True
        assert creature.saving_throws["con"] is True
        assert "dex" not in creature.saving_throws

    def test_to_dict_does_not_mutate_original(self) -> None:
        creature = _make_creature(name="Test")
        data = creature.to_dict()
        data["name"] = "Mutated"
        assert creature.name == "Test"

    def test_from_dict_does_not_mutate_input(self) -> None:
        data = dict(SAMPLE_GOBLIN_DATA)
        original_name = data["name"]
        Creature.from_dict(data)  # type: ignore[arg-type]
        assert data["name"] == original_name


# ---------------------------------------------------------------------------
# Bestiary JSON loading
# ---------------------------------------------------------------------------


class TestBestiaryLoading:
    """Bestiary JSON must load and produce valid Creature instances."""

    BESTIARY_PATH = "data/tables/bestiary.json"

    def test_bestiary_json_loads(self) -> None:
        """The bestiary file must be valid JSON and contain an array."""
        import os

        if not os.path.exists(self.BESTIARY_PATH):
            pytest.skip(f"Bestiary file not found at {self.BESTIARY_PATH}")

        with open(self.BESTIARY_PATH) as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) > 0

    def test_bestiary_creatures_are_valid(self) -> None:
        """Every creature in the bestiary must pass _validate_creature."""
        import os

        if not os.path.exists(self.BESTIARY_PATH):
            pytest.skip(f"Bestiary file not found at {self.BESTIARY_PATH}")

        with open(self.BESTIARY_PATH) as f:
            raw_list = json.load(f)

        for i, entry in enumerate(raw_list):
            errors = _validate_creature(entry)
            assert not errors, f"Entry {i} ({entry.get('name', '?')}) failed: {errors}"

    def test_bestiary_creatures_load_as_creature_instances(self) -> None:
        """Every entry in the bestiary must deserialise to a Creature instance."""
        import os

        if not os.path.exists(self.BESTIARY_PATH):
            pytest.skip(f"Bestiary file not found at {self.BESTIARY_PATH}")

        with open(self.BESTIARY_PATH) as f:
            raw_list = json.load(f)

        for i, entry in enumerate(raw_list):
            creature = Creature.from_dict(entry)
            assert isinstance(creature, Creature)
            assert creature.name != "", f"Entry {i} has empty name"
            assert creature.ac >= 0, f"Entry {i} ({creature.name}) has negative AC"
            assert creature.hp >= 0, f"Entry {i} ({creature.name}) has negative HP"

    def test_bestiary_round_trip(self) -> None:
        """Each bestiary entry must survive to_dict/from_dict round-trip."""
        import os

        if not os.path.exists(self.BESTIARY_PATH):
            pytest.skip(f"Bestiary file not found at {self.BESTIARY_PATH}")

        with open(self.BESTIARY_PATH) as f:
            raw_list = json.load(f)

        for entry in raw_list:
            original = Creature.from_dict(entry)
            restored = Creature.from_dict(original.to_dict())
            assert restored.name == original.name
            assert restored.ac == original.ac
            assert restored.hp == original.hp
            assert restored.abilities == original.abilities
            assert restored.cr == original.cr

    def test_bestiary_contains_goblin(self) -> None:
        """The bestiary must contain a Goblin entry with correct stats."""
        import os

        if not os.path.exists(self.BESTIARY_PATH):
            pytest.skip(f"Bestiary file not found at {self.BESTIARY_PATH}")

        with open(self.BESTIARY_PATH) as f:
            raw_list = json.load(f)

        goblins = [e for e in raw_list if e.get("name") == "Goblin"]
        assert len(goblins) >= 1
        goblin = goblins[0]
        assert goblin["cr"] == 0.25
        assert goblin["size"] == "Small"
        assert goblin["ac"] == 15

    def test_bestiary_contains_all_five_creatures(self) -> None:
        """The bestiary must contain all 5 expected creature types."""
        import os

        if not os.path.exists(self.BESTIARY_PATH):
            pytest.skip(f"Bestiary file not found at {self.BESTIARY_PATH}")

        with open(self.BESTIARY_PATH) as f:
            raw_list = json.load(f)

        names = {e["name"] for e in raw_list}
        expected = {"Goblin", "Skeleton", "Wolf", "Giant Rat", "Bandit"}
        missing = expected - names
        assert not missing, f"Missing creatures in bestiary: {missing}"
