"""
Item Data Model — THE SHINIES THAT HEROES CARRY.

Defines the ``Item`` dataclass, ``ItemType`` enum, mixin classes
(``PhysicalItem``, ``EquippableItem``, ``ConsumableItem``) that
provide type-specific property defaults, and a ``Container`` dataclass
for items that can hold other items.

Every item is serializable to/from JSON so the Evil Wizard can stash,
retrieve, and barter shinies across sessions.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# ItemType — WHAT KIND OF SHINY BE THIS?
# ---------------------------------------------------------------------------


class ItemType(Enum):
    """Categorical type of an item.

    Each variant describes the item's primary role in the game world.
    """

    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    TOOL = "tool"
    CONTAINER = "container"
    QUEST = "quest"
    MISC = "misc"


# ---------------------------------------------------------------------------
# Mixins — TEMPLATE COMPOSITION PATTERN
#
# Each mixin class provides a *default_properties()* classmethod that
# returns a dict of type-specific default values.  Callers merge these
# into the item's ``properties`` dict as needed.
#
# The mixins do NOT modify ``Item`` itself — they are pure templates.
# ---------------------------------------------------------------------------


class PhysicalItem:
    """Default properties for a physical item that has size and material."""

    @classmethod
    def default_properties(cls) -> dict[str, Any]:
        return {
            "size": "medium",
            "material": "iron",
        }


class EquippableItem:
    """Default properties for an item that can be worn or wielded."""

    @classmethod
    def default_properties(cls) -> dict[str, Any]:
        return {
            "slot": "hand",
            "armor_bonus": 0,
        }


class ConsumableItem:
    """Default properties for an item that is consumed on use."""

    @classmethod
    def default_properties(cls) -> dict[str, Any]:
        return {
            "effect": "none",
            "duration": 0,
        }


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------


@dataclass
class Item:
    """A single item — the smallest unit of shiny in the game.

    Every item has an identity (``id``), a ``name``, a ``quantity``,
    a categorical ``item_type``, arbitrary ``properties``, a
    ``description``, a ``weight`` (in pounds), and a gold ``value``.

    Parameters
    ----------
    id : str
        UUID string — auto-generated if not provided.
    name : str
        Display name of the item.
    quantity : int
        How many of this item are stacked together (default 1).
    item_type : ItemType
        Type category — determines how the item interacts with game
        mechanics (default ``MISC``).
    properties : dict[str, Any]
        Arbitrary key-value metadata such as ``{"damage": "1d8"}``.
    description : str
        Flavour text describing the item.
    weight : float
        Weight in pounds (default 0.0).
    value : int
        Gold value (default 0).
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    quantity: int = 1
    item_type: ItemType = ItemType.MISC
    properties: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    weight: float = 0.0
    value: int = 0

    def __post_init__(self) -> None:
        """Validate that *item_type* is a genuine ``ItemType``."""
        if not isinstance(self.item_type, ItemType):
            raise ValueError(
                f"Invalid item_type: {self.item_type!r}. "
                f"Must be an ItemType enum member."
            )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert the item to a JSON-compatible dictionary.

        The ``item_type`` enum is serialised as its string value so the
        result is plain JSON.
        """
        data = asdict(self)
        data["item_type"] = self.item_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Item:
        """Reconstruct an ``Item`` from a dictionary.

        This is the inverse of :meth:`to_dict`.  The ``item_type``
        string value is coerced back to an ``ItemType`` enum member.

        Unknown keys in *data* are silently ignored for forward
        compatibility.

        Parameters
        ----------
        data : dict[str, Any]
            A dictionary produced by :meth:`to_dict`.

        Returns
        -------
        Item
            A new ``Item`` instance with the deserialised fields.
        """
        data = dict(data)  # Shallow copy — don't mutate caller's dict.

        # Filter to known fields only (forward compatibility)
        known_fields = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known_fields}

        # Coerce item_type string → ItemType enum
        if "item_type" in filtered:
            raw = filtered["item_type"]
            if isinstance(raw, str):
                try:
                    filtered["item_type"] = ItemType(raw)
                except ValueError:
                    raise ValueError(
                        f"Invalid item_type value: {raw!r}. "
                        f"Must be one of {[e.value for e in ItemType]}."
                    )
            elif not isinstance(raw, ItemType):
                raise ValueError(
                    f"Invalid item_type: {raw!r}. "
                    f"Must be an ItemType or a valid string value."
                )

        return cls(**filtered)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


@dataclass
class Container:
    """A container item that can hold other items.

    Wraps an ``Item`` (the container itself — a backpack, chest, pouch,
    etc.) and a list of ``contents``.

    Parameters
    ----------
    item : Item
        The container's own item record (defaults to a generic container
        with ``item_type=CONTAINER``).
    contents : list[Item]
        Items currently stored inside this container.
    """

    item: Item = field(
        default_factory=lambda: Item(
            name="Container",
            item_type=ItemType.CONTAINER,
        )
    )
    contents: list[Item] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def weight(self) -> float:
        """The weight of the container itself (not including contents)."""
        return self.item.weight

    def total_weight(self) -> float:
        """Total weight of the container plus all contents.

        Returns
        -------
        float
            The sum of the container's own weight and the weight of
            every item nested inside.
        """
        return self.weight + sum(item.weight for item in self.contents)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Convert the container to a JSON-compatible dictionary.

        The result includes all ``Item`` fields (from the wrapped
        container item) plus a ``"contents"`` list.
        """
        data = self.item.to_dict()
        data["contents"] = [item.to_dict() for item in self.contents]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Container:
        """Reconstruct a ``Container`` from a dictionary.

        Parameters
        ----------
        data : dict[str, Any]
            A dictionary produced by :meth:`to_dict`.

        Returns
        -------
        Container
            A new ``Container`` instance with the deserialised fields.
        """
        data = dict(data)  # Shallow copy.
        contents_data = data.pop("contents", [])
        item = Item.from_dict(data)
        contents = [Item.from_dict(c) for c in contents_data]
        return cls(item=item, contents=contents)
