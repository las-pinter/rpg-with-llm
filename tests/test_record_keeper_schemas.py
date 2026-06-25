"""Comprehensive tests for Record-Keeper Entity Schemas.

Covers NPCRecord, PlaceRecord, ItemRecord, and EntityChangeLog —
serialisation round-trips, default values, edge cases, forward
compatibility, and mutable-default isolation.
"""

from __future__ import annotations

import copy
import dataclasses
import json

import pytest

from app.agents.record_keeper_schemas import (
    EntityChangeLog,
    ItemRecord,
    NPCRecord,
    PlaceRecord,
)

# ===================================================================
# Helpers
# ===================================================================

LONG_DESCRIPTION = (
    "A very long description that exceeds typical boundaries to verify "
    "that the schema handles long text content without truncation or "
    "corruption. " * 50
).strip()

UNICODE_NAME = "Günther von Rätselhaft—Ägir's Björk 🧝"


def _assert_round_trip(instance, cls):
    """Assert that ``instance`` survives to_dict → from_dict unchanged."""
    data = instance.to_dict()
    restored = cls.from_dict(data)
    assert restored is not instance, "Must produce a new object, not the same reference"
    assert restored == instance, (
        f"Round-trip mismatch:\n  original: {instance!r}\n  restored: {restored!r}"
    )


# ===================================================================
# NPCRecord
# ===================================================================


