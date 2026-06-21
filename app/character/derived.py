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
- ``prepare_embedded_data(base, record)`` — produces skill_modifiers,
  saving_throw_modifiers, and passive_perception.
- ``prepare_derived_data(embedded, base, record)`` — produces ac, initiative,
  encumbrance, attack_bonus, and formulas.
- ``compute_derived_sheet(record)`` — orchestrator that runs all three phases
  and returns a fully populated ``DerivedSheet``.
"""

from __future__ import annotations

import math

from app.character.model import STANDARD_ABILITIES, CharacterRecord, DerivedSheet
from app.character.resources import ResourceData
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


# ---------------------------------------------------------------------------
# ResourceData max formula resolution
# ---------------------------------------------------------------------------


def _resolve_resource_max(
    resource: ResourceData, ability_modifiers: dict[str, int]
) -> tuple[int, str]:
    """Resolve a ResourceData max value to an integer.

    If max is already an int, return it unchanged with a simple formula string.
    If max is a string like "12+CON", replace ability abbreviations with their
    modifier values and evaluate the expression.

    Returns:
        Tuple of (resolved_max_value, formula_string)
    """
    import re

    max_val = resource.max
    if isinstance(max_val, int):
        return max_val, str(max_val)

    # String formula like "12+CON"
    formula = max_val

    def _replace_ability(match: re.Match) -> str:
        abil = match.group(1)
        mod = ability_modifiers.get(abil, 0)
        return str(mod)

    # Replace ability abbreviations (STR, DEX, CON, INT, WIS, CHA) with modifier values
    resolved_expr = re.sub(r"(STR|DEX|CON|INT|WIS|CHA)", _replace_ability, formula)

    try:
        result = eval(resolved_expr, {"__builtins__": {}}, {})
        result = int(result)
    except Exception:
        result = 10  # fallback

    # Build formula string for display
    formula_parts = []
    remaining = formula
    for abil in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        if abil in remaining:
            mod = ability_modifiers.get(abil, 0)
            formula_parts.append(f"{abil}({mod:+d})")
            remaining = remaining.replace(abil, str(mod))
    formula_str = formula
    for abil in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
        mod = ability_modifiers.get(abil, 0)
        formula_str = formula_str.replace(abil, f"{abil}({mod:+d})")
    formula_str = f"{formula_str} = {result}"

    return result, formula_str


def compute_derived_sheet(record: CharacterRecord) -> DerivedSheet:
    """Compute a fully populated DerivedSheet from a CharacterRecord.

    Runs all three pipeline phases in sequence, resolves ResourceData max
    string formulas, and constructs a ``DerivedSheet`` instance.

    This is the main entry point for the derivation pipeline. Pure function —
    no side effects, deterministic output for the same input.

    Args:
        record: The source CharacterRecord (player choices only)

    Returns:
        DerivedSheet with all computed stats populated
    """

    # Phase 1-3: Run the pipeline
    base = prepare_base_data(record)
    embedded = prepare_embedded_data(base, record)
    derived = prepare_derived_data(embedded, base, record)

    ability_modifiers = base["ability_modifiers"]

    # Resolve ResourceData max string formulas
    formulas = dict(derived["formulas"])  # Copy to avoid mutation
    for resource_name, resource in record.resources.items():
        resolved_max, formula_str = _resolve_resource_max(resource, ability_modifiers)
        formulas[f"{resource_name}_max"] = formula_str

    # Build and return the DerivedSheet
    sheet = DerivedSheet(
        ability_modifiers=ability_modifiers,
        proficiency_bonus=base["proficiency_bonus"],
        ac=derived["ac"],
        initiative=derived["initiative"],
        speed=base["speed"],
        skill_modifiers=embedded["skill_modifiers"],
        saving_throw_modifiers=embedded["saving_throw_modifiers"],
        passive_perception=embedded["passive_perception"],
        attack_bonus=derived["attack_bonus"],
        encumbrance=derived["encumbrance"],
        hit_dice=base["hit_dice"],
        formulas=formulas,
    )

    return sheet


# ---------------------------------------------------------------------------
# Derived data helpers (Phase 3 — AC, initiative, encumbrance, attack bonus)
# ---------------------------------------------------------------------------


def _get_armor_category(item) -> str:
    """Determine armor category from item properties.

    Uses 'armor_category' property if present, otherwise heuristics:
    - armor_bonus >= 16 → "heavy"
    - armor_bonus >= 13 → "medium"
    - armor_bonus >= 11 → "light"
    - armor_bonus < 10  → "shield" (small bonus, stacks)
    """
    from app.character.items import ItemType  # noqa: F401 — kept for future use

    category = item.properties.get("armor_category", "")
    if category:
        return category

    bonus = item.properties.get("armor_bonus", 0)
    if bonus >= 16:
        return "heavy"
    elif bonus >= 13:
        return "medium"
    elif bonus >= 11:
        return "light"
    else:
        return "shield"


def _compute_ac(
    record: CharacterRecord, ability_modifiers: dict[str, int]
) -> tuple[int, list[str]]:
    """Compute AC and return (ac_value, parts_list for formula)."""
    from app.character.items import ItemType

    equipped_ids = set(record.equipped_items)
    body_armor_ac = 10  # Base unarmored
    body_armor_name = "Unarmored"
    shield_bonus = 0
    shield_name = ""
    dex_mod = ability_modifiers.get("DEX", 0)
    dex_cap: int | None = None  # None = no cap (unarmored & light)

    for item in record.inventory:
        if item.id not in equipped_ids:
            continue
        if item.item_type != ItemType.ARMOR:
            continue

        category = _get_armor_category(item)
        bonus = item.properties.get("armor_bonus", 0)

        if category == "shield":
            shield_bonus += bonus
            shield_name = item.name
        elif category == "heavy":
            dex_cap = 0
            if bonus > body_armor_ac:
                body_armor_ac = bonus
                body_armor_name = item.name
        elif category == "medium":
            if dex_cap is None or dex_cap > 2:
                dex_cap = 2
            if bonus > body_armor_ac:
                body_armor_ac = bonus
                body_armor_name = item.name
        else:  # light
            if bonus > body_armor_ac:
                body_armor_ac = bonus
                body_armor_name = item.name

    # Apply DEX cap (if any)
    if dex_cap is not None:
        dex_mod = min(dex_mod, dex_cap) if dex_cap >= 0 else 0

    if dex_cap == 0 and body_armor_ac > 10:
        # Heavy armor: body_armor_ac IS the total AC (includes base)
        ac = body_armor_ac + shield_bonus
        parts = [f"{body_armor_ac} ({body_armor_name})"]
    else:
        if body_armor_ac > 10:
            ac = 10 + dex_mod + (body_armor_ac - 10) + shield_bonus
        else:
            ac = 10 + dex_mod + shield_bonus
        parts = ["10 (base)"]
        if body_armor_ac > 10:
            parts.append(f"{body_armor_ac - 10} ({body_armor_name})")
        if dex_mod != 0:
            parts.append(f"{dex_mod} (DEX)")

    if shield_bonus > 0:
        parts.append(f"{shield_bonus} ({shield_name})")

    return ac, parts


def _compute_encumbrance(record: CharacterRecord) -> dict:
    """Compute encumbrance: current weight, max weight, status."""
    total_weight = sum(item.weight * item.quantity for item in record.inventory)
    str_score = record.abilities.get("STR", 10)
    max_weight = str_score * 15

    if total_weight > str_score * 10:
        status = "heavily encumbered"
    elif total_weight > str_score * 5:
        status = "encumbered"
    else:
        status = "normal"

    return {
        "current": total_weight,
        "max": max_weight,
        "status": status,
    }


def _compute_attack_bonus(
    record: CharacterRecord,
    ability_modifiers: dict[str, int],
    proficiency_bonus: int,
) -> dict[str, int]:
    """Compute attack bonuses for melee, ranged, and spell."""
    str_mod = ability_modifiers.get("STR", 0)
    dex_mod = ability_modifiers.get("DEX", 0)

    # Spell attack ability varies by class
    _class_spell_ability: dict[str, str] = {
        "Fighter": "INT",
        "Rogue": "INT",
        "Mage": "INT",
        "Cleric": "WIS",
    }
    spell_ability = _class_spell_ability.get(record.character_class, "INT")
    spell_mod = ability_modifiers.get(spell_ability, 0)

    return {
        "melee": proficiency_bonus + str_mod,
        "ranged": proficiency_bonus + dex_mod,
        "spell": proficiency_bonus + spell_mod,
    }


def _build_formulas(
    ac_parts: list[str],
    initiative: int,
    encumbrance: dict,  # noqa: ARG001 — kept for future formula expansions
    attack_bonus: dict[str, int],
    ability_modifiers: dict[str, int],
    record: CharacterRecord,  # noqa: ARG001 — kept for future formula expansions
) -> dict[str, str]:
    """Build human-readable formula breakdowns."""
    formulas: dict[str, str] = {
        "ac": " + ".join(ac_parts),
        "initiative": f"{initiative} (DEX modifier)",
    }

    if attack_bonus.get("melee") is not None:
        str_mod = ability_modifiers.get("STR", 0)
        formulas["attack_melee"] = (
            f"{attack_bonus['melee']} = prof({attack_bonus['melee'] - str_mod})"
            f" + STR({str_mod})"
        )

    if attack_bonus.get("ranged") is not None:
        dex_mod = ability_modifiers.get("DEX", 0)
        formulas["attack_ranged"] = (
            f"{attack_bonus['ranged']} = prof({attack_bonus['ranged'] - dex_mod})"
            f" + DEX({dex_mod})"
        )

    return formulas


def prepare_derived_data(embedded: dict, base: dict, record: CharacterRecord) -> dict:
    """Third phase of the derivation pipeline.

    Takes output from prepare_embedded_data(), prepare_base_data(), and the
    CharacterRecord to compute AC (with armor), initiative, encumbrance,
    attack bonuses, and formula breakdowns.

    Args:
        embedded: Output from prepare_embedded_data()
        base: Output from prepare_base_data() with ability_modifiers etc.
        record: The source CharacterRecord

    Returns:
        dict with keys: ac, initiative, encumbrance, attack_bonus, formulas
    """
    ability_modifiers = base["ability_modifiers"]
    proficiency_bonus = base["proficiency_bonus"]

    # --- AC Computation ---
    ac, ac_parts = _compute_ac(record, ability_modifiers)

    # --- Initiative ---
    initiative = ability_modifiers.get("DEX", 0)

    # --- Encumbrance ---
    encumbrance = _compute_encumbrance(record)

    # --- Attack Bonuses ---
    attack_bonus = _compute_attack_bonus(record, ability_modifiers, proficiency_bonus)

    # --- Formulas ---
    formulas = _build_formulas(
        ac_parts, initiative, encumbrance, attack_bonus, ability_modifiers, record
    )

    return {
        "ac": ac,
        "initiative": initiative,
        "encumbrance": encumbrance,
        "attack_bonus": attack_bonus,
        "formulas": formulas,
    }
