"""Flask server for the LLM-Powered RPG.

Provides REST API endpoints for the game, starting with a health
check endpoint for LLM provider connectivity, plus save/load/reset
endpoints for persisting and restoring game state, and game loop
endpoints for processing player turns.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from pathlib import Path

from flask import Flask, Response, jsonify, request, stream_with_context

from app.agents.dm import DungeonMaster, format_npc_results, format_tool_results
from app.agents.parser import parse_dm_response
from app.agents.tools import dispatch_tool
from app.character.creation import (
    AssistedCreation,
    CharacterGenerationError,
    CharacterStorage,
)
from app.character.model import Character
from app.llm.base import (
    LLMProvider,
    ProviderConfig,
    get_cached_models,
    set_cached_models,
)
from app.llm.config import create_provider
from app.world.model import WorldState
from app.world.persistence import WorldStorage
from app.world.validator import apply_changes, validate_state_changes

# Resolve static folder relative to this module's location
_static_folder = str(Path(__file__).resolve().parent / "static")
app = Flask(__name__, static_folder=_static_folder, static_url_path="/static")
logger = logging.getLogger(__name__)
_storage = WorldStorage(data_dir=Path("data"))
_character_storage = CharacterStorage(data_dir=Path("data"))


# ---------------------------------------------------------------------------
# Static file serving (SPA frontend)
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    """Serve the SPA entry point (index.html)."""
    return app.send_static_file("index.html")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.route("/api/health", methods=["POST"])
def health_check():
    """Check the health of an LLM provider.

    Accepts JSON body with ``base_url``, ``model``, and optional
    ``api_key``.  Creates an LLM provider (based on ``provider_type``)
    and calls its :meth:`health` method.

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

    base_url = str(data.get("base_url") or "").strip()
    model = str(data.get("model") or "").strip()

    if not base_url or not model:
        return jsonify({"ok": False, "error": "base_url and model are required"}), 400

    api_key = data.get("api_key")
    provider_type = str(data.get("provider_type") or "").strip() or "ollama"
    print(provider_type)
    config = ProviderConfig(
        base_url=base_url,
        model=model,
        provider_type=provider_type,
        api_key=api_key,
    )
    provider = create_provider(config)

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
# Model List
# ---------------------------------------------------------------------------


