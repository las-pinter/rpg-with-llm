"""Tests for the DM response parser module — Phase 5.2."""

from __future__ import annotations

from app.agents.parser import (
    _strip_backtick_state_attrs,
    _strip_markdown_bold,
    parse_dm_response,
)


class TestParseDMResponse:
    """Tests for ``parse_dm_response``."""

    def test_parse_with_narrative(self) -> None:
        """Should extract narrative text from <narrative> tags."""
        text = """
        <narrative>
        The ancient door groans on rusted hinges.
        </narrative>
        """
        result = parse_dm_response(text)
        assert result["narrative"] == "The ancient door groans on rusted hinges."
        assert result["tool_requests"] == []
        assert result["state_changes"] == []
        assert result["npc_requests"] == []

    def test_parse_with_tool_request(self) -> None:
        """Should extract tool_request attributes."""
        text = """
        <narrative>You try to pick the lock.</narrative>
        <tool_request name="dice" params='{"formula":"d20+5"}' />
        """
        result = parse_dm_response(text)
        assert len(result["tool_requests"]) == 1
        assert result["tool_requests"][0]["name"] == "dice"
        assert result["tool_requests"][0]["params"] == {"formula": "d20+5"}

    def test_parse_with_state_change(self) -> None:
        """Should extract state_change attributes."""
        text = """
        <narrative>You pick up the rusty key.</narrative>
        <state_change action="append" path="inventory" value="Rusted Key" />
        """
        result = parse_dm_response(text)
        assert len(result["state_changes"]) == 1
        assert result["state_changes"][0]["action"] == "append"
        assert result["state_changes"][0]["path"] == "inventory"
        assert result["state_changes"][0]["value"] == "Rusted Key"

    def test_parse_with_multiple_tool_requests(self) -> None:
        """Should extract multiple tool_request tags."""
        text = """
        <tool_request name="dice" params='{"formula":"2d6"}' />
        <tool_request name="table" params='{"table_name":"weather"}' />
        """
        result = parse_dm_response(text)
        assert len(result["tool_requests"]) == 2
        assert result["tool_requests"][0]["name"] == "dice"
        assert result["tool_requests"][1]["name"] == "table"

    def test_parse_with_npc_request(self) -> None:
        """Should extract npc_request attributes."""
        text = """
        <narrative>The innkeeper looks at you expectantly.</narrative>
        <npc_request npc_id="innkeep" context="Player asks about quest" />
        """
        result = parse_dm_response(text)
        assert len(result["npc_requests"]) == 1
        assert result["npc_requests"][0]["npc_id"] == "innkeep"

    def test_parse_missing_tags(self) -> None:
        """Should handle text with no XML tags."""
        text = "Just some plain text without any tags."
        result = parse_dm_response(text)
        assert result["narrative"] == ""
        assert result["tool_requests"] == []
        assert result["state_changes"] == []
        assert result["npc_requests"] == []

    def test_parse_empty_string(self) -> None:
        """Should handle empty string input."""
        result = parse_dm_response("")
        assert result["narrative"] == ""
        assert result["tool_requests"] == []
        assert result["state_changes"] == []
        assert result["npc_requests"] == []

    def test_parse_none_input(self) -> None:
        """Should handle None input gracefully."""
        result = parse_dm_response(None)  # type: ignore[arg-type]
        assert result["narrative"] == ""
        assert result["tool_requests"] == []

    def test_parse_malformed_attributes(self) -> None:
        """Should handle malformed tool_request attributes."""
        text = '<tool_request name="dice" params="not-valid-json" />'
        result = parse_dm_response(text)
        assert len(result["tool_requests"]) == 1
        assert result["tool_requests"][0]["name"] == "dice"
        # params should default to empty dict since JSON parse fails
        assert result["tool_requests"][0]["params"] == {}

    def test_parse_state_change_with_json_value(self) -> None:
        """Should parse JSON values in state_change tags."""
        text = '<state_change action="set" path="turn_count" value="5" />'
        result = parse_dm_response(text)
        assert len(result["state_changes"]) == 1
        assert result["state_changes"][0]["value"] == 5  # int, not str

    def test_parse_state_change_with_dict_value(self) -> None:
        """Should parse dict JSON values in state_change tags."""
        text = (
            '<state_change action="add" path="active_npcs" '
            'value=\'{"goblin":{"hp":5}}\' />'
        )
        result = parse_dm_response(text)
        assert len(result["state_changes"]) == 1
        assert result["state_changes"][0]["value"] == {"goblin": {"hp": 5}}

    def test_parse_with_all_tag_types(self) -> None:
        """Should extract all tag types simultaneously."""
        text = """
        <narrative>You enter the dark forest.</narrative>
        <tool_request name="dice" params='{"formula":"d20"}' />
        <state_change action="set" path="current_location" value="dark_forest" />
        <npc_request npc_id="forest_spirit" context="Player calls out" />
        """
        result = parse_dm_response(text)
        assert result["narrative"] == "You enter the dark forest."
        assert len(result["tool_requests"]) == 1
        assert len(result["state_changes"]) == 1
        assert len(result["npc_requests"]) == 1

    def test_parse_tool_request_without_params(self) -> None:
        """Should handle tool_request without params attribute."""
        text = '<tool_request name="dice" />'
        result = parse_dm_response(text)
        assert len(result["tool_requests"]) == 1
        assert result["tool_requests"][0]["name"] == "dice"
        assert result["tool_requests"][0]["params"] == {}

    def test_parse_returns_dict_with_expected_keys(self) -> None:
        """Should always return dict with the four expected keys."""
        result = parse_dm_response("anything")
        assert set(result.keys()) == {
            "narrative",
            "tool_requests",
            "state_changes",
            "npc_requests",
        }

    def test_parse_state_change_with_bool_value(self) -> None:
        """Should parse boolean JSON values."""
        text = (
            '<state_change action="set" path="quests.old_well.status" value="true" />'
        )
        result = parse_dm_response(text)
        assert result["state_changes"][0]["value"] is True


