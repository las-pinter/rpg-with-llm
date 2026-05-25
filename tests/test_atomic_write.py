"""Tests for the atomic file write utility."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.utils.atomic_write import atomic_write


class TestAtomicWriteHappyPath:
    """Successful writes — data lands correctly, no leftover tmp files."""

    def test_writes_and_reads_back_data(self, tmp_path: Path) -> None:
        """Write a dict, read it back, verify content matches."""
        data = {"name": "Grubnik", "role": "tinkerer", "level": 3}
        dest = tmp_path / "character.json"

        atomic_write(dest, data)

        assert dest.exists()
        with open(dest, encoding="utf-8") as f:
            result = json.load(f)
        assert result == data

    def test_no_tmp_file_after_success(self, tmp_path: Path) -> None:
        """Verify .tmp file is removed after successful write."""
        data = {"ok": True}
        dest = tmp_path / "data.json"

        atomic_write(dest, data)

        tmp_file = tmp_path / "data.json.tmp"
        assert not tmp_file.exists()

    def test_writes_to_nested_path(self, tmp_path: Path) -> None:
        """Write into an existing nested directory structure."""
        data = {"nested": True}
        dest = tmp_path / "sub" / "dir" / "data.json"
        dest.parent.mkdir(parents=True)

        atomic_write(dest, data)

        assert dest.exists()
        with open(dest, encoding="utf-8") as f:
            assert json.load(f) == data


class TestAtomicWriteIndent:
    """Indentation parameter controls formatting."""

    def test_default_indent_is_two(self, tmp_path: Path) -> None:
        """Default indent=2 produces 2-space indentation."""
        data = {"a": {"b": 1}}
        dest = tmp_path / "data.json"

        atomic_write(dest, data)

        with open(dest, encoding="utf-8") as f:
            lines = f.readlines()
        # Nested key should be indented 4 spaces (2 + 2)
        b_line = next(line for line in lines if '"b"' in line)
        leading = len(b_line) - len(b_line.lstrip())
        assert leading == 4

    def test_custom_indent_four(self, tmp_path: Path) -> None:
        """indent=4 produces 4-space indentation."""
        data = {"x": 1}
        dest = tmp_path / "data.json"

        atomic_write(dest, data, indent=4)

        content = dest.read_text(encoding="utf-8")
        # "x" should be indented by 4 spaces
        assert '    "x"' in content


class TestAtomicWriteFailure:
    """Error handling — cleanup, missing dirs, and re-raise."""

    def test_raises_on_nonexistent_directory(self, tmp_path: Path) -> None:
        """Writing to a non-existent directory raises FileNotFoundError."""
        data = {"a": 1}
        dest = tmp_path / "nonexistent" / "file.json"

        with pytest.raises(FileNotFoundError):
            atomic_write(dest, data)

    def test_cleans_up_stale_tmp_file_on_open_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        If open() raises, any stale .tmp file (from a prior crash) is
        cleaned up by the exception handler.
        """
        data = {"a": 1}
        dest = tmp_path / "data.json"
        tmp_file = tmp_path / "data.json.tmp"

        # Create a stale tmp file as if from a previous crash
        tmp_file.write_text("stale garbage")
        assert tmp_file.exists()

        def raising_open(*args: object, **kwargs: object) -> object:
            raise OSError("Disk full")

        monkeypatch.setattr("builtins.open", raising_open)

        with pytest.raises(OSError):
            atomic_write(dest, data)

        # Stale tmp file should have been cleaned up
        assert not tmp_file.exists()

    def test_cleans_up_own_tmp_file_on_rename_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        If os.replace() raises, the tmp file created during this call
        is cleaned up by the exception handler.
        """
        data = {"a": 1}
        dest = tmp_path / "data.json"
        tmp_file = tmp_path / "data.json.tmp"

        def raising_replace(*args: object, **kwargs: object) -> object:
            raise OSError("Permission denied")

        monkeypatch.setattr("os.replace", raising_replace)

        with pytest.raises(OSError):
            atomic_write(dest, data)

        # Tmp file should not remain on disk
        assert not tmp_file.exists()

    def test_tmp_file_collision_overwritten(self, tmp_path: Path) -> None:
        """
        If a stale .tmp file exists from a previous crash,
        it gets overwritten and the final write succeeds.
        """
        data = {"fresh": "data"}
        dest = tmp_path / "data.json"
        tmp_file = tmp_path / "data.json.tmp"

        # Pre-create a stale tmp file
        tmp_file.write_text('{"stale": true}')

        # Should succeed despite stale tmp file
        atomic_write(dest, data)

        # Final file has fresh data
        with open(dest, encoding="utf-8") as f:
            result = json.load(f)
        assert result == data

        # Tmp file should be removed after success
        assert not tmp_file.exists()
