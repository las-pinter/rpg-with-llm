"""
Status effects, conditions, and effect lifecycle management.

Provides a ``StatusEffect`` dataclass for modelling temporary conditions,
pre-defined condition constants, and helpers for applying/removing/ticking
effects.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Core dataclass
# ---------------------------------------------------------------------------


@dataclass
class StatusEffect:
    """A status effect that modifies a character's stats for a duration.

    Attributes:
        name: Human-readable name (e.g. ``"Poisoned"``).
        duration: Duration in turns. ``-1`` means permanent/until cured.
        source: Optional identifier for what caused the effect.
        description: Flavour text or mechanical description.
        modifiers: Stat adjustments keyed by stat name
            (e.g. ``{"attack_bonus": -2, "ac_bonus": -2}``).
    """

    name: str
    duration: int
    source: str | None = None
    description: str = ""
    modifiers: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pre-defined conditions (D&D 5e standard)
# ---------------------------------------------------------------------------

BLINDED = StatusEffect(
    name="Blinded",
    duration=-1,
    description=(
        "A blinded creature can't see and automatically fails any ability "
        "check that requires sight. Attack rolls against the creature have "
        "advantage, and the creature's attack rolls have disadvantage."
    ),
    modifiers={
        "attack_disadvantage": True,
        "defender_attack_advantage": True,
    },
)

POISONED = StatusEffect(
    name="Poisoned",
    duration=-1,
    description=(
        "A poisoned creature has disadvantage on attack rolls and ability checks."
    ),
    modifiers={
        "attack_disadvantage": True,
        "ability_check_disadvantage": True,
    },
)

RESTRAINED = StatusEffect(
    name="Restrained",
    duration=-1,
    description=(
        "A restrained creature's speed becomes 0, attack rolls against it "
        "have advantage, and it has disadvantage on Dexterity saving throws."
    ),
    modifiers={
        "defender_attack_advantage": True,
        "dexterity_save_disadvantage": True,
        "speed": 0,
    },
)

STUNNED = StatusEffect(
    name="Stunned",
    duration=-1,
    description=(
        "A stunned creature can't move or act. Attack rolls against it have "
        "advantage. Strength and Dexterity saving throws automatically fail."
    ),
    modifiers={
        "incapacitated": True,
        "defender_attack_advantage": True,
        "strength_save_auto_fail": True,
        "dexterity_save_auto_fail": True,
    },
)

INSPIRED = StatusEffect(
    name="Inspired",
    duration=10,  # 10 minutes in combat ~ 10 rounds
    source="Bardic Inspiration",
    description=(
        "Once within the duration, the creature can roll a d4 and add it "
        "to one attack roll, ability check, or saving throw."
    ),
    modifiers={
        "inspiration_d4": True,
    },
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_effect(stats: dict, effect: StatusEffect) -> dict:
    """Apply a status effect's modifiers to a stat dictionary.

    Each modifier key/value is added to the corresponding stat entry.
    Returns a **copy** of the stats dict -- the original is not mutated.

    Args:
        stats: Character stat dictionary.
        effect: The status effect to apply.

    Returns:
        A new stat dict with the effect's modifiers applied.
    """
    modified = deepcopy(stats)
    for key, value in effect.modifiers.items():
        modified[key] = modified.get(key, 0) + value
    return modified


def remove_effect(stats: dict, effect: StatusEffect) -> dict:
    """Remove a status effect's modifiers from a stat dictionary.

    Reverses the modifier values (adds the negated modifier).
    Returns a **copy** of the stats dict.

    Args:
        stats: Character stat dictionary (with the effect currently applied).
        effect: The status effect to remove.

    Returns:
        A new stat dict with the effect's modifiers reversed.
    """
    modified = deepcopy(stats)
    for key, value in effect.modifiers.items():
        # Only modify keys that already exist in the stat dict.
        # This prevents creating phantom entries when the effect was
        # never actually applied to these stats.
        if key in modified:
            modified[key] = modified[key] - value
    return modified


def tick_effects(
    effects: list[StatusEffect],
) -> tuple[list[StatusEffect], list[StatusEffect]]:
    """Decrement the duration of all active effects by one turn.

    Effects with ``duration == -1`` (permanent) are never removed.
    Effects whose duration reaches 0 after ticking are returned as expired.

    Args:
        effects: List of currently active status effects.

    Returns:
        A tuple of ``(remaining_effects, expired_effects)``.
    """
    remaining: list[StatusEffect] = []
    expired: list[StatusEffect] = []

    for effect in effects:
        if effect.duration == -1:
            # Permanent -- never expires
            remaining.append(effect)
        elif effect.duration > 1:
            # Still active -- decrement duration
            remaining.append(
                StatusEffect(
                    name=effect.name,
                    duration=effect.duration - 1,
                    source=effect.source,
                    description=effect.description,
                    modifiers=effect.modifiers,
                )
            )
        else:
            # Duration was 1 -- this tick consumes it
            expired.append(effect)

    return remaining, expired
