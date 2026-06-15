"""Save / Load / Reset API routes.

Provides endpoints for persisting, restoring, and deleting game world
states.  Also includes legacy companion-character helpers for backward
compatibility with old save formats that used separate ``.char.json``
files.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import flask as flask
from flask import jsonify, request

from app.world.model import WorldState
from app.world.persistence import WorldStorage

logger = logging.getLogger(__name__)

bp = flask.Blueprint("saves", __name__, url_prefix="/api")

_storage = WorldStorage(data_dir=Path("data"))


@bp.route("/save", methods=["POST"])
def save_game() -> tuple[flask.Response, int] | flask.Response:
    """Persist the current world state (and optionally character) to disk.

    Accepts JSON body with a ``state`` dict (the serialised
    :class:`~app.world.model.WorldState`), an optional ``character``
    dict (the serialised :class:`~app.character.model.Character`),
    and an optional ``name`` (defaults to an auto-generated name).

    Returns
    -------
    JSON with ``ok``, ``name``, and ``timestamp`` on success.

    Errors
    ------
    400
        If the request body is not valid JSON, or ``state`` is missing.
    500
        If the persistence layer raises an error (e.g. invalid name,
        filesystem failure).
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
        from datetime import datetime

        name = f"Adventure - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    state_dict = data["state"]
    if isinstance(state_dict, dict):
        # Shallow copy to avoid mutating the original request data (Bug 8)
        state_dict = state_dict.copy()
        # Embed character data inside the state dict for single-file save
        char_data = data.get("character")
        if char_data and isinstance(char_data, dict):
            state_dict["_character"] = char_data
            state_dict["character_name"] = char_data.get("name", "")
        logger.debug(
            "Saving game '%s' with state keys: %s", name, list(state_dict.keys())
        )
    else:
        logger.debug(
            "Saving game '%s' with non-dict state: %s", name, type(state_dict).__name__
        )

    try:
        world_state = WorldState.from_dict(state_dict)
        slug = _storage.save(world_state, name)
        logger.debug("Game '%s' saved successfully with slug '%s'", name, slug)
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


def _load_companion_character(slug: str) -> dict | None:
    """Load companion character data for a save, or None.

    This is a backward-compatibility shim for old saves that used
    separate .char.json files. New saves embed character data directly
    in the world state file.
    """
    char_dir = (Path("data") / "saves").resolve()
    save_key = hashlib.sha256(slug.encode("utf-8")).hexdigest()
    char_path = (char_dir / f"{save_key}.char.json").resolve()
    try:
        char_path.relative_to(char_dir)
    except ValueError:
        return None
    if not char_path.exists():
        return None
    try:
        with open(char_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _delete_companion_character(slug: str) -> None:
    """Delete orphan companion character file for a save, if it exists."""
    char_dir = (Path("data") / "saves").resolve()
    save_key = hashlib.sha256(slug.encode("utf-8")).hexdigest()
    char_path = (char_dir / f"{save_key}.char.json").resolve()
    try:
        char_path.relative_to(char_dir)
    except ValueError:
        return
    try:
        char_path.unlink(missing_ok=True)
    except OSError:
        pass


@bp.route("/load/<string:slug>", methods=["POST"])
def load_game(slug: str) -> tuple[flask.Response, int] | flask.Response:
    """Restore a previously saved world state.

    Returns
    -------
    JSON with ``ok``, the full ``state`` dict, and optional
    ``character`` data on success.

    Errors
    ------
    404
        If no save with the given *slug* exists.
    400
        If the save file is corrupt or unreadable.
    """
    try:
        world_state = _storage.load(slug)
        logger.debug(
            "Loaded game '%s' — location=%s, turn=%d",
            slug,
            world_state.current_location,
            world_state.turn_count,
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

    # Extract character data from embedded _character field
    char_data = world_state._character
    if char_data is None:
        # Backward compat: try loading from old companion file
        char_data = _load_companion_character(slug)
    result: dict[str, object] = {"ok": True, "state": world_state.to_dict()}
    if char_data is not None:
        result["character"] = char_data
    return jsonify(result)


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

    # Clean up any orphan .char.json companion files (legacy format)
    _delete_companion_character(slug)

    return jsonify({"ok": True})


@bp.route("/story/<string:slug>", methods=["GET"])
def get_story(slug: str) -> tuple[flask.Response, int] | flask.Response:
    """Return the story log for a saved game.

    Parameters
    ----------
    slug : str
        The slug of the saved game (URL-decoded automatically by Flask).

    Returns
    -------
    JSON with ``ok`` and ``story`` (list of narrative strings) on success.

    Errors
    ------
    404
        If no save with the given *slug* exists.
    """
    try:
        world_state = _storage.load(slug)
        return jsonify({"ok": True, "story": world_state._narrative_entries})
    except FileNotFoundError:
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
