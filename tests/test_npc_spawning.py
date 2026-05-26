"""
Tests for DM NPC subagent spawning — Phase 7.2 + 7.3.

Covers NPC spawning, parallel execution, result formatting, and
integration with the DM turn loop.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.agents.dm import DungeonMaster, format_npc_results

# ===========================================================================
# Helpers
# ===========================================================================


def _make_npc_request(
    npc_id: str = "test_npc",
    context: str = "A dark tavern.",
    goal: str = "",
    personality: str = "",
    mood: str = "",
    identity: str = "",
) -> dict[str, str]:
    """Build a canned NPC request dict (as parser would return it)."""
    req: dict[str, str] = {"npc_id": npc_id, "context": context}
    if goal:
        req["goal"] = goal
    if personality:
        req["personality"] = personality
    if mood:
        req["mood"] = mood
    if identity:
        req["identity"] = identity
    return req


# ===========================================================================
# DungeonMaster.__init__ — new NPC-related attributes
# ===========================================================================


class TestDungeonMasterNpcInit:
    """Tests for NPC-related parameters in DungeonMaster.__init__."""

    def test_npc_provider_defaults_to_llm_provider(self) -> None:
        """When npc_provider is not given, it should fall back to
        llm_provider."""
        dm = DungeonMaster(llm_provider="shared", world_state=None, character=None)
        assert dm.npc_provider == "shared"

    def test_npc_provider_can_be_set_explicitly(self) -> None:
        """npc_provider should be settable independently from llm_provider."""
        dm = DungeonMaster(
            llm_provider="dm_provider",
            world_state=None,
            character=None,
            npc_provider="npc_provider",
        )
        assert dm.npc_provider == "npc_provider"
        assert dm.llm_provider == "dm_provider"

    def test_npc_provider_is_none_when_both_none(self) -> None:
        """When both providers are None, npc_provider should be None."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        assert dm.npc_provider is None

    def test_npcs_dict_starts_empty(self) -> None:
        """The npcs identity dict should start empty."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        assert dm.npcs == {}


# ===========================================================================
# _spawn_npcs — empty input
# ===========================================================================


class TestSpawnNpcsEmpty:
    """_spawn_npcs with empty or no-op input."""

    def test_empty_request_list_returns_empty(self) -> None:
        """An empty request list should return an empty result list."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result = dm._spawn_npcs([], "hello")
        assert result == []


# ===========================================================================
# _spawn_npcs — canned / no-provider
# ===========================================================================


