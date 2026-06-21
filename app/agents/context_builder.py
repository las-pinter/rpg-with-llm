"""
Context builder — builds the message list for the DM LLM call.

Extracted from ``DungeonMaster._build_context()`` to keep the DM agent class
focused on orchestration rather than message construction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.agents.history import Fidelity, SessionHistory
from app.rules.plausibility import classify_action

if TYPE_CHECKING:
    from app.agents.dm import DungeonMaster
    from app.agents.record_keeper import RecordKeeperAgent

logger = logging.getLogger(__name__)

# Maximum character budget for the timeline context block.
# Approx 4 chars per token → 3000 chars ≈ 750 tokens.
# Can be tuned at the module level without changing function signatures.
MAX_TIMELINE_CHARS: int = 3000


def build_context(
    dm: DungeonMaster,
    player_input: str,
    plausibility_note: str | None = None,
    record_keeper: RecordKeeperAgent | None = None,
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
        from app.character.model import CharacterRecord

        if isinstance(dm.character, CharacterRecord):
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
        from app.character.model import CharacterRecord

        record = dm.character
        sheet = getattr(dm, "derived_sheet", None)

        abilities_str = ", ".join(
            f"{k}={v}" for k, v in sorted(record.abilities.items())
        )
        skills = getattr(record, "skills", [])
        skills_str = ", ".join(skills) if skills else "none"
        inventory = getattr(record, "inventory", [])
        # Handle both list[str] (legacy Character) and list[Item] (CharacterRecord)
        if inventory and isinstance(inventory[0], str):
            inventory_str = ", ".join(inventory)
        elif inventory:
            inventory_str = ", ".join(item.name for item in inventory)
        else:
            inventory_str = "empty"
        gold = getattr(record, "gold", 0)

        # Build derived stats display if available
        ability_mods_str = ""
        skill_mods_str = ""
        proficiency_bonus_str = "?"
        passive_perception_str = "?"
        save_str = "?/?/?/?/?/?"
        attack_str = "?/?/?"
        ac_formula_str = "unknown"

        if sheet:
            ability_mods_str = ", ".join(
                f"{k}{v:+d}" for k, v in sorted(sheet.ability_modifiers.items())
            )

            key_skills = [
                "perception",
                "stealth",
                "investigation",
                "athletics",
                "acrobatics",
            ]
            skill_mods_str = ", ".join(
                f"{k}={sheet.skill_modifiers.get(k, '?')}"
                for k in key_skills
                if k in sheet.skill_modifiers
            )

            proficiency_bonus_str = str(sheet.proficiency_bonus)
            passive_perception_str = str(sheet.passive_perception)

            save_mods = sheet.saving_throw_modifiers
            save_str = f"{save_mods.get('STR', '?')}/{save_mods.get('DEX', '?')}/{save_mods.get('CON', '?')}/{save_mods.get('INT', '?')}/{save_mods.get('WIS', '?')}/{save_mods.get('CHA', '?')}"

            atk = sheet.attack_bonus
            attack_str = f"{atk.get('melee', '?')}/{atk.get('ranged', '?')}/{atk.get('spell', '?')}"

            ac_formula_str = (
                sheet.formulas.get("ac", "unknown") if sheet.formulas else "unknown"
            )

        # Get HP from resources (CharacterRecord) or legacy hp/max_hp fields
        if isinstance(record, CharacterRecord) and record.resources:
            hp_res = record.resources.get("hp")
            hp_current = str(hp_res.value) if hp_res else "?"
            hp_max = str(hp_res.max) if hp_res else "?"
        elif hasattr(record, "max_hp"):
            # Legacy Character compat
            hp_current = str(getattr(record, "hp", "?"))
            hp_max = str(getattr(record, "max_hp", "?"))
        else:
            hp_current = "?"
            hp_max = "?"

        messages.append(
            {
                "role": "system",
                "content": (
                    f"Player character:\n"
                    f"  Name: {record.name}\n"
                    f"  Class: {record.character_class} "
                    f"(level {record.level})\n"
                    f"  HP: {hp_current}/{hp_max}\n"
                    f"  AC: {sheet.ac if sheet else getattr(record, 'ac', '?')} "
                    f"({ac_formula_str})\n"
                    f"  Abilities: {abilities_str}\n"
                    f"  Ability Modifiers: ({ability_mods_str})\n"
                    f"  Skills: {skills_str}\n"
                    f"  Key Skill Mods: ({skill_mods_str})\n"
                    f"  Proficiency Bonus: +{proficiency_bonus_str}\n"
                    f"  Passive Perception: {passive_perception_str}\n"
                    f"  Saves - STR: {save_str.split('/')[0]}, "
                    f"DEX: {save_str.split('/')[1]}, "
                    f"CON: {save_str.split('/')[2]}, "
                    f"INT: {save_str.split('/')[3]}, "
                    f"WIS: {save_str.split('/')[4]}, "
                    f"CHA: {save_str.split('/')[5]}\n"
                    f"  Attack Bonus - Melee: {attack_str.split('/')[0]}, "
                    f"Ranged: {attack_str.split('/')[1]}, "
                    f"Spell: {attack_str.split('/')[2]}\n"
                    f"  XP: {record.xp}\n"
                    f"  Gold: {gold} GP\n"
                    f"  Inventory: {inventory_str}\n"
                ),
            }
        )

    # === RECORD-KEEPER CONTEXT INJECTION ===
    if record_keeper is not None and dm.world_state is not None:
        try:
            # Build a current_narrative from the last few turns
            narrative_parts = []
            # recent_turns is a deque — convert to list for slice access
            recent = list(dm.history.recent_turns)
            for turn in recent[-3:]:  # last 3 turns
                narrative_parts.append(f"Player: {turn.get('user', '')}")
                narrative_parts.append(f"DM: {turn.get('assistant', '')}")
            current_narrative = "\n".join(narrative_parts)

            rk_context = record_keeper.analyze_pre_dm(
                player_input=player_input,
                world_state=dm.world_state,
                current_narrative=current_narrative,
            )

            if rk_context.context_text:
                # Timeline context (truncated to 1000 chars)
                timeline_text = rk_context.timeline_summary
                if len(timeline_text) > 1000:
                    timeline_text = timeline_text[:997] + "..."

                if timeline_text:
                    messages.append(
                        {
                            "role": "system",
                            "content": f"RECORD-KEEPER: Timeline Context\n\n{timeline_text}",
                        }
                    )

                # Relevant entities (compact single-line summaries)
                if rk_context.relevant_entities:
                    entity_lines = []
                    for entity in rk_context.relevant_entities:
                        eid = entity.get("entity_id", "?")
                        ename = entity.get("name", eid)
                        etype = entity.get("entity_type", "?")
                        entity_lines.append(f"  - [{etype}] {ename} ({eid})")

                    messages.append(
                        {
                            "role": "system",
                            "content": "RECORD-KEEPER: Relevant Entities\n\n"
                            + "\n".join(entity_lines),
                        }
                    )
        except Exception:
            logger.exception("Failed to inject Record-Keeper context")
            # Don't block the game if record-keeper fails

    # --- Timeline context (replaces old summary + full conversation history) ---
    timeline_parts: list[str] = []

    # 1. L3 meta-summaries (oldest first)
    for l3_text, fidelity in dm.history.get_l3_summaries_with_fidelity():
        if fidelity == Fidelity.COMPRESSED:
            timeline_parts.append(f"[L3 Meta-Summary]\n{l3_text}")
        elif fidelity == Fidelity.PLACEHOLDER:
            timeline_parts.append(f"[L3 Meta-Summary (older)]\n{l3_text[:200]}...")

    # 2. L2 summaries from world_state (oldest first)
    if dm.world_state is not None:
        l2_with_fidelity = SessionHistory.get_l2_summaries_with_fidelity(
            dm.world_state.technical_summary,
            forgotten_indices=dm.history.get_forgotten_indices(),
        )
        for i, (summary_text, fidelity) in enumerate(l2_with_fidelity):
            turn_start = i * 5 + 1
            turn_end = (i + 1) * 5
            if fidelity == Fidelity.COMPRESSED:
                timeline_parts.append(
                    f"[Session Summary: Turns {turn_start}-{turn_end}]\n{summary_text}"
                )
            elif fidelity == Fidelity.PLACEHOLDER:
                first_line = (
                    summary_text.split(".")[0]
                    if "." in summary_text
                    else summary_text[:100]
                )
                timeline_parts.append(
                    f"[Session Summary: Turns {turn_start}-{turn_end} (condensed)]\n{first_line}..."
                )

    # 3. Recent turns from history buffer (oldest first)
    buffer_size = len(dm.history.recent_turns)
    for i, (turn, fidelity) in enumerate(dm.history.get_turns_with_fidelity()):
        turn_num = dm.turn_count - buffer_size + i + 1 if dm.turn_count > 0 else i + 1
        if fidelity == Fidelity.FULL:
            timeline_parts.append(
                f"[Turn {turn_num}]\nPlayer: {turn['user']}\nDM: {turn['assistant']}"
            )
        elif fidelity == Fidelity.PLACEHOLDER:
            timeline_parts.append(
                f"[Turn {turn_num} (older)]\nPlayer: {turn['user'][:100]}..."
            )

    # Assemble the timeline context message
    if timeline_parts:
        total_chars = sum(len(p) for p in timeline_parts)

        if total_chars > MAX_TIMELINE_CHARS:
            # Degrade oldest L2 summaries and drop oldest turns to fit budget.
            # L3 entries are preserved by design (they are expected to be small).
            degraded_timeline: list[str] = []
            remaining_to_trim = total_chars - MAX_TIMELINE_CHARS
            for part in timeline_parts:
                if remaining_to_trim <= 0:
                    degraded_timeline.append(part)
                elif part.startswith("[Session Summary:"):
                    shortened = part[:150] + "..."
                    degraded_timeline.append(shortened)
                    remaining_to_trim -= len(part) - len(shortened)
                elif part.startswith("[Turn"):
                    # Drop older turns entirely
                    remaining_to_trim -= len(part)
                    continue
                else:
                    # L3 entries are preserved (expected to be small)
                    degraded_timeline.append(part)
            timeline_parts = degraded_timeline

        if dm.turn_count > 0:
            timeline_header = (
                "Active Memory Context (most recent entries shown, "
                "oldest first within each tier):"
            )
        else:
            timeline_header = "Active Memory Context:"

        messages.append(
            {
                "role": "system",
                "content": timeline_header + "\n\n" + "\n\n".join(timeline_parts),
            }
        )

    # Append the most recent 1-2 turns (up to 4 messages) as user/assistant
    # pairs to preserve conversation flow for the LLM (it needs to see
    # the alternation pattern).
    recent_msgs = dm.history.get_context_messages()
    for msg in recent_msgs[-4:]:
        messages.append(msg)

    # Add the player's input
    messages.append({"role": "user", "content": player_input})

    total_chars = sum(len(m.get("content", "")) for m in messages)
    logger.debug("_build_context: %d messages, ~%d chars", len(messages), total_chars)

    return messages
