"""Flask server for the LLM-Powered RPG.

Provides REST API endpoints for the game, starting with a health
check endpoint for LLM provider connectivity, plus save/load/reset
endpoints for persisting and restoring game state.
"""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify, request

from app.llm.ollama import OllamaProvider
from app.world.model import WorldState
from app.world.persistence import WorldStorage

app = Flask(__name__)
logger = logging.getLogger(__name__)
_storage = WorldStorage(data_dir=Path("data"))


@app.route("/api/health", methods=["POST"])
def health_check():
    """Check the health of an LLM provider.

    Accepts JSON body with ``base_url``, ``model``, and optional
    ``api_key``.  Creates an :class:`OllamaProvider` and calls its
    :meth:`~OllamaProvider.health` method.

    Returns
    -------
    JSON response with ``ok``, ``latency_ms``, ``model``, and
    ``error`` fields.

    Errors
    ------
    400
        If the request body is not valid JSON, or if ``base_url`` or
        ``model`` are missing or empty.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    base_url = data.get("base_url", "").strip()
    model = data.get("model", "").strip()

    if not base_url or not model:
        return jsonify({"ok": False, "error": "base_url and model are required"}), 400

    api_key = data.get("api_key")

    provider = OllamaProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
    )

    result = provider.health()

    return jsonify(
        {
            "ok": result.ok,
            "latency_ms": result.latency_ms,
            "model": result.model,
            "error": result.error,
        }
    )


# ---------------------------------------------------------------------------
# Save / Load / Reset
# ---------------------------------------------------------------------------


@app.route("/api/save", methods=["POST"])
def save_game():
    """Persist the current world state to disk.

    Accepts JSON body with a ``state`` dict (the serialised
    :class:`~app.world.model.WorldState`) and an optional ``name``
    (defaults to ``"autosave"``).

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
        return jsonify({"ok": False, "error": "Missing 'state' in request body"}), 400

    name = data.get("name", "autosave")
    state_dict = data["state"]

    try:
        world_state = WorldState.from_dict(state_dict)
        timestamp = _storage.save(world_state, name)
    except Exception:
        logger.exception("Failed to save game '%s'", name)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "name": name, "timestamp": timestamp})


@app.route("/api/saves", methods=["GET"])
def list_saves():
    """Return metadata for all saved games.

    Returns
    -------
    JSON with ``ok`` and a ``saves`` list of metadata dicts.
    """
    saves = _storage.list_saves()
    return jsonify({"ok": True, "saves": saves})


@app.route("/api/load/<string:name>", methods=["POST"])
def load_game(name):
    """Restore a previously saved world state.

    Returns
    -------
    JSON with ``ok`` and the full ``state`` dict on success.

    Errors
    ------
    404
        If no save with the given *name* exists.
    400
        If the save file is corrupt or unreadable.
    """
    try:
        world_state = _storage.load(name)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": f"Save '{name}' not found"}), 404
    except ValueError:
        logger.warning("Invalid or corrupt save data for '%s'", name, exc_info=True)
        return jsonify({"ok": False, "error": "Invalid or corrupt save data"}), 400
    except Exception:
        logger.exception("Failed to load save '%s'", name)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "state": world_state.to_dict()})


@app.route("/api/reset", methods=["POST"])
def reset_game():
    """Return a fresh default world state without touching disk.

    Returns
    -------
    JSON with ``ok`` and a fresh ``state`` dict.
    """
    fresh_state = WorldState()
    return jsonify({"ok": True, "state": fresh_state.to_dict()})
