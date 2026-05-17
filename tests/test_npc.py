"""Tests for the NPC agent module — Phase 7.1."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.agents.npc import (
    NPC_SYSTEM_PROMPT,
    NPCAgent,
    compress_text,
    decompress_hint,
    parse_npc_response,
)

# ===========================================================================
# Caveman Compression — compress_text
# ===========================================================================


class TestCompressArticles:
    """compress_text should remove articles (a, an, the)."""

    def test_removes_a(self) -> None:
        assert compress_text("a cat") == "cat"

    def test_removes_an(self) -> None:
        assert compress_text("an apple") == "apple"

    def test_removes_the(self) -> None:
        assert compress_text("the dog") == "dog"

    def test_removes_all_articles(self) -> None:
        assert compress_text("a cat the dog an apple") == "cat dog apple"

    def test_removes_the_middle(self) -> None:
        assert compress_text("I saw the cat") == "I saw cat"


class TestCompressFillers:
    """compress_text should remove filler words."""

    def test_removes_well(self) -> None:
        assert compress_text("Well it is fine") == "it is fine"

    def test_removes_so(self) -> None:
        assert compress_text("So anyway") == "anyway"

    def test_removes_basically(self) -> None:
        assert compress_text("Basically it works") == "it works"

    def test_removes_actually(self) -> None:
        assert compress_text("Actually no") == "no"

    def test_removes_just(self) -> None:
        assert compress_text("I just need rest") == "I need rest"

    def test_removes_very(self) -> None:
        assert compress_text("very big") == "big"

    def test_removes_really(self) -> None:
        assert compress_text("really good") == "good"

    def test_removes_multiple_fillers(self) -> None:
        result = compress_text("well basically just very big")
        assert result == "big"


class TestCompressHedging:
    """compress_text should remove hedging words and phrases."""

    def test_removes_perhaps(self) -> None:
        assert compress_text("perhaps it is") == "it is"

    def test_removes_maybe(self) -> None:
        assert compress_text("maybe later") == "later"

    def test_removes_sort_of(self) -> None:
        result = compress_text("It is sort of broken")
        assert "sort" not in result
        assert "of" not in result or "of" not in result.split()

    def test_removes_kind_of(self) -> None:
        result = compress_text("kind of strange")
        assert "kind" not in result
        assert "of" not in result or "of" not in result.split()

    def test_removes_i_think_phrase(self) -> None:
        result = compress_text("I think it works")
        assert "I think" not in result

    def test_removes_i_believe_phrase(self) -> None:
        result = compress_text("I believe you are right")
        assert "I believe" not in result

    def test_removes_it_seems_that(self) -> None:
        result = compress_text("It seems that you are lost")
        assert "It seems that" not in result


class TestCompressPleasantries:
    """compress_text should remove pleasantries at boundaries."""

    def test_removes_leading_please(self) -> None:
        assert compress_text("Please help me") == "help me"

    def test_removes_trailing_please(self) -> None:
        assert compress_text("Help me please") == "Help me"

    def test_removes_leading_thank_you(self) -> None:
        assert compress_text("Thank you goodbye") == "goodbye"

    def test_removes_trailing_thank_you(self) -> None:
        result = compress_text("Here you go thank you")
        assert "thank" not in result.lower()

    def test_removes_greetings(self) -> None:
        assert compress_text("Greetings traveller") == "traveller"


class TestCompressPreserveProperNouns:
    """compress_text should preserve proper nouns."""

    def test_preserves_capitalised_name(self) -> None:
        assert "Elara" in compress_text("Ask Elara for help")

    def test_preserves_multiple_names(self) -> None:
        result = compress_text("Thorn spoke to Elara")
        assert "Thorn" in result
        assert "Elara" in result

    def test_preserves_place_name(self) -> None:
        assert "Rivendell" in compress_text("Go to Rivendell")


class TestCompressPreserveNumbers:
    """compress_text should preserve numbers."""

    def test_preserves_single_digit(self) -> None:
        assert "5" in compress_text("There are 5 goblins")

    def test_preserves_multi_digit(self) -> None:
        assert "100" in compress_text("100 gold pieces")

    def test_preserves_combined_numbers(self) -> None:
        result = compress_text("Roll 3d6 for damage")
        assert "3d6" in result


class TestCompressLevels:
    """compress_text should respect the level parameter."""

    def test_full_keeps_prepositions(self) -> None:
        result = compress_text("I went to the shop", level="full")
        assert "to" in result.split()

    def test_ultra_removes_prepositions(self) -> None:
        result = compress_text("I went to the shop", level="ultra")
        assert "to" not in result.split()

    def test_ultra_removes_conjunctions(self) -> None:
        result = compress_text("cats and dogs", level="ultra")
        assert "and" not in result.split()

    def test_ultra_removes_helping_verbs(self) -> None:
        result = compress_text("I am going", level="ultra")
        assert "am" not in result.split()

    def test_full_keeps_helping_verbs(self) -> None:
        result = compress_text("I am going", level="full")
        assert "am" in result.split()

    def test_default_level_is_full(self) -> None:
        result = compress_text("I am going to the shop")
        assert "am" in result
        assert "to" in result


class TestCompressEdgeCases:
    """compress_text edge cases."""

    def test_empty_string(self) -> None:
        assert compress_text("") == ""

    def test_none_text(self) -> None:
        assert compress_text(None) == ""  # type: ignore[arg-type]

    def test_only_stop_words(self) -> None:
        result = compress_text("a the an well so just")
        assert result == ""

    def test_whitespace_only(self) -> None:
        assert compress_text("   ") == ""

    def test_no_stop_words(self) -> None:
        assert compress_text("Dragons fly") == "Dragons fly"

    def test_mixed_case_stop_words(self) -> None:
        result = compress_text("The cat AND the dog")
        assert result == "cat AND dog"


# ===========================================================================
# Caveman Compression — decompress_hint
# ===========================================================================


class TestDecompressHint:
    """decompress_hint should add minimal readability."""

    def test_adds_period(self) -> None:
        result = decompress_hint("hello")
        assert result == "Hello."

    def test_capitalises_first_letter(self) -> None:
        result = decompress_hint("hello world")
        assert result == "Hello world."

    def test_preserves_existing_punctuation(self) -> None:
        result = decompress_hint("hello!")
        assert result == "Hello!"

    def test_preserves_question_mark(self) -> None:
        assert decompress_hint("really?") == "Really?"

    def test_handles_empty_string(self) -> None:
        assert decompress_hint("") == ""

    def test_handles_none(self) -> None:
        assert decompress_hint(None) == ""  # type: ignore[arg-type]

    def test_already_capitalised(self) -> None:
        assert decompress_hint("Hello") == "Hello."

    def test_does_not_double_punctuate(self) -> None:
        assert decompress_hint("Yes.") == "Yes."

    def test_trims_whitespace(self) -> None:
        assert decompress_hint("  hello  ") == "Hello."


# ===========================================================================
# NPC Parser — parse_npc_response
# ===========================================================================


class TestParseNpcResponse:
    """Tests for parse_npc_response."""

    def test_parse_full_response(self) -> None:
        text = """
        <dialogue>
        "Hello traveller!"
        </dialogue>
        <action>
        The innkeeper wipes a mug with a rag.
        </action>
        <emotional_state>
        friendly
        </emotional_state>
        """
        result = parse_npc_response(text)
        assert result["dialogue"] == '"Hello traveller!"'
        assert result["action"] == "The innkeeper wipes a mug with a rag."
        assert result["emotional_state"] == "friendly"
        assert result["tool_request"] is None

    def test_parse_minimal_response(self) -> None:
        text = """
        <dialogue>Yes.</dialogue>
        <action>Nods.</action>
        <emotional_state>neutral</emotional_state>
        """
        result = parse_npc_response(text)
        assert result["dialogue"] == "Yes."
        assert result["action"] == "Nods."
        assert result["emotional_state"] == "neutral"

    def test_parse_missing_tags_returns_defaults(self) -> None:
        text = "Some plain text without any XML tags."
        result = parse_npc_response(text)
        assert result["dialogue"] == ""
        assert result["action"] == ""
        assert result["emotional_state"] == ""
        assert result["tool_request"] is None

    def test_parse_empty_text(self) -> None:
        result = parse_npc_response("")
        assert result["dialogue"] == ""
        assert result["action"] == ""
        assert result["emotional_state"] == ""
        assert result["tool_request"] is None

    def test_parse_with_tool_request(self) -> None:
        text = """
        <dialogue>I will test your strength.</dialogue>
        <action>Puts down his mug.</action>
        <emotional_state>determined</emotional_state>
        <tool_request name="dice" params='{"formula":"d20"}' />
        """
        result = parse_npc_response(text)
        assert result["dialogue"] == "I will test your strength."
        assert result["tool_request"] is not None
        assert result["tool_request"]["name"] == "dice"
        assert result["tool_request"]["params"] == {"formula": "d20"}

    def test_parse_multiple_tool_requests_returns_first(self) -> None:
        """parse_npc_response should return only the first tool_request."""
        text = """
        <dialogue>Let me try twice.</dialogue>
        <action>Rolls up sleeves.</action>
        <emotional_state>eager</emotional_state>
        <tool_request name="dice" params='{"formula":"d20"}' />
        <tool_request name="dice" params='{"formula":"2d6"}' />
        """
        result = parse_npc_response(text)
        assert result["tool_request"] is not None
        assert result["tool_request"]["name"] == "dice"
        assert result["tool_request"]["params"] == {"formula": "d20"}

    def test_parse_handles_none(self) -> None:
        result = parse_npc_response(None)  # type: ignore[arg-type]
        assert result["dialogue"] == ""
        assert result["tool_request"] is None

    def test_parse_returns_expected_keys(self) -> None:
        result = parse_npc_response("anything")
        assert set(result.keys()) == {
            "dialogue",
            "action",
            "emotional_state",
            "tool_request",
        }

    def test_parse_preserves_dialogue_formatting(self) -> None:
        """Dialogue should preserve its inner text exactly."""
        text = (
            "<dialogue>\nWhat do you need?\n</dialogue>\n"
            "<action>\nThe merchant leans forward.\n</action>\n"
            "<emotional_state>\ncurious\n</emotional_state>"
        )
        result = parse_npc_response(text)
        assert result["dialogue"] == "What do you need?"
        assert result["action"] == "The merchant leans forward."
        assert result["emotional_state"] == "curious"


# ===========================================================================
# NPC System Prompt
# ===========================================================================


class TestNpcSystemPrompt:
    """Tests for the NPC_SYSTEM_PROMPT constant."""

    def test_is_non_empty_string(self) -> None:
        assert isinstance(NPC_SYSTEM_PROMPT, str)
        assert len(NPC_SYSTEM_PROMPT) > 0

    def test_has_minimum_length(self) -> None:
        assert len(NPC_SYSTEM_PROMPT) >= 500

    def test_contains_role_section(self) -> None:
        assert "ROLE" in NPC_SYSTEM_PROMPT

    def test_contains_core_rules(self) -> None:
        assert "CORE RULES" in NPC_SYSTEM_PROMPT

    def test_contains_output_format(self) -> None:
        assert "OUTPUT FORMAT" in NPC_SYSTEM_PROMPT

    def test_contains_dialogue_tag(self) -> None:
        assert "dialogue" in NPC_SYSTEM_PROMPT

    def test_contains_action_tag(self) -> None:
        assert "action" in NPC_SYSTEM_PROMPT

    def test_contains_emotional_state(self) -> None:
        assert "emotional_state" in NPC_SYSTEM_PROMPT

    def test_contains_tool_request(self) -> None:
        assert "tool_request" in NPC_SYSTEM_PROMPT

    def test_contains_constraints_section(self) -> None:
        assert "CONSTRAINTS" in NPC_SYSTEM_PROMPT

    def test_does_not_mention_caveman(self) -> None:
        """Caveman compression is applied by the system, not the NPC."""
        assert "compress" not in NPC_SYSTEM_PROMPT.lower()

    def test_says_not_dungeon_master(self) -> None:
        assert "not the Dungeon Master" in NPC_SYSTEM_PROMPT


# ===========================================================================
# NPCAgent
# ===========================================================================


class TestNPCAgentInit:
    """Tests for NPCAgent instantiation."""

    def test_can_instantiate_with_none_provider(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test_npc",
            identity="Test NPC",
            personality="friendly",
            mood="curious",
            scene_summary="A dark tavern.",
            goal="Learn about the player.",
        )
        assert agent is not None
        assert agent.llm_provider is None
        assert agent.npc_id == "test_npc"
        assert agent.identity == "Test NPC"
        assert agent.personality == "friendly"
        assert agent.mood == "curious"
        assert agent.scene_summary == "A dark tavern."
        assert agent.goal == "Learn about the player."

    def test_stores_all_params(self) -> None:
        agent = NPCAgent(
            llm_provider="mock",
            npc_id="elara",
            identity="Elara the Keeper",
            personality="warm but shrewd",
            mood="suspicious",
            scene_summary="Evening in the tavern.",
            goal="Get information about the stranger.",
        )
        assert agent.npc_id == "elara"
        assert agent.identity == "Elara the Keeper"


class TestNPCAgentBuildContext:
    """Tests for NPCAgent._build_context."""

    def test_returns_list_of_dicts(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test",
            personality="friendly",
            mood="calm",
            scene_summary="A room.",
            goal="Help.",
        )
        context = agent._build_context("Hello")
        assert isinstance(context, list)
        assert len(context) > 0
        for msg in context:
            assert isinstance(msg, dict)
            assert "role" in msg
            assert "content" in msg

    def test_starts_with_system_message(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test",
            personality="friendly",
            mood="calm",
            scene_summary="A room.",
            goal="Help.",
        )
        context = agent._build_context("Hello")
        assert context[0]["role"] == "system"
        assert context[0]["content"] == NPC_SYSTEM_PROMPT

    def test_second_message_is_npc_context(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="elara",
            identity="Elara the Keeper",
            personality="warm",
            mood="curious",
            scene_summary="Tavern at night.",
            goal="Serve drinks.",
        )
        context = agent._build_context("What ale do you have?")
        assert context[1]["role"] == "system"
        assert "Elara the Keeper" in context[1]["content"]
        assert "warm" in context[1]["content"]
        assert "curious" in context[1]["content"]
        assert "Tavern at night." in context[1]["content"]
        assert "Serve drinks." in context[1]["content"]

    def test_ends_with_user_message(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test",
            personality="friendly",
            mood="calm",
            scene_summary="A room.",
            goal="Help.",
        )
        context = agent._build_context("I need a room.")
        assert context[-1]["role"] == "user"
        assert context[-1]["content"] == "I need a room."

    def test_has_three_messages(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test",
            personality="friendly",
            mood="calm",
            scene_summary="A room.",
            goal="Help.",
        )
        context = agent._build_context("Hello")
        assert len(context) == 3


class TestNPCAgentProcess:
    """Tests for NPCAgent.process."""

    def test_no_provider_returns_canned_response(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test NPC",
            personality="friendly",
            mood="neutral",
            scene_summary="A room.",
            goal="Help.",
        )
        result = agent.process("Hello")
        assert result["dialogue"] == "..."
        # Compressed: "The" is removed, "NPC waits for your response."
        assert "NPC" in result["action"]
        assert "waits" in result["action"]
        assert result["emotional_state"] == "neutral"
        assert result["tool_request"] is None

    def test_returns_expected_keys(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test NPC",
            personality="friendly",
            mood="neutral",
            scene_summary="A room.",
            goal="Help.",
        )
        result = agent.process("Hello")
        expected_keys = {
            "dialogue",
            "action",
            "emotional_state",
            "tool_request",
            "raw_response",
        }
        assert set(result.keys()) == expected_keys

    def test_handles_empty_input(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test NPC",
            personality="friendly",
            mood="neutral",
            scene_summary="A room.",
            goal="Help.",
        )
        result = agent.process("")
        assert result["dialogue"] == "..."
        assert result["tool_request"] is None

    def test_calls_llm_provider_when_set(self) -> None:
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": (
                "<dialogue>\nWelcome, stranger!\n</dialogue>\n"
                "<action>\nThe guard steps forward.\n</action>\n"
                "<emotional_state>\nwatchful\n</emotional_state>"
            ),
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 20,
                "total_tokens": 70,
            },
        }
        agent = NPCAgent(
            llm_provider=mock_provider,
            npc_id="guard",
            identity="Town guard",
            personality="stern",
            mood="watchful",
            scene_summary="Town gate at dusk.",
            goal="Check all arrivals.",
        )
        result = agent.process("I come in peace.")
        assert result["dialogue"] == "Welcome, stranger!"
        # Compressed: "The" removed by caveman compression
        assert "guard" in result["action"]
        assert "steps forward" in result["action"]
        assert result["emotional_state"] == "watchful"
        assert result["tool_request"] is None
        assert mock_provider.call.call_count >= 1

    def test_response_contains_required_fields(self) -> None:
        agent = NPCAgent(
            llm_provider=None,
            npc_id="test",
            identity="Test NPC",
            personality="friendly",
            mood="neutral",
            scene_summary="A room.",
            goal="Help.",
        )
        result = agent.process("Hello")
        assert isinstance(result["dialogue"], str)
        assert isinstance(result["action"], str)
        assert isinstance(result["emotional_state"], str)
        assert result["tool_request"] is None or isinstance(
            result["tool_request"], dict
        )

    def test_provider_failure_returns_canned(self) -> None:
        mock_provider = MagicMock()
        mock_provider.call.side_effect = RuntimeError("Provider offline")
        agent = NPCAgent(
            llm_provider=mock_provider,
            npc_id="test",
            identity="Test NPC",
            personality="friendly",
            mood="neutral",
            scene_summary="A room.",
            goal="Help.",
        )
        result = agent.process("Hello")
        assert result["dialogue"] == "..."

    def test_handles_tool_request_in_response(self) -> None:
        mock_provider = MagicMock()
        mock_provider.call.return_value = {
            "content": (
                "<dialogue>\nLet me roll for it.\n</dialogue>\n"
                "<action>\nThe dwarf pulls out dice.\n</action>\n"
                "<emotional_state>\nplayful\n</emotional_state>\n"
                '<tool_request name="dice" params=\'{"formula":"d20"}\' />'
            ),
            "finish_reason": "stop",
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 30,
                "total_tokens": 80,
            },
        }
        agent = NPCAgent(
            llm_provider=mock_provider,
            npc_id="dwarf",
            identity="Dwarf gambler",
            personality="boisterous",
            mood="playful",
            scene_summary="Gambling den.",
            goal="Win some coin.",
        )
        result = agent.process("I bet 10 gold.")
        assert result["tool_request"] is not None
        assert result["tool_request"]["name"] == "dice"
        assert result["tool_request"]["params"] == {"formula": "d20"}
