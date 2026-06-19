"""
Memory Summarizer — compresses RPG session history for long-term context.

Phase 8 module that takes recent gameplay turns and produces a concise
summary, preserving meaningful player decisions, NPC interactions, quest
progress, and world changes while discarding inconsequential flavour text.
Summaries are compressed using Caveman-style rules for agent-to-agent
communication (never player-facing).
"""

from __future__ import annotations

import logging
from typing import Any

from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SUMMARIZER_SYSTEM_PROMPT: str = (
    "You are a memory summarization agent for a dark fantasy RPG session. "
    "Your job is to distill recent gameplay turns into a concise, information-dense "
    "summary that preserves everything the Dungeon Master needs to maintain "
    "narrative continuity.\n\n"
    "You will receive the most recent player-and-DM exchanges in chronological order. "
    "Analyse them and produce a summary of 200-400 words that captures:\n\n"
    "- Meaningful player decisions and their consequences — what the player chose "
    "to do and what happened as a result.\n"
    "- Key NPC interactions and relationship shifts — who was met, what was said, "
    "and how attitudes changed.\n"
    "- Quests accepted, progressed, or completed — any tasks, promises, or "
    "mysteries the player engaged with.\n"
    "- Items gained, lost, or used — important equipment, keys, artifacts, or "
    "consumables that affect the player's capabilities.\n"
    "- Combat outcomes and significant events — battles fought, traps triggered, "
    "discoveries made, and their lasting effects.\n"
    "- World changes the player has caused — doors opened, factions influenced, "
    "locations altered, or persistent effects set in motion.\n\n"
    "You MUST discard the following as they do not contribute to long-term context:\n"
    "- Inconsequential flavour text and purely atmospheric description.\n"
    "- Repetitive dialogue or greetings that do not advance relationships.\n"
    "- Minor descriptions of scenery that have no mechanical or plot relevance.\n"
    "- Hedging, pleasantries, and filler from either the player or the DM.\n\n"
    "Write in an ultra-compressed style:\n"
    "- Drop articles (a, an, the), fillers (well, so, basically), and hedging.\n"
    "- Drop prepositions, conjunctions, and helping verbs where meaning remains "
    "clear without them.\n"
    "- Preserve proper nouns, numbers, item names, quest names, and mechanical "
    "details exactly as written.\n"
    '- Omit explanatory phrasing: no "The player decided to..." — just state '
    "what was decided.\n\n"
    "Output ONLY the summary text. Do not include labels, greetings, explanations, "
    "or any preamble. Do not wrap the summary in quotes or tags. The summary must "
    "stand alone as a single block of plain text."
)

# ---------------------------------------------------------------------------
# Story Writer System Prompt
# ---------------------------------------------------------------------------

META_SUMMARIZER_SYSTEM_PROMPT: str = """You are a meta-summarizer for a long-running RPG campaign. Your task is to condense multiple session summaries into a concise, high-level overview.

Focus on:
- Major plot developments and story arcs
- Character growth and relationship changes
- World-changing events and their consequences
- Open threads and unresolved mysteries
- Long-term goals and shifts in direction

Ignore minor details, individual combat exchanges, and routine actions.
Output 2-4 paragraphs covering the most important developments."""

# ---------------------------------------------------------------------------
# Story Writer System Prompt
# ---------------------------------------------------------------------------

STORY_WRITER_SYSTEM_PROMPT: str = (
    "You are a fantasy novelist chronicling the adventures of a hero. "
    "Your job is to transform raw gameplay narrative into a flowing, "
    "novel-like story entry.\n\n"
    "Guidelines:\n"
    "- Write 2-4 paragraphs of atmospheric, evocative prose\n"
    "- Focus on the hero's actions, decisions, and their consequences\n"
    "- Use a dark fantasy tone fitting a gritty RPG world\n"
    "- Keep it concise but vivid — this is a chapter summary, not a full chapter\n"
    "- Write in third person, past tense\n"
    "- Do NOT use bullet points or lists — write natural prose\n"
    "- Each entry should stand alone as a short passage in the hero's journal"
)

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def count_tokens(text: str) -> int:
    """Estimate the number of tokens in *text* using a rough heuristic.

    Uses word count as a simple approximation.  Each word is treated as
    roughly one token.  This is intentionally imprecise — it exists to
    provide a lightweight trigger threshold, not for billing or context
    window management.

    Parameters
    ----------
    text : str
        The text to estimate token count for.

    Returns
    -------
    int
        Estimated number of tokens (word count).
    """
    if not text or not isinstance(text, str):
        return 0
    return len(text.split())


