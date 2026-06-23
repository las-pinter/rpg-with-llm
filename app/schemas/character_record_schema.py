"""JSON Schema for CharacterRecord — version 1.0.0."""

CHARACTER_RECORD_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://tarragon.app/schemas/character_record/v1.0.0",
    "title": "CharacterRecord",
    "description": "Player character record — stores only player choices, not derived stats.",  # noqa: E501
    "version": "1.0.0",
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "UUID v4"},
        "name": {"type": "string", "minLength": 1},
        "character_class": {
            "type": "string",
            "enum": ["Fighter", "Rogue", "Mage", "Cleric"],
        },
        "level": {"type": "integer", "minimum": 1, "maximum": 20},
        "abilities": {
            "type": "object",
            "properties": {
                "STR": {"type": "integer", "minimum": 1, "maximum": 30},
                "DEX": {"type": "integer", "minimum": 1, "maximum": 30},
                "CON": {"type": "integer", "minimum": 1, "maximum": 30},
                "INT": {"type": "integer", "minimum": 1, "maximum": 30},
                "WIS": {"type": "integer", "minimum": 1, "maximum": 30},
                "CHA": {"type": "integer", "minimum": 1, "maximum": 30},
            },
            "required": ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
        },
        "skills": {"type": "array", "items": {"type": "string"}},
        "resources": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "value": {"type": "integer", "minimum": 0},
                    "max": {"type": ["integer", "string"]},
                    "short_rest_recovery": {"type": "string"},
                    "long_rest_recovery": {"type": "string"},
                },
                "required": [
                    "value",
                    "max",
                    "short_rest_recovery",
                    "long_rest_recovery",
                ],
            },
        },
        "inventory": {
            "type": "array",
            "items": {"$ref": "item_schema.json"},
        },
        "equipped_items": {"type": "array", "items": {"type": "string"}},
        "gold": {"type": "integer", "minimum": 0},
        "xp": {"type": "integer", "minimum": 0},
        "appearance": {"type": "string"},
        "personality": {"type": "string"},
        "backstory": {"type": "string"},
        "hooks": {"type": "array", "items": {"type": "string"}},
        "created_at": {"type": "string", "format": "date-time"},
    },
    "required": [
        "name",
        "character_class",
        "level",
        "abilities",
        "skills",
        "resources",
        "gold",
        "xp",
    ],
}


def validate_character_record(data: dict) -> list[str]:
    """Validate *data* against the CharacterRecord schema.

    Returns a list of error messages. An empty list means the data is valid.
    """
    errors: list[str] = []

    # Check required top-level fields
    required = {
        "name",
        "character_class",
        "level",
        "abilities",
        "skills",
        "resources",
        "gold",
        "xp",
    }
    missing = required - set(data.keys())
    if missing:
        errors.append(f"Missing required fields: {', '.join(sorted(missing))}")

    # Type checks
    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        errors.append("name must be a non-empty string")

    if data.get("character_class") not in ("Fighter", "Rogue", "Mage", "Cleric"):
        errors.append(
            f"character_class must be one of Fighter, Rogue, Mage, Cleric, got {data.get('character_class')!r}"  # noqa: E501
        )

    level = data.get("level")
    if not isinstance(level, int) or level < 1 or level > 20:
        errors.append(f"level must be an integer 1-20, got {level!r}")

    # Abilities check
    abilities = data.get("abilities", {})
    for abil in ("STR", "DEX", "CON", "INT", "WIS", "CHA"):
        val = abilities.get(abil)
        if not isinstance(val, int) or val < 1 or val > 30:
            errors.append(f"abilities.{abil} must be an integer 1-30, got {val!r}")

    # Resources check
    resources = data.get("resources", {})
    if not isinstance(resources, dict):
        errors.append("resources must be a dict")
    else:
        for key, resource in resources.items():
            if not isinstance(resource, dict):
                errors.append(f"resources.{key} must be an object")
                continue
            for field in ("value", "max", "short_rest_recovery", "long_rest_recovery"):
                if field not in resource:
                    errors.append(f"resources.{key} missing required field: {field}")

    return errors
