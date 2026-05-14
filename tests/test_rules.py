"""Comprehensive tests for the rules engine (checks, combat, XP, status)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.dice.parser import DiceExpression, KeepMode
from app.rules.checks import (
    SKILL_ABILITY_MAP,
    ability_check,
    get_ability_modifier,
    saving_throw,
    skill_check,
)
from app.rules.combat import apply_damage, attack_roll, calculate_damage
from app.rules.status import (
    BLINDED,
    INSPIRED,
    POISONED,
    RESTRAINED,
    STUNNED,
    StatusEffect,
    apply_effect,
    remove_effect,
    tick_effects,
)
from app.rules.xp import XP_THRESHOLDS, calculate_xp, check_level_up, xp_to_next_level


def _mock_roll(total: int = 10, sides: int = 20, formula: str = "1d20") -> dict:
    """Return a standardised roll result dict for use across tests."""
    return {
        "total": total,
        "rolls": [total],
        "sides": sides,
        "formula": formula,
    }


# ---------------------------------------------------------------------------
# Shared fixture: character stats used across multiple test classes
# ---------------------------------------------------------------------------

BASE_STATS = {
    "strength": 14,
    "dexterity": 12,
    "constitution": 15,
    "intelligence": 10,
    "wisdom": 8,
    "charisma": 13,
    "proficiency_bonus": 2,
    "level": 1,
    "armor_class": 14,
    "hit_points": 12,
    "max_hit_points": 12,
    "saving_throws": {"strength": True, "constitution": True},
    "skills": {"perception": True, "stealth": True, "investigation": True},
}


# ===========================================================================
# Checks tests
# ===========================================================================


class TestGetAbilityModifier:
    """``get_ability_modifier`` correctness."""

    def test_score_10(self):
        """Score 10 should give modifier 0."""
        assert get_ability_modifier(10) == 0

    def test_score_14(self):
        """Score 14 should give modifier +2."""
        assert get_ability_modifier(14) == 2

    def test_score_8(self):
        """Score 8 should give modifier -1."""
        assert get_ability_modifier(8) == -1

    def test_score_20(self):
        """Score 20 should give modifier +5."""
        assert get_ability_modifier(20) == 5

    def test_score_3(self):
        """Score 3 should give modifier -4 (floor division)."""
        assert get_ability_modifier(3) == -4

    def test_score_1(self):
        """Score 1 should give modifier -5 (floor division)."""
        assert get_ability_modifier(1) == -5

    def test_score_30(self):
        """Score 30 should give modifier +10."""
        assert get_ability_modifier(30) == 10


class TestSkillCheck:
    """Skill check logic."""

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_trained_skill_adds_proficiency(self, mock_parse, mock_roll):
        """A trained skill should include proficiency bonus in the modifier."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=10)

        # perception is trained, wisdom=8 -> -1 mod, prof=2 -> total mod = 1
        result = skill_check(BASE_STATS, "perception", 10)
        assert result["modifier"] == 1  # -1 (wis) + 2 (prof) = 1
        assert result["total"] == 11  # 10 (roll) + 1 (mod)
        assert result["success"] is True
        assert result["margin"] == 1

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_untrained_skill_no_proficiency(self, mock_parse, mock_roll):
        """An untrained skill should NOT include proficiency bonus."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=10)

        # arcana is not trained, intelligence=10 -> 0 mod, no prof
        result = skill_check(BASE_STATS, "arcana", 10)
        assert result["modifier"] == 0  # 0 (int)
        assert result["total"] == 10
        assert result["success"] is True

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_skill_check_default_ability_lookup(self, mock_parse, mock_roll):
        """When ability is None, it should be inferred from SKILL_ABILITY_MAP."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=10)

        # "athletics" maps to "strength" (14 -> +2)
        result = skill_check(BASE_STATS, "athletics", 10)
        assert result["modifier"] == 2  # +2 (str), no proficiency
        assert result["success"] is True

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_skill_check_failure(self, mock_parse, mock_roll):
        """When total < DC, success should be False."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=5)

        result = skill_check(BASE_STATS, "arcana", 20, ability="intelligence")
        assert result["success"] is False
        assert result["margin"] < 0

    def test_skill_ability_map_completeness(self):
        """All standard skills should be in the map."""
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
        assert set(SKILL_ABILITY_MAP.keys()) == expected_skills


class TestSavingThrow:
    """Saving throw logic."""

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_with_proficiency(self, mock_parse, mock_roll):
        """Proficient save should include proficiency bonus."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=10)

        # strength save is proficient, strength=14 -> +2, prof=2 -> total mod = 4
        result = saving_throw(BASE_STATS, "strength", 14)
        assert result["modifier"] == 4  # +2 (str) + 2 (prof)
        assert result["total"] == 14
        assert result["success"] is True

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_without_proficiency(self, mock_parse, mock_roll):
        """Non-proficient save should NOT include proficiency bonus."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=10)

        # dexterity save is NOT proficient, dex=12 -> +1, no prof
        result = saving_throw(BASE_STATS, "dexterity", 11)
        assert result["modifier"] == 1  # +1 (dex)
        assert result["total"] == 11
        assert result["success"] is True

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_saving_throw_failure(self, mock_parse, mock_roll):
        """When total < DC, success should be False."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=5)

        result = saving_throw(BASE_STATS, "strength", 20)
        assert result["success"] is False