# ---------------------------------------------------------------------------
# Summarization trigger
# ---------------------------------------------------------------------------


def should_summarize(
    recent_turns_count: int,
    estimated_context_tokens: int,
    max_turns: int = 5,
    max_context_tokens: int = 4096,
) -> bool:
    """Determine whether summarization should be triggered.

    Returns ``True`` if the number of recent turns exceeds *max_turns*
    OR if the estimated token count exceeds *max_context_tokens*.

    Parameters
    ----------
    recent_turns_count : int
        Number of recent turn exchanges currently in the rolling buffer.
    estimated_context_tokens : int
        Estimated token count of the current context (use
        :func:`count_tokens`).
    max_turns : int
        Maximum allowed recent turns before summarisation is triggered.
        Defaults to 5.
    max_context_tokens : int
        Maximum allowed context tokens before summarisation is triggered.
        Defaults to 4096.

    Returns
    -------
    bool
        ``True`` if summarization should run, ``False`` otherwise.
    """
    return (
        recent_turns_count > max_turns or estimated_context_tokens > max_context_tokens
    )


# ---------------------------------------------------------------------------
# Fallback truncation
# ---------------------------------------------------------------------------


def _truncation_fallback(text: str) -> str:
    """Return a truncated fallback when the LLM summarizer is unavailable.

    Takes the first 500 characters of *text* and appends a truncation
    notice.

    Parameters
    ----------
    text : str
        The original text to truncate.

    Returns
    -------
    str
        Truncated text with a notice suffix.
    """
    return text[:500] + "... [summary truncated]"


# ---------------------------------------------------------------------------
# Core summarization
# ---------------------------------------------------------------------------


def summarize_turns(
    turns_text: str,
    provider: LLMProvider | None,
    max_retries: int = 2,
) -> str:
    """Compress a block of recent game turns into a concise summary.

    Sends *turns_text* to the LLM summarizer, retries on failure up to
    *max_retries* times, and falls back to a simple truncation if the
    provider is unavailable or all retries fail.  Never raises an
    exception — always returns a string.

    Parameters
    ----------
    turns_text : str
        Raw concatenated recent turns (player input + DM narrative).
    provider : LLMProvider or None
        The LLM provider to use for summarization.  If ``None``, the
        fallback truncation is returned immediately.
    max_retries : int
        Maximum number of retry attempts on failure.  Defaults to 2.

    Returns
    -------
    str
        The compressed summary, or a truncated fallback if summarization
        could not be completed.
    """
    if not turns_text or not isinstance(turns_text, str):
        return ""

    if provider is None:
        return _truncation_fallback(turns_text)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
        {"role": "user", "content": turns_text},
    ]

    last_error: Exception | None = None

    for attempt in range(1 + max_retries):
        try:
            response: dict[str, Any] = provider.call(messages)
            content: str = response.get("content", "")
            if content:
                return content.strip()
            # Empty content counts as a failure — retry
            last_error = ValueError("LLM returned empty content")
            logger.warning(
                "Summarizer attempt %d/%d returned empty content",
                attempt + 1,
                1 + max_retries,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "Summarizer attempt %d/%d failed: %s",
                attempt + 1,
                1 + max_retries,
                e,
            )

    # All attempts exhausted — log and return fallback
    logger.warning(
        "Summarizer failed after %d attempts: %s",
        1 + max_retries,
        last_error,
    )
    return _truncation_fallback(turns_text)


# ---------------------------------------------------------------------------
# Story summarization
# ---------------------------------------------------------------------------


def summarize_story(
    turns_text: str,
    provider: LLMProvider | None,
    max_retries: int = 2,
) -> str:
    """Transform raw gameplay narrative into a novel-like story summary entry.

    Sends *turns_text* to the LLM with the story writer prompt, retries on
    failure up to *max_retries* times, and falls back to a simple truncation
    if the provider is unavailable or all retries fail.  Never raises an
    exception — always returns a string.

    Parameters
    ----------
    turns_text : str
        Raw concatenated recent turns (player input + DM narrative).
    provider : LLMProvider or None
        The LLM provider to use for story writing.  If ``None``, the
        fallback truncation is returned immediately.
    max_retries : int
        Maximum number of retry attempts on failure.  Defaults to 2.

    Returns
    -------
    str
        The novel-like summary, or a truncated fallback if story writing
        could not be completed.
    """
    if not turns_text or not isinstance(turns_text, str):
        return ""
    if provider is None:
        return _truncation_fallback(turns_text)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": STORY_WRITER_SYSTEM_PROMPT},
        {"role": "user", "content": turns_text},
    ]

    for attempt in range(max_retries):
        try:
            response = provider.call(messages)
            content = response.get("content", "").strip()
            if content:
                return content
            logger.warning(
                "Empty response from story summarizer (attempt %d/%d)",
                attempt + 1,
                max_retries,
            )
        except Exception:
            logger.exception(
                "Story summarizer failed (attempt %d/%d)",
                attempt + 1,
                max_retries,
            )

    return _truncation_fallback(turns_text)


