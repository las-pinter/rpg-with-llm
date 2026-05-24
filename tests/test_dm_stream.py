"""Tests for DungeonMaster.process_turn_stream generator.

Tests cover event dict format, token streaming, NPC thinking events,
bookkeeping calls (add_turn, _maybe_summarize, _sync_npcs_to_world_state),
impossible action short-circuit, error handling, turn count semantics,
canned response path, and empty narrative retry.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.dm import DungeonMaster
from app.character.model import Character

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_abilities() -> dict[str, int]:
    """Return a standard ability score array for testing."""
    return {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}


def _make_fighter() -> Character:
    """Create a default level 1 Fighter for impossible-action tests."""
    return Character(
        name="Test Fighter",
        character_class="Fighter",
        level=1,
        hp=12,
        max_hp=12,
        ac=18,
        abilities=_default_abilities(),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_stream_provider():
    """A mock LLM provider that streams tokens and supports call()."""
    provider = MagicMock()
    provider.stream.return_value = iter(
        [
            "<narrative>",
            "Hello",
            " world",
            "!",
            "</narrative>",
        ]
    )
    provider.call.return_value = {
        "content": "<narrative>Hello world!</narrative>",
        "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
    }
    return provider


@pytest.fixture
def dm(mock_stream_provider):
    """A DungeonMaster with a mock streaming provider and no state/char."""
    return DungeonMaster(
        llm_provider=mock_stream_provider,
        world_state=None,
        character=None,
    )


# ===========================================================================
# Event format basics
# ===========================================================================


class TestProcessTurnStream:
    """Tests for ``DungeonMaster.process_turn_stream`` generator."""

    # ------------------------------------------------------------------
    # 1. Token streaming
    # ------------------------------------------------------------------

    def test_yields_token_events(self, dm: DungeonMaster) -> None:
        """With a mock provider that streams, should yield token events."""
        events = list(dm.process_turn_stream("Hello"))

        # Should have at least one token event
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) > 0
        # One token per streamed chunk
        assert token_events[0]["data"]["content"] == "<narrative>"
        assert any(e["data"]["content"] == " world" for e in token_events)

        # Should also include final bookkeeping events
        event_types = {e["event"] for e in events}
        assert "state_update" in event_types
        assert "narrative" in event_types
        assert "token_usage" in event_types
        assert "done" in event_types

    # ------------------------------------------------------------------
    # 2. NPC thinking events
    # ------------------------------------------------------------------

    def test_yields_npc_thinking_during_npc_spawning(
        self,
        mock_stream_provider: MagicMock,
    ) -> None:
        """When DM output includes npc_requests, npc_thinking events yielded."""
        mock_stream_provider.stream.return_value = iter(
            [
                "<narrative>The barkeep grunts.</narrative>\n"
                '<npc_request npc_id="tavern_keep" '
                'context="asks about drink" />',
            ]
        )

        dm = DungeonMaster(
            llm_provider=mock_stream_provider,
            world_state=None,
            character=None,
        )

        with patch.object(dm, "_spawn_npcs", return_value=[]):
            events = list(dm.process_turn_stream("I order a drink"))

        npc_events = [e for e in events if e["event"] == "npc_thinking"]
        assert len(npc_events) == 1
        assert npc_events[0]["data"]["npc_id"] == "tavern_keep"
        assert "drink" in npc_events[0]["data"]["hint"]

    # ------------------------------------------------------------------
    # 3. History bookkeeping
    # ------------------------------------------------------------------

    def test_calls_history_add_turn(self, dm: DungeonMaster) -> None:
        """process_turn_stream should call self.history.add_turn()."""
        with patch.object(dm.history, "add_turn") as mock_add_turn:
            list(dm.process_turn_stream("Hello"))

        mock_add_turn.assert_called_once()
        args, _ = mock_add_turn.call_args
        assert args[0] == "Hello"
        assert len(args[1]) > 0  # narrative content

    # ------------------------------------------------------------------
    # 4. Summarization
    # ------------------------------------------------------------------

    def test_calls_maybe_summarize(self, dm: DungeonMaster) -> None:
        """process_turn_stream should call self._maybe_summarize()."""
        with patch.object(dm, "_maybe_summarize") as mock_summarize:
            list(dm.process_turn_stream("Hello"))

        mock_summarize.assert_called_once()

    # ------------------------------------------------------------------
    # 5. NPC sync
    # ------------------------------------------------------------------

    def test_calls_sync_npcs_to_world_state(self, dm: DungeonMaster) -> None:
        """process_turn_stream should call self._sync_npcs_to_world_state()."""
        with patch.object(dm, "_sync_npcs_to_world_state") as mock_sync:
            list(dm.process_turn_stream("Hello"))

        mock_sync.assert_called_once()

    # ------------------------------------------------------------------
    # 6. Impossible action — yields events
    # ------------------------------------------------------------------

    def test_impossible_action_yields_events_and_returns(self) -> None:
        """Impossible actions should yield state+narrative+done and return."""
        char = _make_fighter()
        dm = DungeonMaster(llm_provider=None, world_state=None, character=char)

        events = list(dm.process_turn_stream("I cast fireball at the goblins"))

        event_types = {e["event"] for e in events}
        # Should NOT have token events (no LLM call)
        assert "token" not in event_types
        # Should have the three impossible-path events
        assert "state_update" in event_types
        assert "narrative" in event_types
        assert "done" in event_types
        assert len(events) == 3  # exactly three events

        # Narrative should mention impossibility
        narr = next(e for e in events if e["event"] == "narrative")
        content = narr["data"]["content"].lower()
        assert any(word in content for word in ("beyond", "cannot", "impossible"))

    # ------------------------------------------------------------------
    # 7. Impossible action — bookkeeping
    # ------------------------------------------------------------------

    def test_impossible_action_calls_bookkeeping(self) -> None:
        """Impossible path should also call add_turn + _maybe_summarize."""
        char = _make_fighter()
        dm = DungeonMaster(llm_provider=None, world_state=None, character=char)

        with patch.object(dm.history, "add_turn") as mock_add_turn:
            with patch.object(dm, "_maybe_summarize") as mock_summarize:
                list(
                    dm.process_turn_stream(
                        "I teleport to the dragon's lair",
                    )
                )

        mock_add_turn.assert_called_once()
        args, _ = mock_add_turn.call_args
        assert args[0] == "I teleport to the dragon's lair"
        mock_summarize.assert_called_once()

    # ------------------------------------------------------------------
    # 8. Stream error
    # ------------------------------------------------------------------

    def test_error_during_stream_yields_error_event(
        self,
        dm: DungeonMaster,
        mock_stream_provider: MagicMock,
    ) -> None:
        """If provider.stream() raises, yield error event and stop."""
        mock_stream_provider.stream.side_effect = RuntimeError("Stream failed")

        events = list(dm.process_turn_stream("Hello"))

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["message"] == "LLM stream error"

        # Should NOT have a done event after error
        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 0

    # ------------------------------------------------------------------
    # 9. Turn count semantics
    # ------------------------------------------------------------------

    def test_turn_count_increments_correctly(self, dm: DungeonMaster) -> None:
        """Each call should increment turn_count and reflect in events."""
        # First turn
        events1 = list(dm.process_turn_stream("First"))
        done1 = next(e for e in events1 if e["event"] == "done")
        assert done1["data"]["turn_count"] == 1

        # Second turn — same dm instance
        events2 = list(dm.process_turn_stream("Second"))
        state2 = next(e for e in events2 if e["event"] == "state_update")
        assert state2["data"]["turn_count"] == 2
        done2 = next(e for e in events2 if e["event"] == "done")
        assert done2["data"]["turn_count"] == 2

        # Internal counter matches
        assert dm.turn_count == 2

    # ------------------------------------------------------------------
    # 10. Event dict format
    # ------------------------------------------------------------------

    def test_event_dict_format(self, dm: DungeonMaster) -> None:
        """Each yielded dict should have 'event' and 'data' keys."""
        events = list(dm.process_turn_stream("Hello"))

        for event in events:
            assert "event" in event, f"Missing 'event' key in {event}"
            assert "data" in event, f"Missing 'data' key in {event}"
            assert isinstance(event["data"], dict), (
                f"'data' should be a dict in {event}"
            )

    # ------------------------------------------------------------------
    # 11. Canned response without provider
    # ------------------------------------------------------------------

    def test_canned_response_without_provider(self) -> None:
        """When llm_provider is None, use canned response and still do
        bookkeeping."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)

        with (
            patch.object(dm.history, "add_turn") as mock_add_turn,
            patch.object(dm, "_maybe_summarize") as mock_summarize,
            patch.object(dm, "_sync_npcs_to_world_state") as mock_sync,
        ):
            events = list(dm.process_turn_stream("Hello"))

        # Should have the correct events
        event_types = {e["event"] for e in events}
        assert "state_update" in event_types
        assert "narrative" in event_types
        assert "done" in event_types
        # Should NOT have token events (no provider)
        assert "token" not in event_types
        # Should NOT have error
        assert "error" not in event_types

        # All three bookkeeping calls should be made
        mock_add_turn.assert_called_once()
        mock_summarize.assert_called_once()
        mock_sync.assert_called_once()

    # ------------------------------------------------------------------
    # 12. Empty narrative retry
    # ------------------------------------------------------------------

    def test_empty_narrative_triggers_retry(
        self,
        mock_stream_provider: MagicMock,
    ) -> None:
        """When LLM response has no <narrative> tag, retry should occur."""
        # Stream a response WITHOUT narrative tags
        mock_stream_provider.stream.return_value = iter(
            [
                "This response has no narrative tags.",
            ]
        )

        dm = DungeonMaster(
            llm_provider=mock_stream_provider,
            world_state=None,
            character=None,
        )

        # The retry path calls provider.call() — mock that too
        mock_stream_provider.call.return_value = {
            "content": ("<narrative>The retry narrative.</narrative>"),
            "usage": {},
        }

        events = list(dm.process_turn_stream("Hello"))

        # Should still complete successfully after retry
        event_types = {e["event"] for e in events}
        assert "error" not in event_types
        assert "narrative" in event_types
        assert "done" in event_types

        # The retry narrative should appear
        narr = next(e for e in events if e["event"] == "narrative")
        assert "retry narrative" in narr["data"]["content"].lower()