class TestAbilityCheck:
    """Pure ability checks."""

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_correct_modifier(self, mock_parse, mock_roll):
        """Ability check should only use ability modifier, no proficiency."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=10)

        # strength=14 -> +2
        result = ability_check(BASE_STATS, "strength", 12)
        assert result["modifier"] == 2
        assert result["total"] == 12
        assert result["success"] is True

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_ability_check_failure(self, mock_parse, mock_roll):
        """When total < DC, success should be False."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=3)

        result = ability_check(BASE_STATS, "charisma", 20)
        assert result["success"] is False


class TestChecksEdgeCases:
    """Edge cases for checks — always fail / always succeed scenarios."""

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_dc_higher_than_max_possible_always_fail(self, mock_parse, mock_roll):
        """If DC exceeds max possible roll + modifier, result should always fail."""
        # Max roll is 20, modifier for arcana (int=10) is 0, so max is 20
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=20)

        # DC 21 > max possible 20
        result = ability_check(BASE_STATS, "intelligence", 21)
        assert result["success"] is False

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_dc_lower_than_min_possible_always_succeed(self, mock_parse, mock_roll):
        """If DC is at or below min possible roll + modifier, always succeed."""
        # Min roll is 1, modifier for strength is 2, so min is 3
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=1)

        # DC 3 <= min possible 3
        result = ability_check(BASE_STATS, "strength", 3)
        assert result["success"] is True


# ===========================================================================
# Combat tests
# ===========================================================================


