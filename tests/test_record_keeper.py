"""Comprehensive tests for RecordKeeperAgent — XML parsing, LLM analysis,
keyword fallback, and entity-fetching.

Covers the following acceptance criteria:
1. RecordKeeperAgent instantiates with None provider (graceful fallback)
2. analyze_pre_dm() returns plausible context with mock LLM
3. analyze_post_dm() correctly extracts entity operations from mock XML
4. fetch_entity() delegates to EntityStorage.get_entity()
5. Fallback behavior when LLM returns empty/unparseable content
6. Dual-branch prompts are separate strings with distinct instructions
7. _parse_timeline_xml — valid, empty, malformed XML
8. _parse_entity_changes_xml — valid, empty, unknown action/type, missing fields
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest

from app.agents.entity_persistence import EntityStorage
from app.agents.record_keeper import (
    ENTITY_SYSTEM_PROMPT,
    PLOT_SYSTEM_PROMPT,
    EntityOperation,
    PostDMAnalysis,
    RecordKeeperAgent,
    RecordKeeperContext,
    _parse_entity_changes_xml,
    _parse_timeline_xml,
)
from app.agents.record_keeper_schemas import EntityChangeLog
from app.llm.base import LLMProvider
from app.world.model import WorldState

# ===================================================================
# Helpers
# ===================================================================


def _make_mock_llm(response_text: str) -> MagicMock:
    """Return a MagicMock LLMProvider whose ``call()`` returns *response_text*."""
    provider = create_autospec(LLMProvider, instance=True)
    provider.call.return_value = {
        "content": response_text,
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    return provider


def _make_failing_llm(exception: type[Exception] = RuntimeError) -> MagicMock:
    """Return a MagicMock LLMProvider whose ``call()`` raises."""
    provider = create_autospec(LLMProvider, instance=True)
    provider.call.side_effect = exception("LLM is on fire")
    return provider


def _make_storage(tmp_path: Path, entities: list[dict] | None = None) -> EntityStorage:
    """Create an EntityStorage with pre-populated entities (optional)."""
    storage = EntityStorage(tmp_path)
    if entities:
        for ent in entities:
            storage.save_entity(ent["entity_type"], ent)
    return storage


def _make_world_state(**overrides) -> WorldState:
    """Create a WorldState with convenient defaults."""
    defaults: dict = {
        "current_location": "dark_forest",
        "turn_count": 5,
        "character_name": "Test Hero",
    }
    defaults.update(overrides)
    return WorldState(**defaults)


# ===================================================================
# Test XML parsing helpers — _parse_timeline_xml
# ===================================================================


class TestParseTimelineXml:
    """Tests for the _parse_timeline_xml function — pure XML parsing."""

    # -- Valid XML ----------------------------------------------------

    def test_parse_timeline_xml_valid(self) -> None:
        """Parse valid timeline XML with entries, threads, and causality."""
        xml = """\
<timeline>
<entry turn="1">Player entered the Dark Forest.</entry>
<entry turn="2">Encountered a wounded goblin scout.</entry>
</timeline>
<plot_threads>
<thread status="open">Who is the chieftain?</thread>
<thread status="open">Why are goblins raiding?</thread>
<thread status="resolved">The old well mystery.</thread>
</plot_threads>
<causality>
Player may face retaliation.
The goblin chieftain knows the player is coming.
</causality>"""
        entries, threads, causality = _parse_timeline_xml(xml)

        assert len(entries) == 2
        assert entries[0] == {"turn": 1, "text": "Player entered the Dark Forest."}
        assert entries[1] == {"turn": 2, "text": "Encountered a wounded goblin scout."}

        assert len(threads) == 3
        assert "Who is the chieftain?" in threads
        assert "Why are goblins raiding?" in threads
        assert "The old well mystery." in threads

        assert len(causality) == 2
        assert "Player may face retaliation." in causality
        assert "The goblin chieftain knows the player is coming." in causality

    def test_parse_timeline_xml_only_timeline(self) -> None:
        """Parse XML with only timeline entries, no plot_threads or causality."""
        xml = """\
<timeline>
<entry turn="1">A thing happened.</entry>
</timeline>"""
        entries, threads, causality = _parse_timeline_xml(xml)

        assert len(entries) == 1
        assert entries[0] == {"turn": 1, "text": "A thing happened."}
        assert threads == []
        assert causality == []

    def test_parse_timeline_xml_empty_tags(self) -> None:
        """Parse XML with empty tag pairs — should return empty lists."""
        xml = """\
<timeline></timeline>
<plot_threads></plot_threads>
<causality></causality>"""
        entries, threads, causality = _parse_timeline_xml(xml)

        assert entries == []
        assert threads == []
        assert causality == []

    def test_parse_timeline_xml_no_causality(self) -> None:
        """Parse XML without <causality> tag — threads still extracted."""
        xml = """\
<timeline>
<entry turn="5">Something happened.</entry>
</timeline>
<plot_threads>
<thread status="open">A mystery.</thread>
</plot_threads>"""
        entries, threads, causality = _parse_timeline_xml(xml)

        assert len(entries) == 1
        assert len(threads) == 1
        assert causality == []

    # -- Edge cases / malformed input ---------------------------------

    def test_parse_timeline_xml_empty_string(self) -> None:
        """Empty string input returns three empty lists."""
        entries, threads, causality = _parse_timeline_xml("")
        assert entries == []
        assert threads == []
        assert causality == []

    def test_parse_timeline_xml_none(self) -> None:
        """None input returns three empty lists (not an error)."""
        entries, threads, causality = _parse_timeline_xml(None)  # type: ignore[arg-type]
        assert entries == []
        assert threads == []
        assert causality == []

    def test_parse_timeline_xml_no_timeline_tag(self) -> None:
        """No <timeline> tag present — still returns empty lists."""
        xml = "<irrelevant>Some text</irrelevant>"
        entries, threads, causality = _parse_timeline_xml(xml)
        assert entries == []
        assert threads == []
        assert causality == []

    def test_parse_timeline_xml_no_plot_threads_tag(self) -> None:
        """No <plot_threads> tag — timeline and causality still parsed."""
        xml = """\
