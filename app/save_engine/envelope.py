from dataclasses import dataclass, field, asdict, fields
from typing import Any, get_origin
import json
from datetime import datetime, timezone


@dataclass
class SaveEnvelope:
    save_version: str = "1.0.0"
    schema_name: str = ""
    schema_version: str = "1.0.0"
    timestamp: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    )
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the dataclass instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SaveEnvelope":
        """Create a SaveEnvelope instance from a dictionary."""
        allowed_keys = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data.items() if k in allowed_keys}
        return cls(**filtered_data)


KNOWN_SCHEMAS = {"world_state", "character", "narrative_entries", "summary", "state"}

SCHEMAS = {
    "envelope": {
        "type": "object",
        "properties": {
            "save_version": {"type": "string"},
            "schema_name": {"type": "string"},
            "schema_version": {"type": "string"},
            "timestamp": {"type": "string"},
            "payload": {"type": "object"},
        },
        "required": [
            "save_version",
            "schema_name",
            "schema_version",
            "timestamp",
            "payload",
        ],
    }
}


def validate_envelope(data: dict[str, Any]) -> list[str]:
    """Validate the envelope data against required fields and types.

    Returns a list of error messages if any validation fails.
    """
    errors = []
    # Derive required fields from dataclass fields to stay in sync
    for f in fields(SaveEnvelope):
        field_name = f.name
        expected_type = f.type
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")
        else:
            val = data[field_name]
            # Check if it's a string type and check against str
            if expected_type is str and not isinstance(val, str):
                errors.append(
                    f"Field {field_name} must be str, got {type(val).__name__}"
                )
            # Check if it's a dict-like type (e.g., dict or dict[str, Any])
            elif get_origin(expected_type) is dict and not isinstance(val, dict):
                errors.append(
                    f"Field {field_name} must be dict, got {type(val).__name__}"
                )

    # Check for unknown schema names
    if "schema_name" in data and isinstance(data["schema_name"], str):
        if data["schema_name"] == "":
            errors.append("schema_name must not be empty")
        elif data["schema_name"] not in KNOWN_SCHEMAS:
            errors.append(f"Unknown schema name: {data['schema_name']}")

    return errors
