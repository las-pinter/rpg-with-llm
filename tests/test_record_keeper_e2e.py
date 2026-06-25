"""
End-to-end smoke tests for the Record-Keeper pipeline.

Verifies that the entire Record-Keeper → DM → Entity persistence pipeline
works end-to-end: pre-DM context injection, post-DM entity extraction,
and file persistence on disk.

Two tests:
1. ``test_full_game_turns_with_record_keeper`` — 3 turns with RecordKeeper.
2. ``test_dm_without_record_keeper_still_works`` — regression: DM without
   RecordKeeper still functions correctly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.agents.dm import DungeonMaster
from app.agents.entity_persistence import EntityStorage
from app.agents.record_keeper import RecordKeeperAgent
from app.character.model import Character
from app.world.model import WorldState


class TestRecordKeeperE2E:
    """End-to-end smoke tests for the Record-Keeper pipeline.

    The main test spins up a DM + RecordKeeper, runs 3 full turns with
    mock LLM responses, and verifies that entities are persisted to disk,
    the changelog is written, and the pre-DM Record-Keeper context is
    injected into DM calls.

    The regression test confirms that a DM without a RecordKeeper still
    produces valid turn events and does not crash.
    """

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _make_character() -> Character:
        """Create a standard level-1 Fighter test character."""
        return Character(
            id="test-hero",
            name="TestHero",
            character_class="Fighter",
            level=1,
            hp=10,
            max_hp=10,
            ac=10,
            abilities={
                "STR": 10,
                "DEX": 10,
                "CON": 10,
                "INT": 10,
                "WIS": 10,
                "CHA": 10,
            },
            skills=["perception"],
            inventory=["sword"],
            gold=10,
            xp=0,
        )

    @staticmethod
    def _make_world_state() -> WorldState:
        """Create a fresh world state for a new game."""
        return WorldState(
            character_id="test-hero",
            character_name="TestHero",
            current_location="starting_village",
            turn_count=0,
        )

    @staticmethod
    def _make_mock_provider() -> MagicMock:
        """Create a mock LLM provider with context-aware responses.

        The side-effect function inspects the message list to determine
        which branch the caller is in:

        * **Plot analysis** — messages contain *analytical scribe* →
          returns timeline / plot-threads / causality XML.
        * **Entity analysis** — messages contain *meticulous record
          keeper* → returns entity-changes XML.
        * **Everything else** (DM narrative, summarizer, etc.) → returns
          a plain ``<narrative>`` response.
        """
        provider = MagicMock()

        def _side_effect(messages):
            for msg in messages:
                content = msg.get("content", "")

                # ---- Plot analysis (pre-DM) ----
                if "analytical scribe" in content:
                    return {
                        "content": (
                            "<timeline>\n"
                            '<entry turn="1">Player exploring the area.</entry>\n'
                            "</timeline>\n"
                            "<plot_threads>\n"
                            '<thread status="open">What mysteries await?</thread>\n'
                            "</plot_threads>\n"
                            "<causality>\n"
                            "The player's actions may reveal hidden secrets.\n"
                            "</causality>\n"
                        ),
                        "usage": {
                            "prompt_tokens": 50,
                            "completion_tokens": 30,
                            "total_tokens": 80,
                        },
                    }

                # ---- Entity analysis (post-DM) ----
                if "meticulous record keeper" in content:
                    return {
                        "content": (
                            "<entity_changes>\n"
                            '<entity action="create" type="place" '
                            'id="dark_forest">\n'
                            '<field name="name">Dark Forest</field>\n'
                            '<field name="description">'
                            "A dense, eerie forest filled with ancient trees."
                            "</field>\n"
                            "</entity>\n"
                            '<entity action="create" type="npc" '
                            'id="forest_spirit">\n'
                            '<field name="name">Forest Spirit</field>\n'
                            '<field name="description">'
                            "A glowing ethereal figure among the trees."
                            "</field>\n"
                            "</entity>\n"
                            "</entity_changes>\n"
                        ),
                        "usage": {
                            "prompt_tokens": 60,
                            "completion_tokens": 40,
                            "total_tokens": 100,
                        },
                    }

            # ---- Default: DM narrative (or summarizer, etc.) ----
            return {
                "content": "<narrative>\nThe adventure continues...\n</narrative>",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

        provider.call.side_effect = _side_effect
        return provider

    # ==================================================================
    # Main E2E test
    # ==================================================================

    def test_full_game_turns_with_record_keeper(self, tmp_path: Path) -> None:
        """Full end-to-end smoke test: 3 turns with RecordKeeper.

        Coverage:
        * Turn loop does not raise or yield error events.
        * Entity files (NPCs, places) are created on disk after turns.
        * Entity data can be read back and matches expectations.
        * Changelog file is written to disk.
        * Pre-DM Record-Keeper context is injected into DM LLM calls.
        * World-state turn count is updated correctly.
        * RecordKeeper is passed per-DM instance (no global state).
        """
        # ------------------------------------------------------------------
        # Arrange
        # ------------------------------------------------------------------
        mock_provider = self._make_mock_provider()
        character = self._make_character()
        world_state = self._make_world_state()

        entity_storage = EntityStorage(data_dir=tmp_path / "saves" / "test-hero")
        record_keeper = RecordKeeperAgent(
            llm_provider=mock_provider,
            entity_storage=entity_storage,
            character_name="TestHero",
        )

        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=world_state,
            character=character,
            record_keeper=record_keeper,
        )

        # ------------------------------------------------------------------
        # Act — run 3 turns
        # ------------------------------------------------------------------
        player_inputs = [
            "I enter the dark forest ahead.",
            "I search for any signs of life.",
            "I approach the glowing figure.",
        ]

        for turn_idx, player_input in enumerate(player_inputs):
            events = list(dm.process_turn_stream(player_input))

            # -- Assert: no error events --
            error_events = [e for e in events if e.get("event") == "error"]
            assert len(error_events) == 0, (
                f"Turn {turn_idx + 1} produced error events: {error_events}"
            )

            # -- Assert: exactly one done event --
            done_events = [e for e in events if e.get("event") == "done"]
            assert len(done_events) == 1, (
                f"Turn {turn_idx + 1} expected 1 'done' event, got {len(done_events)}"
            )

            # -- Assert: a narrative event was yielded --
            narrative_events = [e for e in events if e.get("event") == "narrative"]
            assert len(narrative_events) >= 1, (
                f"Turn {turn_idx + 1} expected at least 1 'narrative' event, "
                f"got {len(narrative_events)}"
            )

        # ------------------------------------------------------------------
        # Assert — entity files on disk
        # ------------------------------------------------------------------
        entities_dir = tmp_path / "saves" / "test-hero" / "entities"

        # Type directories
        assert (entities_dir / "npcs").exists(), "NPC directory not created"
        assert (entities_dir / "places").exists(), "Place directory not created"

        # At least one file in each directory
        npc_files = list((entities_dir / "npcs").iterdir())
        place_files = list((entities_dir / "places").iterdir())
        assert len(npc_files) > 0, "No NPC entity files written to disk"
        assert len(place_files) > 0, "No Place entity files written to disk"

        # ------------------------------------------------------------------
        # Assert — entity data correctness
        # ------------------------------------------------------------------
        forest_place = entity_storage.get_entity("place", "dark_forest")
        assert forest_place is not None, "Entity 'dark_forest' not found in storage"
        assert forest_place.get("name") == "Dark Forest", (
            f"Expected name 'Dark Forest', got {forest_place.get('name')!r}"
        )

        spirit_npc = entity_storage.get_entity("npc", "forest_spirit")
        assert spirit_npc is not None, "Entity 'forest_spirit' not found in storage"
        assert spirit_npc.get("name") == "Forest Spirit", (
            f"Expected name 'Forest Spirit', got {spirit_npc.get('name')!r}"
        )

        # ------------------------------------------------------------------
        # Assert — changelog
        # ------------------------------------------------------------------
        changelog_path = entities_dir / "changelog.json"
        assert changelog_path.exists(), "Changelog file not created on disk"

        # ------------------------------------------------------------------
        # Assert — world-state turn count
        # ------------------------------------------------------------------
        assert world_state.turn_count == 3, (
            f"Expected world_state.turn_count == 3, got {world_state.turn_count}"
        )

        # ------------------------------------------------------------------
        # Assert — pre-DM context was injected into DM calls
        # ------------------------------------------------------------------
        # The DM's LLM call includes system messages prefixed with
        # "RECORD-KEEPER:" (injected by ``context_builder.build_context``).
        # Walk all captured call arguments to find at least one DM call
        # that contains a RECORD-KEEPER message.
        dm_call_with_rk = False
        for call_args in mock_provider.call.call_args_list:
            args, _kwargs = call_args
            msgs = args[0]  # messages list (first positional arg)
            has_dm_prompt = any("Dungeon Master" in m.get("content", "") for m in msgs)
            has_rk_context = any("RECORD-KEEPER" in m.get("content", "") for m in msgs)
            if has_dm_prompt and has_rk_context:
                dm_call_with_rk = True
                break

        assert dm_call_with_rk, (
            "No DM LLM call found with RECORD-KEEPER context injected. "
            "Expected at least one DM call (containing 'Dungeon Master' "
            "prompt) to also contain a 'RECORD-KEEPER:' system message."
        )

        # ------------------------------------------------------------------
        # Assert — plot-analysis calls were made (pre-DM)
        # ------------------------------------------------------------------
        plot_call_found = any(
            "analytical scribe" in m.get("content", "")
            for call_args in mock_provider.call.call_args_list
            for m in call_args[0][0]  # messages list
        )
        assert plot_call_found, (
            "No plot-analysis LLM call detected. "
            "Expected at least one call with 'analytical scribe' prompt."
        )

        # ------------------------------------------------------------------
        # Assert — entity-analysis calls were made (post-DM)
        # ------------------------------------------------------------------
        entity_call_found = any(
            "meticulous record keeper" in m.get("content", "")
            for call_args in mock_provider.call.call_args_list
            for m in call_args[0][0]  # messages list
        )
        assert entity_call_found, (
            "No entity-analysis LLM call detected. "
            "Expected at least one call with 'meticulous record keeper' prompt."
        )

    # ==================================================================
    # Regression test
    # ==================================================================

    def test_dm_without_record_keeper_still_works(self, tmp_path: Path) -> None:
        """DM without RecordKeeper works exactly as before (regression).

        When no RecordKeeper is configured, the DM should:
        * Process a turn without errors.
        * Yield a ``narrative`` event with expected content.
        * Yield a ``done`` event.
        * Not crash or produce any ``error`` events.
        * Not contain any RECORD-KEEPER context in its LLM calls.
        """
        # ------------------------------------------------------------------
        # Arrange
        # ------------------------------------------------------------------
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "<narrative>\nThe adventure begins!\n</narrative>",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        character = self._make_character()
        world_state = self._make_world_state()

        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=world_state,
            character=character,
            # No record_keeper
        )

        # ------------------------------------------------------------------
        # Act
        # ------------------------------------------------------------------
        events = list(dm.process_turn_stream("Hello world"))

        # ------------------------------------------------------------------
        # Assert
        # ------------------------------------------------------------------
        # No error events
        error_events = [e for e in events if e.get("event") == "error"]
        assert len(error_events) == 0, f"Unexpected error events: {error_events}"

        # Done event present
        done_events = [e for e in events if e.get("event") == "done"]
        assert len(done_events) == 1, f"Expected 1 'done' event, got {len(done_events)}"

        # Narrative event present with expected content
        narrative_events = [e for e in events if e.get("event") == "narrative"]
        assert len(narrative_events) == 1, (
            f"Expected 1 'narrative' event, got {len(narrative_events)}"
        )
        assert "adventure begins" in narrative_events[0]["data"]["content"].lower()

        # No RECORD-KEEPER context in the DM call
        for call_args in mock_provider.call.call_args_list:
            args, _kwargs = call_args
            msgs = args[0]
            for msg in msgs:
                assert "RECORD-KEEPER" not in msg.get("content", ""), (
                    "DM call should not contain RECORD-KEEPER context "
                    "when no RecordKeeper is configured"
                )

        # World-state turn count updated
        assert world_state.turn_count == 1, (
            f"Expected turn_count=1, got {world_state.turn_count}"
        )

        # No entity directories created (no RecordKeeper)
        entities_dir = tmp_path / "saves" / "test-hero" / "entities"
        assert not entities_dir.exists(), (
            "Entity directory should not be created without a RecordKeeper"
        )