<timeline>
<entry turn="1">Event.</entry>
</timeline>
<causality>Some consequence.</causality>"""
        entries, threads, causality = _parse_timeline_xml(xml)

        assert len(entries) == 1
        assert entries[0] == {"turn": 1, "text": "Event."}
        assert threads == []
        assert len(causality) == 1

    def test_parse_timeline_xml_whitespace_only(self) -> None:
        """Whitespace-only input returns three empty lists."""
        entries, threads, causality = _parse_timeline_xml("   \n  \t  ")
        assert entries == []
        assert threads == []
        assert causality == []

    def test_parse_timeline_xml_malformed_entry(self) -> None:
        """Malformed entry (missing turn attr) is silently skipped."""
        xml = """\
<timeline>
<entry turn="1">First entry.</entry>
<entry>No turn attribute.</entry>
<entry turn="3">Third entry.</entry>
</timeline>"""
        entries, threads, causality = _parse_timeline_xml(xml)

        # The middle entry won't match the regex — only valid ones
        assert len(entries) == 2
        assert entries[0] == {"turn": 1, "text": "First entry."}
        assert entries[1] == {"turn": 3, "text": "Third entry."}

    def test_parse_timeline_xml_thread_without_status(self) -> None:
        """Thread without status attribute is still extracted."""
        xml = """\
<plot_threads>
<thread>A bare thread.</thread>
</plot_threads>"""
        entries, threads, causality = _parse_timeline_xml(xml)
        assert threads == ["A bare thread."]

    def test_parse_timeline_xml_multiline_causality(self) -> None:
        """Causality items split by newlines."""
        xml = """\
<causality>
First consequence.
Second consequence.

Third consequence (after blank line).
</causality>"""
        entries, threads, causality = _parse_timeline_xml(xml)
        assert causality == [
            "First consequence.",
            "Second consequence.",
            "Third consequence (after blank line).",
        ]


# ===================================================================
# Test XML parsing helpers — _parse_entity_changes_xml
# ===================================================================


class TestParseEntityChangesXml:
    """Tests for the _parse_entity_changes_xml function."""

    # -- Valid XML ----------------------------------------------------

    def test_parse_entity_changes_xml_valid(self) -> None:
        """Parse valid entity_changes XML with create, update actions."""
        xml = """\
<entity_changes>
<entity action="create" type="npc" id="gribbits">
<field name="name">Gribbits</field>
<field name="description">A wounded goblin scout</field>
</entity>
<entity action="update" type="place" id="dark_forest">
<field name="notes">Player entered this area</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)

        assert len(operations) == 2

        op1 = operations[0]
        assert op1.action == "create"
        assert op1.entity_type == "npc"
        assert op1.entity_id == "gribbits"
        assert op1.fields == {
            "name": "Gribbits",
            "description": "A wounded goblin scout",
        }

        op2 = operations[1]
        assert op2.action == "update"
        assert op2.entity_type == "place"
        assert op2.entity_id == "dark_forest"
        assert op2.fields == {"notes": "Player entered this area"}

    def test_parse_entity_changes_xml_create_with_name(self) -> None:
        """Create action includes a name field."""
        xml = """\
<entity_changes>
<entity action="create" type="item" id="rusted_key">
<field name="name">Rusted Iron Key</field>
<field name="description">A cold, rusted key.</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert len(operations) == 1
        op = operations[0]
        assert op.action == "create"
        assert op.entity_type == "item"
        assert op.entity_id == "rusted_key"
        assert op.fields["name"] == "Rusted Iron Key"

    def test_parse_entity_changes_xml_deactivate(self) -> None:
        """Deactivate action is correctly parsed."""
        xml = """\
<entity_changes>
<entity action="deactivate" type="npc" id="old_king">
<field name="reason">Slain in battle</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert len(operations) == 1
        op = operations[0]
        assert op.action == "deactivate"
        assert op.entity_type == "npc"
        assert op.entity_id == "old_king"
        assert op.fields == {"reason": "Slain in battle"}

    def test_parse_entity_changes_xml_multiple_fields(self) -> None:
        """Entity with many fields — all parsed."""
        xml = """\
<entity_changes>
<entity action="create" type="place" id="dark_tower">
<field name="name">Dark Tower</field>
<field name="description">A tall, foreboding tower.</field>
<field name="tags">dangerous, tower, ancient</field>
<field name="notable_features">Spire, Dungeon, Observatory</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert len(operations) == 1
        op = operations[0]
        assert len(op.fields) == 4
        assert op.fields["name"] == "Dark Tower"
        assert op.fields["tags"] == "dangerous, tower, ancient"

    # -- Empty / missing input ----------------------------------------

    def test_parse_entity_changes_xml_empty_string(self) -> None:
        """Empty string input returns empty list."""
        assert _parse_entity_changes_xml("") == []

    def test_parse_entity_changes_xml_none(self) -> None:
        """None input returns empty list (not an error)."""
        assert _parse_entity_changes_xml(None) == []  # type: ignore[arg-type]

    def test_parse_entity_changes_xml_no_entity_changes_tag(self) -> None:
        """No <entity_changes> tag — returns empty list."""
        xml = "<irrelevant>Some text</irrelevant>"
        assert _parse_entity_changes_xml(xml) == []

    def test_parse_entity_changes_xml_empty_tag(self) -> None:
        """Empty <entity_changes></entity_changes> returns empty list."""
        xml = "<entity_changes></entity_changes>"
        assert _parse_entity_changes_xml(xml) == []

    def test_parse_entity_changes_xml_whitespace_only(self) -> None:
        """Whitespace-only content returns empty list."""
        xml = "<entity_changes>   \n  </entity_changes>"
        assert _parse_entity_changes_xml(xml) == []

    # -- Unknown / invalid actions ------------------------------------

    def test_parse_entity_changes_xml_unknown_action(self) -> None:
        """Entity with unknown action is skipped."""
        xml = """\
