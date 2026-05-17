"""Tests for the DM agent module — Phases 5.1 and 5.2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agents.dm import DM_SYSTEM_PROMPT, DungeonMaster

# ---------------------------------------------------------------------------
# DM_SYSTEM_PROMPT
# ---------------------------------------------------------------------------


class TestDMSystemPrompt:
    """Tests for the ``DM_SYSTEM_PROMPT`` constant."""

    def test_is_non_empty_string(self) -> None:
        """The system prompt should be a non-empty string."""
        assert isinstance(DM_SYSTEM_PROMPT, str)
        assert len(DM_SYSTEM_PROMPT) > 0

    def test_has_minimum_length(self) -> None:
        """The system prompt should be at least 500 characters long."""
        assert len(DM_SYSTEM_PROMPT) >= 500

    def test_contains_narrative_section(self) -> None:
        """The prompt should reference 'narrative' as a key concept."""
        assert "narrative" in DM_SYSTEM_PROMPT.lower()

    def test_contains_tool_reference(self) -> None:
        """The prompt should reference 'tool' as a key concept."""
        assert "tool" in DM_SYSTEM_PROMPT.lower()

    def test_contains_dice_reference(self) -> None:
        """The prompt should reference 'dice' as a mechanic."""
        assert "dice" in DM_SYSTEM_PROMPT.lower()

    def test_contains_state_reference(self) -> None:
        """The prompt should reference 'state' or 'state_change'."""
        assert "state" in DM_SYSTEM_PROMPT.lower() or "state_change" in DM_SYSTEM_PROMPT

    def test_contains_tool_availability(self) -> None:
        """The prompt should list available tools."""
        assert "# AVAILABLE TOOLS" in DM_SYSTEM_PROMPT

    def test_contains_output_format(self) -> None:
        """The prompt should specify output format instructions."""
        assert "OUTPUT FORMAT" in DM_SYSTEM_PROMPT

    def test_contains_constraints_section(self) -> None:
        """The prompt should have a constraints section."""
        assert "CONSTRAINTS" in DM_SYSTEM_PROMPT

    def test_describes_role(self) -> None:
        """The prompt should define the DM's role."""
        assert "Dungeon Master" in DM_SYSTEM_PROMPT

    def test_mentions_tone(self) -> None:
        """The prompt should describe the expected tone."""
        assert "TONE" in DM_SYSTEM_PROMPT

    def test_includes_tool_names(self) -> None:
        """The prompt should name each available tool."""
        for tool in ("dice", "table", "skill_check", "attack", "saving_throw"):
            assert tool in DM_SYSTEM_PROMPT, (
                f"Expected tool '{tool}' to be mentioned in the prompt"
            )

    def test_contains_three_concerns_separation(self) -> None:
        """The prompt should explain the separation of concerns."""
        keywords = ("Narrative decisions", "Numeric outcomes", "Persistent truth")
        for kw in keywords:
            assert kw in DM_SYSTEM_PROMPT, f"Expected '{kw}' to appear in the prompt"

    def test_forbids_simulating_dice(self) -> None:
        """The prompt should forbid the DM from simulating dice rolls."""
        assert "Never simulate" in DM_SYSTEM_PROMPT

    def test_forbids_direct_state_updates(self) -> None:
        """The prompt should forbid the DM from updating state directly."""
        assert "Never update" in DM_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_abilities() -> dict[str, int]:
    """Return a standard ability score array for testing."""
    return {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}


# ---------------------------------------------------------------------------
# DungeonMaster
# ---------------------------------------------------------------------------


class TestDungeonMasterInit:
    """Tests for ``DungeonMaster`` instantiation."""

    def test_can_instantiate_with_none_params(self) -> None:
        """DungeonMaster should be instantiable with all-None params."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        assert dm is not None
        assert dm.llm_provider is None
        assert dm.world_state is None
        assert dm.character is None

    def test_stores_llm_provider_reference(self) -> None:
        """The llm_provider should be stored on the instance."""
        dm = DungeonMaster(
            llm_provider="mock_provider", world_state=None, character=None
        )
        assert dm.llm_provider == "mock_provider"

    def test_stores_world_state_reference(self) -> None:
        """The world_state should be stored on the instance."""
        dm = DungeonMaster(llm_provider=None, world_state="mock_world", character=None)
        assert dm.world_state == "mock_world"

    def test_stores_character_reference(self) -> None:
        """The character should be stored on the instance."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character="mock_char")
        assert dm.character == "mock_char"