class TestAttackRoll:
    """Attack roll logic."""

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_hit_when_roll_plus_modifier_meets_ac(self, mock_parse, mock_roll):
        """Roll + modifier >= AC should be a hit."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=12)

        # strength=14 (+2), prof=2 -> total mod = 4, roll=12 -> total=16, AC=15
        result = attack_roll(BASE_STATS, 15)
        assert result["hit"] is True
        assert result["critical"] is False
        assert result["modifier"] == 4  # +2 (str) + 2 (prof)
        assert result["total"] == 16

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_miss_when_total_below_ac(self, mock_parse, mock_roll):
        """Roll + modifier < AC should be a miss (non-natural-1)."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=5)

        # total=5+4=9, AC=15
        result = attack_roll(BASE_STATS, 15)
        assert result["hit"] is False

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_natural_20_always_hits(self, mock_parse, mock_roll):
        """Natural 20 should always hit, even if total < AC."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=20)

        # AC 99 is impossible to beat normally
        result = attack_roll({"strength": 10, "proficiency_bonus": 0}, 99)
        assert result["hit"] is True
        assert result["critical"] is True

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_natural_1_always_misses(self, mock_parse, mock_roll):
        """Natural 1 should always miss, even if total would meet AC."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=1)

        # AC 2 is trivially easy, but nat 1 misses
        result = attack_roll({"strength": 20, "proficiency_bonus": 10}, 2)
        assert result["hit"] is False
        assert result["critical"] is False

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_advantage_parses_correctly(self, mock_parse, mock_roll):
        """Advantage should use 'd20 advantage' notation."""
        mock_parse.return_value = DiceExpression(
            count=2,
            sides=20,
            keep_mode=KeepMode.HIGHEST,
            keep_count=1,
        )
        mock_roll.return_value = {
            "total": 18,
            "rolls": [12, 18],
            "sides": 20,
            "formula": "d20 advantage",
        }

        attack_roll(BASE_STATS, 15, advantage=True)
        mock_parse.assert_called_with("d20 advantage")

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_disadvantage_parses_correctly(self, mock_parse, mock_roll):
        """Disadvantage should use 'd20 disadvantage' notation."""
        mock_parse.return_value = DiceExpression(
            count=2,
            sides=20,
            keep_mode=KeepMode.LOWEST,
            keep_count=1,
        )
        mock_roll.return_value = {
            "total": 5,
            "rolls": [5, 12],
            "sides": 20,
            "formula": "d20 disadvantage",
        }

        attack_roll(BASE_STATS, 15, disadvantage=True)
        mock_parse.assert_called_with("d20 disadvantage")

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_advantage_and_disadvantage_cancel(self, mock_parse, mock_roll):
        """Both advantage+disadvantage should cancel to a normal roll."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=10)

        attack_roll(BASE_STATS, 15, advantage=True, disadvantage=True)
        mock_parse.assert_called_with("1d20")


class TestApplyDamage:
    """Damage resistance/vulnerability logic."""

    def test_normal_damage(self):
        """No resistance or vulnerability should deal full damage."""
        result = apply_damage(10, [], [], "slashing")
        assert result["applied"] == 10
        assert result["original"] == 10
        assert result["multiplier"] == 1.0

    def test_resistance_halves_floor(self):
        """Resistance should halve damage (floor division)."""
        result = apply_damage(15, ["fire"], [], "fire")
        assert result["applied"] == 7  # 15 // 2 = 7
        assert result["multiplier"] == 0.5

    def test_resistance_halves_odd(self):
        """Odd damage with resistance should floor (e.g. 5 // 2 = 2)."""
        result = apply_damage(5, ["cold"], [], "cold")
        assert result["applied"] == 2

    def test_vulnerability_doubles(self):
        """Vulnerability should double damage."""
        result = apply_damage(10, [], ["radiant"], "radiant")
        assert result["applied"] == 20
        assert result["multiplier"] == 2.0

    def test_vulnerability_beats_resistance(self):
        """If both resistant and vulnerable, vulnerability wins (double)."""
        result = apply_damage(10, ["fire"], ["fire"], "fire")
        assert result["applied"] == 20  # vulnerability wins
        assert result["multiplier"] == 2.0

    def test_case_insensitive_matching(self):
        """Damage type matching should be case-insensitive."""
        result = apply_damage(10, ["FIRE"], [], "Fire")
        assert result["applied"] == 5  # resistance matches case-insensitively

    def test_no_match_different_type(self):
        """Different damage type should pass through normally."""
        result = apply_damage(8, ["fire", "cold"], ["radiant"], "psychic")
        assert result["applied"] == 8
        assert result["multiplier"] == 1.0


class TestCalculateDamage:
    """Damage dice rolling."""

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_damage_roll_with_modifier(self, mock_parse, mock_roll):
        """Damage should include ability modifier (strength)."""
        mock_parse.return_value = DiceExpression(count=1, sides=8)
        mock_roll.return_value = _mock_roll(total=5, sides=8, formula="1d8")

        # strength=14 -> +2, roll=5 -> total=7
        result = calculate_damage("1d8", BASE_STATS)
        assert result["total"] == 7
        assert result["damage_type"] == "slashing"

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_damage_minimum_zero(self, mock_parse, mock_roll):
        """Damage should be floored at 0 (negative modifiers shouldn't go below 0)."""
        mock_parse.return_value = DiceExpression(count=1, sides=4)
        mock_roll.return_value = _mock_roll(total=1, sides=4, formula="1d4")

        # strength=3 -> -3 mod, roll=1 -> would be -2, floored to 0
        weak_stats = {"strength": 3}
        result = calculate_damage("1d4", weak_stats)
        assert result["total"] == 0

    @patch("app.rules.combat.roll")
    @patch("app.rules.combat.parse")
    def test_damage_custom_type(self, mock_parse, mock_roll):
        """Custom damage type should be reflected in the result."""
        mock_parse.return_value = DiceExpression(count=1, sides=6)
        mock_roll.return_value = _mock_roll(total=4, sides=6, formula="1d6")

        result = calculate_damage("1d6", BASE_STATS, damage_type="fire")
        assert result["damage_type"] == "fire"


# ===========================================================================
# XP tests
# ===========================================================================


class TestCalculateXP:
    """Encounter XP calculation."""

    def test_easy_returns_reasonable_values(self):
        """Easy encounter should return per_character > 0."""
        result = calculate_xp("easy", 1)
        assert result["per_character"] > 0
        assert result["difficulty"] == "easy"

    def test_medium_returns_reasonable_values(self):
        """Medium encounter should have higher XP than easy."""
        easy = calculate_xp("easy", 1)
        medium = calculate_xp("medium", 1)
        assert medium["per_character"] > easy["per_character"]

    def test_hard_returns_reasonable_values(self):
        """Hard encounter should have higher XP than medium."""
        medium = calculate_xp("medium", 1)
        hard = calculate_xp("hard", 1)
        assert hard["per_character"] > medium["per_character"]

    def test_deadly_returns_reasonable_values(self):
        """Deadly encounter should have higher XP than hard."""
        hard = calculate_xp("hard", 1)
        deadly = calculate_xp("deadly", 1)
        assert deadly["per_character"] > hard["per_character"]

    def test_party_size_scales_base_xp(self):
        """base_xp should scale with party size."""
        solo = calculate_xp("medium", 1, party_size=1)
        party = calculate_xp("medium", 1, party_size=4)
        assert party["base_xp"] == solo["base_xp"] * 4
        # per_character unchanged by party size
        assert solo["per_character"] == party["per_character"]

    def test_higher_level_gives_more_xp(self):
        """Higher level encounters should give more XP."""
        low = calculate_xp("medium", 1)
        high = calculate_xp("medium", 5)
        assert high["per_character"] > low["per_character"]

    def test_invalid_difficulty_raises_error(self):
        """Invalid difficulty string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid difficulty"):
            calculate_xp("super_deadly", 1)


class TestXPToNextLevel:
    """XP required for next level."""

    def test_level_1_to_2(self):
        """Level 1 -> 2 should require 300 XP."""
        assert xp_to_next_level(1) == 300

    def test_level_2_to_3(self):
        """Level 2 -> 3 should require 600 XP (900 - 300)."""
        assert xp_to_next_level(2) == 600

    def test_level_4_to_5(self):
        """Level 4 -> 5 should require 3800 XP (6500 - 2700)."""
        assert xp_to_next_level(4) == 3800

    def test_level_19_to_20(self):
        """Level 19 -> 20 should require 50000 XP (355000 - 305000)."""
        assert xp_to_next_level(19) == 50000

    def test_level_20_max(self):
        """Level 20 should return 0 (max level)."""
        assert xp_to_next_level(20) == 0

    def test_known_thresholds_match_table(self):
        """Verify xp_to_next_level matches XP_THRESHOLDS table."""
        for level in range(1, 20):
            expected = XP_THRESHOLDS[level + 1] - XP_THRESHOLDS[level]
            assert xp_to_next_level(level) == expected


class TestCheckLevelUp:
    """Level-up detection."""

    def test_below_threshold_no_level_up(self):
        """XP below level 2 threshold should not level up."""
        result = check_level_up(200, 1)
        assert result["leveled_up"] is False
        assert result["new_level"] == 1
        assert result["xp_remaining"] == 200

    def test_at_threshold_levels_up(self):
        """XP at exactly the level 2 threshold should level up."""
        result = check_level_up(300, 1)
        assert result["leveled_up"] is True
        assert result["new_level"] == 2
        assert result["xp_remaining"] == 0

    def test_above_threshold_levels_up(self):
        """XP above threshold should level up with remaining XP."""
        result = check_level_up(500, 1)
        assert result["leveled_up"] is True
        assert result["new_level"] == 2
        assert result["xp_remaining"] == 200

    def test_multi_level_up(self):
        """Enough XP should skip multiple levels."""
        # 900 XP at level 1 should go to level 3 (threshold: 900)
        result = check_level_up(900, 1)
        assert result["leveled_up"] is True
        assert result["new_level"] == 3
        assert result["xp_remaining"] == 0

    def test_max_level_no_level_up(self):
        """Level 20 with any XP should not level up."""
        result = check_level_up(999999, 20)
        assert result["leveled_up"] is False
        assert result["new_level"] == 20

    def test_exact_threshold_no_waste(self):
        """XP exactly at a threshold should yield 0 remaining."""
        result = check_level_up(6500, 1)
        assert result["new_level"] == 5
        assert result["xp_remaining"] == 0


# ===========================================================================
# Status effects tests
# ===========================================================================


class TestStatusEffectDataclass:
    """StatusEffect dataclass construction."""

    def test_minimal_construction(self):
        """A StatusEffect can be created with just name and duration."""
        effect = StatusEffect(name="Test", duration=3)
        assert effect.name == "Test"
        assert effect.duration == 3
        assert effect.source is None
        assert effect.description == ""
        assert effect.modifiers == {}

    def test_full_construction(self):
        """A StatusEffect with all fields should work."""
        effect = StatusEffect(
            name="Full Test",
            duration=5,
            source="Test Source",
            description="A full test effect",
            modifiers={"attack_bonus": -2},
        )
        assert effect.name == "Full Test"
        assert effect.duration == 5
        assert effect.source == "Test Source"
        assert effect.description == "A full test effect"
        assert effect.modifiers == {"attack_bonus": -2}

    def test_permanent_duration(self):
        """Duration of -1 should represent permanent."""
        effect = StatusEffect(name="Perm", duration=-1)
        assert effect.duration == -1


class TestApplyRemoveEffect:
    """Applying and removing status effects."""

    def test_apply_effect_modifies_stats(self):
        """Apply should add modifier values to stats."""
        stats = {"attack_bonus": 5, "ac": 14}
        effect = StatusEffect(
            name="Test",
            duration=1,
            modifiers={"attack_bonus": -2, "ac_bonus": -2},
        )
        modified = apply_effect(stats, effect)

        assert modified["attack_bonus"] == 3  # 5 + (-2)
        assert modified["ac_bonus"] == -2  # 0 + (-2)
        # Original should be unchanged
        assert stats["attack_bonus"] == 5

    def test_remove_effect_restores_stats(self):
        """Remove should reverse modifier values."""
        applied_stats = {"attack_bonus": 3, "ac": 14, "ac_bonus": -2}
        effect = StatusEffect(
            name="Test",
            duration=1,
            modifiers={"attack_bonus": -2, "ac_bonus": -2},
        )
        restored = remove_effect(applied_stats, effect)

        assert restored["attack_bonus"] == 5  # 3 - (-2) = 5
        assert restored["ac_bonus"] == 0  # -2 - (-2) = 0

    def test_apply_then_remove_roundtrip(self):
        """Apply then remove should return to original stats."""
        original = {"strength": 14, "dexterity": 12, "speed": 30}
        effect = StatusEffect(
            name="Slow",
            duration=3,
            modifiers={"speed": -10, "dexterity": -2},
        )

        applied = apply_effect(original, effect)
        assert applied["speed"] == 20
        assert applied["dexterity"] == 10

        restored = remove_effect(applied, effect)
        assert restored["speed"] == 30
        assert restored["dexterity"] == 12
        assert restored == original

    def test_apply_non_existent_key(self):
        """Applying a modifier for a key that doesn't exist should create it."""
        stats = {"strength": 10}
        effect = StatusEffect(name="Test", duration=1, modifiers={"speed": 20})
        modified = apply_effect(stats, effect)
        assert modified["speed"] == 20


class TestTickEffects:
    """Effect duration ticking."""

    def test_tick_decrements_duration(self):
        """Tick should reduce remaining duration by 1."""
        effects = [StatusEffect(name="Test", duration=3)]
        remaining, expired = tick_effects(effects)

        assert len(remaining) == 1
        assert len(expired) == 0
        assert remaining[0].duration == 2

    def test_tick_expires_effect(self):
        """Effect with duration 1 should expire after tick."""
        effects = [StatusEffect(name="Expiring", duration=1)]
        remaining, expired = tick_effects(effects)

        assert len(remaining) == 0
        assert len(expired) == 1
        assert expired[0].name == "Expiring"

    def test_tick_persistent_never_expires(self):
        """Permanent effect (duration=-1) should never expire or decrement."""
        effects = [StatusEffect(name="Perm", duration=-1)]
        remaining, expired = tick_effects(effects)

        assert len(remaining) == 1
        assert len(expired) == 0
        assert remaining[0].duration == -1  # unchanged

    def test_tick_multiple_effects_mixed(self):
        """Tick should handle a mix of durations correctly."""
        effects = [
            StatusEffect(name="Perm", duration=-1),
            StatusEffect(name="ThreeTurn", duration=3),
            StatusEffect(name="OneTurn", duration=1),
            StatusEffect(name="TwoTurn", duration=2),
        ]
        remaining, expired = tick_effects(effects)

        assert len(remaining) == 3  # Perm, ThreeTurn (->2), TwoTurn (->1)
        assert len(expired) == 1  # OneTurn
        expired_names = {e.name for e in expired}
        assert expired_names == {"OneTurn"}
        remaining_names = {e.name for e in remaining}
        assert remaining_names == {"Perm", "ThreeTurn", "TwoTurn"}

    def test_tick_all_expire(self):
        """All non-permanent effects with duration 1 should expire."""
        effects = [
            StatusEffect(name="A", duration=1),
            StatusEffect(name="B", duration=1),
        ]
        remaining, expired = tick_effects(effects)
        assert len(remaining) == 0
        assert len(expired) == 2

    def test_tick_empty_list(self):
        """Empty list should produce empty results."""
        remaining, expired = tick_effects([])
        assert remaining == []
        assert expired == []


class TestPredefinedConditions:
    """Pre-defined condition constants."""

    def test_blinded_exists(self):
        """BLINDED should be a StatusEffect with name 'Blinded'."""
        assert isinstance(BLINDED, StatusEffect)
        assert BLINDED.name == "Blinded"
        assert BLINDED.duration == -1

    def test_poisoned_exists(self):
        """POISONED should be a StatusEffect with name 'Poisoned'."""
        assert isinstance(POISONED, StatusEffect)
        assert POISONED.name == "Poisoned"
        assert POISONED.duration == -1

    def test_restrained_exists(self):
        """RESTRAINED should be a StatusEffect with name 'Restrained'."""
        assert isinstance(RESTRAINED, StatusEffect)
        assert RESTRAINED.name == "Restrained"
        assert RESTRAINED.duration == -1

    def test_stunned_exists(self):
        """STUNNED should be a StatusEffect with name 'Stunned'."""
        assert isinstance(STUNNED, StatusEffect)
        assert STUNNED.name == "Stunned"
        assert STUNNED.duration == -1

    def test_inspired_exists(self):
        """INSPIRED should be a StatusEffect with its own duration."""
        assert isinstance(INSPIRED, StatusEffect)
        assert INSPIRED.name == "Inspired"
        assert INSPIRED.duration == 10  # not permanent
        assert INSPIRED.source == "Bardic Inspiration"

    def test_all_conditions_have_modifiers(self):
        """All predefined conditions should have modifiers dicts."""
        for cond in [BLINDED, POISONED, RESTRAINED, STUNNED, INSPIRED]:
            assert isinstance(cond.modifiers, dict)
            assert len(cond.modifiers) > 0


# ===========================================================================
# Bug-fix regression tests
# ===========================================================================


class TestRemoveEffectBugs:
    """Regression tests for Bug 1: remove_effect corrupting stats."""

    def test_remove_unapplied_effect_does_not_create_phantom_keys(self):
        """remove_effect should NOT create keys that do not exist in stats."""
        stats = {"strength": 10}
        effect = StatusEffect(name="Test", duration=1, modifiers={"speed": 20})
        result = remove_effect(stats, effect)
        assert "speed" not in result
        assert result == {"strength": 10}

    def test_remove_effect_only_touches_existing_keys(self):
        """remove_effect should not add modifier keys that are absent from stats."""
        stats = {"attack_bonus": 10, "ac": 14}
        effect = StatusEffect(
            name="Test",
            duration=1,
            modifiers={"attack_bonus": -2, "ac_bonus": -2, "speed": 999},
        )
        result = remove_effect(stats, effect)
        # attack_bonus exists, so it gets modified: 10 - (-2) = 12
        assert result["attack_bonus"] == 12
        # ac_bonus does NOT exist, so it should NOT be created
        assert "ac_bonus" not in result
        # speed does NOT exist, so it should NOT be created
        assert "speed" not in result
        # Original untouched keys survive
        assert result["ac"] == 14


class TestXPToNextLevelBugs:
    """Regression tests for Bug 2: xp_to_next_level crashing on invalid input."""

    def test_xp_to_next_level_zero_raises_value_error(self):
        """Level 0 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid level"):
            xp_to_next_level(0)

    def test_xp_to_next_level_negative_raises_value_error(self):
        """Negative level should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid level"):
            xp_to_next_level(-1)

    def test_xp_to_next_level_negative_large_raises_value_error(self):
        """Large negative level should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid level"):
            xp_to_next_level(-999)


class TestCheckLevelUpBugs:
    """Regression tests for Bug 3 and Bug 5: level validation and negative XP."""

    def test_check_level_up_level_zero_raises_value_error(self):
        """Level 0 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid level"):
            check_level_up(100, 0)

    def test_check_level_up_level_negative_raises_value_error(self):
        """Negative level should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid level"):
            check_level_up(100, -5)

    def test_check_level_up_level_above_20_raises_value_error(self):
        """Level 21 should raise ValueError (not silently reset to 20)."""
        with pytest.raises(ValueError, match="Invalid level"):
            check_level_up(999999, 21)

    def test_check_level_up_negative_xp_treated_as_zero(self):
        """Negative XP should be treated as 0."""
        result = check_level_up(-100, 1)
        assert result["leveled_up"] is False
        assert result["new_level"] == 1
        assert result["xp_remaining"] == 0

    def test_check_level_up_large_negative_xp_treated_as_zero(self):
        """Very negative XP should be treated as 0, not crash."""
        result = check_level_up(-999999, 1)
        assert result["leveled_up"] is False
        assert result["new_level"] == 1
        assert result["xp_remaining"] == 0


class TestCalculateXPBugs:
    """Regression tests for Bug 4: calculate_xp input validation."""

    def test_calculate_xp_party_size_zero_raises_value_error(self):
        """party_size=0 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid party_size"):
            calculate_xp("easy", 1, party_size=0)

    def test_calculate_xp_party_size_negative_raises_value_error(self):
        """party_size=-1 should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid party_size"):
            calculate_xp("easy", 1, party_size=-1)

    def test_calculate_xp_float_level_raises_type_error(self):
        """Float level should raise TypeError."""
        with pytest.raises(TypeError, match="Level must be an integer"):
            calculate_xp("medium", 1.5)

    def test_calculate_xp_party_size_one_is_valid(self):
        """party_size=1 should work normally."""
        result = calculate_xp("easy", 1, party_size=1)
        assert result["per_character"] > 0
        assert result["base_xp"] > 0


class TestChecksMarginField:
    """Check that saving_throw and ability_check return margin field."""

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_saving_throw_returns_margin(self, mock_parse, mock_roll):
        """saving_throw should include a margin field (total - dc)."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=15)

        result = saving_throw(BASE_STATS, "strength", 14)
        assert "margin" in result
        # strength=14 (+2), prof=2, total=15+4=19, margin=19-14=5
        assert result["margin"] == 5

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_saving_throw_margin_negative_on_failure(self, mock_parse, mock_roll):
        """saving_throw margin should be negative when total < dc."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=5)

        result = saving_throw(BASE_STATS, "dexterity", 20)
        assert "margin" in result
        assert result["margin"] < 0

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_ability_check_returns_margin(self, mock_parse, mock_roll):
        """ability_check should include a margin field (total - dc)."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=12)

        result = ability_check(BASE_STATS, "strength", 10)
        assert "margin" in result
        # strength=14 (+2), total=12+2=14, margin=14-10=4
        assert result["margin"] == 4

    @patch("app.rules.checks.roll")
    @patch("app.rules.checks.parse")
    def test_ability_check_margin_negative_on_failure(self, mock_parse, mock_roll):
        """ability_check margin should be negative when total < dc."""
        mock_parse.return_value = DiceExpression(count=1, sides=20)
        mock_roll.return_value = _mock_roll(total=3)

        result = ability_check(BASE_STATS, "charisma", 20)
        assert "margin" in result
        assert result["margin"] < 0
