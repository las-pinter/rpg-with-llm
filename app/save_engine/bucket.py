from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Bucket:
    """Represents a persistent entity with its own schema and serialization logic."""

    schema_name: str
    version: str
    schema: dict[str, Any]
    serializer: Callable[[Any], dict]
    deserializer: Callable[[dict], Any]
