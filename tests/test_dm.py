"""Tests for DungeonMaster persistent cache.

The DM cache keeps DM instances alive across HTTP requests, keyed by
character_id.  This gives each game its own long-lived DM that retains
conversation history without serializing to WorldState.
"""

from __future__ import annotations

from app.agents.dm import DungeonMaster
from app.world.model import WorldState


class TestDMCache:
    """Tests that the DM cache stores and retrieves DMs by character_id."""

    def test_cache_stores_dm_for_new_character(self) -> None:
        """A new character_id creates a fresh DM and caches it."""
        from app.server import _dm_cache

        _dm_cache.clear()

        character = {"id": "hero_01", "name": "Thorn"}
        character_id = character.get("id") or ""

        dm = DungeonMaster(
            llm_provider=None,
            world_state=WorldState(),
            character=character,
        )

        _dm_cache[character_id] = dm

        assert character_id in _dm_cache
        assert _dm_cache[character_id] is dm

    def test_cache_retrieves_dm_for_existing_character(self) -> None:
        """An existing character_id returns the cached DM."""
        from app.server import _dm_cache

        _dm_cache.clear()

        character = {"id": "hero_02", "name": "Lyra"}
        character_id = character.get("id") or ""

        original_dm = DungeonMaster(
            llm_provider=None,
            world_state=WorldState(),
            character=character,
        )

        _dm_cache[character_id] = original_dm

        retrieved_dm = _dm_cache.get(character_id)

        assert retrieved_dm is original_dm

    def test_cache_different_ids_are_separate(self) -> None:
        """Different character_ids produce different DM instances."""
        from app.server import _dm_cache

        _dm_cache.clear()

        dm1 = DungeonMaster(
            llm_provider=None,
            world_state=WorldState(character_id="hero_a"),
            character={"id": "hero_a", "name": "A"},
        )
        dm2 = DungeonMaster(
            llm_provider=None,
            world_state=WorldState(character_id="hero_b"),
            character={"id": "hero_b", "name": "B"},
        )

        _dm_cache["hero_a"] = dm1
        _dm_cache["hero_b"] = dm2

        assert _dm_cache["hero_a"] is dm1
        assert _dm_cache["hero_b"] is dm2
        assert _dm_cache["hero_a"] is not _dm_cache["hero_b"]

    def test_cache_empty_for_none_character_id(self) -> None:
        """When character_id is None, no caching happens."""
        from app.server import _dm_cache

        _dm_cache.clear()

        DungeonMaster(
            llm_provider=None,
            world_state=WorldState(),
            character=None,
        )

        assert len(_dm_cache) == 0


class TestDMHistoryPersistence:
    """Tests that DM conversation history persists across requests via cache."""

    def test_dm_retains_history_across_turns(self) -> None:
        """A cached DM keeps its conversation history between turns."""
        ws = WorldState()
        dm = DungeonMaster(
            llm_provider=None,
            world_state=ws,
            character={"id": "hero_10", "name": "Kael"},
        )

        # First turn
        result1 = dm.process_turn("I enter the dungeon")
        assert result1["ok"] is True
        assert len(dm.history.recent_turns) == 1
        assert dm.history.recent_turns[0]["user"] == "I enter the dungeon"

        # Second turn — same DM, history preserved
        result2 = dm.process_turn("I light a torch")
        assert result2["ok"] is True
        assert len(dm.history.recent_turns) == 2
        assert dm.history.recent_turns[0]["user"] == "I enter the dungeon"
        assert dm.history.recent_turns[1]["user"] == "I light a torch"

    def test_dm_history_survives_world_state_replacement(self) -> None:
        """DM history persists even when world_state is replaced."""
        ws1 = WorldState()
        dm = DungeonMaster(
            llm_provider=None,
            world_state=ws1,
            character={"id": "hero_11", "name": "Mira"},
        )

        dm.process_turn("Turn one")
        assert len(dm.history.recent_turns) == 1

        # Replace world state (simulating a new request with fresh state)
        ws2 = WorldState()
        dm.world_state = ws2

        # History should still be intact
        assert len(dm.history.recent_turns) == 1
        assert dm.history.recent_turns[0]["user"] == "Turn one"

    def test_multiple_turns_accumulate_in_history(self) -> None:
        """Multiple process_turn calls accumulate history correctly."""
        dm = DungeonMaster(
            llm_provider=None,
            world_state=None,
            character=None,
        )

        for i in range(3):
            dm.process_turn(f"Action {i}")

        assert len(dm.history.recent_turns) == 3
        assert dm.history.recent_turns[0]["user"] == "Action 0"
        assert dm.history.recent_turns[2]["user"] == "Action 2"


class TestDMCacheCleanup:
    """Tests for the DM cache cleanup mechanism."""

    def test_cleanup_does_nothing_when_cache_small(self) -> None:
        """Cache under the limit is not touched."""
        from app.server import _cleanup_stale_dms, _dm_cache

        _dm_cache.clear()

        for i in range(5):
            _dm_cache[f"hero_{i}"] = DungeonMaster(
                llm_provider=None,
                world_state=WorldState(),
                character={"id": f"hero_{i}", "name": f"H{i}"},
            )

        _cleanup_stale_dms()

        assert len(_dm_cache) == 5

    def test_cleanup_evicts_when_cache_exceeds_limit(self) -> None:
        """Cache over 50 entries is trimmed to 50."""
        from app.server import _cleanup_stale_dms, _dm_cache

        _dm_cache.clear()
        # Reset the throttle so cleanup runs immediately
        import app.server as server_mod

        server_mod._dm_cache_cleanup_time = 0.0

        for i in range(55):
            _dm_cache[f"hero_{i}"] = DungeonMaster(
                llm_provider=None,
                world_state=WorldState(),
                character={"id": f"hero_{i}", "name": f"H{i}"},
            )

        _cleanup_stale_dms()

        assert len(_dm_cache) <= 50


class TestDMProcessTurnStreamHistory:
    """Tests that process_turn_stream records history."""

    def test_stream_records_history(self) -> None:
        """process_turn_stream must add turns to history."""
        ws = WorldState()
        dm = DungeonMaster(
            llm_provider=None,
            world_state=ws,
            character=None,
        )

        list(dm.process_turn_stream("Hello, DM!"))

        # Should have recorded history
        assert len(dm.history.recent_turns) == 1
        assert dm.history.recent_turns[0]["user"] == "Hello, DM!"

    def test_stream_multiple_turns(self) -> None:
        """Multiple stream calls accumulate history."""
        ws = WorldState()
        dm = DungeonMaster(
            llm_provider=None,
            world_state=ws,
            character=None,
        )

        for i in range(3):
            list(dm.process_turn_stream(f"Action {i}"))

        assert len(dm.history.recent_turns) == 3


class TestDMProcessTurnHistory:
    """Tests that process_turn records history."""

    def test_process_turn_records_history(self) -> None:
        """process_turn must add turns to history."""
        dm = DungeonMaster(
            llm_provider=None,
            world_state=None,
            character=None,
        )

        result = dm.process_turn("I draw my sword")

        assert result["ok"] is True
        assert len(dm.history.recent_turns) == 1
        assert dm.history.recent_turns[0]["user"] == "I draw my sword"

    def test_process_turn_multiple_turns_accumulate(self) -> None:
        """Multiple process_turn calls accumulate history."""
        dm = DungeonMaster(
            llm_provider=None,
            world_state=None,
            character=None,
        )

        dm.process_turn("First action")
        dm.process_turn("Second action")
        dm.process_turn("Third action")

        assert len(dm.history.recent_turns) == 3
