"""Flask server for the LLM-Powered RPG.

Creates the Flask application and registers all route blueprints via
``app.routes.register_routes()``.
"""

from __future__ import annotations

from pathlib import Path

import flask as flask

from app.routes import register_routes

_static_folder = str(Path(__file__).resolve().parent / "static")
app = flask.Flask(__name__, static_folder=_static_folder, static_url_path="/static")
register_routes(app)
