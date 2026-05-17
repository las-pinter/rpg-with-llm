"""
NPC Agent Module — ephemeral agent for single-turn NPC interactions.

Each NPC agent lives only for one interaction with the player.  It receives
its identity, personality, mood, scene summary, and goal, then produces a
structured response (dialogue, action, emotional state) and optionally
requests a tool call (e.g., a dice roll).

Caveman compression is applied to agent-to-agent communication to reduce
token usage.  The compression strips articles, filler words, hedging, and
pleasantries while preserving proper nouns, numbers, and technical details.
"""

from __future__ import annotations

import json
import logging
import re
import string
from typing import Any

from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caveman Compression — word/phrase removal sets
# ---------------------------------------------------------------------------

# Articles — always removed
_ARTICLES = {"a", "an", "the"}

# Filler words — add no meaning
_FILLERS = {"well", "so", "basically", "actually", "just", "very", "really"}

# Hedging words — weaken statements
_HEDGING = {"perhaps", "maybe"}

# Multi-word hedging phrases (removed before word-level sweep)
_HEDGING_PHRASES: list[str] = [
    r"\bsort of\b",
    r"\bkind of\b",
]

# Hedging verb phrases (removed before word-level sweep)
_HEDGE_PHRASES_RE: list[tuple[str, str]] = [
    (r"\bI think\b", ""),
    (r"\bI believe\b", ""),
    (r"\bIt seems that\b", ""),
]

# Pleasantries (removed from start/end of text)
_PLEASANTRIES = ["please", "thank you", "you're welcome", "greetings"]

# Ultra-level: prepositions
_PREPOSITIONS = {
    "in",
    "on",
    "at",
    "for",
    "to",
    "of",
    "with",
    "by",
    "from",
    "about",
    "between",
    "through",
    "during",
    "without",
    "within",
    "across",
    "around",
    "into",
    "over",
    "under",
    "upon",
}

# Ultra-level: conjunctions
_CONJUNCTIONS = {
    "and",
    "but",
    "or",
    "nor",
    "yet",
    "so",
    "for",
    "because",
    "although",
    "while",
    "since",
    "unless",
    "if",
    "when",
    "as",
}

# Ultra-level: helping verbs
_HELPING_VERBS = {
    "am",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "can",
    "could",
    "shall",
    "should",
    "may",
    "might",
    "must",
}

# Combined stop-word sets per compression level
_FULL_STOP_WORDS = _ARTICLES | _FILLERS | _HEDGING
_ULTRA_STOP_WORDS = _FULL_STOP_WORDS | _PREPOSITIONS | _CONJUNCTIONS | _HELPING_VERBS

# ---------------------------------------------------------------------------
# Caveman Compression — public functions
# ---------------------------------------------------------------------------


def compress_text(text: str, level: str = "full") -> str:
    """Compress text using Caveman-style rules.

    Removes articles, filler words, hedging, pleasantries, and (at
    "ultra" level) prepositions, conjunctions, and helping verbs.
    Preserves proper nouns (capitalised words), numbers, and all
    technical/mechanical information.

    Parameters
    ----------
    text : str
        Input text to compress.
    level : str
        Compression level: "full" (default) or "ultra".

    Returns
    -------
    str
        Compressed text with filler removed.
    """
    if not text or not isinstance(text, str):
        return ""

    result = text.strip()

    # --- Phase 1: Remove multi-word hedging phrases ---
    for pattern in _HEDGING_PHRASES:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)

    for pattern, replacement in _HEDGE_PHRASES_RE:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    result = re.sub(r"\s+", " ", result).strip()

    # --- Phase 2: Remove pleasantries at boundaries ---
    for pleasantry in _PLEASANTRIES:
        # Leading
        result = re.sub(
            r"^" + re.escape(pleasantry) + r"\s*,?\s*",
            "",
            result,
            flags=re.IGNORECASE,
        )
        # Trailing
        result = re.sub(
            r"\s*,?\s*" + re.escape(pleasantry) + r"\.?\s*$",
            "",
            result,
            flags=re.IGNORECASE,
        )

    # --- Phase 3: Word-level removal ---
    stop_words = _ULTRA_STOP_WORDS if level == "ultra" else _FULL_STOP_WORDS
    words = result.split()
    filtered: list[str] = []

    for i, word in enumerate(words):
        # Preserve numbers (any word containing a digit)
        if any(c.isdigit() for c in word):
            filtered.append(word)
            continue

        # Detect if this word starts a new sentence
        is_start = i == 0
        if i > 0 and words[i - 1]:
            is_start = words[i - 1][-1] in ".!?"

        # Preserve proper nouns (capitalised, not at sentence start)
        if not is_start and word[0].isupper() and word.isalpha():
            filtered.append(word)
            continue

        # Strip punctuation for stop-word comparison
        clean = word.strip(string.punctuation)
        if not clean:
            filtered.append(word)
            continue

        if clean.lower() in stop_words:
            continue  # drop this word entirely

        filtered.append(word)

    result = " ".join(filtered)

    # --- Phase 4: Cleanup ---
    result = re.sub(r"\s+", " ", result).strip()
    result = re.sub(r"\s+([.,!?;:])", r"\1", result)

    return result