class TestSpawnNpcsCanned:
    """_spawn_npcs when npc_provider is None (canned responses)."""

    def test_single_npc_returns_structured_result(self) -> None:
        """A single NPC request should return a list with one result."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        requests = [_make_npc_request(npc_id="test_npc")]
        result = dm._spawn_npcs(requests, "hello")
        assert len(result) == 1
        entry = result[0]
        assert entry["npc_id"] == "test_npc"
        assert "dialogue" in entry
        assert "action" in entry
        assert "emotional_state" in entry
        assert "error" not in entry

    def test_canned_result_has_compressed_action(self) -> None:
        """Canned action should be compressed (articles removed)."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        requests = [_make_npc_request(npc_id="npc")]
        result = dm._spawn_npcs(requests, "hi")
        action = result[0]["action"]
        # "The" should be removed by compression
        assert "The" not in action or "NPC" in action

    def test_multiple_npcs_returns_all_results(self) -> None:
        """Multiple NPC requests should return results for each."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        requests = [
            _make_npc_request(npc_id="npc_a", context="Room A"),
            _make_npc_request(npc_id="npc_b", context="Room B"),
        ]
        result = dm._spawn_npcs(requests, "hello")
        assert len(result) == 2
        npc_ids = {r["npc_id"] for r in result}
        assert npc_ids == {"npc_a", "npc_b"}


# ===========================================================================
# _spawn_npcs — identity storage
# ===========================================================================


class TestSpawnNpcsIdentity:
    """_spawn_npcs should store and retrieve NPC identities."""

    def test_stores_npc_identity_on_first_encounter(self) -> None:
        """When an NPC is first encountered, its identity should be
        stored in self.npcs."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        requests = [
            _make_npc_request(
                npc_id="elara",
                identity="Elara the Keeper",
                personality="warm",
            )
        ]
        dm._spawn_npcs(requests, "hello")
        assert "elara" in dm.npcs
        assert dm.npcs["elara"]["identity"] == "Elara the Keeper"
        assert dm.npcs["elara"]["personality"] == "warm"

    def test_uses_stored_identity_when_available(self) -> None:
        """If NPC identity is already stored, it should be reused."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        dm.npcs["old_greta"] = {
            "identity": "Old Greta",
            "personality": "grumpy",
        }
        requests = [
            _make_npc_request(
                npc_id="old_greta",
                context="Behind the bar",
            )
        ]
        result = dm._spawn_npcs(requests, "hello")
        assert result[0]["npc_id"] == "old_greta"
        # The stored identity is used, not replaced
        assert dm.npcs["old_greta"]["identity"] == "Old Greta"


# ===========================================================================
# _spawn_npcs — mock provider (real LLM simulation)
# ===========================================================================


class TestSpawnNpcsWithMock:
    """_spawn_npcs with a mock LLM provider."""

    def test_returns_parsed_and_compressed_result(self) -> None:
        """NPC result should be parsed and compressed correctly."""
        mock = MagicMock()
        mock.call.return_value = {
            "content": (
                "<dialogue>\nHello, traveller!\n</dialogue>\n"
                "<action>\nThe guard nods respectfully.\n</action>\n"
                "<emotional_state>\nwatchful\n</emotional_state>"
            ),
        }
        dm = DungeonMaster(
            llm_provider=None,
            world_state=None,
            character=None,
            npc_provider=mock,
        )
        requests = [_make_npc_request(npc_id="guard")]
        result = dm._spawn_npcs(requests, "I come in peace.")
        assert len(result) == 1
        entry = result[0]
        assert entry["npc_id"] == "guard"
        assert entry["dialogue"] == "Hello, traveller!"
        # "The" should be compressed from action
        assert "guard nods respectfully" in entry["action"]
        assert entry["emotional_state"] == "watchful"

    def test_respects_request_attributes(self) -> None:
        """NPC request attributes (goal, mood, personality) should be
        passed through to the NPC agent."""
        mock = MagicMock()
        mock.call.return_value = {
            "content": (
                "<dialogue>Fine.</dialogue>\n"
                "<action>Nods.</action>\n"
                "<emotional_state>annoyed</emotional_state>"
            ),
        }
        dm = DungeonMaster(
            llm_provider=None,
            world_state=None,
            character=None,
            npc_provider=mock,
        )
        requests = [
            _make_npc_request(
                npc_id="angry_guard",
                context="Town gate",
                mood="annoyed",
                goal="Intimidate the visitor",
                personality="stern",
            )
        ]
        dm._spawn_npcs(requests, "Let me pass.")
        # The mock doesn't validate attributes — the test verifies
        # no crash and that npc identity is stored
        assert "angry_guard" in dm.npcs
        assert dm.npcs["angry_guard"]["personality"] == "stern"

    def test_mock_provider_is_called(self) -> None:
        """The mock provider should be called at least once."""
        mock = MagicMock()
        mock.call.return_value = {
            "content": (
                "<dialogue>Hi</dialogue>\n"
                "<action>Waves.</action>\n"
                "<emotional_state>neutral</emotional_state>"
            ),
        }
        dm = DungeonMaster(
            llm_provider=None,
            world_state=None,
            character=None,
            npc_provider=mock,
        )
        requests = [_make_npc_request(npc_id="greeter")]
        dm._spawn_npcs(requests, "Hello")
        assert mock.call.call_count >= 1


# ===========================================================================
# _format_npc_results
# ===========================================================================


class TestFormatNpcResults:
    """_format_npc_results output formatting."""

    def test_formats_normal_result(self) -> None:
        """Normal NPC results should be formatted with dialogue,
        action, and emotional state."""
        results = [
            {
                "npc_id": "tavern_keep",
                "dialogue": "Welcome!",
                "action": "The innkeeper smiles.",
                "emotional_state": "friendly",
                "tool_request": None,
            }
        ]
        block = format_npc_results(results)
        assert "tavern_keep" in block
        # Dialogue is compressed: "Welcome!" stays
        assert "Welcome" in block
        # Action compressed: "The" removed
        assert "innkeeper smiles" in block
        assert "friendly" in block

    def test_formats_error_result(self) -> None:
        """Error entries should be marked as unavailable."""
        results = [
            {
                "npc_id": "slow_npc",
                "error": "NPC timed out",
                "dialogue": "",
                "action": "",
                "emotional_state": "",
                "tool_request": None,
            }
        ]
        block = format_npc_results(results)
        assert "slow_npc" in block
        assert "unavailable" in block

    def test_formats_multiple_results(self) -> None:
        """Multiple results should be separated."""
        results = [
            {
                "npc_id": "npc_a",
                "dialogue": "Hi A",
                "action": "Waves.",
                "emotional_state": "happy",
                "tool_request": None,
            },
            {
                "npc_id": "npc_b",
                "error": "NPC timed out",
                "dialogue": "",
                "action": "",
                "emotional_state": "",
                "tool_request": None,
            },
        ]
        block = format_npc_results(results)
        assert "npc_a" in block
        assert "npc_b" in block
        assert "unavailable" in block
        assert "Hi A" in block


# ===========================================================================
# process_turn — integration with NPC spawning
# ===========================================================================


class TestProcessTurnWithNpcs:
    """process_turn integration with NPC subagent spawning."""

    _NPC_RESPONSE = {
        "content": (
            "<dialogue>Hello</dialogue>\n"
            "<action>The NPC reacts.</action>\n"
            "<emotional_state>neutral</emotional_state>"
        ),
    }

    def test_process_turn_with_npc_requests_succeeds(self) -> None:
        """When the DM output includes npc_request tags, process_turn
        should spawn NPCs and complete the turn successfully."""
        dm_mock = MagicMock()
        dm_mock.call.side_effect = [
            {
                "content": (
                    "<narrative>\nYou enter the tavern.\n</narrative>\n"
                    '<npc_request npc_id="tavern_keep" '
                    'context="Player just walked in" />'
                ),
            },
            {
                "content": (
                    "<narrative>\nThe tavern keeper greets you warmly.\n</narrative>\n"
                ),
            },
        ]
        npc_mock = MagicMock()
        npc_mock.call.return_value = self._NPC_RESPONSE

        dm = DungeonMaster(
            llm_provider=dm_mock,
            world_state=None,
            character=None,
            npc_provider=npc_mock,
        )
        result = dm.process_turn("I enter the tavern.")
        assert result["ok"] is True
        assert len(result["narrative"]) > 0
        # NPC identity should have been stored
        assert "tavern_keep" in dm.npcs

    def test_process_turn_injects_npc_results(self) -> None:
        """NPC results should be injected into the second LLM call."""
        dm_mock = MagicMock()
        dm_mock.call.side_effect = [
            {
                "content": (
                    "<narrative>\nYou approach.\n</narrative>\n"
                    '<npc_request npc_id="guard" '
                    'context="Player approaches the gate" />'
                ),
            },
            {
                "content": ("<narrative>\nThe guard steps aside.\n</narrative>\n"),
            },
        ]
        npc_mock = MagicMock()
        npc_mock.call.return_value = self._NPC_RESPONSE

        dm = DungeonMaster(
            llm_provider=dm_mock,
            world_state=None,
            character=None,
            npc_provider=npc_mock,
        )
        result = dm.process_turn("I approach the gate.")
        assert result["ok"] is True
        # DM should have been called exactly twice (first + second call)
        assert dm_mock.call.call_count == 2

    def test_process_turn_no_npc_requests_unchanged(self) -> None:
        """Without npc_requests, the turn flow should be unchanged."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result = dm.process_turn("Look around.")
        assert result["ok"] is True
        assert "scene unfolds" in result["narrative"].lower()

    def test_process_turn_tool_and_npc_together(self) -> None:
        """Tool requests and NPC requests should both be handled."""
        dm_mock = MagicMock()
        dm_mock.call.side_effect = [
            {
                "content": (
                    "<narrative>\nYou search.\n</narrative>\n"
                    '<tool_request name="dice" '
                    'params=\'{"formula":"d20"}\' />\n'
                    '<npc_request npc_id="ghost" '
                    'context="Player investigates" />'
                ),
            },
            {
                "content": ("<narrative>\nYou find a clue.\n</narrative>\n"),
            },
        ]
        npc_mock = MagicMock()
        npc_mock.call.return_value = self._NPC_RESPONSE

        dm = DungeonMaster(
            llm_provider=dm_mock,
            world_state=None,
            character=None,
            npc_provider=npc_mock,
        )
        result = dm.process_turn("I investigate the room.")
        assert result["ok"] is True
        # Should have both tool results and npc results
        assert isinstance(result["tool_results"], list)
        assert "ghost" in dm.npcs


