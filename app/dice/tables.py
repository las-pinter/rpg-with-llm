"""
Random Table system for RPG games.

Loads weighted random tables from JSON files and performs lookups
using the dice roller engine. Supports nested table references for
sub-rolls on other tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.dice.parser import parse
from app.dice.roller import roll


class RandomTable:
    """A random table that can be looked up using dice rolls.

    Tables are loaded from JSON files stored in a data directory.
    Each table defines a dice expression and weighted entries with
    range-based results. Entries may reference other tables for
    nested sub-rolls.

    Attributes:
        data_dir: Path to the directory containing table JSON files.
    """

    def __init__(self, data_dir: str | Path) -> None:
        """Initialise with the directory containing table JSON files.

        Args:
            data_dir: Directory path where ``<name>.json`` table files
                are stored.
        """
        self._data_dir = Path(data_dir)
        self._cache: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_table(self, table_name: str) -> dict[str, Any]:
        """Load a table definition from a JSON file.

        The table is cached after first load so subsequent lookups
        are fast without re-reading the file.

        Args:
            table_name: Name of the table (without ``.json`` extension).

        Returns:
            The parsed table definition dict with keys ``name``, ``die``,
            and ``entries``.

        Raises:
            FileNotFoundError: If the table file does not exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            ValueError: If required fields (name, die, entries) are
                missing or malformed, or if any entry has invalid
                ``range`` or ``result`` fields.
        """
        if table_name in self._cache:
            return self._cache[table_name]

        path = self._resolve_path(table_name)
        with path.open("r", encoding="utf-8") as f:
            table: dict[str, Any] = json.load(f)

        # --- Validate required fields ---------------------------------
        if "name" not in table:
            raise ValueError(f"Table '{table_name}' is missing required 'name' field")
        if "die" not in table:
            raise ValueError(f"Table '{table_name}' is missing required 'die' field")
        if "entries" not in table or not isinstance(table["entries"], list):
            raise ValueError(f"Table '{table_name}' is missing required 'entries' list")
        if not table["entries"]:
            raise ValueError(f"Table '{table_name}' has an empty 'entries' list")

        # --- Validate each entry (Bugs 1 & 2) -------------------------
        for i, entry in enumerate(table["entries"]):
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Table '{table_name}' entry {i} must be an object "
                    f"(dict), got {type(entry).__name__}"
                )
            if "range" not in entry:
                raise ValueError(
                    f"Table '{table_name}' entry {i} is missing required 'range' field"
                )
            if "result" not in entry:
                raise ValueError(
                    f"Table '{table_name}' entry {i} is missing required 'result' field"
                )

            r = entry["range"]
            if not isinstance(r, list) or len(r) != 2:
                raise ValueError(
                    f"Table '{table_name}' entry {i}: 'range' must be "
                    f"a list of 2 integers, got {r!r}"
                )
            if not all(isinstance(v, int) for v in r):
                raise ValueError(
                    f"Table '{table_name}' entry {i}: 'range' values "
                    f"must be integers, got {r!r}"
                )
            if r[0] > r[1]:
                raise ValueError(
                    f"Table '{table_name}' entry {i}: range [{r[0]}, {r[1]}] "
                    f"is reversed (min > max)"
                )

            if not isinstance(entry["result"], str):
                raise ValueError(
                    f"Table '{table_name}' entry {i}: 'result' must be "
                    f"a string, got {type(entry['result']).__name__}"
                )

        self._cache[table_name] = table
        return table

    def lookup(
        self,
        table_name: str,
        _depth: int = 0,
        _max_depth: int = 10,
    ) -> dict[str, Any]:
        """Roll on a random table and return the matched result.

        Performs a dice roll using the table's die expression, finds the
        matching entry by range, and returns the result. If the matched
        entry references another table (via the ``table`` field), a
        sub-roll is performed recursively and included in the response.

        Args:
            table_name: Name of the table to look up.
            _depth: Internal recursion depth counter.
            _max_depth: Maximum allowed recursion depth for nested
                table references (default 10).

        Returns:
            A dict with:
                - **result** (``str``): The text result from the matched
                  entry.
                - **roll** (``dict``): The full dice roll result from
                  the roller (contains ``total``, ``rolls``, ``sides``,
                  ``formula``).
                - **table** (``str``): The name of the table used.
                - **sub_rolls** (``list[dict]``): Any nested table roll
                  results, each with the same shape.

        Raises:
            FileNotFoundError: If the table file does not exist.
            ValueError: If no entry matches the roll, or if recursion
                depth exceeds the maximum.
        """
        if _depth > _max_depth:
            raise ValueError(
                f"Max recursion depth ({_max_depth}) exceeded for table '{table_name}'"
            )

        table = self.load_table(table_name)
        return self._roll_on_table(table, _depth, _max_depth)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, table_name: str) -> Path:
        """Resolve a table name to its JSON file path."""
        return self._data_dir / f"{table_name}.json"

    def _roll_on_table(
        self,
        table: dict[str, Any],
        _depth: int = 0,
        _max_depth: int = 10,
    ) -> dict[str, Any]:
        """Roll dice and find the matching entry on a loaded table."""
        die = table["die"]
        expr = parse(die)
        roll_result = roll(expr)
        total = roll_result["total"]

        for entry in table["entries"]:
            r_min, r_max = entry["range"]
            if r_min <= total <= r_max:
                result_text = entry["result"]

                # --- Handle nested table references -------------------
                sub_rolls: list[dict[str, Any]] = []
                if "table" in entry and entry["table"]:
                    sub_result = self.lookup(
                        entry["table"],
                        _depth + 1,
                        _max_depth,
                    )
                    sub_rolls.append(sub_result)

                return {
                    "result": result_text,
                    "roll": roll_result,
                    "table": table["name"],
                    "sub_rolls": sub_rolls,
                }

        # Defensive: should never happen with well-formed tables
        raise ValueError(
            f"Roll {total} on table '{table['name']}' did not match "
            f"any entry. Die: {die}, entries: {len(table['entries'])}",
        )