def decompress_hint(text: str) -> str:
    """Add minimal readability back for logging/debugging.

    Not intended for player-facing use — just makes compressed text
    slightly more readable in logs.  Adds sentence-ending punctuation
    and capitalises the first letter.

    Parameters
    ----------
    text : str
        Compressed text to lightly polish.

    Returns
    -------
    str
        Text with basic readability improvements.
    """
    if not text or not isinstance(text, str):
        return ""

    result = text.strip()

    # Ensure sentences end with punctuation
    if result and result[-1] not in ".!?":
        result += "."

    # Capitalise first letter
    if result and result[0].islower():
        result = result[0].upper() + result[1:]

    return result


# ---------------------------------------------------------------------------
# NPC System Prompt
# ---------------------------------------------------------------------------

NPC_SYSTEM_PROMPT: str = """
# ROLE

You are an inhabitant of a dark fantasy world responding to a traveller who
has approached you.  You are not the Dungeon Master — you are a character
within the story.  You speak and act from your own knowledge, personality,
and desires.

# CORE RULES

- Respond in character at all times.  You know only what your character
  would know — you have no awareness of game mechanics, dice rolls, or
  the DM's narrative plans.
- Your personality, mood, and goals are given to you in each interaction.
  Let them shape how you respond.
- You may ask questions, make offers, demand payment, share information
  (or withhold it), and react emotionally to the player.
- You do not control the world or other NPCs.  You control only yourself.
- You may request a dice roll if you need to resolve uncertainty about
  your own actions.  For example, if you want to sneak a look at
  something or attempt a difficult task.

# AVAILABLE TOOLS

When you need to resolve uncertainty about your own actions, you can
request a tool call.

## dice
Roll dice using standard tabletop notation.  Use for any randomness
that affects what you are trying to do.
Example: <tool_request name="dice" params='{"formula":"d20"}' />

# OUTPUT FORMAT

Your response must use XML-style tags so the system can parse it.

## dialogue (required)
What your character says to the player.  Write this as spoken dialogue.

<dialogue>
"What brings you to my shop, traveller?"
</dialogue>

## action (required)
What your character physically does while speaking.  Describe body
language, movements, or adjustments.

<action>
The merchant eyes you warily, one hand resting near a hidden dagger.
</action>

## emotional_state (required)
A brief description of your character's current emotional state.

<emotional_state>
cautious, curious
</emotional_state>

## tool_request (optional)
If you need to resolve uncertainty, request a tool call here.

<tool_request name="dice" params='{"formula":"d20"}' />

# CONSTRAINTS

- Never break character.  You are a person in this world, not a narrator.
- Never mention game mechanics, dice, or tools outside of a tool_request
  tag.
- Never speak for the player or the Dungeon Master.  You control only
  your own character.
- Keep responses concise and in-character.  A few sentences of dialogue
  and a brief action description are sufficient.
- React naturally to what the player says and does.
"""


# ---------------------------------------------------------------------------
# NPC Response Parser
# ---------------------------------------------------------------------------

_NPC_DIALOGUE_RE = re.compile(
    r"<dialogue>\s*(.*?)\s*</dialogue>", re.DOTALL | re.IGNORECASE
)

_NPC_ACTION_RE = re.compile(r"<action>\s*(.*?)\s*</action>", re.DOTALL | re.IGNORECASE)

_NPC_EMOTION_RE = re.compile(
    r"<emotional_state>\s*(.*?)\s*</emotional_state>",
    re.DOTALL | re.IGNORECASE,
)

_NPC_TOOL_RE = re.compile(r"<tool_request\s+([^>]+?)\s*/>", re.DOTALL | re.IGNORECASE)

