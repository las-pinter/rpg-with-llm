"""
State Change Validator — Phase 3, Task 3.3.

Validates and applies structured state changes proposed by the DM agent.
Changes arrive as a list of dicts with action/path/value keys.

Typical usage::

    from app.world.validator import validate_state_changes, apply_changes

    changes = [
        {"action": "set", "path": "current_location", "value": "dark_forest"},
        {"action": "append", "path": "inventory", "value": "magic_sword"},
    ]
    errors = validate_state_changes(changes)
    if not errors:
        new_state = apply_changes(old_state, changes)
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from app.world.model import DMNotes, WorldState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Valid action types the DM agent may emit.
VALID_ACTIONS = frozenset({"set", "add", "remove", "append"})

# Schema entry: {type, mutability, description}
# mutability:
#   "settable" — can use the "set" action to replace the whole field
#   "mutable"  — dict/list field, supports add/remove/append
#   "immutable" — read-only, no actions allowed
FIELD_SCHEMA: dict[str, dict[str, Any]] = {
    "version": {
        "type": str,
        "mutability": "immutable",
        "description": "Schema version",
    },
    "character_id": {
        "type": (str, type(None)),
        "mutability": "settable",
        "description": "Linked character ID",
    },
    "current_location": {
        "type": str,
        "mutability": "settable",
        "description": "Current location ID",
    },
    "active_npcs": {
        "type": dict,
        "mutability": "mutable",
        "description": "Active NPCs keyed by ID",
    },
    "locations": {
        "type": dict,
        "mutability": "mutable",
        "description": "Location definitions",
    },
    "quests": {
        "type": dict,
        "mutability": "mutable",
        "description": "Active/completed/failed quests",
    },
    "faction_standings": {
        "type": dict,
        "mutability": "mutable",
        "description": "Faction reputation standings",
    },
    "inventory": {
        "type": list,
        "mutability": "mutable",
        "description": "Player inventory items",
    },
    "dm_notes": {
        "type": DMNotes,
        "mutability": "mutable",
        "description": "DM secret notes — plot_threads, secrets, future_plans",
    },
    "turn_count": {
        "type": int,
        "mutability": "settable",
        "description": "Number of turns played",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_path(path: str) -> tuple[str, str | None]:
    """Parse a dot-notation path into (field_name, sub_key).

    For top-level fields like ``"current_location"`` the result is
    ``("current_location", None)``.  For nested paths like
    ``"active_npcs.goblin_01"`` the result is ``("active_npcs", "goblin_01")``.

    Only the first dot is split — deeper nesting is preserved in the
    sub_key for future use.

    Args:
        path: A dot-notation path string.

    Returns:
        A tuple of ``(field_name, sub_key)``.
    """
    parts = path.split(".", 1)
    field_name = parts[0]
    sub_key = parts[1] if len(parts) > 1 else None
    return field_name, sub_key


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_state_changes(
    changes: list[dict[str, Any]],
    state: WorldState | None = None,
) -> list[str]:
    """Validate a list of state change operations.

    Each change dict **must** have ``"action"``, ``"path"``, and
    ``"value"`` keys.  Every change is checked against the ``FIELD_SCHEMA``
    for valid action, known path, allowed mutability, and correct value type.

    Args:
        changes: List of change dicts to validate.
        state: Optional current ``WorldState`` for context (reserved for
            future use; currently unused).

    Returns:
        A list of error message strings.  An empty list means all changes
        are valid.
    """
    errors: list[str] = []

    logger.debug("validate_state_changes: %d change(s) to validate", len(changes))

    for i, change in enumerate(changes):
        if not isinstance(change, dict):
            errors.append(f"Change #{i}: expected a dict, got {type(change).__name__}")
            continue

        action = change.get("action")
        path = change.get("path")
        value = change.get("value")  # noqa: F841

        # --- Validate action ---
        if not isinstance(action, str):
            errors.append(
                f"Change #{i}: 'action' must be a string, got {type(action).__name__}"
            )
            continue

        if action not in VALID_ACTIONS:
            errors.append(f"Change #{i}: unknown action {action!r}")
            continue

        # --- Validate path ---
        if not isinstance(path, str):
            errors.append(
                f"Change #{i}: 'path' must be a string, got {type(path).__name__}"
            )
            continue

        field_name, _sub_key = resolve_path(path)

        if field_name not in FIELD_SCHEMA:
            errors.append(f"Change #{i}: unknown field {field_name!r}")
            continue

        field_schema = FIELD_SCHEMA[field_name]
        mutability = field_schema["mutability"]
        field_type = field_schema["type"]

        # --- Action-specific rules ---
        if action == "set":
            if mutability not in ("settable",):
                errors.append(
                    f"Change #{i}: field {field_name!r} is not settable "
                    f"(mutability={mutability!r})"
                )
                continue

            if not isinstance(value, field_type):
                errors.append(
                    f"Change #{i}: type mismatch for field {field_name!r} "
                    f"— expected {_type_name(field_type)}, "
                    f"got {type(value).__name__}"
                )
                continue

        elif action == "add":
            if mutability != "mutable":
                errors.append(
                    f"Change #{i}: cannot add to non-mutable field {field_name!r}"
                )
                continue

            if field_type is not dict and field_type is not DMNotes:
                errors.append(
                    f"Change #{i}: field {field_name!r} is not a dict or "
                    f"DMNotes, cannot use 'add'"
                )
                continue

            if not isinstance(value, dict):
                errors.append(
                    f"Change #{i}: 'add' requires a dict value, "
                    f"got {type(value).__name__}"
                )
                continue

        elif action == "remove":
            if mutability != "mutable":
                errors.append(
                    f"Change #{i}: cannot remove from non-mutable field {field_name!r}"
                )
                continue

            # For dict fields, value must be a string key
            if field_type is dict and not isinstance(value, str):
                errors.append(
                    f"Change #{i}: 'remove' from dict field "
                    f"{field_name!r} requires a string key, "
                    f"got {type(value).__name__}"
                )
                continue

            # For DMNotes fields, value must be a dict
            if field_type is DMNotes and not isinstance(value, dict):
                errors.append(
                    f"Change #{i}: 'remove' from DMNotes field "
                    f"{field_name!r} requires a dict value, "
                    f"got {type(value).__name__}"
                )
                continue

        elif action == "append":
            if mutability != "mutable":
                errors.append(
                    f"Change #{i}: cannot append to non-mutable field {field_name!r}"
                )
                continue

            if field_type is not list:
                errors.append(
                    f"Change #{i}: field {field_name!r} is not a list, "
                    f"cannot use 'append'"
                )
                continue

    if errors:
        logger.debug(
            "validate_state_changes: %d error(s) found: %s", len(errors), errors[:3]
        )
    else:
        logger.debug("validate_state_changes: all %d change(s) valid", len(changes))

    return errors


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def apply_changes(state: WorldState, changes: list[dict[str, Any]]) -> WorldState:
    """Apply a list of **already-validated** state changes to *state*.

    Returns a **new** ``WorldState`` instance; the original is never mutated.
    Uses :func:`dataclasses.replace` internally.

    .. caution::
        This function assumes changes have been validated by
        :func:`validate_state_changes`.  Passing invalid changes may
        produce unexpected results or runtime errors.

    Note:
        For nested dataclass dict fields (locations, quests, faction_standings),
        raw dict values added via "add" action will NOT be automatically
        converted to dataclass instances. The caller must ensure values are
        proper dataclass dicts or reconstruct them afterward.

    Note:
        The "remove" action on list fields removes ALL occurrences of the
        value, not just the first. This differs from list.remove() which
        only removes the first occurrence.

    Args:
        state: The current ``WorldState`` to apply changes to.
        changes: List of validated change dicts.

    Returns:
        A new ``WorldState`` with all changes applied.
    """
    result = state
    logger.debug("apply_changes: applying %d change(s)", len(changes))

    for change in changes:
        action = change["action"]
        path = change["path"]
        value = change["value"]

        field_name, _sub_key = resolve_path(path)
        current = getattr(result, field_name)

        if action == "set":
            result = dataclasses.replace(result, **{field_name: value})  # type: ignore[arg-type]

        elif action == "add":
            # dm_notes is a dataclass, handle specially to preserve type
            if field_name == "dm_notes":
                current_dm: DMNotes = current
                merged: dict[str, Any] = {
                    "plot_threads": list(current_dm.plot_threads),
                    "secrets": list(current_dm.secrets),
                    "future_plans": list(current_dm.future_plans),
                }
                if isinstance(value, dict):
                    for k, v in value.items():
                        if (
                            k in merged
                            and isinstance(merged[k], list)
                            and isinstance(v, list)
                        ):
                            merged[k].extend(v)
                        else:
                            merged[k] = v
                new_value: Any = DMNotes(**merged)
            elif isinstance(current, dict):
                new_value = {**current, **value}
            else:
                new_value = value
            result = dataclasses.replace(result, **{field_name: new_value})  # type: ignore[arg-type]

        elif action == "remove":
            # dm_notes is a dataclass, handle specially to preserve type
            if field_name == "dm_notes":
                current_dm: DMNotes = current
                merged = {
                    "plot_threads": list(current_dm.plot_threads),
                    "secrets": list(current_dm.secrets),
                    "future_plans": list(current_dm.future_plans),
                }
                if isinstance(value, dict):
                    for k, v in value.items():
                        if k in merged and isinstance(merged[k], list):
                            if isinstance(v, list):
                                for item in v:
                                    if item in merged[k]:
                                        merged[k].remove(item)
                            elif v in merged[k]:
                                merged[k].remove(v)
                new_value = DMNotes(**merged)
            elif isinstance(current, dict):
                new_value = {k: v for k, v in current.items() if k != value}
            elif isinstance(current, list):
                new_value = [item for item in current if item != value]
            else:
                new_value = current
            result = dataclasses.replace(result, **{field_name: new_value})  # type: ignore[arg-type]

        elif action == "append":
            new_list = list(current) + [value]
            result = dataclasses.replace(result, **{field_name: new_list})  # type: ignore[arg-type]

    logger.debug("apply_changes: %d change(s) applied successfully", len(changes))
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _type_name(t: Any) -> str:
    """Return a human-friendly name for a type (or tuple of types)."""
    if isinstance(t, tuple):
        return " | ".join(_type_name(tt) for tt in t)
    if t is type(None):
        return "None"
    if hasattr(t, "__name__"):
        return t.__name__
    return str(t)