class TestDungeonMasterBuildContext:
    """Tests for ``DungeonMaster._build_context``."""

    def test_returns_list_of_dicts(self) -> None:
        """_build_context should return a list of dicts with role and content."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        context = dm._build_context("Hello, DM!")
        assert isinstance(context, list)
        assert len(context) > 0
        for msg in context:
            assert isinstance(msg, dict)
            assert "role" in msg
            assert "content" in msg

    def test_starts_with_system_message(self) -> None:
        """The first message should be a system message with the DM prompt."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        context = dm._build_context("Hello, DM!")
        assert context[0]["role"] == "system"
        assert context[0]["content"] == DM_SYSTEM_PROMPT

    def test_ends_with_user_message(self) -> None:
        """The last message should contain the player input."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        context = dm._build_context("I open the door.")
        assert context[-1]["role"] == "user"
        assert context[-1]["content"] == "I open the door."

    def test_includes_world_state_when_available(self) -> None:
        """World state info should be included when the DM has it."""
        from app.world.model import WorldState

        ws = WorldState(current_location="old_tower", turn_count=5)
        dm = DungeonMaster(llm_provider=None, world_state=ws, character=None)
        context = dm._build_context("Hello")
        # Should have system prompt + world state + user message
        assert len(context) == 3
        assert context[1]["role"] == "system"
        assert "old_tower" in context[1]["content"]

    def test_includes_character_when_available(self) -> None:
        """Character info should be included when the DM has it."""
        from app.character.model import Character

        char = Character(
            name="Thorn",
            character_class="Fighter",
            level=3,
            hp=24,
            max_hp=30,
            ac=18,
            abilities=_default_abilities(),
        )
        dm = DungeonMaster(llm_provider=None, world_state=None, character=char)
        context = dm._build_context("Hello")
        # Should have system prompt + character + user message
        assert len(context) == 3
        # The character message should contain the character name
        char_messages = [m for m in context if "Thorn" in str(m.get("content", ""))]
        assert len(char_messages) == 1

    def test_build_context_with_all_params(self) -> None:
        """Context should include system, world, character, and user messages."""
        from app.character.model import Character
        from app.world.model import WorldState

        ws = WorldState(current_location="dark_forest", turn_count=3)
        char = Character(
            name="Kaelen",
            character_class="Rogue",
            level=2,
            hp=14,
            max_hp=14,
            ac=14,
            abilities=_default_abilities(),
        )
        dm = DungeonMaster(llm_provider=None, world_state=ws, character=char)
        context = dm._build_context("I sneak into the camp.")
        # system prompt + world state + character + user input = 4 messages
        assert len(context) == 4
        assert context[-1]["content"] == "I sneak into the camp."


class TestDungeonMasterProcessTurn:
    """Tests for ``DungeonMaster.process_turn``."""

    def test_returns_expected_keys(self) -> None:
        """process_turn should return a dict with expected keys."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result = dm.process_turn("Hello")
        expected_keys = {
            "narrative",
            "state_changes",
            "tool_results",
            "turn_count",
            "ok",
            "error",
            "warnings",
        }
        assert set(result.keys()) == expected_keys

    def test_returns_narrative(self) -> None:
        """process_turn should return a narrative string."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result = dm.process_turn("Hello")
        assert isinstance(result["narrative"], str)
        assert len(result["narrative"]) > 0

    def test_returns_ok_true(self) -> None:
        """Successful turn should return ok=True."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result = dm.process_turn("Hello")
        assert result["ok"] is True

    def test_increments_turn_count(self) -> None:
        """Each call should increment turn_count."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result1 = dm.process_turn("First")
        result2 = dm.process_turn("Second")
        assert result2["turn_count"] == result1["turn_count"] + 1

    def test_empty_input_returns_error(self) -> None:
        """Empty input should return error."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result = dm.process_turn("")
        assert result["ok"] is False
        assert "non-empty string" in result.get("error", "").lower()

    def test_handles_tool_requests(self) -> None:
        """process_turn should execute tool requests."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        # The canned response has no tool requests, so this just verifies
        # the path works without error
        result = dm.process_turn("Check for traps")
        assert result["ok"] is True
        assert isinstance(result["tool_results"], list)

    def test_handles_provider_call(self) -> None:
        """When llm_provider is set, it should be called."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": (
                "<narrative>\nYou see a room.\n</narrative>\n"
                '<tool_request name="dice" params=\'{"formula":"d20"}\' />'
            ),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=None,
            character=None,
        )
        result = dm.process_turn("Hello")
        assert result["ok"] is True
        # The second call (after tool injection) would also happen
        assert mock_provider.call.call_count >= 1

    def test_provider_failure_returns_error(self) -> None:
        """If LLM provider fails, process_turn should return error."""
        mock_provider = MagicMock()
        mock_provider.call.side_effect = RuntimeError("Provider offline")
        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=None,
            character=None,
        )
        result = dm.process_turn("Hello")
        assert result["ok"] is False
        assert "error" in result

    def test_applies_state_changes(self) -> None:
        """State changes should be applied to world_state."""
        from app.world.model import WorldState

        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": (
                "<narrative>\nYou pick up a sword.\n</narrative>\n"
                '<state_change action="append" path="inventory" value="Iron Sword" />'
            ),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        ws = WorldState(inventory=[])
        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=ws,
            character=None,
        )
        result = dm.process_turn("I pick up the sword.")
        assert result["ok"] is True
        assert len(result["state_changes"]) > 0
        # Inventory should have the sword
        assert "Iron Sword" in dm.world_state.inventory

    def test_invalid_state_changes_are_skipped(self) -> None:
        """Invalid state changes should be logged and skipped."""
        from app.world.model import WorldState

        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": (
                "<narrative>\nSomething happens.\n</narrative>\n"
                '<state_change action="set" path="invalid_field" value="test" />'
            ),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        ws = WorldState()
        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=ws,
            character=None,
        )
        result = dm.process_turn("Do something")
        assert result["ok"] is True
        # The invalid change should be skipped
        assert len(result["state_changes"]) == 0


