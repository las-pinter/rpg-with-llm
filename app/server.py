"""Flask server for the LLM-Powered RPG.

Provides REST API endpoints for the game, starting with a health
check endpoint for LLM provider connectivity.
"""

from __future__ import annotations

from flask import Flask, jsonify, request

from app.llm.ollama import OllamaProvider

app = Flask(__name__)


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