class TestNPCRecord:
    """Tests for NPCRecord — NPC entity profile."""

    # -- 1. Round-trip --------------------------------------------------

    def test_full_npc_round_trip(self):
        """A fully populated NPCRecord survives to_dict → from_dict."""
        record = NPCRecord(
            entity_id="npc_draven",
            name="Draven Blackthorn",
            entity_type="npc",
            description="A brooding dark elf ranger.",
            personality="Brooding, quiet, vengeful.",
            faction="Dark Rangers",
            relationships={
                "npc_velvet": "ally",
                "npc_ironfoot": "rival",
            },
            first_seen_turn=3,
            last_seen_turn=27,
            mention_count=14,
            notes=[
                "Introduced in the Shadowfen",
                "Knows the location of the Soulstone",
            ],
            tags=["elf", "ranger", "dark"],
            is_active=True,
            metadata={"alignment": "chaotic_neutral", "age": 342},
        )
        _assert_round_trip(record, NPCRecord)

    def test_minimal_npc_round_trip(self):
        """An NPCRecord with only required fields survives round-trip."""
        record = NPCRecord(entity_id="npc_01", name="Goblin")
        _assert_round_trip(record, NPCRecord)

    # -- 2. Default values ----------------------------------------------

    def test_default_entity_type_is_npc(self):
        """Default entity_type must be 'npc'."""
        record = NPCRecord(entity_id="npc_01", name="Test")
        assert record.entity_type == "npc"

    def test_default_string_fields_are_empty(self):
        """description, personality, faction must default to empty string."""
        record = NPCRecord(entity_id="npc_01", name="Test")
        assert record.description == ""
        assert record.personality == ""
        assert record.faction == ""

    def test_default_numeric_fields_are_zero(self):
        """first_seen_turn, last_seen_turn, mention_count must default to 0."""
        record = NPCRecord(entity_id="npc_01", name="Test")
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0

    def test_default_list_fields_are_empty(self):
        """notes and tags must default to empty list."""
        record = NPCRecord(entity_id="npc_01", name="Test")
        assert record.notes == []
        assert record.tags == []

    def test_default_dict_fields_are_empty(self):
        """relationships and metadata must default to empty dict."""
        record = NPCRecord(entity_id="npc_01", name="Test")
        assert record.relationships == {}
        assert record.metadata == {}

    def test_default_is_active_is_true(self):
        """is_active must default to True."""
        record = NPCRecord(entity_id="npc_01", name="Test")
        assert record.is_active is True

    # -- 3. Edge cases --------------------------------------------------

    def test_unicode_name(self):
        """NPC names with unicode characters must survive round-trip."""
        record = NPCRecord(
            entity_id="npc_unicode",
            name=UNICODE_NAME,
        )
        _assert_round_trip(record, NPCRecord)

    def test_very_long_description(self):
        """Very long descriptions must survive round-trip without truncation."""
        record = NPCRecord(
            entity_id="npc_long",
            name="Long Talker",
            description=LONG_DESCRIPTION,
        )
        _assert_round_trip(record, NPCRecord)
        assert len(record.description) == len(LONG_DESCRIPTION)

    def test_empty_notes_list(self):
        """An explicit empty notes list must remain empty after round-trip."""
        record = NPCRecord(
            entity_id="npc_empty_notes",
            name="Silent Bob",
            notes=[],
        )
        _assert_round_trip(record, NPCRecord)
        assert record.notes == []

    def test_npc_with_is_active_false(self):
        """is_active=False must survive round-trip."""
        record = NPCRecord(
            entity_id="npc_dead",
            name="Deceased Adventurer",
            is_active=False,
        )
        _assert_round_trip(record, NPCRecord)

    def test_npc_with_rich_metadata(self):
        """metadata dict with mixed types must survive round-trip."""
        record = NPCRecord(
            entity_id="npc_rich",
            name="Rich Data",
            metadata={
                "level": 5,
                "stats": {"str": 10, "dex": 14},
                "inventory": ["potion", "scroll"],
                "is_boss": True,
                "tags": None,
            },
        )
        _assert_round_trip(record, NPCRecord)

    def test_npc_with_many_relationships(self):
        """A large relationships dict must survive round-trip."""
        rels = {f"npc_{i}": f"relation_{i}" for i in range(100)}
        record = NPCRecord(
            entity_id="npc_popular",
            name="Popular Person",
            relationships=rels,
        )
        _assert_round_trip(record, NPCRecord)

    def test_npc_with_zero_mention_count(self):
        """mention_count must be zero by default and persist."""
        record = NPCRecord(
            entity_id="npc_zero",
            name="Never Mentioned",
            mention_count=0,
        )
        assert record.mention_count == 0
        _assert_round_trip(record, NPCRecord)

    # -- 4. Forward compatibility (extra keys dropped) ------------------

    def test_from_dict_ignores_extra_keys(self):
        """Extra unknown keys in the dict must be silently dropped."""
        data = {
            "entity_id": "npc_fwd",
            "name": "Forward Compat",
            "description": "Works with extra fields.",
            "favorite_color": "red",  # not a real field
            "_secret": "should be ignored",
            "non_existent_field": 42,
        }
        record = NPCRecord.from_dict(data)
        assert record.entity_id == "npc_fwd"
        assert record.name == "Forward Compat"
        assert record.description == "Works with extra fields."
        # Defaults for fields not provided
        assert record.personality == ""
        assert record.faction == ""
        assert record.relationships == {}
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0
        assert record.notes == []
        assert record.tags == []
        assert record.is_active is True
        assert record.metadata == {}
        # There must be no extra attributes on the object
        assert not hasattr(record, "favorite_color")
        assert not hasattr(record, "_secret")
        assert not hasattr(record, "non_existent_field")

    # -- 5. Mutable default isolation -----------------------------------

    def test_mutable_defaults_are_isolated_between_instances(self):
        """Each NPCRecord must have its own lists/dicts — no shared references."""
        a = NPCRecord(entity_id="npc_a", name="A")
        b = NPCRecord(entity_id="npc_b", name="B")

        # Mutate a's lists and dicts
        a.notes.append("a note")
        a.tags.append("tag_a")
        a.relationships["key"] = "value"
        a.metadata["key"] = "value"

        # b must be untouched
        assert b.notes == []
        assert b.tags == []
        assert b.relationships == {}
        assert b.metadata == {}

    def test_mutable_defaults_isolated_after_from_dict(self):
        """Instances created via from_dict must also have independent defaults."""
        base = {"entity_id": "npc_iso", "name": "Isolation Test"}
        a = NPCRecord.from_dict(base)
        b = NPCRecord.from_dict(base)

        a.notes.append("owned by a")
        assert b.notes == []

    # -- 6. JSON serialisability ----------------------------------------

    def test_to_dict_is_json_serializable(self):
        """to_dict() output must survive json.dumps / json.loads round-trip."""
        record = NPCRecord(
            entity_id="npc_json",
            name="JSON Ready",
            description="Can be serialized to JSON.",
            personality="Cooperative",
            faction="Testers",
            relationships={"npc_helper": "friend"},
            first_seen_turn=1,
            last_seen_turn=5,
            mention_count=3,
            notes=["Test note"],
            tags=["test"],
            is_active=True,
            metadata={"test_flag": True, "count": 42},
        )
        dumped = json.dumps(record.to_dict())
        loaded = json.loads(dumped)
        restored = NPCRecord.from_dict(loaded)
        assert restored == record

    # -- 7. from_dict with partial data ---------------------------------

    def test_from_dict_with_empty_dict_produces_defaults(self):
        """Calling from_dict({}) must produce a record with defaults for all fields
        except the required ones — and should raise TypeError for missing required."""
        # Missing required fields entity_id and name -> TypeError
        with pytest.raises(TypeError, match="missing.*required.*argument"):
            NPCRecord.from_dict({})

    def test_from_dict_with_only_required_fields(self):
        """Providing only required fields must work and rest are defaults."""
        record = NPCRecord.from_dict({"entity_id": "npc_min", "name": "Minimal"})
        assert record.entity_id == "npc_min"
        assert record.name == "Minimal"
        assert record.entity_type == "npc"
        assert record.description == ""
        assert record.personality == ""
        assert record.faction == ""
        assert record.relationships == {}
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0
        assert record.notes == []
        assert record.tags == []
        assert record.is_active is True
        assert record.metadata == {}

    # -- 8. Equality ----------------------------------------------------

    def test_equality(self):
        """Two NPCRecords with same values must be equal."""
        a = NPCRecord(entity_id="npc_eq", name="Equal", description="Same")
        b = NPCRecord(entity_id="npc_eq", name="Equal", description="Same")
        assert a == b
        assert not (a != b)

    def test_inequality(self):
        """Two NPCRecords with different values must not be equal."""
        a = NPCRecord(entity_id="npc_a", name="A")
        b = NPCRecord(entity_id="npc_b", name="B")
        assert a != b


# ===================================================================
# PlaceRecord
# ===================================================================


