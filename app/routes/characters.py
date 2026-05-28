"""Character API routes — creation, save, load, list, delete."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import flask as flask
from flask import jsonify, request

from app.character.creation import (
    AssistedCreation,
    CharacterGenerationError,
    CharacterStorage,
)
from app.character.model import VALID_CLASSES, Character
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
    character_class = data.get("character_class")
    if not isinstance(character_class, str) or character_class not in VALID_CLASSES:
        character_class = None
    name = data.get("name")
    if not isinstance(name, str):
        name = None
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
        character = creation.generate_character(
            answers_int,
            abilities=abilities,
            name=name,
            character_class=character_class,
        )
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


@bp.route("/character/create", methods=["POST"])
def create_character() -> tuple[flask.Response, int] | flask.Response:
    """Create a new character and persist it.

    Accepts JSON body with:

    * ``name`` (required, non-empty string)
    * ``character_class`` (required, one of ``VALID_CLASSES``)
    * ``appearance`` (optional string)
    * ``backstory`` (optional string)

    Returns
    -------
    JSON with ``ok`` and the full ``character`` dict on success.

    Errors
    ------
    400
        If the request body is invalid, name is missing, or
        character_class is not recognised.
    500
        If an internal error occurs.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"ok": False, "error": "Character name is required"}), 400

    character_class = data.get("character_class")
    if character_class not in VALID_CLASSES:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": (
                        f"Invalid character class '{character_class}'. "
                        f"Must be one of {sorted(VALID_CLASSES)}"
                    ),
                }
            ),
            400,
        )

    # Check if extended fields are present (e.g. from localStorage migration)
    has_extended = any(
        k in data
        for k in (
            "level",
            "xp",
            "hp",
            "max_hp",
            "ac",
            "abilities",
            "gold",
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
            "skills",
            "personality",
            "ideals",
            "bonds",
            "flaws",
            "plot_hooks",
        )
    )

    try:
        if has_extended:
            # Build abilities dict from individual fields or direct dict
            abilities: dict[str, int] = {}
            if "abilities" in data and isinstance(data["abilities"], dict):
                for k, v in data["abilities"].items():
                    if v is not None:
                        abilities[k.upper()] = int(v)
            else:
                ability_map: dict[str, str] = {
                    "strength": "STR",
                    "dexterity": "DEX",
                    "constitution": "CON",
                    "intelligence": "INT",
                    "wisdom": "WIS",
                    "charisma": "CHA",
                }
                for src_key, dst_key in ability_map.items():
                    if src_key in data and data[src_key] is not None:
                        abilities[dst_key] = int(data[src_key])

            # Build character dict for from_dict (handles validation/defaults)
            char_data: dict[str, Any] = {
                "name": name.strip(),
                "character_class": character_class,
            }
            if abilities:
                char_data["abilities"] = abilities
            for field in ("level", "xp", "hp", "max_hp", "ac", "gold"):
                if field in data and data[field] is not None:
                    char_data[field] = data[field]
            for field in ("appearance", "backstory", "personality"):
                if field in data and data[field] is not None:
                    char_data[field] = str(data[field])
            for field in ("skills", "inventory", "hooks"):
                if field in data and isinstance(data[field], list):
                    char_data[field] = data[field]

            character = Character.from_dict(char_data)
        else:
            character = Character.create_default(name.strip(), character_class)
            appearance = data.get("appearance", "")
            backstory = data.get("backstory", "")
            if appearance and isinstance(appearance, str):
                character.appearance = appearance
            if backstory and isinstance(backstory, str):
                character.backstory = backstory
        _character_storage.save(character)
    except ValueError as e:
        logger.warning("Invalid character creation request: %s", e)
        return jsonify({"ok": False, "error": "Invalid character data"}), 400
    except Exception:
        logger.exception("Failed to create character")
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "character": character.to_dict()})


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


@bp.route("/character/id/<char_id>", methods=["GET"])
def load_character_by_id(
    char_id: str,
) -> tuple[flask.Response, int] | flask.Response:
    """Load a single character's full data by UUID.

    Parameters
    ----------
    char_id : str
        The character's UUID string.

    Returns
    -------
    JSON with ``ok`` and the full ``character`` dict on success.

    Errors
    ------
    404
        If no character with the given *char_id* exists.
    500
        If an internal error occurs.
    """
    try:
        character = _character_storage.load_by_id(char_id)
    except FileNotFoundError:
        return (
            jsonify({"ok": False, "error": f"Character with id '{char_id}' not found"}),
            404,
        )
    except ValueError:
        logger.warning(
            "Invalid or corrupt character data for id '%s'", char_id, exc_info=True
        )
        return (
            jsonify({"ok": False, "error": "Invalid or corrupt character data"}),
            400,
        )
    except Exception:
        logger.exception("Failed to load character by id '%s'", char_id)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "character": character.to_dict()})


@bp.route("/character/id/<char_id>", methods=["DELETE"])
def delete_character_by_id(
    char_id: str,
) -> tuple[flask.Response, int] | flask.Response:
    """Delete a saved character by UUID.

    Parameters
    ----------
    char_id : str
        The character's UUID string.

    Returns
    -------
    JSON with ``ok`` on success.

    Errors
    ------
    404
        If no character with the given *char_id* exists.
    500
        If an internal error occurs.
    """
    try:
        _character_storage.delete_by_id(char_id)
    except FileNotFoundError:
        return (
            jsonify({"ok": False, "error": f"Character with id '{char_id}' not found"}),
            404,
        )
    except Exception:
        logger.exception("Failed to delete character by id '%s'", char_id)
        return (
            jsonify({"ok": False, "error": "Internal server error"}),
            500,
        )

    return jsonify({"ok": True})
