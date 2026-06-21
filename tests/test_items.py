"""Tests for the Item data model — Task 1.1 of the Character Sheet Overhaul."""

from __future__ import annotations

import pytest

from app.character.items import (
    ConsumableItem,
    Container,
    EquippableItem,
    Item,
    ItemType,
    PhysicalItem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(**overrides: object) -> Item:
    """Build an Item with safe defaults for quick test setup."""
    defaults: dict[str, object] = {
        "name": "Test Item",
        "item_type": ItemType.MISC,
    }
    defaults.update(overrides)
    return Item(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ItemType enum
# ---------------------------------------------------------------------------


class TestItemType:
    """ItemType must contain exactly the seven expected values."""

    def test_all_values_present(self) -> None:
        assert ItemType.WEAPON.value == "weapon"
        assert ItemType.ARMOR.value == "armor"
        assert ItemType.CONSUMABLE.value == "consumable"
        assert ItemType.TOOL.value == "tool"
        assert ItemType.CONTAINER.value == "container"
        assert ItemType.QUEST.value == "quest"
        assert ItemType.MISC.value == "misc"

    def test_enum_members(self) -> None:
        members = {e.name for e in ItemType}
        expected = {
            "WEAPON",
            "ARMOR",
            "CONSUMABLE",
            "TOOL",
            "CONTAINER",
            "QUEST",
            "MISC",
        }
        assert members == expected

    def test_enum_values_are_strings(self) -> None:
        for item_type in ItemType:
            assert isinstance(item_type.value, str)


# ---------------------------------------------------------------------------
# Item creation
# ---------------------------------------------------------------------------


class TestItemCreation:
    """Item dataclass must store all fields correctly."""

    def test_all_fields_stored(self) -> None:
        item = Item(
            name="Iron Sword",
            quantity=1,
            item_type=ItemType.WEAPON,
            properties={"damage": "1d8", "range": "melee"},
            description="A sturdy iron sword.",
            weight=3.5,
            value=10,
        )
        assert item.name == "Iron Sword"
        assert item.quantity == 1
        assert item.item_type == ItemType.WEAPON
        assert item.properties == {"damage": "1d8", "range": "melee"}
        assert item.description == "A sturdy iron sword."
        assert item.weight == 3.5
        assert item.value == 10

    def test_id_is_uuid_string(self) -> None:
        item = _make_item()
        assert isinstance(item.id, str)
        assert len(item.id) == 36  # standard UUID length
        assert item.id.count("-") == 4

    def test_unique_ids(self) -> None:
        item1 = _make_item()
        item2 = _make_item()
        assert item1.id != item2.id


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestItemDefaults:
    """Optional fields must fall back to sensible defaults."""

    def test_quantity_defaults_to_one(self) -> None:
        item = _make_item()
        assert item.quantity == 1

    def test_item_type_defaults_to_misc(self) -> None:
        item = Item(name="Thing")
        assert item.item_type == ItemType.MISC

    def test_properties_defaults_to_empty_dict(self) -> None:
        item = _make_item()
        assert item.properties == {}

    def test_description_defaults_to_empty_string(self) -> None:
        item = _make_item()
        assert item.description == ""

    def test_weight_defaults_to_zero(self) -> None:
        item = _make_item()
        assert item.weight == 0.0

    def test_value_defaults_to_zero(self) -> None:
        item = _make_item()
        assert item.value == 0

    def test_default_properties_are_independent(self) -> None:
        """Each Item must get its own properties dict, not a shared reference."""
        item1 = _make_item()
        item2 = _make_item()
        item1.properties["damage"] = "1d6"
        assert "damage" not in item2.properties


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestItemEdgeCases:
    """Boundary and edge-case values must be handled correctly."""

    def test_zero_weight(self) -> None:
        item = _make_item(weight=0.0)
        assert item.weight == 0.0

    def test_zero_quantity(self) -> None:
        item = _make_item(quantity=0)
        assert item.quantity == 0

    def test_empty_properties(self) -> None:
        item = _make_item(properties={})
        assert item.properties == {}

    def test_very_heavy_item(self) -> None:
        item = _make_item(weight=999999.0)
        assert item.weight == 999999.0

    def test_very_valuable_item(self) -> None:
        item = _make_item(value=1000000)
        assert item.value == 1000000

    def test_negative_weight(self) -> None:
        """Negative weight is technically allowed (the model does not
        validate it) — this test locks in current behaviour."""
        item = _make_item(weight=-5.0)
        assert item.weight == -5.0


# ---------------------------------------------------------------------------
# ItemType validation
# ---------------------------------------------------------------------------


class TestItemTypeValidation:
    """Invalid ItemType must be rejected at construction time."""

    def test_invalid_item_type_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_type"):
            Item(name="Bad", item_type="not_a_type")  # type: ignore[arg-type]

    def test_invalid_item_type_none_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_type"):
            Item(name="Bad", item_type=None)  # type: ignore[arg-type]

    def test_integer_item_type_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_type"):
            Item(name="Bad", item_type=42)  # type: ignore[arg-type]

    def test_valid_item_types_are_accepted(self) -> None:
        """Every member of ItemType must be accepted by the constructor."""
        for item_type in ItemType:
            item = Item(name="Valid", item_type=item_type)
            assert item.item_type == item_type


# ---------------------------------------------------------------------------
# Serialization — Item
# ---------------------------------------------------------------------------


class TestItemSerialization:
    """Item.to_dict() and Item.from_dict() must round-trip correctly."""

    def test_to_dict_returns_dict_with_all_fields(self) -> None:
        item = _make_item(
            name="Steel Dagger",
            quantity=2,
            item_type=ItemType.WEAPON,
            properties={"damage": "1d4"},
            description="A sharp steel dagger.",
            weight=1.0,
            value=5,
        )
        data = item.to_dict()
        assert isinstance(data, dict)
        assert data["name"] == "Steel Dagger"
        assert data["quantity"] == 2
        assert data["item_type"] == "weapon"
        assert data["properties"] == {"damage": "1d4"}
        assert data["description"] == "A sharp steel dagger."
        assert data["weight"] == 1.0
        assert data["value"] == 5
        assert isinstance(data["id"], str)

    def test_item_type_is_serialized_as_string(self) -> None:
        item = _make_item(item_type=ItemType.ARMOR)
        data = item.to_dict()
        assert data["item_type"] == "armor"
        assert isinstance(data["item_type"], str)

    def test_from_dict_reconstructs_item(self) -> None:
        data = {
            "id": "test-id-001",
            "name": "Health Potion",
            "quantity": 3,
            "item_type": "consumable",
            "properties": {"healing": "2d4+2"},
            "description": "Restores hit points.",
            "weight": 0.5,
            "value": 50,
        }
        item = Item.from_dict(data)
        assert item.id == "test-id-001"
        assert item.name == "Health Potion"
        assert item.quantity == 3
        assert item.item_type == ItemType.CONSUMABLE
        assert item.properties == {"healing": "2d4+2"}
        assert item.description == "Restores hit points."
        assert item.weight == 0.5
        assert item.value == 50

    def test_round_trip_preserves_all_fields(self) -> None:
        original = _make_item(
            name="Mage Staff",
            quantity=1,
            item_type=ItemType.WEAPON,
            properties={"damage": "1d6", "type": "bludgeoning"},
            description="A wooden staff imbued with arcane energy.",
            weight=4.0,
            value=100,
        )
        restored = Item.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.quantity == original.quantity
        assert restored.item_type == original.item_type
        assert restored.properties == original.properties
        assert restored.description == original.description
        assert restored.weight == original.weight
        assert restored.value == original.value

    def test_round_trip_default_item(self) -> None:
        """Even a default-constructed Item must survive serialization."""
        original = _make_item()
        restored = Item.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.item_type == original.item_type

    def test_from_dict_invalid_item_type_string_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid item_type value"):
            Item.from_dict({"item_type": "magical"})

    def test_from_dict_preserves_extra_fields_forward_compat(self) -> None:
        """Extra keys beyond known fields must be silently ignored."""
        data = _make_item().to_dict()
        data["favourite_colour"] = "red"
        data["version"] = 2
        item = Item.from_dict(data)
        assert item.name == "Test Item"
        assert item.item_type == ItemType.MISC


# ---------------------------------------------------------------------------
# Mixin default properties
# ---------------------------------------------------------------------------


class TestMixins:
    """Mixin classes must provide the correct default property dicts."""

    def test_physical_item_defaults(self) -> None:
        props = PhysicalItem.default_properties()
        assert props["size"] == "medium"
        assert props["material"] == "iron"
        assert len(props) == 2

    def test_equippable_item_defaults(self) -> None:
        props = EquippableItem.default_properties()
        assert props["slot"] == "hand"
        assert props["armor_bonus"] == 0
        assert len(props) == 2

    def test_consumable_item_defaults(self) -> None:
        props = ConsumableItem.default_properties()
        assert props["effect"] == "none"
        assert props["duration"] == 0
        assert len(props) == 2

    def test_mixin_merging_with_item_properties(self) -> None:
        """Mixins provide defaults that can be merged into an Item's
        properties dict without overwriting existing values."""
        item = Item(
            name="Fine Sword",
            item_type=ItemType.WEAPON,
            properties={"damage": "1d8"},
        )
        # Apply PhysicalItem defaults without overwriting existing keys
        merged = {**PhysicalItem.default_properties(), **item.properties}
        assert merged == {"size": "medium", "material": "iron", "damage": "1d8"}
        # Verify original item is unchanged
        assert item.properties == {"damage": "1d8"}

    def test_mixin_class_not_instantiated(self) -> None:
        """Mixins are templates — they don't need instances."""
        # Checking that default_properties is a classmethod, not a regular method
        assert callable(PhysicalItem.default_properties)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class TestContainer:
    """Container dataclass must manage a wrapped item and its contents."""

    def test_container_defaults(self) -> None:
        container = Container()
        assert container.item.item_type == ItemType.CONTAINER
        assert container.item.name == "Container"
        assert container.contents == []

    def test_container_with_custom_item(self) -> None:
        backpack = Item(
            name="Leather Backpack", weight=2.0, value=5, item_type=ItemType.CONTAINER
        )
        container = Container(item=backpack, contents=[])
        assert container.item.name == "Leather Backpack"
        assert container.weight == 2.0

    def test_total_weight_empty_container(self) -> None:
        container = Container(
            item=Item(name="Pouch", weight=0.5, item_type=ItemType.CONTAINER),
        )
        assert container.total_weight() == 0.5

    def test_total_weight_with_contents(self) -> None:
        container = Container(
            item=Item(name="Backpack", weight=2.0, item_type=ItemType.CONTAINER),
            contents=[
                Item(name="Ration", weight=0.5, quantity=5),
                Item(name="Torch", weight=1.0),
                Item(name="Potion", weight=0.5),
            ],
        )
        expected = 2.0 + 0.5 + 1.0 + 0.5
        assert container.total_weight() == expected

    def test_container_weight_property(self) -> None:
        container = Container(
            item=Item(name="Chest", weight=10.0, item_type=ItemType.CONTAINER),
            contents=[
                Item(name="Gold Coins", weight=2.0),
                Item(name="Silver Coins", weight=1.5),
            ],
        )
        assert container.weight == 10.0
        assert container.total_weight() == 10.0 + 2.0 + 1.5

    def test_container_serialization_round_trip(self) -> None:
        original = Container(
            item=Item(
                name="Magic Bag", weight=1.0, value=50, item_type=ItemType.CONTAINER
            ),
            contents=[
                Item(name="Health Potion", weight=0.5, value=20),
                Item(name="Mana Potion", weight=0.5, value=30),
            ],
        )
        data = original.to_dict()
        assert isinstance(data, dict)
        assert data["name"] == "Magic Bag"
        assert data["item_type"] == "container"
        assert len(data["contents"]) == 2

        restored = Container.from_dict(data)
        assert restored.item.name == original.item.name
        assert restored.item.weight == original.item.weight
        assert restored.item.item_type == ItemType.CONTAINER
        assert len(restored.contents) == len(original.contents)
        for restored_content, original_content in zip(
            restored.contents, original.contents, strict=True
        ):
            assert restored_content.name == original_content.name
            assert restored_content.weight == original_content.weight

    def test_container_default_serialization(self) -> None:
        """Default Container must survive serialization round-trip."""
        original = Container()
        data = original.to_dict()
        restored = Container.from_dict(data)
        assert restored.item.name == "Container"
        assert restored.item.item_type == ItemType.CONTAINER
        assert restored.contents == []

    def test_container_nested_weight(self) -> None:
        """total_weight must include weights of all items in contents,
        even when some items have zero weight."""
        container = Container(
            item=Item(name="Box", weight=1.0, item_type=ItemType.CONTAINER),
            contents=[
                Item(name="Feather", weight=0.0),
                Item(name="Rock", weight=2.0),
            ],
        )
        assert container.total_weight() == 3.0


# ---------------------------------------------------------------------------
# Container — Edge cases
# ---------------------------------------------------------------------------


class TestContainerEdgeCases:
    """Edge cases for Container behaviour."""

    def test_container_with_many_items(self) -> None:
        """A container must handle a large number of items."""
        contents = [Item(name=f"Item-{i}", weight=0.1) for i in range(100)]
        container = Container(
            item=Item(name="Big Bag", weight=1.0, item_type=ItemType.CONTAINER),
            contents=contents,
        )
        assert container.total_weight() == 1.0 + 100 * 0.1

    def test_container_no_contents_serialization(self) -> None:
        """Container with an empty contents list must serialize correctly."""
        container = Container(
            item=Item(name="Empty Sack", weight=0.5, item_type=ItemType.CONTAINER),
            contents=[],
        )
        data = container.to_dict()
        assert data["contents"] == []
        restored = Container.from_dict(data)
        assert restored.contents == []
