"""
Shared pytest fixtures for Speculae tests.
"""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from speculae import db
from speculae.config import PatternsConfig
from speculae.models import Entry


@pytest.fixture
def tmp_db(tmp_path):
    """An in-memory-equivalent Database backed by a temp file."""
    path = tmp_path / "test_journal.db"
    database = db.Database(path)
    database.connect()
    yield database
    database.close()


def _make_entry(
    days_ago: int = 0,
    mood: int | None = 3,
    energy: int | None = 3,
    content: str = "Test entry",
    tags: list[str] | None = None,
) -> Entry:
    """Helper to create Entry instances for tests."""
    return Entry(
        date=date.today() - timedelta(days=days_ago),
        content=content,
        mood=mood,
        energy=energy,
        tags=tags or [],
    )


def _insert_entries(database: db.Database, entries: list[Entry]) -> list[Entry]:
    """Bulk-insert entries and return them with IDs assigned."""
    saved = []
    for e in entries:
        saved.append(db.save_entry(database, e))
    return saved


@pytest.fixture
def default_patterns_cfg() -> PatternsConfig:
    return PatternsConfig(
        arc_window_days=7,
        arc_threshold=0.3,
        cycle_min_period_days=5,
        cycle_max_period_days=30,
        blindspot_multiplier=2.0,
        min_entries_for_patterns=7,
    )
