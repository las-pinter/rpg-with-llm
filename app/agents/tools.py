"""
Tool Dispatcher — maps tool names to deterministic functions.

The DM agent can request tool calls (dice rolls, table lookups, skill
checks, etc.) during a turn.  This module provides a registry mapping
tool names to implementations and a ``dispatch_tool`` function that
executes a tool by name with given parameters.

Every tool function returns a dict and handles its own error cases.
The dispatch wrapper catches unexpected exceptions and returns a
structured error response.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.dice.parser import ParseError, parse
from app.dice.roller import roll
from app.dice.tables import RandomTable
from app.rules.checks import saving_throw, skill_check
from app.rules.combat import attack_roll

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def dice_roll(params: dict[str, Any]) -> dict[str, Any]:
    """Roll dice using standard tabletop notation.

    Parameters
    ----------
    params : dict
        Must contain ``formula`` (str) — a dice notation string like
        ``"2d6+3"``, ``"d20"``, ``"4d6k3"``.

    Returns
    -------
    dict
        The result from ``dice.roller.roll()`` with keys ``total``,
        ``rolls``, ``sides``, ``formula``.
    """
    formula = params.get("formula", "")
    if not formula:
        return {"ok": False, "error": "Missing required param: 'formula'"}
    try:
        expr = parse(formula)
        result = roll(expr)
        return {"ok": True, "result": result}
    except (ValueError, KeyError, ParseError) as e:
        return {"ok": False, "error": f"Dice roll failed: {e}"}


def table_lookup(params: dict[str, Any]) -> dict[str, Any]:
    """Look up a random table entry.

    Parameters
    ----------
    params : dict
        Must contain ``table_name`` (str) — the name of the table
        (without ``.json`` extension).

    Returns
    -------
    dict
        The result from ``dice.tables.RandomTable.lookup()`` with keys
        ``result``, ``roll``, ``table``, ``sub_rolls``.
    """
    table_name = params.get("table_name", "")
    if not table_name:
        return {"ok": False, "error": "Missing required param: 'table_name'"}
    try:
        from pathlib import Path

        # Validate that the table file exists before attempting lookup
        table_path = Path("data/tables") / f"{table_name}.json"
        if not table_path.exists():
            logger.warning(
                "Table '%s' not found — no file at %s. "
                "The DM should narratively create a custom result.",
                table_name,
                table_path,
            )
            return {
                "ok": False,
                "error": f"Table '{table_name}' does not exist. "
                f"Create a custom narrative result instead.",
            }

        table = RandomTable(data_dir=Path("data/tables"))
        result = table.lookup(table_name)
        logger.debug(
            "table_lookup: '%s' -> %s",
            table_name,
            result.get("result", "?") if isinstance(result, dict) else "?",
        )
        return {"ok": True, "result": result}
    except (FileNotFoundError, ValueError, KeyError) as e:
        logger.warning("Table lookup failed for '%s': %s", table_name, e)
        return {"ok": False, "error": f"Table lookup failed: {e}"}


def rules_skill_check(params: dict[str, Any]) -> dict[str, Any]:
    """Resolve a skill check.

    Parameters
    ----------
    params : dict
        Should contain ``ability`` (str), ``skill`` (str), ``dc`` (int),
        and optionally ``character_stats`` (dict).

    Returns
    -------
    dict
        The result from ``rules.checks.skill_check()`` with keys
        ``success``, ``total``, ``roll``, ``modifier``, ``margin``.
    """
    skill = params.get("skill", "")
    dc = params.get("dc", 10)
    ability = params.get("ability")
    stats = params.get("character_stats", {})

    if not skill:
        return {"ok": False, "error": "Missing required param: 'skill'"}

    try:
        result = skill_check(stats=stats, skill=skill, dc=int(dc), ability=ability)
        return {"ok": True, "result": result}
    except (ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": f"Skill check failed: {e}"}


def rules_attack(params: dict[str, Any]) -> dict[str, Any]:
    """Resolve a combat attack.

    Parameters
    ----------
    params : dict
        Should contain ``attacker_stats`` (dict) and ``defender_ac`` (int).

    Returns
    -------
    dict
        The result from ``rules.combat.attack_roll()`` with keys ``hit``,
        ``critical``, ``total``, ``roll``, ``modifier``.
    """
    attacker_stats = params.get("attacker_stats", {})
    defender_ac = params.get("defender_ac", 10)

    if not attacker_stats:
        return {"ok": False, "error": "Missing required param: 'attacker_stats'"}

    try:
        result = attack_roll(
            attacker_stats=attacker_stats,
            defender_ac=int(defender_ac),
        )
        return {"ok": True, "result": result}
    except (ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": f"Attack roll failed: {e}"}


def rules_saving_throw(params: dict[str, Any]) -> dict[str, Any]:
    """Resolve a saving throw.

    Parameters
    ----------
    params : dict
        Should contain ``ability`` (str), ``dc`` (int), and optionally
        ``character_stats`` (dict).

    Returns
    -------
    dict
        The result from ``rules.checks.saving_throw()`` with keys
        ``success``, ``total``, ``roll``, ``modifier``, ``margin``.
    """
    ability = params.get("ability", "")
    dc = params.get("dc", 10)
    stats = params.get("character_stats", {})

    if not ability:
        return {"ok": False, "error": "Missing required param: 'ability'"}

    try:
        result = saving_throw(stats=stats, ability=ability, dc=int(dc))
        return {"ok": True, "result": result}
    except (ValueError, KeyError, TypeError) as e:
        return {"ok": False, "error": f"Saving throw failed: {e}"}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "dice": dice_roll,
    "table": table_lookup,
    "skill_check": rules_skill_check,
    "attack": rules_attack,
    "saving_throw": rules_saving_throw,
}

# Aliases for flexibility
TOOL_REGISTRY["dice_roll"] = dice_roll
TOOL_REGISTRY["table_lookup"] = table_lookup


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def dispatch_tool(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name with the given parameters.

    Looks up *name* in ``TOOL_REGISTRY``, calls the corresponding
    function with *params*, and returns the result wrapped in a
    standard envelope ``{ok, result, error}``.

    Parameters
    ----------
    name : str
        The tool name (must be a key in ``TOOL_REGISTRY``).
    params : dict
        Parameters to pass to the tool function.

    Returns
    -------
    dict
        A dict with keys:

        - **ok** (``bool``): Whether the tool executed successfully.
        - **result** (any): The tool's result data (only present on
          success).
        - **error** (``str`` | ``None``): Error message if the tool
          failed (only present on failure).
    """
    logger.debug("dispatch_tool: name='%s' params=%s", name, params)

    if name not in TOOL_REGISTRY:
        return {"ok": False, "error": f"Unknown tool: '{name}'"}

    if not isinstance(params, dict):
        return {"ok": False, "error": "Params must be a dict"}

    try:
        tool_fn = TOOL_REGISTRY[name]
        result = tool_fn(params)
        logger.debug(
            "dispatch_tool: '%s' returned ok=%s",
            name,
            result.get("ok", False) if isinstance(result, dict) else "?",
        )
        return result
    except Exception:
        logger.exception("Tool '%s' raised unexpected exception", name)
        return {"ok": False, "error": f"Tool '{name}' failed"}
