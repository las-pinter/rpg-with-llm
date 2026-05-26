"""Health check and model-listing API routes.

Provides ``POST /api/health`` for provider connectivity checks and
``POST /api/models`` for listing available models from an LLM backend.
"""

from __future__ import annotations

import logging

import flask as flask
from flask import jsonify, request

from app.llm.base import (
    get_cached_models,
    set_cached_models,
)
from app.llm.config import ProviderConfig, create_provider

logger = logging.getLogger(__name__)

bp = flask.Blueprint("health", __name__, url_prefix="/api")


@bp.route("/health", methods=["POST"])
def health_check() -> tuple[flask.Response, int] | flask.Response:
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
        return (
            jsonify({"ok": False, "error": "base_url and model are required"}),
            400,
        )

    api_key = data.get("api_key")
    provider_type = str(data.get("provider_type") or "").strip() or "ollama"

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


@bp.route("/models", methods=["POST"])
def list_models() -> tuple[flask.Response, int] | flask.Response:
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
        return (
            jsonify({"ok": False, "error": "Invalid JSON body", "models": []}),
            400,
        )

    data = request.get_json(silent=True)
    if data is None:
        return (
            jsonify({"ok": False, "error": "Invalid JSON body", "models": []}),
            400,
        )

    base_url = str(data.get("base_url") or "").strip()
    model = str(data.get("model") or "").strip()

    if not base_url or not model:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "base_url and model are required",
                    "models": [],
                }
            ),
            400,
        )

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
