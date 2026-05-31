"""
World State Data Model — the SKELETON OF REALITY.

Holds the entire persistent game world state: locations, quests,
faction standings, active NPCs, inventory, and the DM's secret notes.

All dataclasses are serializable to/from JSON via to_dict() / from_dict()
so the Evil Wizard can save, load, and transmit the world state at will.
"""

from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


@dataclass
class Location:
    """A single location (room, area, region) in the game world.

    Each location has a unique ID, a human-readable name, a description,
    a mapping of exit directions to target location IDs, and an optional
    list of semantic tags (e.g. "dungeon", "forest", "safe_zone") that
    can be used by game systems for behaviour triggers.
    """

    id: str
    name: str
    description: str
    exits: dict[str, str] = field(default_factory=dict)
    #   ^ direction -> location_id, e.g. {"north": "forest_clearing"}
    tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Quest
# ---------------------------------------------------------------------------


@dataclass
class Quest:
    """A quest or task the player has been given.

    Status must be one of "active", "completed", or "failed".
    Objectives are ordered strings describing discrete sub-goals.
    """

    id: str
    name: str
    description: str
    status: str = "active"
    objectives: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate status on construction."""
        _validate_quest_status(self.status)


def _validate_quest_status(status: str) -> None:
    valid = {"active", "completed", "failed"}
    if status not in valid:
        raise ValueError(f"Invalid quest status {status!r}. Must be one of {valid}.")


# ---------------------------------------------------------------------------
# FactionStanding
# ---------------------------------------------------------------------------


@dataclass
class FactionStanding:
    """The player's reputation standing with a faction.

    *standing* ranges from -100 (mortal enemy) through 0 (neutral)
    to +100 (beloved ally).
    """

    faction_id: str
    name: str
    standing: int = 0

    def __post_init__(self) -> None:
        """Validate standing is within the allowed range."""
        _validate_standing(self.standing)


def _validate_standing(value: int) -> None:
    if value < -100 or value > 100:
        raise ValueError(f"Faction standing {value} is out of range [-100, 100].")


# ---------------------------------------------------------------------------
# DMNotes
# ---------------------------------------------------------------------------


@dataclass
class DMNotes:
    """The Dungeon Master's secret notes — plot threads, secrets, future plans.

    These are never revealed directly to the player and exist purely
    for the DM (or game master system) to track narrative state.
    """

    plot_threads: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    future_plans: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# WorldState
# ---------------------------------------------------------------------------


@dataclass
class WorldState:
    """The top-level container for the entire game world state.

    This is a "new game" by default — all fields have sensible defaults
    so you can create a fresh WorldState() and start playing immediately.

    The *character_id* field references a character by ID (loose coupling)
    rather than embedding the character object, keeping the world model
    independent of the character system.
    """

    version: str = "1.0"
    character_id: str | None = None
    character_name: str = ""
    current_location: str = "starting_village"
    active_npcs: dict[str, dict[str, Any]] = field(default_factory=dict)
    locations: dict[str, Location] = field(default_factory=dict)
    quests: dict[str, Quest] = field(default_factory=dict)
    faction_standings: dict[str, FactionStanding] = field(default_factory=dict)
    inventory: list[str] = field(default_factory=list)
    gold: int = 0
    dm_notes: DMNotes = field(default_factory=DMNotes)
    turn_count: int = 0
    established_facts: list[str] = field(default_factory=list)
    story_log: list[str] = field(default_factory=list)
    # Novel-like condensed story summaries, updated periodically by the summarizer
    story_summary: list[str] = field(default_factory=list)

    # Embedded character data for single-file save (not part of game logic)
    _character: dict[str, Any] | None = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert the entire state tree to a JSON-compatible dictionary.

        Nested dataclasses (Location, Quest, FactionStanding, DMNotes)
        are recursively converted to plain dicts via ``asdict()``.
        """
        result = asdict(self)
        # Remove duplicate flat fields that are already in _character
        # to prevent data duplication and divergence in save files
        if result.get("_character") is not None:
            # Strip only fields that are genuinely redundant with _character.
            # inventory and gold are WORLD-LEVEL runtime state, not character
            # duplicates — stripping them causes data loss on save/reload.
            for field in ("character_id", "character_name"):
                result.pop(field, None)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldState:
        """Reconstruct a ``WorldState`` (and all nested objects) from a dict.

        This is the inverse of :meth:`to_dict`.  Use it to load saved
        game state that arrived as JSON.
        """
        # Reconstruct nested dataclass instances from their dict forms.
        # Use field filtering for forward compatibility (Bug 2)
        # and type guards for robustness (Bug 3).

        # --- locations ---
        if not isinstance(data.get("locations"), dict):
            locations = {}
        else:
            loc_fields = {f.name for f in dataclasses.fields(Location)}
            locations = {
                lid: Location(**{k: v for k, v in loc.items() if k in loc_fields})
                for lid, loc in data["locations"].items()
            }

        # --- quests ---
        if not isinstance(data.get("quests"), dict):
            quests = {}
        else:
            q_fields = {f.name for f in dataclasses.fields(Quest)}
            quests = {
                qid: Quest(**{k: v for k, v in q.items() if k in q_fields})
                for qid, q in data["quests"].items()
            }

        # --- faction_standings ---
        if not isinstance(data.get("faction_standings"), dict):
            faction_standings = {}
        else:
            fs_fields = {f.name for f in dataclasses.fields(FactionStanding)}
            faction_standings = {
                fid: FactionStanding(**{k: v for k, v in fs.items() if k in fs_fields})
                for fid, fs in data["faction_standings"].items()
            }

        # --- dm_notes ---
        if not isinstance(data.get("dm_notes"), dict):
            dm_notes = DMNotes()
        else:
            dm_fields = {f.name for f in dataclasses.fields(DMNotes)}
            dm_notes = DMNotes(
                **{k: v for k, v in data["dm_notes"].items() if k in dm_fields}
            )

        # --- active_npcs ---
        if not isinstance(data.get("active_npcs"), dict):
            active_npcs = {}
        else:
            active_npcs = data["active_npcs"]

        # Type coercion for scalar fields (Bug 3)
        raw_tc = data.get("turn_count", 0)
        turn_count = int(raw_tc) if raw_tc is not None else 0
        version_raw = data.get("version", "1.0")
        version = str(version_raw) if version_raw is not None else "1.0"
        raw_gold = data.get("gold", 0)
        gold = int(raw_gold) if raw_gold is not None else 0

        # established_facts — ensure it's a list of strings
        raw_facts = data.get("established_facts", [])
        if isinstance(raw_facts, list):
            established_facts = [str(f) for f in raw_facts if isinstance(f, str)]
        else:
            established_facts = []

        # story_log — ensure it's a list of strings
        raw_story = data.get("story_log", [])
        if isinstance(raw_story, list):
            story_log = [str(s) for s in raw_story if isinstance(s, str)]
        else:
            story_log = []

        # story_summary — ensure it's a list of strings
        raw_story_summary = data.get("story_summary", [])
        if isinstance(raw_story_summary, list):
            story_summary = [str(s) for s in raw_story_summary if isinstance(s, str)]
        else:
            story_summary = []

        return cls(
            version=version,
            character_id=data.get("character_id"),
            character_name=str(data.get("character_name", "")),
            current_location=data.get("current_location", "starting_village"),
            active_npcs=active_npcs,
            locations=locations,
            quests=quests,
            faction_standings=faction_standings,
            inventory=data.get("inventory", []),
            gold=gold,
            dm_notes=dm_notes,
            turn_count=turn_count,
            established_facts=established_facts,
            story_log=story_log,
            story_summary=story_summary,
            _character=data.get("_character"),
        )
