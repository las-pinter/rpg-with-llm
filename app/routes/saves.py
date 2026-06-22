"""Save / Load / Reset API routes.

Provides endpoints for persisting, restoring, and deleting game world
states and related data (character, narrative entries, summaries).
Uses SaveGameManager for envelope-wrapped, schema-validated I/O and
WorldStorage for index management and slug generation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import flask as flask
from flask import jsonify, request

from app.character.derived import compute_derived_sheet
from app.character.model import CharacterRecord
from app.save_engine.envelope import SaveEnvelope
from app.save_engine.manager import SaveGameManager
from app.utils import atomic_write
from app.world.model import WorldState
from app.world.persistence import WorldStorage

logger = logging.getLogger(__name__)

bp = flask.Blueprint("saves", __name__, url_prefix="/api")

_storage = WorldStorage(data_dir=Path("data"))
_save_manager = SaveGameManager(data_dir=Path("data"))
_save_manager.register_defaults()


@bp.route("/save", methods=["POST"])
def save_game() -> tuple[flask.Response, int] | flask.Response:
    """Persist the current game state (and optional character, narrative, summary) to disk.

    Accepts JSON body with a ``state`` dict (the serialised
    :class:`~app.world.model.WorldState`), an optional ``character``
    dict (the serialised :class:`~app.character.model.Character`),
    optional ``narrative_entries`` list, optional ``summary`` dict,
    and an optional ``name`` (defaults to an auto-generated name).

    Returns
    -------
    JSON with ``ok`` and ``slug`` on success.

    Errors
    ------
    400
        If the request body is not valid JSON, ``state`` is missing,
        or the save data fails schema validation.
    500
        If an unexpected internal error occurs.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    if "state" not in data:
        return (
            jsonify({"ok": False, "error": "Missing 'state' in request body"}),
            400,
        )

    name = data.get("name") or ""
    if not name or not name.strip():
        name = f"Adventure - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    state_dict = data["state"]
    if isinstance(state_dict, dict):
        # Shallow copy to avoid mutating the original request data (Bug 8)
        state_dict = state_dict.copy()

        # Extract character for backward compat: if _character is embedded
        # in state dict and no separate character field, lift it out
        character_dict = data.get("character")
        if character_dict is None and "_character" in state_dict:
            character_dict = state_dict.pop("_character")

        # Sync character_name / character_id to the world state if we have
        # separate character data (new-style saves)
        if character_dict is not None and isinstance(character_dict, dict):
            if character_dict.get("name"):
                state_dict["character_name"] = character_dict["name"]
            if character_dict.get("id"):
                state_dict["character_id"] = character_dict["id"]

        logger.debug(
            "Saving game '%s' with state keys: %s", name, list(state_dict.keys())
        )
    else:
        character_dict = None
        logger.debug(
            "Saving game '%s' with non-dict state: %s", name, type(state_dict).__name__
        )

    try:
        world_state = WorldState.from_dict(state_dict)

        # Generate slug via WorldStorage slug generator
        slug = _storage._generate_slug(name or "autosave")

        # Prepare buckets for SaveGameManager
        buckets_data: dict[str, object] = {
            "world_state": world_state,
        }

        if character_dict is not None and isinstance(character_dict, dict):
            buckets_data["character"] = CharacterRecord.from_dict(character_dict)

        narrative_entries = data.get("narrative_entries")
        if (
            narrative_entries is not None
            and isinstance(narrative_entries, list)
            and len(narrative_entries) > 0
        ):
            buckets_data["narrative_entries"] = {"entries": narrative_entries}

        summary = data.get("summary")
        if summary is not None and isinstance(summary, dict) and len(summary) > 0:
            buckets_data["summary"] = summary

        # Write envelope-wrapped, schema-validated files
        _save_manager.save(slug, buckets_data)

        # Update save index with metadata
        metadata = {
            "id": slug,
            "name": name,
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
            "character_name": world_state.character_name
            or world_state.character_id
            or "Unknown",
            "level": world_state.turn_count,
            "turn_count": world_state.turn_count,
        }
        _storage._update_index(slug, metadata)

        # Write story_summary.json for backward compat with the get_story
        # endpoint, which reads this file directly (Task 4.1)
        if world_state.story_summary:
            story_summary_data = SaveEnvelope(
                save_version="1.0.0",
                schema_name="story_summary",
                schema_version="1.0.0",
                payload={"entries": world_state.story_summary},
            ).to_dict()
            atomic_write(
                _storage.saves_dir / slug / "story_summary.json",
                story_summary_data,
                indent=2,
            )

        logger.debug("Game '%s' saved successfully with slug '%s'", name, slug)
    except ValueError as exc:
        logger.warning("Failed to save game '%s': %s", name, exc)
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception:
        logger.exception("Failed to save game '%s'", name)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "slug": slug})


