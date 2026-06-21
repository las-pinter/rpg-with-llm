"""
Creature/Monster Stat Block Model — FLESH AND BONES FOR THE BESTIARY.

Defines the ``Creature`` dataclass: a self-contained monster or NPC stat
block with all the shinies an Evil Wizard needs — abilities, HP, AC,
skills, resistances, actions, and more.

Every creature is serializable to/from JSON so the horde can be saved,
loaded, and thrown at heroes across sessions.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Any

# ---------------------------------------------------------------------------
# Creature
# ---------------------------------------------------------------------------


@dataclass
class Creature:
    """A creature/monster stat block.

    Fields
    ------
    id : str
        UUID string — auto-generated if not provided.
    name : str
        Display name of the creature.
    ac : int
        Armour Class.
    hp : int
        Current hit points.
    max_hp : int
        Maximum hit points.
    abilities : dict[str, int]
        Ability scores keyed by three-letter abbreviation
        (``str``, ``dex``, ``con``, ``int``, ``wis``, ``cha``).
    skills : list[str]
        Skills the creature is trained in (e.g. ``["stealth", "perception"]``).
    resistances : list[str]
        Damage types the creature resists.
    vulnerabilities : list[str]
        Damage types the creature is vulnerable to.
    immunities : list[str]
        Damage types (or conditions) the creature is immune to.
    actions : list[dict]
        Action entries, each with ``name``, ``description``, ``damage``,
        and ``attack_bonus`` keys.
    xp_value : int
        Experience points awarded for defeating this creature.
    cr : float
        Challenge rating (0–30).
    size : str
        Size category, e.g. ``"Small"``, ``"Medium"``, ``"Large"``.
    movement : dict[str, int]
        Movement speeds in feet, e.g. ``{"walk": 30, "fly": 60}``.
    saving_throws : dict[str, bool]
        Saving throw proficiencies keyed by ability abbreviation,
        e.g. ``{"str": True, "dex": False}``.
    senses : list[str]
        Special senses such as ``"darkvision 60 ft"``.
    languages : list[str]
        Languages the creature can speak or understand.
    special_abilities : list[dict]
        Special ability entries, each with ``name`` and ``description`` keys.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    ac: int = 10
    hp: int = 1
    max_hp: int = 1
    abilities: dict[str, int] = field(
        default_factory=lambda: {
            "str": 10,
            "dex": 10,
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
        }
    )
    skills: list[str] = field(default_factory=list)
    resistances: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)
    immunities: list[str] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    xp_value: int = 0
    cr: float = 0.0
    size: str = "Medium"
    movement: dict[str, int] = field(default_factory=lambda: {"walk": 30})
    saving_throws: dict[str, bool] = field(default_factory=dict)
    senses: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    special_abilities: list[dict[str, Any]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Ability modifier
    # ------------------------------------------------------------------

    def get_ability_modifier(self, ability: str) -> int:
        """Return the D&D 5e ability modifier for the given ability score.

        Formula: ``(score - 10) // 2``

        Args:
            ability: Three-letter ability abbreviation (``"str"``, ``"dex"``,
                ``"con"``, ``"int"``, ``"wis"``, ``"cha"``).

        Returns:
            The ability modifier (e.g. score 14 → +2, score 8 → -1).
        """
        score = self.abilities.get(ability, 10)
        return (score - 10) // 2

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert this creature to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Creature:
        """Reconstruct a ``Creature`` from a dictionary.

        Unknown keys in *data* are silently ignored for forward
        compatibility.

        Args:
            data: A dictionary produced by :meth:`to_dict`.

        Returns:
            A new ``Creature`` instance with the deserialised fields.
        """
        known_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_creature(data: dict[str, Any]) -> list[str]:
    """Validate a creature data dictionary and return a list of error messages.

    An empty list means the data is valid.

    Checks performed:
    - CR between 0 and 30
    - HP is non-negative
    - max_hp is positive
    - All 6 ability scores present
    - Ability scores in range 3–18
    - AC is non-negative

    Args:
        data: A dict with creature fields (typically from user input).

    Returns:
        A list of human-readable error messages (empty = valid).
    """
    errors: list[str] = []

    # --- CR -----------------------------------------------------------------
    cr = data.get("cr", 0)
    if not isinstance(cr, (int, float)):
        errors.append(f"CR must be a number, got {type(cr).__name__}")
    elif isinstance(cr, float) and math.isnan(cr):
        errors.append("CR cannot be NaN")
    elif cr < 0 or cr > 30:
        errors.append(f"CR must be between 0 and 30, got {cr}")

    # --- HP ----------------------------------------------------------------
    hp = data.get("hp", 0)
    if not isinstance(hp, int):
        errors.append(f"HP must be an integer, got {type(hp).__name__}")
    elif hp < 0:
        errors.append(f"HP cannot be negative, got {hp}")

    max_hp = data.get("max_hp", 0)
    if not isinstance(max_hp, int):
        errors.append(f"max_hp must be an integer, got {type(max_hp).__name__}")
    elif max_hp <= 0:
        errors.append(f"max_hp must be positive, got {max_hp}")

    if isinstance(hp, int) and isinstance(max_hp, int) and hp > max_hp:
        errors.append(f"HP ({hp}) cannot exceed max_hp ({max_hp})")

    # --- Abilities ----------------------------------------------------------
    abilities = data.get("abilities", {})
    required_abilities = {"str", "dex", "con", "int", "wis", "cha"}
    if not isinstance(abilities, dict):
        errors.append(f"abilities must be a dict, got {type(abilities).__name__}")
    else:
        missing = required_abilities - set(abilities.keys())
        if missing:
            errors.append(f"Missing abilities: {', '.join(sorted(missing))}")

        for abbr in required_abilities:
            if abbr in abilities:
                score = abilities[abbr]
                if not isinstance(score, int):
                    errors.append(
                        f"Ability {abbr!r} must be an integer, "
                        f"got {type(score).__name__}"
                    )
                elif score < 3 or score > 18:
                    errors.append(
                        f"Ability {abbr!r} score {score} is out of range (must be 3–18)"
                    )

    # --- AC ----------------------------------------------------------------
    ac = data.get("ac", 0)
    if not isinstance(ac, int):
        errors.append(f"AC must be an integer, got {type(ac).__name__}")
    elif ac < 0:
        errors.append(f"AC cannot be negative, got {ac}")

    return errors
