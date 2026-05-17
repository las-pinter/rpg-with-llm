"""Tests for the memory summarizer module — Phase 8."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agents.summarizer import (
    SUMMARIZER_SYSTEM_PROMPT,
    compress_summary,
    count_tokens,
    should_summarize,
    summarize_turns,
)

# ===========================================================================
# SUMMARIZER_SYSTEM_PROMPT
# ===========================================================================


class TestSummarizerPrompt:
    """Tests for the ``SUMMARIZER_SYSTEM_PROMPT`` constant."""

    def test_is_non_empty_string(self) -> None:
        """SUMMARIZER_SYSTEM_PROMPT should be a non-empty string."""
        assert isinstance(SUMMARIZER_SYSTEM_PROMPT, str)
        assert len(SUMMARIZER_SYSTEM_PROMPT) > 0

    def test_mentions_summary_requirements(self) -> None:
        """Should mention decisions, NPC, and quests as key concepts."""
        prompt = SUMMARIZER_SYSTEM_PROMPT.lower()
        keywords = ("decisions", "npc", "quests")
        for kw in keywords:
            assert kw in prompt, f"Expected '{kw}' to appear in the summarizer prompt"

    def test_mentions_ultra_compressed_style(self) -> None:
        """Should mention ultra-compressed or compression style."""
        prompt = SUMMARIZER_SYSTEM_PROMPT.lower()
        has_compress_keyword = (
            "ultra-compressed" in prompt
            or "compressed" in prompt
            or "compress" in prompt
        )
        assert has_compress_keyword, "Expected the prompt to mention compression style"

    def test_mentions_output_format(self) -> None:
        """Should instruct to output only the summary text."""
        assert "Output ONLY" in SUMMARIZER_SYSTEM_PROMPT, (
            "Expected 'Output ONLY' instruction in the prompt"
        )


# ===========================================================================
# count_tokens
# ===========================================================================


class TestCountTokens:
    """Tests for ``count_tokens``."""

    def test_returns_zero_for_empty_string(self) -> None:
        """Empty string should yield zero tokens."""
        assert count_tokens("") == 0

    def test_returns_zero_for_non_string_input(self) -> None:
        """Non-string input (None) should yield zero tokens."""
        assert count_tokens(None) == 0  # type: ignore[arg-type]

    def test_returns_word_count_for_normal_text(self) -> None:
        """A simple sentence should return the correct word count."""
        assert count_tokens("hello world") == 2

    def test_counts_multiple_words_correctly(self) -> None:
        """Longer text should reflect the accurate word count."""
        text = "The quick brown fox jumps over the lazy dog"
        assert count_tokens(text) == 9

    def test_counts_single_word(self) -> None:
        """A single word should return 1."""
        assert count_tokens("hello") == 1

    def test_handles_whitespace_only(self) -> None:
        """Whitespace-only text should return zero."""
        assert count_tokens("   ") == 0

    def test_handles_text_with_multiple_spaces(self) -> None:
        """Extra whitespace between words should not inflate count."""
        assert count_tokens("hello    world") == 2


# ===========================================================================
# should_summarize
# ===========================================================================


class TestShouldSummarize:
    """Tests for ``should_summarize``."""

    def test_returns_false_when_below_thresholds(self) -> None:
        """Both counts below thresholds should return False."""
        assert should_summarize(3, 2000) is False

    def test_returns_true_when_turns_exceed_max(self) -> None:
        """Turns exceeding max_turns should trigger summarization."""
        assert should_summarize(6, 2000) is True

    def test_returns_true_when_tokens_exceed_max(self) -> None:
        """Tokens exceeding max_context_tokens should trigger."""
        assert should_summarize(3, 5000) is True

    def test_returns_true_when_both_exceed_max(self) -> None:
        """Both exceeding thresholds should still return True."""
        assert should_summarize(10, 10000) is True

    def test_uses_default_thresholds(self) -> None:
        """Default thresholds should be max_turns=5, max_context_tokens=4096.

        Exactly equal to thresholds returns False (checks > not >=).
        """
        assert should_summarize(5, 4096) is False
        # Exceeding either individually should return True
        assert should_summarize(6, 4096) is True
        assert should_summarize(5, 4097) is True

    def test_custom_thresholds(self) -> None:
        """Custom thresholds should override defaults."""
        assert should_summarize(9, 500, max_turns=10, max_context_tokens=800) is False
        assert should_summarize(11, 500, max_turns=10, max_context_tokens=800) is True
        assert should_summarize(9, 900, max_turns=10, max_context_tokens=800) is True

    def test_zero_turns_does_not_trigger(self) -> None:
        """Zero recent turns with below-threshold tokens should not trigger."""
        assert should_summarize(0, 100) is False

    def test_zero_max_turns_triggers_immediately(self) -> None:
        """When max_turns is 0, any turn count > 0 triggers."""
        assert should_summarize(1, 100, max_turns=0) is True
        assert should_summarize(0, 100, max_turns=0) is False

    def test_boundary_at_max_turns(self) -> None:
        """Exactly max_turns should NOT trigger (uses > not >=)."""
        for n in range(0, 6):
            expected = n > 5
            assert should_summarize(n, 1000) is expected, (
                f"should_summarize({n}, 1000) should be {expected}"
            )

    def test_boundary_at_max_context_tokens(self) -> None:
        """Exactly max_context_tokens should NOT trigger (uses > not >=)."""
        assert should_summarize(1, 4096) is False
        assert should_summarize(1, 4097) is True


# ===========================================================================
# summarize_turns
# ===========================================================================


class TestSummarizeTurns:
    """Tests for ``summarize_turns``."""

    def test_returns_empty_string_for_empty_input(self) -> None:
        """Empty input should return an empty string."""
        assert summarize_turns("", provider=None) == ""

    def test_returns_truncation_fallback_when_provider_is_none(self) -> None:
        """When provider is None, should return the truncation fallback."""
        text = "Player did something interesting in the game today."
        result = summarize_turns(text, provider=None)
        assert "... [summary truncated]" in result
        assert text in result  # short text is fully preserved

    def test_truncation_fallback_truncates_long_text(self) -> None:
        """Text exceeding 500 chars should be truncated with a notice."""
        text = "Long gameplay text. " * 60  # well over 500 chars
        result = summarize_turns(text, provider=None)
        # First 500 chars should be preserved
        assert result.startswith(text[:500])
        # Truncation notice should be appended
        assert "... [summary truncated]" in result
        # Total length should be 500 + notice
        expected_len = 500 + len("... [summary truncated]")
        assert len(result) == expected_len

    def test_calls_provider_with_correct_messages(self) -> None:
        """Provider should receive system prompt and user text."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {"content": "summary"}
        user_text = "Player explored the dark forest."
        summarize_turns(user_text, provider=mock_provider)
        mock_provider.call.assert_called_once()
        (messages,) = mock_provider.call.call_args[0]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == SUMMARIZER_SYSTEM_PROMPT
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == user_text

    def test_returns_provider_content_stripped(self) -> None:
        """Provider content should be stripped of leading/trailing whitespace."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {"content": "  summary with spaces  "}
        result = summarize_turns("Some text", provider=mock_provider)
        assert result == "summary with spaces"

    def test_exhausts_retries_on_failure(self) -> None:
        """All retry attempts exhausted should fall back to truncation."""
        mock_provider = MagicMock()
        mock_provider.call.side_effect = RuntimeError("LLM failed")
        text = "Important gameplay text that needs summarizing."
        result = summarize_turns(text, provider=mock_provider, max_retries=2)
        # 1 initial + 2 retries = 3 total attempts
        assert mock_provider.call.call_count == 3
        assert "truncated" in result

    def test_retries_on_empty_content(self) -> None:
        """Empty content from provider should trigger retries."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {"content": ""}
        text = "Some gameplay text."
        result = summarize_turns(text, provider=mock_provider, max_retries=1)
        assert mock_provider.call.call_count == 2
        assert "truncated" in result

    def test_retries_then_succeeds(self) -> None:
        """Provider that fails once then succeeds should return summary."""
        mock_provider = MagicMock()
        mock_provider.call.side_effect = [
            RuntimeError("First attempt failed"),
            {"content": "Success summary here"},
        ]
        result = summarize_turns("Some text", provider=mock_provider, max_retries=2)
        assert mock_provider.call.call_count == 2
        assert result == "Success summary here"

    def test_handles_empty_response_content(self) -> None:
        """Response dict without 'content' key should trigger retries."""
        mock_provider = MagicMock()
        # Return a dict that exists but has no 'content' key
        mock_provider.call.return_value = {"finish_reason": "stop"}
        text = "Some text."
        result = summarize_turns(text, provider=mock_provider, max_retries=1)
        assert mock_provider.call.call_count == 2
        assert "truncated" in result

    def test_succeeds_on_first_attempt(self) -> None:
        """Successful provider call on first attempt returns content."""
        mock_provider = MagicMock()
        mock_provider.call.return_value = {"content": "Successful summary"}
        result = summarize_turns("Some text", provider=mock_provider)
        assert result == "Successful summary"
        mock_provider.call.assert_called_once()

    def test_default_max_retries(self) -> None:
        """Default max_retries should be 2 (3 total attempts)."""
        mock_provider = MagicMock()
        mock_provider.call.side_effect = RuntimeError("fail")
        text = "Text for retry count test."
        summarize_turns(text, provider=mock_provider)
        assert mock_provider.call.call_count == 3

    def test_empty_provider_response_no_content_key(self) -> None:
        """When provider returns {} the .get('content', '') yields empty."""
        # This should also trigger retries because content is falsy
        mock_provider = MagicMock()
        mock_provider.call.return_value = {}
        text = "Summarize this."
        result = summarize_turns(text, provider=mock_provider, max_retries=0)
        # Only 1 attempt with max_retries=0
        assert mock_provider.call.call_count == 1
        assert "truncated" in result


