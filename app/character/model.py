"""
Character Data Model — THE FLESH AND BONE OF HEROES.

Holds the complete player character state: identity, origin story,
capabilities (class, level, abilities, skills, combat stats), and
inventory.  Every character is serializable to/from JSON so the Evil
Wizard can save, load, and teleport characters across sessions.

This module now defines three main classes:

- ``CharacterRecord`` — stores only player choices (what gets persisted).
- ``DerivedSheet`` — computed values that are never persisted (AC, HP
  max, ability modifiers, proficiency bonus, etc.).
- ``Character`` — legacy compatibility shim (kept for backward
  compatibility; all new code should use ``CharacterRecord`` +
  ``DerivedSheet`` instead).
"""

from __future__ import annotations

import dataclasses
import uuid
import warnings
from dataclasses import asdict, dataclass, field
from typing import Any

from app.character.items import Item, ItemType
from app.character.resources import ResourceData

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CLASSES: frozenset[str] = frozenset({"Fighter", "Rogue", "Mage", "Cleric"})

STANDARD_ABILITIES: list[str] = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

# Point-buy system rules
POINT_BUY_COST: dict[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}
MAX_POINTS: int = 27
MIN_SCORE: int = 8
MAX_SCORE: int = 15

# Assisted creation prompts
ASSISTED_CREATION_QUESTIONS: list[str] = [
    "Where were you born, and what was your childhood like?",
    "What drove you to become an adventurer?",
    "Describe a pivotal moment that shaped who you are.",
    "What is your greatest fear, and why?",
    "Who or what do you value above all else?",
    "Tell me about a mentor or rival who influenced you.",
    "What is your ultimate goal or ambition?",
]

# ---------------------------------------------------------------------------
# Starting gear options — alternatives players can choose during creation.
# Each class has categories ("weapon", "armor", "pack") with a list of
# Item alternatives.  The first option in each category matches the
# default inventory in ``_CLASS_TEMPLATES``.
# ---------------------------------------------------------------------------
_STARTING_GEAR_OPTIONS: dict[str, dict[str, list[Item]]] = {
    "Fighter": {
        "weapon": [
            Item(
                name="Longsword",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d8"},
                weight=3.0,
                value=15,
            ),
            Item(
                name="Battleaxe",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d8"},
                weight=4.0,
                value=10,
            ),
        ],
        "armor": [
            Item(
                name="Chain Mail",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 16},
                weight=55.0,
                value=75,
            ),
            Item(
                name="Leather Armor",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 11},
                weight=10.0,
                value=10,
            ),
        ],
        "pack": [
            Item(
                name="Explorer's Pack",
                item_type=ItemType.CONTAINER,
                weight=5.0,
                value=10,
            ),
            Item(
                name="Dungeoneer's Pack",
                item_type=ItemType.CONTAINER,
                weight=8.0,
                value=12,
            ),
        ],
    },
    "Rogue": {
        "weapon": [
            Item(
                name="Rapier",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d8"},
                weight=2.0,
                value=25,
            ),
            Item(
                name="Shortsword",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d6"},
                weight=2.0,
                value=10,
            ),
        ],
        "armor": [
            Item(
                name="Leather Armor",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 11},
                weight=10.0,
                value=10,
            ),
        ],
        "pack": [
            Item(
                name="Burglar's Pack",
                item_type=ItemType.CONTAINER,
                weight=6.0,
                value=16,
            ),
            Item(
                name="Thieves' Pack",
                item_type=ItemType.CONTAINER,
                weight=7.0,
                value=15,
            ),
        ],
    },
    "Mage": {
        "weapon": [
            Item(
                name="Quarterstaff",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d6"},
                weight=4.0,
                value=0,
            ),
            Item(
                name="Dagger",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d4"},
                weight=1.0,
                value=2,
            ),
        ],
        "armor": [],
        "pack": [
            Item(
                name="Scholar's Pack",
                item_type=ItemType.CONTAINER,
                weight=4.0,
                value=10,
            ),
            Item(
                name="Explorer's Pack",
                item_type=ItemType.CONTAINER,
                weight=5.0,
                value=10,
            ),
        ],
    },
    "Cleric": {
        "weapon": [
            Item(
                name="Mace",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d6"},
                weight=4.0,
                value=5,
            ),
            Item(
                name="Warhammer",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d8"},
                weight=5.0,
                value=15,
            ),
        ],
        "armor": [
            Item(
                name="Chain Mail",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 16},
                weight=55.0,
                value=75,
            ),
            Item(
                name="Scale Mail",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 14},
                weight=45.0,
                value=50,
            ),
        ],
        "pack": [
            Item(
                name="Priest's Pack",
                item_type=ItemType.CONTAINER,
                weight=5.0,
                value=10,
            ),
            Item(
                name="Explorer's Pack",
                item_type=ItemType.CONTAINER,
                weight=5.0,
                value=10,
            ),
        ],
    },
}

