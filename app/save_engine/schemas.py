import json
from typing import Any, Dict, List
from jsonschema import validate, ValidationError, SchemaError

# JSON Schema definitions for various RPG entities
NPC_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "npc",
    "title": "Non-Player Character (NPC)",
    "description": "Defines a non-player character in the game world.",
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "Unique identifier for the NPC"},
        "name": {"type": "string", "description": "Display name of the NPC"},
        "faction": {"type": "string", "description": "The faction the NPC belongs to"},
        "health": {
            "type": "integer",
            "minimum": 0,
            "description": "Current health points",
        },
        "personality": {
            "type": "string",
            "description": "Brief description of personality traits",
        },
        "stats": {
            "type": "object",
            "properties": {
                "strength": {"type": "integer"},
                "dexterity": {"type": "integer"},
                "intelligence": {"type": "integer"},
                "wisdom": {"type": "integer"},
                "charisma": {"type": "integer"},
            },
            "required": ["strength", "dexterity", "intelligence", "wisdom", "charisma"],
        },
    },
    "required": ["id", "name", "faction", "health"],
    "additionalProperties": False,
    "version": "1.0.0",
}

ITEM_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "item",
    "title": "Item",
    "description": "Defines an item in the game world.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "type": {
            "type": "string",
            "enum": ["weapon", "armor", "consumable", "quest_item", "junk"],
        },
        "properties": {
            "type": "object",
            "description": "Specific attributes of the item (e.g., weight, damage).",
        },
        "quantity": {"type": "integer", "minimum": 1},
    },
    "required": ["id", "name", "type"],
    "additionalProperties": False,
    "version": "1.0.0",
}

PLACE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "place",
    "title": "Place",
    "description": "Defines a location in the game world.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "exits": {"type": "array", "items": {"type": "string"}},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
    "version": "1.0.0",
}

ENEMY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "enemy",
    "title": "Enemy",
    "description": "Defines a hostile entity in the game world.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "stats": {
            "type": "object",
            "properties": {
                "health": {"type": "integer"},
                "attack": {"type": "integer"},
                "defense": {"type": "integer"},
            },
        },
        "loot": {"type": "array", "items": {"type": "object"}},
        "abilities": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
    "version": "1.0.0",
}

SPELL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "spell",
    "title": "Spell",
    "description": "Defines a magical ability.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "school": {"type": "string"},
        "level": {"type": "integer"},
        "effects": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["id", "name", "level"],
    "additionalProperties": False,
    "version": "1.0.0",
}

QUEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "quest",
    "title": "Quest",
    "description": "Defines a task or objective for the player.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["not_started", "in_progress", "completed", "failed"],
        },
        "objectives": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
    "version": "1.0.0",
}

BOOK_NOTE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "book_note",
    "title": "Book Note",
    "description": "Defines a piece of lore or a note.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "content": {"type": "string"},
        "type": {"type": "string"},
    },
    "required": ["id", "title"],
    "additionalProperties": False,
    "version": "1.0.0",
}

INJURY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "injury",
    "title": "Injury",
    "description": "Defines a physical or magical affliction.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "effect": {"type": "string"},
        "duration": {"type": "integer"},
        "severity": {"type": "number"},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
    "version": "1.0.0",
}

FLAG_EVENT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "flag_event",
    "title": "Flag Event",
    "description": "Defines a world state flag or event.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "type": {"type": "string"},
        "value": {"type": ["string", "number", "boolean"]},
        "turn": {"type": "integer"},
    },
    "required": ["id", "name"],
    "additionalProperties": False,
    "version": "1.0.0",
}

OTHER_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "other",
    "title": "Other",
    "description": "Catch-all schema for miscellaneous data.",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "payload": {
            "type": "object",
            "description": "Flexible payload for arbitrary data.",
        },
    },
    "required": ["id"],
    "additionalProperties": True,
    "version": "1.0.0",
}

SCHEMA_REGISTRY = {
    "npc": NPC_SCHEMA,
    "item": ITEM_SCHEMA,
    "place": PLACE_SCHEMA,
    "enemy": ENEMY_SCHEMA,
    "spell": SPELL_SCHEMA,
    "quest": QUEST_SCHEMA,
    "book_note": BOOK_NOTE_SCHEMA,
    "injury": INJURY_SCHEMA,
    "flag_event": FLAG_EVENT_SCHEMA,
    "other": OTHER_SCHEMA,
}


def validate_entity_schema(data: Dict[str, Any], entity_type: str) -> List[str]:
    """Validates data against the registered schema for a given entity type.

    Uses jsonschema to validate the data against the schema registered
    for the given entity type.

    Args:
        data: The data to validate.
        entity_type: The type key to look up in SCHEMA_REGISTRY.

    Returns:
        A list of error messages. An empty list means validation passed.
    """
    schema = SCHEMA_REGISTRY.get(entity_type)
    if not schema:
        return [f"Unknown entity type: {entity_type}"]
    try:
        validate(instance=data, schema=schema)
        return []
    except ValidationError as e:
        return [str(e)]
    except SchemaError as e:
        return [f"Schema error: {e}"]
