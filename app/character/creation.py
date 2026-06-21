"""
Character Creation and Persistence.

Provides CharacterStorage, which persists Character dataclasses to
JSON files with atomic saves, corruption detection, and a save index
for fast listing without re-reading every file.

Also provides AssistedCreation, which uses an LLM to generate a
Character from the player's narrative answers to a few open-ended
questions.
"""

from __future__ import annotations

import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

from app.character.items import Item, ItemType
from app.character.model import (
    ASSISTED_CREATION_QUESTIONS,
    STANDARD_ABILITIES,
    VALID_CLASSES,
    Character,
    CharacterRecord,
)
from app.character.resources import ResourceData
from app.llm.base import LLMProvider
from app.utils import atomic_write

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CharacterGenerationError(Exception):
    """Raised when the LLM cannot produce a valid character from the
    player's answers, even after a retry."""


# ---------------------------------------------------------------------------
# Assisted Creation
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a Game Master and narrative storyteller for a fantasy RPG. Based on \
the player's narrative answers below, create a character with solid mechanics \
and a vivid, playable identity.

The 7 story answers (journal chapters) provided below describe the character's \
life journey. Use them as the primary source for the backstory and appearance \
fields in your JSON output — every detail in those fields should be rooted in \
what the player wrote.

--- MECHANICS ---
{CLASS_INSTRUCTION}
Assign ability scores (STR, DEX, CON, INT, WIS, CHA) between 3 and 18, with \
a reasonable distribution for the chosen class.
Pick 2-4 skills appropriate for the class and backstory.
Set HP, AC, and starting inventory appropriate for the class.

{NAME_INSTRUCTION}

--- ABILITY SCORES (USE THESE) ---
The player has chosen the following ability scores. Let these numbers shape
the character's appearance, backstory, and reputation. Extreme scores (3-5
or 16-18) should be prominently featured in the narrative:

STR={STR}, DEX={DEX}, CON={CON}, INT={INT}, WIS={WIS}, CHA={CHA}

If any ability is very high (16+), the character has an extraordinary
reputation related to that ability. If very low (5-), the character has
struggled with it and it shaped their life path. Moderate scores (8-14)
are unremarkable and need not be mentioned.

When writing the backstory, weave these stat-based details naturally:
- Very high STR: extraordinary physical feats, broad-shouldered build
- Very low STR: slight build, relied on wit over force
- Very high INT: intellectual achievements, memorized entire libraries
- Very low INT: reputation for foolishness, relies on instinct
- Very high CHA: magnetic bearing, people drawn to them, once calmed a riot
- Very low CHA: awkward or off-putting, people keep their distance
- Very high WIS: reads omens correctly, sensed danger before it arrived
- Very low WIS: missed obvious warnings, spiritually blind, stubborn denial

--- BACKSTORY (3-5 paragraphs, 300-500 words) ---
Weave the player's narrative answers into a cohesive backstory. Each journal \
chapter answer should contribute elements to the story. Include:
1. Upbringing & Origins — Where were they raised? Family? Social station?
2. Pivotal Event — The moment that changed everything and set them on the \
adventuring path. Keep it personal and grounded (no epic heroics at level 1).
3. Personality & Flaws — Core traits, a defining strength, and a meaningful \
weakness that complicates their decisions.
4. Goals & Motivation — What are they chasing? What do they hope to find \
(treasure, knowledge, redemption, revenge)?
5. Secret or Unresolved Thread — Something from their past that could surface \
later — a debt, a hidden identity, a promise unkept.

--- APPEARANCE (2-4 sentences, driven by story answers) ---
Describe their look vividly, basing it on details from the player's narrative \
answers:
- Build, height, notable physical features (scars, tattoos, eye color, etc.)
- Clothing and armor style
- Bearing or presence (stoic, fidgety, commanding, haunted)
- Any distinguishing marks or equipment visible at a glance

