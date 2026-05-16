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

    def __init__(self, max_turns: int = 5) -> None:
        self.max_turns: int = max_turns
        self.recent_turns: deque[dict[str, str]] = deque(maxlen=max_turns)
        self.compressed_summary: str = ""

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
        """Return the compressed summary (placeholder for Phase 8).

        Currently returns an empty string — will be populated by
        the memory summarizer in Phase 8.
        """
        return self.compressed_summary

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
