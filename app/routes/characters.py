"""Character API routes — creation, save, load, list, delete."""

from __future__ import annotations

import logging
from pathlib import Path

import flask as flask
from flask import jsonify, request

from app.character.creation import (
    AssistedCreation,
    CharacterGenerationError,
    CharacterStorage,
)
from app.character.model import Character
from app.llm.config import ProviderConfig, create_provider

logger = logging.getLogger(__name__)

bp = flask.Blueprint("characters", __name__, url_prefix="/api")

_character_storage = CharacterStorage(data_dir=Path("data"))


@bp.route("/character/generate", methods=["POST"])
def generate_character() -> tuple[flask.Response, int] | flask.Response:
    """Generate a character from narrative answers using the LLM.

    Accepts JSON body with ``answers`` (dict of index -> answer text)
    and optional ``provider`` config (``base_url``, ``model``, ``api_key``).

    Returns
    -------
    JSON with ``ok`` and ``character`` (serialised Character) on success.

    Errors
    ------
    400
        If the request body is invalid, answers are missing/fewer than 3,
        or provider config is missing.
    422
        If the LLM fails to generate a valid character.
    500
        If an internal error occurs.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    answers = data.get("answers")
    abilities = data.get("abilities", {})
    if not isinstance(answers, dict) or len(answers) < 3:
        return (
            jsonify({"ok": False, "error": "At least 3 answers are required"}),
            400,
        )

    # Convert string keys to int
    try:
        answers_int: dict[int, str] = {}
        for k, v in answers.items():
            answers_int[int(k)] = str(v)
    except (ValueError, TypeError):
        return (
            jsonify({"ok": False, "error": "Answer keys must be numeric indices"}),
            400,
        )

    provider_config = data.get("provider", {})
    if not isinstance(provider_config, dict):
        return (
            jsonify({"ok": False, "error": "Provider config must be a dict"}),
            400,
        )

    base_url = str(provider_config.get("base_url") or "").strip()
    model = str(provider_config.get("model") or "").strip()
    if not base_url or not model:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Provider base_url and model are required",
                }
            ),
            400,
        )

    api_key = provider_config.get("api_key")
    provider_type = str(provider_config.get("provider_type") or "").strip() or "ollama"

    try:
        config = ProviderConfig(
            base_url=base_url,
            model=model,
            provider_type=provider_type,
            api_key=api_key,
        )
        provider = create_provider(config)
        creation = AssistedCreation(llm_provider=provider)
        character = creation.generate_character(answers_int, abilities=abilities)
    except ValueError as e:
        logger.warning("Invalid character generation request: %s", e)
        return jsonify({"ok": False, "error": "Invalid request data"}), 400
    except CharacterGenerationError as e:
        logger.warning("Character generation validation failed: %s", e)
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Unable to generate character from provided answers",
                }
            ),
            422,
        )
    except Exception:
        logger.exception("Character generation failed")
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "character": character.to_dict()})


@bp.route("/character/save", methods=["POST"])
def save_character() -> tuple[flask.Response, int] | flask.Response:
    """Save a character to disk.

    Accepts JSON body with ``character`` (serialised Character dict)
    and optional ``name`` (defaults to the character's own name).

    Returns
    -------
    JSON with ``ok``, ``name``, and ``timestamp`` on success.

    Errors
    ------
    400
        If the request body is invalid or character data is missing.
    500
        If the persistence layer raises an error.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    char_data = data.get("character")
    if not isinstance(char_data, dict):
        return (
            jsonify({"ok": False, "error": "Missing 'character' dict in request body"}),
            400,
        )

    name = data.get("name")

    try:
        character = Character.from_dict(char_data)
        timestamp = _character_storage.save(character, name=name)
        saved_name = name if name and name.strip() else character.name
    except ValueError:
        logger.warning("Invalid character data in save_character", exc_info=True)
        return jsonify({"ok": False, "error": "Invalid character data"}), 400
    except Exception:
        logger.exception("Failed to save character")
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "name": saved_name, "timestamp": timestamp})


@bp.route("/characters", methods=["GET"])
def list_characters() -> tuple[flask.Response, int] | flask.Response:
    """Return metadata for all saved characters.

    Returns
    -------
    JSON with ``ok`` and a ``characters`` list of metadata dicts.
    """
    characters = _character_storage.list_characters()
    return jsonify({"ok": True, "characters": characters})


@bp.route("/character/load/<name>", methods=["GET"])
def load_character(name: str) -> tuple[flask.Response, int] | flask.Response:
    """Load a single character's full data by name.

    Parameters
    ----------
    name : str
        The character's name (URL-decoded automatically by Flask).

    Returns
    -------
    JSON with ``ok`` and the full ``character`` dict on success.

    Errors
    ------
    404
        If no character with the given *name* exists.
    400
        If the save file is corrupt or unreadable.
    500
        If an internal error occurs.
    """
    try:
        character = _character_storage.load(name)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": f"Character '{name}' not found"}), 404
    except ValueError:
        logger.warning(
            "Invalid or corrupt character data for '%s'", name, exc_info=True
        )
        return (
            jsonify({"ok": False, "error": "Invalid or corrupt character data"}),
            400,
        )
    except Exception:
        logger.exception("Failed to load character '%s'", name)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "character": character.to_dict()})


@bp.route("/character/delete/<name>", methods=["DELETE"])
def delete_character(name: str) -> tuple[flask.Response, int] | flask.Response:
    """Delete a saved character by name.

    Parameters
    ----------
    name : str
        The character's name (URL-decoded automatically by Flask).

    Returns
    -------
    JSON with ``ok`` on success.

    Errors
    ------
    404
        If no character with the given *name* exists.
    500
        If an internal error occurs.
    """
    try:
        _character_storage.delete(name)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": f"Character '{name}' not found"}), 404
    except Exception:
        logger.exception("Failed to delete character '%s'", name)
        return (
            jsonify({"ok": False, "error": "Internal server error"}),
            500,
        )

    return jsonify({"ok": True})
