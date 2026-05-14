"""Tests for the random table system."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.dice.tables import RandomTable

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data" / "tables"


@pytest.fixture
def table() -> RandomTable:
    """A RandomTable instance pointing at the real data tables."""
    return RandomTable(DATA_DIR)


@pytest.fixture
def temp_table(tmp_path: Path) -> Path:
    """Create a temporary tables directory with a single-entry table."""
    table_file = tmp_path / "always_42.json"
    table_file.write_text(
        json.dumps(
            {
                "name": "always_42",
                "die": "1d6",
                "entries": [{"range": [1, 6], "result": "You always get this result."}],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


# ===========================================================================
# Loading tests
# ===========================================================================


class TestLoadTable:
    """Loading tables from JSON files."""

    def test_load_existing_table(self, table: RandomTable):
        """Loading an existing table returns its parsed data."""
        data = table.load_table("encounters")
        assert data["name"] == "encounters"
        assert data["die"] == "1d20"
        assert len(data["entries"]) > 0

    def test_load_all_tables(self, table: RandomTable):
        """All four table files should load without error."""
        for name in ("encounters", "loot", "weather", "npc_traits"):
            data = table.load_table(name)
            assert data["name"] == name
            assert "die" in data
            assert len(data["entries"]) >= 1

    def test_load_nonexistent_table(self, table: RandomTable):
        """Loading a nonexistent table raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            table.load_table("no_such_table_xyz")

    def test_load_is_cached(self, table: RandomTable):
        """Loading the same table twice should return the same cached dict."""
        data1 = table.load_table("weather")
        data2 = table.load_table("weather")
        assert data1 is data2  # same object (cached)

    def test_table_missing_name_raises(self, tmp_path: Path):
        """A JSON file without a 'name' field should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "die": "1d6",
                    "entries": [{"range": [1, 6], "result": "oops"}],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="missing required 'name'"):
            rt.load_table("bad")

    def test_table_missing_die_raises(self, tmp_path: Path):
        """A JSON file without a 'die' field should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "entries": [{"range": [1, 6], "result": "oops"}],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="missing required 'die'"):
            rt.load_table("bad")

    def test_empty_entries_raises(self, tmp_path: Path):
        """A table with an empty entries list should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="empty 'entries'"):
            rt.load_table("bad")


# ===========================================================================
# Lookup tests
# ===========================================================================


class TestLookup:
    """Table lookups produce correct results."""

    def test_lookup_returns_expected_keys(self, table: RandomTable):
        """Lookup result should contain result, roll, table, and sub_rolls."""
        result = table.lookup("npc_traits")
        assert "result" in result
        assert "roll" in result
        assert "table" in result
        assert "sub_rolls" in result

    def test_lookup_result_is_string(self, table: RandomTable):
        """The result field should be a non-empty string."""
        result = table.lookup("npc_traits")
        assert isinstance(result["result"], str)
        assert len(result["result"]) > 0

    def test_lookup_roll_contains_expected_keys(self, table: RandomTable):
        """The roll dict should contain total, rolls, sides, formula."""
        result = table.lookup("npc_traits")
        roll_data = result["roll"]
        assert "total" in roll_data
        assert "rolls" in roll_data
        assert "sides" in roll_data
        assert "formula" in roll_data

    def test_lookup_table_name_in_result(self, table: RandomTable):
        """Result should include the table name used."""
        result = table.lookup("weather")
        assert result["table"] == "weather"

    def test_lookup_sub_rolls_defaults_to_empty(self, table: RandomTable):
        """Results without nested table refs should have empty sub_rolls."""
        result = table.lookup("npc_traits")
        assert result["sub_rolls"] == []

    def test_invalid_table_name_raises(self, table: RandomTable):
        """Looking up a nonexistent table raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            table.lookup("this_does_not_exist")

    def test_single_entry_table(self, temp_table: Path):
        """A table with a single entry always returns that result."""
        rt = RandomTable(temp_table)
        for _ in range(20):
            result = rt.lookup("always_42")
            assert result["result"] == "You always get this result."