<entity_changes>
<entity action="destroy" type="npc" id="gribbits">
<field name="name">Gribbits</field>
</entity>
<entity action="create" type="item" id="new_sword">
<field name="name">New Sword</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        # Only the valid action survives
        assert len(operations) == 1
        assert operations[0].entity_id == "new_sword"
        assert operations[0].action == "create"

    def test_parse_entity_changes_xml_unknown_type(self) -> None:
        """Entity with unknown type is skipped."""
        xml = """\
<entity_changes>
<entity action="create" type="vehicle" id="flying_boat">
<field name="name">Flying Boat</field>
</entity>
<entity action="update" type="npc" id="gribbits">
<field name="notes">Still wounded</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert len(operations) == 1
        assert operations[0].entity_id == "gribbits"

    def test_parse_entity_changes_xml_empty_id(self) -> None:
        """Entity with empty id is skipped."""
        xml = """\
<entity_changes>
<entity action="create" type="npc" id="">
<field name="name">Nameless</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert operations == []

    def test_parse_entity_changes_xml_mixed_valid_invalid(self) -> None:
        """Valid entities are kept, invalid ones are skipped."""
        xml = """\
<entity_changes>
<entity action="create" type="npc" id="valid_npc">
<field name="name">Valid NPC</field>
</entity>
<entity action="explode" type="npc" id="bad_action">
<field name="name">Bad Action</field>
</entity>
<entity action="update" type="spaceship" id="bad_type">
<field name="name">Bad Type</field>
</entity>
<entity action="deactivate" type="item" id="valid_item">
<field name="name">Valid Item</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert len(operations) == 2
        ids = {op.entity_id for op in operations}
        assert ids == {"valid_npc", "valid_item"}

    def test_parse_entity_changes_xml_no_fields(self) -> None:
        """Entity with no child fields still produces an operation."""
        xml = """\
<entity_changes>
<entity action="create" type="npc" id="empty_fields">
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert len(operations) == 1
        op = operations[0]
        assert op.entity_id == "empty_fields"
        assert op.fields == {}

    def test_parse_entity_changes_xml_field_with_empty_name(self) -> None:
        """Field with empty name attribute is skipped."""
        xml = """\
<entity_changes>
<entity action="create" type="npc" id="test">
<field name="">Empty name field</field>
<field name="real">Real field</field>
</entity>
</entity_changes>"""
        operations = _parse_entity_changes_xml(xml)
        assert len(operations) == 1
        op = operations[0]
        assert "real" in op.fields
        assert "" not in op.fields


# ===================================================================
# Test RecordKeeperAgent — __init__
# ===================================================================


class TestRecordKeeperAgentInit:
    """Tests for RecordKeeperAgent.__init__."""

    def test_init_with_none_provider(self, tmp_path: Path) -> None:
        """Agent instantiates gracefully with llm_provider=None."""
        storage = EntityStorage(tmp_path)
        agent = RecordKeeperAgent(
            llm_provider=None,
            entity_storage=storage,
            character_name="Test Hero",
        )
        assert agent.llm_provider is None
        assert agent.entity_storage is storage
        assert agent.character_name == "Test Hero"

    def test_init_with_provider(self, tmp_path: Path) -> None:
        """Agent stores the LLM provider reference."""
        provider = _make_mock_llm("some response")
        storage = EntityStorage(tmp_path)
        agent = RecordKeeperAgent(
            llm_provider=provider,
            entity_storage=storage,
            character_name="Hero",
        )
        assert agent.llm_provider is provider
        assert agent.entity_storage is storage

    def test_init_default_character_name(self, tmp_path: Path) -> None:
        """character_name defaults to empty string when not provided."""
        storage = EntityStorage(tmp_path)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)
        assert agent.character_name == ""


# ===================================================================
# Test RecordKeeperAgent — analyze_pre_dm
# ===================================================================


