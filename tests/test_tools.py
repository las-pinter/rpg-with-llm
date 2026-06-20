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
    set_record_keeper,
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


class TestRecordKeeperTools:
    """Tests for ``record_keeper_fetch`` tool and ``set_record_keeper``."""

    def test_record_keeper_fetch_not_configured(self) -> None:
        """Without record_keeper set, returns 'not configured' error."""
        set_record_keeper(None)
        result = dispatch_tool(
            "record_keeper_fetch",
            {
                "entity_type": "npc",
                "entity_id": "test",
            },
        )
        assert result == {"ok": False, "error": "Record-Keeper not configured"}

    def test_record_keeper_fetch_missing_entity_type(self) -> None:
        """Missing entity_type returns appropriate error when configured."""
        mock_rk = MagicMock()
        set_record_keeper(mock_rk)
        try:
            result = dispatch_tool("record_keeper_fetch", {})
            assert result["ok"] is False
            assert "entity_type" in result.get("error", "")
        finally:
            set_record_keeper(None)

    def test_record_keeper_fetch_missing_entity_id(self) -> None:
        """Missing entity_id returns appropriate error when configured."""
        mock_rk = MagicMock()
        set_record_keeper(mock_rk)
        try:
            result = dispatch_tool("record_keeper_fetch", {"entity_type": "npc"})
            assert result["ok"] is False
            assert "entity_id" in result.get("error", "")
        finally:
            set_record_keeper(None)

    def test_record_keeper_fetch_alias_resolves(self) -> None:
        """Alias 'rk_fetch' dispatches to record_keeper_fetch."""
        set_record_keeper(None)
        result = dispatch_tool("rk_fetch", {"entity_type": "npc", "entity_id": "x"})
        assert result["ok"] is False  # Not configured, but alias resolves
        # Should say "not configured", NOT "Unknown tool"
        assert "Unknown tool" not in result.get("error", "")

    def test_rk_fetch_and_record_keeper_fetch_in_registry(self) -> None:
        """Both names are registered in TOOL_REGISTRY."""
        assert "rk_fetch" in TOOL_REGISTRY
        assert "record_keeper_fetch" in TOOL_REGISTRY
        assert TOOL_REGISTRY["rk_fetch"] is TOOL_REGISTRY["record_keeper_fetch"]

    def test_record_keeper_fetch_with_mock(self) -> None:
        """With a mock record_keeper, returns entity data."""
        mock_rk = MagicMock()
        mock_rk.fetch_entity.return_value = {
            "entity_id": "test_npc",
            "name": "Test NPC",
            "entity_type": "npc",
        }
        set_record_keeper(mock_rk)
        try:
            result = dispatch_tool(
                "record_keeper_fetch",
                {
                    "entity_type": "npc",
                    "entity_id": "test_npc",
                },
            )
            assert result["ok"] is True
            assert result["result"]["entity_id"] == "test_npc"
            mock_rk.fetch_entity.assert_called_once_with("npc", "test_npc")
        finally:
            set_record_keeper(None)

    def test_record_keeper_fetch_not_found(self) -> None:
        """Entity not found returns appropriate error."""
        mock_rk = MagicMock()
        mock_rk.fetch_entity.return_value = None
        set_record_keeper(mock_rk)
        try:
            result = dispatch_tool(
                "record_keeper_fetch",
                {
                    "entity_type": "npc",
                    "entity_id": "unknown",
                },
            )
            assert result["ok"] is False
            assert "not found" in result.get("error", "")
        finally:
            set_record_keeper(None)

    def test_set_record_keeper_clears_reference(self) -> None:
        """set_record_keeper(None) clears the module-level reference."""
        mock_rk = MagicMock()
        set_record_keeper(mock_rk)
        set_record_keeper(None)
        result = dispatch_tool(
            "record_keeper_fetch",
            {
                "entity_type": "npc",
                "entity_id": "x",
            },
        )
        assert result["ok"] is False
        assert "not configured" in result.get("error", "")
