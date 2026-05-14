"""Tests for state change validation — Phase 3, Task 3.3."""

from __future__ import annotations

import dataclasses
from typing import Any

from app.world.model import DMNotes, WorldState
from app.world.validator import (
    FIELD_SCHEMA,
    apply_changes,
    resolve_path,
    validate_state_changes,
)

# ---------------------------------------------------------------------------
# resolve_path
# ---------------------------------------------------------------------------


class TestResolvePath:
    def test_top_level_field(self) -> None:
        assert resolve_path("current_location") == ("current_location", None)

    def test_nested_field(self) -> None:
        assert resolve_path("active_npcs.goblin_01") == (
            "active_npcs",
            "goblin_01",
        )

    def test_deeply_nested(self) -> None:
        """Only splits on the first dot — deeper nesting preserved in sub_key."""
        assert resolve_path("a.b.c") == ("a", "b.c")

    def test_single_component(self) -> None:
        assert resolve_path("inventory") == ("inventory", None)


# ---------------------------------------------------------------------------
# validate_state_changes
# ---------------------------------------------------------------------------


class TestValidateStateChanges:
    """Happy path — valid changes return no errors."""

    def test_valid_set_to_string_field(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "current_location", "value": "dark_forest"}
        ]
        assert validate_state_changes(changes) == []

    def test_valid_set_character_id(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "character_id", "value": "hero_01"}
        ]
        assert validate_state_changes(changes) == []

    def test_valid_set_character_id_to_none(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "character_id", "value": None}
        ]
        assert validate_state_changes(changes) == []

    def test_valid_set_turn_count(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "turn_count", "value": 42}
        ]
        assert validate_state_changes(changes) == []

    def test_valid_append_to_list(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "inventory", "value": "magic_sword"}
        ]
        assert validate_state_changes(changes) == []

    def test_valid_add_to_dict(self) -> None:
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "active_npcs",
                "value": {"goblin_01": {"name": "Gribbits", "health": 10}},
            }
        ]
        assert validate_state_changes(changes) == []

    def test_valid_add_to_dm_notes(self) -> None:
        """Adding to dm_notes with a dict value should be valid."""
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "dm_notes",
                "value": {"plot_threads": ["a new thread"]},
            }
        ]
        assert validate_state_changes(changes) == []

    def test_valid_remove_from_dict(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "active_npcs", "value": "goblin_01"}
        ]
        assert validate_state_changes(changes) == []

    def test_valid_remove_from_list(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "inventory", "value": "rusty_sword"}
        ]
        assert validate_state_changes(changes) == []

    def test_valid_remove_from_dm_notes(self) -> None:
        """Removing from dm_notes with a dict value should be valid."""
        changes: list[dict[str, Any]] = [
            {
                "action": "remove",
                "path": "dm_notes",
                "value": {"plot_threads": ["old thread"]},
            }
        ]
        assert validate_state_changes(changes) == []

    def test_multiple_valid_changes(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "current_location", "value": "cave"},
            {
                "action": "add",
                "path": "active_npcs",
                "value": {"bat": {"name": "Bruce", "health": 5}},
            },
            {"action": "append", "path": "inventory", "value": "torch"},
        ]
        assert validate_state_changes(changes) == []

    def test_empty_changes_list(self) -> None:
        assert validate_state_changes([]) == []

    """Error cases — invalid changes return appropriate error messages."""

    def test_reject_unknown_action(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "fly", "path": "current_location", "value": "forest"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "unknown action" in errors[0].lower()

    def test_reject_unknown_path(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "magic_power", "value": 100}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "unknown field" in errors[0].lower()

    def test_reject_immutable_field(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "version", "value": "2.0"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "immutable" in errors[0].lower() or "not settable" in errors[0]

    def test_reject_type_mismatch(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "turn_count", "value": "hello"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "type mismatch" in errors[0].lower()

    def test_reject_set_on_dict_field(self) -> None:
        """Trying to 'set' a mutable dict field should be rejected."""
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "active_npcs", "value": "not_a_dict"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "not settable" in errors[0]

    def test_reject_set_on_list_field(self) -> None:
        """Trying to 'set' a mutable list field should be rejected."""
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "inventory", "value": "sword"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "not settable" in errors[0]

    def test_reject_append_to_dict_field(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "active_npcs", "value": "goblin"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "not a list" in errors[0].lower()

    def test_reject_add_to_list_field(self) -> None:
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "inventory",
                "value": {"item": "sword"},
            }
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "not a dict" in errors[0].lower()

    def test_reject_add_with_non_dict_value(self) -> None:
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "active_npcs",
                "value": "just_a_string",
            }
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "requires a dict" in errors[0].lower()

    def test_reject_remove_with_non_string_from_dict(self) -> None:
        """Removing from a dict field must use a string key."""
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "active_npcs", "value": 42}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "string key" in errors[0].lower()

    def test_reject_remove_with_non_dict_from_dm_notes(self) -> None:
        """Removing from dm_notes must use a dict value."""
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "dm_notes", "value": "not_a_dict"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "requires a dict" in errors[0].lower()

    def test_reject_add_to_immutable_field(self) -> None:
        changes: list[dict[str, Any]] = [
            {"action": "add", "path": "version", "value": {"x": "y"}}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1

    def test_reject_missing_action_key(self) -> None:
        changes: list[dict[str, Any]] = [
            {"path": "current_location", "value": "forest"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "action" in errors[0].lower()

    def test_reject_non_dict_change(self) -> None:
        changes: list[Any] = ["not_a_dict"]
        errors = validate_state_changes(changes)  # type: ignore[arg-type]
        assert len(errors) == 1

    def test_state_parameter_is_optional(self) -> None:
        """The state parameter is optional and currently unused."""
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "current_location", "value": "cave"}
        ]
        assert validate_state_changes(changes, state=None) == []
        assert validate_state_changes(changes, state=WorldState()) == []

    # --- Edge cases: missing/empty/odd inputs ---

    def test_empty_string_path(self) -> None:
        """Empty string as path should be rejected as unknown field."""
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "", "value": "forest"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "unknown field" in errors[0].lower()

    def test_whitespace_only_path(self) -> None:
        """Whitespace-only path should be rejected as unknown field."""
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "   ", "value": "forest"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "unknown field" in errors[0].lower()

    def test_missing_path_key(self) -> None:
        """Change dict without 'path' key should be rejected."""
        changes: list[dict[str, Any]] = [{"action": "set", "value": "forest"}]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "path" in errors[0].lower()

    def test_missing_value_key_for_set(self) -> None:
        """Missing value key for set action triggers type mismatch (None)."""
        changes: list[dict[str, Any]] = [{"action": "set", "path": "turn_count"}]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "type mismatch" in errors[0].lower()

    def test_case_sensitive_action_uppercase(self) -> None:
        """Uppercase 'SET' should be rejected as unknown action."""
        changes: list[dict[str, Any]] = [
            {"action": "SET", "path": "current_location", "value": "forest"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "unknown action" in errors[0].lower()

    def test_case_sensitive_action_mixed_case(self) -> None:
        """Mixed-case 'Set' should be rejected as unknown action."""
        changes: list[dict[str, Any]] = [
            {"action": "Set", "path": "current_location", "value": "forest"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "unknown action" in errors[0].lower()

    def test_path_with_hyphens_in_subkey(self) -> None:
        """Sub-keys with hyphens should be valid."""
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "active_npcs.npc-with-hyphens",
                "value": {"id": "1"},
            }
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 0

    def test_path_with_unicode_in_subkey(self) -> None:
        """Sub-keys with unicode characters should be valid."""
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "active_npcs.npc_ünîçødê",
                "value": {"id": "1"},
            }
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 0

    def test_reject_string_instead_of_list(self) -> None:
        """Passing a string iterates char by char — each rejected."""
        errors = validate_state_changes("abc")  # type: ignore[arg-type]
        assert len(errors) == 3
        for err in errors:
            assert "expected a dict" in err.lower()

    def test_reject_remove_from_settable_field(self) -> None:
        """Remove on a settable field should be rejected."""
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "current_location", "value": "village"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "cannot remove" in errors[0].lower()

    def test_reject_remove_from_immutable_field(self) -> None:
        """Remove on an immutable field should be rejected."""
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "version", "value": "1.0"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "cannot remove" in errors[0].lower()

    def test_reject_append_to_settable_field(self) -> None:
        """Append on a settable field should be rejected."""
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "current_location", "value": "forest"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "cannot append" in errors[0].lower()

    def test_reject_append_to_immutable_field(self) -> None:
        """Append on an immutable field should be rejected."""
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "version", "value": "2.0"}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "cannot append" in errors[0].lower()

    def test_reject_set_character_id_type_mismatch(self) -> None:
        """Character_id rejects non-string, non-None types."""
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "character_id", "value": 42}
        ]
        errors = validate_state_changes(changes)
        assert len(errors) == 1
        assert "type mismatch" in errors[0].lower()
        # Error should mention both accepted types
        assert "str" in errors[0]
        assert "None" in errors[0]


# ---------------------------------------------------------------------------
# apply_changes
# ---------------------------------------------------------------------------


class TestApplyChanges:
    """Happy path — applying valid changes produces correct results."""

    def test_apply_single_set(self) -> None:
        state = WorldState(current_location="starting_village")
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "current_location", "value": "dark_forest"}
        ]
        result = apply_changes(state, changes)
        assert result.current_location == "dark_forest"

    def test_apply_set_character_id(self) -> None:
        state = WorldState(character_id=None)
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "character_id", "value": "hero_42"}
        ]
        result = apply_changes(state, changes)
        assert result.character_id == "hero_42"

    def test_apply_set_turn_count(self) -> None:
        state = WorldState(turn_count=0)
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "turn_count", "value": 42}
        ]
        result = apply_changes(state, changes)
        assert result.turn_count == 42

    def test_apply_append_to_list(self) -> None:
        state = WorldState(inventory=["rusty_sword"])
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "inventory", "value": "magic_shield"}
        ]
        result = apply_changes(state, changes)
        assert result.inventory == ["rusty_sword", "magic_shield"]

    def test_apply_append_multiple_items(self) -> None:
        state = WorldState(inventory=[])
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "inventory", "value": "sword"},
            {"action": "append", "path": "inventory", "value": "shield"},
            {"action": "append", "path": "inventory", "value": "potion"},
        ]
        result = apply_changes(state, changes)
        assert result.inventory == ["sword", "shield", "potion"]

    def test_apply_add_to_dict(self) -> None:
        state = WorldState()
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "active_npcs",
                "value": {
                    "goblin_01": {"name": "Gribbits", "health": 10},
                },
            }
        ]
        result = apply_changes(state, changes)
        assert "goblin_01" in result.active_npcs
        assert result.active_npcs["goblin_01"]["name"] == "Gribbits"
        assert result.active_npcs["goblin_01"]["health"] == 10

    def test_apply_add_multiple_keys(self) -> None:
        state = WorldState(active_npcs={"existing": {"name": "Old", "health": 1}})
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "active_npcs",
                "value": {
                    "new_01": {"name": "Newbie", "health": 5},
                    "new_02": {"name": "Newer", "health": 3},
                },
            }
        ]
        result = apply_changes(state, changes)
        assert "existing" in result.active_npcs
        assert "new_01" in result.active_npcs
        assert "new_02" in result.active_npcs
        assert result.active_npcs["existing"]["name"] == "Old"

    def test_apply_remove_from_dict(self) -> None:
        state = WorldState()
        state.active_npcs["goblin_01"] = {"name": "Gribbits", "health": 10}
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "active_npcs", "value": "goblin_01"}
        ]
        result = apply_changes(state, changes)
        assert "goblin_01" not in result.active_npcs

    def test_apply_remove_from_list(self) -> None:
        state = WorldState(inventory=["rusty_sword", "healing_potion"])
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "inventory", "value": "rusty_sword"}
        ]
        result = apply_changes(state, changes)
        assert "rusty_sword" not in result.inventory

    def test_apply_multiple_changes(self) -> None:
        state = WorldState(inventory=[], active_npcs={})
        changes: list[dict[str, Any]] = [
            {
                "action": "set",
                "path": "current_location",
                "value": "dragon_cave",
            },
            {"action": "append", "path": "inventory", "value": "magic_sword"},
            {"action": "append", "path": "inventory", "value": "shield"},
            {
                "action": "add",
                "path": "active_npcs",
                "value": {
                    "dragon": {"name": "Ignis", "health": 200},
                },
            },
        ]
        result = apply_changes(state, changes)
        assert result.current_location == "dragon_cave"
        assert result.inventory == ["magic_sword", "shield"]
        assert result.active_npcs["dragon"]["name"] == "Ignis"

    def test_empty_changes_apply(self) -> None:
        state = WorldState(current_location="village")
        result = apply_changes(state, [])
        assert result.current_location == "village"

    """Immutability — original WorldState must never be mutated."""

    def test_immutability_original_unchanged_after_set(self) -> None:
        state = WorldState(current_location="starting_village", turn_count=5)
        changes: list[dict[str, Any]] = [
            {
                "action": "set",
                "path": "current_location",
                "value": "dark_forest",
            },
            {"action": "set", "path": "turn_count", "value": 6},
        ]
        apply_changes(state, changes)
        assert state.current_location == "starting_village"
        assert state.turn_count == 5

    def test_immutability_original_unchanged_after_append(self) -> None:
        state = WorldState(inventory=["sword"])
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "inventory", "value": "shield"}
        ]
        apply_changes(state, changes)
        assert state.inventory == ["sword"]

    def test_immutability_original_unchanged_after_add(self) -> None:
        state = WorldState()
        state.active_npcs["goblin"] = {"name": "Gribbits", "health": 10}
        original_npcs = dict(state.active_npcs)
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "active_npcs",
                "value": {"orc": {"name": "Urgash", "health": 30}},
            }
        ]
        apply_changes(state, changes)
        assert state.active_npcs == original_npcs

    def test_immutability_original_unchanged_after_remove(self) -> None:
        state = WorldState(inventory=["sword", "shield", "potion"])
        orig = list(state.inventory)
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "inventory", "value": "shield"}
        ]
        apply_changes(state, changes)
        assert state.inventory == orig

    def test_immutability_dm_notes_unchanged_after_add(self) -> None:
        """Original dm_notes must not be mutated when adding."""
        state = WorldState()
        state.dm_notes.plot_threads.append("original_thread")
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "dm_notes",
                "value": {"plot_threads": ["new_thread"]},
            }
        ]
        apply_changes(state, changes)
        assert state.dm_notes.plot_threads == ["original_thread"]

    def test_apply_returns_new_instance(self) -> None:
        state = WorldState()
        result = apply_changes(
            state,
            [{"action": "set", "path": "current_location", "value": "forest"}],
        )
        assert result is not state

    # --- Edge cases: empty collections, None values, missing keys ---

    def test_apply_remove_from_empty_list(self) -> None:
        """Removing from an empty list produces an empty list."""
        state = WorldState(inventory=[])
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "inventory", "value": "nothing"}
        ]
        result = apply_changes(state, changes)
        assert result.inventory == []

    def test_apply_remove_non_existent_value_from_list(self) -> None:
        """Removing a non-existent value leaves the list unchanged."""
        state = WorldState(inventory=["sword", "shield"])
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "inventory", "value": "potion"}
        ]
        result = apply_changes(state, changes)
        assert result.inventory == ["sword", "shield"]

    def test_apply_remove_non_existent_key_from_dict(self) -> None:
        """Removing a non-existent key leaves the dict unchanged."""
        state = WorldState()
        state.active_npcs["goblin"] = {"name": "Gribbits"}
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "active_npcs", "value": "nonexistent"}
        ]
        result = apply_changes(state, changes)
        assert "goblin" in result.active_npcs
        assert "nonexistent" not in result.active_npcs

    def test_apply_append_none_value(self) -> None:
        """Appending None to a list adds None as an item."""
        state = WorldState(inventory=["sword"])
        changes: list[dict[str, Any]] = [
            {"action": "append", "path": "inventory", "value": None}
        ]
        result = apply_changes(state, changes)
        assert result.inventory == ["sword", None]

    def test_apply_set_character_id_to_none(self) -> None:
        """Setting character_id to None clears it."""
        state = WorldState(character_id="hero_01")
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "character_id", "value": None}
        ]
        result = apply_changes(state, changes)
        assert result.character_id is None

    def test_apply_set_empty_string_location(self) -> None:
        """Setting a string field to empty string is accepted."""
        state = WorldState(current_location="village")
        changes: list[dict[str, Any]] = [
            {"action": "set", "path": "current_location", "value": ""}
        ]
        result = apply_changes(state, changes)
        assert result.current_location == ""

    # --- DMNotes-specific tests ---

    def test_dm_notes_add_plot_thread(self) -> None:
        """Adding plot_threads to dm_notes preserves the DMNotes type."""
        state = WorldState()
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "dm_notes",
                "value": {"plot_threads": ["the_ancient_artifact"]},
            }
        ]
        result = apply_changes(state, changes)
        # Must still be a DMNotes instance, not a plain dict
        assert isinstance(result.dm_notes, DMNotes)
        assert "the_ancient_artifact" in result.dm_notes.plot_threads

    def test_dm_notes_remove_plot_thread(self) -> None:
        """Removing plot_threads from dm_notes preserves the DMNotes type."""
        state = WorldState()
        state.dm_notes.plot_threads = ["thread_a", "thread_b", "thread_c"]
        changes: list[dict[str, Any]] = [
            {
                "action": "remove",
                "path": "dm_notes",
                "value": {"plot_threads": ["thread_b"]},
            }
        ]
        result = apply_changes(state, changes)
        assert isinstance(result.dm_notes, DMNotes)
        assert "thread_b" not in result.dm_notes.plot_threads
        assert result.dm_notes.plot_threads == ["thread_a", "thread_c"]

    def test_dm_notes_add_preserves_existing(self) -> None:
        """Adding to dm_notes preserves existing fields."""
        state = WorldState()
        state.dm_notes.plot_threads = ["existing_plot"]
        state.dm_notes.secrets = ["dark_secret"]
        state.dm_notes.future_plans = ["epic_battle"]
        changes: list[dict[str, Any]] = [
            {
                "action": "add",
                "path": "dm_notes",
                "value": {"plot_threads": ["new_plot"]},
            }
        ]
        result = apply_changes(state, changes)
        assert isinstance(result.dm_notes, DMNotes)
        # Existing content preserved
        assert "existing_plot" in result.dm_notes.plot_threads
        assert "dark_secret" in result.dm_notes.secrets
        assert "epic_battle" in result.dm_notes.future_plans
        # New content added
        assert "new_plot" in result.dm_notes.plot_threads

    def test_remove_all_occurrences_from_list(self) -> None:
        """Remove removes ALL occurrences, not just the first."""
        state = WorldState(inventory=["potion", "sword", "potion", "shield"])
        changes: list[dict[str, Any]] = [
            {"action": "remove", "path": "inventory", "value": "potion"}
        ]
        result = apply_changes(state, changes)
        assert result.inventory == ["sword", "shield"]