# ===========================================================================
# compress_summary
# ===========================================================================


class TestCompressSummary:
    """Tests for ``compress_summary``."""

    def test_returns_empty_string_for_empty_input(self) -> None:
        """Empty input should return an empty string."""
        assert compress_summary("") == ""

    def test_returns_empty_string_for_whitespace(self) -> None:
        """Whitespace-only input should return empty string.

        The inner compress_text function handles whitespace.
        """
        result = compress_summary("   ")
        assert result == ""

    def test_imports_and_calls_compress_text(self) -> None:
        """Should call compress_text from NPC module with level='ultra'."""
        with patch("app.agents.npc.compress_text") as mock_compress:
            mock_compress.return_value = "ultra compressed summary"
            result = compress_summary("some summary text")
            mock_compress.assert_called_once_with("some summary text", level="ultra")
            assert result == "ultra compressed summary"

    def test_returns_original_on_import_error(self) -> None:
        """When compress_text raises ImportError, original is returned.

        The try/except in compress_summary catches ImportError from both
        the import statement and the function call, so a mock that raises
        ImportError exercises the fallback path.
        """
        with patch("app.agents.npc.compress_text") as mock_compress:
            mock_compress.side_effect = ImportError("test")
            original = "Summary that would be compressed"
            result = compress_summary(original)
            assert result == original

    def test_preserves_summary_through_compression_cycle(self) -> None:
        """Normal compression should work end-to-end via real import."""
        # This is a light integration test — it relies on the real
        # compress_text being importable.
        original = "The hero entered the dark forest and found a key."
        result = compress_summary(original)
        # Compression should remove articles
        assert "The" not in result
        # Key information preserved
        assert "hero" in result
        assert "forest" in result
        assert "key" in result


# ===========================================================================
# _truncation_fallback (tested via summarize_turns behavior)
# ===========================================================================


class TestTruncationFallback:
    """Tests for ``_truncation_fallback`` exercised through
    ``summarize_turns``."""

    def test_provider_none_uses_fallback(self) -> None:
        """provider=None triggers the truncation fallback path."""
        text = "Short text."
        result = summarize_turns(text, provider=None)
        assert "... [summary truncated]" in result

    def test_fallback_preserves_first_500_chars(self) -> None:
        """The first 500 characters of the original text are preserved."""
        text = "A" * 1000
        result = summarize_turns(text, provider=None)
        assert result.startswith("A" * 500)
        assert len(result) == 500 + len("... [summary truncated]")

    def test_fallback_on_short_text(self) -> None:
        """Text shorter than 500 chars is fully preserved (plus suffix)."""
        text = "Brief gameplay moment."
        result = summarize_turns(text, provider=None)
        assert text in result
        assert result.endswith("... [summary truncated]")

    def test_fallback_empty_input_still_empty(self) -> None:
        """Empty input bypasses fallback entirely, returning empty string."""
        result = summarize_turns("", provider=None)
        assert result == ""
