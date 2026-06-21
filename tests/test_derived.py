"""Comprehensive tests for the Derivation Pipeline — Phase 2, Task 2.1."""

from __future__ import annotations

import pytest

from app.character.derived import prepare_base_data, prepare_embedded_data
from app.character.model import STANDARD_ABILITIES, CharacterRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    abilities: dict[str, int] | None = None,
    level: int = 1,
    character_class: str = "Fighter",
    **overrides: object,
) -> CharacterRecord:
    """Build a minimal CharacterRecord for derived-data tests."""
    if abilities is None:
        abilities = {a: 10 for a in STANDARD_ABILITIES}
    defaults: dict[str, object] = {
        "name": "Test",
        "character_class": character_class,
        "level": level,
        "abilities": abilities,
    }
    defaults.update(overrides)
    return CharacterRecord(**defaults)  # type: ignore[arg-type]


def _make_record_unvalidated(
    abilities: dict[str, int] | None = None,
    level: int = 1,
    character_class: str = "Fighter",
) -> CharacterRecord:
    """Build a CharacterRecord bypassing validation for edge-case tests.

    ``CharacterRecord.__post_init__`` enforces ability scores in 3-18,
    valid classes, and level >= 1.  Use this helper when the test needs
    values outside those ranges to verify that *prepare_base_data* itself
    handles them gracefully.
    """
    if abilities is None:
        abilities = {a: 10 for a in STANDARD_ABILITIES}
    record = object.__new__(CharacterRecord)
    record.abilities = dict(abilities)
    record.level = level
    record.character_class = character_class
    # Fill remaining fields with defaults
    record.name = "Test"
    record.xp = 0
    record.skills = []
    record.gold = 0
    record.inventory = []
    record.equipped_items = []
    record.resources = {}
    record.appearance = ""
    record.personality = ""
    record.backstory = ""
    record.hooks = []
    return record


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPrepareBaseData:
    """``prepare_base_data`` correctness."""

    # ------------------------------------------------------------------
    # Class hit dice
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("class_name", "expected_hit_dice"),
        [
            ("Fighter", "1d10"),
            ("Rogue", "1d8"),
            ("Mage", "1d6"),
            ("Cleric", "1d8"),
        ],
    )
    def test_hit_dice_by_class(self, class_name: str, expected_hit_dice: str) -> None:
        """Each class must produce the correct hit dice string."""
        data = prepare_base_data(_make_record(character_class=class_name))
        assert data["hit_dice"] == expected_hit_dice

    def test_hit_dice_unknown_class_defaults_to_1d8(self) -> None:
        """An unrecognised character_class must fall back to '1d8'."""
        data = prepare_base_data(_make_record_unvalidated(character_class="Barbarian"))
        assert data["hit_dice"] == "1d8"

    # ------------------------------------------------------------------
    # Speed
    # ------------------------------------------------------------------

    def test_speed_is_always_30(self) -> None:
        """Base speed must be 30 for all classes."""
        for cls_name in ("Fighter", "Rogue", "Mage", "Cleric"):
            data = prepare_base_data(_make_record(character_class=cls_name))
            assert data["speed"] == 30

    # ------------------------------------------------------------------
    # Proficiency bonus at level boundaries
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("level", "expected_prof_bonus"),
        [
            (1, 2),
            (2, 2),
            (3, 2),
            (4, 2),
            (5, 3),
            (6, 3),
            (7, 3),
            (8, 3),
            (9, 4),
            (10, 4),
            (11, 4),
            (12, 4),
            (13, 5),
            (14, 5),
            (15, 5),
            (16, 5),
            (17, 6),
            (18, 6),
            (19, 6),
            (20, 6),
        ],
    )
    def test_proficiency_bonus_at_level(
        self, level: int, expected_prof_bonus: int
    ) -> None:
        """Proficiency bonus must follow the ceil(level/4)+1 formula."""
        data = prepare_base_data(_make_record(level=level))
        assert data["proficiency_bonus"] == expected_prof_bonus

    def test_proficiency_bonus_at_zero_level(self) -> None:
        """Level 0 must still compute cleanly (ceil(0/4)+1 = 1)."""
        data = prepare_base_data(_make_record_unvalidated(level=0))
        assert data["proficiency_bonus"] == 1

    # ------------------------------------------------------------------
    # Ability modifiers
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        ("score", "expected_modifier"),
        [
            (1, -5),
            (2, -4),
            (3, -4),
            (4, -3),
            (5, -3),
            (6, -2),
            (7, -2),
            (8, -1),
            (9, -1),
            (10, 0),
            (11, 0),
            (12, 1),
            (13, 1),
            (14, 2),
            (15, 2),
            (16, 3),
            (17, 3),
            (18, 4),
            (19, 4),
            (20, 5),
            (30, 10),
        ],
    )
    def test_ability_modifier_formula(self, score: int, expected_modifier: int) -> None:
        """Each ability modifier must be (score - 10) // 2."""
        abilities = {a: 10 for a in STANDARD_ABILITIES}
        abilities["STR"] = score
        data = prepare_base_data(_make_record_unvalidated(abilities=abilities))
        assert data["ability_modifiers"]["STR"] == expected_modifier

    def test_all_six_ability_modifiers_present(self) -> None:
        """The ability_modifiers dict must contain all six abilities."""
        data = prepare_base_data(_make_record())
        assert set(data["ability_modifiers"].keys()) == set(STANDARD_ABILITIES)

    def test_ability_modifiers_match_get_ability_modifier(self) -> None:
        """Must produce same results as app.rules.checks.get_ability_modifier."""
        from app.rules.checks import get_ability_modifier

        scores = {"STR": 15, "DEX": 14, "CON": 13, "INT": 12, "WIS": 10, "CHA": 8}
        data = prepare_base_data(_make_record(abilities=scores))
        for abil in STANDARD_ABILITIES:
            expected = get_ability_modifier(scores.get(abil, 10))
            assert data["ability_modifiers"][abil] == expected, (
                f"Mismatch for {abil}: "
                f"prepare_base_data={data['ability_modifiers'][abil]}, "
                f"get_ability_modifier={expected}"
            )

    # ------------------------------------------------------------------
    # Fighter at level 1 (smoke test)
    # ------------------------------------------------------------------

    def test_fighter_level_1(self) -> None:
        """A level-1 Fighter must produce expected derived values."""
        abilities = {
            "STR": 15,
            "DEX": 13,
            "CON": 14,
            "WIS": 12,
            "INT": 10,
            "CHA": 8,
        }
        data = prepare_base_data(
            _make_record(abilities=abilities, level=1, character_class="Fighter")
        )

        # Ability modifiers
        assert data["ability_modifiers"]["STR"] == 2  # (15-10)//2
        assert data["ability_modifiers"]["DEX"] == 1  # (13-10)//2
        assert data["ability_modifiers"]["CON"] == 2  # (14-10)//2
        assert data["ability_modifiers"]["WIS"] == 1  # (12-10)//2
        assert data["ability_modifiers"]["INT"] == 0  # (10-10)//2
        assert data["ability_modifiers"]["CHA"] == -1  # (8-10)//2

        # Proficiency bonus: ceil(1/4)+1 = 1+1 = 2
        assert data["proficiency_bonus"] == 2

        # Hit dice
        assert data["hit_dice"] == "1d10"

        # Speed
        assert data["speed"] == 30

    # ------------------------------------------------------------------
    # Pure function test
    # ------------------------------------------------------------------

    def test_pure_function_same_input_same_output(self) -> None:
        """prepare_base_data must be deterministic (same record → same dict)."""
        abilities = {
            "STR": 15,
            "DEX": 13,
            "CON": 14,
            "WIS": 12,
            "INT": 10,
            "CHA": 8,
        }
        record = _make_record(abilities=abilities, level=5, character_class="Rogue")

        result1 = prepare_base_data(record)
        result2 = prepare_base_data(record)

        assert result1 == result2

    def test_pure_function_does_not_mutate_record(self) -> None:
        """prepare_base_data must not modify the input record."""
        abilities = {
            "STR": 15,
            "DEX": 13,
            "CON": 14,
            "WIS": 12,
            "INT": 10,
            "CHA": 8,
        }
        original_abilities = dict(abilities)
        record = _make_record(abilities=abilities, level=1, character_class="Fighter")

        prepare_base_data(record)

        assert record.abilities == original_abilities
        assert record.level == 1
        assert record.character_class == "Fighter"