class TestLookupRanges:
    """Lookup results fall within valid entry ranges."""

    def test_lookup_within_range(self, table: RandomTable):
        """Lookup result roll total should be within expected range."""
        for _ in range(50):
            result = table.lookup("encounters")
            total = result["roll"]["total"]
            assert 1 <= total <= 20

    def test_loot_range(self, table: RandomTable):
        """Loot table uses 1d100, values should be 1..100."""
        for _ in range(50):
            result = table.lookup("loot")
            total = result["roll"]["total"]
            assert 1 <= total <= 100

    def test_weather_range(self, table: RandomTable):
        """Weather table uses 1d20."""
        for _ in range(50):
            result = table.lookup("weather")
            total = result["roll"]["total"]
            assert 1 <= total <= 20

    def test_npc_traits_range(self, table: RandomTable):
        """NPC traits table uses 1d12."""
        for _ in range(50):
            result = table.lookup("npc_traits")
            total = result["roll"]["total"]
            assert 1 <= total <= 12


class TestLookupVaried:
    """Multiple lookups produce varied results over many rolls."""

    def test_encounters_varied(self, table: RandomTable):
        """Over many rolls we should see at least 3 different encounter results."""
        results: set[str] = set()
        for _ in range(100):
            result = table.lookup("encounters")
            results.add(result["result"])
        assert len(results) >= 3, (
            f"Expected at least 3 different encounter results, got {len(results)}"
        )

    def test_loot_varied(self, table: RandomTable):
        """Over many rolls we should see at least 3 different loot results."""
        results: set[str] = set()
        for _ in range(200):
            result = table.lookup("loot")
            results.add(result["result"])
        assert len(results) >= 3, (
            f"Expected at least 3 different loot results, got {len(results)}"
        )

    def test_weather_varied(self, table: RandomTable):
        """Over many rolls we should see at least 3 different weather results."""
        results: set[str] = set()
        for _ in range(100):
            result = table.lookup("weather")
            results.add(result["result"])
        assert len(results) >= 3, (
            f"Expected at least 3 different weather results, got {len(results)}"
        )

    def test_npc_traits_varied(self, table: RandomTable):
        """Over many rolls we should see at least 5 different trait results."""
        results: set[str] = set()
        for _ in range(100):
            result = table.lookup("npc_traits")
            results.add(result["result"])
        assert len(results) >= 5, (
            f"Expected at least 5 different trait results, got {len(results)}"
        )


# ===========================================================================
# Nested table references
# ===========================================================================


class TestNestedTables:
    """Entries with a 'table' field trigger sub-rolls."""

    def test_encounter_has_nested_refs(self, table: RandomTable):
        """The encounters table has at least one entry with a nested ref."""
        data = table.load_table("encounters")
        has_nested = any("table" in e for e in data["entries"])
        assert has_nested, "Expected at least one nested table reference in encounters"

    def test_lookup_returns_sub_rolls_when_applicable(self, table: RandomTable):
        """When matching entry has a nested ref, sub_rolls should be populated."""
        # The first entry (range 1-3) references "weather".
        # Mock roll to return a value in that range.
        with patch("app.dice.tables.roll") as mock_roll:
            # First call for encounters table, second for the nested weather table
            # encounters roll, then nested weather sub-roll
            mock_roll.side_effect = [
                {"total": 2, "rolls": [2], "sides": 20, "formula": "1d20"},
                {"total": 10, "rolls": [10], "sides": 20, "formula": "1d20"},
            ]
            result = table.lookup("encounters")

        assert result["result"] == (
            "A pack of slavering wolves encircles the party, "
            "hackles raised and eyes glowing in the dark."
        )
        assert len(result["sub_rolls"]) == 1
        sub = result["sub_rolls"][0]
        assert sub["table"] == "weather"
        assert sub["result"] == (
            "Light drizzle and drifting fog. "
            "Visibility is poor; sounds are muffled and strange."
        )

    def test_sub_roll_has_correct_shape(self, table: RandomTable):
        """Sub-rolls should have the same shape as top-level results."""
        with patch("app.dice.tables.roll") as mock_roll:
            # encounters roll, then nested weather sub-roll
            mock_roll.side_effect = [
                {"total": 2, "rolls": [2], "sides": 20, "formula": "1d20"},
                {"total": 10, "rolls": [10], "sides": 20, "formula": "1d20"},
            ]
            result = table.lookup("encounters")

        sub = result["sub_rolls"][0]
        assert "result" in sub
        assert "roll" in sub
        assert "table" in sub
        assert "sub_rolls" in sub
        # Sub-roll itself should have no further nested results
        assert sub["sub_rolls"] == []