@app.route("/api/models", methods=["POST"])
def list_models():
    """Fetch available models from an LLM provider.

    Accepts JSON body with ``base_url``, ``model``, and optional
    ``api_key`` and ``provider_type``.  Creates the appropriate
    provider, checks the cache, and calls its ``list_models()``
    method.

    Results are cached for 5 minutes by ``(provider_type, base_url)``.

    Returns
    -------
    JSON with ``ok`` and ``models`` (list of ``{"id", "name"}`` dicts).

    Errors
    ------
    400
        If the request body is invalid, or ``base_url`` or
        ``model`` are missing or empty.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Invalid JSON body", "models": []}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body", "models": []}), 400

    base_url = str(data.get("base_url") or "").strip()
    model = str(data.get("model") or "").strip()

    if not base_url or not model:
        return jsonify(
            {"ok": False, "error": "base_url and model are required", "models": []}
        ), 400

    api_key = data.get("api_key")
    provider_type = str(data.get("provider_type") or "").strip() or "ollama"

    # Check cache first
    cached = get_cached_models(provider_type, base_url)
    if cached is not None:
        return jsonify({"ok": True, "models": [m.to_dict() for m in cached]})

    # Cache miss — create provider and fetch
    config = ProviderConfig(
        base_url=base_url,
        model=model,
        provider_type=provider_type,
        api_key=api_key,
    )
    try:
        provider = create_provider(config)
        models = provider.list_models()
    except Exception as exc:
        logger.warning("Failed to fetch models: %s", exc)
        return jsonify({"ok": False, "error": "Failed to fetch models", "models": []})

    # Cache the result
    set_cached_models(provider_type, base_url, models)

    return jsonify({"ok": True, "models": [m.to_dict() for m in models]})


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


# ---------------------------------------------------------------------------
# Character API — Assisted Creation, Save, Load, List
# ---------------------------------------------------------------------------


@app.route("/api/character/generate", methods=["POST"])
def generate_character():
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
    if not isinstance(answers, dict) or len(answers) < 3:
        return jsonify({"ok": False, "error": "At least 3 answers are required"}), 400

    # Convert string keys to int
    try:
        answers_int: dict[int, str] = {}
        for k, v in answers.items():
            answers_int[int(k)] = str(v)
    except (ValueError, TypeError):
        return jsonify(
            {"ok": False, "error": "Answer keys must be numeric indices"}
        ), 400

    provider_config = data.get("provider", {})
    if not isinstance(provider_config, dict):
        return jsonify({"ok": False, "error": "Provider config must be a dict"}), 400

    base_url = str(provider_config.get("base_url") or "").strip()
    model = str(provider_config.get("model") or "").strip()
    if not base_url or not model:
        return jsonify(
            {
                "ok": False,
                "error": "Provider base_url and model are required",
            }
        ), 400

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
        character = creation.generate_character(answers_int)
    except ValueError as e:
        logger.warning("Invalid character generation request: %s", e)
        return jsonify({"ok": False, "error": "Invalid request data"}), 400
    except CharacterGenerationError as e:
        logger.warning("Character generation validation failed: %s", e)
        return jsonify(
            {"ok": False, "error": "Unable to generate character from provided answers"}
        ), 422
    except Exception:
        logger.exception("Character generation failed")
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return jsonify({"ok": True, "character": character.to_dict()})


@app.route("/api/character/save", methods=["POST"])
def save_character():
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
        return jsonify(
            {"ok": False, "error": "Missing 'character' dict in request body"}
        ), 400

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


@app.route("/api/characters", methods=["GET"])
def list_characters():
    """Return metadata for all saved characters.

    Returns
    -------
    JSON with ``ok`` and a ``characters`` list of metadata dicts.
    """
    characters = _character_storage.list_characters()
    return jsonify({"ok": True, "characters": characters})


# ---------------------------------------------------------------------------
# Game Loop
# ---------------------------------------------------------------------------


def _build_provider_from_dict(config_data: dict) -> LLMProvider | None:
    """Build a provider from a config dict, returning None if incomplete."""
    base_url = str(config_data.get("base_url") or "").strip()
    model = str(config_data.get("model") or "").strip()
    if not base_url or not model:
        return None

    provider_type = str(config_data.get("provider_type") or "").strip() or "ollama"
    api_key = config_data.get("api_key")
    timeout = config_data.get("timeout", 30)
    if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
        timeout = 30

    config = ProviderConfig(
        base_url=base_url,
        model=model,
        provider_type=provider_type,
        api_key=api_key,
        timeout=timeout,
    )
    return create_provider(config)


def _build_dm(data: dict) -> tuple[DungeonMaster | None, str | None]:
    """Build a DungeonMaster from request data, with per-agent providers.

    Looks for optional ``provider`` (DM), ``npc_provider``,
    ``summarizer_provider``, ``state``, and ``character`` keys.
    If ``provider`` is missing, creates a DM with ``llm_provider=None``
    (which returns canned responses for testing).

    Parameters
    ----------
    data : dict
        Request JSON data.

    Returns
    -------
    tuple[DungeonMaster | None, str | None]
        (dm, error) — either a configured DungeonMaster or an error
        message string.
    """
    # DM provider config
    dm_config_data = data.get("provider", {})
    if dm_config_data and isinstance(dm_config_data, dict):
        dm_provider = _build_provider_from_dict(dm_config_data)
    else:
        dm_provider = None

    # NPC provider config (separate agent)
    npc_config_data = data.get("npc_provider", {})
    if npc_config_data and isinstance(npc_config_data, dict):
        npc_provider = _build_provider_from_dict(npc_config_data)
    else:
        npc_provider = dm_provider  # Fallback to DM provider

    # Summarizer provider config (separate agent, falls back to DM provider)
    summarizer_config_data = data.get("summarizer_provider", {})
    if summarizer_config_data and isinstance(summarizer_config_data, dict):
        summarizer_provider = _build_provider_from_dict(summarizer_config_data)
    else:
        summarizer_provider = None  # Falls back to DM provider in DungeonMaster

    # Build optional world state
    state_data = data.get("state")
    if state_data and isinstance(state_data, dict):
        try:
            world_state = WorldState.from_dict(state_data)
        except Exception:
            world_state = WorldState()
    else:
        world_state = WorldState()

    # Character (optional, pass through as-is)
    character = data.get("character")

    dm = DungeonMaster(
        llm_provider=dm_provider,
        world_state=world_state,
        character=character,
        npc_provider=npc_provider,
        summarizer_provider=summarizer_provider,
    )
    return dm, None


@app.route("/api/turn", methods=["POST"])
def game_turn():
    """Process a single player turn through the Dungeon Master.

    Accepts JSON body with ``input`` (the player's action text) and
    optional ``provider``, ``state``, and ``character`` overrides.

    Returns
    -------
    JSON with ``narrative``, ``state_changes``, ``tool_results``,
    ``turn_count``, and ``ok``.

    Errors
    ------
    400
        If ``input`` is missing or empty.
    500
        If an internal error occurs during turn processing.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Request must be JSON"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    player_input = (data.get("input") or "").strip()
    if not player_input:
        return jsonify({"ok": False, "error": "Missing 'input' in request body"}), 400

    dm, error = _build_dm(data)
    if error:
        return jsonify({"ok": False, "error": error}), 400

    try:
        result = dm.process_turn(player_input)
        return jsonify(result)
    except Exception:
        logger.exception("Turn processing failed")
        return jsonify(
            {
                "ok": False,
                "error": "Internal server error during turn processing",
                "narrative": "",
                "state_changes": [],
                "tool_results": [],
                "turn_count": 0,
            }
        ), 500


@app.route("/api/game/stream", methods=["GET"])
def game_stream():
    """SSE endpoint for streaming DM responses.

    Accepts ``?input=player+action`` query parameter.  Creates a
    DungeonMaster, collects the LLM streaming response, parses it,
    executes any tool requests, spawns NPC subagents, and yields the
    final result as SSE events.

    SSE events:
      ``data: {"type": "token", "content": "..."}``
        Individual tokens as they stream from the LLM.
      ``data: {"type": "npc_thinking", "npc_id": "...", "hint": "..."}``
        Indicates an NPC agent is processing.
      ``data: {"type": "narrative", "content": "..."}``
        The final parsed narrative.
      ``data: {"type": "done", "turn_count": N}``
        Signals completion.
      ``data: {"type": "error", "message": "..."}``
        Signals an error.
    """
    player_input = request.args.get("input", "").strip()
    if not player_input:
        return jsonify({"ok": False, "error": "Missing 'input' query parameter"}), 400

    # Build provider config from query params
    base_url = request.args.get("base_url", "").strip()
    model = request.args.get("model", "").strip()

    if base_url and model:
        provider_type = str(request.args.get("provider_type") or "").strip() or "ollama"
        config = ProviderConfig(
            base_url=base_url,
            model=model,
            provider_type=provider_type,
            api_key=request.args.get("api_key"),
        )
        llm_provider = create_provider(config)
        npc_provider = llm_provider
    else:
        llm_provider = None
        npc_provider = None

    world_state = WorldState()
    dm = DungeonMaster(
        llm_provider=llm_provider,
        world_state=world_state,
        character=None,
        npc_provider=npc_provider,
    )

    def generate() -> Generator[str, None, None]:
        """Generate SSE events for the streaming response."""
        messages = dm._build_context(player_input)

        collected_tokens: list[str] = []

        if dm.llm_provider is not None:
            # Stream tokens from the LLM
            try:
                for token in dm.llm_provider.stream(messages):
                    collected_tokens.append(token)
                    yield (
                        f"event: token\n"
                        f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                    )
            except Exception:
                logger.exception("Stream error")
                error_data = json.dumps(
                    {"type": "error", "message": "Internal server error"}
                )
                yield f"event: error\ndata: {error_data}\n\n"
                return

            full_response = "".join(collected_tokens)
        else:
            # No provider configured — use canned response
            full_response = "<narrative>\nThe scene unfolds before you.\n</narrative>"

        # Parse the collected response
        try:
            parsed = parse_dm_response(full_response)
            narrative = parsed.get("narrative", "")
            state_changes = parsed.get("state_changes", [])
            tool_requests = parsed.get("tool_requests", [])
            npc_requests = parsed.get("npc_requests", [])
        except Exception:
            logger.exception("Parse error in stream response")
            yield (
                f"event: error\n"
                f"data: {json.dumps({'type': 'error', 'message': 'Parse error'})}\n\n"
            )
            return

        # Execute tool requests
        tool_results = []
        if tool_requests:
            for req in tool_requests:
                result = dispatch_tool(req["name"], req.get("params", {}))
                tool_results.append(
                    {
                        "name": req["name"],
                        "params": req.get("params", {}),
                        "result": result,
                    }
                )

        # Spawn NPC subagents and yield npc_thinking events
        npc_results = []
        if npc_requests:
            for nr in npc_requests:
                npc_id = nr.get("npc_id", "unknown")
                hint = nr.get("context", f"The {npc_id} considers...")[:60]
                event_data = json.dumps(
                    {
                        "type": "npc_thinking",
                        "npc_id": npc_id,
                        "hint": hint,
                    }
                )
                yield (f"event: npc_thinking\ndata: {event_data}\n\n")
            npc_results = dm._spawn_npcs(npc_requests, player_input)

        # Second LLM call with tool results and/or NPC results
        need_second_call = bool(tool_requests) or bool(npc_results)
        if need_second_call:
            messages.append({"role": "assistant", "content": full_response})

            context_parts = []

            if tool_results:
                tool_summary = format_tool_results(tool_results)
                context_parts.append(f"Tool results:\n{tool_summary}")

            if npc_results:
                npc_block = format_npc_results(npc_results)
                context_parts.append(
                    f"NPC interactions produced the following results:\n\n"
                    f"{npc_block}\n\n"
                    f"You may use, modify, or ignore these NPC responses "
                    f"as you see fit.  Weave them into the narrative."
                )

            context_parts.append(
                "Now continue the narrative, weaving these results into the story."
            )

            messages.append(
                {
                    "role": "user",
                    "content": "\n\n".join(context_parts),
                }
            )

            try:
                if dm.llm_provider is not None:
                    second_response = dm.llm_provider.call(messages)
                    if second_response:
                        second_text = second_response.get("content", "")
                        parsed2 = parse_dm_response(second_text)
                        narrative = parsed2.get("narrative", narrative)
                        state_changes = parsed2.get("state_changes", state_changes)
            except Exception as e:
                logger.warning("Second LLM call in stream failed: %s", e)

        # Validate and apply state changes
        if state_changes:
            validation_errors = validate_state_changes(state_changes, world_state)
            if not validation_errors:
                try:
                    new_state = apply_changes(world_state, state_changes)
                    dm.world_state = new_state
                except Exception as e:
                    logger.warning("Failed to apply state changes in stream: %s", e)

        # Yield narrative
        yield (
            f"event: narrative\n"
            f"data: {json.dumps({'type': 'narrative', 'content': narrative})}\n\n"
        )
        yield (
            f"event: done\n"
            f"data: {json.dumps({'type': 'done', 'turn_count': dm.turn_count + 1})}\n\n"
        )

        # Update DM turn count
        dm.turn_count += 1

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
