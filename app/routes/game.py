"""Game loop API routes — SSE stream endpoint."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator
from pathlib import Path

import flask as flask
from flask import Response, jsonify, request, stream_with_context

from app.agents.dm import DungeonMaster
from app.character.model import Character, CharacterRecord
from app.llm.base import (
    LLMProvider,  # noqa: F401 — used in type hint for _build_provider_from_dict
)
from app.llm.config import ProviderConfig, create_provider
from app.world.model import WorldState
from app.world.persistence import WorldStorage
from app.agents.record_keeper import RecordKeeperAgent
from app.agents.entity_persistence import EntityStorage
from app.agents.tools import set_record_keeper

logger = logging.getLogger(__name__)

bp = flask.Blueprint("game", __name__)


# ---------------------------------------------------------------------------
# Cache of persistent DungeonMaster instances, keyed by character_id.
# DMs are recreated for new games and evicted after inactivity.
# ---------------------------------------------------------------------------

_dm_cache: dict[str, DungeonMaster] = {}

# Track last cleanup time
_dm_cache_cleanup_time: float = 0.0
_DM_CACHE_CLEANUP_INTERVAL: float = 300.0  # 5 minutes

# Shared storage backend for per-turn narrative persistence
_storage = WorldStorage(data_dir=Path("data"))


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


def _prov_from_json(body: dict, prefix: str = "") -> dict:
    """Extract a provider config from parsed JSON body with optional key prefix."""
    raw: dict = body.get(f"{prefix}provider") or {}  # type: ignore[assignment]
    if not isinstance(raw, dict):
        raw = {}
    base_url = str(raw.get("base_url") or "").strip()
    model = str(raw.get("model") or "").strip()
    if not base_url or not model:
        return {}
    timeout_val = _safe_int(raw.get("timeout"))
    max_tokens_val = _safe_int(raw.get("max_tokens"))
    temperature_val = _safe_float(raw.get("temperature"))
    return {
        "base_url": base_url,
        "model": model,
        "provider_type": str(raw.get("provider_type") or "").strip() or "ollama",
        "api_key": raw.get("api_key"),
        "timeout": timeout_val,
        "max_tokens": max_tokens_val,
        "temperature": temperature_val,
    }


# ---------------------------------------------------------------------------
# Game Stream (SSE endpoint)
# ---------------------------------------------------------------------------


@bp.route("/api/game/stream", methods=["POST"])
def game_stream() -> tuple[flask.Response, int] | flask.Response:
    """SSE endpoint for streaming DM responses via POST with JSON body.

    Accepts a JSON body containing:
      ``input`` (str): The player's action text (required).
      ``provider`` (dict): Main LLM provider config.
      ``state`` (dict): Current world state dict for continuity.
      ``character`` (dict): Current character data.
      ``npc_provider`` (dict): NPC subagent provider config.
      ``summarizer_provider`` (dict): Summarizer provider config.

    SSE events: (same as before — token, narrative, state_update, done, etc.)
    """
    body = request.get_json(silent=True) or {}
    player_input = (body.get("input") or "").strip()
    if not player_input:
        return jsonify({"ok": False, "error": "Missing 'input' in request body"}), 400

    logger.debug(
        "game_stream: received player input (len=%d): %s",
        len(player_input),
        player_input,
    )

    dm_provider_cfg = _prov_from_json(body)
    npc_provider_cfg = _prov_from_json(body, "npc_")
    summarizer_provider_cfg = _prov_from_json(body, "summarizer_")

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

    # Record-Keeper provider (optional — falls back to DM provider, then None)
    record_keeper_provider_cfg = _prov_from_json(body, "record_keeper_")
    record_keeper_provider = (
        _build_provider_from_dict(record_keeper_provider_cfg)
        if record_keeper_provider_cfg
        else None
    )

    # Clean up stale DMs periodically
    _cleanup_stale_dms()

    world_state_data = body.get("state") or {}
    if isinstance(world_state_data, dict):
        world_state = WorldState.from_dict(world_state_data)
    else:
        world_state = WorldState()

    character_data = (
        body.get("character") if isinstance(body.get("character"), dict) else None
    )
    character = CharacterRecord.from_dict(character_data) if character_data else None

    # If starting a new game (no prior state was provided), seed the world
    # state inventory and gold from the character's starting equipment.
    if character is not None and not body.get("state"):
        if not world_state.inventory and character.inventory:
            world_state.inventory = list(character.inventory)
        if not world_state.gold and character.gold:
            world_state.gold = character.gold

    # Extract optional save slug for per-turn narrative persistence.
    # The frontend passes this when the game was loaded from a save.
    raw_slug = body.get("slug")
    save_slug: str | None = str(raw_slug).strip() if raw_slug else None

    # Create or retrieve persistent DungeonMaster for this character.
    character_id = character.id if character else None
    if character_id and character_id in _dm_cache:
        dm = _dm_cache[character_id]
        # Keep world_state fresh from the request while preserving history
        dm.world_state = world_state
        # Update storage attributes so per-turn persistence uses
        # the correct slug and storage backend (Bug 2 fix)
        dm._save_slug = save_slug
        dm._storage = _storage
    else:
        # Create Record-Keeper agent (entity memory & narrative analysis)
        record_keeper = None
        if character_id:
            rk_provider = record_keeper_provider or dm_provider
            data_dir = Path("data") / "saves" / (save_slug or character_id or "default")
            entity_storage = EntityStorage(data_dir=data_dir)
            record_keeper = RecordKeeperAgent(
                llm_provider=rk_provider,
                entity_storage=entity_storage,
                character_name=character.name if character else "",
            )
            # Set the module-level reference so the on-demand fetch tool works
            set_record_keeper(record_keeper)

        dm = DungeonMaster(
            llm_provider=dm_provider,
            world_state=world_state,
            character=character,
            npc_provider=npc_provider,
            summarizer_provider=summarizer_provider,
            storage=_storage,
            save_slug=save_slug,
            record_keeper=record_keeper,
        )
        if character_id:
            _dm_cache[character_id] = dm

    # Restore DM compressed summary from saved technical_summary
    # so the DM's memory survives save/load cycles
    if world_state.technical_summary:
        dm.history.compressed_summary = world_state.technical_summary[-1]

    # Restore L3 meta-summaries for continuity across save/load cycles
    if world_state.meta_summary:
        for ms in world_state.meta_summary:
            dm.history.add_l3_summary(ms)

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
