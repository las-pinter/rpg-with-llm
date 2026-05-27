"""Route registration — registers all API blueprints with a Flask app.

Import ``register_routes(app)`` from your application factory or
server entry point to wire up every route module at once.
"""

from __future__ import annotations

import flask as flask


def register_routes(app: flask.Flask) -> None:  # type: ignore[name-defined]
    """Register all route blueprints with the given Flask app."""
    from app.routes.characters import bp as characters_bp
    from app.routes.game import bp as game_bp
    from app.routes.health import bp as health_bp
    from app.routes.saves import bp as saves_bp
    from app.routes.settings import bp as settings_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(saves_bp)
    app.register_blueprint(characters_bp)
    app.register_blueprint(game_bp)
    app.register_blueprint(settings_bp)
