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
from app.rules.checks import SKILL_ABILITY_MAP

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
# Ability name mapping — lowercase → uppercase
# ---------------------------------------------------------------------------
_ABILITY_NAME_TO_UPPER: dict[str, str] = {
    "strength": "STR",
    "dexterity": "DEX",
    "constitution": "CON",
    "intelligence": "INT",
    "wisdom": "WIS",
    "charisma": "CHA",
}

# ---------------------------------------------------------------------------
# Class save proficiencies (D&D 5e SRD)
# ---------------------------------------------------------------------------
_CLASS_SAVE_PROFICIENCIES: dict[str, list[str]] = {
    "Fighter": ["STR", "CON"],
    "Rogue": ["DEX", "INT"],
    "Mage": ["INT", "WIS"],
    "Cleric": ["WIS", "CHA"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_skill_name(name: str) -> str:
    """Convert Title Case skill name to snake_case for SKILL_ABILITY_MAP lookup.

    Example: 'Sleight of Hand' -> 'sleight_of_hand', 'Perception' -> 'perception'
    """
    return name.lower().replace(" ", "_")


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


def prepare_embedded_data(base: dict, record: CharacterRecord) -> dict:
    """Second phase of the derivation pipeline.

    Takes output from prepare_base_data() and the CharacterRecord to compute
    skill modifiers, saving throw modifiers, and passive perception.

    Args:
        base: Output dict from prepare_base_data() with ability_modifiers,
              proficiency_bonus, etc.
        record: The source CharacterRecord

    Returns:
        dict with keys: skill_modifiers, saving_throw_modifiers, passive_perception
    """
    ability_modifiers = base["ability_modifiers"]
    proficiency_bonus = base["proficiency_bonus"]

    # Normalize trained skills for lookup (Title Case -> snake_case)
    trained_skills = {_normalize_skill_name(s) for s in record.skills}

    # --- Skill Modifiers ---
    skill_modifiers: dict[str, int] = {}
    for skill_key, ability_name in SKILL_ABILITY_MAP.items():
        upper_ability = _ABILITY_NAME_TO_UPPER[ability_name]
        modifier = ability_modifiers[upper_ability]
        if skill_key in trained_skills:
            modifier += proficiency_bonus
        skill_modifiers[skill_key] = modifier

    # --- Saving Throw Modifiers ---
    proficient_saves = _CLASS_SAVE_PROFICIENCIES.get(record.character_class, [])
    saving_throw_modifiers: dict[str, int] = {}
    for ability in STANDARD_ABILITIES:
        modifier = ability_modifiers[ability]
        if ability in proficient_saves:
            modifier += proficiency_bonus
        saving_throw_modifiers[ability] = modifier

    # --- Passive Perception ---
    passive_perception = 10 + skill_modifiers.get("perception", 0)

    return {
        "skill_modifiers": skill_modifiers,
        "saving_throw_modifiers": saving_throw_modifiers,
        "passive_perception": passive_perception,
    }