# ---------------------------------------------------------------------------
# Legacy class templates — used by ``Character.create_default()`` for
# backward compatibility.  New code should use ``_CLASS_TEMPLATES``
# (see below) which uses ``Item`` and ``ResourceData`` objects.
# ---------------------------------------------------------------------------
_LEGACY_CLASS_TEMPLATES: dict[str, dict[str, Any]] = {
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
# Class templates for ``CharacterRecord`` — stores only player choices.
# Inventory uses ``Item`` objects, resources use ``ResourceData``.
# HP, max_hp, and AC are NOT stored here — they belong on ``DerivedSheet``.
# ---------------------------------------------------------------------------
_CLASS_TEMPLATES: dict[str, dict[str, Any]] = {
    "Fighter": {
        "abilities": {"STR": 15, "DEX": 13, "CON": 14, "WIS": 12, "INT": 10, "CHA": 8},
        "skills": ["Athletics", "Perception"],
        "gold": 10,
        "inventory": [
            Item(
                name="Longsword",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d8"},
                weight=3.0,
                value=15,
            ),
            Item(
                name="Chain Mail",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 16},
                weight=55.0,
                value=75,
            ),
            Item(
                name="Shield",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 2},
                weight=6.0,
                value=10,
            ),
            Item(
                name="Explorer's Pack",
                item_type=ItemType.CONTAINER,
                weight=5.0,
                value=10,
            ),
        ],
        "resources": {
            "hp": ResourceData(
                value=12, max=12, short_rest_recovery="1d10", long_rest_recovery="full"
            )
        },
    },
    "Rogue": {
        "abilities": {"STR": 8, "DEX": 15, "CON": 13, "INT": 14, "WIS": 12, "CHA": 10},
        "skills": ["Stealth", "Sleight of Hand", "Perception"],
        "gold": 15,
        "inventory": [
            Item(
                name="Rapier",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d8"},
                weight=2.0,
                value=25,
            ),
            Item(
                name="Leather Armor",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 11},
                weight=10.0,
                value=10,
            ),
            Item(name="Thieves' Tools", item_type=ItemType.TOOL, weight=1.0, value=25),
            Item(
                name="Burglar's Pack",
                item_type=ItemType.CONTAINER,
                weight=5.0,
                value=16,
            ),
        ],
        "resources": {
            "hp": ResourceData(
                value=9, max=9, short_rest_recovery="1d8", long_rest_recovery="full"
            )
        },
    },
    "Mage": {
        "abilities": {"STR": 8, "DEX": 13, "CON": 14, "INT": 15, "WIS": 12, "CHA": 10},
        "skills": ["Arcana", "Investigation"],
        "gold": 20,
        "inventory": [
            Item(
                name="Quarterstaff",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d6"},
                weight=4.0,
                value=0,
            ),
            Item(name="Spellbook", item_type=ItemType.TOOL, weight=3.0, value=50),
            Item(name="Arcane Focus", item_type=ItemType.TOOL, weight=1.0, value=10),
            Item(
                name="Scholar's Pack",
                item_type=ItemType.CONTAINER,
                weight=5.0,
                value=10,
            ),
        ],
        "resources": {
            "hp": ResourceData(
                value=8, max=8, short_rest_recovery="1d6", long_rest_recovery="full"
            )
        },
    },
    "Cleric": {
        "abilities": {"WIS": 15, "CON": 14, "STR": 13, "CHA": 12, "INT": 10, "DEX": 8},
        "skills": ["Religion", "Medicine"],
        "gold": 10,
        "inventory": [
            Item(
                name="Mace",
                item_type=ItemType.WEAPON,
                properties={"damage": "1d6"},
                weight=4.0,
                value=5,
            ),
            Item(
                name="Chain Mail",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 16},
                weight=55.0,
                value=75,
            ),
            Item(
                name="Shield",
                item_type=ItemType.ARMOR,
                properties={"armor_bonus": 2},
                weight=6.0,
                value=10,
            ),
            Item(
                name="Priest's Pack", item_type=ItemType.CONTAINER, weight=5.0, value=10
            ),
        ],
        "resources": {
            "hp": ResourceData(
                value=10, max=10, short_rest_recovery="1d8", long_rest_recovery="full"
            )
        },
    },
}


