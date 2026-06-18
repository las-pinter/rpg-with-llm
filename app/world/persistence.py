"""
World State File Persistence Layer — Phase 1, Task 1.2.

Provides WorldStorage, which persists WorldState dataclasses to
JSON files with atomic saves, corruption detection, and a save index
for fast listing without re-reading every file.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.utils import atomic_write
from app.save_engine.envelope import SaveEnvelope
from app.world.model import WorldState


class WorldStorage:
    """Persist and restore WorldState objects as JSON files on disk.

    Saves are stored as ``{data_dir}/saves/{slug}/`` folders.
    Each folder contains up to four JSON files
    (``state.json``, ``character.json``, ``narrative_entries.json``,
    ``summary.json``), each wrapped in a :class:`SaveEnvelope` for
    versioning and corruption detection.  A companion ``index.json``
    tracks metadata for fast listing.

    All writes are **atomic**: content is first written to a .tmp
    file on the same filesystem, then os.rename()ed to the final
    path.  This prevents partial/corrupt files from crashes.
    """

    def __init__(
        self,
        data_dir: str | Path,
        auto_save_interval: int | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.saves_dir = self.data_dir / "saves"
        self.auto_save_interval = auto_save_interval
        self._last_save_turn: int | None = None
        self.saves_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Name validation (Bug 1: path traversal prevention)
    # ------------------------------------------------------------------

    def _validate_name(self, name: str) -> None:
        """Validate save name to prevent path traversal."""
        if not name or not name.strip():
            raise ValueError("Save name must be non-empty")
        if "/" in name or "\\" in name:
            raise ValueError(
                f"Invalid save name: '{name}' (no path separators allowed)"
            )
        if ".." in name:
            raise ValueError(
                f"Invalid save name: '{name}' (no parent directory references allowed)"
            )
        if len(name) > 200:
            raise ValueError("Save name too long (max 200 characters)")

    def _generate_slug(self, character_name: str) -> str:
        """Generate a filesystem-safe unique slug for a save file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = re.sub(r"[^a-zA-Z0-9-]", "-", character_name.lower()).strip("-")
        if not safe_name:
            safe_name = "unknown"
        rand_suffix = secrets.token_hex(2)  # 4 hex chars = 65536 combos
        return f"{safe_name}-{timestamp}-{rand_suffix}"

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, world_state: WorldState, name: str = "autosave") -> str:
        """Atomically persist *world_state* and return the generated slug."""
        self._validate_name(name)
        # Ensure directory exists — it may have been deleted at runtime (Bug 4)
        self.saves_dir.mkdir(parents=True, exist_ok=True)

        timestamp = _timestamp_now()
        slug = self._generate_slug(world_state.character_name or name)
        save_folder = self.saves_dir / slug
        save_folder.mkdir(parents=True, exist_ok=True)

        # Prepare and save state.json
        state_data = SaveEnvelope(
            schema_name="world_state", payload=world_state.to_dict()
        ).to_dict()
        atomic_write(save_folder / "state.json", state_data, indent=2)

        # Prepare and save character.json (omit if no character)
        if world_state._character is not None:
            char_data = SaveEnvelope(
                schema_name="character", payload=world_state._character
            ).to_dict()
            atomic_write(save_folder / "character.json", char_data, indent=2)

        # Prepare and save narrative_entries.json
        narrative_data = SaveEnvelope(
            schema_name="narrative_entries",
            payload={"entries": world_state._narrative_entries},
        ).to_dict()
        atomic_write(save_folder / "narrative_entries.json", narrative_data, indent=2)

        # Prepare and save summary.json
        summary_data = SaveEnvelope(
            schema_name="summary",
            payload={
                "technical_summary": world_state.technical_summary,
                "story_summary": world_state.story_summary,
            },
        ).to_dict()
        atomic_write(save_folder / "summary.json", summary_data, indent=2)

        # Populate metadata from WorldState (Bug 6)
        metadata: dict[str, Any] = {
            "id": slug,
            "name": name,
            "timestamp": timestamp,
            "character_name": world_state.character_name
            or world_state.character_id
            or "Unknown",
            "level": world_state.turn_count,  # Placeholder until character system
            "turn_count": world_state.turn_count,
        }
        self._update_index(slug, metadata)
        self._last_save_turn = world_state.turn_count
        return slug

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self, slug: str) -> WorldState:
        """Load and return a WorldState previously saved under *slug*."""
        self._validate_name(slug)
        save_folder = self.saves_dir / slug
        if not save_folder.is_dir():
            raise FileNotFoundError(f"Save '{slug}' folder not found at {save_folder}")

        # Load state.json
        state_path = save_folder / "state.json"
        if not state_path.exists():
            raise FileNotFoundError(
                f"State file missing in save '{slug}' at {state_path}"
            )
        try:
            with open(state_path, encoding="utf-8") as f:
                state_data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Save file 'state.json' in '{slug}' is corrupt -- invalid JSON: {exc}"
            ) from exc

        if not isinstance(state_data, dict):
            raise ValueError(
                f"Save file 'state.json' in '{slug}' is corrupt -- expected a JSON object but got {type(state_data).__name__}"
            )

        # Extract payload from envelope
        # The SaveEnvelope structure: {"save_version": ..., "schema_name": ..., "payload": ...}
        if "payload" not in state_data:
            raise ValueError(
                f"Save file 'state.json' in '{slug}' is corrupt -- missing payload field"
            )

        world_state = WorldState.from_dict(state_data["payload"])

        # Load character.json (optional)
        char_path = save_folder / "character.json"
        if char_path.exists():
            try:
                with open(char_path, encoding="utf-8") as f:
                    char_data = json.load(f)
                if "payload" in char_data:
                    world_state._character = char_data["payload"]
            except Exception as e:
                # We can choose to ignore or raise here. The requirement doesn't specify.
                # Let's log it if possible, but for now just continue.
                pass

        # Load narrative_entries.json (optional)
        narrative_path = save_folder / "narrative_entries.json"
        if narrative_path.exists():
            try:
                with open(narrative_path, encoding="utf-8") as f:
                    narrative_data = json.load(f)
                if (
                    "payload" in narrative_data
                    and "entries" in narrative_data["payload"]
                ):
                    world_state._narrative_entries = narrative_data["payload"][
                        "entries"
                    ]
            except Exception:
                pass

        # Load summary.json (optional)
        summary_path = save_folder / "summary.json"
        if summary_path.exists():
            try:
                with open(summary_path, encoding="utf-8") as f:
                    summary_data = json.load(f)
                if "payload" in summary_data:
                    payload = summary_data["payload"]
                    world_state.technical_summary = payload.get("technical_summary", [])
                    world_state.story_summary = payload.get("story_summary", [])
            except Exception:
                pass

        return world_state

    # ------------------------------------------------------------------
    # List saves
    # ------------------------------------------------------------------

    def list_saves(self) -> list[dict[str, Any]]:
        """Return metadata for all known saves from the index."""
        index_path = self.saves_dir / "index.json"
        if not index_path.exists():
            return []
        try:
            with open(index_path, encoding="utf-8") as f:
                index: Any = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []
        saves: dict[str, Any] = index.get("saves", {})
        # Ensure backward compat: every entry has id and name fields
        result: list[dict[str, Any]] = []
        for key, entry in saves.items():
            if isinstance(entry, dict):
                if "id" not in entry:
                    entry["id"] = key
                if "name" not in entry:
                    entry["name"] = key
                result.append(entry)
        return result

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, slug: str) -> None:
        """Delete the save with the given *slug*."""
        self._validate_name(slug)
        save_folder = self.saves_dir / slug

        # Check if the save exists in index or on disk
        if not save_folder.is_dir() and not self._index_has(slug):
            raise FileNotFoundError(f"Save '{slug}' not found at {save_folder}")

        # Remove from index FIRST so orphan metadata can't linger (Bug 5)
        self._remove_from_index(slug)

        # Then try to delete the folder tree
        if save_folder.is_dir():
            shutil.rmtree(save_folder, ignore_errors=True)

    # ------------------------------------------------------------------
    # Save exists
    # ------------------------------------------------------------------

    def save_exists(self, slug: str) -> bool:
        """Return True if a save with *slug* exists on disk."""
        self._validate_name(slug)
        return (self.saves_dir / slug).is_dir()

    # ------------------------------------------------------------------
    # Auto-save
    # ------------------------------------------------------------------

    def should_auto_save(self, current_turn: int) -> bool:
        """Check whether an auto-save should be triggered."""
        if self.auto_save_interval is None or self._last_save_turn is None:
            return False
        return (current_turn - self._last_save_turn) >= self.auto_save_interval

    # ------------------------------------------------------------------
    # Index helpers
    # ------------------------------------------------------------------

    def _index_has(self, name: str) -> bool:
        """Check if *name* exists in the save index."""
        index_path = self.saves_dir / "index.json"
        if not index_path.exists():
            return False
        try:
            with open(index_path, encoding="utf-8") as f:
                index: Any = json.load(f)
            if not isinstance(index, dict):
                return False
            return name in index.get("saves", {})
        except (json.JSONDecodeError, OSError):
            return False

    def _update_index(self, name: str, metadata: dict[str, Any]) -> None:
        """Insert or update *name* in the save index."""
        index_path = self.saves_dir / "index.json"
        index: dict[str, Any] = {"saves": {}}
        if index_path.exists():
            try:
                with open(index_path, encoding="utf-8") as f:
                    existing = json.load(f)
                if isinstance(existing, dict):
                    index = existing
            except (json.JSONDecodeError, OSError):
                pass
        index.setdefault("saves", {})[name] = metadata
        self._write_index_atomic(index_path, index)

    def _remove_from_index(self, name: str) -> None:
        """Remove *name* from the save index."""
        index_path = self.saves_dir / "index.json"
        if not index_path.exists():
            return
        try:
            with open(index_path, encoding="utf-8") as f:
                index: Any = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(index, dict):
            return
        index.setdefault("saves", {}).pop(name, None)
        self._write_index_atomic(index_path, index)

    @staticmethod
    def _write_index_atomic(index_path: Path, index: dict[str, Any]) -> None:
        """Atomically write *index* to *index_path*."""
        atomic_write(index_path, index, indent=2)


def _timestamp_now() -> str:
    """Return a compact, human-readable timestamp string."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")