class TestPrepareEmbeddedData:
    """Tests for prepare_embedded_data — skill/save/passive perception computation."""

    @pytest.mark.parametrize(
        "character_class,expected_save_profs",
        [
            ("Fighter", ["STR", "CON"]),
            ("Rogue", ["DEX", "INT"]),
            ("Mage", ["INT", "WIS"]),
            ("Cleric", ["WIS", "CHA"]),
        ],
    )
    def test_saving_throw_proficiencies_by_class(
        self, character_class, expected_save_profs
    ):
        """Each class gets correct saving throw proficiencies per D&D 5e SRD."""
        record = _make_record(
            character_class=character_class,
            abilities={
                "STR": 14,
                "DEX": 14,
                "CON": 14,
                "INT": 14,
                "WIS": 14,
                "CHA": 14,
            },
        )
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        st = result["saving_throw_modifiers"]
        for abil in expected_save_profs:
            assert st[abil] == 4, (
                f"{character_class} should be proficient in {abil} (+2 ability +2 prof)"
            )
        non_prof = [
            a
            for a in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
            if a not in expected_save_profs
        ]
        for abil in non_prof:
            assert st[abil] == 2, (
                f"{character_class} not proficient in {abil} (only +2 ability)"
            )

    def test_all_six_saving_throws_present(self):
        """All 6 ability saving throws are present in result."""
        record = _make_record()
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        assert set(result["saving_throw_modifiers"].keys()) == {
            "STR",
            "DEX",
            "CON",
            "INT",
            "WIS",
            "CHA",
        }

    @pytest.mark.parametrize(
        "skill_key,expected_ability",
        [
            ("acrobatics", "DEX"),
            ("animal_handling", "WIS"),
            ("arcana", "INT"),
            ("athletics", "STR"),
            ("deception", "CHA"),
            ("history", "INT"),
            ("insight", "WIS"),
            ("intimidation", "CHA"),
            ("investigation", "INT"),
            ("medicine", "WIS"),
            ("nature", "INT"),
            ("perception", "WIS"),
            ("performance", "CHA"),
            ("persuasion", "CHA"),
            ("religion", "INT"),
            ("sleight_of_hand", "DEX"),
            ("stealth", "DEX"),
            ("survival", "WIS"),
        ],
    )
    def test_untrained_skill_uses_ability_modifier_only(
        self, skill_key, expected_ability
    ):
        """Untrained skills get only ability modifier (no proficiency bonus)."""
        record = _make_record(
            abilities={"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}
        )
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        assert result["skill_modifiers"][skill_key] == 0, (
            f"{skill_key} untrained should be 0"
        )

    def test_trained_skill_adds_proficiency_bonus(self):
        """A trained skill gets ability modifier + proficiency bonus."""
        record = _make_record(
            abilities={
                "STR": 14,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            skills=["Athletics"],
        )
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        # STR 14 -> +2 modifier, level 1 -> +2 prof bonus -> total 4
        assert result["skill_modifiers"]["athletics"] == 4

    def test_title_case_skill_with_spaces_matches_snake_case(self):
        """'Sleight of Hand' correctly maps to 'sleight_of_hand' in skill map."""
        record = _make_record(skills=["Sleight of Hand"])
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        assert (
            result["skill_modifiers"]["sleight_of_hand"] == 2
        )  # DEX 10 (0) + prof(2) = 2

    def test_passive_perception_without_training(self):
        """Passive perception = 10 + perception modifier when untrained."""
        record = _make_record()
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        assert result["passive_perception"] == 10  # perception skill modifier is 0

    def test_passive_perception_with_training(self):
        """Passive perception includes proficiency bonus when trained."""
        record = _make_record(skills=["Perception"])
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        assert result["passive_perception"] == 12  # 10 + 0 (WIS 10) + 2 (prof) = 12

    def test_all_18_skill_modifiers_present(self):
        """All 18 skill keys from SKILL_ABILITY_MAP are present in result."""
        record = _make_record()
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        expected_skills = {
            "acrobatics",
            "animal_handling",
            "arcana",
            "athletics",
            "deception",
            "history",
            "insight",
            "intimidation",
            "investigation",
            "medicine",
            "nature",
            "perception",
            "performance",
            "persuasion",
            "religion",
            "sleight_of_hand",
            "stealth",
            "survival",
        }
        assert set(result["skill_modifiers"].keys()) == expected_skills

    def test_returns_exactly_three_keys(self):
        """Result dict has exactly three expected keys."""
        record = _make_record()
        base = prepare_base_data(record)
        result = prepare_embedded_data(base, record)
        assert set(result.keys()) == {
            "skill_modifiers",
            "saving_throw_modifiers",
            "passive_perception",
        }

    def test_deterministic_same_input_same_output(self):
        """Same input always produces same output."""
        record = _make_record(
            abilities={"STR": 15, "DEX": 12, "CON": 14, "INT": 8, "WIS": 10, "CHA": 13},
            skills=["Athletics", "Perception"],
        )
        base = prepare_base_data(record)
        result1 = prepare_embedded_data(base, record)
        result2 = prepare_embedded_data(base, record)
        assert result1 == result2

    def test_does_not_mutate_base_dict(self):
        """The function does not modify the input base dict."""
        record = _make_record()
        base = prepare_base_data(record)
        original = dict(base)
        prepare_embedded_data(base, record)
        assert base == original

    def test_does_not_mutate_record(self):
        """The function does not modify the input record."""
        record = _make_record(name="TestHero")
        base = prepare_base_data(record)
        original_name = record.name
        prepare_embedded_data(base, record)
        assert record.name == original_name
