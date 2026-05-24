"""Tests for the world state data model — Phase 3, Task 3.1."""

from __future__ import annotations

import pytest

from app.world.model import (
    DMNotes,
    FactionStanding,
    Location,
    Quest,
    WorldState,
)

# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


class TestLocation:
    def test_create_with_minimal_fields(self) -> None:
        loc = Location(id="room_1", name="Damp Cellar", description="A dark cellar.")
        assert loc.id == "room_1"
        assert loc.name == "Damp Cellar"
        assert loc.description == "A dark cellar."
        assert loc.exits == {}
        assert loc.tags == []

    def test_create_with_exits_and_tags(self) -> None:
        loc = Location(
            id="forest_clearing",
            name="Forest Clearing",
            description="A sun-dappled clearing.",
            exits={"north": "cave_entrance", "east": "old_well"},
            tags=["forest", "safe_zone"],
        )
        assert loc.exits == {"north": "cave_entrance", "east": "old_well"}
        assert loc.tags == ["forest", "safe_zone"]


# ---------------------------------------------------------------------------
# Quest
# ---------------------------------------------------------------------------


class TestQuest:
    def test_default_status_is_active(self) -> None:
        q = Quest(id="q_01", name="Gather Herbs", description="Collect 5 herbs.")
        assert q.status == "active"

    def test_create_with_completed_status(self) -> None:
        q = Quest(
            id="q_01",
            name="Gather Herbs",
            description="Collect 5 herbs.",
            status="completed",
        )
        assert q.status == "completed"

    def test_create_with_failed_status(self) -> None:
        q = Quest(
            id="q_01",
            name="Gather Herbs",
            description="Collect 5 herbs.",
            status="failed",
        )
        assert q.status == "failed"

    def test_invalid_status_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid quest status"):
            Quest(id="q_01", name="Gather Herbs", description="...", status="invalid")

    def test_objectives_are_stored(self) -> None:
        q = Quest(
            id="q_02",
            name="Slay the Rat King",
            description="Clean out the sewers.",
            objectives=["Find the entrance", "Defeat the Rat King", "Report back"],
        )
        assert len(q.objectives) == 3
        assert q.objectives[1] == "Defeat the Rat King"


# ---------------------------------------------------------------------------
# FactionStanding
# ---------------------------------------------------------------------------