class TestPlaceRecord:
    """Tests for PlaceRecord — place / location entity profile."""

    # -- 1. Round-trip --------------------------------------------------

    def test_full_place_round_trip(self):
        """A fully populated PlaceRecord survives to_dict → from_dict."""
        record = PlaceRecord(
            entity_id="place_blackmarsh",
            name="Blackmarsh Swamp",
            entity_type="place",
            description="A fetid, misty swamp teeming with dangerous creatures.",
            tags=["swamp", "dangerous", "poison"],
            notable_features=[
                "The Weeping Willow",
                "Abandoned Shrine",
                "Quicksand Pit",
            ],
            connected_places=["place_darkwood", "place_murkwater"],
            first_seen_turn=1,
            last_seen_turn=42,
            mention_count=18,
            notes=["Party was ambushed here by lizardfolk"],
            is_active=True,
            metadata={"region": "southlands", "biome": "swamp", "danger_level": 7},
        )
        _assert_round_trip(record, PlaceRecord)

    def test_minimal_place_round_trip(self):
        """A PlaceRecord with only required fields survives round-trip."""
        record = PlaceRecord(entity_id="place_01", name="Forest Clearing")
        _assert_round_trip(record, PlaceRecord)

    # -- 2. Default values ----------------------------------------------

    def test_default_entity_type_is_place(self):
        """Default entity_type must be 'place'."""
        record = PlaceRecord(entity_id="place_01", name="Test")
        assert record.entity_type == "place"

    def test_default_string_fields_are_empty(self):
        """description must default to empty string."""
        record = PlaceRecord(entity_id="place_01", name="Test")
        assert record.description == ""

    def test_default_list_fields_are_empty(self):
        """tags, notable_features, connected_places, notes default to empty list."""
        record = PlaceRecord(entity_id="place_01", name="Test")
        assert record.tags == []
        assert record.notable_features == []
        assert record.connected_places == []
        assert record.notes == []

    def test_default_numeric_fields_are_zero(self):
        """first_seen_turn, last_seen_turn, mention_count must default to 0."""
        record = PlaceRecord(entity_id="place_01", name="Test")
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0

    def test_default_is_active_is_true(self):
        """is_active must default to True."""
        record = PlaceRecord(entity_id="place_01", name="Test")
        assert record.is_active is True

    def test_default_metadata_is_empty(self):
        """metadata must default to empty dict."""
        record = PlaceRecord(entity_id="place_01", name="Test")
        assert record.metadata == {}

    # -- 3. Edge cases --------------------------------------------------

    def test_unicode_name(self):
        """Place names with unicode characters must survive round-trip."""
        record = PlaceRecord(
            entity_id="place_unicode",
            name=UNICODE_NAME,
        )
        _assert_round_trip(record, PlaceRecord)

    def test_very_long_description(self):
        """Very long descriptions must survive round-trip without truncation."""
        record = PlaceRecord(
            entity_id="place_long",
            name="Expansive Realm",
            description=LONG_DESCRIPTION,
        )
        _assert_round_trip(record, PlaceRecord)
        assert len(record.description) == len(LONG_DESCRIPTION)

    def test_empty_notable_features(self):
        """An explicit empty notable_features must survive round-trip."""
        record = PlaceRecord(
            entity_id="place_empty_features",
            name="Featureless Plain",
            notable_features=[],
        )
        _assert_round_trip(record, PlaceRecord)
        assert record.notable_features == []

    def test_empty_connected_places(self):
        """An explicit empty connected_places list must survive round-trip."""
        record = PlaceRecord(
            entity_id="place_isolated",
            name="Isolated Tower",
            connected_places=[],
        )
        _assert_round_trip(record, PlaceRecord)
        assert record.connected_places == []

    def test_many_connected_places(self):
        """A large connected_places list must survive round-trip."""
        places = [f"place_{i}" for i in range(200)]
        record = PlaceRecord(
            entity_id="place_hub",
            name="Central Hub",
            connected_places=places,
        )
        _assert_round_trip(record, PlaceRecord)
        assert len(record.connected_places) == 200

    def test_place_is_active_false(self):
        """is_active=False must survive round-trip."""
        record = PlaceRecord(
            entity_id="place_ruined",
            name="Ruined Fortress",
            is_active=False,
        )
        _assert_round_trip(record, PlaceRecord)

    def test_place_with_rich_metadata(self):
        """metadata dict with mixed types must survive round-trip."""
        record = PlaceRecord(
            entity_id="place_rich",
            name="Rich Metadata Place",
            metadata={
                "population": 0,
                "has_inn": True,
                "guards": 5,
                "resources": {"wood": "abundant", "stone": "scarce"},
                "npc_ids": ["npc_01", "npc_02"],
            },
        )
        _assert_round_trip(record, PlaceRecord)

    # -- 4. Forward compatibility (extra keys dropped) ------------------

    def test_from_dict_ignores_extra_keys(self):
        """Extra unknown keys in the dict must be silently dropped."""
        data = {
            "entity_id": "place_fwd",
            "name": "Forward Compat Place",
            "description": "Works with extra fields.",
            "elevation": 1500,  # not a real field
            "climate": "temperate",  # not a real field
        }
        record = PlaceRecord.from_dict(data)
        assert record.entity_id == "place_fwd"
        assert record.name == "Forward Compat Place"
        assert record.description == "Works with extra fields."
        # Defaults
        assert record.tags == []
        assert record.notable_features == []
        assert record.connected_places == []
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0
        assert record.notes == []
        assert record.is_active is True
        assert record.metadata == {}
        # Extra fields must not leak through
        assert not hasattr(record, "elevation")
        assert not hasattr(record, "climate")

    def test_from_dict_with_extra_keys_and_defaults(self):
        """Extra keys must not interfere with default values for real fields."""
        data = {
            "entity_id": "place_extra",
            "name": "Extra Test",
            "not_a_real_field": "garbage",
            "another_bogus": [1, 2, 3],
        }
        record = PlaceRecord.from_dict(data)
        # Defaults must still hold
        assert record.tags == []
        assert record.notable_features == []
        assert record.connected_places == []
        assert record.notes == []
        assert record.metadata == {}

    # -- 5. Mutable default isolation -----------------------------------

    def test_mutable_defaults_are_isolated_between_instances(self):
        """Each PlaceRecord must have its own lists/dicts — no shared references."""
        a = PlaceRecord(entity_id="place_a", name="A")
        b = PlaceRecord(entity_id="place_b", name="B")

        a.tags.append("tag_a")
        a.notable_features.append("feature_a")
        a.connected_places.append("place_a_connect")
        a.notes.append("note_a")
        a.metadata["key"] = "value"

        assert b.tags == []
        assert b.notable_features == []
        assert b.connected_places == []
        assert b.notes == []
        assert b.metadata == {}

    # -- 6. JSON serialisability ----------------------------------------

    def test_to_dict_is_json_serializable(self):
        """to_dict() output must survive json.dumps / json.loads round-trip."""
        record = PlaceRecord(
            entity_id="place_json",
            name="JSON Place",
            description="JSON test.",
            tags=["test"],
            notable_features=["Fountain"],
            connected_places=["place_other"],
            mention_count=7,
            metadata={"key": "value"},
        )
        dumped = json.dumps(record.to_dict())
        loaded = json.loads(dumped)
        restored = PlaceRecord.from_dict(loaded)
        assert restored == record

    # -- 7. from_dict with partial data ---------------------------------

    def test_from_dict_with_only_required_fields(self):
        """Providing only required fields must work and rest are defaults."""
        record = PlaceRecord.from_dict({"entity_id": "place_min", "name": "Minimal"})
        assert record.entity_id == "place_min"
        assert record.name == "Minimal"
        assert record.entity_type == "place"
        assert record.description == ""
        assert record.tags == []
        assert record.notable_features == []
        assert record.connected_places == []
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0
        assert record.notes == []
        assert record.is_active is True
        assert record.metadata == {}

    def test_from_dict_missing_required_entity_id_raises(self):
        """Missing entity_id in from_dict must raise TypeError."""
        with pytest.raises(TypeError):
            PlaceRecord.from_dict({"name": "No ID"})

    def test_from_dict_missing_required_name_raises(self):
        """Missing name in from_dict must raise TypeError."""
        with pytest.raises(TypeError):
            PlaceRecord.from_dict({"entity_id": "no_name"})

    # -- 8. Equality ----------------------------------------------------

    def test_equality(self):
        """Two PlaceRecords with same values must be equal."""
        a = PlaceRecord(entity_id="place_eq", name="Equal Place")
        b = PlaceRecord(entity_id="place_eq", name="Equal Place")
        assert a == b

    def test_inequality(self):
        """Two PlaceRecords with different values must not be equal."""
        a = PlaceRecord(entity_id="place_a", name="A")
        b = PlaceRecord(entity_id="place_b", name="B")
        assert a != b


