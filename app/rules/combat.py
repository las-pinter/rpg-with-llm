"""
Combat resolution: attack rolls, damage calculation, and damage application.

All randomness flows through ``app.dice.roller.roll`` — no direct calls to
``random`` anywhere in this module.
"""

from __future__ import annotations

from app.dice.parser import parse
from app.dice.roller import roll

from .checks import _is_derived_sheet, get_ability_modifier

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def attack_roll(
    attacker_stats: dict,
    defender_ac: int,
    advantage: bool = False,
    disadvantage: bool = False,
) -> dict:
    """Roll to hit versus an armour class.

    Natural 1 always misses.  Natural 20 always hits (critical).

    If both *advantage* and *disadvantage* are ``True`` they cancel out
    (normal roll).

    Args:
        attacker_stats: Character stat dict.  Accepts either an old-style
            dict (must contain ``strength``, ``proficiency_bonus``) **or** a
            DerivedSheet-style dict (containing ``ability_modifiers`` with
            an ``"STR"`` key).
        defender_ac: Armour class of the target.
        advantage: Whether the attacker has advantage.
        disadvantage: Whether the attacker has disadvantage.

    Returns:
        A dict with:
        - **hit** (``bool``): Whether the attack lands.
        - **critical** (``bool``): ``True`` if natural 20.
        - **total** (``int``): Roll result + attack modifier.
        - **roll** (``dict``): Raw roll result from the dice roller.
        - **modifier** (``int``): Attack modifier (proficiency + strength).
    """
    # Resolve advantage / disadvantage
    if advantage and disadvantage:
        notation = "1d20"
    elif advantage:
        notation = "d20 advantage"
    elif disadvantage:
        notation = "d20 disadvantage"
    else:
        notation = "1d20"

    result = roll(parse(notation))

    # Attack modifier: proficiency + strength (default melee)
    if _is_derived_sheet(attacker_stats):
        str_mod = attacker_stats["ability_modifiers"]["STR"]
        prof = attacker_stats.get("proficiency_bonus", 0)
    else:
        prof = attacker_stats.get("proficiency_bonus", 0)
        str_mod = get_ability_modifier(attacker_stats.get("strength", 10))
    modifier = prof + str_mod

    total = result["total"] + modifier
    is_natural_20 = result["total"] == 20
    is_natural_1 = result["total"] == 1

    # Natural 20 always hits, natural 1 always misses
    hit = is_natural_20 or (not is_natural_1 and total >= defender_ac)

    return {
        "hit": hit,
        "critical": is_natural_20,
        "total": total,
        "roll": result,
        "modifier": modifier,
    }


def apply_damage(
    damage: int,
    resistances: list[str],
    vulnerabilities: list[str],
    damage_type: str,
) -> dict:
    """Apply damage resistances and vulnerabilities.

    Rules:
    - Resistance halves the damage (floor).
    - Vulnerability doubles the damage.
    - If both resistant and vulnerable, vulnerability wins (double).

    Args:
        damage: Incoming damage amount.
        resistances: Damage types the target is resistant to.
        vulnerabilities: Damage types the target is vulnerable to.
        damage_type: The type of incoming damage (e.g. ``"fire"``,
            ``"slashing"``).

    Returns:
        A dict with:
        - **applied** (``int``): Damage actually dealt after multipliers.
        - **original** (``int``): Incoming damage before multipliers.
        - **multiplier** (``float``): The multiplier applied (2.0, 1.0, 0.5).
    """
    dt_lower = damage_type.lower()
    vuln_lower = [v.lower() for v in vulnerabilities]
    res_lower = [r.lower() for r in resistances]

    # Vulnerability beats resistance
    if dt_lower in vuln_lower:
        multiplier = 2.0
        applied = damage * 2
    elif dt_lower in res_lower:
        multiplier = 0.5
        applied = damage // 2
    else:
        multiplier = 1.0
        applied = damage

    return {
        "applied": applied,
        "original": damage,
        "multiplier": multiplier,
    }


def calculate_damage(
    damage_dice: str,
    attacker_stats: dict,
    damage_type: str = "slashing",
) -> dict:
    """Roll damage dice and add the relevant ability modifier.

    The ability modifier defaults to the Strength modifier (melee).
    The total is floored at 0 (minimal damage).

    Args:
        damage_dice: Dice notation string (e.g. ``"1d8"``, ``"2d6"``).
        attacker_stats: Character stat dict.  Accepts either an old-style
            dict (must contain ``strength``) **or** a DerivedSheet-style dict
            (containing ``ability_modifiers`` with an ``"STR"`` key).
        damage_type: The type of damage dealt.

    Returns:
        A dict with:
        - **total** (``int``): Final damage (dice + modifier, min 0).
        - **roll** (``dict``): Raw roll result from the dice roller.
        - **damage_type** (``str``): The damage type.
    """
    result = roll(parse(damage_dice))

    if _is_derived_sheet(attacker_stats):
        str_mod = attacker_stats["ability_modifiers"]["STR"]
    else:
        str_mod = get_ability_modifier(attacker_stats.get("strength", 10))
    total = max(0, result["total"] + str_mod)

    return {
        "total": total,
        "roll": result,
        "damage_type": damage_type,
    }