class TestRecordKeeperAgentAnalyzePreDM:
    """Tests for RecordKeeperAgent.analyze_pre_dm()."""

    def test_analyze_pre_dm_no_llm_fallback(self, tmp_path: Path) -> None:
        """Without LLM provider, returns minimal context with keyword entities."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits",
                "description": "A goblin scout",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="I talk to Gribbits",
            world_state=world,
            current_narrative="You see a goblin.",
        )

        assert isinstance(result, RecordKeeperContext)
        # timeline should be empty (no LLM)
        assert result.timeline_summary == ""
        assert result.plot_threads == []
        assert result.dm_suggestions == []
        # Entities matched by keyword
        assert len(result.relevant_entities) == 1
        assert result.relevant_entities[0]["entity_id"] == "gribbits"
        # Context text should contain the entity
        assert "Gribbits" in result.context_text

    def test_analyze_pre_dm_no_llm_no_entities(self, tmp_path: Path) -> None:
        """Without LLM and no matching entities, returns empty context."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="Hello there",
            world_state=world,
            current_narrative="",
        )

        assert result.timeline_summary == ""
        assert result.relevant_entities == []
        assert result.context_text == ""

    def test_analyze_pre_dm_with_llm(self, tmp_path: Path) -> None:
        """With LLM provider, returns parsed context from XML response."""
        mock_response = """\
<timeline>
<entry turn="1">Player entered the Dark Forest.</entry>
</timeline>
<plot_threads>
<thread status="open">Who is the chieftain?</thread>
</plot_threads>
<causality>
Player may face retaliation.
</causality>"""
        provider = _make_mock_llm(mock_response)
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="I search the forest",
            world_state=world,
            current_narrative="You are in a dark forest.",
        )

        assert isinstance(result, RecordKeeperContext)
        assert "[Turn 1] Player entered the Dark Forest." in result.timeline_summary
        assert "Who is the chieftain?" in result.plot_threads
        assert "Player may face retaliation." in result.dm_suggestions
        # Context text assembled from parts
        assert "=== Timeline ===" in result.context_text
        assert "=== Causality & Suggestions ===" in result.context_text

    def test_analyze_pre_dm_llm_call_fails(self, tmp_path: Path) -> None:
        """When LLM call throws, falls back to fallback context."""
        provider = _make_failing_llm(RuntimeError)
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "forest_guard",
                "name": "Forest Guard",
                "description": "A guard",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="I talk to the Forest Guard",
            world_state=world,
            current_narrative="A guard stands before you.",
        )

        # Falls back gracefully
        assert isinstance(result, RecordKeeperContext)
        assert result.timeline_summary == ""
        assert result.plot_threads == []
        # Entity matching still worked
        assert len(result.relevant_entities) >= 1

    def test_analyze_pre_dm_llm_returns_empty(self, tmp_path: Path) -> None:
        """When LLM returns empty content, falls back gracefully."""
        provider = _make_mock_llm("")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        # _call_llm raises RuntimeError for empty content → caught → fallback
        result = agent.analyze_pre_dm(
            player_input="Hello",
            world_state=world,
            current_narrative="",
        )

        assert isinstance(result, RecordKeeperContext)
        assert result.timeline_summary == ""
        assert result.relevant_entities == []

    def test_analyze_pre_dm_llm_returns_unparseable(self, tmp_path: Path) -> None:
        """When LLM returns content that isn't valid XML, parsing fails gracefully."""
        provider = _make_mock_llm("This is not XML at all. No tags here.")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="Hello",
            world_state=world,
            current_narrative="",
        )

        # Parsing doesn't raise — it returns empty lists → fallback
        assert isinstance(result, RecordKeeperContext)
        assert result.timeline_summary == ""
        assert result.plot_threads == []
        assert result.dm_suggestions == []

    def test_analyze_pre_dm_with_entities_and_llm(self, tmp_path: Path) -> None:
        """Both LLM analysis and keyword-matched entities in the same result."""
        mock_response = """\
<timeline>
<entry turn="1">Entered the cave.</entry>
</timeline>
<plot_threads></plot_threads>
<causality></causality>"""
        provider = _make_mock_llm(mock_response)
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "goblin_king",
                "name": "Goblin King",
                "description": "Ruler of the goblins",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="I challenge the Goblin King",
            world_state=world,
            current_narrative="You stand before the throne.",
        )

        assert "[Turn 1] Entered the cave." in result.timeline_summary
        assert len(result.relevant_entities) == 1
        assert result.relevant_entities[0]["entity_id"] == "goblin_king"
        assert "=== Relevant Entities ===" in result.context_text

    def test_analyze_pre_dm_provider_is_none_after_creation(
        self, tmp_path: Path
    ) -> None:
        """Agent created with provider=None still produces context."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="Test",
            world_state=world,
            current_narrative="",
        )

        assert isinstance(result, RecordKeeperContext)
        assert result.timeline_summary == ""


# ===================================================================
# Test RecordKeeperAgent — analyze_post_dm
# ===================================================================


class TestRecordKeeperAgentAnalyzePostDM:
    """Tests for RecordKeeperAgent.analyze_post_dm()."""

    def test_analyze_post_dm_no_llm_fallback(self, tmp_path: Path) -> None:
        """Without LLM provider, returns empty PostDMAnalysis."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="The goblin king appears!",
            world_state=world,
            turn_count=5,
        )

        assert isinstance(result, PostDMAnalysis)
        assert result.entity_operations == []
        assert result.changelog_entries == []
        assert result.raw_llm_response == ""

    def test_analyze_post_dm_with_llm(self, tmp_path: Path) -> None:
        """With LLM provider, returns parsed entity operations."""
        mock_response = """\
<entity_changes>
<entity action="create" type="npc" id="gribbits">
<field name="name">Gribbits</field>
<field name="description">A wounded goblin scout</field>
</entity>
<entity action="update" type="place" id="dark_forest">
<field name="notes">Player entered this area</field>
</entity>
</entity_changes>"""
        provider = _make_mock_llm(mock_response)
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="Gribbits appears in the dark forest.",
            world_state=world,
            turn_count=5,
        )

        assert isinstance(result, PostDMAnalysis)
        assert len(result.entity_operations) == 2

        op1 = result.entity_operations[0]
        assert op1.action == "create"
        assert op1.entity_type == "npc"
        assert op1.entity_id == "gribbits"
        assert op1.fields["name"] == "Gribbits"

        op2 = result.entity_operations[1]
        assert op2.action == "update"
        assert op2.entity_type == "place"
        assert op2.entity_id == "dark_forest"
        assert op2.fields["notes"] == "Player entered this area"

        # Changelog entries match operations
        assert len(result.changelog_entries) == 2
        changelog0 = result.changelog_entries[0]
        assert isinstance(changelog0, EntityChangeLog)
        assert changelog0.turn == 5
        assert changelog0.entity_type == "npc"
        assert changelog0.entity_id == "gribbits"
        assert changelog0.change_type == "create"
        assert "Created" in changelog0.summary

        # raw_llm_response is preserved
        assert result.raw_llm_response == mock_response

    def test_analyze_post_dm_llm_call_fails(self, tmp_path: Path) -> None:
        """When LLM call throws, returns empty analysis."""
        provider = _make_failing_llm(RuntimeError)
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="Something happens.",
            world_state=world,
            turn_count=3,
        )

        assert isinstance(result, PostDMAnalysis)
        assert result.entity_operations == []
        assert result.changelog_entries == []
        assert result.raw_llm_response == ""

    def test_analyze_post_dm_llm_returns_empty(self, tmp_path: Path) -> None:
        """When LLM returns empty content, returns empty analysis."""
        provider = _make_mock_llm("")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="Something happens.",
            world_state=world,
            turn_count=3,
        )

        assert isinstance(result, PostDMAnalysis)
        assert result.entity_operations == []
        assert result.changelog_entries == []

    def test_analyze_post_dm_unparseable_xml(self, tmp_path: Path) -> None:
        """When LLM returns content without valid entity_changes XML, still succeeds."""
        provider = _make_mock_llm("This is plain text with no XML tags whatsoever.")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="Something happens.",
            world_state=world,
            turn_count=3,
        )

        # No valid entity changes found, but not an error
        assert isinstance(result, PostDMAnalysis)
        assert result.entity_operations == []
        # raw_llm_response still preserved
        assert "plain text" in result.raw_llm_response

    def test_analyze_post_dm_partial_parse_failure(self, tmp_path: Path) -> None:
        """XML with some valid and some invalid entities — valid ones returned."""
        mock_response = """\
<entity_changes>
<entity action="create" type="npc" id="good_npc">
<field name="name">Good NPC</field>
</entity>
<entity action="destroy" type="npc" id="bad_action">
<field name="name">Bad Action</field>
</entity>
<entity action="update" type="place" id="good_place">
<field name="notes">Updated</field>
</entity>
</entity_changes>"""
        provider = _make_mock_llm(mock_response)
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="Scene description.",
            world_state=world,
            turn_count=7,
        )

        # Only the two valid entities survive
        assert len(result.entity_operations) == 2
        ids = {op.entity_id for op in result.entity_operations}
        assert ids == {"good_npc", "good_place"}

    def test_analyze_post_dm_changelog_all_change_types(self, tmp_path: Path) -> None:
        """All three action types produce correct changelog summaries."""
        mock_response = """\
<entity_changes>
<entity action="create" type="item" id="magic_sword">
<field name="name">Magic Sword</field>
</entity>
<entity action="update" type="npc" id="old_man">
<field name="age">Older</field>
</entity>
<entity action="deactivate" type="place" id="ruined_tower">
<field name="reason">Collapsed</field>
</entity>
</entity_changes>"""
        provider = _make_mock_llm(mock_response)
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="Scene.",
            world_state=world,
            turn_count=10,
        )

        summaries = {
            entry.entity_id: entry.summary for entry in result.changelog_entries
        }
        assert "Created" in summaries["magic_sword"]
        assert "Updated" in summaries["old_man"]
        assert "Deactivated" in summaries["ruined_tower"]

    def test_analyze_post_dm_provider_is_none_after_creation(
        self, tmp_path: Path
    ) -> None:
        """Agent created with provider=None always returns empty analysis."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="Something happens.",
            world_state=world,
            turn_count=1,
        )

        assert result.entity_operations == []
        assert result.raw_llm_response == ""


# ===================================================================
# Test RecordKeeperAgent — fetch_entity
# ===================================================================


class TestRecordKeeperAgentFetchEntity:
    """Tests for RecordKeeperAgent.fetch_entity()."""

    def test_fetch_entity_exists(self, tmp_path: Path) -> None:
        """fetch_entity returns the entity dict when it exists."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits",
                "description": "A goblin scout",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent.fetch_entity("npc", "gribbits")
        assert result is not None
        assert result["entity_id"] == "gribbits"
        assert result["name"] == "Gribbits"

    def test_fetch_entity_not_found(self, tmp_path: Path) -> None:
        """fetch_entity returns None when the entity does not exist."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent.fetch_entity("npc", "nonexistent")
        assert result is None

    def test_fetch_entity_delegates_to_storage(self, tmp_path: Path) -> None:
        """fetch_entity calls EntityStorage.get_entity with correct args."""
        storage = _make_storage(tmp_path, [])
        # Spy on get_entity
        storage.get_entity = MagicMock(return_value={"entity_id": "test"})  # type: ignore[method-assign]
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent.fetch_entity("item", "test_item")

        storage.get_entity.assert_called_once_with("item", "test_item")
        assert result == {"entity_id": "test"}

    def test_fetch_entity_unknown_type(self, tmp_path: Path) -> None:
        """fetch_entity with invalid entity type returns None."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent.fetch_entity("spaceship", "enterprise")
        assert result is None


