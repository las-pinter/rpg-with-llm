"""
Entity Persistence Layer — Phase 1, Task 1.2.

Provides ``EntityStorage``, which persists entity records (NPCs, places,
items) as JSON files organised in a subdirectory tree under
``{data_dir}/entities/``.  All writes are atomic via ``atomic_write()``
from ``app.utils.atomic_write``, preventing partial/corrupt files.

Directory structure::

    {data_dir}/entities/
        npcs/{entity_id}.json
        places/{entity_id}.json
        items/{entity_id}.json
        changelog.json          — list of EntityChangeLog dicts
        index.json              — quick lookup: entity_id → {type, path}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agents.record_keeper_schemas import EntityChangeLog
from app.utils.atomic_write import atomic_write

# ---------------------------------------------------------------------------
# Mapping from entity type → subdirectory name
# ---------------------------------------------------------------------------
_ENTITY_DIR_MAP: dict[str, str] = {
    "npc": "npcs",
    "place": "places",
    "item": "items",
}

_VALID_TYPES = frozenset(_ENTITY_DIR_MAP)

# ---------------------------------------------------------------------------
# Index filename
# ---------------------------------------------------------------------------
_INDEX_FILE = "index.json"
_CHANGELOG_FILE = "changelog.json"


class EntityStorage:
    """Persist, retrieve, and search entity records as JSON files on disk.

    All writes go through :func:`atomic_write` so partial writes never
    leave behind corrupt files.  An in-memory index (``index.json``) is
    maintained for fast lookups; if it becomes corrupt or is missing, it
    is rebuilt automatically by scanning the entity directories.
    """

    def __init__(self, data_dir: Path) -> None:
        """Prepare storage rooted at *data_dir*.

        Parameters
        ----------
        data_dir : Path
            Root folder for the save (e.g. ``data/saves/{slug}``).
            The ``entities/`` subdirectory tree will be created on first
            write and does not need to exist at construction time.
        """
        self.data_dir = Path(data_dir)
        self.entities_dir = self.data_dir / "entities"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        """Read and return the entity dict for *entity_id*.

        Parameters
        ----------
        entity_type : str
            One of ``"npc"``, ``"place"``, ``"item"``.
        entity_id : str
            The unique identifier of the entity.

        Returns
        -------
        dict | None
            The entity data as a dictionary, or ``None`` if the entity
            does not exist or the *entity_type* is unknown.
        """
        path = self._entity_path(entity_type, entity_id)
        if path is None or not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data: Any = json.load(f)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    def save_entity(self, entity_type: str, entity: dict[str, Any]) -> None:
        """Atomically write *entity* to disk.

        The entity dict **must** contain an ``"entity_id"`` key — it is
        used to derive the filename.  Creates the required subdirectory
        tree if it does not yet exist, and updates the lookup index.

        Parameters
        ----------
        entity_type : str
            One of ``"npc"``, ``"place"``, ``"item"``.
        entity : dict
            The entity data.  Must include an ``entity_id`` field.

        Raises
        ------
        ValueError
            If *entity_type* is unknown or *entity* has no ``entity_id``.
        """
        self._validate_type(entity_type)
        entity_id = entity.get("entity_id")
        if not entity_id:
            raise ValueError("Entity dict must contain an 'entity_id' key")

        # Ensure the target directory exists
        self._ensure_dirs(entity_type)

        path = self._entity_path(entity_type, entity_id)
        # path is guaranteed non-None after _validate_type
        assert path is not None

        atomic_write(path, entity, indent=2)

        # Update the index
        self._update_index(
            entity_id,
            {"type": entity_type, "path": str(path.relative_to(self.entities_dir))},
        )

    def delete_entity(self, entity_type: str, entity_id: str) -> None:
        """Remove the entity file for *entity_id* and update the index.

        If the file does not exist, the method completes silently
        (idempotent delete).  The index entry is always removed.

        Parameters
        ----------
        entity_type : str
            One of ``"npc"``, ``"place"``, ``"item"``.
        entity_id : str
            The unique identifier of the entity to remove.
        """
        path = self._entity_path(entity_type, entity_id)
        if path is not None and path.exists():
            path.unlink(missing_ok=True)

        # Always clean up the index, even if the file was already gone
        self._remove_from_index(entity_id)

    def list_entities(self, entity_type: str | None = None) -> list[dict[str, Any]]:
        """Return all entity dicts, optionally filtered by type.

        Parameters
        ----------
        entity_type : str or None
            If provided, only entities of this type are returned
            (``"npc"``, ``"place"``, ``"item"``).

        Returns
        -------
        list[dict]
            A list of entity dictionaries.  Returns an empty list when
            the directory does not exist or contains no files.
        """
        # If a specific type was requested, only scan that subdirectory
        if entity_type is not None:
            self._validate_type(entity_type)
            return self._list_from_dir(self._entity_dir(entity_type))

        # Otherwise scan all known type directories
        results: list[dict[str, Any]] = []
        for etype in _VALID_TYPES:
            results.extend(self._list_from_dir(self._entity_dir(etype)))
        return results

    def search_entities(self, query: str) -> list[dict[str, Any]]:
        """Simple case-insensitive substring search across all entities.

        Matches against ``entity_id``, ``name``, and ``description``
        fields.  Returns every entity that contains *query* as a
        substring of any of those fields.

        Parameters
        ----------
        query : str
            The substring to search for (case-insensitive).

        Returns
        -------
        list[dict]
            Matching entity dictionaries.  Returns an empty list if
            the storage is empty or no matches are found.
        """
        if not query:
            return []

        q = query.lower()
        matches: list[dict[str, Any]] = []
        for entity in self.list_entities():
            # Check entity_id
            if q in (entity.get("entity_id") or "").lower():
                matches.append(entity)
                continue
            # Check name
            if q in (entity.get("name") or "").lower():
                matches.append(entity)
                continue
            # Check description
            if q in (entity.get("description") or "").lower():
                matches.append(entity)
                continue
        return matches

    def log_change(self, change: EntityChangeLog) -> None:
        """Append a change entry to the changelog.

        Parameters
        ----------
        change : EntityChangeLog
            The change event to record.  Converted to a dict via
            :meth:`EntityChangeLog.to_dict`.
        """
        changelog = self._load_changelog()
        changelog.append(change.to_dict())
        self._save_changelog(changelog)

    def get_recent_changes(self, turns_back: int = 5) -> list[dict[str, Any]]:
        """Return changelog entries from the most recent *turns_back* turns.

        Determines the highest turn number in the changelog, then
        returns every entry whose ``turn`` is greater than or equal to
        ``(max_turn - turns_back)``.

        Parameters
        ----------
        turns_back : int
            How many turns to look back from the most recent entry.

        Returns
        -------
        list[dict]
            Matching changelog entries (newest first within each turn).
            Returns an empty list if the changelog is empty.
        """
        changelog = self._load_changelog()
        if not changelog:
            return []

        max_turn = max(entry["turn"] for entry in changelog)
        threshold = max_turn - turns_back

        return [entry for entry in changelog if entry["turn"] >= threshold]

    # ------------------------------------------------------------------
    # Internal helpers — directory & path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_type(entity_type: str) -> None:
        """Raise ``ValueError`` if *entity_type* is not recognised."""
        if entity_type not in _VALID_TYPES:
            valid = ", ".join(sorted(_VALID_TYPES))
            raise ValueError(
                f"Unknown entity type '{entity_type}'. Valid types: {valid}"
            )

    def _entity_dir(self, entity_type: str) -> Path:
        """Return the subdirectory for a given entity type."""
        return self.entities_dir / _ENTITY_DIR_MAP[entity_type]

    def _entity_path(self, entity_type: str, entity_id: str) -> Path | None:
        """Return the full path for an entity file, or ``None`` for unknown type."""
        if entity_type not in _VALID_TYPES:
            return None
        return self._entity_dir(entity_type) / f"{entity_id}.json"

    def _ensure_dirs(self, entity_type: str) -> None:
        """Create the subdirectory tree for *entity_type*, if needed."""
        self._entity_dir(entity_type).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers — reading entity files
    # ------------------------------------------------------------------

    @staticmethod
    def _list_from_dir(directory: Path) -> list[dict[str, Any]]:
        """Return all valid entity dicts found as ``*.json`` in *directory*.

        Non-dict JSON files and unreadable files are silently skipped.
        """
        if not directory.is_dir():
            return []

        entities: list[dict[str, Any]] = []
        for child in sorted(directory.iterdir()):
            if child.suffix != ".json":
                continue
            try:
                with open(child, encoding="utf-8") as f:
                    data: Any = json.load(f)
                if isinstance(data, dict):
                    entities.append(data)
            except (json.JSONDecodeError, OSError):
                # Skip corrupt / unreadable files
                continue
        return entities

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def _index_path(self) -> Path:
        """Return the path to ``index.json``."""
        return self.entities_dir / _INDEX_FILE

    def _load_index(self) -> dict[str, Any]:
        """Load the entity index from disk.

        If the file is missing or corrupt, the index is rebuilt by
        scanning the entity directories.
        """
        path = self._index_path()
        if not path.exists():
            return self._rebuild_index()

        try:
            with open(path, encoding="utf-8") as f:
                index: Any = json.load(f)
            if isinstance(index, dict):
                return index
        except (json.JSONDecodeError, OSError):
            pass

        # Corrupt or unexpected format — rebuild
        return self._rebuild_index()

    def _save_index(self, index: dict[str, Any]) -> None:
        """Atomically write the index to disk."""
        # Ensure the entities directory exists before writing the index
        self.entities_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(self._index_path(), index, indent=2)

    def _rebuild_index(self) -> dict[str, Any]:
        """Scan all entity directories and rebuild ``index.json``.

        Returns the newly built index dict and persists it to disk.
        """
        index: dict[str, Any] = {}
        for entity_type in _VALID_TYPES:
            directory = self._entity_dir(entity_type)
            if not directory.is_dir():
                continue
            for child in directory.iterdir():
                if child.suffix != ".json":
                    continue
                entity_id = child.stem
                index[entity_id] = {
                    "type": entity_type,
                    "path": str(child.relative_to(self.entities_dir)),
                }
        self._save_index(index)
        return index

    def _update_index(self, entity_id: str, entry: dict[str, Any]) -> None:
        """Insert or update *entity_id* in the index."""
        index = self._load_index()
        index[entity_id] = entry
        self._save_index(index)

    def _remove_from_index(self, entity_id: str) -> None:
        """Remove *entity_id* from the index, if present."""
        index = self._load_index()
        index.pop(entity_id, None)
        self._save_index(index)

    # ------------------------------------------------------------------
    # Changelog management
    # ------------------------------------------------------------------

    def _changelog_path(self) -> Path:
        """Return the path to ``changelog.json``."""
        return self.entities_dir / _CHANGELOG_FILE

    def _load_changelog(self) -> list[dict[str, Any]]:
        """Load the changelog from disk, returning an empty list on failure."""
        path = self._changelog_path()
        if not path.exists():
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data: Any = json.load(f)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_changelog(self, changelog: list[dict[str, Any]]) -> None:
        """Atomically write the changelog to disk."""
        self.entities_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(self._changelog_path(), changelog, indent=2)
