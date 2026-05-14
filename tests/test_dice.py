"""Tests for the dice notation parser and roller."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.dice.parser import KeepMode, ParseError, parse
from app.dice.roller import roll

# ===========================================================================
# Parser tests
# ===========================================================================


class TestParseStandard:
    """Standard dice notation: ``XdY[+Z]`` and ``dY``."""

    def test_xdy_plus_z(self):
        """``2d6+3`` should parse count, sides, and positive modifier."""
        expr = parse("2d6+3")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 3
        assert expr.keep_mode == KeepMode.NONE

    def test_xdy_minus_z(self):
        """``2d6-3`` should parse count, sides, and negative modifier."""
        expr = parse("2d6-3")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == -3
        assert expr.keep_mode == KeepMode.NONE

    def test_xdy_no_modifier(self):
        """``1d20`` should parse with modifier defaulting to 0."""
        expr = parse("1d20")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.modifier == 0

    def test_shorthand_die(self):
        """``d6`` should default count to 1."""
        expr = parse("d6")
        assert expr.count == 1
        assert expr.sides == 6
        assert expr.modifier == 0

    def test_shorthand_with_modifier(self):
        """``d6+2`` should default count to 1 with a modifier."""
        expr = parse("d6+2")
        assert expr.count == 1
        assert expr.sides == 6
        assert expr.modifier == 2

    def test_large_numbers(self):
        """Large dice counts and sides should parse correctly."""
        expr = parse("100d100")
        assert expr.count == 100
        assert expr.sides == 100
        assert expr.modifier == 0


class TestParseAdvantageDisadvantage:
    """Advantage / disadvantage notation: ``d20 advantage``, ``d20 disadvantage``."""

    def test_advantage(self):
        """``d20 advantage`` should roll 2d20 keep highest 1."""
        expr = parse("d20 advantage")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_disadvantage(self):
        """``d20 disadvantage`` should roll 2d20 keep lowest 1."""
        expr = parse("d20 disadvantage")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1

    def test_advantage_with_count(self):
        """``2d20 advantage`` should work explicitly."""
        expr = parse("2d20 advantage")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_case_insensitive(self):
        """``D20 Advantage`` should parse correctly (case-insensitive)."""
        expr = parse("D20 Advantage")
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST


class TestParseKeep:
    """Keep notation: ``4d6k3``, ``2d20h1``, ``2d20l1``."""

    def test_keep_highest_k(self):
        """``4d6k3`` should roll 4d6 keep highest 3."""
        expr = parse("4d6k3")
        assert expr.count == 4
        assert expr.sides == 6
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 3

    def test_keep_highest_h(self):
        """``2d20h1`` should roll 2d20 keep highest 1."""
        expr = parse("2d20h1")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_keep_lowest_l(self):
        """``2d20l1`` should roll 2d20 keep lowest 1."""
        expr = parse("2d20l1")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1

    def test_keep_highest_uppercase_k(self):
        """``4d6K3`` (uppercase K) should keep highest."""
        expr = parse("4d6K3")
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 3

    def test_keep_highest_uppercase_h(self):
        """``2d20H1`` (uppercase H) should keep highest."""
        expr = parse("2d20H1")
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_keep_lowest_uppercase_l(self):
        """``2d20L1`` (uppercase L) should keep lowest."""
        expr = parse("2d20L1")
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1

    def test_keep_equals_count(self):
        """Keeping all dice (``4d6k4``) should be valid."""
        expr = parse("4d6k4")
        assert expr.keep_count == 4


class TestParseErrors:
    """Invalid inputs should raise ``ParseError`` with a descriptive message."""

    def test_d0_raises_error(self):
        """``d0`` should raise ParseError (zero-sided die)."""
        with pytest.raises(ParseError, match="sides"):
            parse("d0")

    def test_zero_dice_raises_error(self):
        """``0d6`` should raise ParseError."""
        with pytest.raises(ParseError):
            parse("0d6")

    def test_negative_dice_raises_error(self):
        """Negative dice count should raise ParseError."""
        with pytest.raises(ParseError):
            parse("-1d6")

    def test_keep_count_exceeds_dice(self):
        """Keep count larger than dice count should raise ParseError."""
        with pytest.raises(ParseError, match="exceed"):
            parse("2d6k3")

    def test_zero_keep_count(self):
        """Keep count of 0 should raise ParseError."""
        with pytest.raises(ParseError):
            parse("2d6k0")

    def test_invalid_string(self):
        """Gibberish should raise ParseError."""
        with pytest.raises(ParseError, match="Invalid dice notation"):
            parse("not dice at all")

    def test_empty_string(self):
        """Empty string should raise ParseError."""
        with pytest.raises(ParseError, match="non-empty"):
            parse("")

    def test_whitespace_only(self):
        """Whitespace-only string should raise ParseError."""
        with pytest.raises(ParseError):
            parse("   ")

    def test_partial_notation(self):
        """Incomplete notation like ``d`` should raise ParseError."""
        with pytest.raises(ParseError):
            parse("d")

    def test_negative_sides(self):
        """``1d-6`` is malformed and should raise ParseError."""
        with pytest.raises(ParseError):
            parse("1d-6")

    def test_missing_keep_count(self):
        """``4d6k`` should raise ParseError."""
        with pytest.raises(ParseError):
            parse("4d6k")


# ===========================================================================
# Roller tests
# ===========================================================================


class TestRollBasic:
    """Basic dice rolling: no keep rules, no modifiers."""

    def test_result_keys(self):
        """Result dict should contain total, rolls, sides, and formula."""
        result = roll(parse("1d6"))
        assert "total" in result
        assert "rolls" in result
        assert "sides" in result
        assert "formula" in result

    def test_single_die_range(self):
        """Single die result should be within 1..sides."""
        for _ in range(100):
            result = roll(parse("1d20"))
            assert 1 <= result["total"] <= 20

    def test_multiple_dice(self):
        """Multiple dice should produce the correct number of individual rolls."""
        result = roll(parse("3d6"))
        assert len(result["rolls"]) == 3

    def test_multiple_dice_total_range(self):
        """Total of 3d6 should be between 3 and 18."""
        for _ in range(100):
            result = roll(parse("3d6"))
            assert 3 <= result["total"] <= 18

    def test_sides_in_result(self):
        """Result should include the number of sides."""
        result = roll(parse("1d8"))
        assert result["sides"] == 8

    def test_formula_in_result(self):
        """Result should include the formula string."""
        result = roll(parse("2d6+3"))
        assert result["formula"] == "2d6+3"


class TestRollModifier:
    """Dice rolling with flat modifiers."""

    def test_positive_modifier(self):
        """Total should include the positive modifier."""
        for _ in range(100):
            result = roll(parse("1d6+3"))
            assert 4 <= result["total"] <= 9

    def test_negative_modifier(self):
        """Total should include the negative modifier (may go below 1)."""
        for _ in range(100):
            result = roll(parse("1d6-3"))
            # Minimum: 1-3 = -2, Maximum: 6-3 = 3
            assert -2 <= result["total"] <= 3

    def test_zero_modifier(self):
        """Total without modifier should equal the die value(s)."""
        result = roll(parse("1d20"))
        assert result["total"] == result["rolls"][0]


class TestRollAdvantageDisadvantage:
    """Advantage and disadvantage rolling."""

    def test_advantage_keeps_highest(self):
        """Advantage total should equal max of the two rolls."""
        for _ in range(50):
            result = roll(parse("d20 advantage"))
            assert len(result["rolls"]) == 2
            assert result["total"] == max(result["rolls"])
            assert 1 <= result["total"] <= 20

    def test_disadvantage_keeps_lowest(self):
        """Disadvantage total should equal min of the two rolls."""
        for _ in range(50):
            result = roll(parse("d20 disadvantage"))
            assert len(result["rolls"]) == 2
            assert result["total"] == min(result["rolls"])
            assert 1 <= result["total"] <= 20


class TestRollKeep:
    """Keep-highest and keep-lowest rolling."""

    def test_keep_highest(self):
        """``4d6k3`` total should be sum of the 3 highest rolls."""
        for _ in range(50):
            result = roll(parse("4d6k3"))
            assert len(result["rolls"]) == 4
            sorted_rolls = sorted(result["rolls"], reverse=True)
            assert result["total"] == sum(sorted_rolls[:3])
            assert 3 <= result["total"] <= 18

    def test_keep_highest_1(self):
        """``2d20h1`` total should equal max of the two rolls."""
        for _ in range(50):
            result = roll(parse("2d20h1"))
            assert len(result["rolls"]) == 2
            assert result["total"] == max(result["rolls"])

    def test_keep_lowest_1(self):
        """``2d20l1`` total should equal min of the two rolls."""
        for _ in range(50):
            result = roll(parse("2d20l1"))
            assert len(result["rolls"]) == 2
            assert result["total"] == min(result["rolls"])


class TestRollFormula:
    """Formula string in roll results."""

    def test_formula_standard(self):
        """Standard notation should produce matching formula."""
        assert roll(parse("2d6+3"))["formula"] == "2d6+3"

    def test_formula_negative_modifier(self):
        """Negative modifier should produce correct formula."""
        assert roll(parse("2d6-3"))["formula"] == "2d6-3"

    def test_formula_no_modifier(self):
        """No modifier should produce simple formula."""
        assert roll(parse("3d6"))["formula"] == "3d6"

    def test_formula_keep_highest(self):
        """Keep-highest notation should produce matching formula."""
        assert roll(parse("4d6k3"))["formula"] == "4d6k3"

    def test_formula_keep_lowest(self):
        """Keep-lowest notation should produce matching formula."""
        assert roll(parse("2d20l1"))["formula"] == "2d20l1"


class TestRollAuditTrail:
    """Every individual die value must be recorded (audit trail)."""

    def test_audit_trail_all_rolls_recorded(self):
        """All individual die values should be in the rolls list."""
        result = roll(parse("5d10"))
        assert len(result["rolls"]) == 5
        for value in result["rolls"]:
            assert 1 <= value <= 10

    def test_audit_trail_independent_of_keep(self):
        """Rolls list should contain ALL rolls even when keeping only some."""
        result = roll(parse("4d6k3"))
        assert len(result["rolls"]) == 4  # all 4 rolls recorded
        # Total should be sum of highest 3
        sorted_rolls = sorted(result["rolls"], reverse=True)
        assert result["total"] == sum(sorted_rolls[:3])

    def test_audit_trail_single_die(self):
        """Single die roll should have exactly 1 entry in rolls."""
        result = roll(parse("1d20"))
        assert len(result["rolls"]) == 1

    def test_audit_trail_advantage(self):
        """Advantage should record both rolls."""
        result = roll(parse("d20 advantage"))
        assert len(result["rolls"]) == 2


class TestRollSystemRandom:
    """Verify that ``random.SystemRandom`` is used for entropy."""

    def test_system_random_is_used(self):
        """The module-level _rng should be called for each die."""
        with patch("app.dice.roller._rng") as mock_rng:
            mock_rng.randint.return_value = 10
            result = roll(parse("2d6"))
            assert mock_rng.randint.call_count == 2
            assert result["rolls"] == [10, 10]
            assert result["total"] == 20

    def test_system_random_instance(self):
        """The _rng should be a SystemRandom instance."""
        from random import SystemRandom

        from app.dice.roller import _rng

        assert isinstance(_rng, SystemRandom)

    def test_mocked_advantage(self):
        """Mocked SystemRandom should produce predictable advantage results."""
        with patch("app.dice.roller._rng") as mock_rng:
            mock_rng.randint.side_effect = [5, 15]
            result = roll(parse("d20 advantage"))
            assert result["rolls"] == [5, 15]
            assert result["total"] == 15  # keeps highest

    def test_mocked_disadvantage(self):
        """Mocked SystemRandom should produce predictable disadvantage results."""
        with patch("app.dice.roller._rng") as mock_rng:
            mock_rng.randint.side_effect = [5, 15]
            result = roll(parse("d20 disadvantage"))
            assert result["rolls"] == [5, 15]
            assert result["total"] == 5  # keeps lowest

# ===========================================================================
# Tests for keep notation + modifier
# ===========================================================================


class TestParseKeepModifier:
    """Keep notation with modifier: ``4d6k3+2``, ``2d20h1+5``, ``2d20l1-3``."""

    def test_keep_highest_with_positive_modifier(self):
        """``4d6k3+2`` should parse with keep-highiest and positive modifier."""
        expr = parse("4d6k3+2")
        assert expr.count == 4
        assert expr.sides == 6
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 3
        assert expr.modifier == 2

    def test_keep_highest_h_with_positive_modifier(self):
        """``2d20h1+5`` should parse with keep-highest and positive modifier."""
        expr = parse("2d20h1+5")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 5

    def test_keep_lowest_with_negative_modifier(self):
        """``2d20l1-3`` should parse with keep-lowest and negative modifier."""
        expr = parse("2d20l1-3")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1
        assert expr.modifier == -3


class TestRollKeepModifier:
    """Roll test for keep notation with modifier."""

    def test_keep_highest_with_modifier_range(self):
        """``4d6k3+2`` total should be within correct range."""
        for _ in range(50):
            result = roll(parse("4d6k3+2"))
            assert len(result["rolls"]) == 4
            # Min: 3 ones + 2 = 5, Max: 3 sixes + 2 = 20
            assert 5 <= result["total"] <= 20

    def test_keep_highest_h_with_modifier(self):
        """``2d20h1+5`` total should be max of rolls + 5."""
        for _ in range(50):
            result = roll(parse("2d20h1+5"))
            assert len(result["rolls"]) == 2
            assert result["total"] == max(result["rolls"]) + 5

    def test_keep_lowest_with_modifier(self):
        """``2d20l1-3`` total should be min of rolls - 3."""
        for _ in range(50):
            result = roll(parse("2d20l1-3"))
            assert len(result["rolls"]) == 2
            assert result["total"] == min(result["rolls"]) - 3

    def test_keep_highest_with_modifier_formula(self):
        """Formula for keep notation with modifier should include it."""
        result = roll(parse("4d6k3+2"))
        assert result["formula"] == "4d6k3+2"

    def test_keep_lowest_with_modifier_formula(self):
        """Formula for keep-lowest with modifier should include it."""
        result = roll(parse("2d20l1-3"))
        assert result["formula"] == "2d20l1-3"


# ===========================================================================
# Tests for advantage/disadvantage + modifier
# ===========================================================================


class TestParseAdvantageDisadvantageModifier:
    """Advantage/disadvantage with modifier: ``d20 advantage +2``, ``d20 disadvantage -1``."""

    def test_advantage_with_positive_modifier(self):
        """``d20 advantage +2`` should parse with advantage and positive modifier."""
        expr = parse("d20 advantage +2")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 2

    def test_disadvantage_with_negative_modifier(self):
        """``d20 disadvantage -1`` should parse with disadvantage and negative modifier."""
        expr = parse("d20 disadvantage -1")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1
        assert expr.modifier == -1

    def test_advantage_with_modifier_with_count(self):
        """``2d20 advantage +3`` should parse with explicit count and modifier."""
        expr = parse("2d20 advantage +3")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 3


class TestRollAdvantageDisadvantageModifier:
    """Roll test for advantage/disadvantage with modifier."""

    def test_advantage_plus_modifier(self):
        """``d20 advantage +2`` total should be max + 2."""
        for _ in range(50):
            result = roll(parse("d20 advantage +2"))
            assert len(result["rolls"]) == 2
            assert result["total"] == max(result["rolls"]) + 2

    def test_disadvantage_minus_modifier(self):
        """``d20 disadvantage -1`` total should be min - 1."""
        for _ in range(50):
            result = roll(parse("d20 disadvantage -1"))
            assert len(result["rolls"]) == 2
            assert result["total"] == min(result["rolls"]) - 1

    def test_advantage_plus_modifier_formula(self):
        """Formula for advantage with modifier should include modifier."""
        result = roll(parse("d20 advantage +2"))
        assert result["formula"] == "2d20k1+2"

    def test_disadvantage_minus_modifier_formula(self):
        """Formula for disadvantage with modifier should include modifier."""
        result = roll(parse("d20 disadvantage -1"))
        assert result["formula"] == "2d20l1-1"


# ===========================================================================
# Tests for input validation (whitespace-only, non-string)
# ===========================================================================


class TestParseInputValidation:
    """Non-string and whitespace-only inputs should raise ParseError."""

    def test_none_input_raises_error(self):
        """``None`` should raise ParseError with type info."""
        with pytest.raises(ParseError, match="string"):
            parse(None)  # type: ignore[arg-type]

    def test_int_input_raises_error(self):
        """Integer input should raise ParseError with type info."""
        with pytest.raises(ParseError, match="string"):
            parse(42)  # type: ignore[arg-type]

    def test_whitespace_only_raises_non_empty(self):
        """Whitespace-only string should raise ParseError with non-empty message."""
        with pytest.raises(ParseError, match="non-empty"):
            parse("   ")


# ===========================================================================
# Tests for Bug 3: 1d20 advantage should use 2 dice
# ===========================================================================


class TestParseAdvantageExplicitCountOne:
    """When user writes ``1d20 advantage``, force count to 2."""

    def test_advantage_count_one_becomes_two(self):
        """``1d20 advantage`` should set count to 2 (not 1)."""
        expr = parse("1d20 advantage")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_disadvantage_count_one_becomes_two(self):
        """``1d20 disadvantage`` should set count to 2 (not 1)."""
        expr = parse("1d20 disadvantage")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1


# ===========================================================================
# Tests for Bug 5: d20h1 shorthand (no count before d)
# ===========================================================================


class TestParseKeepShorthand:
    """Shorthand keep notation: ``d20h1`` (no count before ``d``)."""

    def test_shorthand_keep_highest(self):
        """``d20h1`` should parse as 1d20 keep-highest 1."""
        expr = parse("d20h1")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_shorthand_keep_lowest(self):
        """``d20l1`` should parse as 1d20 keep-lowest 1."""
        expr = parse("d20l1")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1

    def test_shorthand_keep_highest_with_modifier(self):
        """``d20h1+5`` should parse with modifier."""
        expr = parse("d20h1+5")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 5

    def test_shorthand_keep_lowest_with_modifier(self):
        """``d20l1-3`` should parse with negative modifier."""
        expr = parse("d20l1-3")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1
        assert expr.modifier == -3


# ===========================================================================
# Tests for Bug 6: Multiple modifiers 2d6+3+2
# ===========================================================================


class TestParseMultipleModifiers:
    """Multiple cumulative modifiers: ``2d6+3+2``."""

    def test_two_positive_modifiers(self):
        """``2d6+3+2`` should sum modifiers to 5."""
        expr = parse("2d6+3+2")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 5

    def test_positive_and_negative_modifiers(self):
        """``2d6+5-2`` should sum modifiers to 3."""
        expr = parse("2d6+5-2")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 3

    def test_three_modifiers(self):
        """``2d6+1+2+3`` should sum modifiers to 6."""
        expr = parse("2d6+1+2+3")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 6

    def test_keep_with_multiple_modifiers(self):
        """``4d6k3+2+1`` should sum modifiers."""
        expr = parse("4d6k3+2+1")
        assert expr.count == 4
        assert expr.sides == 6
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 3
        assert expr.modifier == 3

    def test_advantage_with_multiple_modifiers(self):
        """``d20 advantage+1+2`` should sum modifiers."""
        expr = parse("d20 advantage+1+2")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 3


class TestRollMultipleModifiers:
    """Rolling with multiple cumulative modifiers."""

    def test_multiple_modifiers_total_range(self):
        """``2d6+3+2`` should include total modifier."""
        for _ in range(50):
            result = roll(parse("2d6+3+2"))
            # 2d6 min=2, max=12 → 2+5=7, 12+5=17
            assert 7 <= result["total"] <= 17

    def test_multiple_modifiers_formula(self):
        """Formula for multiple modifiers should show total."""
        result = roll(parse("2d6+3+2"))
        # The formula shows the cumulative modifier
        assert result["formula"] == "2d6+5"


# ===========================================================================
# Tests for Bug 7: Whitespace tolerance
# ===========================================================================


class TestParseWhitespaceTolerance:
    """Whitespace around operators and keywords."""

    def test_space_before_modifier(self):
        """``2d6 + 3`` should parse with space before modifier."""
        expr = parse("2d6 + 3")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 3

    def test_spaces_around_modifier(self):
        """``2d6 + 3`` should work with spaces."""
        expr = parse("2d6 + 3")
        assert expr.modifier == 3

    def test_advantage_with_space_before_modifier(self):
        """``d20 advantage + 2`` should parse."""
        expr = parse("d20 advantage + 2")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 2

    def test_disadvantage_with_space_before_modifier(self):
        """``d20 disadvantage - 1`` should parse."""
        expr = parse("d20 disadvantage - 1")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1
        assert expr.modifier == -1

    def test_keep_with_space_before_modifier(self):
        """``4d6k3 + 2`` should parse with space."""
        expr = parse("4d6k3 + 2")
        assert expr.count == 4
        assert expr.sides == 6
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 3
        assert expr.modifier == 2

    def test_keep_shorthand_with_space_before_modifier(self):
        """``d20h1 + 5`` should parse with space."""
        expr = parse("d20h1 + 5")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 5

    def test_keep_shorthand_with_spaces_around_modifier(self):
        """``2d20h1 - 3`` should parse with space before negative modifier."""
        expr = parse("2d20h1 - 3")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == -3

    def test_multiple_modifiers_with_spaces(self):
        """``2d6 + 3 + 2`` should parse multiple spaced modifiers."""
        expr = parse("2d6 + 3 + 2")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 5

    def test_advantage_with_spaces_and_multiple_modifiers(self):
        """``d20 advantage + 1 + 2`` should parse."""
        expr = parse("d20 advantage + 1 + 2")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 3


# ===========================================================================
# Tests for Bug 4: Roller defensive validation
# ===========================================================================


class TestRollerValidation:
    """Direct DiceExpression construction with invalid values."""

    def test_zero_sides_raises_value_error(self):
        """``DiceExpression(count=1, sides=0)`` should raise ValueError."""
        from app.dice.parser import DiceExpression
        expr = DiceExpression(count=1, sides=0)
        with pytest.raises(ValueError, match="sides"):
            roll(expr)

    def test_negative_sides_raises_value_error(self):
        """``DiceExpression(count=1, sides=-5)`` should raise ValueError."""
        from app.dice.parser import DiceExpression
        expr = DiceExpression(count=1, sides=-5)
        with pytest.raises(ValueError, match="sides"):
            roll(expr)

    def test_zero_count_raises_value_error(self):
        """``DiceExpression(count=0, sides=6)`` should raise ValueError."""
        from app.dice.parser import DiceExpression
        expr = DiceExpression(count=0, sides=6)
        with pytest.raises(ValueError, match="dice"):
            roll(expr)

    def test_keep_count_exceeds_count_raises_value_error(self):
        """``DiceExpression(count=2, sides=6, keep_count=5)`` should raise."""
        from app.dice.parser import DiceExpression, KeepMode
        expr = DiceExpression(
            count=2, sides=6, keep_mode=KeepMode.HIGHEST, keep_count=5,
        )
        with pytest.raises(ValueError, match="exceed"):
            roll(expr)

    def test_valid_expression_passes_validation(self):
        """A valid DiceExpression should roll normally."""
        from app.dice.parser import DiceExpression
        expr = DiceExpression(count=1, sides=6)
        result = roll(expr)
        assert 1 <= result["total"] <= 6
        assert len(result["rolls"]) == 1