--- OUTPUT FORMAT ---
Return ONLY valid JSON — no explanation, no markdown formatting, no code fences:
{{
    "name": "",
    "character_class": "Fighter|Rogue|Mage|Cleric",
    "level": 1,
    "abilities": {{"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10}},
    "skills": ["Skill1", "Skill2"],
    "hp": 10,
    "max_hp": 10,
    "ac": 12,
    "appearance": "Vivid description grounded in the story answers.",
    "backstory": "Rich narrative drawn from the journal chapters (3-5 paragraphs).",
    "inventory": ["Item1", "Item2"]
}}"""

_CORRECTION_PROMPT = """\
The JSON you returned was invalid. Please return ONLY valid JSON — no \
explanation, no markdown, no code fences — in the exact format specified \
earlier. Use the player's original answers to generate the character."""


class AssistedCreation:
    """LLM-assisted character creation flow.

    The player answers 7 open-ended narrative questions, and the DM
    (an LLM call) generates a complete Character from those answers.
    """

    # Uses the canonical question list from model.py so the frontend
    # (served via /api/config/character-rules) and the LLM backend
    # always see the same questions.
    QUESTIONS: list[str] = ASSISTED_CREATION_QUESTIONS

    def __init__(self, llm_provider: LLMProvider) -> None:
        """Store the LLM provider used to generate characters.

        Parameters
        ----------
        llm_provider : LLMProvider
            An LLM provider instance for making generation calls.
        """
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_character(
        self,
        answers: dict[int, str],
        abilities: dict[str, int] | None = None,
        name: str | None = None,
        character_class: str | None = None,
    ) -> Character:
        """Send up to 7 narrative answers to the LLM and parse the response
        into a complete Character object.

        Parameters
        ----------
        answers : dict[int, str]
            Dictionary mapping question index (0-6) to the player's
            answer.  At least 3 answers must be provided.
        abilities : dict[str, int] | None
            Player-chosen ability scores (STR, DEX, CON, INT, WIS, CHA).
            When provided, the LLM will weave these into appearance
            and backstory.
        name : str | None
            Optional player-chosen name.  When provided and non-empty,
            the LLM is instructed to use it exactly.  When None or empty,
            the LLM generates a fitting name.
        character_class : str | None
            Optional player-chosen class.  When provided, the LLM is
            instructed to use this exact class.  When None or empty,
            the LLM chooses the most fitting class.

        Returns
        -------
        Character
            A fully populated Character generated from the player's
            answers.

        Raises
        ------
        ValueError
            If fewer than 3 answers are provided.
        CharacterGenerationError
            If the LLM response cannot be parsed after one retry.
        """
        if len(answers) < 3:
            raise ValueError(f"At least 3 answers are required, got {len(answers)}.")

        logger.debug(
            "generate_character: answers=%d, class=%s, name=%s, abilities=%s",
            len(answers),
            character_class,
            name,
            abilities is not None,
        )

        # Build the user message from answers
        user_parts: list[str] = []
        if abilities:
            user_parts.append(
                "--- PLAYER ABILITY SCORES ---\n"
                f"STR={abilities.get('STR', 10)}, DEX={abilities.get('DEX', 10)}, "
                f"CON={abilities.get('CON', 10)}, INT={abilities.get('INT', 10)}, "
                f"WIS={abilities.get('WIS', 10)}, CHA={abilities.get('CHA', 10)}\n"
            )
        user_parts.append("Here are the player's answers:\n")
        for idx in sorted(answers):
            user_parts.append(f"Q{idx + 1}: {answers[idx]}")
        user_message = "\n\n".join(user_parts)

        # Build name instruction
        name = name.strip() if name else ""
        if name:
            name_instruction = (
                "--- PLAYER NAME ---\n"
                f"The player has chosen the name: {name}\n"
                "You MUST use this exact name. Do not change it."
                f' The character\'s name field MUST be exactly "{name}".\n'
                "---"
            )
        else:
            name_instruction = (
                "--- NAME GENERATION ---\n"
                "Generate a fitting name for this character.\n"
                "---"
            )

        # Build class instruction
        if character_class:
            class_instruction = (
                f"The player has already chosen their class: {character_class}. "
                f"You MUST use this exact class. Do NOT change it."
            )
        else:
            class_instruction = (
                "Choose the most fitting class from: Fighter, Rogue, Mage, Cleric."
            )

        system_prompt = _SYSTEM_PROMPT.format(
            CLASS_INSTRUCTION=class_instruction,
            NAME_INSTRUCTION=name_instruction,
            STR=abilities.get("STR", 10) if abilities else 10,
            DEX=abilities.get("DEX", 10) if abilities else 10,
            CON=abilities.get("CON", 10) if abilities else 10,
            INT=abilities.get("INT", 10) if abilities else 10,
            WIS=abilities.get("WIS", 10) if abilities else 10,
            CHA=abilities.get("CHA", 10) if abilities else 10,
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # First attempt
        logger.debug(
            "LLM call attempt 1: messages=%d, total_chars=%d",
            len(messages),
            sum(len(m.get("content", "")) for m in messages),
        )
        raw = self._call_llm(messages)
        logger.debug(
            "LLM response (attempt 1): %d chars — %s...",
            len(raw),
            raw[:200].replace("\n", " "),
        )
        char = self._try_parse(raw, requested_class=character_class)

        if char is not None:
            logger.info(
                "Character generated (attempt 1): %s (%s, lvl %d)",
                char.name,
                char.character_class,
                char.level,
            )
            return char

        # Retry with correction prompt
        logger.warning(
            "Retry triggered: first attempt failed to produce valid character"
        )
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": _CORRECTION_PROMPT})
        raw2 = self._call_llm(messages)
        logger.debug(
            "LLM response (attempt 2): %d chars — %s...",
            len(raw2),
            raw2[:200].replace("\n", " "),
        )
        char2 = self._try_parse(raw2, requested_class=character_class)

        if char2 is not None:
            logger.info(
                "Character generated on retry: %s (%s, lvl %d)",
                char2.name,
                char2.character_class,
                char2.level,
            )
            return char2

        logger.error(
            "Character generation failed after 2 attempts. "
            "Last response (first 500): %s",
            raw2[:500].replace("\n", " "),
        )
        raise CharacterGenerationError(
            "Failed to generate a valid character after two attempts. "
            "The LLM response could not be parsed as valid character data."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Call the LLM and return the raw response text."""
        result = self._llm.call(messages)
        return result.get("content", "")

    def _try_parse(
        self, raw: str, requested_class: str | None = None
    ) -> Character | None:
        """Try to parse *raw* LLM output into a Character.

        Parameters
        ----------
        raw : str
            Raw LLM response text.
        requested_class : str | None
            The class the player actually chose.  When provided, the
            parsed ``character_class`` must match exactly.

        Returns
        -------
        Character | None
            ``None`` if parsing or validation fails.
        """
        data = self._extract_json(raw)
        if data is None:
            logger.debug("_try_parse: JSON extraction returned None")
            return None

        return self._validate_and_build(data, requested_class=requested_class)

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any] | None:
        """Extract and parse a JSON object from *raw* text.

        Tries to parse the raw text directly first.  If that fails,
        walks through *raw* character by character to find the first
        ``{...}`` block with balanced braces — this correctly handles
        nested objects and avoids the pitfalls of both greedy and
        non-greedy regex.  Returns ``None`` if no valid JSON object
        is found.
        """
        # Try direct parse first
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # Walk through raw to find the first balanced { ... } block
        start = raw.find("{")
        if start == -1:
            return None

        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(raw[start : i + 1])
                        if isinstance(data, dict):
                            return data
                    except json.JSONDecodeError:
                        # This block wasn't valid JSON; continue searching
                        # for the next balanced block (skip past this one)
                        start = raw.find("{", i + 1)
                        if start == -1:
                            return None
                        depth = 0

        return None

    @staticmethod
    def _validate_and_build(
        data: dict[str, Any], requested_class: str | None = None
    ) -> Character | None:
        """Validate parsed JSON data and build a Character.

        Parameters
        ----------
        data : dict[str, Any]
            Parsed JSON data from the LLM response.
        requested_class : str | None
            The class the player actually chose.  When provided, the
            returned ``character_class`` must match this exactly or the
            validation fails, preventing the LLM from ignoring the
            player's choice.

        Returns
        -------
        Character | None
            ``None`` if any validation check fails.
        """
        # Required fields
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            logger.debug("_validate_and_build: name is empty")
            return None

        char_class = data.get("character_class")
        if char_class not in VALID_CLASSES:
            logger.debug(
                "_validate_and_build: class '%s' not in VALID_CLASSES", char_class
            )
            return None

        # Ensure the LLM didn't ignore the player's chosen class
        if requested_class is not None and char_class != requested_class:
            logger.debug(
                "_validate_and_build: class mismatch — got '%s', expected '%s'",
                char_class,
                requested_class,
            )
            return None

        # Abilities
        abilities = data.get("abilities")
        if not isinstance(abilities, dict):
            return None
        for abil in STANDARD_ABILITIES:
            val = abilities.get(abil)
            if not isinstance(val, int) or val < 3 or val > 18:
                logger.debug(
                    "_validate_and_build: ability '%s' = %s (must be int 3-18)",
                    abil,
                    val,
                )
                return None

        # Numeric fields
        hp = data.get("hp")
        max_hp = data.get("max_hp")
        ac = data.get("ac")
        if (
            not isinstance(hp, int)
            or not isinstance(max_hp, int)
            or not isinstance(ac, int)
        ):
            logger.debug(
                "_validate_and_build: non-int field — hp=%s, max_hp=%s, ac=%s",
                type(hp).__name__,
                type(max_hp).__name__,
                type(ac).__name__,
            )
            return None

        # Skills & inventory (must be lists)
        skills = data.get("skills")
        inventory = data.get("inventory")
        if not isinstance(skills, list):
            skills = []
        if not isinstance(inventory, list):
            inventory = []

        appearance = data.get("appearance", "")
        backstory = data.get("backstory", "")

        try:
            return Character(
                name=name.strip(),
                character_class=char_class,
                level=data.get("level", 1),
                abilities=abilities,
                skills=skills,
                hp=hp,
                max_hp=max_hp,
                ac=ac,
                appearance=appearance if isinstance(appearance, str) else "",
                backstory=backstory if isinstance(backstory, str) else "",
                inventory=inventory,
            )
        except (ValueError, TypeError) as e:
            logger.debug(
                "_validate_and_build: constructor raised %s: %s", type(e).__name__, e
            )
            return None


def _convert_legacy_character(data: dict) -> dict:
    """Convert a legacy Character dict to CharacterRecord format.

    Maps:
    - hp/max_hp → resources.hp ResourceData
    - ac → dropped (computed by derivation pipeline)
    - inventory: list[str] → inventory: list[Item dicts] (as MISC items)
    - Adds equipped_items: [] (legacy didn't track this)

    This is a courtesy helper for dev testing with old save files.
    """
    converted = dict(data)

    # Remove legacy derived fields
    converted.pop("ac", None)
    hp = converted.pop("hp", 10)
    max_hp = converted.pop("max_hp", 10)

    # Convert inventory from list[str] to list[dict]
    old_inventory = converted.get("inventory", [])
    if old_inventory and isinstance(old_inventory[0], str):
        new_inventory = []
        for item_name in old_inventory:
            item = Item(name=item_name, item_type=ItemType.MISC, weight=0.0)
            new_inventory.append(item.to_dict())
        converted["inventory"] = new_inventory

    # Add equipped_items if missing
    if "equipped_items" not in converted:
        converted["equipped_items"] = []

    # Add resources with hp ResourceData
    if "resources" not in converted or not converted["resources"]:
        converted["resources"] = {"hp": ResourceData(value=hp, max=max_hp).to_dict()}

    return converted


class CharacterStorage:
    """Persist and restore Character objects as JSON files on disk.

    Saves are stored as {data_dir}/characters/{name}.json.  Each file
    contains the raw Character.to_dict() output — no wrapping envelope
    — so it can be handed directly to Character.from_dict().

    A companion index.json tracks metadata (timestamp, class, level)
    for every character, enabling fast listings without loading each
    file.

    All writes are **atomic**: content is first written to a .tmp file
    on the same filesystem, then os.rename()ed to the final path.
    This prevents partial/corrupt files from crashes.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.characters_dir = self.data_dir / "characters"
        self.characters_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Name validation
    # ------------------------------------------------------------------

    def _validate_name(self, name: str) -> None:
        """Validate character name to prevent path traversal."""
        if not name or not name.strip():
            raise ValueError("Character name must be non-empty")
        # Reject control characters (null bytes, backspace, etc.)
        for c in name:
            if ord(c) < 32 or ord(c) == 127:
                raise ValueError(
                    f"Invalid character name: '{name}' "
                    "(control characters are not allowed)"
                )
        if "/" in name or "\\" in name:
            raise ValueError(
                f"Invalid character name: '{name}' (no path separators allowed)"
            )
        if ".." in name:
            raise ValueError(
                f"Invalid character name: '{name}' "
                "(no parent directory references allowed)"
            )
        if len(name) > 200:
            raise ValueError("Character name too long (max 200 characters)")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(
        self, character: CharacterRecord | Character, name: str | None = None
    ) -> str:
        """Atomically persist *character* under the given *name*.

        If *name* is ``None``, the character's own ``.name`` field is
        used as the filename.  Returns the timestamp string of the save.
        """
        if name is None:
            name = character.name
        self._validate_name(name)

        # Ensure directory still exists (may have been deleted at runtime)
        self.characters_dir.mkdir(parents=True, exist_ok=True)

        timestamp = _timestamp_now()

        if isinstance(character, Character):
            warnings.warn(
                "Character is deprecated, use CharacterRecord instead",
                DeprecationWarning,
                stacklevel=2,
            )
            data = _convert_legacy_character(character.to_dict())
        else:
            data = character.to_dict()

        final_path = self.characters_dir / f"{name}.json"
        atomic_write(final_path, data, indent=2)

        metadata: dict[str, Any] = {
            "id": character.id,
            "name": name,
            "timestamp": timestamp,
            "class": character.character_class,
            "level": character.level,
        }
        self._update_index(name, metadata)
        return timestamp

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self, name: str) -> CharacterRecord:
        """Load and return a CharacterRecord previously saved under *name*.

        Raises
        ------
        FileNotFoundError
            If no character file exists for *name*.
        ValueError
            If the file exists but contains corrupt or invalid JSON, or if
            the file uses the legacy Character format.
        """
        self._validate_name(name)
        final_path = self.characters_dir / f"{name}.json"
        if not final_path.exists():
            raise FileNotFoundError(f"Character '{name}' not found at {final_path}")
        try:
            with open(final_path, encoding="utf-8") as f:
                data: Any = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Character file '{name}' is corrupt -- invalid JSON: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(
                f"Character file '{name}' is corrupt -- expected a JSON "
                f"object (dict) but got {type(data).__name__}"
            )

        # Detect legacy format (has flat hp/max_hp/ac fields)
        if "hp" in data or "max_hp" in data:
            raise ValueError(
                f"Character file {name!r} uses the legacy Character format. "
                "This format is no longer supported. "
                "Use _convert_legacy_character() to migrate old saves."
            )

        return CharacterRecord.from_dict(data)

    # ------------------------------------------------------------------
    # List characters
    # ------------------------------------------------------------------

    def list_characters(self) -> list[dict[str, Any]]:
        """Return metadata for all saved characters from the index.

        Each entry includes ``id``, ``name``, ``timestamp``, ``class``,
        and ``level``.  For backward compatibility with indexes that were
        written before the ``id`` field was added, the character's JSON
        file is loaded on demand to fill in the missing ``id``.
        """
        index_path = self.characters_dir / "index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, encoding="utf-8") as f:
                index: Any = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        characters: dict[str, Any] = index.get("characters", {})
        result: list[dict[str, Any]] = list(characters.values())

        # Backward compat — fill in missing 'id' fields from the
        # actual saved JSON files for characters saved before the
        # id field was added to the index metadata.
        for entry in result:
            if entry.get("id"):
                continue
            name = entry.get("name", "")
            if name:
                try:
                    char = self.load(name)
                    entry["id"] = char.id
                except (FileNotFoundError, ValueError):
                    entry["id"] = ""

        return result

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, name: str) -> None:
        """Delete the character save with the given *name*."""
        self._validate_name(name)
        char_path = self.characters_dir / f"{name}.json"

        # Check if the character exists in index or on disk
        if not char_path.exists() and not self._index_has(name):
            raise FileNotFoundError(f"Character '{name}' not found at {char_path}")

        # Remove from index FIRST so orphan metadata can't linger
        self._remove_from_index(name)

        # Then try to delete the file (may already be gone)
        try:
            char_path.unlink(missing_ok=True)
        except Exception:
            pass  # File might already be gone

    # ------------------------------------------------------------------
    # Load / Delete by ID
    # ------------------------------------------------------------------

    def load_by_id(self, char_id: str) -> CharacterRecord:
        """Load a character by its UUID ``id`` field.

        Scans all saved character JSON files until it finds one whose
        ``id`` matches *char_id*.  This is O(n) in the number of saved
        characters — acceptable for the small scale of this RPG.

        Raises
        ------
        FileNotFoundError
            If no character with *char_id* exists.
        ValueError
            If the matching file contains corrupt data, or if the file
            uses the legacy Character format.
        """
        if not char_id:
            raise ValueError("Character id must be non-empty")

        for file_path in self.characters_dir.glob("*.json"):
            if file_path.name == "index.json":
                continue
            try:
                with open(file_path, encoding="utf-8") as f:
                    data: Any = json.load(f)
                if isinstance(data, dict) and data.get("id") == char_id:
                    # Detect legacy format
                    if "hp" in data or "max_hp" in data:
                        raise ValueError(
                            f"Character file {file_path.name!r} uses the legacy "
                            "Character format. This format is no longer supported. "
                            "Use _convert_legacy_character() to migrate old saves."
                        )
                    return CharacterRecord.from_dict(data)
            except (json.JSONDecodeError, OSError):
                continue

        raise FileNotFoundError(f"Character with id '{char_id}' not found")

    def delete_by_id(self, char_id: str) -> None:
        """Delete a character by its UUID ``id`` field.

        Scans saved files to find the matching character, removes
        the file and cleans up the index.

        Raises
        ------
        FileNotFoundError
            If no character with *char_id* exists.
        """
        if not char_id:
            raise ValueError("Character id must be non-empty")

        for file_path in self.characters_dir.glob("*.json"):
            if file_path.name == "index.json":
                continue
            try:
                with open(file_path, encoding="utf-8") as f:
                    data: Any = json.load(f)
                if isinstance(data, dict) and data.get("id") == char_id:
                    name = data.get("name", "")
                    file_path.unlink(missing_ok=True)
                    self._remove_from_index(name)
                    return
            except (json.JSONDecodeError, OSError):
                continue

        raise FileNotFoundError(f"Character with id '{char_id}' not found")

    # ------------------------------------------------------------------
    # Character exists
    # ------------------------------------------------------------------

    def character_exists(self, name: str) -> bool:
        """Return ``True`` if a character with *name* exists (on disk and in index)."""
        self._validate_name(name)
        return (self.characters_dir / f"{name}.json").exists() and self._index_has(name)

    # ------------------------------------------------------------------
    # Index helpers
    # ------------------------------------------------------------------

    def _index_has(self, name: str) -> bool:
        """Check if *name* exists in the character index."""
        index_path = self.characters_dir / "index.json"
        if not index_path.exists():
            return False
        try:
            with open(index_path, encoding="utf-8") as f:
                index: Any = json.load(f)
            if not isinstance(index, dict):
                return False
            return name in index.get("characters", {})
        except (json.JSONDecodeError, OSError):
            return False

    def _update_index(self, name: str, metadata: dict[str, Any]) -> None:
        """Insert or update *name* in the character index."""
        index_path = self.characters_dir / "index.json"
        index: dict[str, Any] = {"characters": {}}
        if index_path.exists():
            try:
                with open(index_path, encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, dict):
                    index = existing
            except (json.JSONDecodeError, OSError):
                pass
        index.setdefault("characters", {})[name] = metadata
        self._write_index_atomic(index_path, index)

    def _remove_from_index(self, name: str) -> None:
        """Remove *name* from the character index."""
        index_path = self.characters_dir / "index.json"
        if not index_path.exists():
            return
        try:
            with open(index_path, encoding="utf-8") as f:
                index: Any = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(index, dict):
            return
        index.setdefault("characters", {}).pop(name, None)
        self._write_index_atomic(index_path, index)

    @staticmethod
    def _write_index_atomic(index_path: Path, index: dict[str, Any]) -> None:
        """Atomically write *index* to *index_path*."""
        atomic_write(index_path, index, indent=2)


def _timestamp_now() -> str:
    """Return a compact, human-readable timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
