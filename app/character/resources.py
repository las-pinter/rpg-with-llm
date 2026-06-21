"""
Resource Data Model — HP, MANA, STAMINA, AND SUCH.

Defines the ``ResourceData`` dataclass that represents a tracked resource
(e.g. hit points, mana, stamina) with a current value, a maximum value
(supporting both raw integers and dice-formula strings for later
resolution), and recovery-formula strings for short and long rests.

Every resource is serializable to/from JSON so the Evil Wizard can save,
load, and tweak the shinies that keep heroes alive.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, fields
from typing import Any

from app.dice.parser import parse as parse_dice
from app.dice.roller import roll as roll_dice

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ResourceData
# ---------------------------------------------------------------------------


@dataclass
class ResourceData:
    """A tracked numerical resource — hit points, mana, stamina, or similar.

    Attributes:
        value: Current resource amount (default 0).
        max: Maximum resource value.  Can be a plain ``int`` or a dice
            formula string (e.g. ``"12+CON"``) that the derivation
            pipeline will resolve later.
        short_rest_recovery: Recovery formula for a short rest —
            a dice expression like ``"1d8"``, or the keyword ``"none"``
            (no recovery) or ``"full"`` (restore to maximum).
        long_rest_recovery: Recovery formula for a long rest —
            a dice expression, or ``"full"``, ``"half"``, or ``"none"``.
    """

    value: int = 0
    max: int | str = 10
    short_rest_recovery: str = "none"
    long_rest_recovery: str = "full"

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Validate resource fields at construction time.

        Raises ``ValueError`` if *value* is negative, *max* is zero or
        negative (when it is an ``int``), or if *value* exceeds *max*
        (when *max* is an ``int``).
        """
        _validate_resource(self.value, self.max)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    def current_ratio(self) -> float:
        """Return the fraction of resource remaining, capped 0.0 – 1.0.

        When *max* is a string (an unresolved dice formula), returns
        ``0.0`` as a safe fallback since the actual maximum hasn't been
        determined yet.

        Returns:
            A float between ``0.0`` and ``1.0``.
        """
        if isinstance(self.max, str):
            return 0.0
        if self.max <= 0:
            return 0.0
        ratio = self.value / self.max
        return max(0.0, min(1.0, ratio))

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    def apply_recovery(self, is_long_rest: bool) -> int:
        """Roll recovery dice and update *value*, capped at *max*.

        Args:
            is_long_rest: If ``True`` the **long_rest_recovery** formula
                is used; otherwise the **short_rest_recovery** formula.

        Returns:
            The actual amount of resource recovered (always ≥ 0).
        """
        formula = self.long_rest_recovery if is_long_rest else self.short_rest_recovery
        return self._apply_formula(formula)

    def _apply_formula(self, formula: str) -> int:
        """Resolve *formula* and apply the recovery to *value*.

        Handles the special keywords ``"full"``, ``"half"``, and
        ``"none"``, as well as dice expressions such as ``"1d8"``.

        Returns the amount actually recovered (≥ 0).  If *max* is still
        a string (not yet resolved), no recovery can be applied and
        this method returns ``0``.
        """
        # --- Can't resolve recovery when max is still a formula ----------
        if not isinstance(self.max, int):
            logger.debug("_apply_formula: max is not resolved (str), skipping recovery")
            return 0

        old_value = self.value

        # --- Special keywords --------------------------------------------
        if formula == "full":
            self.value = self.max
        elif formula == "half":
            recovered = max(1, self.max // 2)
            self.value = min(self.max, self.value + recovered)
        elif formula == "none":
            return 0
        else:
            # --- Dice formula (e.g. "1d8", "2d4+2") ----------------------
            try:
                expr = parse_dice(formula)
                result = roll_dice(expr)
                recovered = result["total"]
                self.value = min(self.max, self.value + recovered)
            except Exception as exc:
                logger.warning(
                    "Failed to parse/roll recovery formula '%s': %s", formula, exc
                )
                return 0

        # Don't let value dip below zero
        self.value = max(0, self.value)
        return self.value - old_value

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert this resource to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceData:
        """Reconstruct a ``ResourceData`` from a dictionary.

        Unknown keys in *data* are silently ignored for forward
        compatibility.

        Args:
            data: A dictionary produced by :meth:`to_dict`.

        Returns:
            A new ``ResourceData`` instance.
        """
        known_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_resource(value: int, max_val: int | str) -> None:
    """Validate resource value and max fields.

    Args:
        value: Current resource amount (must be a non-negative int).
        max_val: Maximum value — either a positive ``int`` or a non-empty
            string formula.

    Raises:
        ValueError: If any validation rule is violated.
    """
    if not isinstance(value, int):
        raise ValueError(f"Resource value must be an int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"Resource value cannot be negative, got {value}")

    if isinstance(max_val, int):
        if max_val <= 0:
            raise ValueError(f"Resource max must be positive, got {max_val}")
        if value > max_val:
            raise ValueError(f"Resource value ({value}) cannot exceed max ({max_val})")
    elif isinstance(max_val, str):
        if not max_val.strip():
            raise ValueError("Resource max string formula cannot be empty")
    else:
        raise ValueError(
            f"Resource max must be an int or a string, got {type(max_val).__name__}"
        )