# ---------------------------------------------------------------------------
# SessionHistory
# ---------------------------------------------------------------------------


class TestSessionHistory:
    """Tests for the ``SessionHistory`` class."""

    def test_starts_empty(self) -> None:
        """A fresh SessionHistory should have no turns and empty summary."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        assert len(sh.recent_turns) == 0
        assert sh.get_context_messages() == []
        assert sh.get_summary() == ""

    def test_add_turn_stores_it(self) -> None:
        """Adding a turn should make it available in context messages."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.add_turn("Hello", "Hi there!")
        msgs = sh.get_context_messages()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "Hello"}
        assert msgs[1] == {"role": "assistant", "content": "Hi there!"}

    def test_add_multiple_turns(self) -> None:
        """Multiple turns should appear in chronological order."""
        from app.agents.history import SessionHistory

        sh = SessionHistory(max_turns=10)
        sh.add_turn("First", "Response 1")
        sh.add_turn("Second", "Response 2")
        msgs = sh.get_context_messages()
        assert len(msgs) == 4
        assert msgs[0]["content"] == "First"
        assert msgs[1]["content"] == "Response 1"
        assert msgs[2]["content"] == "Second"
        assert msgs[3]["content"] == "Response 2"

    def test_respects_max_turns(self) -> None:
        """When max_turns is exceeded, the oldest turn should drop off."""
        from app.agents.history import SessionHistory

        sh = SessionHistory(max_turns=2)
        sh.add_turn("Turn 1", "Resp 1")
        sh.add_turn("Turn 2", "Resp 2")
        sh.add_turn("Turn 3", "Resp 3")
        msgs = sh.get_context_messages()
        assert len(msgs) == 4  # 2 turns * 2 messages each
        assert msgs[0]["content"] == "Turn 2"  # oldest dropped
        assert msgs[2]["content"] == "Turn 3"

    def test_to_dict_round_trip(self) -> None:
        """Serialization round-trip should preserve all data."""
        from app.agents.history import SessionHistory

        sh = SessionHistory(max_turns=3)
        sh.add_turn("Hello", "Hi")
        sh.add_turn("How are you?", "Good!")
        data = sh.to_dict()

        assert data["max_turns"] == 3
        assert len(data["recent_turns"]) == 2
        assert data["compressed_summary"] == ""

        restored = SessionHistory.from_dict(data)
        assert restored.max_turns == 3
        assert len(restored.recent_turns) == 2
        assert restored.get_context_messages() == sh.get_context_messages()
        assert restored.get_summary() == sh.get_summary()

    def test_from_dict_default_max_turns(self) -> None:
        """from_dict should use default max_turns when key is missing."""
        from app.agents.history import SessionHistory

        restored = SessionHistory.from_dict(
            {"recent_turns": [], "compressed_summary": ""}
        )
        assert restored.max_turns == SessionHistory.MAX_RECENT_TURNS

    def test_clear_resets_everything(self) -> None:
        """clear() should remove all turns and summary."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.add_turn("Hello", "Hi")
        sh.compressed_summary = "Some old summary"
        sh.clear()
        assert len(sh.recent_turns) == 0
        assert sh.compressed_summary == ""
        assert sh.get_context_messages() == []

    def test_max_turns_class_constant(self) -> None:
        """MAX_RECENT_TURNS should be 5 by default."""
        from app.agents.history import SessionHistory

        assert SessionHistory.MAX_RECENT_TURNS == 5

    def test_default_constructor_uses_5(self) -> None:
        """Default max_turns should be 5."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        assert sh.max_turns == 5
        assert sh.recent_turns.maxlen == 5

    # ------------------------------------------------------------------
    # get_turns_text
    # ------------------------------------------------------------------

    def test_get_turns_text_returns_empty_for_empty_history(self) -> None:
        """get_turns_text should return empty string when no turns exist."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        assert sh.get_turns_text() == ""

    def test_get_turns_text_formats_single_turn(self) -> None:
        """get_turns_text should format a single turn with turn number."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.add_turn("Hello", "Hi there!")
        text = sh.get_turns_text()
        assert "[Turn 1]" in text
        assert "Player: Hello" in text
        assert "DM: Hi there!" in text

    def test_get_turns_text_formats_multiple_turns(self) -> None:
        """get_turns_text should format multiple turns separated by blank lines."""
        from app.agents.history import SessionHistory

        sh = SessionHistory(max_turns=10)
        sh.add_turn("First", "Response 1")
        sh.add_turn("Second", "Response 2")
        text = sh.get_turns_text()
        assert "[Turn 1]" in text
        assert "[Turn 2]" in text
        assert "Player: First" in text
        assert "Player: Second" in text
        assert "DM: Response 1" in text
        assert "DM: Response 2" in text
        assert "\n\n" in text

    def test_get_turns_text_includes_player_and_dm_labels(self) -> None:
        """Each turn should have Player: and DM: labels."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.add_turn("Attack the goblin", "The goblin dodges!")
        text = sh.get_turns_text()
        assert "Player:" in text
        assert "DM:" in text

    # ------------------------------------------------------------------
    # set_summary
    # ------------------------------------------------------------------

    def test_set_summary_stores_text(self) -> None:
        """set_summary should store the provided text."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.set_summary("Player fought a dragon")
        assert sh.compressed_summary == "Player fought a dragon"
        assert sh.get_summary() == "Player fought a dragon"

    def test_set_summary_overwrites_previous(self) -> None:
        """set_summary should replace any existing summary."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.set_summary("First summary")
        sh.set_summary("Second summary")
        assert sh.compressed_summary == "Second summary"

    def test_set_summary_accepts_empty_string(self) -> None:
        """set_summary should accept an empty string to clear the summary."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.set_summary("Some summary")
        sh.set_summary("")
        assert sh.compressed_summary == ""

    # ------------------------------------------------------------------
    # clear_turns
    # ------------------------------------------------------------------

    def test_clear_turns_empties_buffer(self) -> None:
        """clear_turns should remove all recent turns from the buffer."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.add_turn("Hello", "Hi")
        sh.add_turn("How are you?", "Good")
        sh.clear_turns()
        assert len(sh.recent_turns) == 0
        assert sh.get_context_messages() == []

    def test_clear_turns_leaves_summary_intact(self) -> None:
        """clear_turns should keep compressed_summary unchanged."""
        from app.agents.history import SessionHistory

        sh = SessionHistory()
        sh.add_turn("Hello", "Hi")
        sh.set_summary("Previous summary")
        sh.clear_turns()
        assert len(sh.recent_turns) == 0
        assert sh.compressed_summary == "Previous summary"
        assert sh.get_summary() == "Previous summary"


class TestDungeonMasterHistoryIntegration:
    """Tests for DungeonMaster integration with SessionHistory."""

    def test_history_is_session_history_instance(self) -> None:
        """DM should have a SessionHistory instance."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        from app.agents.history import SessionHistory

        assert isinstance(dm.history, SessionHistory)

    def test_history_initializes_empty(self) -> None:
        """DM's history should start empty."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        assert dm.history.get_context_messages() == []
        assert dm.history.get_summary() == ""

    def test_process_turn_records_history(self) -> None:
        """process_turn should record the exchange in history."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        result = dm.process_turn("Hello")
        assert result["ok"] is True
        msgs = dm.history.get_context_messages()
        assert len(msgs) == 2  # user + assistant
        assert msgs[0] == {"role": "user", "content": "Hello"}
        assert msgs[1]["role"] == "assistant"
        assert len(msgs[1]["content"]) > 0

    def test_multiple_turns_appear_in_context(self) -> None:
        """After multiple turns, context should include all history."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        dm.process_turn("First")
        dm.process_turn("Second")
        dm.process_turn("Third")
        msgs = dm.history.get_context_messages()
        assert len(msgs) == 6  # 3 turns * 2 = 6 messages
        assert msgs[0]["content"] == "First"
        assert msgs[2]["content"] == "Second"
        assert msgs[4]["content"] == "Third"

    def test_build_context_includes_history(self) -> None:
        """Context built after turns should include history messages."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        dm.process_turn("Hello")
        dm.process_turn("I open the door")
        # Build context for the next turn
        context = dm._build_context("I step inside")
        # Should have: system + world(if avail) + char(if avail) + history + user
        # At minimum: system + history(4 msgs) + user
        history_msgs = dm.history.get_context_messages()
        # The history messages appear before the final user message
        for hmsg in history_msgs:
            assert hmsg in context
        assert context[-1]["role"] == "user"
        assert context[-1]["content"] == "I step inside"

    def test_history_survives_tool_calls(self) -> None:
        """History should be recorded even when tool calls happen."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": (
                "<narrative>\nYou see a room.\n</narrative>\n"
                '<tool_request name="dice" params=\'{"formula":"d20"}\' />'
            ),
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=None,
            character=None,
        )
        dm.process_turn("Check for traps")
        msgs = dm.history.get_context_messages()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "Check for traps"}

    def test_process_turn_triggers_summarize_at_capacity(self) -> None:
        """After 5 process_turn calls, summarization should trigger."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": "<narrative>Stuff happens.</narrative>",
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        dm = DungeonMaster(
            llm_provider=mock_provider,
            world_state=None,
            character=None,
        )
        with patch(
            "app.agents.dm.summarize_turns", return_value="summary"
        ) as mock_summ:
            for i in range(5):
                dm.process_turn(f"Turn {i + 1}")
        mock_summ.assert_called_once()
        assert dm.history.compressed_summary == "summary"
        assert len(dm.history.recent_turns) == 0


