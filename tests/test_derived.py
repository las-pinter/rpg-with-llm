"""Comprehensive tests for the Derivation Pipeline — Phase 2, Task 2.1."""

from __future__ import annotations

import pytest

from app.character.derived import (
    compute_derived_sheet,
    prepare_base_data,
    prepare_derived_data,
    prepare_embedded_data,
)
from app.character.items import Item, ItemType
from app.character.model import STANDARD_ABILITIES, CharacterRecord
from app.character.resources import ResourceData

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


def _make_item(
    name: str,
    item_type: ItemType,
    weight: float = 0.0,
    properties: dict | None = None,
) -> Item:
    """Create a simple Item for testing."""
    return Item(
        name=name,
        item_type=item_type,
        weight=weight,
        properties=properties or {},
    )


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


class TestPrepareDerivedData:
    """Tests for prepare_derived_data — AC, initiative, encumbrance, attack bonuses."""

    def _make_record_with_items(
        self,
        abilities: dict[str, int] | None = None,
        level: int = 1,
        character_class: str = "Fighter",
        inventory: list[Item] | None = None,
        equipped_items: list[str] | None = None,
        skills: list[str] | None = None,
        name: str = "Test",
    ) -> CharacterRecord:
        """Helper to create a record with inventory."""
        if abilities is None:
            abilities = {a: 10 for a in STANDARD_ABILITIES}
        if inventory is None:
            inventory = []
        if equipped_items is None:
            equipped_items = []
        record = _make_record(
            name=name,
            abilities=abilities,
            level=level,
            character_class=character_class,
            skills=skills or [],
        )
        record.inventory = inventory
        record.equipped_items = equipped_items
        return record

    def _compute(self, record: CharacterRecord) -> dict:
        """Run all three pipeline phases and return prepare_derived_data result."""
        base = prepare_base_data(record)
        embedded = prepare_embedded_data(base, record)
        return prepare_derived_data(embedded, base, record)

    # ------------------------------------------------------------------
    # AC Tests
    # ------------------------------------------------------------------

    def test_ac_no_armor(self):
        """Without armor, AC = 10 + DEX modifier."""
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 14,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = self._compute(record)
        assert result["ac"] == 12  # 10 + 2 (DEX 14)

    def test_ac_light_armor(self):
        """Light armor adds its armor_bonus and allows full DEX."""
        armor = _make_item(
            "Leather Armor",
            ItemType.ARMOR,
            weight=10.0,
            properties={"armor_bonus": 11, "armor_category": "light"},
        )
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 14,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=[armor],
            equipped_items=[armor.id],
        )
        result = self._compute(record)
        assert result["ac"] == 13  # 11 (Leather) + 2 (DEX)

    def test_ac_medium_armor_caps_dex(self):
        """Medium armor caps DEX modifier at +2."""
        armor = _make_item(
            "Chain Shirt",
            ItemType.ARMOR,
            weight=20.0,
            properties={"armor_bonus": 13, "armor_category": "medium"},
        )
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 18,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=[armor],
            equipped_items=[armor.id],
        )
        result = self._compute(record)
        # DEX 18 gives +4, but medium armor caps at +2, so AC = 13 + 2 = 15
        assert result["ac"] == 15

    def test_ac_heavy_armor_no_dex(self):
        """Heavy armor does not add DEX modifier."""
        armor = _make_item(
            "Chain Mail",
            ItemType.ARMOR,
            weight=55.0,
            properties={"armor_bonus": 16, "armor_category": "heavy"},
        )
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 14,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=[armor],
            equipped_items=[armor.id],
        )
        result = self._compute(record)
        assert result["ac"] == 16  # Chain Mail is flat 16

    def test_ac_with_shield(self):
        """Shield adds +2 AC on top of other armor."""
        body = _make_item(
            "Chain Mail",
            ItemType.ARMOR,
            weight=55.0,
            properties={"armor_bonus": 16, "armor_category": "heavy"},
        )
        shield = _make_item(
            "Shield",
            ItemType.ARMOR,
            weight=6.0,
            properties={"armor_bonus": 2, "armor_category": "shield"},
        )
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=[body, shield],
            equipped_items=[body.id, shield.id],
        )
        result = self._compute(record)
        assert result["ac"] == 18  # 16 (Chain Mail) + 2 (Shield)

    def test_ac_light_armor_with_shield(self):
        """Light armor + shield = armor AC + DEX + shield."""
        body = _make_item(
            "Leather Armor",
            ItemType.ARMOR,
            weight=10.0,
            properties={"armor_bonus": 11, "armor_category": "light"},
        )
        shield = _make_item(
            "Shield",
            ItemType.ARMOR,
            weight=6.0,
            properties={"armor_bonus": 2, "armor_category": "shield"},
        )
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 14,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=[body, shield],
            equipped_items=[body.id, shield.id],
        )
        result = self._compute(record)
        assert result["ac"] == 15  # 11 + 2 (DEX) + 2 (shield) = 15

    def test_ac_not_equipped_armor_not_counted(self):
        """Items in inventory but not equipped don't affect AC."""
        armor = _make_item(
            "Chain Mail",
            ItemType.ARMOR,
            weight=55.0,
            properties={"armor_bonus": 16, "armor_category": "heavy"},
        )
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=[armor],
            equipped_items=[],  # Not equipped!
        )
        result = self._compute(record)
        assert result["ac"] == 10  # Unarmored

    # ------------------------------------------------------------------
    # Initiative Tests
    # ------------------------------------------------------------------

    def test_initiative_equals_dex_modifier(self):
        """Initiative = DEX modifier."""
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 14,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = self._compute(record)
        assert result["initiative"] == 2

    def test_initiative_negative_dex(self):
        """Initiative can be negative with low DEX."""
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 6,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = self._compute(record)
        assert result["initiative"] == -2

    # ------------------------------------------------------------------
    # Encumbrance Tests
    # ------------------------------------------------------------------

    def test_encumbrance_empty_inventory(self):
        """Empty inventory has 0 weight and 'normal' status."""
        record = self._make_record_with_items()
        result = self._compute(record)
        assert result["encumbrance"]["current"] == 0
        assert result["encumbrance"]["status"] == "normal"

    def test_encumbrance_normal_load(self):
        """Weight ≤ STR×5 is 'normal'."""
        items = [
            _make_item("Sword", ItemType.WEAPON, weight=3.0),
            _make_item("Torch", ItemType.TOOL, weight=1.0),
        ]
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=items,
        )
        result = self._compute(record)
        assert result["encumbrance"]["current"] == 4.0
        assert result["encumbrance"]["max"] == 150  # STR 10 * 15
        assert result["encumbrance"]["status"] == "normal"

    def test_encumbrance_encumbered(self):
        """Weight between STR×5 and STR×10 is 'encumbered'."""
        items = [_make_item("Heavy Rock", ItemType.MISC, weight=60.0)]
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=items,
        )
        result = self._compute(record)
        assert result["encumbrance"]["status"] == "encumbered"  # 60 > 50

    def test_encumbrance_heavily_encumbered(self):
        """Weight between STR×10 and STR×15 is 'heavily encumbered'."""
        items = [_make_item("Very Heavy Rock", ItemType.MISC, weight=120.0)]
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=items,
        )
        result = self._compute(record)
        assert result["encumbrance"]["status"] == "heavily encumbered"

    def test_encumbrance_at_boundary(self):
        """Exactly at STR×5 is normal, STR×5+1 is encumbered."""
        # At exactly STR×5 (50 for STR 10): not > 50, so normal
        items = [_make_item("Boundary Load", ItemType.MISC, weight=50.0)]
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=items,
        )
        assert self._compute(record)["encumbrance"]["status"] == "normal"

        # At STR×5 + 1 (51 for STR 10): > 50, so encumbered
        items2 = [_make_item("Encumbering Load", ItemType.MISC, weight=51.0)]
        record2 = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            inventory=items2,
        )
        assert self._compute(record2)["encumbrance"]["status"] == "encumbered"

    # ------------------------------------------------------------------
    # Attack Bonus Tests
    # ------------------------------------------------------------------

    def test_attack_bonus_melee_uses_strength(self):
        """Melee attack = proficiency_bonus + STR modifier."""
        record = self._make_record_with_items(
            abilities={
                "STR": 16,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            level=1,
            character_class="Fighter",
        )
        result = self._compute(record)
        assert result["attack_bonus"]["melee"] == 5  # +2 prof + 3 STR

    def test_attack_bonus_ranged_uses_dexterity(self):
        """Ranged attack = proficiency_bonus + DEX modifier."""
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 16,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            level=1,
            character_class="Rogue",
        )
        result = self._compute(record)
        assert result["attack_bonus"]["ranged"] == 5  # +2 prof + 3 DEX

    @pytest.mark.parametrize(
        "char_class,expected_ability,expected_mod",
        [
            ("Mage", "INT", 1),  # Mage uses INT (INT 12 → +1)
            ("Cleric", "WIS", 3),  # Cleric uses WIS (WIS 16 → +3)
            ("Fighter", "INT", 1),  # Fighter uses INT (INT 12 → +1)
            ("Rogue", "INT", 1),  # Rogue uses INT (INT 12 → +1)
        ],
    )
    def test_attack_bonus_spell_by_class(
        self, char_class: str, expected_ability: str, expected_mod: int
    ):
        """Spell attack = proficiency_bonus + class-specific ability modifier."""
        abilities = {
            "STR": 10,
            "DEX": 10,
            "CON": 10,
            "INT": 12,
            "WIS": 16,
            "CHA": 10,
        }
        record = self._make_record_with_items(
            abilities=abilities, level=1, character_class=char_class
        )
        result = self._compute(record)
        # prof bonus (+2) + ability modifier
        assert result["attack_bonus"]["spell"] == 2 + expected_mod, (
            f"{char_class} spell attack should use {expected_ability}"
        )

    def test_attack_bonus_has_all_three_keys(self):
        """Attack bonus dict has melee, ranged, spell keys."""
        record = self._make_record_with_items()
        result = self._compute(record)
        assert set(result["attack_bonus"].keys()) == {"melee", "ranged", "spell"}

    # ------------------------------------------------------------------
    # Formula Tests
    # ------------------------------------------------------------------

    def test_formulas_contains_ac_breakdown(self):
        """Formulas include AC breakdown string."""
        record = self._make_record_with_items()
        result = self._compute(record)
        assert "ac" in result["formulas"]
        assert "10 (base)" in result["formulas"]["ac"]

    def test_formulas_contains_initiative(self):
        """Formulas include initiative breakdown."""
        record = self._make_record_with_items(
            abilities={
                "STR": 10,
                "DEX": 14,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = self._compute(record)
        assert "initiative" in result["formulas"]

    # ------------------------------------------------------------------
    # Pure function tests
    # ------------------------------------------------------------------

    def test_deterministic_same_input_same_output(self):
        """Same input always produces same output."""
        armor = _make_item(
            "Leather Armor",
            ItemType.ARMOR,
            weight=10.0,
            properties={"armor_bonus": 11, "armor_category": "light"},
        )
        record = self._make_record_with_items(
            abilities={
                "STR": 15,
                "DEX": 14,
                "CON": 13,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            },
            level=3,
            character_class="Rogue",
            inventory=[armor],
            equipped_items=[armor.id],
        )
        base = prepare_base_data(record)
        embedded = prepare_embedded_data(base, record)
        result1 = prepare_derived_data(embedded, base, record)
        result2 = prepare_derived_data(embedded, base, record)
        assert result1 == result2

    def test_does_not_mutate_record(self):
        """Function does not modify the input record."""
        record = self._make_record_with_items(name="TestHero")
        base = prepare_base_data(record)
        embedded = prepare_embedded_data(base, record)
        original_name = record.name
        prepare_derived_data(embedded, base, record)
        assert record.name == original_name

    def test_returns_exactly_five_keys(self):
        """Result dict has exactly five expected keys."""
        record = self._make_record_with_items()
        base = prepare_base_data(record)
        embedded = prepare_embedded_data(base, record)
        result = prepare_derived_data(embedded, base, record)
        assert set(result.keys()) == {
            "ac",
            "initiative",
            "encumbrance",
            "attack_bonus",
            "formulas",
        }


class TestComputeDerivedSheet:
    """Integration tests for the full derivation pipeline orchestrator."""

    def _make_full_record(
        self,
        name="TestHero",
        character_class="Fighter",
        level=1,
        abilities=None,
        skills=None,
        inventory=None,
        equipped_items=None,
        resources=None,
    ):
        """Create a CharacterRecord fully populated for integration tests."""
        if abilities is None:
            abilities = {
                "STR": 15,
                "DEX": 13,
                "CON": 14,
                "INT": 10,
                "WIS": 12,
                "CHA": 8,
            }
        if skills is None:
            skills = ["Athletics", "Perception"]
        if resources is None:
            resources = {"hp": ResourceData(value=12, max=12)}

        record = _make_record(
            name=name,
            abilities=abilities,
            level=level,
            character_class=character_class,
            skills=skills,
            resources=resources,
        )

        if inventory:
            record.inventory = inventory
        if equipped_items:
            record.equipped_items = equipped_items

        return record

    # ------------------------------------------------------------------
    # Happy path — each class at level 1
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "class_name,exp_prof,exp_hd,exp_ac_base",
        [
            ("Fighter", 2, "1d10", 11),  # DEX 13 -> +1, unarmored -> 10 + 1 = 11
            ("Rogue", 2, "1d8", 11),  # DEX 13 -> +1
            ("Mage", 2, "1d6", 11),  # DEX 13 -> +1
            ("Cleric", 2, "1d8", 11),  # DEX 13 -> +1
        ],
    )
    def test_class_at_level_1(self, class_name, exp_prof, exp_hd, exp_ac_base):
        """Full DerivedSheet for each class at level 1 has correct base values."""
        sheet = compute_derived_sheet(
            self._make_full_record(character_class=class_name)
        )

        assert sheet.proficiency_bonus == exp_prof
        assert sheet.hit_dice == exp_hd
        assert sheet.speed == 30

        # Ability mods: STR +2, DEX +1, CON +2, INT 0, WIS +1, CHA -1
        assert sheet.ability_modifiers["STR"] == 2
        assert sheet.ability_modifiers["DEX"] == 1
        assert sheet.ability_modifiers["CON"] == 2
        assert sheet.ability_modifiers["INT"] == 0
        assert sheet.ability_modifiers["WIS"] == 1
        assert sheet.ability_modifiers["CHA"] == -1

        # AC: unarmored = 10 + DEX(+1) = 11
        assert sheet.ac == exp_ac_base

        # Initiative: DEX modifier
        assert sheet.initiative == 1

    def test_fighter_level_1_skills(self):
        """Fighter with Athletics and Perception has correct skill modifiers."""
        sheet = compute_derived_sheet(
            self._make_full_record(
                character_class="Fighter",
                skills=["Athletics", "Perception"],
            )
        )
        # Athletics: STR 15 (+2) + prof (2) = 4
        assert sheet.skill_modifiers["athletics"] == 4
        # Perception: WIS 12 (+1) + prof (2) = 3
        assert sheet.skill_modifiers["perception"] == 3
        # Stealth: untrained, DEX 13 (+1) only = 1
        assert sheet.skill_modifiers["stealth"] == 1
        # Arcana: untrained, INT 10 (0) only = 0
        assert sheet.skill_modifiers["arcana"] == 0

    def test_fighter_level_1_saving_throws(self):
        """Fighter has proficient STR and CON saves."""
        sheet = compute_derived_sheet(self._make_full_record(character_class="Fighter"))
        # STR save: STR 15 (+2) + prof (2) = 4
        assert sheet.saving_throw_modifiers["STR"] == 4
        # CON save: CON 14 (+2) + prof (2) = 4
        assert sheet.saving_throw_modifiers["CON"] == 4
        # INT save: untrained, INT 10 (0) only = 0
        assert sheet.saving_throw_modifiers["INT"] == 0

    def test_fighter_level_1_passive_perception(self):
        """Fighter with Perception training has passive perception 13."""
        sheet = compute_derived_sheet(
            self._make_full_record(
                character_class="Fighter",
                skills=["Athletics", "Perception"],
            )
        )
        # 10 + perception_mod (WIS +1 + prof +2 = 3) = 13
        assert sheet.passive_perception == 13

    # ------------------------------------------------------------------
    # Level-up scenario
    # ------------------------------------------------------------------

    def test_level_up_increases_proficiency(self):
        """Level 1->5 increases proficiency bonus from +2 to +3."""
        record_l1 = self._make_full_record(level=1)
        record_l5 = self._make_full_record(level=5)

        sheet_l1 = compute_derived_sheet(record_l1)
        sheet_l5 = compute_derived_sheet(record_l5)

        assert sheet_l1.proficiency_bonus == 2
        assert sheet_l5.proficiency_bonus == 3

    def test_level_up_increases_skill_modifiers(self):
        """Proficiency bonus increase at level 5 boosts trained skills."""
        record_l1 = self._make_full_record(level=1, skills=["Athletics"])
        record_l5 = self._make_full_record(level=5, skills=["Athletics"])

        sheet_l1 = compute_derived_sheet(record_l1)
        sheet_l5 = compute_derived_sheet(record_l5)

        # Athletics at level 1: STR 15 (+2) + prof 2 = 4
        assert sheet_l1.skill_modifiers["athletics"] == 4
        # Athletics at level 5: STR 15 (+2) + prof 3 = 5
        assert sheet_l5.skill_modifiers["athletics"] == 5

    def test_level_up_increases_saving_throws(self):
        """Proficiency bonus increase at level 5 boosts proficient saves."""
        record_l1 = self._make_full_record(level=1, character_class="Fighter")
        record_l5 = self._make_full_record(level=5, character_class="Fighter")

        sheet_l1 = compute_derived_sheet(record_l1)
        sheet_l5 = compute_derived_sheet(record_l5)

        # STR save at level 1: +2 + 2 = 4; at level 5: +2 + 3 = 5
        assert sheet_l1.saving_throw_modifiers["STR"] == 4
        assert sheet_l5.saving_throw_modifiers["STR"] == 5

    def test_level_up_attack_bonus_increases(self):
        """Proficiency bonus increase improves attack bonuses."""
        record_l1 = self._make_full_record(level=1, character_class="Fighter")
        record_l5 = self._make_full_record(level=5, character_class="Fighter")

        sheet_l1 = compute_derived_sheet(record_l1)
        sheet_l5 = compute_derived_sheet(record_l5)

        # Melee at level 1: prof 2 + STR 2 = 4; at level 5: prof 3 + STR 2 = 5
        assert sheet_l1.attack_bonus["melee"] == 4
        assert sheet_l5.attack_bonus["melee"] == 5

    # ------------------------------------------------------------------
    # ResourceData max formula resolution
    # ------------------------------------------------------------------

    def test_resource_max_int_resolved(self):
        """ResourceData with int max is resolved to same value."""
        record = self._make_full_record(
            resources={
                "hp": ResourceData(value=12, max=12),
            }
        )
        sheet = compute_derived_sheet(record)
        assert "hp_max" in sheet.formulas

    def test_resource_max_string_formula_resolved(self):
        """ResourceData with '12+CON' formula is resolved using CON modifier."""
        record = self._make_full_record(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 14,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            resources={"hp": ResourceData(value=10, max="12+CON")},
        )
        sheet = compute_derived_sheet(record)
        # CON 14 -> +2 modifier -> 12 + 2 = 14
        assert "hp_max" in sheet.formulas
        assert (
            "14" in sheet.formulas["hp_max"]
            or "12 + CON(+2) = 14" in sheet.formulas["hp_max"]
        )

    def test_resource_multiple_resources_resolved(self):
        """Multiple resources each have their max resolved."""
        record = self._make_full_record(
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 14,
                "INT": 12,
                "WIS": 10,
                "CHA": 10,
            },
            resources={
                "hp": ResourceData(value=10, max="12+CON"),
                "mana": ResourceData(value=5, max="5+INT"),
            },
        )
        sheet = compute_derived_sheet(record)
        assert "hp_max" in sheet.formulas
        assert "mana_max" in sheet.formulas

    # ------------------------------------------------------------------
    # Armor integration (full pipeline with items)
    # ------------------------------------------------------------------

    def test_fighter_with_chain_mail_and_shield(self):
        """Equipped armor correctly affects AC through full pipeline."""
        body = _make_item(
            "Chain Mail",
            ItemType.ARMOR,
            weight=55.0,
            properties={"armor_bonus": 16, "armor_category": "heavy"},
        )
        shield = _make_item(
            "Shield",
            ItemType.ARMOR,
            weight=6.0,
            properties={"armor_bonus": 2, "armor_category": "shield"},
        )

        # Fighter with STR 15, DEX 13, CON 14
        record = self._make_full_record(
            character_class="Fighter",
            abilities={"STR": 15, "DEX": 13, "CON": 14, "INT": 10, "WIS": 12, "CHA": 8},
            inventory=[body, shield],
            equipped_items=[body.id, shield.id],
        )
        sheet = compute_derived_sheet(record)
        # Chain Mail 16 + Shield 2 = 18 (heavy, no DEX)
        assert sheet.ac == 18

    # ------------------------------------------------------------------
    # Pure function tests
    # ------------------------------------------------------------------

    def test_deterministic_same_input_same_output(self):
        """Same record always produces same DerivedSheet."""
        record = self._make_full_record(level=3, character_class="Rogue")
        sheet1 = compute_derived_sheet(record)
        sheet2 = compute_derived_sheet(record)
        assert sheet1 == sheet2

    def test_does_not_mutate_record(self):
        """compute_derived_sheet does not modify the input record."""
        record = self._make_full_record(name="Unchanged")
        original_name = record.name
        original_level = record.level
        compute_derived_sheet(record)
        assert record.name == original_name
        assert record.level == original_level

    def test_returns_derived_sheet_instance(self):
        """Returns a DerivedSheet instance, not a dict."""
        record = self._make_full_record()
        sheet = compute_derived_sheet(record)
        from app.character.model import DerivedSheet

        assert isinstance(sheet, DerivedSheet)
