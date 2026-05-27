"""Settings API routes — get and update application-wide settings.

Provides ``GET /api/settings`` for reading the current settings (hardcoded
defaults merged with any saved provider config), and ``POST /api/settings``
for updating and persisting settings to ``data/providers/default.json``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import flask as flask
from flask import jsonify, request

from app.llm.base import ProviderConfig
from app.llm.config import ConfigError, ConfigManager

logger = logging.getLogger(__name__)

bp = flask.Blueprint("settings", __name__, url_prefix="/api")

_config_manager = ConfigManager(config_dir=Path("data"))

# ---------------------------------------------------------------------------
# Default settings — agent configs and provider defaults
# ---------------------------------------------------------------------------

_DEFAULT_SETTINGS: dict = {
    # DM agent
    "dm_max_tokens": 4096,
    "dm_temperature": 0.8,
    "dm_timeout": 300,
    # NPC agent
    "npc_max_tokens": 1024,
    "npc_temperature": 0.8,
    "npc_timeout": 300,
    # Summarizer agent
    "summarizer_max_tokens": 4096,
    "summarizer_temperature": 0.3,
    "summarizer_timeout": 300,
    # Provider defaults
    "base_url": "http://localhost:11434",
    "model": "llama3.2",
    "provider_type": "ollama",
    "api_key": None,
    "timeout": 300,
    "max_tokens": None,
    "temperature": None,
}

_PROVIDER_FIELDS = [
    "base_url",
    "model",
    "provider_type",
    "api_key",
    "timeout",
    "max_tokens",
    "temperature",
]

_AGENT_PREFIXES = ["dm_", "npc_", "summarizer_"]


def _get_merged_settings() -> dict:
    """Return default settings merged with any saved provider config.

    If a ``default`` provider config exists in ConfigManager, its values
    for the provider-level fields (``base_url``, ``model``, etc.)
    override the hardcoded defaults.  Agent-specific prefixed fields
    (``dm_max_tokens``, etc.) are **not** affected by the saved config.
    """
    settings = dict(_DEFAULT_SETTINGS)
    try:
        saved = _config_manager.get_config("default")
        for key in _PROVIDER_FIELDS:
            val = getattr(saved, key, None)
            if val is not None:
                settings[key] = val
            elif key == "api_key":
                settings[key] = None
    except ConfigError:
        # No saved config — keep the hardcoded defaults
        pass
    return settings


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------


@bp.route("/settings", methods=["GET"])
def get_settings() -> tuple[flask.Response, int] | flask.Response:
    """Return current settings, merging defaults with any saved config.

    Returns
    -------
    JSON with ``ok`` and ``settings`` dict containing all flat settings.
    """
    settings = _get_merged_settings()
    return jsonify({"ok": True, "settings": settings})


# ---------------------------------------------------------------------------
# POST /api/settings
# ---------------------------------------------------------------------------


@bp.route("/settings", methods=["POST"])
def save_settings() -> tuple[flask.Response, int] | flask.Response:
    """Update settings and persist the provider config to disk.

    Accepts a flat JSON dict with any subset of settings keys.  Only
    provided keys are updated; missing keys retain their current values.

    Validates:
      - ``*_max_tokens`` / ``max_tokens``: positive integer (or ``null``
        for the bare ``max_tokens`` field)
      - ``*_temperature`` / ``temperature``: float between 0 and 2
        (or ``null`` for bare ``temperature``)
      - ``*_timeout`` / ``timeout``: positive integer

    Returns
    -------
    JSON with ``ok`` and full ``settings`` dict on success.

    Errors
    ------
    400
        If the body is not valid JSON, or if any field fails validation.
    """
    if not request.is_json:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON body"}), 400

    # ---- Validation -------------------------------------------------------
    errors: dict[str, str] = {}

    for prefix in _AGENT_PREFIXES:
        _validate_agent_field(data, prefix, "max_tokens", errors, allow_null=False)
        _validate_agent_field(data, prefix, "temperature", errors, allow_null=False)
        _validate_agent_field(data, prefix, "timeout", errors, allow_null=False)

    # Bare provider fields
    _validate_agent_field(data, "", "max_tokens", errors, allow_null=True)
    _validate_agent_field(data, "", "temperature", errors, allow_null=True)
    _validate_agent_field(data, "", "timeout", errors, allow_null=False)

    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    # ---- Merge & persist --------------------------------------------------
    current = _get_merged_settings()
    current.update(data)

    # Build a ProviderConfig from the provider-level fields
    provider_kwargs: dict = {}
    for key in _PROVIDER_FIELDS:
        if key in current:
            provider_kwargs[key] = current[key]

    try:
        config = ProviderConfig(**provider_kwargs)
        _config_manager.save_config(config, name="default")
    except (ConfigError, ValueError, TypeError) as e:
        logger.warning("Failed to save provider config: %s", e)
        return (
            jsonify({"ok": False, "error": f"Failed to save settings: {e}"}),
            400,
        )

    # Return the full merged state from memory (avoids a redundant
    # filesystem read that could be stale or mocked in tests).
    return jsonify({"ok": True, "settings": current})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_agent_field(
    data: dict,
    prefix: str,
    field: str,
    errors: dict[str, str],
    *,
    allow_null: bool,
) -> None:
    """Validate a single settings field, appending to *errors* if invalid.

    Parameters
    ----------
    data :
        The raw request data dict.
    prefix :
        Agent prefix (e.g. ``"dm_"``) or ``""`` for bare fields.
    field :
        Field name (``"max_tokens"``, ``"temperature"``, ``"timeout"``).
    errors :
        Mutable dict of field -> error message being accumulated.
    allow_null :
        If ``True``, a ``None`` value is considered valid (used for bare
        ``max_tokens`` and ``temperature`` which are optional).
    """
    key = f"{prefix}{field}"
    if key not in data:
        return

    val = data[key]

    if allow_null and val is None:
        return

    if field in ("max_tokens", "timeout"):
        if not isinstance(val, int) or val <= 0:
            errors[key] = "Must be a positive integer"
    elif field == "temperature":
        if not isinstance(val, (int, float)) or val < 0 or val > 2:
            errors[key] = "Must be between 0 and 2"
