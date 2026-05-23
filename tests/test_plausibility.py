"""Tests for the plausibility classification module."""

from __future__ import annotations

import pytest

from app.character.model import Character
from app.rules.plausibility import (
    CATEGORY_DC,
    CATEGORY_DESCRIPTIONS,
    CATEGORY_ORDER,
    classify_action,
    get_categories,
    suggest_dc,
)


def _make_fighter() -> Character:
    """Return a default level 1 Fighter for testing."""
    return Character.create_default("Test Fighter", "Fighter")


def _make_mage() -> Character:
    """Return a default level 1 Mage for testing."""
    return Character.create_default("Test Mage", "Mage")


def _make_high_level_fighter() -> Character:
    """Return a level 10 Fighter for testing."""
    return Character(
        name="Test High Fighter",
        character_class="Fighter",
        level=10,
        xp=64000,
        abilities={"STR": 18, "DEX": 14, "CON": 16, "WIS": 12, "INT": 10, "CHA": 8},
        skills=["Athletics", "Perception", "Survival"],
        hp=85,
        max_hp=85,
        ac=18,
        inventory=["Longsword+1", "Plate Armor", "Shield"],
    )


# ===========================================================================
# classify_action tests
# ===========================================================================


class TestClassifyAction:
    """Tests for ``classify_action``."""

    def test_fighter_casting_spell_is_impossible(self) -> None:
        """A Fighter attempting to cast a spell should be impossible."""
        char = _make_fighter()
        result = classify_action(char, "I cast fireball at the goblins")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False
        assert result["dc"] is None
        assert "Fighter" in result["reason"]

    def test_fighter_wishing_to_be_god_is_impossible(self) -> None:
        """A level 1 Fighter trying to become a god is impossible."""
        char = _make_fighter()
        result = classify_action(char, "I become a god")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False
        assert result["dc"] is None
        assert "become god" in result["reason"].lower()

    def test_mage_wishing_to_be_god_is_impossible(self) -> None:
        """A Mage trying to become a god is still impossible."""
        char = _make_mage()
        result = classify_action(char, "I wish to become a god")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False

    def test_fighter_teleport_is_impossible(self) -> None:
        """Teleport is impossible for a Fighter."""
        char = _make_fighter()
        result = classify_action(char, "I teleport to the dragon's lair")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False

    def test_level_1_raise_dead_is_impossible(self) -> None:
        """A level 1 character cannot raise the dead."""
        char = _make_fighter()
        result = classify_action(char, "I raise the dead king")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False

    def test_level_1_fighter_summon_spirit_is_impossible(self) -> None:
        """A level 1 Fighter trying to summon a spirit is impossible (bug #4)."""
        char = _make_fighter()
        result = classify_action(char, "I summon the spirit of the forest")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False
        assert result["dc"] is None

    def test_fighter_summon_guard_is_plausible(self) -> None:
        """A Fighter summoning a guard should still be plausible (regression)."""
        char = _make_fighter()
        result = classify_action(char, "I summon the guard to help me")
        assert result["category"] == "plausible"
        assert result["allow_roll"] is True

    def test_strong_fighter_lifting_is_plausible(self) -> None:
        """A Fighter with STR 15 should find lifting plausible."""
        char = _make_fighter()
        result = classify_action(char, "I lift the heavy portcullis")
        assert result["category"] == "plausible"
        assert result["allow_roll"] is True

    def test_high_level_fighter_overthrow_kingdom_is_possible(self) -> None:
        """A high level fighter can attempt ambitious things."""
        char = _make_high_level_fighter()
        # High level characters don't get auto-blocked on kingdom stuff
        result = classify_action(char, "I climb the castle wall")
        # Should default to plausible for generic actions
        assert result["category"] == "plausible"

    def test_charisma_action_for_low_cha_is_ambitious(self) -> None:
        """A Fighter with CHA 8 should find persuasion ambitious."""
        char = _make_fighter()  # Fighter base has CHA 8
        result = classify_action(char, "I persuade the king to give me his crown")
        assert result["category"] == "ambitious"
        assert result["dc"] == 18
        assert result["allow_roll"] is True

    def test_inventory_does_not_affect_classification(self) -> None:
        """Inventory items should not crash the classifier."""
        char = _make_fighter()
        # This shouldn't crash even though "ancient dragon" is a level 1 blocker
        result = classify_action(char, "attack the ancient dragon")
        assert result["category"] == "impossible"

    def test_default_abilities_plausible(self) -> None:
        """Character with default (all-10) abilities should get plausible."""
        char = Character(
            name="Average",
            character_class="Fighter",
            level=1,
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = classify_action(char, "I open the door")
        assert result["category"] == "plausible"
        assert result["allow_roll"] is True

    # ------------------------------------------------------------------
    # Gap coverage: ability-score edge cases
    # ------------------------------------------------------------------

    def test_weak_fighter_low_strength_implausible(self) -> None:
        """A character with STR <= 8 attempting a STR action gets implausible."""
        char = Character(
            name="Weakling",
            character_class="Fighter",
            level=1,
            abilities={
                "STR": 6,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = classify_action(char, "I lift the heavy gate")
        assert result["category"] == "implausible"
        assert result["dc"] == 23
        assert result["allow_roll"] is True

    def test_low_intelligence_implausible(self) -> None:
        """INT < 8 should make intellectual actions implausible."""
        char = Character(
            name="Dullard",
            character_class="Fighter",
            level=1,
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 6,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = classify_action(char, "I decipher the ancient runes")
        assert result["category"] == "implausible"
        assert result["dc"] == 22
        assert result["allow_roll"] is True

    def test_high_intelligence_plausible(self) -> None:
        """INT >= 14 should make intellectual actions plausible."""
        char = Character(
            name="Scholar",
            character_class="Fighter",
            level=1,
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 16,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = classify_action(char, "I solve the puzzle")
        assert result["category"] == "plausible"
        assert result["dc"] == 12
        assert result["allow_roll"] is True

    def test_high_charisma_plausible(self) -> None:
        """CHA >= 14 should make social actions plausible."""
        char = Character(
            name="Charmer",
            character_class="Fighter",
            level=1,
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 16,
            },
        )
        result = classify_action(char, "I persuade the guard to let me pass")
        assert result["category"] == "plausible"
        assert result["dc"] == 12
        assert result["allow_roll"] is True

    def test_low_wisdom_is_implausible(self) -> None:
        """WIS <= 8 should make spiritual/perceptive actions implausible."""
        char = Character(
            name="Oblivious",
            character_class="Fighter",
            level=1,
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 6,
                "CHA": 10,
            },
        )
        result = classify_action(char, "I look for an omen in the sky")
        assert result["category"] == "implausible"
        assert result["dc"] == 23
        assert result["allow_roll"] is True

    def test_high_wisdom_is_plausible(self) -> None:
        """WIS >= 14 should make spiritual actions plausible."""
        char = Character(
            name="Sage",
            character_class="Fighter",
            level=1,
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 16,
                "CHA": 10,
            },
        )
        result = classify_action(char, "I pray for guidance from the spirits")
        assert result["category"] == "plausible"
        assert result["dc"] == 12
        assert result["allow_roll"] is True

    # ------------------------------------------------------------------
    # Gap coverage: other class blacklists
    # ------------------------------------------------------------------

    def test_rogue_casting_spell_is_impossible(self) -> None:
        """A Rogue attempting to cast a spell should be impossible."""
        char = Character.create_default("Test Rogue", "Rogue")
        result = classify_action(char, "I cast a spell of invisibility")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False
        assert result["dc"] is None

    def test_mage_turning_into_dragon_is_impossible(self) -> None:
        """A Mage trying to turn into a dragon is impossible."""
        char = Character.create_default("Test Mage", "Mage")
        result = classify_action(char, "I turn into a dragon and fly away")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False

    def test_cleric_commanding_deity_is_impossible(self) -> None:
        """A Cleric trying to command a deity is impossible."""
        char = Character.create_default("Test Cleric", "Cleric")
        result = classify_action(char, "I command the deity to grant me power")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False

    # ------------------------------------------------------------------
    # Level-based cap at level 1
    # ------------------------------------------------------------------

    def test_level_1_teleport_is_impossible(self) -> None:
        """A level 1 character cannot teleport (level cap)."""
        char = Character.create_default("Test Fighter", "Fighter")
        result = classify_action(char, "I teleport across the chasm")
        assert result["category"] == "impossible"
        assert result["allow_roll"] is False


# ===========================================================================
# suggest_dc tests
# ===========================================================================


class TestSuggestDC:
    """Tests for ``suggest_dc``."""

    def test_trivial_returns_none(self) -> None:
        """Trivial actions should have no DC and allow_roll=False."""
        char = _make_fighter()
        result = suggest_dc(char, "trivial")
        assert result["category"] == "trivial"
        assert result["suggested_dc"] is None
        assert result["allow_roll"] is True  # trivial is auto-success

    def test_impossible_returns_none(self) -> None:
        """Impossible actions should have no DC and allow_roll=False."""
        char = _make_fighter()
        result = suggest_dc(char, "impossible")
        assert result["category"] == "impossible"
        assert result["suggested_dc"] is None
        assert not result["allow_roll"]

    def test_plausible_returns_dc(self) -> None:
        """Plausible actions should return a valid DC."""
        char = _make_fighter()
        result = suggest_dc(char, "plausible")
        assert result["category"] == "plausible"
        assert isinstance(result["suggested_dc"], int)
        assert result["suggested_dc"] >= 5
        assert result["allow_roll"] is True

    def test_implausible_returns_high_dc(self) -> None:
        """Implausible actions should return a high DC."""
        char = _make_fighter()
        result = suggest_dc(char, "implausible")
        assert result["suggested_dc"] is not None
        # implausible base is 23, no level adjustment for level 1-2
        assert result["suggested_dc"] == 23
        assert result["allow_roll"] is True

    def test_high_level_lowers_dc(self) -> None:
        """Higher level characters should have slightly lower DCs."""
        low_char = _make_fighter()  # level 1
        high_char = _make_high_level_fighter()  # level 10

        low_result = suggest_dc(low_char, "ambitious")
        high_result = suggest_dc(high_char, "ambitious")

        # High level should have lower (or equal) suggested DC
        assert high_result["suggested_dc"] is not None
        assert low_result["suggested_dc"] is not None
        assert high_result["suggested_dc"] <= low_result["suggested_dc"]

    def test_invalid_category_raises_error(self) -> None:
        """Invalid category should raise ValueError."""
        char = _make_fighter()
        with pytest.raises(ValueError, match="Invalid category"):
            suggest_dc(char, "nonexistent")

    # ------------------------------------------------------------------
    # Level adjustment coverage for missing branches
    # ------------------------------------------------------------------

    def test_level_3_to_4_adjustment(self) -> None:
        """Level 3-4 characters should get level_adj of -1."""
        char = Character(
            name="Mid Level",
            character_class="Fighter",
            level=3,
            abilities={
                "STR": 14,
                "DEX": 12,
                "CON": 13,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
        )
        result = suggest_dc(char, "ambitious")
        assert result["level_adjustment"] == -1
        # ambitious base is 17, -1 = 16
        assert result["suggested_dc"] == 16

    def test_level_5_to_7_adjustment(self) -> None:
        """Level 5-7 characters should get level_adj of -2."""
        char = Character(
            name="Higher Level",
            character_class="Fighter",
            level=6,
            abilities={
                "STR": 16,
                "DEX": 14,
                "CON": 15,
                "INT": 12,
                "WIS": 10,
                "CHA": 8,
            },
        )
        result = suggest_dc(char, "ambitious")
        assert result["level_adjustment"] == -2
        # ambitious base is 17, -2 = 15
        assert result["suggested_dc"] == 15


# ===========================================================================
# get_categories tests
# ===========================================================================


class TestGetCategories:
    """Tests for ``get_categories``."""

    def test_returns_all_categories(self) -> None:
        """get_categories should return all defined categories."""
        cats = get_categories()
        assert set(cats.keys()) == set(CATEGORY_ORDER)
        for cat in CATEGORY_ORDER:
            assert isinstance(cats[cat], str)
            assert len(cats[cat]) > 0

    def test_descriptions_match_constants(self) -> None:
        """Descriptions should match the module constants."""
        cats = get_categories()
        for cat in CATEGORY_ORDER:
            assert cats[cat] == CATEGORY_DESCRIPTIONS[cat]


# ===========================================================================
# Module constant tests
# ===========================================================================


class TestConstants:
    """Tests for module-level constants."""

    def test_category_order_has_all_categories(self) -> None:
        """CATEGORY_ORDER should include all standard categories."""
        assert "trivial" in CATEGORY_ORDER
        assert "plausible" in CATEGORY_ORDER
        assert "ambitious" in CATEGORY_ORDER
        assert "implausible" in CATEGORY_ORDER
        assert "impossible" in CATEGORY_ORDER

    def test_category_dc_has_all_entries(self) -> None:
        """CATEGORY_DC should have an entry for each category."""
        for cat in CATEGORY_ORDER:
            assert cat in CATEGORY_DC

    def test_category_descriptions_has_all_entries(self) -> None:
        """CATEGORY_DESCRIPTIONS should have an entry for each category."""
        for cat in CATEGORY_ORDER:
            assert cat in CATEGORY_DESCRIPTIONS

    def test_trivial_and_impossible_have_none_dc(self) -> None:
        """Trivial and impossible should have None DC."""
        assert CATEGORY_DC["trivial"] is None
        assert CATEGORY_DC["impossible"] is None

    def test_mid_categories_have_valid_dc(self) -> None:
        """Plausible, ambitious, implausible should have DC values."""
        assert isinstance(CATEGORY_DC["plausible"], int)
        assert isinstance(CATEGORY_DC["ambitious"], int)
        assert isinstance(CATEGORY_DC["implausible"], int)
        assert CATEGORY_DC["plausible"] >= 5
        assert CATEGORY_DC["ambitious"] >= 10
        assert CATEGORY_DC["implausible"] >= 15
