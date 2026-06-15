"""React SPA route — serves the production build at ``/``.

Serves the React production build as the primary frontend at ``/``.
Any path that doesn't match an API route falls through to React's
``index.html`` for client-side routing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import flask as flask
from flask import send_from_directory

logger = logging.getLogger(__name__)

bp = flask.Blueprint("react", __name__)

_REACT_DIST = (Path(__file__).resolve().parent.parent.parent / "client" / "dist").resolve()


@bp.route("/")
@bp.route("/<path:path>")
def serve_react(path: str = "") -> flask.Response:
    """Serve the React SPA production build.

    If a path is provided and the file exists in the build directory,
    it's served directly.  API routes are intentionally not caught
    here — they're handled by their own blueprints and will 404
    through to this handler only if no blueprint matches.
    Otherwise, ``index.html`` is returned to support client-side
    routing.
    """
    # Don't catch API routes — let other blueprints handle them
    if path and path.startswith("api/"):
        return flask.abort(404)

    safe_path = ""
    if path:
        requested = Path(path).as_posix().lstrip("/")
        requested_path = Path(requested)
        if not requested or requested_path.is_absolute() or any(part == ".." for part in requested_path.parts):
            return flask.abort(404)
        safe_path = requested

    # Try to serve the exact file (e.g., assets/index-abc.js)
    if safe_path:
        candidate = (_REACT_DIST / safe_path).resolve(strict=False)
        try:
            rel_candidate = candidate.relative_to(_REACT_DIST)
        except ValueError:
            rel_candidate = None
        if rel_candidate is not None and candidate.is_file():
            return send_from_directory(str(_REACT_DIST), str(rel_candidate))
    # Everything else gets index.html for client-side routing
    return send_from_directory(str(_REACT_DIST), "index.html")
