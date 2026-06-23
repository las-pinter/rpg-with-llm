"""JSON Schema for Creature — version 1.0.0."""

CREATURE_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://tarragon.app/schemas/creature/v1.0.0",
    "title": "Creature",
    "description": "A creature (enemy/NPC) stat block.",
    "version": "1.0.0",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "type": {
            "type": "string",
            "enum": [
                "beast",
                "humanoid",
                "monstrosity",
                "dragon",
                "undead",
                "fiend",
                "celestial",
                "fey",
                "elemental",
                "construct",
                "plant",
                "ooze",
            ],
        },
        "level": {"type": "integer", "minimum": 0},
        "abilities": {
            "type": "object",
            "properties": {
                "STR": {"type": "integer"},
                "DEX": {"type": "integer"},
                "CON": {"type": "integer"},
                "INT": {"type": "integer"},
                "WIS": {"type": "integer"},
                "CHA": {"type": "integer"},
            },
            "required": ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
        },
        "ac": {"type": "integer", "minimum": 1},
        "hp": {"type": "integer", "minimum": 1},
        "speed": {"type": "integer", "minimum": 0},
    },
    "required": ["name", "type", "abilities"],
}


def validate_creature(data: dict) -> list[str]:
    """Validate *data* against the Creature schema.

    Returns a list of error messages. An empty list means valid.
    """
    errors: list[str] = []
    valid_types = {
        "beast",
        "humanoid",
        "monstrosity",
        "dragon",
        "undead",
        "fiend",
        "celestial",
        "fey",
        "elemental",
        "construct",
        "plant",
        "ooze",
    }

    if not isinstance(data.get("name"), str):
        errors.append("name must be a string")

    if data.get("type") not in valid_types:
        errors.append(
            f"type must be one of {sorted(valid_types)}, got {data.get('type')!r}"
        )

    # Abilities
    abilities = data.get("abilities", {})
    if not isinstance(abilities, dict):
        errors.append("abilities must be an object")
    else:
        for abil in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
            if abil not in abilities:
                errors.append(f"Missing required ability: {abil}")

    for field, expected_type in [("ac", int), ("hp", int), ("level", int)]:
        val = data.get(field)
        if val is not None and not isinstance(val, expected_type):
            errors.append(f"{field} must be an integer, got {type(val).__name__}")

    return errors
