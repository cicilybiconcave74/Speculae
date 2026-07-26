"""
Tests for export/import round-trip via the CLI and the DB layer.

We test the JSON serialisation format directly rather than running the
full Typer CLI to avoid subprocess complexity.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from speculae import db
from speculae.models import Entry


def _make_entry(days_ago: int, mood: int | None = 3, energy: int | None = 2,
                content: str = "test", tags: list[str] | None = None) -> Entry:
    return Entry(
        date=date.today() - timedelta(days=days_ago),
        mood=mood,
        energy=energy,
        content=content,
        tags=tags or [],
    )


def _entry_to_dict(e: Entry) -> dict:
    """Mirrors the export format in cli.export."""
    return {
        "date": e.date.isoformat(),
        "content": e.content,
        "mood": e.mood,
        "energy": e.energy,
        "tags": e.tags,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


class TestJSONRoundTrip:
    """Verify that export → JSON → import produces identical entries."""

    def test_roundtrip_preserves_all_fields(self, tmp_db, tmp_path):
        original = _make_entry(
            days_ago=1,
            mood=4,
            energy=3,
            content="A detailed entry with paragraphs.\n\nSecond paragraph here.",
            tags=["work", "gratitude"],
        )
        saved = db.save_entry(tmp_db, original)

        # Simulate export
        data = [_entry_to_dict(saved)]
        json_file = tmp_path / "export.json"
        json_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Simulate import into a fresh DB
        raw = json.loads(json_file.read_text(encoding="utf-8"))
        item = raw[0]
        imported = Entry(
            date=date.fromisoformat(item["date"]),
            content=item["content"],
            mood=item["mood"],
            energy=item["energy"],
            tags=item["tags"],
        )

        assert imported.date == saved.date
        assert imported.content == saved.content
        assert imported.mood == saved.mood
        assert imported.energy == saved.energy
        assert imported.tags == saved.tags

    def test_export_json_is_valid_json(self, tmp_db, tmp_path):
        entries = [_make_entry(i) for i in range(5)]
        for e in entries:
            db.save_entry(tmp_db, e)

        all_entries = db.list_entries(tmp_db, limit=100)
        data = [_entry_to_dict(e) for e in all_entries]
        text = json.dumps(data, indent=2, ensure_ascii=False)

        # Should parse without error
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        assert len(parsed) == 5

    def test_export_json_schema(self, tmp_db):
        e = _make_entry(0, mood=5, energy=5, tags=["test"])
        saved = db.save_entry(tmp_db, e)
        d = _entry_to_dict(saved)

        required_keys = {"date", "content", "mood", "energy", "tags"}
        assert required_keys.issubset(d.keys())
        assert isinstance(d["date"], str)
        assert isinstance(d["tags"], list)
        assert d["mood"] == 5
        assert d["energy"] == 5

    def test_null_mood_and_energy_in_export(self, tmp_db):
        e = _make_entry(0, mood=None, energy=None)
        saved = db.save_entry(tmp_db, e)
        d = _entry_to_dict(saved)

        assert d["mood"] is None
        assert d["energy"] is None


class TestImportValidation:
    """Validate the import parsing logic matches what the CLI enforces."""

    def _parse_import(self, items: list[dict]) -> tuple[list[Entry], list[str]]:
        """Mirror of the import validation in cli.import_entries."""
        parsed = []
        errors = []

        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(f"Item {i}: expected object")
                continue
            if "date" not in item:
                errors.append(f"Item {i}: missing 'date'")
                continue
            try:
                entry_date = date.fromisoformat(item["date"])
            except ValueError:
                errors.append(f"Item {i}: invalid date {item['date']!r}")
                continue

            mood = item.get("mood")
            energy = item.get("energy")
            if mood is not None and not (isinstance(mood, int) and 1 <= mood <= 5):
                errors.append(f"Item {i}: invalid mood {mood!r}")
                mood = None
            if energy is not None and not (isinstance(energy, int) and 1 <= energy <= 5):
                errors.append(f"Item {i}: invalid energy {energy!r}")
                energy = None

            tags = item.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            parsed.append(Entry(
                date=entry_date,
                content=item.get("content", ""),
                mood=mood,
                energy=energy,
                tags=[str(t) for t in tags if t],
            ))

        return parsed, errors

    def test_valid_minimal_item(self):
        items = [{"date": "2026-01-15"}]
        parsed, errors = self._parse_import(items)
        assert len(errors) == 0
        assert len(parsed) == 1
        assert parsed[0].date == date(2026, 1, 15)

    def test_missing_date_produces_error(self):
        items = [{"content": "No date here"}]
        _, errors = self._parse_import(items)
        assert any("missing" in e and "date" in e for e in errors)

    def test_invalid_date_format_produces_error(self):
        items = [{"date": "July 20 2026"}]
        _, errors = self._parse_import(items)
        assert any("invalid date" in e for e in errors)

    def test_out_of_range_mood_is_cleared(self):
        items = [{"date": "2026-01-01", "mood": 99}]
        parsed, errors = self._parse_import(items)
        assert any("mood" in e for e in errors)
        assert parsed[0].mood is None

    def test_valid_mood_and_energy_pass_through(self):
        items = [{"date": "2026-01-01", "mood": 4, "energy": 2}]
        parsed, errors = self._parse_import(items)
        assert len(errors) == 0
        assert parsed[0].mood == 4
        assert parsed[0].energy == 2

    def test_non_list_tags_become_empty(self):
        items = [{"date": "2026-01-01", "tags": "work,rest"}]
        parsed, _ = self._parse_import(items)
        assert parsed[0].tags == []

    def test_multiple_items_partially_valid(self):
        items = [
            {"date": "2026-01-01", "mood": 3},
            {"content": "missing date"},
            {"date": "not-a-date"},
            {"date": "2026-01-04", "mood": 1},
        ]
        parsed, errors = self._parse_import(items)
        assert len(parsed) == 2
        assert len(errors) == 2


class TestMergeLogic:
    """Test import semantics with multi-entry support."""

    def test_import_adds_entries_without_removing_originals(self, tmp_db):
        original = _make_entry(0, content="Original", mood=2)
        db.save_entry(tmp_db, original)

        incoming = Entry(date=original.date, content="Imported entry", mood=5)
        db.save_entry(tmp_db, incoming)

        results = db.get_entries_for_date(tmp_db, original.date)
        assert len(results) == 2
        contents = {r.content for r in results}
        assert "Original" in contents
        assert "Imported entry" in contents

    def test_multiple_entries_for_same_date(self, tmp_db):
        e1 = _make_entry(0, content="First", mood=3)
        e2 = _make_entry(0, content="Second", mood=5)
        db.save_entry(tmp_db, e1)
        db.save_entry(tmp_db, e2)

        results = db.get_entries_for_date(tmp_db, e1.date)
        assert len(results) == 2

    def test_import_preserves_entries_not_in_file(self, tmp_db):
        keep_me = _make_entry(5, content="Keep me", mood=4)
        db.save_entry(tmp_db, keep_me)

        incoming = _make_entry(0, content="New entry")
        db.save_entry(tmp_db, incoming)

        results = db.get_entries_for_date(tmp_db, keep_me.date)
        assert len(results) == 1
        assert results[0].content == "Keep me"
