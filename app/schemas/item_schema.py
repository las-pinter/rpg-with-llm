"""JSON Schema for Item — version 1.0.0."""

ITEM_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://tarragon.app/schemas/item/v1.0.0",
    "title": "Item",
    "description": "An item in a character's inventory.",
    "version": "1.0.0",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string", "minLength": 1},
        "quantity": {"type": "integer", "minimum": 1},
        "item_type": {
            "type": "string",
            "enum": [
                "WEAPON",
                "ARMOR",
                "CONSUMABLE",
                "TOOL",
                "CONTAINER",
                "QUEST",
                "MISC",
            ],
        },
        "properties": {"type": "object"},
        "description": {"type": "string"},
        "weight": {"type": "number", "minimum": 0},
        "value": {"type": "integer", "minimum": 0},
    },
    "required": [
        "id",
        "name",
        "quantity",
        "item_type",
        "properties",
        "description",
        "weight",
        "value",
    ],
}


def validate_item(data: dict) -> list[str]:
    """Validate *data* against the Item schema.

    Returns a list of error messages. An empty list means valid.
    """
    errors: list[str] = []
    valid_types = {
        "WEAPON",
        "ARMOR",
        "CONSUMABLE",
        "TOOL",
        "CONTAINER",
        "QUEST",
        "MISC",
    }

    # Required fields
    for field in (
        "id",
        "name",
        "quantity",
        "item_type",
        "properties",
        "description",
        "weight",
        "value",
    ):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if not isinstance(data.get("name"), str) or not data.get("name", "").strip():
        errors.append("name must be a non-empty string")

    if data.get("item_type") not in valid_types:
        errors.append(
            f"item_type must be one of {sorted(valid_types)}, got {data.get('item_type')!r}"  # noqa: E501
        )

    qty = data.get("quantity")
    if isinstance(qty, int) and qty < 1:
        errors.append(f"quantity must be >= 1, got {qty}")

    weight = data.get("weight")
    if isinstance(weight, (int, float)) and weight < 0:
        errors.append(f"weight must be >= 0, got {weight}")

    return errors