# Regex to extract key="value" or key='value' attribute pairs.
_ATTR_PAIR_RE = re.compile(
    r"""(\w+)\s*=\s*"""
    r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""",
    re.VERBOSE,
)


def _default_npc_result() -> dict[str, Any]:
    """Return a default empty NPC parse result."""
    return {
        "dialogue": "",
        "action": "",
        "emotional_state": "",
        "tool_request": None,
    }


def parse_npc_response(text: str) -> dict[str, Any]:
    """Parse NPC structured response into component parts.

    Extracts dialogue, action, emotional_state, and optional tool_request
    from the NPC LLM's XML-style output.

    Parameters
    ----------
    text : str
        The raw text output from the NPC language model.

    Returns
    -------
    dict[str, Any]
        A dictionary with keys:

        - **dialogue** (str): What the NPC says.
        - **action** (str): What the NPC does.
        - **emotional_state** (str): Current mood/emotion.
        - **tool_request** (dict | None): Optional tool request with
          ``name`` and ``params``, or None if absent.
    """
    if not text or not isinstance(text, str):
        return _default_npc_result()

    dialogue = _extract_npc_dialogue(text)
    action = _extract_npc_action(text)
    emotional_state = _extract_npc_emotional_state(text)
    tool_request = _extract_npc_tool_request(text)

    return {
        "dialogue": dialogue,
        "action": action,
        "emotional_state": emotional_state,
        "tool_request": tool_request,
    }


def _extract_npc_dialogue(text: str) -> str:
    """Extract content from the first ``<dialogue>`` tag pair."""
    match = _NPC_DIALOGUE_RE.search(text)
    if match:
        return match.group(1).strip()
    return ""


def _extract_npc_action(text: str) -> str:
    """Extract content from the first ``<action>`` tag pair."""
    match = _NPC_ACTION_RE.search(text)
    if match:
        return match.group(1).strip()
    return ""


def _extract_npc_emotional_state(text: str) -> str:
    """Extract content from the first ``<emotional_state>`` tag pair."""
    match = _NPC_EMOTION_RE.search(text)
    if match:
        return match.group(1).strip()
    return ""


def _extract_npc_tool_request(text: str) -> dict[str, Any] | None:
    """Extract the first ``<tool_request>`` tag, if present.

    Returns a dict with ``name`` and ``params`` keys, or None if no
    tool request tag is found.
    """
    match = _NPC_TOOL_RE.search(text)
    if not match:
        return None

    attr_text = match.group(1)
    attrs = _parse_npc_attributes(attr_text)
    name = attrs.get("name", "")
    if not name:
        return None

    params_raw = attrs.get("params", "{}")
    if isinstance(params_raw, str):
        try:
            params: dict[str, Any] = json.loads(params_raw)
        except (json.JSONDecodeError, ValueError):
            params = {}
    else:
        params = {}

    return {"name": name, "params": params}


def _parse_npc_attributes(attr_text: str) -> dict[str, str]:
    """Parse key=\"value\" attribute pairs from a raw attribute string.

    Supports both double-quoted and single-quoted values.  Returns a
    dict mapping attribute names to their string values.  Malformed
    pairs are silently ignored.
    """
    attrs: dict[str, str] = {}
    for match in _ATTR_PAIR_RE.finditer(attr_text):
        name = match.group(1)
        raw_value = match.group(2)
        # Strip surrounding quotes
        value = raw_value[1:-1]
        attrs[name] = value
    return attrs


# ---------------------------------------------------------------------------
# NPCAgent
# ---------------------------------------------------------------------------

_NPC_CANNED_DIALOGUE = "..."
_NPC_CANNED_ACTION = "The NPC waits for your response."
_NPC_CANNED_EMOTION = "neutral"

_CANNED_XML = (
    "<dialogue>\n...\n</dialogue>\n"
    "<action>\nThe NPC waits for your response.\n</action>\n"
    "<emotional_state>\nneutral\n</emotional_state>"
)


class NPCAgent:
    """An ephemeral NPC agent spawned for a single turn.

    Each NPC agent lives only for one interaction.  It receives its
    identity, personality, mood, scene summary, and goal, then produces
    a structured response (dialogue, action, emotional state) and
    optionally requests a tool call.

    Parameters
    ----------
    llm_provider : LLMProvider or None
        The LLM provider used to generate responses.  If None, returns
        a canned response (useful for testing).
    npc_id : str
        Unique identifier for this NPC.
    identity : str
        Who they are, e.g. "Elara, the tavern keeper".
    personality : str
        Personality traits, e.g. "warm but shrewd".
    mood : str
        Current mood, e.g. "curious", "suspicious".
    scene_summary : str
        Brief scene context from the DM.
    goal : str
        What the NPC wants in this scene.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        npc_id: str,
        identity: str,
        personality: str,
        mood: str,
        scene_summary: str,
        goal: str,
    ) -> None:
        self.llm_provider = llm_provider
        self.npc_id = npc_id
        self.identity = identity
        self.personality = personality
        self.mood = mood
        self.scene_summary = scene_summary
        self.goal = goal

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_context(self, player_input: str) -> list[dict[str, str]]:
        """Build the message list for the LLM call.

        Constructs a conversation context with the NPC system prompt,
        NPC identity/background, and the player's input.

        Parameters
        ----------
        player_input : str
            What the player said or did to this NPC.

        Returns
        -------
        list[dict[str, str]]
            Messages in OpenAI chat format.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": NPC_SYSTEM_PROMPT},
        ]

        # NPC context block
        context_lines = [
            f"Your identity: {self.identity}",
            f"Your personality: {self.personality}",
            f"Your current mood: {self.mood}",
            f"Scene context: {self.scene_summary}",
            f"Your goal in this scene: {self.goal}",
            "",
            "Respond as this character to the player's input below.",
        ]
        messages.append({"role": "system", "content": "\n".join(context_lines)})

        # Player's input to the NPC
        messages.append({"role": "user", "content": player_input})

        return messages

    def _canned_response(self) -> dict[str, Any]:
        """Return a canned response when no LLM is available."""
        return {
            "dialogue": _NPC_CANNED_DIALOGUE,
            "action": _NPC_CANNED_ACTION,
            "emotional_state": _NPC_CANNED_EMOTION,
            "tool_request": None,
            "raw_response": "",
        }

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Call the LLM provider and return the response text.

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
            return _CANNED_XML

        try:
            response = self.llm_provider.call(messages)
        except Exception:
            logger.warning("NPC LLM call failed, retrying once")
            try:
                response = self.llm_provider.call(messages)
            except Exception as e:
                raise RuntimeError(f"NPC LLM call failed after retry: {e}") from e

        content = response.get("content", "")
        if not content:
            raise RuntimeError("NPC LLM returned empty content")

        return content

    def _compress_output(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """Apply Caveman compression to NPC output fields.

        Compresses dialogue, action, and emotional_state at the "full"
        level to reduce token usage in agent-to-agent communication.
        """
        result = dict(parsed)
        if result.get("dialogue"):
            result["dialogue"] = compress_text(result["dialogue"], level="full")
        if result.get("action"):
            result["action"] = compress_text(result["action"], level="full")
        if result.get("emotional_state"):
            result["emotional_state"] = compress_text(
                result["emotional_state"], level="full"
            )
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, player_input: str) -> dict[str, Any]:
        """Generate the NPC's response to the player.

        The full process:

        1. Build context from NPC identity, scene, and player input.
        2. Call the LLM provider.
        3. Parse the structured XML response.
        4. If parsing fails, retry once with a correction prompt.
        5. If retry also fails, return a canned response.
        6. Apply Caveman compression to dialogue/action/emotion.

        Parameters
        ----------
        player_input : str
            What the player said or did to this NPC.

        Returns
        -------
        dict[str, Any]
            Structured response with keys:

            - **dialogue** (str): What the NPC says.
            - **action** (str): What the NPC does.
            - **emotional_state** (str): Current mood after response.
            - **tool_request** (dict | None): Optional tool request
              with ``name`` and ``params``, or None.
            - **raw_response** (str): Full raw LLM text (for debugging).
        """
        if not player_input or not isinstance(player_input, str):
            return self._canned_response()

        # Build context
        messages = self._build_context(player_input)

        # Call LLM
        try:
            raw_response = self._call_llm(messages)
        except Exception:
            logger.exception("NPC LLM call failed")
            return self._canned_response()

        # Parse response — first attempt
        try:
            parsed = parse_npc_response(raw_response)
            result = self._compress_output(parsed)
            result["raw_response"] = raw_response
            return result
        except Exception as e:
            logger.warning("NPC parse failed, retrying: %s", e)

        # Retry with a correction prompt
        messages.append({"role": "assistant", "content": raw_response})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Please format your response correctly using XML-style "
                    "tags: <dialogue>, <action>, <emotional_state>."
                ),
            }
        )

        try:
            raw_response2 = self._call_llm(messages)
            parsed2 = parse_npc_response(raw_response2)
            result2 = self._compress_output(parsed2)
            result2["raw_response"] = raw_response2
            return result2
        except Exception:
            logger.exception("NPC retry parse also failed")
            canned = self._canned_response()
            canned["raw_response"] = raw_response
            return canned
