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
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.character.model import (
    STANDARD_ABILITIES,
    VALID_CLASSES,
    Character,
)
from app.llm.base import LLMProvider

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
You are a Game Master for a fantasy RPG. Create a character based on the \
player's narrative answers below.

Choose the most fitting class from: Fighter, Rogue, Mage, Cleric.
Assign ability scores (STR, DEX, CON, INT, WIS, CHA) between 3 and 18, \
with a reasonable distribution for the chosen class.
Pick 2-4 skills appropriate for the class and backstory.
Set HP, AC, and starting inventory appropriate for the class.

If the player did not provide a name, generate one.

Return ONLY valid JSON — no explanation, no markdown formatting, no \
code fences — in this exact format:
{
    "name": "",
    "character_class": "Fighter|Rogue|Mage|Cleric",
    "level": 1,
    "abilities": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    "skills": ["Skill1", "Skill2"],
    "hp": 10,
    "max_hp": 10,
    "ac": 12,
    "appearance": "",
    "backstory": "",
    "inventory": ["Item1", "Item2"]
}"""

_CORRECTION_PROMPT = """\
The JSON you returned was invalid. Please return ONLY valid JSON — no \
explanation, no markdown, no code fences — in the exact format specified \
earlier. Use the player's original answers to generate the character."""


class AssistedCreation:
    """LLM-assisted character creation flow.

    The player answers 3-5 open-ended narrative questions, and the DM
    (an LLM call) generates a complete Character from those answers.
    """

    QUESTIONS: list[str] = [
        "Where do you come from, and what was your life before adventure found you?",
        "What event set you on the path of a hero — or a fool with a death wish?",
        "What is your greatest strength and your deepest flaw?",
        "What do you hope to find in the world — treasure, "
        "knowledge, redemption, or a good death?",
        "Tell me about a person you left behind and what they'd say about you now.",
    ]

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

    def generate_character(self, answers: dict[int, str]) -> Character:
        """Send 3-5 narrative answers to the LLM and parse the response
        into a complete Character object.

        Parameters
        ----------
        answers : dict[int, str]
            Dictionary mapping question index (0-4) to the player's
            answer.  At least 3 answers must be provided.

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

        # Build the user message from answers
        user_parts: list[str] = ["Here are the player's answers:\n"]
        for idx in sorted(answers):
            user_parts.append(f"Q{idx + 1}: {answers[idx]}")
        user_message = "\n".join(user_parts)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        # First attempt
        raw = self._call_llm(messages)
        char = self._try_parse(raw)

        if char is not None:
            return char

        # Retry with correction prompt
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": _CORRECTION_PROMPT})
        raw2 = self._call_llm(messages)
        char2 = self._try_parse(raw2)

        if char2 is not None:
            return char2

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

    def _try_parse(self, raw: str) -> Character | None:
        """Try to parse *raw* LLM output into a Character.

        Returns ``None`` if parsing or validation fails.
        """
        data = self._extract_json(raw)
        if data is None:
            return None

        return self._validate_and_build(data)

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
    def _validate_and_build(data: dict[str, Any]) -> Character | None:
        """Validate parsed JSON data and build a Character.

        Returns ``None`` if any validation check fails.
        """
        # Required fields
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return None

        char_class = data.get("character_class")
        if char_class not in VALID_CLASSES:
            return None

        # Abilities
        abilities = data.get("abilities")
        if not isinstance(abilities, dict):
            return None
        for abil in STANDARD_ABILITIES:
            val = abilities.get(abil)
            if not isinstance(val, int) or val < 3 or val > 18:
                return None

        # Numeric fields
        hp = data.get("hp")
        max_hp = data.get("max_hp")
        ac = data.get("ac")
        if not all(isinstance(v, int) for v in (hp, max_hp, ac)):
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
        except (ValueError, TypeError):
            return None


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

    def save(self, character: Character, name: str | None = None) -> str:
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
        data: dict[str, Any] = character.to_dict()

        tmp_path = self.characters_dir / f"{name}.json.tmp"
        final_path = self.characters_dir / f"{name}.json"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.rename(tmp_path, final_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        metadata: dict[str, Any] = {
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

    def load(self, name: str) -> Character:
        """Load and return a Character previously saved under *name*.

        Raises
        ------
        FileNotFoundError
            If no character file exists for *name*.
        ValueError
            If the file exists but contains corrupt or invalid JSON.
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
        return Character.from_dict(data)

    # ------------------------------------------------------------------
    # List characters
    # ------------------------------------------------------------------

    def list_characters(self) -> list[dict[str, Any]]:
        """Return metadata for all saved characters from the index."""
        index_path = self.characters_dir / "index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, encoding="utf-8") as f:
                index: Any = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        characters: dict[str, Any] = index.get("characters", {})
        return list(characters.values())

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
        tmp_path = index_path.with_name("index.json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            os.rename(tmp_path, index_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise


def _timestamp_now() -> str:
    """Return a compact, human-readable timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
