"""
World State File Persistence Layer — Phase 3, Task 3.2.

Provides WorldStorage, which persists WorldState dataclasses to
JSON files with atomic saves, corruption detection, and a save index
for fast listing without re-reading every file.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from app.world.model import WorldState


class WorldStorage:
    """Persist and restore WorldState objects as JSON files on disk.

    Saves are stored as {data_dir}/saves/{name}.json.  Each file
    contains the raw WorldState.to_dict() output — no wrapping
    envelope — so it can be handed directly to WorldState.from_dict().

    A companion index.json tracks metadata (timestamp, character
    name, level, turn count) for every save, enabling fast listings
    without loading each file.

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

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, world_state: WorldState, name: str = "autosave") -> str:
        """Atomically persist *world_state* under the given *name*."""
        self._validate_name(name)
        # Ensure directory exists — it may have been deleted at runtime (Bug 4)
        self.saves_dir.mkdir(parents=True, exist_ok=True)

        timestamp = _timestamp_now()
        data: dict[str, Any] = world_state.to_dict()

        tmp_path = self.saves_dir / f"{name}.json.tmp"
        final_path = self.saves_dir / f"{name}.json"

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.rename(tmp_path, final_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        # Populate metadata from WorldState (Bug 6)
        metadata: dict[str, Any] = {
            "timestamp": timestamp,
            "character_name": world_state.character_id or "Unknown",
            "level": world_state.turn_count,  # Placeholder until character system
            "turn_count": world_state.turn_count,
        }
        self._update_index(name, metadata)
        self._last_save_turn = world_state.turn_count
        return timestamp

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self, name: str) -> WorldState:
        """Load and return a WorldState previously saved under *name*."""
        self._validate_name(name)
        final_path = self.saves_dir / f"{name}.json"
        if not final_path.exists():
            raise FileNotFoundError(f"Save '{name}' not found at {final_path}")
        try:
            with open(final_path, encoding="utf-8") as f:
                data: Any = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Save file '{name}' is corrupt -- invalid JSON: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(
                f"Save file '{name}' is corrupt -- expected a JSON object "
                f"(dict) but got {type(data).__name__}"
            )
        return WorldState.from_dict(data)

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
        return list(saves.values())

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, name: str) -> None:
        """Delete the save with the given *name*."""
        self._validate_name(name)
        save_path = self.saves_dir / f"{name}.json"

        # Check if the save exists in index or on disk
        if not save_path.exists() and not self._index_has(name):
            raise FileNotFoundError(f"Save '{name}' not found at {save_path}")

        # Remove from index FIRST so orphan metadata can't linger (Bug 5)
        self._remove_from_index(name)

        # Then try to delete the file (may already be gone)
        try:
            save_path.unlink(missing_ok=True)
        except Exception:
            pass  # File might already be gone

    # ------------------------------------------------------------------
    # Save exists
    # ------------------------------------------------------------------

    def save_exists(self, name: str) -> bool:
        """Return True if a save with *name* exists on disk."""
        self._validate_name(name)
        return (self.saves_dir / f"{name}.json").exists()

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
