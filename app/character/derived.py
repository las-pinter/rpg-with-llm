"""
Derivation Pipeline — transforms CharacterRecord into DerivedSheet.

This module is the bridge between what the player chooses (CharacterRecord)
and what the game engine needs (DerivedSheet).  Each function in this
pipeline is a pure transformation — given the same record, you always get
the same derived values.

Current functions
-----------------
- ``prepare_base_data(record)`` — produces ability_modifiers, proficiency_bonus,
  hit_dice, and speed from a ``CharacterRecord``.
"""

from __future__ import annotations

import math

from app.character.model import STANDARD_ABILITIES, CharacterRecord

# ---------------------------------------------------------------------------
# Hit dice mapping — class name → hit die string
# ---------------------------------------------------------------------------
_HIT_DICE_MAP: dict[str, str] = {
    "Fighter": "1d10",
    "Rogue": "1d8",
    "Mage": "1d6",
    "Cleric": "1d8",
}

_DEFAULT_HIT_DICE: str = "1d8"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def prepare_base_data(record: CharacterRecord) -> dict:
    """Compute the base derived values for a character record.

    Produces the four "always-needed" fields:

    * ``ability_modifiers`` — a dict of the six D&D 5e ability modifiers
      computed via ``(score - 10) // 2``.
    * ``proficiency_bonus`` — the character's proficiency bonus using the
      formula ``ceil(level / 4) + 1``.
    * ``hit_dice`` — the class's hit die string (e.g. ``"1d10"``).
    * ``speed`` — base movement speed (30 ft).

    Parameters
    ----------
    record : CharacterRecord
        The persisted character record containing abilities, level, and class.

    Returns
    -------
    dict
        A dictionary whose keys match ``DerivedSheet`` field names so the
        caller can unpack/merge them directly.
    """
    # Ability modifiers: (score - 10) // 2 for each of the six abilities
    ability_modifiers: dict[str, int] = {}
    for abil in STANDARD_ABILITIES:
        score = record.abilities.get(abil, 10)
        ability_modifiers[abil] = (score - 10) // 2

    # Proficiency bonus: ceil(level / 4) + 1
    proficiency_bonus: int = math.ceil(record.level / 4) + 1

    # Hit dice based on class
    hit_dice: str = _HIT_DICE_MAP.get(record.character_class, _DEFAULT_HIT_DICE)

    # Base speed (30 ft for all standard races)
    speed: int = 30

    return {
        "ability_modifiers": ability_modifiers,
        "proficiency_bonus": proficiency_bonus,
        "hit_dice": hit_dice,
        "speed": speed,
    }
