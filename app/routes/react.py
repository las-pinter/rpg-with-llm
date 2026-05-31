"""React SPA route for the strangler fig migration.

Serves the React production build at ``/new/`` while the old SPA
continues serving at ``/`` without disruption.
"""

from __future__ import annotations

import logging
from pathlib import Path

import flask as flask
from flask import send_from_directory

logger = logging.getLogger(__name__)

bp = flask.Blueprint("react", __name__)

_REACT_DIST = Path(__file__).resolve().parent.parent.parent / "client" / "dist"


@bp.route("/new/")
@bp.route("/new/<path:path>")
def serve_react(path: str = "") -> flask.Response:
    """Serve the React SPA production build.

    If a path is provided and the file exists in the build directory,
    it's served directly.  Otherwise, ``index.html`` is returned to
    support client-side routing.
    """
    if path:
        target = _REACT_DIST / path
        if target.is_file():
            return send_from_directory(str(_REACT_DIST), path)
    return send_from_directory(str(_REACT_DIST), "index.html")
