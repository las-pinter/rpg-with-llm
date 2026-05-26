"""
Context builder — builds the message list for the DM LLM call.

Extracted from ``DungeonMaster._build_context()`` to keep the DM agent class
focused on orchestration rather than message construction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.rules.plausibility import classify_action

if TYPE_CHECKING:
    from app.agents.dm import DungeonMaster

logger = logging.getLogger(__name__)


def build_context(
    dm: DungeonMaster,
    player_input: str,
    plausibility_note: str | None = None,
) -> list[dict[str, str]]:
    """Build the message list for the LLM call.

    Constructs a conversation context starting with the DM system prompt,
    followed by the current world state summary, character summary, and
    the player's latest input.

    Parameters
    ----------
    dm : DungeonMaster
        The DungeonMaster instance providing world state, character,
        history, and other context.
    player_input : str
        The player's latest action or utterance.
    plausibility_note : str or None
        Optional note about action plausibility to inject into the
        context (used for implausible/ambitious actions).  When ``None``,
        the method performs its own classification via
        :func:`classify_action` and injects a note for
        ``implausible``/``ambitious`` results.

    Returns
    -------
    list[dict[str, str]]
        A list of message dicts, each with ``role`` and ``content`` keys,
        suitable for passing to an LLM provider's ``call()`` or ``stream()``.
    """
    # Deferred import to avoid circular import — DM_SYSTEM_PROMPT is defined
    # in dm.py which imports this module.
    from app.agents.dm import DM_SYSTEM_PROMPT

    messages: list[dict[str, str]] = [
        {"role": "system", "content": DM_SYSTEM_PROMPT},
    ]

    # Auto-classify if no note was provided and we have a character
    if plausibility_note is None and dm.character is not None:
        classification = classify_action(dm.character, player_input)
        category = classification.get("category", "plausible")
        if category in ("implausible", "ambitious"):
            reason = classification.get("reason", "")
            suggested_dc = classification.get("dc", "N/A")
            plausibility_note = (
                f"[PLAUSIBILITY NOTE: The player attempts something "
                f"{category}. {reason} "
                f"Suggested DC: {suggested_dc}. "
                f"The player must roll for this — set an appropriately "
                f"high DC and describe the stakes before the roll.]"
            )

    # Inject plausibility note early if provided
    if plausibility_note:
        messages.append({"role": "system", "content": plausibility_note})

    # Incorporate world state summary (if available)
    if dm.world_state is not None:
        context_parts: list[str] = [
            f"Current world state:\n"
            f"  Location: {dm.world_state.current_location}\n"
            f"  Turn: {dm.world_state.turn_count}\n",
        ]

        if dm.world_state.established_facts:
            context_parts.append(
                "Established facts:\n"
                + "\n".join(f"  - {fact}" for fact in dm.world_state.established_facts)
            )

        messages.append(
            {
                "role": "system",
                "content": "\n".join(context_parts),
            }
        )

        # If the game is already in progress, tell the LLM not to generate
        # an opening scene (since it has no conversation history, it would
        # otherwise treat every request as the first turn)
        if dm.world_state.turn_count > 0:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "IMPORTANT: The adventure is already in progress. "
                        "Do NOT describe an opening scene or start a new scenario. "
                        "Continue the current narrative naturally from where the "
                        "player left off. The player's action is a continuation "
                        "of the existing story — react to it directly."
                    ),
                }
            )

    # Incorporate character summary (if available)
    if dm.character is not None:
        # Build ability scores string
        abilities = getattr(dm.character, "abilities", {})
        abilities_str = ", ".join(f"{k}={v}" for k, v in sorted(abilities.items()))
        # Build skills string
        skills = getattr(dm.character, "skills", [])
        skills_str = ", ".join(skills) if skills else "none"
        # Build inventory string
        inventory = getattr(dm.character, "inventory", [])
        inventory_str = ", ".join(inventory) if inventory else "empty"
        # Gold
        gold = getattr(dm.character, "gold", 0)

        messages.append(
            {
                "role": "system",
                "content": (
                    f"Player character:\n"
                    f"  Name: {dm.character.name}\n"
                    f"  Class: {dm.character.character_class} "
                    f"(level {dm.character.level})\n"
                    f"  HP: {dm.character.hp}/{dm.character.max_hp}\n"
                    f"  AC: {dm.character.ac}\n"
                    f"  Abilities: {abilities_str}\n"
                    f"  Skills: {skills_str}\n"
                    f"  XP: {dm.character.xp}\n"
                    f"  Gold: {gold} GP\n"
                    f"  Inventory: {inventory_str}\n"
                ),
            }
        )

    # Append compressed summary if available
    summary_text = dm.history.get_summary()
    if summary_text:
        messages.append(
            {
                "role": "system",
                "content": (f"Session summary (previous events):\n{summary_text}"),
            }
        )

    # Append conversation history (last few exchanges for context)
    for msg in dm.history.get_context_messages():
        messages.append(msg)

    # Add the player's input
    messages.append({"role": "user", "content": player_input})

    total_chars = sum(len(m.get("content", "")) for m in messages)
    logger.debug("_build_context: %d messages, ~%d chars", len(messages), total_chars)

    return messages
