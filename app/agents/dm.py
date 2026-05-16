"""
Dungeon Master Agent — the STORYTELLER, RULES ARBITER, and WORLD NARRATOR.

This module defines the DM system prompt and the DungeonMaster class that
orchestrates the game loop.  The DM is the only long-lived agent in the
system; it interprets player intent, decides which deterministic tools to
invoke, weaves narrative, and proposes world state changes at every turn.
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.history import SessionHistory
from app.agents.parser import parse_dm_response
from app.agents.tools import dispatch_tool
from app.llm.base import LLMProvider
from app.world.validator import apply_changes, validate_state_changes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DM System Prompt
# ---------------------------------------------------------------------------

DM_SYSTEM_PROMPT: str = """
# ROLE

You are the Dungeon Master — the storyteller, rules arbiter, and living world of a
dark fantasy RPG.  You exist at the intersection of narrative and mechanics.  Your
purpose is to interpret what the player attempts, decide whether the rules need to
speak, describe what happens, and move the story forward.  You are an author as
much as a referee.  The world breathes through your words.

# CORE PHILOSOPHY

This is a storytelling system first.  Combat, dice, and rules mechanics exist to
serve the narrative — they create stakes, consequences, and texture — but the
story is always the primary experience.  Every scene should feel alive.  Every
decision should matter.  Every outcome, whether triumph or disaster, should deepen
the tale.

Three concerns are separated and must never bleed into each other:

1. **Narrative decisions** belong to you, the DM — what happens, why, and how it
   feels.  You decide when the player faces a consequence, when an NPC speaks,
   when the world reacts.

2. **Numeric outcomes** belong to deterministic tools — dice rolls, damage math,
   rule lookups.  You decide *when* a tool is needed and *why*; the tool decides
   the actual number.

3. **Persistent truth** belongs to the world state — what has actually happened
   and been recorded.  You propose changes; the system validates and applies them.

You must NEVER simulate randomness or calculate rules yourself.  You decide the
stakes; the tools decide the outcomes.

# AVAILABLE TOOLS

You can request tool calls to resolve uncertainty.  Each tool is described below.
When you need one, include a tool_request in your output.

## dice
Roll dice using standard tabletop notation.  Use for any randomness that affects
the story — damage, random events, uncertainty about how many of something exist.
Examples: "2d6+3", "d20", "4d6k3", "d20 advantage".
Parameters: {"formula": str}

## table
Look up a random table entry.  Use for encounters, loot, weather, NPC traits,
or any structured randomness defined in the world's tables.
Parameters: {"table_name": str}

## skill_check
Resolve a character's attempt to do something where success is uncertain.
Given the character's relevant ability, skill proficiency, and the difficulty
class, returns success or failure with roll details.
Parameters: {"ability": str, "skill": str, "dc": int}

## attack
Resolve a combat attack against a defender.  Given the attacker's stats and
the defender's armour class, returns hit or miss and damage.
Parameters: {"attacker_stats": dict, "defender_ac": int}

## saving_throw
Resolve whether a character resists an effect (spell, poison, trap, etc.).
Given stats, the difficulty class, and the type of effect, returns success
or failure.
Parameters: {"ability": str, "dc": int, "effect_type": str}

# OUTPUT FORMAT

Your response must be structured so the system can parse it.  Use XML-style
tags to separate the different parts of your output:

## narrative (required)
The story text shown to the player.  Rich, immersive prose that describes
what happens.  This is your primary output — everything else supports it.

<narrative>
The ancient door groans on rusted hinges as you push it open.  Beyond lies a
circular chamber lit by guttering torches.  In the centre, a hooded figure
kneels before an altar of black stone.  The air smells of old dust and copper.
</narrative>

## tool_request (optional, repeatable)
When you need the outcome of an uncertain action, request a tool call.  The
system will execute the tool and inject the result before you continue.

<tool_request name="dice" params='{"formula":"d20+5"}' />

