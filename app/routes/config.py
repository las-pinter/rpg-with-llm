"""Character creation config API — exposes game rules data for the frontend.

Provides ``GET /api/config/character-rules`` which returns all the
class templates, point-buy rules, ability scores, and assisted creation
questions that the frontend needs to build a character.  This lets the
frontend stop hardcoding these values.
"""

from __future__ import annotations

from typing import Any

import flask as flask
from flask import jsonify

from app.character.model import (
    _CLASS_TEMPLATES,
    _LEGACY_CLASS_TEMPLATES,
    ASSISTED_CREATION_QUESTIONS,
    MAX_POINTS,
    MAX_SCORE,
    MIN_SCORE,
    POINT_BUY_COST,
    STANDARD_ABILITIES,
    VALID_CLASSES,
)

bp = flask.Blueprint("config", __name__, url_prefix="/api/config")


@bp.route("/character-rules", methods=["GET"])
def get_character_rules() -> flask.Response:
    """Return all character creation game rules data.

    Returns
    -------
    JSON with ``ok`` and ``rules`` dict containing:
      - ``valid_classes`` — list of valid class names
      - ``standard_abilities`` — list of ability score names
      - ``class_templates`` — per-class default abilities, hp, ac,
        skills, inventory, gold
      - ``point_buy`` — cost table, max points, min/max scores
      - ``assisted_creation_questions`` — list of backstory prompts
    """
    # Build point_buy costs with string keys for JSON compatibility
    point_buy_costs: dict[str, int] = {str(k): v for k, v in POINT_BUY_COST.items()}

    # Make a shallow copy of class templates so we don't mutate the
    # originals if the caller later tweaks them.
    # Note: uses _LEGACY_CLASS_TEMPLATES because the frontend expects
    # hp/ac fields (not Item/ResourceData objects).
    class_templates: dict[str, dict] = {
        cls: dict(tmpl) for cls, tmpl in _LEGACY_CLASS_TEMPLATES.items()
    }

    # Build typed templates using _CLASS_TEMPLATES with serialized Items
    typed_templates: dict[str, dict[str, Any]] = {}
    for cls, tmpl in _CLASS_TEMPLATES.items():
        typed_templates[cls] = {
            **tmpl,
            "inventory": [item.to_dict() for item in tmpl["inventory"]],
            "resources": {k: v.to_dict() for k, v in tmpl["resources"].items()},
        }

    return jsonify(
        {
            "ok": True,
            "rules": {
                "valid_classes": sorted(VALID_CLASSES),
                "standard_abilities": STANDARD_ABILITIES,
                "class_templates": class_templates,
                "class_templates_typed": typed_templates,
                "point_buy": {
                    "costs": point_buy_costs,
                    "max_points": MAX_POINTS,
                    "min_score": MIN_SCORE,
                    "max_score": MAX_SCORE,
                },
                "assisted_creation_questions": list(ASSISTED_CREATION_QUESTIONS),
            },
        }
    )
