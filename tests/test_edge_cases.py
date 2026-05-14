"""
Frettnik's Paranoid Edge Case Tests for the Dice Module.
Trust nothing. Test everything.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.dice.parser import DiceExpression, KeepMode, ParseError, parse
from app.dice.roller import _build_formula, roll


class TestParserExtremeNumbers:
    """What if someone feeds absurdly large numbers?"""

    def test_absurdly_large_numbers(self):
        """999999d999999 should parse (Python can handle big ints)."""
        expr = parse("999999d999999")
        assert expr.count == 999999
        assert expr.sides == 999999
        assert expr.modifier == 0

    def test_max_int_sides(self):
        """d2147483647 should parse (max int32 sides)."""
        expr = parse("d2147483647")
        assert expr.sides == 2147483647
        assert expr.count == 1

    def test_extremely_large_count(self):
        """1000000d1 should parse (big count, d1 so manageable)."""
        expr = parse("1000000d1")
        assert expr.count == 1000000
        assert expr.sides == 1

    def test_very_large_modifier(self):
        """1d6+999999 should parse with large modifier."""
        expr = parse("1d6+999999")
        assert expr.modifier == 999999

    def test_very_large_negative_modifier(self):
        """1d6-999999 should parse with large negative modifier."""
        expr = parse("1d6-999999")
        assert expr.modifier == -999999


class TestParserMultipleModifiers:
    """What about notation with multiple modifiers? -- NOW SUPPORTED."""

    def test_two_positive_modifiers_accepted(self):
        """2d6+3+2 should parse and sum modifiers to 5."""
        expr = parse("2d6+3+2")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 5

    def test_positive_and_negative_modifiers_accepted(self):
        """2d6+3-2 should parse and sum modifiers to 1."""
        expr = parse("2d6+3-2")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 1

    def test_keep_with_two_modifiers_accepted(self):
        """4d6k3+2+1 should parse and sum modifiers."""
        expr = parse("4d6k3+2+1")
        assert expr.count == 4
        assert expr.sides == 6
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 3
        assert expr.modifier == 3

    def test_advantage_with_two_modifiers_accepted(self):
        """d20 advantage +2+1 should parse and sum modifiers."""
        expr = parse("d20 advantage +2+1")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1
        assert expr.modifier == 3


class TestParserWhitespace:
    """Whitespace tolerance in dice notation -- NOW SUPPORTED."""

    def test_spaces_before_modifier_accepted(self):
        """2d6 + 3 should parse (whitespace around modifier)."""
        expr = parse("2d6 + 3")
        assert expr.count == 2
        assert expr.sides == 6
        assert expr.modifier == 3

    def test_trailing_spaces_stripped(self):
        """2d6+3   should be stripped and OK."""
        expr = parse("2d6+3  ")
        assert expr.count == 2
        assert expr.modifier == 3

    def test_leading_spaces_stripped(self):
        """2d6 should be stripped and parsed OK."""
        expr = parse("  2d6")
        assert expr.count == 2
        assert expr.sides == 6

    def test_tabs_accepted_as_whitespace(self):
        """d20\tadvantage should parse (tab is whitespace)."""
        expr = parse("d20\tadvantage")
        assert expr.count == 2
        assert expr.keep_mode == KeepMode.HIGHEST

    def test_no_space_before_advantage_rejected(self):
        """d20advantage should raise ParseError."""
        with pytest.raises(ParseError):
            parse("d20advantage")

    def test_advantage_no_space_before_modifier(self):
        """d20 advantage+2 should parse."""
        expr = parse("d20 advantage+2")
        assert expr.modifier == 2
        assert expr.keep_mode == KeepMode.HIGHEST

    def test_advantage_space_in_modifier_accepted(self):
        """d20 advantage + 2 should parse (whitespace between + and 2)."""
        expr = parse("d20 advantage + 2")
        assert expr.count == 2
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.modifier == 2


class TestParserNonNumeric:
    """Completely invalid inputs."""

    def test_unicode_dice(self):
        """d6🎲 should raise ParseError."""
        with pytest.raises(ParseError):
            parse("d6🎲")

    def test_alpha_only(self):
        """abc should raise ParseError."""
        with pytest.raises(ParseError):
            parse("abc")

    def test_alpha_dash(self):
        """abc-def should raise ParseError."""
        with pytest.raises(ParseError):
            parse("abc-def")

    def test_float_dice(self):
        """2.5d6 should raise ParseError."""
        with pytest.raises(ParseError):
            parse("2.5d6")

    def test_float_sides(self):
        """d6.5 should raise ParseError."""
        with pytest.raises(ParseError):
            parse("d6.5")

    def test_float_modifier(self):
        """2d6+3.5 should raise ParseError."""
        with pytest.raises(ParseError):
            parse("2d6+3.5")


class TestParserEdgeCases:
    """Other edge cases in the parser."""

    def test_advantage_on_d6_rejected(self):
        """d6 advantage should raise ParseError (non-d20)."""
        with pytest.raises(ParseError):
            parse("d6 advantage")

    def test_advantage_on_d1_rejected(self):
        """d1 advantage should raise ParseError (non-d20)."""
        with pytest.raises(ParseError):
            parse("d1 advantage")

    def test_shorthand_keep_accepted(self):
        """d20h1 should parse (no count defaults to 1)."""
        expr = parse("d20h1")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_shorthand_keep_lowest_accepted(self):
        """d20l1 should parse (no count defaults to 1)."""
        expr = parse("d20l1")
        assert expr.count == 1
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.LOWEST
        assert expr.keep_count == 1

    def test_percentile_dice_rejected(self):
        """d% should raise ParseError."""
        with pytest.raises(ParseError):
            parse("d%")

    def test_weird_modifier_chain_rejected(self):
        """2d6+-3 should raise ParseError."""
        with pytest.raises(ParseError):
            parse("2d6+-3")

    def test_case_variations_advantage(self):
        """All case variants of advantage should parse."""
        for variant in ["ADVANTAGE", "Advantage", "advantage"]:
            expr = parse(f"d20 {variant}")
            assert expr.keep_mode == KeepMode.HIGHEST, f"Failed for {variant}"

    def test_case_variations_disadvantage(self):
        """All case variants of disadvantage should parse."""
        for variant in ["DISADVANTAGE", "Disadvantage", "disadvantage"]:
            expr = parse(f"d20 {variant}")
            assert expr.keep_mode == KeepMode.LOWEST, f"Failed for {variant}"

    def test_d1_is_valid(self):
        """'d1' should parse — a 1-sided die."""
        expr = parse("d1")
        assert expr.count == 1
        assert expr.sides == 1

    def test_keep_all_dice(self):
        """4d6k4 (keep all) should be valid."""
        expr = parse("4d6k4")
        assert expr.keep_count == 4
        assert expr.count == 4

    def test_keep_equals_count_with_lowest(self):
        """4d6l4 (keep all lowest) should be valid."""
        expr = parse("4d6l4")
        assert expr.keep_count == 4
        assert expr.keep_mode == KeepMode.LOWEST

    def test_advantage_with_explicit_count_one(self):
        """1d20 advantage should force count to 2 (advantage needs 2 dice)."""
        expr = parse("1d20 advantage")
        assert expr.count == 2  # force to 2
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 1

    def test_advantage_with_zero_count_becomes_two(self):
        """0d20 advantage should be treated as 2 (advantage needs 2 dice)."""
        expr = parse("0d20 advantage")
        assert expr.count == 2
        assert expr.keep_mode == KeepMode.HIGHEST

    def test_uppercase_d_standard(self):
        """1D20 should parse (uppercase D)."""
        expr = parse("1D20")
        assert expr.count == 1
        assert expr.sides == 20

    def test_uppercase_d_adv(self):
        """D20 advantage should parse (uppercase D)."""
        expr = parse("D20 advantage")
        assert expr.sides == 20
        assert expr.keep_mode == KeepMode.HIGHEST

    def test_uppercase_d_keep(self):
        """4D6K3 should parse (uppercase D and K)."""
        expr = parse("4D6K3")
        assert expr.count == 4
        assert expr.sides == 6
        assert expr.keep_mode == KeepMode.HIGHEST
        assert expr.keep_count == 3


class TestRollerEdgeCases:
    """Edge cases for the dice roller."""

    def test_d1_always_rolls_1(self):
        """A 1-sided die always rolls 1."""
        for _ in range(100):
            result = roll(parse("d1"))
            assert result["total"] == 1
            assert result["rolls"] == [1]

    def test_100d1_all_ones(self):
        """100d1 should produce 100 ones."""
        result = roll(parse("100d1"))
        assert result["total"] == 100
        assert result["rolls"] == [1] * 100

    def test_advantage_formula(self):
        """d20 advantage formula should be normalized to 2d20k1."""
        result = roll(parse("d20 advantage"))
        assert result["formula"] == "2d20k1"

    def test_disadvantage_formula(self):
        """d20 disadvantage formula should be normalized to 2d20l1."""
        result = roll(parse("d20 disadvantage"))
        assert result["formula"] == "2d20l1"

    def test_audit_trail_advantage_matches_total(self):
        """Total should equal max of rolls for advantage."""
        for _ in range(50):
            result = roll(parse("d20 advantage"))
            assert result["total"] == max(result["rolls"])

    def test_audit_trail_disadvantage_matches_total(self):
        """Total should equal min of rolls for disadvantage."""
        for _ in range(50):
            result = roll(parse("d20 disadvantage"))
            assert result["total"] == min(result["rolls"])

    def test_audit_trail_keep_highest_matches_total(self):
        """Total = sum(highest 3) for 4d6k3."""
        for _ in range(50):
            result = roll(parse("4d6k3"))
            sorted_rolls = sorted(result["rolls"], reverse=True)
            expected = sum(sorted_rolls[:3])
            assert result["total"] == expected

    def test_negative_modifier_can_produce_negative_total(self):
        """1d6-10 can go negative."""
        for _ in range(100):
            result = roll(parse("1d6-10"))
            assert -9 <= result["total"] <= -4

    def test_large_modifier_big_int(self):
        """1d6+9999999999 should use Python big ints."""
        with patch("app.dice.roller._rng") as mock_rng:
            mock_rng.randint.return_value = 5
            result = roll(parse("1d6+9999999999"))
            assert result["total"] == 5 + 9999999999

    def test_keep_ten_from_four_raises(self):
        """4d6k10 should raise ParseError."""
        with pytest.raises(ParseError, match="exceed"):
            parse("4d6k10")


class TestRollerDirectConstruction:
    """Roller behavior when DiceExpression bypasses parser."""

    def test_zero_sides_raises_value_error(self):
        """sides=0 raises ValueError with descriptive message."""
        expr = DiceExpression(count=1, sides=0)
        with pytest.raises(ValueError, match="sides"):
            roll(expr)

    def test_negative_sides_raises_value_error(self):
        """sides=-5 raises ValueError with descriptive message."""
        expr = DiceExpression(count=1, sides=-5)
        with pytest.raises(ValueError, match="sides"):
            roll(expr)

    def test_zero_count_raises_value_error(self):
        """count=0 raises ValueError (must be at least 1)."""
        expr = DiceExpression(count=0, sides=6, modifier=5)
        with pytest.raises(ValueError, match="dice"):
            roll(expr)

    def test_negative_count_raises_value_error(self):
        """count=-3 raises ValueError (must be at least 1)."""
        expr = DiceExpression(count=-3, sides=6)
        with pytest.raises(ValueError, match="dice"):
            roll(expr)

    def test_none_keep_count_with_high_keep_mode(self):
        """HIGHEST with keep_count=None keeps ALL (Python slice [:None])."""
        expr = DiceExpression(
            count=4,
            sides=6,
            keep_mode=KeepMode.HIGHEST,
            keep_count=None,
        )
        result = roll(expr)
        assert len(result["rolls"]) == 4
        assert result["total"] == sum(result["rolls"])


class TestTableEntryValidation:
    """Tables should validate entry structure on load, not crash on lookup."""

    def test_entry_missing_range_raises_on_load(self, tmp_path):
        """Entry lacking 'range' raises ValueError on load."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [{"result": "no range!"}],
                }
            ),
            encoding="utf-8",
        )
        from app.dice.tables import RandomTable

        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="missing.*'range'"):
            rt.load_table("bad")

    def test_entry_missing_result_raises_on_load(self, tmp_path):
        """Entry lacking 'result' raises ValueError on load."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [{"range": [1, 6]}],
                }
            ),
            encoding="utf-8",
        )
        from app.dice.tables import RandomTable

        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="missing.*'result'"):
            rt.load_table("bad")

    def test_reversed_range_raises_on_load(self, tmp_path):
        """Range [3, 1] raises ValueError on load (reversed)."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": [3, 1], "result": "reversed!"},
                        {"range": [1, 6], "result": "normal"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        from app.dice.tables import RandomTable

        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="reversed"):
            rt.load_table("bad")

    def test_overlapping_ranges_first_wins(self, tmp_path):
        """When ranges overlap, the first matching entry wins."""
        table_file = tmp_path / "priority.json"
        table_file.write_text(
            json.dumps(
                {
                    "name": "priority",
                    "die": "1d6",
                    "entries": [
                        {"range": [1, 6], "result": "first"},
                        {"range": [1, 6], "result": "second"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        from app.dice.tables import RandomTable

        rt = RandomTable(tmp_path)
        for _ in range(100):
            result = rt.lookup("priority")
            assert result["result"] == "first"

    def test_gap_in_ranges_raises(self, tmp_path):
        """If no range matches the roll, ValueError is raised."""
        gap_file = tmp_path / "gap.json"
        gap_file.write_text(
            json.dumps(
                {
                    "name": "gap",
                    "die": "1d10",
                    "entries": [
                        {"range": [1, 3], "result": "low"},
                        {"range": [7, 10], "result": "high"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        from app.dice.tables import RandomTable

        rt = RandomTable(tmp_path)
        with patch("app.dice.tables.roll") as mock_roll:
            mock_roll.return_value = {
                "total": 5,
                "rolls": [5],
                "sides": 10,
                "formula": "1d10",
            }
            with pytest.raises(ValueError, match="did not match"):
                rt.lookup("gap")

    def test_range_not_a_list_raises_on_load(self, tmp_path):
        """Range set to a string raises ValueError on load."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [{"range": "1-6", "result": "string range!"}],
                }
            ),
            encoding="utf-8",
        )
        from app.dice.tables import RandomTable

        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="range"):
            rt.load_table("bad")

    def test_invalid_die_expression_crashes(self, tmp_path):
        """Table with invalid 'die' raises ParseError on lookup."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "not a valid die",
                    "entries": [{"range": [1, 6], "result": "oops"}],
                }
            ),
            encoding="utf-8",
        )
        from app.dice.parser import ParseError
        from app.dice.tables import RandomTable

        rt = RandomTable(tmp_path)
        with pytest.raises(ParseError):
            rt.lookup("bad")


class TestTableDeepNesting:
    """Deeply nested table references."""

    def test_deep_nesting_within_limits(self, tmp_path):
        """Valid nesting at depth 5 should work (well under max_depth=10)."""
        from app.dice.tables import RandomTable

        for i in range(6):
            next_table = f"table_{i + 1}" if i < 5 else None
            entry = {"range": [1, 6], "result": f"level_{i}"}
            if next_table:
                entry["table"] = next_table
            table_data = {"name": f"table_{i}", "die": "1d6", "entries": [entry]}
            (tmp_path / f"table_{i}.json").write_text(
                json.dumps(table_data), encoding="utf-8"
            )
        rt = RandomTable(tmp_path)
        result = rt.lookup("table_0")
        assert result["result"] == "level_0"
        assert len(result["sub_rolls"]) == 1
        sub = result["sub_rolls"][0]
        assert sub["result"] == "level_1"
        assert len(sub["sub_rolls"]) == 1

    def test_nesting_at_max_depth_raises(self, tmp_path):
        """Nesting deeper than max_depth=10 should raise ValueError."""
        from app.dice.tables import RandomTable

        # Create tables 0 through 12, each pointing to the next.
        # lookup(0) at depth=0, lookup(1) at depth=1, ..., lookup(10) at depth=10
        # Then lookup(11) at depth=11 -> 11 > 10? YES -> raises
        n = 12
        for i in range(n):
            next_table = f"deep_{i + 1}" if i < n - 1 else None
            entry = {"range": [1, 6], "result": f"level_{i}"}
            if next_table:
                entry["table"] = next_table
            table_data = {"name": f"deep_{i}", "die": "1d6", "entries": [entry]}
            (tmp_path / f"deep_{i}.json").write_text(
                json.dumps(table_data), encoding="utf-8"
            )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="recursion depth"):
            rt.lookup("deep_0")


class TestFormulaBuilder:
    """Verify _build_formula produces correct strings."""

    def test_advantage_no_modifier(self):
        """d20 advantage -> '2d20k1'."""
        expr = parse("d20 advantage")
        assert _build_formula(expr) == "2d20k1"

    def test_disadvantage_no_modifier(self):
        """d20 disadvantage -> '2d20l1'."""
        expr = parse("d20 disadvantage")
        assert _build_formula(expr) == "2d20l1"

    def test_advantage_with_modifier(self):
        """d20 advantage +2 -> '2d20k1+2'."""
        expr = parse("d20 advantage +2")
        assert _build_formula(expr) == "2d20k1+2"

    def test_disadvantage_with_modifier(self):
        """d20 disadvantage -1 -> '2d20l1-1'."""
        expr = parse("d20 disadvantage -1")
        assert _build_formula(expr) == "2d20l1-1"

    def test_keep_highest_no_modifier(self):
        """4d6k3 -> '4d6k3'."""
        expr = parse("4d6k3")
        assert _build_formula(expr) == "4d6k3"

    def test_keep_lowest_no_modifier(self):
        """2d20l1 -> '2d20l1'."""
        expr = parse("2d20l1")
        assert _build_formula(expr) == "2d20l1"

    def test_standard_die(self):
        """1d20 -> '1d20'."""
        expr = parse("1d20")
        assert _build_formula(expr) == "1d20"

    def test_zero_modifier_omitted(self):
        """modifier=0 should not appear in formula."""
        expr = DiceExpression(count=1, sides=20, modifier=0)
        assert _build_formula(expr) == "1d20"
