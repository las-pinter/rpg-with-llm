"""
Character Creation and Persistence.

Provides CharacterStorage, which persists Character dataclasses to
JSON files with atomic saves, corruption detection, and a save index
for fast listing without re-reading every file.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.character.model import Character


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
            raise FileNotFoundError(
                f"Character '{name}' not found at {final_path}"
            )
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
            raise FileNotFoundError(
                f"Character '{name}' not found at {char_path}"
            )

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
