"""
Skill checks, saving throws, and ability checks for the RPG engine.

All randomness flows through ``app.dice.roller.roll`` — no direct calls to
``random`` anywhere in this module.
"""

from __future__ import annotations

import logging

from app.dice.parser import parse
from app.dice.roller import roll

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DerivedSheet detection
# ---------------------------------------------------------------------------


def _is_derived_sheet(stats: dict) -> bool:
    """Check whether *stats* is a DerivedSheet-style dict (new format).

    A DerivedSheet-style dict contains an ``"ability_modifiers"`` key.
    Old-style stat dicts do not have this key.
    """
    return isinstance(stats, dict) and "ability_modifiers" in stats


# Ability name → abbreviation mapping for DerivedSheet lookups
# DerivedSheet.ability_modifiers uses UPPERCASE abbreviated keys ("STR", "DEX")
ABILITY_NAME_TO_ABBR: dict[str, str] = {
    "strength": "STR",
    "dexterity": "DEX",
    "constitution": "CON",
    "intelligence": "INT",
    "wisdom": "WIS",
    "charisma": "CHA",
}

# ---------------------------------------------------------------------------
# Skill-to-ability mapping (D&D 5e standard)
# ---------------------------------------------------------------------------

SKILL_ABILITY_MAP: dict[str, str] = {
    "acrobatics": "dexterity",
    "animal_handling": "wisdom",
    "arcana": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "history": "intelligence",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "religion": "intelligence",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_ability_modifier(score: int) -> int:
    """Return the D&D 5e ability modifier for a given ability score.

    Formula: ``(score - 10) // 2``

    Args:
        score: Ability score (typically 1–30).

    Returns:
        The ability modifier (e.g. 14 → +2, 8 → -1).
    """
    return (score - 10) // 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def skill_check(
    stats: dict,
    skill: str,
    dc: int,
    ability: str | None = None,
) -> dict:
    """Roll a skill check: 1d20 + ability modifier + proficiency (if trained).

    Args:
        stats: Character stat dictionary.  Accepts either an old-style dict
            (containing ability scores, ``proficiency_bonus``, and ``skills``)
            **or** a DerivedSheet-style dict (containing ``skill_modifiers``).
        skill: Skill name (e.g. ``"perception"``, ``"stealth"``).
        dc: Difficulty class (target number).
        ability: Ability to use. If ``None``, inferred from
            :data:`SKILL_ABILITY_MAP` (old-style only — ignored when
            ``stats`` is a DerivedSheet-style dict).

    Returns:
        A dict with:
        - **success** (``bool``): Whether total >= DC.
        - **total** (``int``): Roll result + modifier.
        - **roll** (``dict``): Raw roll result from the dice roller.
        - **modifier** (``int``): Total modifier applied.
        - **margin** (``int``): ``total - dc`` (negative means failure).
    """
    if _is_derived_sheet(stats):
        modifier = stats["skill_modifiers"][skill]
        logger.debug(
            "checks.skill_check(derived): skill=%s dc=%d mod=%d",
            skill,
            dc,
            modifier,
        )
    else:
        if ability is None:
            ability = SKILL_ABILITY_MAP.get(skill, "intelligence")

        ability_mod = get_ability_modifier(stats.get(ability, 10))
        trained = stats.get("skills", {}).get(skill, False)
        prof = stats.get("proficiency_bonus", 0) if trained else 0
        modifier = ability_mod + prof

        logger.debug(
            "checks.skill_check:"
            " skill=%s ability=%s dc=%d mod=%d (prof=%d, trained=%s)",
            skill,
            ability,
            dc,
            modifier,
            prof,
            trained,
        )

    result = roll(parse("1d20"))
    total = result["total"] + modifier

    logger.debug(
        "checks.skill_check: → total=%d success=%s margin=%d",
        total,
        total >= dc,
        total - dc,
    )

    return {
        "success": total >= dc,
        "total": total,
        "roll": result,
        "modifier": modifier,
        "margin": total - dc,
    }


def saving_throw(stats: dict, ability: str, dc: int) -> dict:
    """Roll a saving throw: 1d20 + ability modifier + proficiency (if proficient).

    Args:
        stats: Character stat dictionary.  Accepts either an old-style dict
            (containing ability scores, ``proficiency_bonus``, and
            ``saving_throws``) **or** a DerivedSheet-style dict (containing
            ``saving_throw_modifiers``).
        ability: Ability name (e.g. ``"strength"``, ``"dexterity"``).
        dc: Difficulty class (target number).

    Returns:
        A dict with:
        - **success** (``bool``): Whether total >= DC.
        - **total** (``int``): Roll result + modifier.
        - **roll** (``dict``): Raw roll result from the dice roller.
        - **modifier** (``int``): Total modifier applied.
        - **margin** (``int``): ``total - dc`` (negative means failure).
    """
    if _is_derived_sheet(stats):
        modifier = stats["saving_throw_modifiers"][ability]
        logger.debug(
            "checks.saving_throw(derived): ability=%s dc=%d mod=%d",
            ability,
            dc,
            modifier,
        )
    else:
        ability_mod = get_ability_modifier(stats.get(ability, 10))
        proficient = stats.get("saving_throws", {}).get(ability, False)
        prof = stats.get("proficiency_bonus", 0) if proficient else 0
        modifier = ability_mod + prof

        logger.debug(
            "checks.saving_throw: ability=%s dc=%d mod=%d (proficient=%s)",
            ability,
            dc,
            modifier,
            proficient,
        )

    result = roll(parse("1d20"))
    total = result["total"] + modifier

    logger.debug(
        "checks.saving_throw: → total=%d success=%s margin=%d",
        total,
        total >= dc,
        total - dc,
    )

    return {
        "success": total >= dc,
        "total": total,
        "roll": result,
        "modifier": modifier,
        "margin": total - dc,
    }


def ability_check(stats: dict, ability: str, dc: int) -> dict:
    """Roll a pure ability check (no proficiency): 1d20 + ability modifier.

    Args:
        stats: Character stat dictionary.  Accepts either an old-style dict
            (containing ability scores) **or** a DerivedSheet-style dict
            (containing ``ability_modifiers`` with **uppercase** keys).
        ability: Ability name (e.g. ``"strength"``, ``"charisma"``).
        dc: Difficulty class (target number).

    Returns:
        A dict with:
        - **success** (``bool``): Whether total >= DC.
        - **total** (``int``): Roll result + modifier.
        - **roll** (``dict``): Raw roll result from the dice roller.
        - **modifier** (``int``): Ability modifier applied.
        - **margin** (``int``): ``total - dc`` (negative means failure).
    """
    if _is_derived_sheet(stats):
        # DerivedSheet uses UPPERCASE abbreviated keys (e.g. "STR", "DEX")
        abbr = ABILITY_NAME_TO_ABBR.get(ability, ability.upper()[:3])
        modifier = stats["ability_modifiers"][abbr]
    else:
        modifier = get_ability_modifier(stats.get(ability, 10))

    logger.debug("checks.ability_check: ability=%s dc=%d mod=%d", ability, dc, modifier)

    result = roll(parse("1d20"))
    total = result["total"] + modifier

    logger.debug(
        "checks.ability_check: → total=%d success=%s margin=%d",
        total,
        total >= dc,
        total - dc,
    )

    return {
        "success": total >= dc,
        "total": total,
        "roll": result,
        "modifier": modifier,
        "margin": total - dc,
    }