@bp.route("/saves", methods=["GET"])
def list_saves() -> tuple[flask.Response, int] | flask.Response:
    """Return metadata for all saved games.

    Returns
    -------
    JSON with ``ok`` and a ``saves`` list of metadata dicts.
    """
    saves = _storage.list_saves()
    return jsonify({"ok": True, "saves": saves})


@bp.route("/load/<string:slug>", methods=["POST"])
def load_game(slug: str) -> tuple[flask.Response, int] | flask.Response:
    """Restore a previously saved game state.

    Returns
    -------
    JSON with ``ok``, the full ``state`` dict, and optional
    ``character`` dict on success.

    Errors
    ------
    404
        If no save with the given *slug* exists.
    400
        If the save data is corrupt or fails validation.
    500
        If an unexpected internal error occurs.
    """
    try:
        result = _save_manager.load(slug)
        world_state: WorldState | None = result.get("world_state")
        character: CharacterRecord | None = result.get("character")

        state_dict = world_state.to_dict() if world_state else {}

        char_dict: dict | None = None
        sheet_dict: dict | None = None
        if character is not None:
            char_dict = character.to_dict()
            try:
                sheet = compute_derived_sheet(character)
                sheet_dict = sheet.to_dict()
            except Exception:
                logger.warning(
                    "Failed to compute derived sheet for '%s'", slug, exc_info=True
                )

        logger.debug(
            "Loaded game '%s' — location=%s, turn=%d",
            slug,
            getattr(world_state, "current_location", "unknown"),
            getattr(world_state, "turn_count", 0),
        )
    except FileNotFoundError:
        return jsonify({"ok": False, "error": f"Save '{slug}' not found"}), 404
    except ValueError:
        logger.warning("Invalid or corrupt save data for '%s'", slug, exc_info=True)
        return (
            jsonify({"ok": False, "error": "Invalid or corrupt save data"}),
            400,
        )
    except Exception:
        logger.exception("Failed to load save '%s'", slug)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    response: dict[str, object] = {"ok": True, "state": state_dict}
    if char_dict is not None:
        response["character"] = char_dict
    if sheet_dict is not None:
        response["sheet"] = sheet_dict
    return jsonify(response)


@bp.route("/delete/<string:slug>", methods=["DELETE"])
def delete_save(slug: str) -> tuple[flask.Response, int] | flask.Response:
    """Delete a saved game by slug.

    Returns
    -------
    JSON with ``ok`` on success.

    Errors
    ------
    404
        If no save with the given *slug* exists.
    500
        If an internal error occurs.
    """
    try:
        _storage.delete(slug)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": f"Save '{slug}' not found"}), 404
    except Exception:
        logger.exception("Failed to delete save '%s'", slug)
        return (
            jsonify({"ok": False, "error": "Internal server error"}),
            500,
        )

    return jsonify({"ok": True})


@bp.route("/story/<string:slug>", methods=["GET"])
def get_story(slug: str) -> tuple[flask.Response, int] | flask.Response:
    """Return the condensed story summaries for a saved game.

    Parameters
    ----------
    slug : str
        The slug of the saved game (URL-decoded automatically by Flask).

    Returns
    -------
    JSON with ``ok`` and ``story`` (list of prose summary strings) on success.

    Errors
    ------
    404
        If no save with the given *slug* exists.
    """
    try:
        # Validate slug before reading
        _storage._validate_name(slug)
        story_path = _storage.saves_dir / slug / "story_summary.json"

        if not story_path.exists():
            # Fall back to loading from summary.json for old saves
            world_state = _storage.load(slug)
            return jsonify({"ok": True, "story": world_state.story_summary})

        with open(story_path, encoding="utf-8") as f:
            data = json.load(f)

        story = []
        if "payload" in data and "entries" in data["payload"]:
            story = [str(e) for e in data["payload"]["entries"] if isinstance(e, str)]

        return jsonify({"ok": True, "story": story})
    except (FileNotFoundError, ValueError):
        return jsonify({"ok": False, "error": "Save not found"}), 404


@bp.route("/reset", methods=["POST"])
def reset_game() -> tuple[flask.Response, int] | flask.Response:
    """Return a fresh default world state without touching disk.

    Returns
    -------
    JSON with ``ok`` and a fresh ``state`` dict.
    """
    fresh_state = WorldState()
    return jsonify({"ok": True, "state": fresh_state.to_dict()})
