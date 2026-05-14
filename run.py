"""Entry point for the LLM-Powered RPG.

Run this module to start the Flask development server::

    python run.py
"""

from __future__ import annotations

from app.server import app

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
