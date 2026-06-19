"""
Shared atomic file write utilities.

Provides atomic_write() for safely writing JSON data to disk using
a write-to-tmp-then-rename pattern, preventing partial/corrupt files.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_write(path: Path, data: Any, indent: int = 2) -> None:
    """
    Atomically write *data* as JSON to *path*.

    Writes to a .tmp file first, then renames to final path.
    Cleans up tmp file on failure.

    *data* can be any JSON-serialisable value (dict, list, etc.).
    """
    tmp_path = path.parent / (path.name + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