# ===================================================================
# ItemRecord
# ===================================================================


class TestItemRecord:
    """Tests for ItemRecord — item entity profile."""

    # -- 1. Round-trip --------------------------------------------------

    def test_full_item_round_trip(self):
        """A fully populated ItemRecord survives to_dict → from_dict."""
        record = ItemRecord(
            entity_id="item_soulstone",
            name="Soulstone of Ahn'Qiraj",
            entity_type="item",
            description="A pulsating crystal that radiates dark energy.",
            properties={
                "type": "artifact",
                "rarity": "legendary",
                "magical": True,
                "charges": 5,
                "effects": ["soul_bind", "dark_vision"],
            },
            origin="Forged in the Heart of Ahn'Qiraj by the Twilight Hammer",
            history=[
                "Created by Twilight Hammer cultists",
                "Stolen by the adventurer party",
                "Currently held by the party wizard",
            ],
            current_holder="npc_wizard",
            first_seen_turn=12,
            last_seen_turn=45,
            mention_count=23,
            notes=[
                "Key item for the main quest",
                "Can be used to open the Dark Portal",
            ],
            tags=["artifact", "quest_item", "magical"],
            is_active=True,
            metadata={"weight_kg": 0.5, "value_gp": 5000},
        )
        _assert_round_trip(record, ItemRecord)

    def test_minimal_item_round_trip(self):
        """An ItemRecord with only required fields survives round-trip."""
        record = ItemRecord(entity_id="item_01", name="Wooden Stick")
        _assert_round_trip(record, ItemRecord)

    # -- 2. Default values ----------------------------------------------

    def test_default_entity_type_is_item(self):
        """Default entity_type must be 'item'."""
        record = ItemRecord(entity_id="item_01", name="Test")
        assert record.entity_type == "item"

    def test_default_string_fields_are_empty(self):
        """description, origin, current_holder must default to empty string."""
        record = ItemRecord(entity_id="item_01", name="Test")
        assert record.description == ""
        assert record.origin == ""
        assert record.current_holder == ""

    def test_default_list_fields_are_empty(self):
        """history, notes, tags must default to empty list."""
        record = ItemRecord(entity_id="item_01", name="Test")
        assert record.history == []
        assert record.notes == []
        assert record.tags == []

    def test_default_dict_fields_are_empty(self):
        """properties and metadata must default to empty dict."""
        record = ItemRecord(entity_id="item_01", name="Test")
        assert record.properties == {}
        assert record.metadata == {}

    def test_default_numeric_fields_are_zero(self):
        """first_seen_turn, last_seen_turn, mention_count must default to 0."""
        record = ItemRecord(entity_id="item_01", name="Test")
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0

    def test_default_is_active_is_true(self):
        """is_active must default to True."""
        record = ItemRecord(entity_id="item_01", name="Test")
        assert record.is_active is True

    # -- 3. Edge cases --------------------------------------------------

    def test_unicode_name(self):
        """Item names with unicode characters must survive round-trip."""
        record = ItemRecord(
            entity_id="item_unicode",
            name=UNICODE_NAME,
        )
        _assert_round_trip(record, ItemRecord)

    def test_very_long_description(self):
        """Very long descriptions must survive round-trip without truncation."""
        record = ItemRecord(
            entity_id="item_long",
            name="Long Described Item",
            description=LONG_DESCRIPTION,
        )
        _assert_round_trip(record, ItemRecord)
        assert len(record.description) == len(LONG_DESCRIPTION)

    def test_empty_history_list(self):
        """An explicit empty history list must survive round-trip."""
        record = ItemRecord(
            entity_id="item_no_history",
            name="Brand New Item",
            history=[],
        )
        _assert_round_trip(record, ItemRecord)
        assert record.history == []

    def test_item_with_no_current_holder(self):
        """current_holder can be empty string and must survive round-trip."""
        record = ItemRecord(
            entity_id="item_free",
            name="Unclaimed Treasure",
            current_holder="",
        )
        _assert_round_trip(record, ItemRecord)

    def test_item_is_active_false(self):
        """is_active=False must survive round-trip."""
        record = ItemRecord(
            entity_id="item_destroyed",
            name="Destroyed Artifact",
            is_active=False,
        )
        _assert_round_trip(record, ItemRecord)

    def test_item_with_nested_properties(self):
        """Complex nested properties dict must survive round-trip."""
        record = ItemRecord(
            entity_id="item_complex",
            name="Complex Item",
            properties={
                "stats": {"damage": "2d8", "type": "piercing"},
                "requirements": {"level": 10, "class": "warrior"},
                "enchantments": [
                    {"name": "flame", "damage": "1d6"},
                    {"name": "frost", "damage": "1d4"},
                ],
            },
        )
        _assert_round_trip(record, ItemRecord)

    def test_item_with_extensive_history(self):
        """A long history list must survive round-trip."""
        history = [f"Event number {i}" for i in range(500)]
        record = ItemRecord(
            entity_id="item_historic",
            name="Ancient Relic",
            history=history,
        )
        _assert_round_trip(record, ItemRecord)
        assert len(record.history) == 500

    # -- 4. Forward compatibility (extra keys dropped) ------------------

    def test_from_dict_ignores_extra_keys(self):
        """Extra unknown keys in the dict must be silently dropped."""
        data = {
            "entity_id": "item_fwd",
            "name": "Forward Compat Item",
            "description": "Works with extra fields.",
            "weight": 2.5,  # not a real field
            "value": 100,  # not a real field
            "unextra_field": "drop me",
        }
        record = ItemRecord.from_dict(data)
        assert record.entity_id == "item_fwd"
        assert record.name == "Forward Compat Item"
        assert record.description == "Works with extra fields."
        # Defaults
        assert record.properties == {}
        assert record.origin == ""
        assert record.history == []
        assert record.current_holder == ""
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0
        assert record.notes == []
        assert record.tags == []
        assert record.is_active is True
        assert record.metadata == {}
        # Extra fields must not leak through
        assert not hasattr(record, "weight")
        assert not hasattr(record, "value")
        assert not hasattr(record, "unextra_field")

    # -- 5. Mutable default isolation -----------------------------------

    def test_mutable_defaults_are_isolated_between_instances(self):
        """Each ItemRecord must have its own lists/dicts — no shared references."""
        a = ItemRecord(entity_id="item_a", name="A")
        b = ItemRecord(entity_id="item_b", name="B")

        a.properties["key"] = "value"
        a.history.append("event_a")
        a.notes.append("note_a")
        a.tags.append("tag_a")
        a.metadata["key"] = "value"

        assert b.properties == {}
        assert b.history == []
        assert b.notes == []
        assert b.tags == []
        assert b.metadata == {}

    # -- 6. JSON serialisability ----------------------------------------

    def test_to_dict_is_json_serializable(self):
        """to_dict() output must survive json.dumps / json.loads round-trip."""
        record = ItemRecord(
            entity_id="item_json",
            name="JSON Item",
            description="JSON test.",
            properties={"damage": "1d8"},
            history=["Created"],
            tags=["weapon"],
            metadata={"weight": 3},
        )
        dumped = json.dumps(record.to_dict())
        loaded = json.loads(dumped)
        restored = ItemRecord.from_dict(loaded)
        assert restored == record

    # -- 7. from_dict with partial data ---------------------------------

    def test_from_dict_with_only_required_fields(self):
        """Providing only required fields must work and rest are defaults."""
        record = ItemRecord.from_dict({"entity_id": "item_min", "name": "Minimal"})
        assert record.entity_id == "item_min"
        assert record.name == "Minimal"
        assert record.entity_type == "item"
        assert record.description == ""
        assert record.properties == {}
        assert record.origin == ""
        assert record.history == []
        assert record.current_holder == ""
        assert record.first_seen_turn == 0
        assert record.last_seen_turn == 0
        assert record.mention_count == 0
        assert record.notes == []
        assert record.tags == []
        assert record.is_active is True
        assert record.metadata == {}

    # -- 8. Equality ----------------------------------------------------

    def test_equality(self):
        """Two ItemRecords with same values must be equal."""
        a = ItemRecord(entity_id="item_eq", name="Equal Item")
        b = ItemRecord(entity_id="item_eq", name="Equal Item")
        assert a == b

    def test_inequality(self):
        """Two ItemRecords with different values must not be equal."""
        a = ItemRecord(entity_id="item_a", name="A")
        b = ItemRecord(entity_id="item_b", name="B")
        assert a != b