# ---------------------------------------------------------------------------
# FIELD_SCHEMA sanity
# ---------------------------------------------------------------------------


class TestFieldSchema:
    def test_all_world_state_fields_covered(self) -> None:
        """Every field in WorldState should have a schema entry."""
        model_fields = {f.name for f in dataclasses.fields(WorldState)}
        schema_fields = set(FIELD_SCHEMA.keys())
        missing = model_fields - schema_fields
        assert not missing, f"Fields missing from FIELD_SCHEMA: {missing}"

    def test_no_extra_fields_in_schema(self) -> None:
        """Schema should not contain fields not in WorldState."""
        model_fields = {f.name for f in dataclasses.fields(WorldState)}
        schema_fields = set(FIELD_SCHEMA.keys())
        extra = schema_fields - model_fields
        assert not extra, f"Extra fields in FIELD_SCHEMA not in model: {extra}"

    def test_all_schema_entries_have_required_keys(self) -> None:
        for field_name, entry in FIELD_SCHEMA.items():
            assert "type" in entry, f"{field_name} missing 'type'"
            assert "mutability" in entry, f"{field_name} missing 'mutability'"
            assert "description" in entry, f"{field_name} missing 'description'"
            assert entry["mutability"] in (
                "settable",
                "mutable",
                "immutable",
            ), f"{field_name} has invalid mutability {entry['mutability']!r}"
