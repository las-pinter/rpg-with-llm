import json
import logging
from typing import Any
from pathlib import Path
from app.save_engine.schemas import validate_payload

from app.save_engine.bucket import Bucket
from app.save_engine.envelope import SaveEnvelope
from app.world.persistence import WorldStorage
from app.world.model import WorldState
from app.character.model import Character
from app.utils import atomic_write

logger = logging.getLogger(__name__)


def _validate_slug(slug: str) -> None:
    """Raise ValueError if the slug contains path-traversal characters."""
    if "/" in slug or "\\" in slug or ".." in slug:
        raise ValueError(f"Invalid slug: {slug}")


class SaveGameManager:
    """Manages the registration and serialization of various game state buckets."""

    SAVE_VERSION = "1.0.0"

    def __init__(self, data_dir: str | Path):
        # We use WorldStorage to determine the base saves directory.
        # Since we need to write files into {slug}/, we can use its logic.
        self.storage = WorldStorage(data_dir)
        self.buckets: dict[str, Bucket] = {}

    def register_bucket(self, bucket: Bucket) -> None:
        """Registers a bucket type with its schema and serialization logic."""
        self.buckets[bucket.schema_name] = bucket

    def unregister_bucket(self, schema_name: str) -> None:
        """Removes a registered bucket."""
        if schema_name in self.buckets:
            del self.buckets[schema_name]

    def save(self, slug: str, buckets_data: dict[str, Any]) -> None:
        """
        Saves multiple buckets into the {slug}/ folder.
        Each bucket is serialized, wrapped in a SaveEnvelope, and saved as a JSON file.
        """
        _validate_slug(slug)

        # Ensure the directory for this slug exists (using WorldStorage's logic)
        save_folder = self.storage.saves_dir / slug
        save_folder.mkdir(parents=True, exist_ok=True)

        for schema_name, data in buckets_data.items():
            bucket = self.buckets.get(schema_name)
            if bucket is None:
                logger.warning(
                    "Skipping unregistered bucket '%s' during save — no data written",
                    schema_name,
                )
                continue

            serialized_data = bucket.serializer(data)

            # Validate the serialized data against the bucket's schema before writing
            schema_errors = validate_payload(serialized_data, bucket.schema)
            if schema_errors:
                raise ValueError(
                    f"Validation failed for bucket '{schema_name}': {'; '.join(schema_errors)}"
                )

            envelope = SaveEnvelope(
                save_version=self.SAVE_VERSION,
                schema_name=schema_name,
                schema_version=bucket.version,
                payload=serialized_data,
            )

            file_path = save_folder / f"{schema_name}.json"
            atomic_write(file_path, envelope.to_dict(), indent=2)

    def load(self, slug: str) -> dict[str, Any]:
        """
        Loads all buckets from the {slug}/ folder.
        Unwraps envelopes, validates against schemas, and deserializes data.
        """
        _validate_slug(slug)

        save_folder = self.storage.saves_dir / slug
        if not save_folder.is_dir():
            raise FileNotFoundError(f"Save '{slug}' folder not found at {save_folder}")

        loaded_data: dict[str, Any] = {}

        # List all files in the directory
        for file_path in save_folder.glob("*.json"):
            filename = file_path.name
            if filename == "index.json":
                continue

            schema_name = filename.replace(".json", "")

            bucket = self.buckets.get(schema_name)
            if bucket is None:
                # Skip unknown schemas during load as per requirements
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                envelope = SaveEnvelope.from_dict(data)

                # Validate payload against schema
                schema_errors = validate_payload(envelope.payload, bucket.schema)
                if schema_errors:
                    logger.warning(
                        "Schema validation warnings for bucket '%s': %s",
                        schema_name,
                        "; ".join(schema_errors),
                    )
                    continue

                # Deserialize
                loaded_data[schema_name] = bucket.deserializer(envelope.payload)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(
                    "Error loading bucket %s from %s: %s", schema_name, file_path, e
                )
                continue

        return loaded_data

    def list_buckets(self) -> list[str]:
        """Returns a list of all registered schema names."""
        return list(self.buckets.keys())

    def register_defaults(self) -> None:
        """Registers the default buckets for the game state."""
        # world_state
        self.register_bucket(
            Bucket(
                "world_state",
                "1.0.0",
                {
                    "type": "object",
                    "properties": {
                        "version": {"type": "string"},
                        "character_id": {"type": ["string", "null"]},
                        "character_name": {"type": "string"},
                        "current_location": {"type": "string"},
                        "active_npcs": {"type": "object"},
                        "locations": {"type": "object"},
                        "quests": {"type": "object"},
                        "faction_standings": {"type": "object"},
                        "inventory": {"type": "array", "items": {"type": "string"}},
                        "gold": {"type": "integer"},
                        "dm_notes": {"type": "object"},
                        "turn_count": {"type": "integer"},
                        "established_facts": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "story_summary": {"type": "array", "items": {"type": "string"}},
                        "technical_summary": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["version", "character_id", "character_name"],
                },
                WorldState.to_dict,
                WorldState.from_dict,
            )
        )

        # character
        self.register_bucket(
            Bucket(
                "character",
                "1.0.0",
                {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "appearance": {"type": "string"},
                        "personality": {"type": "string"},
                        "backstory": {"type": "string"},
                        "hooks": {"type": "array", "items": {"type": "string"}},
                        "character_class": {"type": "string"},
                        "level": {"type": "integer"},
                        "xp": {"type": "integer"},
                        "abilities": {"type": "object"},
                        "skills": {"type": "array", "items": {"type": "string"}},
                        "hp": {"type": "integer"},
                        "max_hp": {"type": "integer"},
                        "ac": {"type": "integer"},
                        "inventory": {"type": "array", "items": {"type": "string"}},
                        "gold": {"type": "integer"},
                    },
                    "required": ["id", "name"],
                },
                Character.to_dict,
                Character.from_dict,
            )
        )

        # narrative_entries
        self.register_bucket(
            Bucket(
                "narrative_entries",
                "1.0.0",
                {
                    "type": "object",
                    "properties": {
                        "entries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "content": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                            },
                        }
                    },
                    "required": ["entries"],
                },
                lambda x: x,
                lambda x: x,
            )
        )

        # summary
        self.register_bucket(
            Bucket(
                "summary",
                "1.0.0",
                {
                    "type": "object",
                    "properties": {
                        "technical_summary": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "story_summary": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["technical_summary", "story_summary"],
                },
                lambda x: x,
                lambda x: x,
            )
        )
