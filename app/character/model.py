"""
Character Data Model — THE FLESH AND BONE OF HEROES.

Holds the complete player character state: identity, origin story,
capabilities (class, level, abilities, skills, combat stats), and
inventory.  Every character is serializable to/from JSON so the Evil
Wizard can save, load, and teleport characters across sessions.
"""

from __future__ import annotations

import dataclasses
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CLASSES: frozenset[str] = frozenset({"Fighter", "Rogue", "Mage", "Cleric"})

STANDARD_ABILITIES: frozenset[str] = frozenset(
    {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
)

# Default templates: (ability_scores, hp, ac, skills, inventory)
# Standard array: 15, 14, 13, 12, 10, 8
_CLASS_TEMPLATES: dict[str, dict[str, Any]] = {
    "Fighter": {
        "abilities": {"STR": 15, "DEX": 13, "CON": 14, "WIS": 12, "INT": 10, "CHA": 8},
        "hp": 12,
        "ac": 18,
        "skills": ["Athletics", "Perception"],
        "inventory": ["Longsword", "Chain Mail", "Shield", "Explorer's Pack"],
        "gold": 10,
    },
    "Rogue": {
        "abilities": {"STR": 8, "DEX": 15, "CON": 13, "INT": 14, "WIS": 12, "CHA": 10},
        "hp": 9,
        "ac": 14,
        "skills": ["Stealth", "Sleight of Hand", "Perception"],
        "inventory": [
            "Shortsword",
            "Leather Armor",
            "Thieves' Tools",
            "Burglar's Pack",
        ],
        "gold": 15,
    },
    "Mage": {
        "abilities": {"STR": 8, "DEX": 13, "CON": 14, "INT": 15, "WIS": 12, "CHA": 10},
        "hp": 8,
        "ac": 12,
        "skills": ["Arcana", "Investigation"],
        "inventory": ["Spellbook", "Arcane Focus", "Scholar's Pack"],
        "gold": 20,
    },
    "Cleric": {
        "abilities": {"WIS": 15, "CON": 14, "STR": 13, "CHA": 12, "INT": 10, "DEX": 8},
        "hp": 10,
        "ac": 16,
        "skills": ["Religion", "Medicine"],
        "inventory": ["Mace", "Chain Mail", "Shield", "Priest's Pack"],
        "gold": 10,
    },
}


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------


@dataclass
class Character:
    """A player character — the hero at the centre of the story.

    Every character has a name, appearance, personality, backstory,
    plot hooks, a class, level, experience points, six ability scores,
    skill proficiencies, hit points, armour class, and a list of
    carried items.

    Validation is performed in *__post_init__* so that invalid state
    is caught at construction time rather than silently corrupting the
    game later.
    """

    # -- Identity -----------------------------------------------------------
    name: str
    appearance: str = ""
    personality: str = ""

    # -- Origin -------------------------------------------------------------
    backstory: str = ""
    hooks: list[str] = field(default_factory=list)

    # -- Capabilities -------------------------------------------------------
    character_class: str = "Fighter"
    level: int = 1
    xp: int = 0
    abilities: dict[str, int] = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    hp: int = 10
    max_hp: int = 10
    ac: int = 10
    inventory: list[str] = field(default_factory=list)
    gold: int = 0

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Validate all fields on construction."""
        _validate_name(self.name)
        _validate_class(self.character_class)
        _validate_abilities(self.abilities)
        _validate_level(self.level)
        _validate_xp(self.xp)
        _validate_hp(self.hp, self.max_hp)
        _validate_ac(self.ac)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert the character to a JSON-compatible dictionary.

        Nested containers (lists, dicts) are converted recursively
        via ``asdict()``.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Character:
        """Reconstruct a ``Character`` from a dictionary.

        This is the inverse of :meth:`to_dict`.  Use it to load a
        character that was saved as JSON.

        Field filtering is applied for forward compatibility —
        unexpected keys in *data* are silently ignored.  Type coercion
        is applied to scalar fields for robustness against
        int-as-string and similar edge cases.
        """
        known_fields = {f.name for f in dataclasses.fields(cls)}

        # Filter to known fields only (forward compatibility)
        filtered = {k: v for k, v in data.items() if k in known_fields}

        # Type coercion for scalar fields
        if "level" in filtered:
            filtered["level"] = _coerce_int(filtered["level"], 1)
        if "xp" in filtered:
            filtered["xp"] = _coerce_int(filtered["xp"], 0)
        if "hp" in filtered:
            filtered["hp"] = _coerce_int(filtered["hp"], 10)
        if "max_hp" in filtered:
            filtered["max_hp"] = _coerce_int(filtered["max_hp"], 10)
        if "ac" in filtered:
            filtered["ac"] = _coerce_int(filtered["ac"], 10)
        if "gold" in filtered:
            filtered["gold"] = _coerce_int(filtered["gold"], 0)

        # Guard container fields against non-list values
        if not isinstance(filtered.get("skills"), list):
            filtered["skills"] = []
        if not isinstance(filtered.get("inventory"), list):
            filtered["inventory"] = []
        if not isinstance(filtered.get("hooks"), list):
            filtered["hooks"] = []

        # Guard abilities against missing/incomplete dict
        if not isinstance(filtered.get("abilities"), dict):
            filtered["abilities"] = {abil: 10 for abil in STANDARD_ABILITIES}
        else:
            for abil in STANDARD_ABILITIES:
                if abil not in filtered["abilities"]:
                    filtered["abilities"][abil] = 10

        return cls(**filtered)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create_default(cls, name: str, character_class: str) -> Character:
        """Create a default character with the given *name* and *character_class*.

        Ability scores use the standard array (15, 14, 13, 12, 10, 8)
        assigned according to the class's primary attributes.  Hit
        points, armour class, skill proficiencies, and starting
        equipment are all set to class-appropriate defaults.

        Parameters
        ----------
        name : str
            The character's name (must be non-empty).
        character_class : str
            One of ``"Fighter"``, ``"Rogue"``, ``"Mage"``, or ``"Cleric"``.

        Returns
        -------
        Character
            A fully populated ``Character`` instance ready for adventure.
        """
        _validate_class(character_class)

        tmpl = _CLASS_TEMPLATES[character_class]

        return cls(
            name=name,
            character_class=character_class,
            level=1,
            xp=0,
            abilities=dict(tmpl["abilities"]),
            skills=list(tmpl["skills"]),
            hp=tmpl["hp"],
            max_hp=tmpl["hp"],
            ac=tmpl["ac"],
            inventory=list(tmpl["inventory"]),
            gold=tmpl["gold"],
        )


# ---------------------------------------------------------------------------
# Private validation helpers
# ---------------------------------------------------------------------------


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Character name must be a non-empty string.")


def _validate_class(character_class: str) -> None:
    if character_class not in VALID_CLASSES:
        raise ValueError(
            f"Invalid character class {character_class!r}. "
            f"Must be one of {sorted(VALID_CLASSES)}."
        )


def _validate_abilities(abilities: dict[str, int]) -> None:
    if not isinstance(abilities, dict):
        raise ValueError("Abilities must be a dictionary.")

    missing = STANDARD_ABILITIES - set(abilities.keys())
    if missing:
        raise ValueError(
            f"Missing ability score(s): {', '.join(sorted(missing))}. "
            f"All six (STR, DEX, CON, INT, WIS, CHA) are required."
        )

    for abil, value in abilities.items():
        if not isinstance(value, int) or value < 3 or value > 18:
            raise ValueError(
                f"Ability score {abil}={value!r} is out of range. "
                f"Each ability must be an integer between 3 and 18."
            )


def _validate_level(level: int) -> None:
    if not isinstance(level, int) or level < 1:
        raise ValueError(f"Level must be >= 1, got {level!r}.")


def _validate_xp(xp: int) -> None:
    if not isinstance(xp, int) or xp < 0:
        raise ValueError(f"XP must be >= 0, got {xp!r}.")


def _validate_hp(hp: int, max_hp: int) -> None:
    if not isinstance(hp, int) or hp < 0:
        raise ValueError(f"HP must be >= 0, got {hp!r}.")
    if not isinstance(max_hp, int) or max_hp <= 0:
        raise ValueError(f"max_hp must be > 0, got {max_hp!r}.")
    if hp > max_hp:
        raise ValueError(f"hp ({hp}) cannot exceed max_hp ({max_hp}).")


def _validate_ac(ac: int) -> None:
    """Validate armour class is non-negative."""
    if not isinstance(ac, int) or ac < 0:
        raise ValueError(f"AC must be >= 0, got {ac!r}.")


# ---------------------------------------------------------------------------
# Private coercion helpers
# ---------------------------------------------------------------------------


def _coerce_int(value: Any, default: int) -> int:
    """Try to coerce *value* to an int; return *default* on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        warnings.warn(f"Failed to coerce {value!r} to int, using default {default}")
        return default
