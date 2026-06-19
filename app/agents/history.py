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

    # Forgetting mechanism thresholds
    FORGET_THRESHOLD: int = 20  # Start forgetting when L2 count exceeds this
    FORGET_PROTECTED_COUNT: int = 5  # Never forget the last N L2 summaries
    FORGET_MAX_RATIO: float = 0.5  # Forget at most 50% of entries above threshold

    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns: int = max_turns
        self.recent_turns: deque[dict[str, str]] = deque(maxlen=max_turns)
        self.compressed_summary: str = ""
        self.l3_summaries: list[str] = []
        self.forgotten_l2_indices: set[int] = set()  # Indices of forgotten L2 summaries

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
    # Forgetting mechanism
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_novelty_score(summary: str) -> float:
        """Score a summary by its unique entity mentions.

        Counts capitalized words (proper nouns) that aren't at the start
        of a sentence as a rough proxy for novelty/density of information.
        Normalizes by average across all summaries.
        """
        # Count capitalized words not at the start of sentences
        sentences = summary.replace("!", ".").replace("?", ".").split(".")
        entity_count = 0
        for sentence in sentences:
            words = sentence.strip().split()
            for word in words[1:]:  # Skip first word (start of sentence)
                if word and word[0].isupper():
                    entity_count += 1
        return float(entity_count)

    def forget(self, technical_summaries: list[str]) -> list[int]:
        """Run forgetting mechanism on the L2 summary list.

        When the number of summaries exceeds FORGET_THRESHOLD, score eligible
        entries (those not in the protected last N) by recency + novelty.
        The lowest-scoring entries are marked as forgotten (up to
        FORGET_MAX_RATIO of the excess).

        Args:
            technical_summaries: Full list of L2 summaries (oldest first).

        Returns:
            List of newly forgotten indices for logging/debugging.
        """
        total = len(technical_summaries)
        if total <= self.FORGET_THRESHOLD:
            return []

        # Identify eligible entries (not in protected newest ones)
        excess = total - self.FORGET_THRESHOLD
        max_to_forget = int(excess * self.FORGET_MAX_RATIO)  # At most 50% of excess
        eligible_indices = list(range(total - self.FORGET_PROTECTED_COUNT))

        if not eligible_indices:
            return []

        # Score eligible entries
        scored: list[tuple[float, int]] = []  # (score, index)
        for i in eligible_indices:
            summary = technical_summaries[i]
            # Recency: i / total — older (lower i) = lower score, more forgettable
            recency = i / total
            # Novelty: entities / average entities
            novelty = self._compute_novelty_score(summary)
            avg_novelty = sum(
                self._compute_novelty_score(technical_summaries[j])
                for j in eligible_indices
            ) / max(len(eligible_indices), 1)
            novelty_norm = min(novelty / max(avg_novelty, 0.01), 2.0)
            # Combined score
            score = 0.7 * recency + 0.3 * novelty_norm
            scored.append((score, i))

        # Sort by score ascending (worst first)
        scored.sort(key=lambda x: x[0])

        # Forget the lowest-scoring entries
        newly_forgotten = []
        for score, idx in scored[:max_to_forget]:
            if idx not in self.forgotten_l2_indices:
                self.forgotten_l2_indices.add(idx)
                newly_forgotten.append(idx)

        return newly_forgotten

    def get_forgotten_count(self) -> int:
        """Return the number of currently forgotten L2 entries."""
        return len(self.forgotten_l2_indices)

    def get_forgotten_indices(self) -> set[int]:
        """Return a copy of the forgotten indices set."""
        return self.forgotten_l2_indices.copy()

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

    @staticmethod
    def get_l2_summaries_with_fidelity(
        technical_summaries: list[str],
        recent_count: int = 4,
        forgotten_indices: set[int] | None = None,
    ) -> list[tuple[str, Fidelity]]:
        """Return L2 summaries with fidelity levels.

        The most recent *recent_count* summaries are COMPRESSED.
        Older summaries are PLACEHOLDER, unless they are in the
        *forgotten_indices* set, in which case they are also PLACEHOLDER
        (regardless of recency).

        Parameters
        ----------
        technical_summaries : list[str]
            List of L2 summary strings, oldest first.
        recent_count : int
            Number of most recent summaries to keep as COMPRESSED.
        forgotten_indices : set[int] or None
            Set of indices that have been marked as forgotten.

        Returns
        -------
        list[tuple[str, Fidelity]]
            List of (summary_text, fidelity) pairs, oldest first.
        """
        result: list[tuple[str, Fidelity]] = []
        n = len(technical_summaries)
        for i, summary in enumerate(technical_summaries):
            if forgotten_indices and i in forgotten_indices:
                result.append((summary, Fidelity.PLACEHOLDER))
            elif n - i <= recent_count:
                result.append((summary, Fidelity.COMPRESSED))
            else:
                result.append((summary, Fidelity.PLACEHOLDER))
        return result

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
            "forgotten_l2_indices": list(self.forgotten_l2_indices),
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
        instance.forgotten_l2_indices = set(data.get("forgotten_l2_indices", []))
        for turn in data.get("recent_turns", []):
            instance.recent_turns.append(turn)
        return instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset all history — drops recent turns, summary, and forgotten state."""
        self.recent_turns.clear()
        self.compressed_summary = ""
        self.l3_summaries.clear()
        self.forgotten_l2_indices.clear()

    def clear_turns(self) -> None:
        """Clear all recent turns from the buffer.

        Unlike :meth:`clear`, this only removes the verbatim turn
        history, leaving the compressed summary intact.
        """
        self.recent_turns.clear()
