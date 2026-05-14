"""
Dice notation parser for RPG games.

Supported notations:
  - Standard: ``XdY[+Z]`` — roll X dice of Y sides, add modifier Z
  - Shorthand: ``dY`` — single die of Y sides
  - Advantage: ``d20 advantage`` — roll 2d20, keep the highest
  - Disadvantage: ``d20 disadvantage`` — roll 2d20, keep the lowest
  - Keep highest: ``4d6k3`` or ``2d20h1`` — roll XdY, keep highest N
  - Keep lowest: ``2d20l1`` — roll XdY, keep lowest N
  - Multiple modifiers: ``2d6+3+2`` — cumulative modifiers supported
  - Whitespace tolerant: ``2d6 + 3``, ``d20 advantage + 2``
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ParseError(Exception):
    """Raised when a dice notation string cannot be parsed."""


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class KeepMode(Enum):
    """Whether (and how) to keep a subset of rolls."""

    NONE = auto()
    HIGHEST = auto()
    LOWEST = auto()


# ---------------------------------------------------------------------------
# AST Node
# ---------------------------------------------------------------------------


@dataclass
class DiceExpression:
    """AST node representing a fully parsed dice expression.

    Attributes:
        count: Number of dice to roll.
        sides: Number of sides per die.
        modifier: Flat modifier added to the total (default 0).
        keep_mode: Whether to keep only a subset of rolls.
        keep_count: How many dice to keep (only meaningful when keep_mode != NONE).
    """

    count: int
    sides: int
    modifier: int = 0
    keep_mode: KeepMode = KeepMode.NONE
    keep_count: int | None = None


# ---------------------------------------------------------------------------
# Regex patterns  (ordered most-specific first)
# ---------------------------------------------------------------------------

# Advantage / disadvantage  e.g. "d20 advantage", "2d20 disadvantage"
# Modifier group captures zero or more modifiers with optional whitespace.
# (?:\s*[+-]\s*\d+) allows spaces between operator and digits (e.g. "+ 3").
_PATTERN_ADV_DIS = re.compile(
    r"^(\d+)?d20\s+(advantage|disadvantage)"
    r"((?:\s*[+-]\s*\d+)*)\s*$",
    re.IGNORECASE,
)

# Keep notation  e.g. "4d6k3", "2d20h1", "d20h1", "2d20l1"
# Count is optional (defaults to 1). Keep count is required.
_PATTERN_KEEP = re.compile(
    r"^(\d+)?d(\d+)([kKhHlL])(\d+)"
    r"((?:\s*[+-]\s*\d+)*)\s*$",
    re.IGNORECASE,
)

# Standard notation  e.g. "2d6+3", "d20", "d6-2", "2d6+3+2"
_PATTERN_STANDARD = re.compile(
    r"^(\d+)?d(\d+)"
    r"((?:\s*[+-]\s*\d+)*)\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(notation: str) -> DiceExpression:
    """Parse a dice notation string into a ``DiceExpression``.

    Args:
        notation: Dice notation string (e.g. ``'2d6+3'``, ``'d20 advantage'``,
            ``'4d6k3'``).

    Returns:
        A ``DiceExpression`` representing the parsed expression.

    Raises:
        ParseError: If the notation is empty, invalid, or contains
            semantically invalid values (e.g. zero sides).
    """
    if not isinstance(notation, str):
        raise ParseError(f"Dice notation must be a string, got {type(notation).__name__}")

    stripped = notation.strip()
    if not stripped:
        raise ParseError("Dice notation must be a non-empty string")

    # 1. Advantage / disadvantage  (most specific)
    match = _PATTERN_ADV_DIS.match(stripped)
    if match:
        count_str, mode, modifier_str = match.groups()
        count = int(count_str) if count_str else 2
        modifier = _sum_modifiers(modifier_str)
        # Bug 3 fix: if user explicitly wrote count=1 with advantage/disadvantage,
        # treat it the same as no count (force to 2, since advantage needs 2 dice).
        if count < 2:
            count = 2
        _validate_positive(count, "Number of dice")
        if mode.lower() == "advantage":
            return DiceExpression(
                count=count, sides=20, keep_mode=KeepMode.HIGHEST, keep_count=1,
                modifier=modifier,
            )
        return DiceExpression(
            count=count, sides=20, keep_mode=KeepMode.LOWEST, keep_count=1,
            modifier=modifier,
        )

    # 2. Keep notation  (e.g. 4d6k3, 2d20h1, d20h1, 2d20l1)
    match = _PATTERN_KEEP.match(stripped)
    if match:
        count_str, sides_str, operator, keep_str, modifier_str = match.groups()
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        keep_n = int(keep_str)
        modifier = _sum_modifiers(modifier_str)

        _validate_positive(count, "Number of dice")
        _validate_positive(sides, "Number of sides")
        _validate_positive(keep_n, "Keep count")

        if keep_n > count:
            raise ParseError(
                f"Keep count ({keep_n}) cannot exceed dice count ({count})"
            )

        if operator.lower() == "l":
            return DiceExpression(
                count=count, sides=sides,
                keep_mode=KeepMode.LOWEST, keep_count=keep_n,
                modifier=modifier,
            )
        # k, K, h, H  all mean keep-highest
        return DiceExpression(
            count=count, sides=sides,
            keep_mode=KeepMode.HIGHEST, keep_count=keep_n,
            modifier=modifier,
        )

    # 3. Standard notation  (e.g. 2d6+3, d20, d6-2, 2d6+3+2)
    match = _PATTERN_STANDARD.match(stripped)
    if match:
        count_str, sides_str, modifier_str = match.groups()
        count = int(count_str) if count_str else 1
        sides = int(sides_str)
        modifier = _sum_modifiers(modifier_str)

        _validate_positive(count, "Number of dice")
        _validate_positive(sides, "Number of sides")

        return DiceExpression(count=count, sides=sides, modifier=modifier)

    # Nothing matched → invalid notation
    raise ParseError(f"Invalid dice notation: '{notation}'")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_positive(value: int, name: str) -> None:
    """Validate that *value* is strictly positive.

    Args:
        value: The numeric value to validate.
        name: Human-readable name used in the error message.

    Raises:
        ParseError: If *value* ≤ 0.
    """
    if value <= 0:
        raise ParseError(f"{name} must be positive, got {value}")


def _sum_modifiers(mod_string: str) -> int:
    """Parse and sum all modifiers from a modifier string.

    Handles strings like ``'+3+2'``, ``' + 3 - 2'``, ``' - 5'``,
    or empty strings (returns 0).

    Whitespace is stripped before parsing so that ``' + 3 - 2'``
    works as expected.

    Args:
        mod_string: Raw modifier capture group from a regex match.

    Returns:
        The sum of all modifier values.
    """
    if not mod_string or not mod_string.strip():
        return 0
    # Strip all whitespace so that e.g. " + 3 - 2" becomes "+3-2"
    compact = re.sub(r"\s+", "", mod_string)
    matches = re.findall(r"[+-]\d+", compact)
    return sum(int(m) for m in matches)
