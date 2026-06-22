"""Migration framework for SaveEnvelope payloads.

Provides a registry of migration functions that transform payload dicts
from one schema version to another. Migrations are chained automatically
through intermediate versions.

Migration functions MUST be **idempotent** — running them twice on the
same payload produces the same result. They MAY mutate the input dict
in place or return a new dict. They MUST NOT perform I/O or access
external state.
"""

from __future__ import annotations

from collections.abc import Callable

# Registry: (schema_name, from_version) -> (to_version, callable)
# callable signature: (payload: dict) -> dict
MIGRATIONS: dict[tuple[str, str], tuple[str, Callable[[dict], dict]]] = {}


class MigrationError(Exception):
    """Raised when a migration cannot be completed."""

    pass


def register_migration(
    schema_name: str,
    from_version: str,
    to_version: str,
    func: Callable[[dict], dict],
) -> None:
    """Register a migration function.

    Args:
        schema_name: The schema this migration applies to.
        from_version: The source version string (e.g. "1.0.0").
        to_version: The target version string (e.g. "1.1.0").
        func: A callable that takes a payload dict and returns a new
            (or mutated) payload dict.
    """
    # Validate version strings
    _parse_version(from_version)
    _parse_version(to_version)

    MIGRATIONS[(schema_name, from_version)] = (to_version, func)


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a semver string into a tuple of integers for comparison.

    Args:
        version: A version string like "1.0.0" or "1.2".

    Returns:
        A tuple of integers, e.g. (1, 0, 0).

    Raises:
        ValueError: If the version string is empty or contains non-integer
            components.
    """
    if not version or not version.strip():
        raise ValueError(f"Empty or blank version string: {version!r}")

    parts = version.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError as e:
        raise ValueError(f"Invalid version string: {version!r}") from e


def _find_migration_path(
    schema_name: str, from_version: str, to_version: str
) -> list[Callable[[dict], dict]]:
    """Find the chain of migrations from *from_version* to *to_version*.

    Walks the registered migrations step by step until the target version
    is reached.  Each step moves forward by exactly one registered
    migration.

    Args:
        schema_name: The schema to migrate.
        from_version: Starting version.
        to_version: Target version.

    Returns:
        An ordered list of migration functions to apply sequentially.

    Raises:
        MigrationError: If no migration path exists between the versions.
    """
    if _parse_version(from_version) > _parse_version(to_version):
        raise MigrationError(
            f"Cannot migrate {schema_name} from v{from_version} to v{to_version}: "
            f"from_version is newer than to_version"
        )

    if _parse_version(from_version) == _parse_version(to_version):
        return []

    path: list[Callable[[dict], dict]] = []
    current = from_version

    visited: set[str] = set()
    while current != to_version:
        if current in visited:
            raise MigrationError(
                f"Cycle detected in migration path for {schema_name} "
                f"at version v{current}"
            )
        visited.add(current)

        key = (schema_name, current)
        if key not in MIGRATIONS:
            raise MigrationError(
                f"No migration path from v{current} for schema '{schema_name}' "
                f"(target v{to_version})"
            )

        next_version, func = MIGRATIONS[key]
        path.append(func)
        current = next_version

    return path


def run_migration(
    schema_name: str,
    payload: dict,
    from_version: str,
    to_version: str,
) -> dict:
    """Run all migrations needed to get *payload* from *from_version* to *to_version*.

    Chains through intermediate versions automatically.  Each migration
    function is applied sequentially to the payload.

    Args:
        schema_name: The schema being migrated.
        payload: The data payload to transform.
        from_version: The current version of the payload.
        to_version: The target version.

    Returns:
        The transformed payload dict.

    Raises:
        MigrationError: If no migration path exists.
    """
    if _parse_version(from_version) == _parse_version(to_version):
        return payload

    functions = _find_migration_path(schema_name, from_version, to_version)
    result = payload
    for func in functions:
        result = func(result)
    return result


# ---------------------------------------------------------------------------
# Example migration: character schema v1.0.0 -> v1.1.0
# ---------------------------------------------------------------------------


def _migrate_character_v1_to_v1_1(payload: dict) -> dict:
    """Example migration: add default ``alignment`` field.

    If the payload does not already contain an ``alignment`` key, it is
    set to ``"neutral"``.
    """
    if "alignment" not in payload:
        payload["alignment"] = "neutral"
    return payload


# Register the example migration at import time so it is available whenever
# the migration module is loaded.
register_migration("character", "1.0.0", "1.1.0", _migrate_character_v1_to_v1_1)


# ---------------------------------------------------------------------------
# Migration: character schema v1.1.0 -> v1.2.0 (Character → CharacterRecord)
# ---------------------------------------------------------------------------


def _migrate_character_v1_1_to_v1_2(payload: dict) -> dict:
    """Migrate legacy Character format to CharacterRecord format.

    Converts:
    - ``hp`` / ``max_hp`` (removed) → ``resources.hp`` ResourceData
    - ``ac`` (removed) — dropped entirely (computed by derivation pipeline)
    - ``inventory`` from ``list[str]`` → ``list[dict]`` (Item format)
    - Adds ``equipped_items: []`` if missing
    - Adds ``resources`` with an ``hp`` entry if ``resources`` is missing
    """
    # Remove legacy derived fields
    payload.pop("ac", None)
    hp = payload.pop("hp", 10)
    max_hp = payload.pop("max_hp", 10)

    # Convert inventory from list[str] to list[Item dicts]
    old_inventory = payload.get("inventory", [])
    if (
        isinstance(old_inventory, list)
        and old_inventory
        and isinstance(old_inventory[0], str)
    ):
        import uuid

        new_inventory = []
        for item_name in old_inventory:
            new_inventory.append(
                {
                    "id": str(uuid.uuid4()),
                    "name": item_name,
                    "quantity": 1,
                    "item_type": "misc",
                    "properties": {},
                    "description": "",
                    "weight": 0.0,
                    "value": 0,
                }
            )
        payload["inventory"] = new_inventory

    # Add equipped_items if missing
    if "equipped_items" not in payload:
        payload["equipped_items"] = []

    # Add resources in CharacterRecord format
    if "resources" not in payload or not payload["resources"]:
        payload["resources"] = {
            "hp": {
                "value": hp,
                "max": max_hp,
                "short_rest_recovery": "none",
                "long_rest_recovery": "full",
            }
        }

    return payload


register_migration("character", "1.1.0", "1.2.0", _migrate_character_v1_1_to_v1_2)