# ===================================================================
# EntityChangeLog
# ===================================================================


class TestEntityChangeLog:
    """Tests for EntityChangeLog — change tracking record."""

    # -- 1. Round-trip --------------------------------------------------

    def test_full_changelog_round_trip(self):
        """A fully populated EntityChangeLog survives to_dict → from_dict."""
        record = EntityChangeLog(
            turn=7,
            entity_type="npc",
            entity_id="npc_draven",
            change_type="updated",
            changed_fields=["description", "faction", "last_seen_turn"],
            summary="Updated Draven's faction to Dark Rangers and advanced last_seen.",
        )
        _assert_round_trip(record, EntityChangeLog)

    def test_minimal_changelog_round_trip(self):
        """An EntityChangeLog with only required fields survives round-trip."""
        record = EntityChangeLog(
            turn=1,
            entity_type="npc",
            entity_id="npc_01",
            change_type="created",
        )
        _assert_round_trip(record, EntityChangeLog)

    # -- 2. Default values ----------------------------------------------

    def test_default_changed_fields_is_empty_list(self):
        """changed_fields must default to empty list."""
        record = EntityChangeLog(
            turn=1, entity_type="npc", entity_id="npc_01", change_type="created"
        )
        assert record.changed_fields == []

    def test_default_summary_is_empty_string(self):
        """summary must default to empty string."""
        record = EntityChangeLog(
            turn=1, entity_type="npc", entity_id="npc_01", change_type="created"
        )
        assert record.summary == ""

    # -- 3. Metadata correctness ----------------------------------------

    def test_changelog_tracks_turn_correctly(self):
        """The turn field must store and return the correct turn number."""
        record = EntityChangeLog(
            turn=42, entity_type="place", entity_id="place_01", change_type="seen"
        )
        assert record.turn == 42

    def test_changelog_tracks_entity_type_correctly(self):
        """The entity_type field must store and return the correct type."""
        record = EntityChangeLog(
            turn=1, entity_type="item", entity_id="item_01", change_type="created"
        )
        assert record.entity_type == "item"

    def test_changelog_tracks_entity_id_correctly(self):
        """The entity_id field must store and return the correct ID."""
        record = EntityChangeLog(
            turn=1, entity_type="npc", entity_id="npc_draven", change_type="updated"
        )
        assert record.entity_id == "npc_draven"

    def test_changelog_tracks_change_type_correctly(self):
        """The change_type field must store and return the correct change type."""
        record = EntityChangeLog(
            turn=5, entity_type="npc", entity_id="npc_01", change_type="deactivated"
        )
        assert record.change_type == "deactivated"

    def test_changelog_tracks_changed_fields(self):
        """changed_fields must accurately store the list of changed field names."""
        fields = ["name", "description", "faction", "is_active"]
        record = EntityChangeLog(
            turn=3,
            entity_type="npc",
            entity_id="npc_draven",
            change_type="updated",
            changed_fields=fields,
        )
        assert record.changed_fields == fields
        assert len(record.changed_fields) == 4

    def test_changelog_tracks_summary(self):
        """summary must accurately store the change summary text."""
        summary = "NPC Draven was updated: name, description, faction changed."
        record = EntityChangeLog(
            turn=10,
            entity_type="npc",
            entity_id="npc_draven",
            change_type="updated",
            summary=summary,
        )
        assert record.summary == summary

    def test_changelog_with_all_change_types(self):
        """All common change types must survive round-trip."""
        for change_type in [
            "created",
            "updated",
            "seen",
            "deactivated",
            "reactivated",
            "deleted",
        ]:
            record = EntityChangeLog(
                turn=1,
                entity_type="npc",
                entity_id="npc_01",
                change_type=change_type,
                summary=f"Entity was {change_type}.",
            )
            _assert_round_trip(record, EntityChangeLog)

    # -- 4. Edge cases --------------------------------------------------

    def test_changelog_turn_zero(self):
        """turn=0 (valid initial state) must survive round-trip."""
        record = EntityChangeLog(
            turn=0, entity_type="npc", entity_id="npc_01", change_type="created"
        )
        _assert_round_trip(record, EntityChangeLog)
        assert record.turn == 0

    def test_changelog_unicode_in_summary(self):
        """Unicode characters in summary must survive round-trip."""
        record = EntityChangeLog(
            turn=5,
            entity_type="item",
            entity_id="item_étoile",
            change_type="updated",
            summary=f"Item modified: {UNICODE_NAME}",
        )
        _assert_round_trip(record, EntityChangeLog)

    def test_changelog_very_long_summary(self):
        """Very long summaries must survive round-trip without truncation."""
        record = EntityChangeLog(
            turn=99,
            entity_type="place",
            entity_id="place_long",
            change_type="updated",
            summary=LONG_DESCRIPTION,
        )
        _assert_round_trip(record, EntityChangeLog)
        assert len(record.summary) == len(LONG_DESCRIPTION)

    def test_changelog_many_changed_fields(self):
        """A large list of changed_fields must survive round-trip."""
        fields = [f"field_{i}" for i in range(300)]
        record = EntityChangeLog(
            turn=1,
            entity_type="npc",
            entity_id="npc_big",
            change_type="updated",
            changed_fields=fields,
        )
        _assert_round_trip(record, EntityChangeLog)
        assert len(record.changed_fields) == 300

    def test_changelog_empty_changed_fields_explicit(self):
        """An explicit empty changed_fields list must remain empty after round-trip."""
        record = EntityChangeLog(
            turn=2,
            entity_type="npc",
            entity_id="npc_01",
            change_type="seen",
            changed_fields=[],
        )
        _assert_round_trip(record, EntityChangeLog)
        assert record.changed_fields == []

    def test_changelog_empty_summary(self):
        """An empty summary string must survive round-trip."""
        record = EntityChangeLog(
            turn=3,
            entity_type="place",
            entity_id="place_01",
            change_type="seen",
            summary="",
        )
        _assert_round_trip(record, EntityChangeLog)
        assert record.summary == ""

    # -- 5. Forward compatibility (extra keys dropped) ------------------

    def test_changelog_from_dict_ignores_extra_keys(self):
        """Extra unknown keys in the dict must be silently dropped."""
        data = {
            "turn": 15,
            "entity_type": "npc",
            "entity_id": "npc_fwd",
            "change_type": "updated",
            "changed_fields": ["name"],
            "summary": "Updated name.",
            "extra_field": "should be ignored",
            "_internal": "also ignored",
            "redundant": True,
        }
        record = EntityChangeLog.from_dict(data)
        assert record.turn == 15
        assert record.entity_type == "npc"
        assert record.entity_id == "npc_fwd"
        assert record.change_type == "updated"
        assert record.changed_fields == ["name"]
        assert record.summary == "Updated name."
        assert not hasattr(record, "extra_field")
        assert not hasattr(record, "_internal")
        assert not hasattr(record, "redundant")

    def test_changelog_from_dict_missing_extra_with_defaults(self):
        """Extra keys must not interfere with default field values."""
        data = {
            "turn": 1,
            "entity_type": "npc",
            "entity_id": "npc_01",
            "change_type": "created",
            "bogus_field": "garbage",
        }
        record = EntityChangeLog.from_dict(data)
        assert record.changed_fields == []
        assert record.summary == ""

    # -- 6. Mutable default isolation -----------------------------------

    def test_changelog_mutable_defaults_are_isolated(self):
        """Each EntityChangeLog must have its own list — no shared references."""
        a = EntityChangeLog(
            turn=1, entity_type="npc", entity_id="npc_a", change_type="created"
        )
        b = EntityChangeLog(
            turn=2, entity_type="npc", entity_id="npc_b", change_type="created"
        )

        a.changed_fields.append("name")
        assert b.changed_fields == []

    def test_changelog_mutable_defaults_isolated_after_from_dict(self):
        """EntityChangeLog from_dict instances must have independent lists."""
        base = {
            "turn": 1,
            "entity_type": "npc",
            "entity_id": "npc_iso",
            "change_type": "created",
        }
        a = EntityChangeLog.from_dict(base)
        b = EntityChangeLog.from_dict(base)

        a.changed_fields.append("owned_by_a")
        assert b.changed_fields == []

    # -- 7. JSON serialisability ----------------------------------------

    def test_changelog_to_dict_is_json_serializable(self):
        """to_dict() output must survive json.dumps / json.loads round-trip."""
        record = EntityChangeLog(
            turn=42,
            entity_type="npc",
            entity_id="npc_json",
            change_type="updated",
            changed_fields=["name", "faction"],
            summary="Updated name and faction.",
        )
        dumped = json.dumps(record.to_dict())
        loaded = json.loads(dumped)
        restored = EntityChangeLog.from_dict(loaded)
        assert restored == record

    # -- 8. from_dict with partial data ---------------------------------

    def test_changelog_from_dict_with_only_required_fields(self):
        """Providing only required fields must work and rest are defaults."""
        record = EntityChangeLog.from_dict(
            {
                "turn": 1,
                "entity_type": "npc",
                "entity_id": "npc_01",
                "change_type": "created",
            }
        )
        assert record.turn == 1
        assert record.entity_type == "npc"
        assert record.entity_id == "npc_01"
        assert record.change_type == "created"
        assert record.changed_fields == []
        assert record.summary == ""

    @pytest.mark.parametrize(
        "missing_field", ["turn", "entity_type", "entity_id", "change_type"]
    )
    def test_changelog_from_dict_missing_required_field_raises(self, missing_field):
        """Missing any required field in from_dict must raise TypeError."""
        data = {
            "turn": 1,
            "entity_type": "npc",
            "entity_id": "npc_01",
            "change_type": "created",
        }
        del data[missing_field]
        with pytest.raises(TypeError):
            EntityChangeLog.from_dict(data)

    # -- 9. Equality ----------------------------------------------------

    def test_changelog_equality(self):
        """Two EntityChangeLogs with same values must be equal."""
        a = EntityChangeLog(
            turn=1, entity_type="npc", entity_id="npc_eq", change_type="created"
        )
        b = EntityChangeLog(
            turn=1, entity_type="npc", entity_id="npc_eq", change_type="created"
        )
        assert a == b

    def test_changelog_inequality(self):
        """Two EntityChangeLogs with different values must not be equal."""
        a = EntityChangeLog(
            turn=1, entity_type="npc", entity_id="npc_a", change_type="created"
        )
        b = EntityChangeLog(
            turn=2, entity_type="npc", entity_id="npc_a", change_type="created"
        )
        assert a != b