# ---------------------------------------------------------------------------
# _build_context with summary
# ---------------------------------------------------------------------------


class TestDungeonMasterBuildContextSummary:
    """Tests for ``_build_context`` with compressed summary integration."""

    def test_context_includes_summary_when_present(self) -> None:
        """A system message with summary should appear when summary is set."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        dm.history.set_summary("Player entered the dark forest")
        context = dm._build_context("Hello")
        summary_msgs = [m for m in context if "Session summary" in m.get("content", "")]
        assert len(summary_msgs) == 1
        assert summary_msgs[0]["role"] == "system"
        assert "Player entered the dark forest" in summary_msgs[0]["content"]

    def test_context_skips_summary_when_empty(self) -> None:
        """No summary message should appear when compressed_summary is empty."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        context = dm._build_context("Hello")
        summary_msgs = [m for m in context if "Session summary" in m.get("content", "")]
        assert len(summary_msgs) == 0

    def test_context_summary_position(self) -> None:
        """Summary should appear after character info but before history."""
        from app.character.model import Character
        from app.world.model import WorldState

        ws = WorldState(current_location="dark_forest", turn_count=3)
        char = Character(
            name="Kaelen",
            character_class="Rogue",
            level=2,
            hp=14,
            max_hp=14,
            ac=14,
            abilities={
                "STR": 10,
                "DEX": 14,
                "CON": 10,
                "INT": 12,
                "WIS": 10,
                "CHA": 8,
            },
        )
        dm = DungeonMaster(llm_provider=None, world_state=ws, character=char)
        dm.history.add_turn("I sneak ahead", "You move silently through the shadows")
        dm.history.set_summary("Summary text here")
        context = dm._build_context("I continue forward")

        # Summary should be message index 3 (0=system, 1=world, 2=character)
        summary_idx = next(
            i
            for i, m in enumerate(context)
            if "Session summary" in m.get("content", "")
        )
        assert summary_idx == 3, (
            f"Expected summary at index 3, got {summary_idx}. "
            f"Messages: {[m['role'] + ':' + m['content'][:30] for m in context]}"
        )

        # History messages should appear after the summary
        history_idx = next(
            i for i, m in enumerate(context) if m.get("content") == "I sneak ahead"
        )
        assert history_idx > summary_idx


