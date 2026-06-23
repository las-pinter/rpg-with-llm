"""
Consultation Agent — Pure Q&A for players without touching game state.

Completely separate from DungeonMaster. Never touches game state, turn count,
NPC spawning, or summarization. Time is stopped — pure knowledge only.

Public functions
----------------
build_consultation_context
    Standalone helper that assembles context messages for a consultation LLM
    call.  Pure function — no side effects, no state.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.llm.base import LLMProvider
from app.utils import atomic_write

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CONSULTATION_SYSTEM_PROMPT = (
    "You are the DM in consultation mode. Time is stopped. "
    "Answer the player's question directly. Do NOT advance the story, "
    "spawn NPCs, call tools, roll dice, or propose state changes. "
    "If the player tries to take an action, politely refuse: "
    "'Time is stopped. You cannot take actions during consultation. "
    "I can only answer questions about the world, your character, or the rules.' "
    "Just answer the question based on the current world state and character "
    "information provided."
)

_UNAVAILABLE_MESSAGE = "The DM is unavailable for consultation right now."
_ERROR_MESSAGE = "The DM is momentarily distracted. Please try again."


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def build_consultation_context(
    question: str,
    world_state_snapshot: dict[str, Any],
    character_snapshot: dict[str, Any],
    character_name: str = "",
    recent_consultations: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build the context messages for a consultation LLM call.

    Pure function — no side effects, no state.

    Parameters
    ----------
    question:
        The player's question or consultation request.
    world_state_snapshot:
        Read-only snapshot of the current world state.
    character_snapshot:
        Read-only snapshot of the player character.
    character_name:
        The name of the player character (used for personalisation).
    recent_consultations:
        Optional list of recent Q&A entries for continuity.  Each entry
        should have at least ``question`` and ``answer`` keys.

    Returns
    -------
    list[dict[str, str]]
        Messages in OpenAI chat-completion format.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _CONSULTATION_SYSTEM_PROMPT},
    ]

    # World state as readable key-value text
    if world_state_snapshot:
        world_lines = "\n".join(f"  {k}: {v}" for k, v in world_state_snapshot.items())
        messages.append(
            {
                "role": "system",
                "content": f"Current World State:\n{world_lines}",
            }
        )

    # Character sheet as readable key-value text
    if character_snapshot or character_name:
        char_parts = []
        if character_name:
            char_parts.append(f"  name: {character_name}")
        if character_snapshot:
            char_parts.extend(f"  {k}: {v}" for k, v in character_snapshot.items())
        char_lines = "\n".join(char_parts)
        messages.append(
            {
                "role": "system",
                "content": f"Character Information:\n{char_lines}",
            }
        )

    # Previous consultation log (last 5 entries for context window sanity)
    if recent_consultations:
        consult_lines = ["Previous consultations:"]
        for i, entry in enumerate(recent_consultations[-5:], start=1):
            q = entry.get("question", "")
            a = entry.get("answer", "")
            consult_lines.append(f"  {i}. Q: {q}\n     A: {a}")
        messages.append(
            {
                "role": "system",
                "content": "\n".join(consult_lines),
            }
        )

    # The player's question
    messages.append({"role": "user", "content": question})

    return messages


# ---------------------------------------------------------------------------
# Consultation log persistence
# ---------------------------------------------------------------------------


def read_consultation_log(slug: str, last_n: int = 5) -> list[dict]:
    """Read the last N entries from the consultation log for a save slug.

    Args:
        slug: The save slug (e.g., "gorten-tarragon-20260615_203021_164175-e00b")
        last_n: Number of recent entries to return (default 5)

    Returns:
        List of consultation entry dicts, most recent last, empty list if
        no log exists or log is empty.
    """
    # Validate slug
    if "/" in slug or "\\" in slug or ".." in slug:
        raise ValueError(f"Invalid save slug: {slug}")

    from app.world.persistence import WorldStorage

    storage = WorldStorage(data_dir=Path("data"))
    log_path = storage.saves_dir / slug / "consultation_log.json"

    if not log_path.exists():
        return []

    try:
        with open(log_path, encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list):
            return []
        return entries[-last_n:] if len(entries) > last_n else entries
    except (json.JSONDecodeError, OSError):
        return []


def append_to_consultation_log(slug: str, entry: dict) -> None:
    """Append a consultation entry to the consultation log for a save slug.

    Creates the log file if it doesn't exist. Uses atomic writes.

    Args:
        slug: The save slug (e.g., "gorten-tarragon-20260615_203021_164175-e00b")
        entry: Dict with keys: turn (int), question (str), answer (str),
               timestamp (str)
    """
    # Validate slug
    if "/" in slug or "\\" in slug or ".." in slug:
        raise ValueError(f"Invalid save slug: {slug}")

    from app.world.persistence import WorldStorage

    storage = WorldStorage(data_dir=Path("data"))
    log_path = storage.saves_dir / slug / "consultation_log.json"

    # Ensure save directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing entries
    if log_path.exists():
        try:
            with open(log_path, encoding="utf-8") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, OSError):
            entries = []
    else:
        entries = []

    # Append new entry
    entries.append(entry)

    # Write atomically
    atomic_write(log_path, entries)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ConsultationAgent:
    """Standalone agent for player consultation.

    Completely separate from DungeonMaster. Never touches game state,
    turn count, NPC spawning, or summarization. Pure Q&A.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        character_name: str = "",
    ) -> None:
        """Initialise the consultation agent.

        Parameters
        ----------
        llm_provider:
            The LLM provider used to answer questions.  If *None* a canned
            "unavailable" message is returned for every call.
        character_name:
            The name of the player character (used for personalisation).
        """
        self.llm_provider = llm_provider
        self.character_name = character_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consult(
        self,
        question: str,
        world_state_snapshot: dict[str, Any],
        character_snapshot: dict[str, Any],
        recent_consultations: list[dict[str, Any]] | None = None,
    ) -> str:
        """Answer a player question **without** affecting game state.

        Parameters
        ----------
        question:
            The player's question or consultation request.
        world_state_snapshot:
            Read-only snapshot of the current world state (location, turn
            count, active NPCs, established facts).
        character_snapshot:
            Read-only snapshot of the player character (name, class, level,
            HP, abilities, inventory).
        recent_consultations:
            Optional list of recent Q&A entries for continuity.  Each entry
            should have at least ``question`` and ``answer`` keys.

        Returns
        -------
        str
            The DM's answer as plain text.  Any XML-style tags in the
            response are stripped before returning.
        """
        if self.llm_provider is None:
            return _UNAVAILABLE_MESSAGE

        if not question or not question.strip():
            return "Please ask a question."

        messages = self._build_context(
            question=question,
            world_state_snapshot=world_state_snapshot,
            character_snapshot=character_snapshot,
            recent_consultations=recent_consultations,
        )

        try:
            response = self.llm_provider.call(messages)
            answer: str = response.get("content", "")
            # Strip XML/HTML-like tags that the LLM might produce
            answer = re.sub(r"<[^>]+>", "", answer)
            return answer.strip()
        except Exception:
            return _ERROR_MESSAGE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_context(
        self,
        question: str,
        world_state_snapshot: dict[str, Any],
        character_snapshot: dict[str, Any],
        recent_consultations: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        """Assemble the message list for the LLM call.

        Delegates to the standalone :func:`build_consultation_context`
        function, injecting ``self.character_name`` for personalisation.

        Returns
        -------
        list[dict[str, str]]
            Messages in OpenAI chat-completion format.
        """
        return build_consultation_context(
            question=question,
            world_state_snapshot=world_state_snapshot,
            character_snapshot=character_snapshot,
            character_name=self.character_name,
            recent_consultations=recent_consultations,
        )