# ---------------------------------------------------------------------------
# DerivedSheet — NEVER persisted, always computed.
# ---------------------------------------------------------------------------


@dataclass
class DerivedSheet:
    """Computed character values derived from a ``CharacterRecord``.

    This dataclass is never persisted to disk — it is recalculated every
    time a character is loaded.  All fields have sensible defaults for
    a level-1 character.

    ``to_dict()`` is provided for API serialisation; there is no
    ``from_dict()`` because this class is never loaded from storage.
    """

    ability_modifiers: dict[str, int] = field(default_factory=dict)
    proficiency_bonus: int = 2
    ac: int = 10
    initiative: int = 0
    speed: int = 30
    skill_modifiers: dict[str, int] = field(default_factory=dict)
    saving_throw_modifiers: dict[str, int] = field(default_factory=dict)
    passive_perception: int = 10
    attack_bonus: dict[str, int] = field(default_factory=dict)
    encumbrance: dict = field(default_factory=dict)
    hit_dice: str = ""
    resistances: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)
    formulas: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the derived sheet to a JSON-compatible dictionary."""
        return asdict(self)


# ---------------------------------------------------------------------------
# CharacterRecord — stores only player choices.
# ---------------------------------------------------------------------------


@dataclass
class CharacterRecord:
    """A player character record — stores only player choices.

    This is the **new** primary data model for character persistence.
    Unlike the legacy ``Character`` class, this dataclass does NOT store
    computed/derived values (AC, HP max, ability modifiers, proficiency
    bonus, saving throws, etc.) — those live on ``DerivedSheet``.

    Fields
    ------
    id : str
        UUID string — auto-generated if not provided.
    name : str
        Character's name.
    character_class : str
        One of ``"Fighter"``, ``"Rogue"``, ``"Mage"``, ``"Cleric"``.
    level : int
        Current level (default 1).
    xp : int
        Experience points (default 0).
    abilities : dict[str, int]
        Six ability scores (STR, DEX, CON, INT, WIS, CHA).
    skills : list[str]
        Skill proficiencies.
    gold : int
        Gold pieces carried.
    inventory : list[Item]
        Items carried (uses ``Item`` from ``items.py``).
    equipped_items : list[str]
        Item IDs of currently equipped items (references ``inventory``).
    resources : dict[str, ResourceData]
        Tracked resources such as HP, mana, stamina.
    appearance : str
        Physical description.
    personality : str
        Personality traits.
    backstory : str
        Character backstory.
    hooks : list[str]
        Plot hooks / adventure seeds.
    """

    # -- Identity -----------------------------------------------------------
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""

    # -- Origin -------------------------------------------------------------
    appearance: str = ""
    personality: str = ""
    backstory: str = ""
    hooks: list[str] = field(default_factory=list)

    # -- Capabilities (player choices only) ----------------------------------
    character_class: str = "Fighter"
    level: int = 1
    xp: int = 0
    abilities: dict[str, int] = field(
        default_factory=lambda: {abil: 10 for abil in STANDARD_ABILITIES}
    )
    skills: list[str] = field(default_factory=list)
    gold: int = 0

    # -- Inventory & resources -----------------------------------------------
    inventory: list[Item] = field(default_factory=list)
    equipped_items: list[str] = field(default_factory=list)
    resources: dict[str, ResourceData] = field(default_factory=dict)

    # NOTE: AC, HP, max_hp, ability modifiers, proficiency bonus, saving
    # throws, and all other derived values are on ``DerivedSheet``, NOT here.

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

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert the character record to a JSON-compatible dictionary.

        Inventory items and resources are serialised via their own
        ``to_dict()`` methods.
        """
        data = asdict(self)
        # Override inventory with properly serialised items
        data["inventory"] = [item.to_dict() for item in self.inventory]
        # Override resources with properly serialised resource data
        data["resources"] = {k: v.to_dict() for k, v in self.resources.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterRecord:
        """Reconstruct a ``CharacterRecord`` from a dictionary.

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
        if "gold" in filtered:
            filtered["gold"] = _coerce_int(filtered["gold"], 0)

        # Guard container fields against non-list values
        if not isinstance(filtered.get("skills"), list):
            filtered["skills"] = []
        if not isinstance(filtered.get("hooks"), list):
            filtered["hooks"] = []
        if not isinstance(filtered.get("equipped_items"), list):
            filtered["equipped_items"] = []

        # Guard abilities against missing/incomplete dict
        if not isinstance(filtered.get("abilities"), dict):
            filtered["abilities"] = {abil: 10 for abil in STANDARD_ABILITIES}
        else:
            for abil in STANDARD_ABILITIES:
                if abil not in filtered["abilities"]:
                    filtered["abilities"][abil] = 10

        # Deserialize inventory items
        if isinstance(filtered.get("inventory"), list):
            filtered["inventory"] = [
                Item.from_dict(item) if isinstance(item, dict) else item
                for item in filtered["inventory"]
            ]
        else:
            filtered["inventory"] = []

        # Deserialize resources
        if isinstance(filtered.get("resources"), dict):
            filtered["resources"] = {
                k: ResourceData.from_dict(v) if isinstance(v, dict) else v
                for k, v in filtered["resources"].items()
            }
        else:
            filtered["resources"] = {}

        return cls(**filtered)

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create_default(cls, name: str, character_class: str) -> CharacterRecord:
        """Create a default character record for *name* and *character_class*.

        Ability scores use the standard array (15, 14, 13, 12, 10, 8)
        assigned according to the class's primary attributes.  Skill
        proficiencies, starting equipment, and resources (HP) are set to
        class-appropriate defaults.

        Parameters
        ----------
        name : str
            The character's name (must be non-empty).
        character_class : str
            One of ``"Fighter"``, ``"Rogue"``, ``"Mage"``, or ``"Cleric"``.

        Returns
        -------
        CharacterRecord
            A fully populated ``CharacterRecord`` instance ready for adventure.
        """
        _validate_class(character_class)

        tmpl = _CLASS_TEMPLATES[character_class]

        # Create fresh copies of inventory items (each gets a NEW UUID)
        inventory = [
            Item(
                name=i.name,
                item_type=i.item_type,
                quantity=i.quantity,
                properties=dict(i.properties),
                description=i.description,
                weight=i.weight,
                value=i.value,
            )
            for i in tmpl["inventory"]
        ]

        # Create fresh copies of resources
        resources = {k: dataclasses.replace(v) for k, v in tmpl["resources"].items()}

        return cls(
            name=name,
            character_class=character_class,
            level=1,
            xp=0,
            abilities=dict(tmpl["abilities"]),
            skills=list(tmpl["skills"]),
            gold=tmpl["gold"],
            inventory=inventory,
            resources=resources,
        )


# ---------------------------------------------------------------------------
# Character — LEGACY compatibility shim
#
# DEPRECATED: New code should use ``CharacterRecord`` + ``DerivedSheet``
# instead.  This class is kept for backward compatibility with existing
# consumers (routes, save engine, agents, etc.) and will be removed in a
# future migration phase.
# ---------------------------------------------------------------------------


@dataclass
class Character:
    """A player character — the hero at the centre of the story.

    .. deprecated::
       Use ``CharacterRecord`` + ``DerivedSheet`` instead.  This class
       is kept for backward compatibility only.

    Every character has a name, appearance, personality, backstory,
    plot hooks, a class, level, experience points, six ability scores,
    skill proficiencies, hit points, armour class, and a list of
    carried items.

    Validation is performed in *__post_init__* so that invalid state
    is caught at construction time rather than silently corrupting the
    game later.
    """

    # -- Identity -----------------------------------------------------------
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
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

        tmpl = _LEGACY_CLASS_TEMPLATES[character_class]

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

    missing = set(STANDARD_ABILITIES) - set(abilities.keys())
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
