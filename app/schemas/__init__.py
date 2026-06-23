"""JSON Schema definitions for core data models.

These schemas are intended for documentation and validation purposes.
Engine code should NOT import them at runtime — they are standalone
definitions for external consumers and testing.
"""

from app.schemas.character_record_schema import (
    CHARACTER_RECORD_SCHEMA,
    validate_character_record,
)
from app.schemas.creature_schema import CREATURE_SCHEMA, validate_creature
from app.schemas.item_schema import ITEM_SCHEMA, validate_item

__all__ = [
    "CHARACTER_RECORD_SCHEMA",
    "ITEM_SCHEMA",
    "CREATURE_SCHEMA",
    "validate_character_record",
    "validate_item",
    "validate_creature",
]