class TestMarkdownBoldStripping:
    """Tests for markdown bold artifact stripping (tag leak fix)."""

    def test_strip_markdown_bold_narrative(self) -> None:
        """Should strip **narrative** bold artifacts."""
        text = "**narrative** The ancient door groans."
        result = _strip_markdown_bold(text)
        assert result == " The ancient door groans."

    def test_strip_markdown_bold_tool_request(self) -> None:
        """Should strip **tool_request** bold artifacts."""
        text = "I see **tool_request** in the output."
        result = _strip_markdown_bold(text)
        assert result == "I see  in the output."

    def test_strip_markdown_bold_multiple(self) -> None:
        """Should strip multiple bold artifacts."""
        text = "**narrative** Hello **tool_request** world"
        result = _strip_markdown_bold(text)
        assert result == " Hello  world"

    def test_strip_markdown_bold_none(self) -> None:
        """Should pass through text without bold artifacts."""
        text = "Just plain narrative text."
        result = _strip_markdown_bold(text)
        assert result == "Just plain narrative text."

    def test_strip_markdown_bold_underscore_name(self) -> None:
        """Should strip bold with underscore names like **state_change**."""
        text = "**state_change** leaked through."
        result = _strip_markdown_bold(text)
        assert result == " leaked through."

    def test_strip_markdown_bold_no_false_positive(self) -> None:
        """Should not strip **not-a-tag** with hyphens."""
        text = "This is **bold-text** not a tag."
        result = _strip_markdown_bold(text)
        assert result == "This is **bold-text** not a tag."


class TestBacktickStateAttrStripping:
    """Tests for backtick state attribute stripping (tag leak fix)."""

    def test_strip_backtick_action(self) -> None:
        """Should strip backtick-wrapped action attributes."""
        text = 'Some text `action="set" path="location"` more text'
        result = _strip_backtick_state_attrs(text)
        assert result == "Some text  more text"

    def test_strip_backtick_path(self) -> None:
        """Should strip backtick-wrapped path attributes."""
        text = 'Look `path="inventory"` here'
        result = _strip_backtick_state_attrs(text)
        assert result == "Look  here"

    def test_strip_backtick_value(self) -> None:
        """Should strip backtick-wrapped value attributes."""
        text = 'Check `value="Rusted Key"` now'
        result = _strip_backtick_state_attrs(text)
        assert result == "Check  now"

    def test_strip_backtick_full_state_change(self) -> None:
        """Should strip full state change in backticks."""
        text = 'Got `action="set" path="location" value="village_street"` here'
        result = _strip_backtick_state_attrs(text)
        assert result == "Got  here"

    def test_strip_backtick_multiple(self) -> None:
        """Should strip multiple backtick artifacts."""
        text = '`action="set" path="loc"` and `value="test"` done'
        result = _strip_backtick_state_attrs(text)
        assert result == " and  done"

    def test_strip_backtick_none(self) -> None:
        """Should pass through text without backtick artifacts."""
        text = "Just plain text, nothing leaked."
        result = _strip_backtick_state_attrs(text)
        assert result == "Just plain text, nothing leaked."


class TestParseDMResponseTagLeakFix:
    """Integration tests: parse_dm_response strips leaked artifacts."""

    def test_narrative_strips_markdown_bold(self) -> None:
        """Narrative should have **word** bold artifacts stripped."""
        text = "<narrative>**narrative** You enter the village.</narrative>"
        result = parse_dm_response(text)
        assert "**narrative**" not in result["narrative"]
        assert "You enter the village." in result["narrative"]

    def test_narrative_strips_backtick_state_attrs(self) -> None:
        """Narrative should have backtick state attrs stripped."""
        text = '<narrative>You see `action="set" path="location"` nearby.</narrative>'
        result = parse_dm_response(text)
        assert "action=" not in result["narrative"]
        assert "path=" not in result["narrative"]
        assert "You see  nearby." in result["narrative"]

    def test_narrative_strips_both_artifacts(self) -> None:
        """Narrative should strip both markdown bold and backtick attrs."""
        text = (
            "<narrative>**narrative** You see "
            '`action="set" path="loc"` here.</narrative>'
        )
        result = parse_dm_response(text)
        assert "**narrative**" not in result["narrative"]
        assert "action=" not in result["narrative"]
        assert "path=" not in result["narrative"]
        assert "You see  here." in result["narrative"]

    def test_narrative_preserves_real_bold_text(self) -> None:
        """Real bold text with hyphens/special chars should not be stripped."""
        text = "<narrative>The **bold-text** item glows.</narrative>"
        result = parse_dm_response(text)
        assert "**bold-text**" in result["narrative"]