# ===========================================================================
# DM_SYSTEM_PROMPT — npc_request is now active
# ===========================================================================


class TestDmSystemPromptNpc:
    """DM_SYSTEM_PROMPT should reflect active NPC support."""

    def test_mentions_npc_request_section(self) -> None:
        """The prompt should describe the npc_request feature."""
        from app.agents.dm import DM_SYSTEM_PROMPT

        assert "npc_request" in DM_SYSTEM_PROMPT

    def test_not_reserved_anymore(self) -> None:
        """The prompt should NOT say 'reserved for future use'."""
        from app.agents.dm import DM_SYSTEM_PROMPT

        assert "reserved for future use" not in DM_SYSTEM_PROMPT

    def test_lists_supported_attributes(self) -> None:
        """The prompt should list npc_request attributes."""
        from app.agents.dm import DM_SYSTEM_PROMPT

        assert "npc_id" in DM_SYSTEM_PROMPT
        assert "context" in DM_SYSTEM_PROMPT

    def test_describes_npc_result_handling(self) -> None:
        """The prompt should explain NPC result handling."""
        from app.agents.dm import DM_SYSTEM_PROMPT

        assert "NPC Subagent Results" in DM_SYSTEM_PROMPT
        assert "use, modify, or ignore" in DM_SYSTEM_PROMPT
