"""Game loop API routes — SPA entry point and SSE stream endpoint."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator

import flask as flask
from flask import Response, current_app, jsonify, request, stream_with_context

from app.agents.dm import DungeonMaster
from app.llm.base import (
    LLMProvider,  # noqa: F401 — used in type hint for _build_provider_from_dict
)
from app.llm.config import ProviderConfig, create_provider
from app.world.model import WorldState

logger = logging.getLogger(__name__)

bp = flask.Blueprint("game", __name__)


# ---------------------------------------------------------------------------
# Static file serving (SPA frontend)
# ---------------------------------------------------------------------------


@bp.route("/")
def index() -> tuple[flask.Response, int] | flask.Response:
    """Serve the SPA entry point (index.html)."""
    return current_app.send_static_file("index.html")


# ---------------------------------------------------------------------------
# Cache of persistent DungeonMaster instances, keyed by character_id.
# DMs are recreated for new games and evicted after inactivity.
# ---------------------------------------------------------------------------

_dm_cache: dict[str, DungeonMaster] = {}

# Track last cleanup time
_dm_cache_cleanup_time: float = 0.0
_DM_CACHE_CLEANUP_INTERVAL: float = 300.0  # 5 minutes


def _cleanup_stale_dms() -> None:
    """Evict DMs that have been idle too long. Called periodically."""
    global _dm_cache_cleanup_time
    now = time.monotonic()
    if now - _dm_cache_cleanup_time < _DM_CACHE_CLEANUP_INTERVAL:
        return
    _dm_cache_cleanup_time = now

    # Keep cache bounded — production would track last-access per DM
    if len(_dm_cache) > 50:
        keys = list(_dm_cache.keys())
        for key in keys[:-50]:
            del _dm_cache[key]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_int(val: str | None) -> int | None:
    """Cast a string to int safely, returning None on failure."""
    try:
        return int(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(val: str | None) -> float | None:
    """Cast a string to float safely, returning None on failure."""
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _build_provider_from_dict(config_data: dict) -> LLMProvider | None:
    """Build a provider from a config dict, returning None if incomplete."""
    base_url = str(config_data.get("base_url") or "").strip()
    model = str(config_data.get("model") or "").strip()
    if not base_url or not model:
        return None

    provider_type = str(config_data.get("provider_type") or "").strip() or "ollama"
    api_key = config_data.get("api_key")
    raw_timeout = config_data.get("timeout", 300)
    timeout = raw_timeout if isinstance(raw_timeout, int) and raw_timeout > 0 else 300
    max_tokens = config_data.get("max_tokens")
    temperature = config_data.get("temperature")

    config = ProviderConfig(
        base_url=base_url,
        model=model,
        provider_type=provider_type,
        api_key=api_key,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return create_provider(config)


# ---------------------------------------------------------------------------
# Game Stream (SSE endpoint)
# ---------------------------------------------------------------------------


@bp.route("/api/game/stream", methods=["GET"])
def game_stream() -> tuple[flask.Response, int] | flask.Response:
    """SSE endpoint for streaming DM responses.

    Accepts ``?input=player+action`` query parameter, plus optional
    ``state``, ``character``, ``npc_provider``, and
    ``summarizer_provider`` (all JSON-encoded) to restore continuity.

    Creates a DungeonMaster, collects the LLM streaming response,
    parses it, executes any tool requests, spawns NPC subagents, and
    yields the final result as SSE events.

    SSE events:
      ``data: {"type": "token", "content": "..."}``
        Individual tokens as they stream from the LLM.
      ``data: {"type": "npc_thinking", "npc_id": "...", "hint": "..."}``
        Indicates an NPC agent is processing.
      ``data: {"type": "narrative", "content": "..."}``
        The final parsed narrative.
      ``data: {"type": "state_update", "state": ..., "turn_count": N}``
        The updated world state and turn count for the client.
      ``data: {"type": "token_usage", "usage": ...}``
        Token usage stats.
      ``data: {"type": "done", "turn_count": N}``
        Signals completion.
      ``data: {"type": "error", "message": "..."}``
        Signals an error.
    """
    player_input = request.args.get("input", "").strip()
    if not player_input:
        return (
            jsonify({"ok": False, "error": "Missing 'input' query parameter"}),
            400,
        )

    logger.debug(
        "game_stream: received player input (len=%d): %s",
        len(player_input),
        player_input,
    )

    # Build provider configs from query params
    def _prov_from_args(prefix: str = "") -> dict:
        """Extra a provider config dict from query args with optional prefix."""
        base = request.args.get(f"{prefix}base_url", "").strip()
        model = request.args.get(f"{prefix}model", "").strip()
        if not base or not model:
            return {}
        timeout = _safe_int(request.args.get(f"{prefix}timeout"))
        max_tokens = _safe_int(request.args.get(f"{prefix}max_tokens"))
        temperature = _safe_float(request.args.get(f"{prefix}temperature"))
        return {
            "base_url": base,
            "model": model,
            "provider_type": request.args.get(f"{prefix}provider_type", "ollama"),
            "api_key": request.args.get(f"{prefix}api_key"),
            "timeout": timeout,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    dm_provider_cfg = _prov_from_args()
    npc_provider_cfg = _prov_from_args("npc_")
    summarizer_provider_cfg = _prov_from_args("summarizer_")

    dm_provider = (
        _build_provider_from_dict(dm_provider_cfg) if dm_provider_cfg else None
    )
    npc_provider = (
        _build_provider_from_dict(npc_provider_cfg) if npc_provider_cfg else dm_provider
    )
    summarizer_provider = (
        _build_provider_from_dict(summarizer_provider_cfg)
        if summarizer_provider_cfg
        else None
    )

    # Clean up stale DMs periodically
    _cleanup_stale_dms()

    # Restore world state from query param (JSON-encoded)
    state_raw = request.args.get("state")
    if state_raw:
        try:
            world_state = WorldState.from_dict(json.loads(state_raw))
        except (json.JSONDecodeError, Exception):
            world_state = WorldState()
    else:
        world_state = WorldState()

    # Restore character from query param (JSON-encoded)
    character_raw = request.args.get("character")
    character = None
    if character_raw:
        try:
            character = json.loads(character_raw)
        except (json.JSONDecodeError, Exception):
            character = None

    # Create or retrieve persistent DungeonMaster for this character.
    character_id = character.get("id") if isinstance(character, dict) else None
    if character_id and character_id in _dm_cache:
        dm = _dm_cache[character_id]
        # Keep world_state fresh from the request while preserving history
        dm.world_state = world_state
    else:
        dm = DungeonMaster(
            llm_provider=dm_provider,
            world_state=world_state,
            character=character,
            npc_provider=npc_provider,
            summarizer_provider=summarizer_provider,
        )
        if character_id:
            _dm_cache[character_id] = dm

    def generate() -> Generator[str, None, None]:
        try:
            for event in dm.process_turn_stream(player_input):
                yield (
                    f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
                )
        except Exception:
            logger.exception("process_turn_stream failed")
            error_data = json.dumps(
                {"type": "error", "message": "Internal server error"}
            )
            yield f"event: error\ndata: {error_data}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