# ===================================================================
# Test RecordKeeperAgent — _keyword_match_entities
# ===================================================================


class TestRecordKeeperAgentKeywordMatch:
    """Tests for RecordKeeperAgent._keyword_match_entities()."""

    def test_keyword_match_by_entity_id(self, tmp_path: Path) -> None:
        """Token matching entity_id returns the entity."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits the Goblin",
                "description": "A goblin",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent._keyword_match_entities("I see gribbits here")
        assert len(result) == 1
        assert result[0]["entity_id"] == "gribbits"

    def test_keyword_match_by_name(self, tmp_path: Path) -> None:
        """Token matching entity name returns the entity."""
        entities = [
            {
                "entity_type": "place",
                "entity_id": "df_01",
                "name": "Dark Forest",
                "description": "A dark forest",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent._keyword_match_entities("I go to the forest")
        assert len(result) == 1
        assert result[0]["entity_id"] == "df_01"

    def test_keyword_match_no_match(self, tmp_path: Path) -> None:
        """No matching tokens returns empty list.

        Uses tokens that are NOT substrings of entity IDs or names,
        avoiding false positives from single-character tokens like
        "i" or "a" which commonly appear as substrings.
        """
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits",
                "description": "A goblin",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent._keyword_match_entities("xyzzy zork quux")
        assert result == []

    def test_keyword_match_empty_text(self, tmp_path: Path) -> None:
        """Empty input text returns empty list."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits",
                "description": "A goblin",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        assert agent._keyword_match_entities("") == []

    def test_keyword_match_no_entities_in_storage(self, tmp_path: Path) -> None:
        """Empty storage always returns empty list."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent._keyword_match_entities("gribbits")
        assert result == []

    def test_keyword_match_deduplicates(self, tmp_path: Path) -> None:
        """Same entity matched by multiple tokens is only returned once."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits the Goblin",
                "description": "A goblin scout",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        # Both "gribbits" and "goblin" would match the same entity
        result = agent._keyword_match_entities("gribbits goblin")
        assert len(result) == 1

    def test_keyword_match_multiple_entities(self, tmp_path: Path) -> None:
        """Multiple matching entities are all returned.

        Uses tokens that are NOT substrings of non-target entity IDs
        to avoid false positives (e.g. token "i" matches "gribbits").
        """
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits",
                "description": "A goblin scout",
            },
            {
                "entity_type": "place",
                "entity_id": "dark_forest",
                "name": "Dark Forest",
                "description": "A spooky forest",
            },
            {
                "entity_type": "item",
                "entity_id": "magic_sword",
                "name": "Magic Sword",
                "description": "A shiny blade",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent._keyword_match_entities(
            "player ventures dark forest wielding magic sword"
        )
        assert len(result) == 2
        ids = {e["entity_id"] for e in result}
        assert ids == {"dark_forest", "magic_sword"}

    def test_keyword_match_punctuation_stripping(self, tmp_path: Path) -> None:
        """Punctuation around tokens is stripped before matching."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "gribbits",
                "name": "Gribbits",
                "description": "A goblin",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        # "gribbits!" should strip to "gribbits"
        result = agent._keyword_match_entities("Hello, gribbits!")
        assert len(result) == 1
        assert result[0]["entity_id"] == "gribbits"

    def test_keyword_match_case_insensitive(self, tmp_path: Path) -> None:
        """Matching is case-insensitive."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "GRIBBITS",
                "name": "Gribbits the Goblin",
                "description": "A goblin",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent._keyword_match_entities("gribbits")
        assert len(result) == 1

    def test_keyword_match_substring_token(self, tmp_path: Path) -> None:
        """Token that is a substring of entity_id matches."""
        entities = [
            {
                "entity_type": "npc",
                "entity_id": "old_forest_guard",
                "name": "Forest Guard",
                "description": "A guard",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        # "forest" is a substring of "old_forest_guard"
        result = agent._keyword_match_entities("forest")
        assert len(result) == 1
        assert result[0]["entity_id"] == "old_forest_guard"


# ===================================================================
# Test Dual-Branch Prompts
# ===================================================================


class TestDualBranchPrompts:
    """Verify PLOT_SYSTEM_PROMPT and ENTITY_SYSTEM_PROMPT are separate,
    distinct strings with appropriate instructions."""

    def test_plot_prompt_is_non_empty(self) -> None:
        """PLOT_SYSTEM_PROMPT must be a non-empty string."""
        assert isinstance(PLOT_SYSTEM_PROMPT, str)
        assert len(PLOT_SYSTEM_PROMPT) > 0

    def test_entity_prompt_is_non_empty(self) -> None:
        """ENTITY_SYSTEM_PROMPT must be a non-empty string."""
        assert isinstance(ENTITY_SYSTEM_PROMPT, str)
        assert len(ENTITY_SYSTEM_PROMPT) > 0

    def test_prompts_are_separate_strings(self) -> None:
        """The two prompts must not be the same object or equal."""
        assert PLOT_SYSTEM_PROMPT is not ENTITY_SYSTEM_PROMPT
        assert PLOT_SYSTEM_PROMPT != ENTITY_SYSTEM_PROMPT

    def test_plot_prompt_contains_timeline_instructions(self) -> None:
        """Plot prompt must reference timeline and plot threads."""
        assert "timeline" in PLOT_SYSTEM_PROMPT.lower()
        assert "plot_threads" in PLOT_SYSTEM_PROMPT
        assert "causality" in PLOT_SYSTEM_PROMPT.lower()

    def test_entity_prompt_contains_entity_instructions(self) -> None:
        """Entity prompt must reference entity changes and actions."""
        assert "entity_changes" in ENTITY_SYSTEM_PROMPT
        assert "create" in ENTITY_SYSTEM_PROMPT
        assert "update" in ENTITY_SYSTEM_PROMPT
        assert "deactivate" in ENTITY_SYSTEM_PROMPT

    def test_plot_prompt_contains_xml_tags(self) -> None:
        """Plot prompt defines expected XML output structure."""
        assert "<timeline>" in PLOT_SYSTEM_PROMPT
        assert "<plot_threads>" in PLOT_SYSTEM_PROMPT
        assert "<causality>" in PLOT_SYSTEM_PROMPT

    def test_entity_prompt_contains_xml_tags(self) -> None:
        """Entity prompt defines expected XML output structure."""
        assert "<entity_changes>" in ENTITY_SYSTEM_PROMPT
        assert "<entity" in ENTITY_SYSTEM_PROMPT
        assert "<field" in ENTITY_SYSTEM_PROMPT

    def test_plot_prompt_has_constraints_section(self) -> None:
        """Plot prompt includes constraints."""
        assert "CONSTRAINTS" in PLOT_SYSTEM_PROMPT

    def test_entity_prompt_has_constraints_section(self) -> None:
        """Entity prompt includes constraints."""
        assert "CONSTRAINTS" in ENTITY_SYSTEM_PROMPT

    def test_plot_prompt_mentions_analysis_role(self) -> None:
        """Plot prompt describes an analytical scribe role."""
        assert "analytical scribe" in PLOT_SYSTEM_PROMPT.lower()

    def test_entity_prompt_mentions_record_keeper_role(self) -> None:
        """Entity prompt describes a meticulous record keeper role."""
        assert "record keeper" in ENTITY_SYSTEM_PROMPT.lower()


# ===================================================================
# Test RecordKeeperAgent — _build_change_summary
# ===================================================================


class TestBuildChangeSummary:
    """Tests for the static _build_change_summary method."""

    def test_build_change_summary_create(self) -> None:
        """Create operation produces 'Created {type} '{name}'."""
        op = EntityOperation(
            action="create",
            entity_type="npc",
            entity_id="gribbits",
            fields={"name": "Gribbits"},
        )
        summary = RecordKeeperAgent._build_change_summary(op)
        assert summary == "Created npc 'Gribbits'"

    def test_build_change_summary_create_no_name(self) -> None:
        """Create without a name field falls back to entity_id."""
        op = EntityOperation(
            action="create",
            entity_type="item",
            entity_id="mystery_item",
            fields={},
        )
        summary = RecordKeeperAgent._build_change_summary(op)
        assert summary == "Created item 'mystery_item'"

    def test_build_change_summary_update(self) -> None:
        """Update operation includes changed field names."""
        op = EntityOperation(
            action="update",
            entity_type="place",
            entity_id="dark_forest",
            fields={"notes": "Updated", "danger_level": "high"},
        )
        summary = RecordKeeperAgent._build_change_summary(op)
        assert "Updated" in summary
        assert "dark_forest" in summary
        assert "notes" in summary or "danger_level" in summary

    def test_build_change_summary_update_no_fields(self) -> None:
        """Update with no fields says 'general'."""
        op = EntityOperation(
            action="update",
            entity_type="npc",
            entity_id="someone",
            fields={},
        )
        summary = RecordKeeperAgent._build_change_summary(op)
        assert "general" in summary

    def test_build_change_summary_deactivate(self) -> None:
        """Deactivate operation produces 'Deactivated {type} '{id}'."""
        op = EntityOperation(
            action="deactivate",
            entity_type="npc",
            entity_id="old_king",
            fields={},
        )
        summary = RecordKeeperAgent._build_change_summary(op)
        assert summary == "Deactivated npc 'old_king'"

    def test_build_change_summary_unknown_action(self) -> None:
        """Unknown action falls through to a generic format."""
        op = EntityOperation(
            action="unknown_action",
            entity_type="npc",
            entity_id="test",
            fields={},
        )
        summary = RecordKeeperAgent._build_change_summary(op)
        assert summary == "unknown_action npc 'test'"


# ===================================================================
# Test RecordKeeperAgent — _build_fallback_context_text
# ===================================================================


class TestBuildFallbackContextText:
    """Tests for the static _build_fallback_context_text method."""

    def test_fallback_context_with_entities(self) -> None:
        """Fallback context lists matching entities."""
        entities = [
            {"entity_id": "gribbits", "name": "Gribbits", "entity_type": "npc"},
            {"entity_id": "dark_forest", "name": "Dark Forest", "entity_type": "place"},
        ]
        text = RecordKeeperAgent._build_fallback_context_text(entities)
        assert "=== Relevant Entities ===" in text
        assert "[npc]" in text
        assert "[place]" in text
        assert "Gribbits" in text
        assert "Dark Forest" in text

    def test_fallback_context_empty(self) -> None:
        """Fallback context with no entities returns empty string."""
        text = RecordKeeperAgent._build_fallback_context_text([])
        assert text == ""

    def test_fallback_context_falls_back_to_id_for_name(self) -> None:
        """Entity without a name uses entity_id as fallback display name."""
        entities = [
            {"entity_id": "no_name_entity", "entity_type": "npc"},
        ]
        text = RecordKeeperAgent._build_fallback_context_text(entities)
        assert "no_name_entity" in text
        assert "?" not in text  # entity_id is used as name

    def test_fallback_context_unknown_type(self) -> None:
        """Entity without entity_type shows 'unknown'."""
        entities = [
            {"entity_id": "mystery", "name": "Mystery"},
        ]
        text = RecordKeeperAgent._build_fallback_context_text(entities)
        assert "[unknown]" in text or "[unknown]" in text

    def test_fallback_context_missing_entity_id(self) -> None:
        """Entity without entity_id shows '?' placeholder."""
        entities = [
            {"name": "Nameless", "entity_type": "npc"},
        ]
        text = RecordKeeperAgent._build_fallback_context_text(entities)
        assert "?" in text


# ===================================================================
# Test RecordKeeperAgent — _call_llm (retry-once logic)
# ===================================================================


class TestRecordKeeperAgentCallLLM:
    """Tests for RecordKeeperAgent._call_llm()."""

    def test_call_llm_no_provider_raises(self, tmp_path: Path) -> None:
        """_call_llm raises RuntimeError when llm_provider is None."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        with pytest.raises(RuntimeError, match="LLM provider is not available"):
            agent._call_llm([{"role": "user", "content": "Hi"}])

    def test_call_llm_success(self, tmp_path: Path) -> None:
        """_call_llm returns content from the provider."""
        provider = _make_mock_llm("Hello, world!")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)

        result = agent._call_llm([{"role": "user", "content": "Hi"}])
        assert result == "Hello, world!"

    def test_call_llm_retry_on_failure(self, tmp_path: Path) -> None:
        """_call_llm retries once when the first call fails."""
        provider = create_autospec(LLMProvider, instance=True)
        # First call fails, second succeeds
        provider.call.side_effect = [
            RuntimeError("First failure"),
            {"content": "Success after retry", "finish_reason": "stop"},
        ]
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)

        result = agent._call_llm([{"role": "user", "content": "Hi"}])
        assert result == "Success after retry"
        assert provider.call.call_count == 2

    def test_call_llm_raises_after_retry_fails(self, tmp_path: Path) -> None:
        """_call_llm raises RuntimeError when both attempts fail."""
        provider = _make_failing_llm(RuntimeError)
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)

        with pytest.raises(
            RuntimeError, match="RecordKeeper LLM call failed after retry"
        ):
            agent._call_llm([{"role": "user", "content": "Hi"}])
        assert provider.call.call_count == 2

    def test_call_llm_raises_on_empty_content(self, tmp_path: Path) -> None:
        """_call_llm raises RuntimeError when content is empty."""
        provider = _make_mock_llm("")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)

        with pytest.raises(RuntimeError, match="empty content"):
            agent._call_llm([{"role": "user", "content": "Hi"}])

    def test_call_llm_passes_messages_to_provider(self, tmp_path: Path) -> None:
        """_call_llm forwards the messages list to the provider."""
        provider = _make_mock_llm("response")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)

        messages = [{"role": "user", "content": "Test message"}]
        agent._call_llm(messages)

        provider.call.assert_called_once_with(messages)


# ===================================================================
# Test RecordKeeperAgent — _build_plot_context / _build_entity_context
# ===================================================================


class TestBuildContextMethods:
    """Tests for the internal context-building methods."""

    def test_build_plot_context_structure(self, tmp_path: Path) -> None:
        """_build_plot_context returns messages with system + user roles."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(
            llm_provider=None,
            entity_storage=storage,
            character_name="Test Hero",
        )
        world = _make_world_state()

        messages = agent._build_plot_context(
            player_input="I explore",
            world_state=world,
            current_narrative="You are in a cave.",
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == PLOT_SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert "Test Hero" in messages[1]["content"]
        assert "dark_forest" in messages[1]["content"]  # current_location
        assert "I explore" in messages[1]["content"]

    def test_build_entity_context_structure(self, tmp_path: Path) -> None:
        """_build_entity_context returns messages with system + user roles."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(
            llm_provider=None,
            entity_storage=storage,
        )
        world = _make_world_state()

        messages = agent._build_entity_context(
            dm_response="The goblin appears!",
            world_state=world,
            turn_count=5,
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == ENTITY_SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert "The goblin appears!" in messages[1]["content"]
        assert "Turn: 5" in messages[1]["content"]

    def test_build_plot_context_no_character_name(self, tmp_path: Path) -> None:
        """Without character_name, falls back to 'Unknown'."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(
            llm_provider=None,
            entity_storage=storage,
            character_name="",
        )
        world = _make_world_state()

        messages = agent._build_plot_context(
            player_input="Hi",
            world_state=world,
            current_narrative="",
        )

        assert "Unknown" in messages[1]["content"]


# ===================================================================
# Test RecordKeeperAgent — Integration-style end-to-end flows
# ===================================================================


class TestRecordKeeperAgentIntegration:
    """End-to-end flows combining multiple behaviors."""

    def test_full_pre_and_post_flow(self, tmp_path: Path) -> None:
        """Run pre-DM and post-DM in sequence with mock LLM."""
        pre_response = """\
<timeline>
<entry turn="1">Player entered the cave.</entry>
</timeline>
<plot_threads>
<thread status="open">What is in the cave?</thread>
</plot_threads>
<causality>
Player may find treasure.
</causality>"""

        post_response = """\
<entity_changes>
<entity action="create" type="item" id="treasure_chest">
<field name="name">Treasure Chest</field>
<field name="description">A locked wooden chest</field>
</entity>
</entity_changes>"""

        provider = create_autospec(LLMProvider, instance=True)
        provider.call.side_effect = [
            {"content": pre_response, "finish_reason": "stop"},
            {"content": post_response, "finish_reason": "stop"},
        ]

        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(
            llm_provider=provider,
            entity_storage=storage,
            character_name="Test Hero",
        )
        world = _make_world_state()

        # Pre-DM
        pre_result = agent.analyze_pre_dm(
            player_input="I enter the cave",
            world_state=world,
            current_narrative="You stand at the cave entrance.",
        )

        assert "[Turn 1] Player entered the cave." in pre_result.timeline_summary
        assert "What is in the cave?" in pre_result.plot_threads
        assert "treasure" in pre_result.dm_suggestions[0].lower()

        # Post-DM
        post_result = agent.analyze_post_dm(
            dm_response="You find a treasure chest!",
            world_state=world,
            turn_count=6,
        )

        assert len(post_result.entity_operations) == 1
        assert post_result.entity_operations[0].entity_id == "treasure_chest"
        assert post_result.entity_operations[0].action == "create"
        assert provider.call.call_count == 2

    def test_fallback_when_llm_fails_then_succeeds(self, tmp_path: Path) -> None:
        """Fallback works after LLM failure, then succeeds on next call."""
        provider = create_autospec(LLMProvider, instance=True)
        # First call fails
        provider.call.side_effect = RuntimeError("LLM unavailable")

        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(
            llm_provider=provider,
            entity_storage=storage,
        )
        world = _make_world_state()

        # First call — fails, falls back
        result1 = agent.analyze_pre_dm(
            player_input="Hello",
            world_state=world,
            current_narrative="",
        )
        assert result1.timeline_summary == ""

        # Now make LLM work again
        provider.call.side_effect = None
        provider.call.return_value = {
            "content": """\
<timeline>
<entry turn="1">Later event.</entry>
</timeline>
<plot_threads></plot_threads>
<causality></causality>""",
            "finish_reason": "stop",
        }

        result2 = agent.analyze_pre_dm(
            player_input="Hello again",
            world_state=world,
            current_narrative="",
        )
        assert "[Turn 1] Later event." in result2.timeline_summary


# ===================================================================
# Test RecordKeeperAgent — Edge cases
# ===================================================================


class TestRecordKeeperAgentEdgeCases:
    """Corner cases and unusual inputs."""

    def test_analyze_pre_dm_empty_player_input(self, tmp_path: Path) -> None:
        """Empty player_input is handled without crashing."""
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_pre_dm(
            player_input="",
            world_state=world,
            current_narrative="Some narrative.",
        )
        assert isinstance(result, RecordKeeperContext)

    def test_analyze_pre_dm_very_long_narrative(self, tmp_path: Path) -> None:
        """Very long narrative text does not cause issues."""
        provider = _make_mock_llm(
            '<timeline><entry turn="1">Long story.</entry></timeline>'
            "<plot_threads></plot_threads><causality></causality>"
        )
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        long_narrative = "word " * 10_000
        result = agent.analyze_pre_dm(
            player_input="Hi",
            world_state=world,
            current_narrative=long_narrative,
        )
        assert "[Turn 1] Long story." in result.timeline_summary

    def test_analyze_post_dm_empty_dm_response(self, tmp_path: Path) -> None:
        """Empty DM response does not crash."""
        provider = _make_mock_llm("<entity_changes></entity_changes>")
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="",
            world_state=world,
            turn_count=1,
        )
        assert isinstance(result, PostDMAnalysis)

    def test_analyze_post_dm_turn_count_zero(self, tmp_path: Path) -> None:
        """Turn count of zero is valid and appears in changelog."""
        provider = _make_mock_llm(
            "<entity_changes>"
            '<entity action="create" type="npc" id="test_npc">'
            '<field name="name">Test NPC</field>'
            "</entity>"
            "</entity_changes>"
        )
        storage = _make_storage(tmp_path, [])
        agent = RecordKeeperAgent(llm_provider=provider, entity_storage=storage)
        world = _make_world_state()

        result = agent.analyze_post_dm(
            dm_response="A new NPC appears.",
            world_state=world,
            turn_count=0,
        )
        assert len(result.entity_operations) == 1
        assert result.changelog_entries[0].turn == 0

    def test_fetch_entity_with_special_chars_in_id(self, tmp_path: Path) -> None:
        """Entity IDs with special characters are handled."""
        entities = [
            {
                "entity_type": "item",
                "entity_id": "sword_of_ahn'qiraj",
                "name": "Sword of Ahn'Qiraj",
                "description": "A legendary blade",
            },
        ]
        storage = _make_storage(tmp_path, entities)
        agent = RecordKeeperAgent(llm_provider=None, entity_storage=storage)

        result = agent.fetch_entity("item", "sword_of_ahn'qiraj")
        assert result is not None
        assert result["entity_id"] == "sword_of_ahn'qiraj"
