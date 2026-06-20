"""
Record-Keeper Entity Schemas — NPC, Place, Item profiles & change logs.

Each dataclass represents a persistent entity profile tracked by the
Record Keeper agent.  They are serializable to/from JSON via
``to_dict()`` / ``from_dict()`` so the Evil Wizard can store, retrieve,
and transmit entity records across turns.
"""

from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# NPCRecord
# ---------------------------------------------------------------------------


@dataclass
class NPCRecord:
    """Profile for a non-player character entity tracked over time.

    Fields capture appearance, personality, faction ties, relationships
    to other entities, mention history, accumulated notes, and an
    extensible metadata dict for ad-hoc information.
    """

    entity_id: str
    name: str
    entity_type: str = "npc"
    description: str = ""
    personality: str = ""
    faction: str = ""
    relationships: dict[str, str] = field(default_factory=dict)
    first_seen_turn: int = 0
    last_seen_turn: int = 0
    mention_count: int = 0
    notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NPCRecord:
        """Reconstruct from a dict, filtering to valid fields for forward compatibility."""
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid_fields})


# ---------------------------------------------------------------------------
# PlaceRecord
# ---------------------------------------------------------------------------


@dataclass
class PlaceRecord:
    """Profile for a place / location entity tracked over time.

    In addition to basic description and mention tracking, a PlaceRecord
    captures notable features (points of interest) and a list of
    connected place IDs for navigation context.
    """

    entity_id: str
    name: str
    entity_type: str = "place"
    description: str = ""
    tags: list[str] = field(default_factory=list)
    notable_features: list[str] = field(default_factory=list)
    connected_places: list[str] = field(default_factory=list)
    first_seen_turn: int = 0
    last_seen_turn: int = 0
    mention_count: int = 0
    notes: list[str] = field(default_factory=list)
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlaceRecord:
        """Reconstruct from a dict, filtering to valid fields for forward compatibility."""
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid_fields})


# ---------------------------------------------------------------------------
# ItemRecord
# ---------------------------------------------------------------------------


@dataclass
class ItemRecord:
    """Profile for an item entity tracked over time.

    Items track mechanical properties (via the free-form *properties*
    dict), origin story, ownership history, current holder, and the
    standard mention/notes fields.
    """

    entity_id: str
    name: str
    entity_type: str = "item"
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    origin: str = ""
    history: list[str] = field(default_factory=list)
    current_holder: str = ""
    first_seen_turn: int = 0
    last_seen_turn: int = 0
    mention_count: int = 0
    notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ItemRecord:
        """Reconstruct from a dict, filtering to valid fields for forward compatibility."""
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid_fields})


# ---------------------------------------------------------------------------
# EntityChangeLog
# ---------------------------------------------------------------------------


@dataclass
class EntityChangeLog:
    """A single change or reference event for an entity on a given turn.

    Used by the Record Keeper to log what happened to each entity over
    time, enabling audit trails and summarisation triggers.
    """

    turn: int
    entity_type: str
    entity_id: str
    change_type: str
    changed_fields: list[str] = field(default_factory=list)
    summary: str = ""

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityChangeLog:
        """Reconstruct from a dict, filtering to valid fields for forward compatibility."""
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid_fields})
