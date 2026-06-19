"""
Turn History Management — rolling buffer for DM conversation history.

Provides ``SessionHistory`` which maintains:
- ``recent_turns``: A deque of the last N (default 5) conversation
  exchanges (each exchange is a user-assistant pair).
- ``compressed_summary``: A text summary of older turns for context
  (placeholder for Phase 8 memory summarization).
"""

from __future__ import annotations

from collections import deque
from enum import IntEnum


class Fidelity(IntEnum):
    """Fidelity level for memory entries in the DM context window.

    FULL: Complete verbatim content (recent turns).
    COMPRESSED: Summarized content (L2/L3 summaries).
    PLACEHOLDER: Single-sentence reminder that content exists but was
                 forgotten (very old content beyond retention).
    """

    FULL = 0
    COMPRESSED = 1
    PLACEHOLDER = 2


class SessionHistory:
    """Manages the conversation history for the DM agent.

    Maintains a rolling buffer of recent turns and an optional compressed
    summary for long-term context preservation.

    Parameters
    ----------
    max_turns : int
        Maximum number of recent turn exchanges to retain verbatim.
        Older turns roll off the buffer automatically.  Defaults to 5.
    """

    MAX_RECENT_TURNS: int = 5
    L3_INTERVAL: int = 25

    # Fidelity thresholds — define how many entries at each level get
    # FULL / COMPRESSED fidelity before falling back to PLACEHOLDER.
    RECENT_TURN_FIDELITY_COUNT: int = 4  # Last 4 turns get FULL fidelity

    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns: int = max_turns
        self.recent_turns: deque[dict[str, str]] = deque(maxlen=max_turns)
        self.compressed_summary: str = ""
        self.l3_summaries: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_turn(self, player_input: str, dm_response: str) -> None:
        """Record a single turn exchange in the rolling buffer.

        Parameters
        ----------
        player_input : str
            What the player said or did this turn.
        dm_response : str
            The DM's narrative response (without XML tags).
        """
        self.recent_turns.append({"user": player_input, "assistant": dm_response})

    def get_turns_text(self) -> str:
        """Get all recent turns as a single text block for summarization.

        Returns a formatted string with each turn labeled as
        ``[Turn N]\\nPlayer: ...\\nDM: ...`` separated by blank lines.

        Returns
        -------
        str
            Formatted turns text, or empty string if no turns exist.
        """
        parts: list[str] = []
        for i, turn in enumerate(self.recent_turns, start=1):
            parts.append(f"[Turn {i}]\nPlayer: {turn['user']}\nDM: {turn['assistant']}")
        return "\n\n".join(parts)

    def get_context_messages(self) -> list[dict[str, str]]:
        """Return recent turns as message dicts for LLM context.

        Returns a flat list of ``{"role": "user"/"assistant",
        "content": "..."}`` dicts suitable for appending to an LLM
        message list.

        Returns
        -------
        list[dict[str, str]]
            Message dicts for each turn in chronological order.
        """
        messages: list[dict[str, str]] = []
        for turn in self.recent_turns:
            messages.append({"role": "user", "content": turn["user"]})
            messages.append({"role": "assistant", "content": turn["assistant"]})
        return messages

    def get_summary(self) -> str:
        """Return the compressed summary of past gameplay turns.

        Populated by the memory summarizer when recent turns are
        compressed.  Returns an empty string if no summary exists yet.
        """
        return self.compressed_summary

    def set_summary(self, summary: str) -> None:
        """Set the compressed summary text.

        Parameters
        ----------
        summary : str
            The new compressed summary string.  Pass an empty string to
            clear the summary without affecting the turns buffer.
        """
        self.compressed_summary = summary

    def add_l3_summary(self, summary: str) -> None:
        """Append an L3 meta-summary.

        Parameters
        ----------
        summary : str
            The L3 meta-summary text to append.
        """
        self.l3_summaries.append(summary)

    def get_l3_summaries(self) -> list[str]:
        """Return all L3 meta-summaries.

        Returns
        -------
        list[str]
            A copy of the accumulated L3 meta-summaries.
        """
        return self.l3_summaries.copy()

    # ------------------------------------------------------------------
    # Fidelity-aware accessors (dynamic — never stored on disk)
    # ------------------------------------------------------------------

    def get_turns_with_fidelity(self) -> list[tuple[dict[str, str], Fidelity]]:
        """Return recent turns with computed fidelity levels.

        The most recent ``RECENT_TURN_FIDELITY_COUNT`` turns are FULL.
        Older turns in the buffer are PLACEHOLDER (will be condensed).

        Returns
        -------
        list[tuple[dict[str, str], Fidelity]]
            List of (turn_dict, fidelity) pairs in chronological order.
        """
        turns: list[tuple[dict[str, str], Fidelity]] = []
        threshold = len(self.recent_turns) - self.RECENT_TURN_FIDELITY_COUNT
        for i, turn in enumerate(self.recent_turns):
            if i >= threshold:
                turns.append((turn, Fidelity.FULL))
            else:
                turns.append((turn, Fidelity.PLACEHOLDER))
        return turns

    def get_summary_with_fidelity(self) -> tuple[str, Fidelity] | None:
        """Return the compressed summary with COMPRESSED fidelity.

        Returns
        -------
        tuple[str, Fidelity] or None
            (summary_text, Fidelity.COMPRESSED) if summary exists, else None.
        """
        if self.compressed_summary:
            return (self.compressed_summary, Fidelity.COMPRESSED)
        return None

    def get_l3_summaries_with_fidelity(self) -> list[tuple[str, Fidelity]]:
        """Return L3 meta-summaries with computed fidelity levels.

        The most recent L3 is COMPRESSED.
        Older L3 summaries are PLACEHOLDER.

        Returns
        -------
        list[tuple[str, Fidelity]]
            List of (summary_text, fidelity) pairs, oldest first.
        """
        if not self.l3_summaries:
            return []
        # All but the last are PLACEHOLDER; the last (most recent) is COMPRESSED
        result: list[tuple[str, Fidelity]] = []
        for i, summary in enumerate(self.l3_summaries):
            if i == len(self.l3_summaries) - 1:
                result.append((summary, Fidelity.COMPRESSED))
            else:
                result.append((summary, Fidelity.PLACEHOLDER))
        return result

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize history for persistence with world state.

        Returns
        -------
        dict
            A JSON-serializable dict with keys ``max_turns``,
            ``recent_turns``, and ``compressed_summary``.
        """
        return {
            "max_turns": self.max_turns,
            "recent_turns": list(self.recent_turns),
            "compressed_summary": self.compressed_summary,
            "l3_summaries": self.l3_summaries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SessionHistory:
        """Deserialize history from saved data.

        Parameters
        ----------
        data : dict
            A dict previously produced by ``to_dict()``.

        Returns
        -------
        SessionHistory
            A new instance populated with the saved state.
        """
        max_turns = data.get("max_turns", cls.MAX_RECENT_TURNS)
        instance = cls(max_turns=max_turns)
        instance.compressed_summary = data.get("compressed_summary", "")
        instance.l3_summaries = data.get("l3_summaries", [])
        for turn in data.get("recent_turns", []):
            instance.recent_turns.append(turn)
        return instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all history — drops recent turns and summary."""
        self.recent_turns.clear()
        self.compressed_summary = ""
        self.l3_summaries.clear()

    def clear_turns(self) -> None:
        """Clear all recent turns from the buffer.

        Unlike :meth:`clear`, this only removes the verbatim turn
        history, leaving the compressed summary intact.
        """
        self.recent_turns.clear()
