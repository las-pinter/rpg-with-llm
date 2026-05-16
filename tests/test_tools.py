"""Tests for the tool dispatcher module — Phase 5.2."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agents.tools import (
    TOOL_REGISTRY,
    dice_roll,
    dispatch_tool,
    rules_attack,
    rules_saving_throw,
    rules_skill_check,
    table_lookup,
)


class TestToolRegistry:
    """Tests for ``TOOL_REGISTRY``."""

    def test_has_expected_keys(self) -> None:
        """TOOL_REGISTRY should contain all expected tool names."""
        expected = {
            "dice",
            "table",
            "skill_check",
            "attack",
            "saving_throw",
        }
        for name in expected:
            assert name in TOOL_REGISTRY, f"Missing tool: {name}"

    def test_all_values_are_callable(self) -> None:
        """Every entry in TOOL_REGISTRY should be a callable function."""
        for name, fn in TOOL_REGISTRY.items():
            assert callable(fn), f"Tool '{name}' is not callable"

    def test_registry_contains_aliases(self) -> None:
        """TOOL_REGISTRY should have alternative name aliases."""
        assert "dice_roll" in TOOL_REGISTRY
        assert "table_lookup" in TOOL_REGISTRY


class TestDispatchTool:
    """Tests for ``dispatch_tool``."""

    def test_unknown_tool_returns_error(self) -> None:
        """Unknown tool name should return error result."""
        result = dispatch_tool("nonexistent_tool", {})
        assert result["ok"] is False
        assert "Unknown tool" in result["error"]

    def test_non_dict_params_returns_error(self) -> None:
        """Non-dict params should return error result."""
        result = dispatch_tool("dice", "not a dict")  # type: ignore[arg-type]
        assert result["ok"] is False
        assert "Params must be a dict" in result["error"]

    def test_dispatch_with_missing_params(self) -> None:
        """Missing required params should return error."""
        result = dispatch_tool("dice", {})
        assert result["ok"] is False
        assert "Missing" in result.get("error", "")

    @patch("app.agents.tools.roll")
    @patch("app.agents.tools.parse")
    def test_dice_dispatch_calls_roll(
        self, mock_parse: MagicMock, mock_roll: MagicMock
    ) -> None:
        """Dice dispatch should call parse and roll."""
        mock_parse.return_value = MagicMock()
        mock_roll.return_value = {
            "total": 15,
            "rolls": [15],
            "sides": 20,
            "formula": "d20",
        }
        result = dispatch_tool("dice", {"formula": "d20"})
        assert result["ok"] is True
        assert result["result"]["total"] == 15

    @patch("app.agents.tools.RandomTable")
    def test_table_lookup_dispatch(self, mock_table: MagicMock) -> None:
        """Table lookup dispatch should call RandomTable.lookup."""
        mock_instance = MagicMock()
        mock_table.return_value = mock_instance
        mock_instance.lookup.return_value = {
            "result": "A goblin appears!",
            "roll": {"total": 12},
            "table": "encounters",
        }
        result = dispatch_tool("table", {"table_name": "encounters"})
        assert result["ok"] is True
        assert result["result"]["result"] == "A goblin appears!"

    @patch("app.agents.tools.skill_check")
    def test_skill_check_dispatch(self, mock_skill: MagicMock) -> None:
        """Skill check dispatch should call rules.skill_check."""
        mock_skill.return_value = {
            "success": True,
            "total": 18,
            "roll": {"total": 15},
            "modifier": 3,
            "margin": 8,
        }
        result = dispatch_tool(
            "skill_check",
            {
                "skill": "perception",
                "dc": 15,
                "ability": "wisdom",
                "character_stats": {"wisdom": 16},
            },
        )
        assert result["ok"] is True
        assert result["result"]["success"] is True

    @patch("app.agents.tools.attack_roll")
    def test_attack_dispatch(self, mock_attack: MagicMock) -> None:
        """Attack dispatch should call rules.attack_roll."""
        mock_attack.return_value = {
            "hit": True,
            "critical": False,
            "total": 22,
            "roll": {"total": 18},
            "modifier": 4,
        }
        result = dispatch_tool(
            "attack",
            {
                "attacker_stats": {"strength": 16, "proficiency_bonus": 2},
                "defender_ac": 15,
            },
        )
        assert result["ok"] is True
        assert result["result"]["hit"] is True

    @patch("app.agents.tools.saving_throw")
    def test_saving_throw_dispatch(self, mock_save: MagicMock) -> None:
        """Saving throw dispatch should call rules.saving_throw."""
        mock_save.return_value = {
            "success": True,
            "total": 16,
            "roll": {"total": 12},
            "modifier": 4,
            "margin": 1,
        }
        result = dispatch_tool(
            "saving_throw",
            {
                "ability": "dexterity",
                "dc": 15,
                "character_stats": {"dexterity": 18},
            },
        )
        assert result["ok"] is True
        assert result["result"]["success"] is True


class TestDiceRoll:
    """Tests for the ``dice_roll`` function."""

    def test_missing_formula(self) -> None:
        """Missing formula should return error."""
        result = dice_roll({})
        assert result["ok"] is False

    def test_invalid_formula(self) -> None:
        """Invalid formula should return error."""
        result = dice_roll({"formula": "not_a_dice_formula"})
        assert result["ok"] is False


class TestTableLookup:
    """Tests for the ``table_lookup`` function."""

    def test_missing_table_name(self) -> None:
        """Missing table_name should return error."""
        result = table_lookup({})
        assert result["ok"] is False

    def test_nonexistent_table(self) -> None:
        """Non-existent table should return error."""
        result = table_lookup({"table_name": "__nonexistent_table__"})
        assert result["ok"] is False


class TestRulesSkillCheck:
    """Tests for the ``rules_skill_check`` function."""

    def test_missing_skill(self) -> None:
        """Missing skill should return error."""
        result = rules_skill_check({})
        assert result["ok"] is False


class TestRulesAttack:
    """Tests for the ``rules_attack`` function."""

    def test_missing_attacker_stats(self) -> None:
        """Missing attacker_stats should return error."""
        result = rules_attack({})
        assert result["ok"] is False


class TestRulesSavingThrow:
    """Tests for the ``rules_saving_throw`` function."""

    def test_missing_ability(self) -> None:
        """Missing ability should return error."""
        result = rules_saving_throw({})
        assert result["ok"] is False