## state_change (optional, repeatable)
When something changes in the world that must be persisted — the player picks
up an item, an NPC is defeated, a quest advances — propose the change here.

<state_change action="append" path="inventory" value="Rusted Key" />
<state_change action="set" path="quests.old_well.status" value="completed" />

## npc_request (optional, repeatable, reserved for future use)
When an NPC interaction is complex enough to require its own agent, request
one here.  (Currently reserved — the system will ignore these for now.)

<npc_request npc_id="tavern_keep" context="The player is asking about the old well" />

# CONSTRAINTS

- Never simulate dice rolls or calculate numeric outcomes.  Always request a
  tool call when randomness or rules are involved.
- Never update state directly in your narrative.  Always use a state_change
  tag to propose changes; the system applies them.
- Never reveal your internal reasoning, tool requests, or state changes to the
  player.  Only the narrative tag is player-facing.
- Keep your response focused on the current scene.  Do not recap the entire
  session unless the player explicitly asks.
- React to both the player's input and the results of tool calls.  When a tool
  result comes back, weave it into the narrative naturally.
- Do not break character.  You are the DM — you speak with authority about the
  world, its inhabitants, and the consequences of the player's choices.
- If the player attempts something impossible, do not call a tool.  Describe
  why it fails and invite a different approach.
- If the player attempts something with uncertain stakes, call a tool.  Let
  the dice tell the story.

# TONE AND STYLE

Dark fantasy.  The world is dangerous, beautiful, and indifferent.  Describe
scenes vividly — engage all the senses.  The player should feel the chill of
the crypt, the weight of their armour, the flicker of torchlight on stone.

- Use rich, specific prose.  "The air smells of wet stone and old ashes" rather
  than "The room is old and dusty."