# ===================================================================
# Cross-cutting concerns
# ===================================================================


class TestCrossCutting:
    """Tests that span across all schema types."""

    @pytest.mark.parametrize(
        "cls,fields",
        [
            (NPCRecord, ("entity_id", "name")),
            (PlaceRecord, ("entity_id", "name")),
            (ItemRecord, ("entity_id", "name")),
            (EntityChangeLog, ("turn", "entity_type", "entity_id", "change_type")),
        ],
    )
    def test_required_fields_are_required(self, cls, fields):
        """All schema classes enforce required fields via TypeError."""
        with pytest.raises(TypeError):
            cls()

    def test_to_dict_returns_plain_dict(self):
        """to_dict() must always return a plain dict, not a subclass."""
        instances = [
            NPCRecord(entity_id="npc_01", name="Test"),
            PlaceRecord(entity_id="place_01", name="Test"),
            ItemRecord(entity_id="item_01", name="Test"),
            EntityChangeLog(
                turn=1, entity_type="npc", entity_id="npc_01", change_type="created"
            ),
        ]
        for instance in instances:
            result = instance.to_dict()
            assert isinstance(result, dict), (
                f"{type(instance).__name__}.to_dict() must return a dict"
            )
            assert type(result) is dict, (
                f"{type(instance).__name__}.to_dict() must return "
                f"plain dict, not {type(result)}"
            )

    def test_from_dict_returns_correct_type(self):
        """from_dict() must return an instance of the expected class."""
        assert isinstance(
            NPCRecord.from_dict({"entity_id": "npc_01", "name": "Test"}), NPCRecord
        )
        assert isinstance(
            PlaceRecord.from_dict({"entity_id": "place_01", "name": "Test"}),
            PlaceRecord,
        )
        assert isinstance(
            ItemRecord.from_dict({"entity_id": "item_01", "name": "Test"}), ItemRecord
        )
        assert isinstance(
            EntityChangeLog.from_dict(
                {
                    "turn": 1,
                    "entity_type": "npc",
                    "entity_id": "npc_01",
                    "change_type": "created",
                }
            ),
            EntityChangeLog,
        )

    def test_dataclass_fields_match_to_dict_keys(self):
        """The keys in to_dict() must exactly match the dataclass field names."""
        for cls in (NPCRecord, PlaceRecord, ItemRecord, EntityChangeLog):
            if cls == NPCRecord:
                inst = cls(entity_id="x", name="y")
            elif cls == PlaceRecord:
                inst = cls(entity_id="x", name="y")
            elif cls == ItemRecord:
                inst = cls(entity_id="x", name="y")
            else:
                inst = cls(
                    turn=0, entity_type="npc", entity_id="x", change_type="created"
                )

            data = inst.to_dict()
            field_names = {f.name for f in dataclasses.fields(cls)}
            assert set(data.keys()) == field_names, (
                f"{cls.__name__}.to_dict() keys {set(data.keys())} do not match "
                f"dataclass fields {field_names}"
            )

    def test_deep_copy_preserves_independence(self):
        """copy.deepcopy on instances must preserve all values."""
        original = NPCRecord(
            entity_id="npc_copy",
            name="Copy Test",
            description="Testing deepcopy.",
            relationships={"npc_01": "friend"},
            notes=["Note 1"],
            tags=["tag1"],
            metadata={"key": "value"},
        )
        copied = copy.deepcopy(original)

        assert copied == original
        assert copied is not original
        # Mutate the copy; original must not change
        copied.notes.append("New note")
        copied.relationships["npc_02"] = "enemy"
        assert len(original.notes) == 1
        assert "npc_02" not in original.relationships
