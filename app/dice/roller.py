"""
Dice roller engine.

**This is the CENTRAL randomness source for the entire project.**
No other module should import or call ``random`` directly — all randomness
must flow through this module so it can be controlled, audited, and tested.
"""

from __future__ import annotations

import random

from .parser import DiceExpression, KeepMode

# ---------------------------------------------------------------------------
# Randomness source — SystemRandom (cryptographic / OS entropy)
# ---------------------------------------------------------------------------

_rng = random.SystemRandom()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def roll(expression: DiceExpression) -> dict:
    """Roll dice described by a parsed ``DiceExpression``.

    Every individual die value is recorded in the ``'rolls'`` list, providing
    a full audit trail of the randomness that was generated.

    Args:
        expression: A ``DiceExpression`` returned by ``parser.parse()``.

    Returns:
        A dictionary with the following keys:

        - **total** (``int``): The final result after applying keep rules
          and any flat modifier.
        - **rolls** (``list[int]``): Every individual die value rolled, in
          the order they were generated (audit trail).
        - **sides** (``int``): The number of sides on each die.
        - **formula** (``str``): A human-readable formula string (e.g.
          ``'4d6k3'``, ``'2d6+3'``).

    Raises:
        ValueError: If the expression has invalid values (sides < 1,
            count < 1, keep_count > count).
    """
    # --- Defensive validation (Bug 4) ------------------------------------
    if expression.sides < 1:
        raise ValueError(
            f"Number of sides must be at least 1, got {expression.sides}"
        )
    if expression.count < 1:
        raise ValueError(
            f"Number of dice must be at least 1, got {expression.count}"
        )
    if expression.keep_count is not None and expression.keep_count > expression.count:
        raise ValueError(
            f"Keep count ({expression.keep_count}) cannot exceed "
            f"dice count ({expression.count})"
        )

    # --- Roll every die ----------------------------------------------------
    raw_rolls = [_rng.randint(1, expression.sides) for _ in range(expression.count)]

    # --- Apply keep / drop rules -------------------------------------------
    if expression.keep_mode == KeepMode.HIGHEST:
        kept = sorted(raw_rolls, reverse=True)[: expression.keep_count]
    elif expression.keep_mode == KeepMode.LOWEST:
        kept = sorted(raw_rolls)[: expression.keep_count]
    else:
        kept = raw_rolls

    # --- Compute total -----------------------------------------------------
    total = sum(kept) + expression.modifier

    return {
        "total": total,
        "rolls": raw_rolls,
        "sides": expression.sides,
        "formula": _build_formula(expression),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_formula(expression: DiceExpression) -> str:
    """Build a human-readable formula string from an expression."""
    parts = [f"{expression.count}d{expression.sides}"]

    if expression.keep_mode == KeepMode.HIGHEST:
        parts.append(f"k{expression.keep_count}")
    elif expression.keep_mode == KeepMode.LOWEST:
        parts.append(f"l{expression.keep_count}")

    if expression.modifier > 0:
        parts.append(f"+{expression.modifier}")
    elif expression.modifier < 0:
        parts.append(str(expression.modifier))

    return "".join(parts)