- Maintain a consistent second-person perspective ("you see", "you feel", "you
  stand before...").
- Vary sentence length for rhythm.  Short sentences for tension.  Longer ones
  for atmosphere.
- Let silence breathe.  Not every moment needs description.  Sometimes "The
  forest is still.  Too still." says more than a paragraph.
- Respond to the player's tone.  If they are cautious, reward caution.  If
  they are reckless, let the world punish them fairly.
- Move the story forward.  Every response should advance the scene, present a
  new choice, or reveal something the player did not know.
"""

# ---------------------------------------------------------------------------
# DungeonMaster
# ---------------------------------------------------------------------------


class DungeonMaster:
    """The Dungeon Master agent — orchestrator of the game loop.

    The DungeonMaster is the only long-lived agent in the system.  It holds
    references to the LLM provider, the current world state, and the player
    character, and it is responsible for:

    - Interpreting player intent
    - Building the LLM context (system prompt + history + state)
    - Deciding which deterministic tools to invoke
    - Parsing the LLM's structured output
    - Proposing world state changes
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        world_state: Any | None,
        character: Any | None,
    ) -> None:
        """Store references for later use in the turn loop.

        Parameters
        ----------
        llm_provider : LLMProvider or None
            The configured LLM provider used to call the DM model.
        world_state : WorldState or None
            The current persistent world state snapshot.
        character : Character or None
            The player character model.
        """
        self.llm_provider = llm_provider
        self.world_state = world_state
        self.character = character
        self.turn_count: int = 0
        self.history: SessionHistory = SessionHistory(max_turns=5)

    def _build_context(self, player_input: str) -> list[dict[str, str]]:
        """Build the message list for the LLM call.

        Constructs a conversation context starting with the DM system prompt,
        followed by the current world state summary, character summary, and
        the player's latest input.

        Parameters
        ----------
        player_input : str
            The player's latest action or utterance.

        Returns
        -------
        list[dict[str, str]]
            A list of message dicts, each with ``role`` and ``content`` keys,
            suitable for passing to an LLM provider's ``call()`` or ``stream()``.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": DM_SYSTEM_PROMPT},
        ]

        # Incorporate world state summary (if available)
        if self.world_state is not None:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Current world state:\n"
                        f"  Location: {self.world_state.current_location}\n"
                        f"  Turn: {self.world_state.turn_count}\n"
                    ),
                }
            )

        # Incorporate character summary (if available)
        if self.character is not None:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Player character:\n"
                        f"  Name: {self.character.name}\n"
                        f"  Class: {self.character.character_class} (level "
                        f"{self.character.level})\n"
                        f"  HP: {self.character.hp}/{self.character.max_hp}\n"
                        f"  AC: {self.character.ac}\n"
                    ),
                }
            )

        # Append conversation history (last few exchanges for context)
        for msg in self.history.get_context_messages():
            messages.append(msg)

        # Add the player's input
        messages.append({"role": "user", "content": player_input})

        return messages

    def process_turn(self, player_input: str) -> dict[str, Any]:
        """Process a single turn of player input.

        The full turn loop:

        1. Build the LLM context from system prompt, world state, character
           info, conversation history, and the player's input.
        2. Call the LLM provider with the context.
        3. Parse the response for tool requests, narrative, and state changes.
        4. If tool requests were found, execute each tool and inject results
           into a second LLM call.
        5. Parse the second response for the final narrative and state changes.
        6. Validate state changes against the world state schema.
        7. Apply valid changes, log/skip invalid ones.
        8. Return the structured result.

        Parameters
        ----------
        player_input : str
            The player's latest action or utterance.

        Returns
        -------
        dict[str, Any]
            A structured response containing:

            - **narrative** (str): The story text for the player.
            - **state_changes** (list[dict]): Applied state changes.
            - **tool_results** (list[dict]): Results of any tool calls.
            - **turn_count** (int): The current turn number.
            - **ok** (bool): Whether the turn completed without critical
              error.
            - **error** (str | None): Error message if something went wrong.
        """
        if not player_input or not isinstance(player_input, str):
            return {
                "narrative": "",
                "state_changes": [],
                "tool_results": [],
                "turn_count": self.turn_count,
                "ok": False,
                "error": "Player input must be a non-empty string",
            }

        self.turn_count += 1

        # ------------------------------------------------------------------
        # 1. Build context and call LLM
        # ------------------------------------------------------------------
        messages = self._build_context(player_input)

        try:
            first_response = self._call_llm(messages)
        except Exception:
            logger.exception("LLM call failed on first attempt")
            return {
                "narrative": "",
                "state_changes": [],
                "tool_results": [],
                "turn_count": self.turn_count,
                "ok": False,
                "error": "LLM call failed",
            }

        # ------------------------------------------------------------------
        # 2. Parse the first response
        # ------------------------------------------------------------------
        try:
            parsed = parse_dm_response(first_response)
        except Exception as e:
            logger.warning("Parse failed on first response, retrying: %s", e)
            # Retry with a correction prompt
            messages.append(
                {
                    "role": "assistant",
                    "content": first_response,
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Please format your response correctly using the XML-style "
                        "tags as described in the system prompt."
                    ),
                }
            )
            try:
                first_response = self._call_llm(messages)
                parsed = parse_dm_response(first_response)
            except Exception:
                logger.exception("LLM retry also failed")
                return {
                    "narrative": "",
                    "state_changes": [],
                    "tool_results": [],
                    "turn_count": self.turn_count,
                    "ok": False,
                    "error": "Failed to get parseable response",
                }

        tool_requests = parsed["tool_requests"]

        # ------------------------------------------------------------------
        # 3. Execute tool requests
        # ------------------------------------------------------------------
        tool_results: list[dict[str, Any]] = []
        if tool_requests:
            for req in tool_requests:
                result = dispatch_tool(req["name"], req.get("params", {}))
                tool_results.append(
                    {
                        "name": req["name"],
                        "params": req.get("params", {}),
                        "result": result,
                    }
                )

            # ------------------------------------------------------------------
            # 4. Inject tool results and call LLM again for final narrative
            # ------------------------------------------------------------------
            tool_summary = self._format_tool_results(tool_results)
            messages.append(
                {
                    "role": "assistant",
                    "content": first_response,
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Tool results:\n{tool_summary}\n\n"
                        f"Now continue the narrative, weaving these results into "
                        f"the story.  Include the final narrative and any "
                        f"necessary state_change tags."
                    ),
                }
            )

            try:
                second_response = self._call_llm(messages)
            except Exception:
                logger.exception("Second LLM call failed")
                # Fall back to the first response's narrative
                second_response = first_response

            try:
                final_parsed = parse_dm_response(second_response)
            except Exception:
                final_parsed = parsed
        else:
            # No tools requested — use the first response directly
            final_parsed = parsed

        narrative = final_parsed.get("narrative", "")
        state_changes = final_parsed.get("state_changes", [])

        # ------------------------------------------------------------------
        # 5. Validate and apply state changes
        # ------------------------------------------------------------------
        applied_changes: list[dict[str, Any]] = []
        valid_changes: list[dict[str, Any]] = []
        warnings: list[str] = []

        if self.world_state is not None and state_changes:
            validation_errors = validate_state_changes(state_changes, self.world_state)
            if validation_errors:
                for err in validation_errors:
                    logger.warning("State change validation error: %s", err)
                # Filter out invalid changes
                for i, change in enumerate(state_changes):
                    change_errors = validate_state_changes([change], self.world_state)
                    if not change_errors:
                        valid_changes.append(change)
                    else:
                        logger.warning(
                            "Skipping invalid state change #%d: %s",
                            i,
                            change_errors[0],
                        )
            else:
                valid_changes = state_changes

            if valid_changes:
                try:
                    self.world_state = apply_changes(self.world_state, valid_changes)
                    applied_changes = valid_changes
                except Exception:
                    logger.exception("Failed to apply state changes")
                    warnings.append(
                        f"Failed to apply {len(valid_changes)} state change(s)"
                    )

        # Update world turn count
        if self.world_state is not None:
            self.world_state.turn_count = self.turn_count

        # Update conversation history — store cleaned narrative (no XML tags)
        self.history.add_turn(player_input, narrative)

        return {
            "narrative": narrative,
            "state_changes": applied_changes,
            "tool_results": tool_results,
            "turn_count": self.turn_count,
            "ok": True,
            "error": None,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Call the LLM provider and return the response content.

        Handles the case where the provider is None (returns a canned
        response for testing), timeouts with a single retry, and
        provider errors.

        Parameters
        ----------
        messages : list[dict[str, str]]
            The message list to send to the LLM.

        Returns
        -------
        str
            The response content text.

        Raises
        ------
        RuntimeError
            If the LLM call fails after retry.
        """
        if self.llm_provider is None:
            # Return a canned response when no provider is configured
            # (useful for testing or when the LLM is not available)
            return "<narrative>\nThe scene unfolds before you.\n</narrative>"

        try:
            response = self.llm_provider.call(messages)
        except Exception:
            logger.warning("LLM call failed, retrying once")
            try:
                response = self.llm_provider.call(messages)
            except Exception as e:
                raise RuntimeError(f"LLM call failed after retry: {e}") from e

        content = response.get("content", "")
        if not content:
            raise RuntimeError("LLM returned empty content")

        return content

    def _format_tool_results(self, tool_results: list[dict[str, Any]]) -> str:
        """Format tool results into a readable summary for the LLM.

        Parameters
        ----------
        tool_results : list[dict]
            List of tool execution results, each with ``name`` and
            ``result`` keys.

        Returns
        -------
        str
            A formatted string summarising each tool result.
        """
        parts: list[str] = []
        for i, tr in enumerate(tool_results):
            name = tr.get("name", "unknown")
            result = tr.get("result", {})
            ok = result.get("ok", False) if isinstance(result, dict) else False
            result_data = (
                result.get("result", result) if isinstance(result, dict) else result
            )
            parts.append(f"  [{i + 1}] {name}: {'OK' if ok else 'FAILED'}")
            parts.append(f"      Result: {result_data}")
        return "\n".join(parts)