# ===========================================================================
# Error handling
# ===========================================================================


class TestErrorHandling:
    """Robust error handling for edge cases."""

    def test_recursion_depth_exceeded(self, tmp_path: Path):
        """Circular table references should eventually raise."""
        # Create two tables that point to each other
        table_a = tmp_path / "table_a.json"
        table_b = tmp_path / "table_b.json"
        table_a.write_text(
            json.dumps(
                {
                    "name": "table_a",
                    "die": "1d6",
                    "entries": [
                        {
                            "range": [1, 6],
                            "result": "Pointing to B",
                            "table": "table_b",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        table_b.write_text(
            json.dumps(
                {
                    "name": "table_b",
                    "die": "1d6",
                    "entries": [
                        {
                            "range": [1, 6],
                            "result": "Pointing to A",
                            "table": "table_a",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="recursion depth"):
            rt.lookup("table_a")

    def test_range_covers_all_values(self, table: RandomTable):
        """Every possible die result should match at least one entry."""
        for table_name in ("encounters", "weather", "npc_traits"):
            data = table.load_table(table_name)
            die_parts = data["die"].split("d")
            max_val = int(die_parts[1])
            covered = set()
            for entry in data["entries"]:
                r_min, r_max = entry["range"]
                covered.update(range(r_min, r_max + 1))
            # Every value from 1..max_val should appear in at least one range
            for val in range(1, max_val + 1):
                assert val in covered, (
                    f"Table '{table_name}': value {val} not covered by any entry range"
                )

    def test_corrupted_json_raises(self, tmp_path: Path):
        """Invalid JSON should raise json.JSONDecodeError."""
        bad_file = tmp_path / "corrupt.json"
        bad_file.write_text("this is not json", encoding="utf-8")
        rt = RandomTable(tmp_path)
        with pytest.raises(json.JSONDecodeError):
            rt.load_table("corrupt")


# ===========================================================================
# Tests for Bugs 1 & 2: Entry validation (missing range/result, reversed)
# ===========================================================================


class TestEntryValidation:
    """Table entries must have valid ``range`` and ``result`` fields."""

    def test_missing_range_in_entry_raises(self, tmp_path: Path):
        """Entry without 'range' field should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"result": "no range here"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="missing.*'range'"):
            rt.load_table("bad")

    def test_missing_result_in_entry_raises(self, tmp_path: Path):
        """Entry without 'result' field should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": [1, 6]},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="missing.*'result'"):
            rt.load_table("bad")

    def test_range_not_a_list_raises(self, tmp_path: Path):
        """Entry with non-list range should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": "1-6", "result": "oops"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="range"):
            rt.load_table("bad")

    def test_range_wrong_length_raises(self, tmp_path: Path):
        """Entry with range of wrong length should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": [1, 2, 3], "result": "oops"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="range"):
            rt.load_table("bad")

    def test_reversed_range_raises(self, tmp_path: Path):
        """Entry with reversed range [3, 1] should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": [3, 1], "result": "reversed range never matches"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="reversed"):
            rt.load_table("bad")

    def test_range_with_non_int_raises(self, tmp_path: Path):
        """Entry with non-integer range values should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": [1, "six"], "result": "bad range values"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="range"):
            rt.load_table("bad")

    def test_result_not_a_string_raises(self, tmp_path: Path):
        """Entry with non-string result should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": [1, 6], "result": 42},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="result.*string"):
            rt.load_table("bad")

    def test_entry_not_a_dict_raises(self, tmp_path: Path):
        """Entry that is not an object should raise ValueError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": ["just a string"],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="entry 0"):
            rt.load_table("bad")

    def test_multiple_entries_second_bad_is_reported(self, tmp_path: Path):
        """The correct index should be reported when later entry is bad."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text(
            json.dumps(
                {
                    "name": "bad",
                    "die": "1d6",
                    "entries": [
                        {"range": [1, 3], "result": "good entry"},
                        {"range": [3, 1], "result": "reversed range"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rt = RandomTable(tmp_path)
        with pytest.raises(ValueError, match="entry 1"):
            rt.load_table("bad")