# ---------------------------------------------------------------------------
# _maybe_summarize
# ---------------------------------------------------------------------------


class TestDungeonMasterMaybeSummarize:
    """Tests for ``DungeonMaster._maybe_summarize``."""

    def _full_buffer(self, dm: DungeonMaster) -> None:
        """Fill the DM's history buffer to capacity (5 turns)."""
        for i in range(5):
            dm.history.add_turn(f"Turn {i + 1}", f"Response {i + 1}")

    def test_maybe_summarize_does_nothing_when_buffer_empty(self) -> None:
        """Empty buffer means no trigger, no summarizer call."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        with patch("app.agents.dm.summarize_turns") as mock_summarize:
            dm._maybe_summarize()
        mock_summarize.assert_not_called()
        assert dm.history.compressed_summary == ""

    def test_maybe_summarize_does_not_trigger_at_four_turns(self) -> None:
        """4 turns should not trigger summarization (threshold is 5)."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        for i in range(4):
            dm.history.add_turn(f"Turn {i + 1}", f"Response {i + 1}")
        with patch("app.agents.dm.summarize_turns") as mock_summarize:
            dm._maybe_summarize()
        mock_summarize.assert_not_called()
        assert dm.history.compressed_summary == ""

    def test_maybe_summarize_triggers_when_buffer_full(self) -> None:
        """Buffer at max_turns triggers summarization."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        self._full_buffer(dm)

        with patch(
            "app.agents.dm.summarize_turns",
            return_value="Mocked summary",
        ) as mock_summarize:
            dm._maybe_summarize()

        mock_summarize.assert_called_once()

    def test_maybe_summarize_clears_turns_after_summary(self) -> None:
        """After summarization the turns buffer should be empty."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        self._full_buffer(dm)

        with patch("app.agents.dm.summarize_turns", return_value="Mocked summary"):
            dm._maybe_summarize()

        assert len(dm.history.recent_turns) == 0

    def test_maybe_summarize_stores_summary(self) -> None:
        """After summarization compressed_summary should hold the result."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        self._full_buffer(dm)

        with patch("app.agents.dm.summarize_turns", return_value="Mocked summary"):
            dm._maybe_summarize()

        assert dm.history.compressed_summary == "Mocked summary"
        assert dm.history.get_summary() == "Mocked summary"

    def test_maybe_summarize_handles_summarize_failure(self) -> None:
        """When summarize_turns raises, _maybe_summarize should catch and not crash."""
        dm = DungeonMaster(llm_provider=None, world_state=None, character=None)
        self._full_buffer(dm)

        with patch(
            "app.agents.dm.summarize_turns",
            side_effect=ValueError("LLM failed"),
        ):
            dm._maybe_summarize()  # Should not raise

        # Summary should remain unchanged after failure
        assert dm.history.compressed_summary == ""
        assert dm.history.get_summary() == ""
