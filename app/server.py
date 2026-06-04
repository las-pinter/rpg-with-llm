"""Flask server for the LLM-Powered RPG.

Creates the Flask application and registers all route blueprints via
``app.routes.register_routes()``.
"""

from __future__ import annotations

import flask as flask

from app.routes import register_routes

app = flask.Flask(__name__)
register_routes(app)