# ---------------------------------------------------------------------------
# L3 Meta-Summarization
# ---------------------------------------------------------------------------


def summarize_meta(
    summaries_text: str,
    provider: Any,
    previous_meta: str | None = None,
    max_retries: int = 2,
) -> str:
    """Generate an L3 meta-summary from a collection of L2 summaries.

    Condenses multiple session summaries into a concise high-level overview
    of the campaign's major plot developments, character growth, and
    unresolved threads.

    Parameters
    ----------
    summaries_text : str
        Concatenated L2 summaries to condense.
    provider : LLMProvider
        LLM provider with ``.call(messages)`` method.
    previous_meta : str or None
        Optional previous L3 summary for continuity.
    max_retries : int
        Number of retries on failure.  Defaults to 2.

    Returns
    -------
    str
        Meta-summary text, or truncated fallback on complete failure.
    """
    if not summaries_text or not isinstance(summaries_text, str):
        return ""

    if provider is None:
        return _truncation_fallback(summaries_text)

    # If previous_meta is provided, prepend it for continuity
    if previous_meta:
        input_text = (
            f"Previous meta-summary:\n{previous_meta}"
            f"\n\nNew summaries to incorporate:\n{summaries_text}"
        )
    else:
        input_text = summaries_text

    messages: list[dict[str, str]] = [
        {"role": "system", "content": META_SUMMARIZER_SYSTEM_PROMPT},
        {"role": "user", "content": input_text},
    ]

    last_error: Exception | None = None

    for attempt in range(1 + max_retries):
        try:
            response: dict[str, Any] = provider.call(messages)
            content: str = response.get("content", "")
            if content:
                return content.strip()
            # Empty content counts as a failure — retry
            last_error = ValueError("LLM returned empty content")
            logger.warning(
                "Meta-summarizer attempt %d/%d returned empty content",
                attempt + 1,
                1 + max_retries,
            )
        except Exception as e:
            last_error = e
            logger.warning(
                "Meta-summarizer attempt %d/%d failed: %s",
                attempt + 1,
                1 + max_retries,
                e,
            )

    # All attempts exhausted — log and return fallback
    logger.warning(
        "Meta-summarizer failed after %d attempts: %s",
        1 + max_retries,
        last_error,
    )
    return _truncation_fallback(summaries_text)


# ---------------------------------------------------------------------------
# Caveman compression for summaries
# ---------------------------------------------------------------------------


def compress_summary(summary: str, level: str | None = None) -> str:
    """Apply ultra Caveman compression to a summary text.

    Reuses the Caveman compression from ``app.agents.npc.compress_text``
    at the ``"ultra"`` level — strips articles, fillers, prepositions,
    conjunctions, and helping verbs while preserving proper nouns,
    numbers, and mechanical details.

    If the import of ``compress_text`` fails (e.g. during refactoring),
    the summary is returned as-is.

    Parameters
    ----------
    summary : str
        The summary text to compress.
    level : str or None
        Optional fidelity level hint (e.g. ``"COMPRESSED"``,
        ``"PLACEHOLDER"``).  Currently unused but reserved for future use.

    Returns
    -------
    str
        Ultra-compressed summary, or the original if compression cannot
        be applied.
    """
    if not summary or not isinstance(summary, str):
        return ""

    try:
        from app.agents.npc import compress_text as _caveman_compress

        return _caveman_compress(summary, level="ultra")
    except ImportError:
        logger.warning("Could not import compress_text from app.agents.npc")
        return summary


__all__ = [
    "META_SUMMARIZER_SYSTEM_PROMPT",
    "SUMMARIZER_SYSTEM_PROMPT",
    "STORY_WRITER_SYSTEM_PROMPT",
    "summarize_meta",
    "summarize_turns",
    "summarize_story",
    "should_summarize",
    "count_tokens",
    "compress_summary",
]
