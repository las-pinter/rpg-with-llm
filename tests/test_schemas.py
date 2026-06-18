import json
from jsonschema import validate
from app.save_engine.schemas import SCHEMA_REGISTRY


def test_schemas():
    test_cases = [
        (
            "npc",
            {
                "id": "npc-1",
                "name": "Gorten",
                "faction": "Guardians",
                "health": "one hundred",
                "personality": "Grumpy",
                "stats": {
                    "strength": 10,
                    "dexterity": 8,
                    "intelligence": 7,
                    "wisdom": 9,
                    "charisma": 5,
                },
            },
        ),
        (
            "item",
            {
                "id": "item-1",
                "name": "Healing Potion",
                "type": "consumable",
                "quantity": 5,
                "properties": {"healing_amount": 50},
            },
        ),
        (
            "place",
            {
                "id": "place-1",
                "name": "The Rusty Tankard",
                "description": "A cozy tavern.",
                "exits": ["north", "south"],
                "tags": ["safe_zone", "tavern"],
            },
        ),
        (
            "enemy",
            {
                "id": "enemy-1",
                "name": "Goblin Scout",
                "stats": {"health": 30, "attack": 5, "defense": 2},
                "loot": [{"item_id": "gold"}],
                "abilities": ["Sneak Attack"],
            },
        ),
        (
            "spell",
            {
                "id": "spell-1",
                "name": "Fireball",
                "school": "Evocation",
                "level": 3,
                "effects": [{"type": "damage", "amount": 20}],
            },
        ),
        (
            "quest",
            {
                "id": "quest-1",
                "name": "Save the Village",
                "description": "Protect the villagers from goblins.",
                "status": "in_progress",
                "objectives": [{"id": "obj-1", "desc": "Defeat 5 goblins"}],
            },
        ),
        (
            "book_note",
            {
                "id": "book-1",
                "title": "Ancient History",
                "content": "The world was created by...",
                "type": "history",
            },
        ),
        (
            "injury",
            {
                "id": "inj-1",
                "name": "Broken Arm",
                "effect": "-50% strength",
                "duration": 3,
                "severity": 2.5,
            },
        ),
        (
            "flag_event",
            {
                "id": "flag-1",
                "name": "Dragon Defeated",
                "type": "world_state",
                "value": True,
                "turn": 50,
            },
        ),
        (
            "other",
            {
                "id": "other-1",
                "name": "Mystery Box",
                "payload": {"secret_content": "Surprise!"},
            },
        ),
    ]

    for schema_name, data in test_cases:
        try:
            validate(instance=data, schema=SCHEMA_REGISTRY[schema_name])
            print(f"✓ {schema_name}: Valid")
        except Exception as e:
            print(f"✗ {schema_name}: Invalid - {e}")


if __name__ == "__main__":
    test_schemas()
