"""Shared fixtures for save-engine tests."""

import copy
import pytest
from app.save_engine.migration import MIGRATIONS


@pytest.fixture(autouse=True)
def _clean_migrations():
    """Save and restore the global MIGRATIONS dict around each test."""
    saved = copy.deepcopy(dict(MIGRATIONS))
    yield
    MIGRATIONS.clear()
    MIGRATIONS.update(saved)
