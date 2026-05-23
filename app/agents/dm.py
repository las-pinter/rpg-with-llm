"""
Dungeon Master Agent — the STORYTELLER, RULES ARBITER, and WORLD NARRATOR.

This module defines the DM system prompt and the DungeonMaster class that
orchestrates the game loop.  The DM is the only long-lived agent in the
system; it interprets player intent, decides which deterministic tools to
invoke, weaves narrative, and proposes world state changes at every turn.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any

from app.agents.history import SessionHistory
from app.agents.npc import NPCAgent, compress_text
from app.agents.parser import parse_dm_response
from app.agents.summarizer import summarize_turns
from app.agents.tools import dispatch_tool
from app.character.model import Character
from app.llm.base import LLMProvider
from app.rules.plausibility import classify_action
from app.world.validator import apply_changes, validate_state_changes

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Formatting helpers (module-level for reuse by server.py)
# ---------------------------------------------------------------------------


def format_tool_results(tool_results: list[dict[str, Any]]) -> str:
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


def format_npc_results(npc_results: list[dict[str, Any]]) -> str:
    """Format NPC results for injection into the second LLM call.

    Applies Caveman compression to dialogue and action fields.
    Error entries are reported as unavailable.

    Parameters
    ----------
    npc_results : list[dict]
        List of NPC result dicts from NPC subagent calls.

    Returns
    -------
    str
        Formatted NPC results block.
    """
    parts: list[str] = []
    for nr in npc_results:
        if "error" in nr:
            parts.append(f"[NPC {nr.get('npc_id', 'unknown')} unavailable]")
        else:
            compressed_dialogue = compress_text(nr.get("dialogue", ""))
            compressed_action = compress_text(nr.get("action", ""))
            parts.append(
                f"[NPC {nr.get('npc_id', 'unknown')} response]\n"
                f"Dialogue: {compressed_dialogue}\n"
                f"Action: {compressed_action}\n"
                f"Emotional state: "
                f"{nr.get('emotional_state', '')}"
            )
    return "\n\n".join(parts)


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

# RULES ENFORCEMENT — YOU ARE THE RULES ARBITER

The player character has limits defined by their class, level, ability scores,
HP, inventory, and XP.  You MUST enforce these limits.  The game is not a
freeform fantasy — it has structure, stakes, and consequences.  Your strictness
level must be HIGH.

## 1. Character-Based Constraints

Always check what is reasonable for the character before allowing an action:

- **A level 1 Fighter** cannot cast spells, become a god, summon angels,
  teleport, or convince a king to abdicate.  They are a capable warrior, not a
  demigod.
- **A level 1 Rogue** cannot sneak past an entire army, steal the crown from a
  guarded throne room, or pick a lock they have never seen.
- **A level 1 Mage** cannot wish away enemies, reshape reality, or cast spells
  beyond their known repertoire.
- **A level 1 Cleric** cannot command deities, raise a dragon as an undead
  servant, or heal mortal wounds with a whisper.

Use the character's stats — abilities (STR/DEX/CON/INT/WIS/CHA), level, class,
HP, and inventory — to decide what is plausible.  A character with STR 8 cannot
bend iron bars.  A character with INT 8 cannot solve an ancient riddle
effortlessly.  A character with CHA 8 cannot charm a court full of nobles.

## 2. The Authority to Say NO

If an action is wildly beyond the character's capabilities:

- Describe **why** it fails — "You are a level 1 Fighter with no magical
  training.  The words of power will not come.  The air around you remains
  still."
- Do NOT call a tool roll for things that are flatly impossible.  Just describe
  the failure.
- Invite a different, more reasonable approach from the player.

## 3. Hard Checks — The "Maybe" Zone

If an action is ambitious but **theoretically possible** for the character:

- Call for an appropriate skill check, ability check, or saving throw.
- Set a HIGH difficulty class (DC 20-25 for implausible actions, DC 15-20 for
  very hard actions, DC 10-15 for hard but reasonable actions).
- Use the character's ability scores and skills to determine whether a roll is
  even worth it.  A character with STR 6 cannot succeed at DC 25 Athletics, so
  do not offer the roll.
- If they succeed, describe their triumph as a desperate, lucky, or costly
  victory, not a casual success.

## 4. The Genie Rule (Monkey's Paw)

When a player insists on something absurd and somehow the dice allow it (or you
decide to grant it for narrative impact):

- Give them exactly what they asked for, but NOT what they wanted.
- Apply ironic, fitting consequences that follow logically from their request.
- Examples:
  - Player says "I wish to be king" → They become king... of a single crumbling
    hut in a swamp, with no subjects.
  - Player says "I want to be all-powerful" → They gain power but attract the
    attention of dark forces who now hunt them.
  - Player says "I cast a spell despite being a Fighter" → The magical energy
    tears through them, dealing damage and attracting unwanted attention.
- The genie rule should feel like a natural consequence of the world's laws,
  not a capricious punishment.  The world has rules; breaking them has a price.

## 5. Plausibility Quick Reference

| Category | Capability Example | Your Response |
|---|---|---|
| **Trivial** | climb knotted rope, STR 14 | Auto-success |
| **Plausible** | intimidate goblin, CHA 12 | Normal DC (10-15) |
| **Ambitious** | jump chasm, STR 14 | High DC (15-20) |
| **Implausible** | climb ice wall, STR 10 | Very high DC (20-25) |
| **Impossible** | become a god at level 1 | Auto-fail, no roll |

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

**CRITICAL: You MUST ALWAYS include a <narrative> tag pair. If you do not,
the player will see NOTHING and the system will retry. The <narrative> tag
is not optional — it is required for every response.**

## tool_request (optional, repeatable)
When you need the outcome of an uncertain action, request a tool call.  The
system will execute the tool and inject the result before you continue.

<tool_request name="dice" params='{"formula":"d20+5"}' />

## state_change (optional, repeatable)
When something changes in the world that must be persisted — the player picks
up an item, an NPC is defeated, a quest advances — propose the change here.

<state_change action="append" path="inventory" value="Rusted Key" />
<state_change action="set" path="quests.old_well.status" value="completed" />

## npc_request (optional, repeatable)
When an NPC interaction is complex enough that the NPC should speak and act
for itself, request an NPC subagent here.  The system will spawn the NPC,
run it in parallel with other NPCs, and return its dialogue and actions to
you.

<npc_request npc_id="tavern_keep" context="Asks about the well" />

Supported attributes:

- **npc_id** (required): Unique identifier for this NPC.
- **context** (required): What's happening that involves this NPC.
- **goal** (optional): What the NPC wants in this interaction.
- **personality** (optional): Brief personality description.
- **mood** (optional): Current emotional state.

## NPC Subagent Results

After NPC subagents have run, their responses will be provided to you as
structured blocks.  You may use, modify, or ignore these results as you
see fit — you are the final author of the narrative.

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
- When the player asks a DIRECT QUESTION about their character, equipment,
  surroundings, or NPCs, ANSWER IT directly before continuing the narrative.
- If a player asks about their inventory or equipment, use the character's
  actual inventory data to answer.
- Player questions are opportunities for world-building, not interruptions
  to ignore.
- Do not break character.  You are the DM — you speak with authority about the
  world, its inhabitants, and the consequences of the player's choices.
- If the player attempts something impossible, do not call a tool.  Describe
  why it fails and invite a different approach.
- If the player attempts something with uncertain stakes, call a tool.  Let
  the dice tell the story.

# OPENING SCENE VARIETY

The first turn of a new game is the player's opening scene.  You MUST vary
the starting scenario with every new game.  Do NOT default to a tavern or a
hooded figure approach.  Instead, choose from a wide range of openers:

- A winding road through a dark forest at dusk
- The entrance to a damp dungeon, iron door ajar
- A bustling village square at market dawn
- A foggy graveyard on a hillside
- The deck of a ship approaching a strange harbour
- A mountain pass with snowflakes swirling
- A ruined temple half-swallowed by jungle
- The edge of a vast, echoing cavern
- A riverside camp beneath ancient willows
- A cobblestone alley in a rain-soaked city
- A desert road with ruins shimmering on the horizon
- A cliffside path overlooking a stormy sea

Each session should begin in a distinct location and situation.  Use the
table tool (table_name="encounters") for inspiration if you need it, but
weave the result into a unique opening narrative.  Never reuse the same
opening scene across different games.

If the player asks "Where am I?" or "What do I see?" in their first turn,
respond with a rich, varied opening scene that matches none of your previous
openings.
- Do not let players trivialise the game by asking to do things their
  character could never accomplish.  A level 1 character is a fledgling
  adventurer, not a legendary hero.

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
- Let the player set the pace.  Respond to their curiosity.  If they want to
  explore the market, generate market details.  If they want to hear rumors,
  have NPCs share rumors.  Only advance the main thread when the player pursues
  it.
- Do NOT rush the player into a quest.  Let them explore, talk to NPCs, examine
  rooms, read books, and visit shops.  The world is meant to be explored, not
  speedrun.
- When the player enters a new area, describe it richly and list visible
  points of interest (shops, NPCs, landmarks, environmental details) the
  player can interact with.
- Give the player room to breathe.  Not every scene needs to advance a plot.
  Some of the best moments happen when nothing "important" is happening.

# MONEY AND SHOPPING

- Money is tracked as gold pieces (GP). The player can earn gold through
  quests, loot, and rewards.
- When the player visits a shop, present items with prices in GP and let
  them choose what to buy.
- Track gold via state_change: <state_change action="set" path="gold"
  value="50" />
- When the player buys something, deduct gold and add the item:
  <state_change action="set" path="gold" value="30" />
  <state_change action="append" path="inventory" value="Potion of Healing" />
- When the player loots gold: <state_change action="add" path="gold"
  value="20" />
- If the player tries to buy something they cannot afford, describe the
  merchant refusing and let them negotiate or find another way.
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
        npc_provider: LLMProvider | None = None,
        summarizer_provider: LLMProvider | None = None,
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
        npc_provider : LLMProvider or None
            Provider for NPC subagents.  Falls back to *llm_provider* if
            not specified.
        summarizer_provider : LLMProvider or None
            Provider for memory summarization.  Falls back to *llm_provider*
            if not specified.
        """
        self.llm_provider = llm_provider
        self.npc_provider = llm_provider if npc_provider is None else npc_provider
        self.summarizer_provider = (
            llm_provider if summarizer_provider is None else summarizer_provider
        )
        self.world_state = world_state

        # Accept both Character objects and plain dicts (from JSON).
        # Convert dicts to Character objects so downstream code can use
        # attribute access (e.g. character.character_class).
        if isinstance(character, dict):
            character = Character.from_dict(character)
        self.character = character
        self.turn_count: int = 0
        self._retried_parse: bool = False
        self.token_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.history: SessionHistory = SessionHistory(max_turns=5)
        self.npcs: dict[str, dict[str, str]] = {}

    def _build_context(
        self,
        player_input: str,
        plausibility_note: str | None = None,
    ) -> list[dict[str, str]]:
        """Build the message list for the LLM call.

        Constructs a conversation context starting with the DM system prompt,
        followed by the current world state summary, character summary, and
        the player's latest input.

        Parameters
        ----------
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
        messages: list[dict[str, str]] = [
            {"role": "system", "content": DM_SYSTEM_PROMPT},
        ]

        # Auto-classify if no note was provided and we have a character
        if plausibility_note is None and self.character is not None:
            classification = classify_action(self.character, player_input)
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

            # If the game is already in progress, tell the LLM not to generate
            # an opening scene (since it has no conversation history, it would
            # otherwise treat every request as the first turn)
            if self.world_state.turn_count > 0:
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
        if self.character is not None:
            # Build ability scores string
            abilities = getattr(self.character, "abilities", {})
            abilities_str = ", ".join(f"{k}={v}" for k, v in sorted(abilities.items()))
            # Build skills string
            skills = getattr(self.character, "skills", [])
            skills_str = ", ".join(skills) if skills else "none"
            # Build inventory string
            inventory = getattr(self.character, "inventory", [])
            inventory_str = ", ".join(inventory) if inventory else "empty"
            # Gold
            gold = getattr(self.character, "gold", 0)

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
                        f"  Abilities: {abilities_str}\n"
                        f"  Skills: {skills_str}\n"
                        f"  XP: {self.character.xp}\n"
                        f"  Gold: {gold} GP\n"
                        f"  Inventory: {inventory_str}\n"
                    ),
                }
            )

        # Append compressed summary if available
        summary_text = self.history.get_summary()
        if summary_text:
            messages.append(
                {
                    "role": "system",
                    "content": f"Session summary (previous events):\n{summary_text}",
                }
            )

        # Append conversation history (last few exchanges for context)
        for msg in self.history.get_context_messages():
            messages.append(msg)

        # Add the player's input
        messages.append({"role": "user", "content": player_input})

        total_chars = sum(len(m.get("content", "")) for m in messages)
        logger.debug(
            "_build_context: %d messages, ~%d chars", len(messages), total_chars
        )
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
        self._retried_parse = False
        logger.debug(
            "process_turn[%d]: input='%s' (len=%d)",
            self.turn_count,
            player_input[:80],
            len(player_input),
        )

        # ------------------------------------------------------------------
        # 0. Plausibility check — short-circuit impossible actions
        # ------------------------------------------------------------------
        plausibility_note: str | None = None
        if self.character is not None:
            classification = classify_action(self.character, player_input)
            category = classification.get("category", "plausible")

            if category == "impossible":
                narrative = self._build_impossible_narrative(
                    classification, player_input
                )
                self.history.add_turn(player_input, narrative)
                return {
                    "narrative": narrative,
                    "state_changes": [],
                    "tool_results": [],
                    "turn_count": self.turn_count,
                    "token_usage": dict(self.token_usage),
                    "ok": True,
                    "error": None,
                    "warnings": ["Action classified as impossible"],
                }

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

        # ------------------------------------------------------------------
        # 1. Build context and call LLM
        # ------------------------------------------------------------------
        messages = self._build_context(player_input, plausibility_note)

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
        npc_requests = parsed.get("npc_requests", [])

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
        # 4. Spawn NPC subagents
        # ------------------------------------------------------------------
        npc_results: list[dict[str, Any]] = []
        if npc_requests:
            npc_results = self._spawn_npcs(npc_requests, player_input)

        # Sync NPC data to world state for persistence across save/load
        self._sync_npcs_to_world_state()

        # ------------------------------------------------------------------
        # 5. Second LLM call — inject tool results and/or NPC results
        # ------------------------------------------------------------------
        need_second_call = bool(tool_requests) or bool(npc_results)
        _raw_final_response: str = first_response
        if need_second_call:
            messages.append(
                {
                    "role": "assistant",
                    "content": first_response,
                }
            )

            context_parts: list[str] = []

            if tool_results:
                tool_summary = self._format_tool_results(tool_results)
                context_parts.append(f"Tool results:\n{tool_summary}")

            if npc_results:
                npc_block = self._format_npc_results(npc_results)
                context_parts.append(
                    f"NPC interactions produced the following results:\n\n"
                    f"{npc_block}\n\n"
                    f"You may use, modify, or ignore these NPC responses "
                    f"as you see fit.  Weave them into the narrative."
                )

            context_parts.append(
                "Now continue the narrative, weaving these results into "
                "the story.  Include the final narrative and any necessary "
                "state_change tags."
            )

            messages.append(
                {
                    "role": "user",
                    "content": "\n\n".join(context_parts),
                }
            )

            try:
                second_response = self._call_llm(messages)
                _raw_final_response = second_response
            except Exception:
                logger.exception("Second LLM call failed")
                # Fall back to the first response's narrative
                second_response = first_response

            try:
                final_parsed = parse_dm_response(second_response)
            except Exception:
                final_parsed = parsed
        else:
            # No tools or NPC results — use the first response directly
            final_parsed = parsed

        narrative = final_parsed.get("narrative", "")
        state_changes = final_parsed.get("state_changes", [])

        # ------------------------------------------------------------------
        # 4a. Empty narrative retry — if the LLM omitted <narrative> tags
        # ------------------------------------------------------------------
        if not narrative and not self._retried_parse:
            raw: str = _raw_final_response
            logger.warning(
                "process_turn[%d]: empty narrative detected (first 500 chars): %s",
                self.turn_count,
                raw[:500],
            )
            self._retried_parse = True
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was missing the required "
                        "<narrative> tag. You MUST include a <narrative> "
                        "tag pair with your story text. Please respond again "
                        "with proper <narrative> tags."
                    ),
                }
            )
            try:
                retry_response = self._call_llm(messages)
                retry_parsed = parse_dm_response(retry_response)
                retry_narrative = retry_parsed.get("narrative", "")
                if retry_narrative:
                    narrative = retry_narrative
                    state_changes = retry_parsed.get("state_changes", state_changes)
                else:
                    logger.warning(
                        "process_turn[%d]: retry also produced empty "
                        "narrative, using fallback",
                        self.turn_count,
                    )
                    narrative = "[The narrative continues...]"
            except Exception:
                logger.exception(
                    "process_turn[%d]: narrative retry LLM call failed",
                    self.turn_count,
                )
                narrative = "[The narrative continues...]"

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

        # Check if summarization should trigger
        self._maybe_summarize()

        logger.debug(
            "Token usage after turn: prompt=%s, completion=%s, total=%s",
            self.token_usage["prompt_tokens"],
            self.token_usage["completion_tokens"],
            self.token_usage["total_tokens"],
        )

        logger.debug(
            "process_turn[%d]: final narrative — %d chars (first 200: %s...)",
            self.turn_count,
            len(narrative),
            narrative[:200],
        )

        return {
            "narrative": narrative,
            "state_changes": applied_changes,
            "tool_results": tool_results,
            "turn_count": self.turn_count,
            "token_usage": dict(self.token_usage),
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
        provider errors.  Accumulates token usage from the response
        into ``self.token_usage``.

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

        logger.debug(
            "_call_llm: response received — %d chars (first 200: %s...)",
            len(content),
            content[:200],
        )

        # Accumulate token usage
        usage = response.get("usage")
        if usage and isinstance(usage, dict):
            try:
                self.token_usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
                self.token_usage["completion_tokens"] += int(
                    usage.get("completion_tokens", 0)
                )
                self.token_usage["total_tokens"] += int(usage.get("total_tokens", 0))
            except (ValueError, TypeError):
                logger.warning("Invalid token usage data: %s", usage)

        return content

    def _format_tool_results(self, tool_results: list[dict[str, Any]]) -> str:
        """Format tool results into a readable summary for the LLM.

        Delegates to the module-level :func:`format_tool_results`.
        """
        return format_tool_results(tool_results)

    # ------------------------------------------------------------------
    # NPC spawning
    # ------------------------------------------------------------------

    def _spawn_npcs(
        self,
        npc_requests: list[dict[str, str]],
        player_input: str,
    ) -> list[dict[str, Any]]:
        """Spawn NPC agents for each request and collect results.

        Uses ``ThreadPoolExecutor`` to run NPCs in parallel (max 3
        workers).  Each NPC gets a 15-second timeout.  Graceful
        degradation: if an NPC times out or fails, an error entry is
        included instead.

        Parameters
        ----------
        npc_requests : list[dict]
            List of NPC request dicts with at minimum ``npc_id`` and
            ``context`` keys.
        player_input : str
            The player's input to pass to each NPC.

        Returns
        -------
        list[dict]
            List of NPC result dicts, each with ``npc_id``,
            ``dialogue``, ``action``, ``emotional_state``,
            ``tool_request``, and optional ``error``.
        """
        if not npc_requests:
            return []

        logger.debug("_spawn_npcs: %d NPC request(s) received", len(npc_requests))
        n_results: list[dict[str, Any]] = []

        def _run_one(req: dict[str, str]) -> dict[str, Any]:
            npc_id = req.get("npc_id", "unknown")

            # Look up or store NPC identity
            if npc_id not in self.npcs:
                self.npcs[npc_id] = {
                    "identity": req.get("identity", npc_id),
                    "personality": req.get("personality", ""),
                }
            known = self.npcs[npc_id]

            agent = NPCAgent(
                llm_provider=self.npc_provider,
                npc_id=npc_id,
                identity=known.get("identity", npc_id),
                personality=req.get("personality", known.get("personality", "")),
                mood=req.get("mood", "neutral"),
                scene_summary=req.get("context", ""),
                goal=req.get("goal", ""),
            )

            raw = agent.process(player_input)
            return {
                "npc_id": npc_id,
                "dialogue": raw.get("dialogue", ""),
                "action": raw.get("action", ""),
                "emotional_state": raw.get("emotional_state", ""),
                "tool_request": raw.get("tool_request"),
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            future_map: dict[
                concurrent.futures.Future[dict[str, Any]],
                str,
            ] = {}
            for req in npc_requests:
                fut = pool.submit(_run_one, req)
                future_map[fut] = req.get("npc_id", "unknown")

            for fut in concurrent.futures.as_completed(future_map):
                npc_id = future_map[fut]
                try:
                    result = fut.result(timeout=15)
                    n_results.append(result)
                except concurrent.futures.TimeoutError:
                    logger.warning("NPC '%s' timed out", npc_id)
                    n_results.append(
                        {
                            "npc_id": npc_id,
                            "error": "NPC timed out",
                            "dialogue": "",
                            "action": "",
                            "emotional_state": "",
                            "tool_request": None,
                        }
                    )
                except Exception:
                    logger.exception("NPC '%s' failed", npc_id)
                    n_results.append(
                        {
                            "npc_id": npc_id,
                            "error": "NPC processing failed",
                            "dialogue": "",
                            "action": "",
                            "emotional_state": "",
                            "tool_request": None,
                        }
                    )

        return n_results

    def _sync_npcs_to_world_state(self) -> None:
        """Sync in-memory NPC tracking (``self.npcs``) to
        ``WorldState.active_npcs`` for persistence.

        Called automatically after ``_spawn_npcs()`` each turn so that
        NPCs the player has interacted with survive save/load cycles.
        Each NPC entry includes a human-readable name, personality, and
        the turn number when it was first and last encountered.
        """
        if self.world_state is None:
            return
        for npc_id, npc_data in self.npcs.items():
            if npc_id not in self.world_state.active_npcs:
                self.world_state.active_npcs[npc_id] = {
                    "name": npc_data.get("identity", npc_id),
                    "personality": npc_data.get("personality", ""),
                    "first_seen_turn": self.turn_count,
                    "last_seen_turn": self.turn_count,
                }
            else:
                entry = self.world_state.active_npcs[npc_id]
                entry["last_seen_turn"] = self.turn_count
                # Merge personality if we now have richer data
                if npc_data.get("personality") and not entry.get("personality"):
                    entry["personality"] = npc_data["personality"]

    def _format_npc_results(
        self,
        npc_results: list[dict[str, Any]],
    ) -> str:
        """Format NPC results for injection into the second LLM call.

        Delegates to the module-level :func:`format_npc_results`.
        """
        return format_npc_results(npc_results)

    # ------------------------------------------------------------------
    # Plausibility — impossible action narrative
    # ------------------------------------------------------------------

    def _build_impossible_narrative(
        self,
        classification: dict[str, Any],
        player_input: str,
    ) -> str:
        """Build a flavorful auto-fail narrative for impossible actions.

        Parameters
        ----------
        classification : dict
            The result from :func:`~app.rules.plausibility.classify_action`
            with ``category``, ``reason``, and other keys.
        player_input : str
            The player's action text.

        Returns
        -------
        str
            A narrative explaining why the action cannot succeed.
        """
        reason = classification.get("reason", "It is beyond your capabilities.")

        return (
            f"You reach for something beyond your grasp. "
            f"{reason}\n\n"
            f"The world does not bend — not yet, not like this. "
            f"Perhaps a wiser course of action presents itself."
        )

    # ------------------------------------------------------------------
    # Memory summarization
    # ------------------------------------------------------------------

    def _maybe_summarize(self) -> None:
        """Check if summarization should trigger and run it if needed.

        Called after each completed turn.  When the recent turns buffer is
        full, compresses recent turns (along with any existing summary) into
        a new summary and clears the verbatim buffer.
        """
        recent_count = len(self.history.recent_turns)
        if recent_count < self.history.max_turns:
            return

        try:
            turns_text = self.history.get_turns_text()
            existing_summary = self.history.get_summary()
            if existing_summary:
                turns_text = (
                    f"Previous summary:\n{existing_summary}"
                    f"\n\nRecent turns:\n{turns_text}"
                )
            if turns_text:
                summary = summarize_turns(turns_text, self.summarizer_provider)
                self.history.set_summary(summary)
                self.history.clear_turns()
                logger.debug(
                    "_maybe_summarize: created compressed summary — "
                    "%d chars (was %d turns + existing summary)",
                    len(summary),
                    recent_count,
                )
        except Exception:
            logger.exception("Summarization failed after turn")