class TestFactionStanding:
    def test_default_standing_is_zero(self) -> None:
        fs = FactionStanding(faction_id="guild_01", name="Thieves Guild")
        assert fs.standing == 0

    def test_valid_standing_accepted(self) -> None:
        fs = FactionStanding(faction_id="guild_01", name="Thieves Guild", standing=50)
        assert fs.standing == 50

    def test_standing_above_100_raises_error(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            FactionStanding(faction_id="guild_01", name="Thieves Guild", standing=101)

    def test_standing_below_neg100_raises_error(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            FactionStanding(faction_id="guild_01", name="Thieves Guild", standing=-101)

    def test_standing_at_boundaries(self) -> None:
        fs_min = FactionStanding(faction_id="guild_01", name="Enemy", standing=-100)
        assert fs_min.standing == -100
        fs_max = FactionStanding(faction_id="guild_01", name="Ally", standing=100)
        assert fs_max.standing == 100


# ---------------------------------------------------------------------------
# DMNotes
# ---------------------------------------------------------------------------


class TestDMNotes:
    def test_defaults_are_empty(self) -> None:
        notes = DMNotes()
        assert notes.plot_threads == []
        assert notes.secrets == []
        assert notes.future_plans == []

    def test_can_store_arbitrary_strings(self) -> None:
        notes = DMNotes(
            plot_threads=["The innkeeper is the lost prince"],
            secrets=["There is a trapdoor behind the throne"],
            future_plans=["The dragon attacks in act 3"],
        )
        assert len(notes.plot_threads) == 1
        assert len(notes.secrets) == 1
        assert len(notes.future_plans) == 1
        assert notes.secrets[0] == "There is a trapdoor behind the throne"


# ---------------------------------------------------------------------------
# WorldState
# ---------------------------------------------------------------------------


class TestWorldState:
    def test_default_values(self) -> None:
        ws = WorldState()
        assert ws.version == "1.0"
        assert ws.character_id is None
        assert ws.current_location == "starting_village"
        assert ws.active_npcs == {}
        assert ws.locations == {}
        assert ws.quests == {}
        assert ws.faction_standings == {}
        assert ws.inventory == []
        assert ws.gold == 0
        assert isinstance(ws.dm_notes, DMNotes)
        assert ws.turn_count == 0

    def test_character_id_is_optional(self) -> None:
        """character_id must accept None (new game with no character yet)."""
        ws = WorldState()
        assert ws.character_id is None

        ws2 = WorldState(character_id="hero_01")
        assert ws2.character_id == "hero_01"

    def test_version_is_1_dot_0_by_default(self) -> None:
        ws = WorldState()
        assert ws.version == "1.0"

    def test_established_facts_defaults_to_empty(self) -> None:
        ws = WorldState()
        assert ws.established_facts == []

    def test_established_facts_survives_round_trip(self) -> None:
        ws = WorldState(
            established_facts=[
                "Tavern is The Cracked Flagon",
                "Blacksmith is Torvin Ironhand",
            ]
        )
        data = ws.to_dict()
        assert "established_facts" in data
        assert len(data["established_facts"]) == 2
        restored = WorldState.from_dict(data)
        assert restored.established_facts == [
            "Tavern is The Cracked Flagon",
            "Blacksmith is Torvin Ironhand",
        ]

    def test_established_facts_from_dict_with_non_list(self) -> None:
        """If established_facts is not a list, must default to empty."""
        ws = WorldState.from_dict({"established_facts": "not a list"})
        assert ws.established_facts == []

    def test_established_facts_from_dict_filters_non_strings(self) -> None:
        """Non-string entries must be filtered out."""
        ws = WorldState.from_dict(
            {"established_facts": ["valid fact", 42, 3.14, None, "also valid"]}
        )
        assert ws.established_facts == ["valid fact", "also valid"]

    # ------------------------------------------------------------------
    # story_log field
    # ------------------------------------------------------------------

    def test_story_log_field_exists(self) -> None:
        """WorldState has story_log field defaulting to []."""
        ws = WorldState()
        assert ws.story_log == []

    def test_story_log_to_dict_roundtrip(self) -> None:
        """to_dict() includes story_log and from_dict() loads it back."""
        ws = WorldState(
            story_log=[
                "[Turn 1] You enter the dark forest.",
                "[Turn 2] A goblin appears!",
            ]
        )
        data = ws.to_dict()
        assert "story_log" in data
        assert len(data["story_log"]) == 2
        restored = WorldState.from_dict(data)
        assert restored.story_log == [
            "[Turn 1] You enter the dark forest.",
            "[Turn 2] A goblin appears!",
        ]

    def test_story_log_backward_compat(self) -> None:
        """Old save data without story_log key loads fine with default []."""
        ws = WorldState.from_dict({"version": "1.0"})
        assert ws.story_log == []

    def test_with_custom_locations_and_quests(self) -> None:
        tavern = Location(
            id="tavern",
            name="The Rusty Nail",
            description="A warm, smoky tavern.",
            exits={"out": "town_square"},
        )
        quest = Quest(
            id="q_main",
            name="Find the Artifact",
            description="Locate the hidden artifact.",
        )
        guild = FactionStanding(
            faction_id="adventurers",
            name="Adventurers' Guild",
            standing=10,
        )
        notes = DMNotes(
            plot_threads=["The mayor is a shapeshifter"],
        )

        ws = WorldState(
            character_id="hero_42",
            current_location="tavern",
            locations={"tavern": tavern},
            quests={"q_main": quest},
            faction_standings={"adventurers": guild},
            inventory=["rusty_sword", "healing_potion"],
            dm_notes=notes,
            turn_count=5,
        )

        assert ws.character_id == "hero_42"
        assert ws.current_location == "tavern"
        assert ws.locations["tavern"].name == "The Rusty Nail"
        assert ws.quests["q_main"].status == "active"
        assert ws.faction_standings["adventurers"].standing == 10
        assert ws.inventory == ["rusty_sword", "healing_potion"]
        assert ws.dm_notes.plot_threads == ["The mayor is a shapeshifter"]
        assert ws.turn_count == 5

    def test_to_dict_and_from_dict_round_trip(self) -> None:
        """Serialise to dict and back — the result must equal the original."""
        tavern = Location(
            id="tavern",
            name="The Rusty Nail",
            description="A warm, smoky tavern.",
            exits={"out": "town_square"},
            tags=["safe_zone"],
        )
        quest = Quest(
            id="q_main",
            name="Find the Artifact",
            description="Locate the hidden artifact.",
            status="active",
            objectives=["Enter the cave", "Retrieve the orb"],
        )
        guild = FactionStanding(
            faction_id="adventurers",
            name="Adventurers' Guild",
            standing=50,
        )
        notes = DMNotes(
            plot_threads=["The mayor is a shapeshifter"],
            secrets=["Trapdoor behind the throne"],
        )

        original = WorldState(
            version="1.0",
            character_id="hero_42",
            current_location="tavern",
            locations={"tavern": tavern},
            quests={"q_main": quest},
            faction_standings={"adventurers": guild},
            inventory=["rusty_sword"],
            dm_notes=notes,
            turn_count=7,
        )

        # Round-trip
        data = original.to_dict()
        restored = WorldState.from_dict(data)

        # Compare field by field
        assert restored.version == original.version
        assert restored.character_id == original.character_id
        assert restored.current_location == original.current_location
        assert restored.turn_count == original.turn_count
        assert restored.inventory == original.inventory

        # Nested objects
        assert restored.locations["tavern"].id == "tavern"
        assert restored.locations["tavern"].name == "The Rusty Nail"
        assert restored.locations["tavern"].exits == {"out": "town_square"}
        assert restored.locations["tavern"].tags == ["safe_zone"]

        assert restored.quests["q_main"].status == "active"
        assert restored.quests["q_main"].objectives == [
            "Enter the cave",
            "Retrieve the orb",
        ]

        assert restored.faction_standings["adventurers"].standing == 50

        assert restored.dm_notes.plot_threads == ["The mayor is a shapeshifter"]
        assert restored.dm_notes.secrets == ["Trapdoor behind the throne"]

        # Verify it's actually a different object (not the same reference)
        assert restored is not original

    def test_from_dict_minimal(self) -> None:
        """Calling from_dict with an empty/partial dict should produce defaults."""
        ws = WorldState.from_dict({})
        assert ws.version == "1.0"
        assert ws.character_id is None
        assert ws.current_location == "starting_village"
        assert ws.locations == {}
        assert ws.quests == {}
        assert ws.faction_standings == {}
        assert ws.inventory == []
        assert ws.gold == 0
        assert ws.dm_notes.plot_threads == []
        assert ws.turn_count == 0

    def test_to_dict_is_json_serializable(self) -> None:
        """The output of to_dict() must survive json.dumps / json.loads."""
        import json

        ws = WorldState(
            character_id="hero_99",
            current_location="dragon_lair",
            inventory=["magic_sword", "shield"],
            turn_count=42,
        )
        dumped = json.dumps(ws.to_dict())
        loaded = json.loads(dumped)
        restored = WorldState.from_dict(loaded)

        assert restored.character_id == "hero_99"
        assert restored.current_location == "dragon_lair"
        assert restored.inventory == ["magic_sword", "shield"]
        assert restored.turn_count == 42
        assert restored.version == "1.0"

    # ---------------------------------------------------------------------------
    # Active NPCs (dict of dicts)
    # ---------------------------------------------------------------------------

    # ------------------------------------------------------------------
    # from_dict robustness — extra fields (Bug 2)
    # ------------------------------------------------------------------

    def test_from_dict_with_extra_fields_in_locations(self) -> None:
        """Extra fields in location dicts must be silently ignored."""
        data = {
            "locations": {
                "tavern": {
                    "id": "tavern",
                    "name": "The Rusty Nail",
                    "description": "A warm tavern.",
                    "gravity": "low",
                    "atmosphere": "cozy",
                }
            }
        }
        ws = WorldState.from_dict(data)
        assert "tavern" in ws.locations
        assert ws.locations["tavern"].name == "The Rusty Nail"
        assert ws.locations["tavern"].id == "tavern"

    def test_from_dict_with_extra_fields_in_quests(self) -> None:
        """Extra fields in quest dicts must be silently ignored."""
        data = {
            "quests": {
                "q_main": {
                    "id": "q_main",
                    "name": "Find the Artifact",
                    "description": "Locate the artifact.",
                    "reward_gold": 500,
                    "difficulty": "hard",
                }
            }
        }
        ws = WorldState.from_dict(data)
        assert "q_main" in ws.quests
        assert ws.quests["q_main"].status == "active"

    def test_from_dict_with_extra_fields_in_faction_standings(self) -> None:
        """Extra fields in faction standing dicts must be silently ignored."""
        data = {
            "faction_standings": {
                "guild_01": {
                    "faction_id": "guild_01",
                    "name": "Thieves Guild",
                    "standing": 50,
                    "color": "red",
                    "members": ["Bob"],
                }
            }
        }
        ws = WorldState.from_dict(data)
        assert "guild_01" in ws.faction_standings
        assert ws.faction_standings["guild_01"].standing == 50

    def test_world_gold_default(self) -> None:
        """gold must default to 0 in a fresh WorldState."""
        ws = WorldState()
        assert ws.gold == 0

    def test_world_gold_serialization(self) -> None:
        """gold must survive to_dict/from_dict round-trip."""
        original = WorldState(
            character_id="hero_01",
            gold=100,
            inventory=["sword"],
        )
        data = original.to_dict()
        assert "gold" in data
        assert data["gold"] == 100
        restored = WorldState.from_dict(data)
        assert restored.gold == 100

    def test_from_dict_with_extra_fields_in_dm_notes(self) -> None:
        """Extra fields in dm_notes dicts must be silently ignored."""
        data = {
            "dm_notes": {
                "plot_threads": ["The mayor is a spy"],
                "secret_recipe": "firebreath potion",
            }
        }
        ws = WorldState.from_dict(data)
        assert ws.dm_notes.plot_threads == ["The mayor is a spy"]
        assert ws.dm_notes.secrets == []

    # ------------------------------------------------------------------
    # from_dict robustness — wrong types (Bug 3)
    # ------------------------------------------------------------------

    def test_from_dict_with_string_instead_of_locations(self) -> None:
        """If locations is a string, must gracefully default to empty dict."""
        data = {"locations": "not_a_dict"}
        ws = WorldState.from_dict(data)
        assert ws.locations == {}

    def test_from_dict_with_string_instead_of_dm_notes(self) -> None:
        """If dm_notes is a string, must gracefully default to empty DMNotes."""
        data = {"dm_notes": "just a string"}
        ws = WorldState.from_dict(data)
        assert isinstance(ws.dm_notes, DMNotes)
        assert ws.dm_notes.plot_threads == []
        assert ws.dm_notes.secrets == []
        assert ws.dm_notes.future_plans == []

    def test_from_dict_with_string_instead_of_quests(self) -> None:
        """If quests is a string, must gracefully default to empty dict."""
        data = {"quests": "oops"}
        ws = WorldState.from_dict(data)
        assert ws.quests == {}

    def test_from_dict_with_string_instead_of_faction_standings(self) -> None:
        """If faction_standings is a string, must gracefully default to empty dict."""
        data = {"faction_standings": "oops"}
        ws = WorldState.from_dict(data)
        assert ws.faction_standings == {}

    def test_from_dict_with_string_instead_of_active_npcs(self) -> None:
        """If active_npcs is a string, must gracefully default to empty dict."""
        data = {"active_npcs": "no npcs here"}
        ws = WorldState.from_dict(data)
        assert ws.active_npcs == {}

    # ------------------------------------------------------------------
    # from_dict robustness — missing scalars (Bug 3)
    # ------------------------------------------------------------------

    def test_from_dict_with_missing_turn_count(self) -> None:
        """Missing turn_count must default to 0."""
        ws = WorldState.from_dict({"turn_count": None})
        assert ws.turn_count == 0

    def test_from_dict_with_turn_count_as_string(self) -> None:
        """turn_count as a string must be coerced to int."""
        ws = WorldState.from_dict({"turn_count": "42"})
        assert ws.turn_count == 42
        assert isinstance(ws.turn_count, int)

    def test_from_dict_with_version_as_none(self) -> None:
        """version=None must be coerced to '1.0'."""
        ws = WorldState.from_dict({"version": None})
        assert ws.version == "1.0"

    def test_from_dict_with_version_as_int(self) -> None:
        """version as int must be coerced to str."""
        ws = WorldState.from_dict({"version": 2})
        assert ws.version == "2"
        assert isinstance(ws.version, str)


class TestActiveNPCs:
    def test_active_npcs_are_dicts_not_dataclasses(self) -> None:
        """NPCs are stored as plain dicts for loose coupling."""
        ws = WorldState()
        ws.active_npcs["goblin_01"] = {
            "name": "Gribbits",
            "health": 10,
            "faction": "goblins",
        }
        assert ws.active_npcs["goblin_01"]["name"] == "Gribbits"
        assert ws.active_npcs["goblin_01"]["health"] == 10

    def test_active_npcs_survive_round_trip(self) -> None:
        ws = WorldState()
        ws.active_npcs["rat_king"] = {"name": "Rat King", "health": 50}
        data = ws.to_dict()
        restored = WorldState.from_dict(data)
        assert restored.active_npcs["rat_king"]["name"] == "Rat King"
        assert restored.active_npcs["rat_king"]["health"] == 50
