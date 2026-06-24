"""Tests for ConsultationAgent — pure Q&A without touching game state."""

from __future__ import annotations

from collections.abc import Generator

from app.agents.consultation import ConsultationAgent, build_consultation_context
from app.llm.base import HealthResult, LLMProvider, ModelInfo

# ===================================================================
# Mock providers
# ===================================================================


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns a canned response and records messages."""

    def __init__(self, response: str = "Test answer.") -> None:
        super().__init__()
        self.response = response
        self.last_messages: list[dict] | None = None

    def call(self, messages: list[dict]) -> dict:
        self.last_messages = messages
        return {
            "content": self.response,
            "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Stub — not used in consultation tests."""
        yield self.response
        _ = messages  # unused

    def list_models(self) -> list[ModelInfo]:
        """Stub — not used in consultation tests."""
        return []

    def health(self) -> HealthResult:
        """Stub — not used in consultation tests."""
        return HealthResult(ok=True, latency_ms=0.0, model="mock")


class MockFailingProvider(LLMProvider):
    """Mock provider whose ``call()`` always raises."""

    def call(self, messages: list[dict]) -> dict:
        raise RuntimeError("Provider failed")

    def stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Stub — not used."""
        raise RuntimeError("stream not implemented")

    def list_models(self) -> list[ModelInfo]:
        """Stub — not used."""
        return []

    def health(self) -> HealthResult:
        """Stub — not used."""
        return HealthResult(ok=True, latency_ms=0.0, model="mock")


# ===================================================================
# ConsultationAgent tests
# ===================================================================


class TestConsultationAgent:
    """Tests for ConsultationAgent.consult()."""

    def test_consult_returns_answer(self) -> None:
        """Happy path: valid question returns a non-empty answer."""
        agent = ConsultationAgent(llm_provider=MockLLMProvider("The answer is 42."))
        answer = agent.consult(
            question="What is the meaning of life?",
            world_state_snapshot={"location": "The World"},
            character_snapshot={"name": "Test", "class": "Fighter"},
        )
        assert answer == "The answer is 42."
        assert len(answer) > 0

    def test_consult_empty_question(self) -> None:
        """Empty question returns a prompt to ask something."""
        agent = ConsultationAgent(llm_provider=MockLLMProvider())
        answer = agent.consult(
            question="",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert answer == "Please ask a question."

    def test_consult_whitespace_question(self) -> None:
        """Whitespace-only question returns a prompt to ask something."""
        agent = ConsultationAgent(llm_provider=MockLLMProvider())
        answer = agent.consult(
            question="   ",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert answer == "Please ask a question."

    def test_consult_none_provider(self) -> None:
        """None provider returns unavailable message."""
        agent = ConsultationAgent(llm_provider=None)
        answer = agent.consult(
            question="Any question?",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert answer == "The DM is unavailable for consultation right now."

    def test_consult_strips_xml_tags(self) -> None:
        """XML tags in the response are stripped."""
        agent = ConsultationAgent(
            llm_provider=MockLLMProvider(
                "<narrative>The answer is <em>yes</em>.</narrative>"
            )
        )
        answer = agent.consult(
            question="Is this working?",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert "<narrative>" not in answer
        assert "</narrative>" not in answer
        assert "<em>" not in answer
        assert "The answer is yes." in answer

    def test_consult_strips_complex_xml(self) -> None:
        """Complex nested XML tags with attributes are stripped."""
        agent = ConsultationAgent(
            llm_provider=MockLLMProvider(
                '<response type="narrative">'
                "<paragraph>The forest is <b>dark</b>.</paragraph></response>"
            )
        )
        answer = agent.consult(
            question="What's in the forest?",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert "<response" not in answer
        assert "<paragraph>" not in answer
        assert "<b>" not in answer
        assert "The forest is dark." in answer

    def test_consult_handles_provider_exception(self) -> None:
        """Provider exception returns a friendly error message."""
        agent = ConsultationAgent(llm_provider=MockFailingProvider())
        answer = agent.consult(
            question="Will this crash?",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert "momentarily distracted" in answer

    def test_consult_no_state_changes(self) -> None:
        """Consultation does not modify any state (read-only)."""
        provider = MockLLMProvider("Some answer.")
        world_state = {"location": "Dungeon", "turn_count": 5}
        character_state = {"name": "Hero", "hp": 50}

        agent = ConsultationAgent(llm_provider=provider)
        agent.consult(
            question="What's here?",
            world_state_snapshot=world_state,
            character_snapshot=character_state,
        )

        # Verify no state mutation
        assert world_state == {"location": "Dungeon", "turn_count": 5}
        assert character_state == {"name": "Hero", "hp": 50}

    def test_consult_with_character_name(self) -> None:
        """Character name is included in context."""
        provider = MockLLMProvider("Answer for Hero.")
        agent = ConsultationAgent(llm_provider=provider, character_name="Hero")
        agent.consult(
            question="Tell me about myself.",
            world_state_snapshot={},
            character_snapshot={},
        )
        # Check that character_name appeared in the messages
        assert provider.last_messages is not None
        context = provider.last_messages
        assert any("Hero" in str(m.get("content", "")) for m in context)

    def test_consult_with_recent_consultations(self) -> None:
        """Recent consultations are included in context."""
        provider = MockLLMProvider("Continuing from before.")
        agent = ConsultationAgent(llm_provider=provider)
        agent.consult(
            question="And then?",
            world_state_snapshot={},
            character_snapshot={},
            recent_consultations=[
                {"question": "First?", "answer": "Start here."},
                {"question": "Next?", "answer": "Then here."},
            ],
        )
        assert provider.last_messages is not None
        context_text = " ".join(
            str(m.get("content", "")) for m in provider.last_messages
        )
        assert "First?" in context_text
        assert "Start here." in context_text
        assert "Next?" in context_text
        assert "Then here." in context_text

    def test_consult_returns_plain_text(self) -> None:
        """Answer is plain text without XML tags."""
        provider = MockLLMProvider("<tool>roll_dice</tool> Just a normal answer.")
        agent = ConsultationAgent(llm_provider=provider)
        answer = agent.consult(
            question="Test?",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert "<tool>" not in answer
        assert "Just a normal answer." in answer

    def test_consult_strips_self_closing_tags(self) -> None:
        """Self-closing XML tags like <br/> are stripped."""
        agent = ConsultationAgent(
            llm_provider=MockLLMProvider("Line one.<br/>Line two.")
        )
        answer = agent.consult(
            question="Format test?",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert "<br/>" not in answer
        assert "Line one." in answer
        assert "Line two." in answer


# ===================================================================
# build_consultation_context tests (standalone pure function)
# ===================================================================


class TestBuildConsultationContext:
    """Tests for the standalone build_consultation_context function."""

    def test_returns_message_list(self) -> None:
        """Returns a list of messages with system + world + character + question."""
        messages = build_consultation_context(
            question="Test?",
            world_state_snapshot={"location": "Cave"},
            character_snapshot={"name": "Grom"},
            character_name="Grom",
        )
        assert isinstance(messages, list)
        # system + world + character + question
        assert len(messages) >= 3
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Test?"

    def test_includes_character_name(self) -> None:
        """Character name appears in context when provided."""
        messages = build_consultation_context(
            question="Who am I?",
            world_state_snapshot={},
            character_snapshot={},
            character_name="Grom",
        )
        context = " ".join(m.get("content", "") for m in messages)
        assert "Grom" in context

    def test_system_prompt_present(self) -> None:
        """First message is the system prompt."""
        messages = build_consultation_context(
            question="Hi",
            world_state_snapshot={},
            character_snapshot={},
        )
        assert messages[0]["role"] == "system"
        assert "consultation mode" in messages[0]["content"]

    def test_world_state_included(self) -> None:
        """World state snapshot appears in context."""
        messages = build_consultation_context(
            question="Where am I?",
            world_state_snapshot={"location": "Dark Forest", "time": "night"},
            character_snapshot={},
        )
        context = " ".join(m.get("content", "") for m in messages)
        assert "Dark Forest" in context
        assert "night" in context

    def test_character_snapshot_included(self) -> None:
        """Character snapshot appears in context."""
        messages = build_consultation_context(
            question="My stats?",
            world_state_snapshot={},
            character_snapshot={"class": "Rogue", "level": 3},
        )
        context = " ".join(m.get("content", "") for m in messages)
        assert "Rogue" in context
        assert "level" in context

    def test_empty_world_state_no_world_message(self) -> None:
        """Empty world state dict does not add a world-state message."""
        messages = build_consultation_context(
            question="Test",
            world_state_snapshot={},
            character_snapshot={"name": "Hero"},
        )
        world_msgs = [m for m in messages if "World State" in m.get("content", "")]
        assert len(world_msgs) == 0

    def test_empty_character_and_name_no_character_message(self) -> None:
        """Both empty character snapshot and name means no character message."""
        messages = build_consultation_context(
            question="Test",
            world_state_snapshot={},
            character_snapshot={},
        )
        char_msgs = [
            m for m in messages if "Character Information" in m.get("content", "")
        ]
        assert len(char_msgs) == 0

    def test_recent_consultations_included(self) -> None:
        """Recent consultations appear in context."""
        messages = build_consultation_context(
            question="Continuing?",
            world_state_snapshot={},
            character_snapshot={},
            recent_consultations=[
                {"question": "Q1", "answer": "A1"},
                {"question": "Q2", "answer": "A2"},
            ],
        )
        context = " ".join(m.get("content", "") for m in messages)
        assert "Q1" in context
        assert "A1" in context
        assert "Q2" in context
        assert "A2" in context

    def test_only_last_five_recent_consultations(self) -> None:
        """Only the last 5 recent consultations are included."""
        many = [{"question": f"Q{i}", "answer": f"A{i}"} for i in range(10)]
        messages = build_consultation_context(
            question="History?",
            world_state_snapshot={},
            character_snapshot={},
            recent_consultations=many,
        )
        context = " ".join(m.get("content", "") for m in messages)
        # Q0 and Q1 should be cut off (only last 5 of 10)
        assert "Q0" not in context
        assert "Q5" in context
        assert "Q9" in context

    def test_no_recent_consultations_omitted(self) -> None:
        """None recent_consultations does not add a consultations message."""
        messages = build_consultation_context(
            question="Test",
            world_state_snapshot={},
            character_snapshot={},
        )
        consult_msgs = [
            m for m in messages if "Previous consultations" in m.get("content", "")
        ]
        assert len(consult_msgs) == 0
