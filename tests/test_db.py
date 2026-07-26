"""
Tests for speculae.db — CRUD, FTS5 search, patterns, insights.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import sqlite3
import time

import pytest

from speculae import db
from speculae.models import Entry, Image, Insight, Pattern

from .conftest import _make_entry, _insert_entries


# ── Entry CRUD ────────────────────────────────────────────────────────────────

class TestEntryCreate:
    def test_upsert_creates_entry(self, tmp_db):
        entry = _make_entry(days_ago=0, mood=4, energy=3, content="Hello world")
        saved = db.save_entry(tmp_db, entry)
        assert saved.id != ""
        assert saved.created_at is not None
        assert saved.updated_at is not None

    def test_upsert_updates_by_id(self, tmp_db):
        entry = _make_entry(days_ago=0, content="First draft")
        saved = db.save_entry(tmp_db, entry)

        saved.content = "Second draft"
        saved.mood = 5
        saved.energy = 4
        saved.tags = ["updated"]
        saved2 = db.save_entry(tmp_db, saved)

        assert saved2.id == saved.id
        assert saved2.content == "Second draft"
        assert saved2.mood == 5
        assert saved2.tags == ["updated"]

    def test_upsert_keeps_created_at_on_update(self, tmp_db):
        entry = _make_entry(days_ago=0, content="First")
        saved = db.save_entry(tmp_db, entry)
        original_created = saved.created_at

        saved.content = "Updated"
        saved2 = db.save_entry(tmp_db, saved)
        assert saved2.created_at == original_created

    def test_get_entries_for_date_empty(self, tmp_db):
        result = db.get_entries_for_date(tmp_db, date(1970, 1, 1))
        assert result == []

    def test_get_entries_for_date_roundtrip(self, tmp_db):
        entry = _make_entry(days_ago=1, mood=2, energy=1, content="Yesterday", tags=["hard"])
        db.save_entry(tmp_db, entry)

        results = db.get_entries_for_date(tmp_db, entry.date)
        assert len(results) == 1
        assert results[0].content == "Yesterday"
        assert results[0].mood == 2
        assert results[0].energy == 1
        assert results[0].tags == ["hard"]

    def test_delete_entry_by_id(self, tmp_db):
        entry = _make_entry(days_ago=2)
        saved = db.save_entry(tmp_db, entry)

        deleted = db.delete_entry(tmp_db, saved.id)
        assert deleted is True
        assert db.get_entries_for_date(tmp_db, entry.date) == []

    def test_delete_nonexistent_returns_false(self, tmp_db):
        assert db.delete_entry(tmp_db, "nonexistent-id") is False


class TestEntryList:
    def test_list_returns_newest_first(self, tmp_db):
        entries = [_make_entry(days_ago=i, content=f"day {i}") for i in range(5)]
        _insert_entries(tmp_db, entries)

        result = db.list_entries(tmp_db, limit=10)
        dates = [e.date for e in result]
        assert dates == sorted(dates, reverse=True)

    def test_list_respects_limit(self, tmp_db):
        entries = [_make_entry(days_ago=i) for i in range(10)]
        _insert_entries(tmp_db, entries)

        result = db.list_entries(tmp_db, limit=5)
        assert len(result) == 5

    def test_list_respects_since(self, tmp_db):
        entries = [_make_entry(days_ago=i) for i in range(10)]
        _insert_entries(tmp_db, entries)

        cutoff = date.today() - timedelta(days=3)
        result = db.list_entries(tmp_db, limit=100, since=cutoff)
        assert all(e.date >= cutoff for e in result)

    def test_entry_count(self, tmp_db):
        assert db.entry_count(tmp_db) == 0
        entries = [_make_entry(days_ago=i) for i in range(7)]
        _insert_entries(tmp_db, entries)
        assert db.entry_count(tmp_db) == 7

    def test_date_range(self, tmp_db):
        assert db.date_range(tmp_db) == (None, None)

        entries = [_make_entry(days_ago=i) for i in range(5)]
        _insert_entries(tmp_db, entries)

        first, last = db.date_range(tmp_db)
        assert first is not None
        assert last is not None
        assert first < last


class TestFTSSearch:
    def test_search_finds_matching_entry(self, tmp_db):
        db.save_entry(tmp_db, _make_entry(days_ago=0, content="The quick brown fox"))
        db.save_entry(tmp_db, _make_entry(days_ago=1, content="Unrelated content"))

        results = db.search_entries(tmp_db, "fox")
        assert len(results) == 1
        assert "fox" in results[0].content

    def test_delete_entries_batch(self, tmp_db):
        e1 = _make_entry(days_ago=0, content="Entry 1")
        e2 = _make_entry(days_ago=1, content="Entry 2")
        e3 = _make_entry(days_ago=2, content="Entry 3")
        db.save_entry(tmp_db, e1)
        db.save_entry(tmp_db, e2)
        db.save_entry(tmp_db, e3)

        count = db.delete_entries_batch(tmp_db, [e1.id, e2.id])
        assert count == 2
        remaining = db.list_entries(tmp_db)
        assert len(remaining) == 1
        assert remaining[0].id == e3.id

    def test_search_returns_empty_for_no_match(self, tmp_db):
        db.save_entry(tmp_db, _make_entry(content="Something else"))
        results = db.search_entries(tmp_db, "xyznotfound")
        assert results == []


# ── Pattern CRUD ──────────────────────────────────────────────────────────────

class TestPatternCRUD:
    def _make_pattern(self, title="Test pattern"):
        return Pattern(
            type="arc",
            title=title,
            description="A test pattern.",
            severity="notable",
            data={"metric": "mood"},
        )

    def test_save_and_list_patterns(self, tmp_db):
        p1 = self._make_pattern("Pattern A")
        p2 = self._make_pattern("Pattern B")
        db.save_patterns(tmp_db, [p1, p2])

        patterns = db.list_patterns(tmp_db)
        titles = {p.title for p in patterns}
        assert "Pattern A" in titles
        assert "Pattern B" in titles

    def test_save_replaces_previous_patterns(self, tmp_db):
        db.save_patterns(tmp_db, [self._make_pattern("Old")])
        db.save_patterns(tmp_db, [self._make_pattern("New")])

        patterns = db.list_patterns(tmp_db)
        titles = {p.title for p in patterns}
        assert "Old" not in titles
        assert "New" in titles

    def test_patterns_get_ids_assigned(self, tmp_db):
        p = self._make_pattern()
        assert p.id == ""
        db.save_patterns(tmp_db, [p])
        assert p.id != ""


# ── Insight CRUD ──────────────────────────────────────────────────────────────

class TestInsightCRUD:
    def test_save_and_retrieve_insight(self, tmp_db):
        insight = Insight(
            period_start=date.today() - timedelta(days=6),
            period_end=date.today(),
            content="This week you were steadier than last.",
            type="weekly",
        )
        db.save_insight(tmp_db, insight)

        fetched = db.latest_insight(tmp_db)
        assert fetched is not None
        assert fetched.content == "This week you were steadier than last."

    def test_latest_insight_returns_none_when_empty(self, tmp_db):
        assert db.latest_insight(tmp_db) is None

    def test_list_agents_detailed(self, tmp_db):
        e1 = Entry(date=date(2026, 7, 20), content="Agent 1 entry 1", agent_id="agent1")
        e2 = Entry(date=date(2026, 7, 21), content="Agent 1 entry 2", agent_id="agent1")
        e3 = Entry(date=date(2026, 7, 22), content="Agent 2 entry 1", agent_id="agent2")
        db.save_entry(tmp_db, e1)
        db.save_entry(tmp_db, e2)
        db.save_entry(tmp_db, e3)

        agents = db.list_agents_detailed(tmp_db)
        assert len(agents) == 2
        agent2_info = next(a for a in agents if a["id"] == "agent2")
        agent1_info = next(a for a in agents if a["id"] == "agent1")

        assert agent2_info["entry_count"] == 1
        assert agent1_info["entry_count"] == 2
        assert agent1_info["latest_date"] == "2026-07-21"


class TestPatternsAreStale:
    def test_own_write_marks_patterns_stale(self, tmp_db):
        entry = Entry(date=date(2024, 1, 1), content="hello", agent_id="agent_a")
        db.save_entry(tmp_db, entry)
        assert db.patterns_are_stale(tmp_db, agent_id="agent_a")

        time.sleep(0.01)
        pattern = Pattern(type="arc", title="T", description="D", severity="info")
        db.save_patterns(tmp_db, [pattern], agent_id="agent_a")
        assert not db.patterns_are_stale(tmp_db, agent_id="agent_a")

        time.sleep(0.01)
        entry2 = Entry(date=date(2024, 1, 2), content="update", agent_id="agent_a")
        db.save_entry(tmp_db, entry2)
        assert db.patterns_are_stale(tmp_db, agent_id="agent_a")

    def test_other_agent_write_does_not_mark_patterns_stale(self, tmp_db):
        entry_a = Entry(date=date(2024, 1, 1), content="agent a", agent_id="agent_a")
        db.save_entry(tmp_db, entry_a)
        time.sleep(0.01)
        pattern = Pattern(type="arc", title="T", description="D", severity="info")
        db.save_patterns(tmp_db, [pattern], agent_id="agent_a")
        assert not db.patterns_are_stale(tmp_db, agent_id="agent_a")

        time.sleep(0.01)
        entry_b = Entry(date=date(2024, 1, 2), content="agent b", agent_id="agent_b")
        db.save_entry(tmp_db, entry_b)
        assert not db.patterns_are_stale(tmp_db, agent_id="agent_a")

    def test_human_write_does_not_mark_agent_patterns_stale(self, tmp_db):
        entry_agent = Entry(date=date(2024, 1, 1), content="bot", agent_id="bot_x")
        db.save_entry(tmp_db, entry_agent)
        time.sleep(0.01)
        pattern = Pattern(type="arc", title="T", description="D", severity="info")
        db.save_patterns(tmp_db, [pattern], agent_id="bot_x")
        assert not db.patterns_are_stale(tmp_db, agent_id="bot_x")

        time.sleep(0.01)
        entry_human = Entry(date=date(2024, 1, 2), content="human", agent_id=None)
        db.save_entry(tmp_db, entry_human)
        assert not db.patterns_are_stale(tmp_db, agent_id="bot_x")


class TestImageStorage:
    def test_save_image_writes_file_and_metadata(self, tmp_db):
        entry = Entry(date=date(2026, 7, 21), content="photo day")
        saved = db.save_entry(tmp_db, entry)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

        img = db.save_image(tmp_db, saved.id, "snap.png", png, "image/png")
        assert img.storage_path
        assert img.file_size == len(png)

        path = db.get_image_file_path(tmp_db, img.id)
        assert path is not None
        assert path.read_bytes() == png

        listed = db.get_images_for_entry(tmp_db, saved.id)
        assert len(listed) == 1
        assert listed[0].data == b""  # metadata-only listing

    def test_get_image_by_id_loads_bytes(self, tmp_db):
        entry = Entry(date=date(2026, 7, 21), content="load test")
        saved = db.save_entry(tmp_db, entry)
        data = b"\x89PNG\r\n\x1a\n" + b"\xff" * 32
        img = db.save_image(tmp_db, saved.id, "t.png", data)

        loaded = db.get_image_by_id(tmp_db, img.id, load_data=True)
        assert loaded is not None
        assert loaded.data == data

    def test_delete_image_removes_file(self, tmp_db):
        entry = Entry(date=date(2026, 7, 21), content="delete test")
        saved = db.save_entry(tmp_db, entry)
        img = db.save_image(tmp_db, saved.id, "d.png", b"testdata")
        path = db.get_image_file_path(tmp_db, img.id)
        assert path is not None

        assert db.delete_image(tmp_db, img.id) is True
        assert db.get_image_by_id(tmp_db, img.id) is None
        assert not path.exists()

    def test_legacy_blob_upgrade(self, tmp_path):
        """Pre-release DBs with inline BLOBs upgrade silently on connect."""
        path = tmp_path / "legacy.db"
        # Build an old-style images table manually
        conn = sqlite3.connect(str(path))
        conn.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO meta VALUES ('schema_version', '1');
            CREATE TABLE entries (
                id TEXT PRIMARY KEY, date TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, content TEXT NOT NULL DEFAULT '',
                mood INTEGER, energy INTEGER, tags TEXT NOT NULL DEFAULT '[]',
                embedding TEXT, starred INTEGER NOT NULL DEFAULT 0, agent_id TEXT
            );
            CREATE TABLE images (
                id TEXT PRIMARY KEY, entry_id TEXT NOT NULL, filename TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT 'image/png',
                data BLOB NOT NULL, created_at TEXT NOT NULL
            );
        """)
        entry_id = "entry-legacy"
        image_id = "img-legacy"
        blob = b"\x89PNG\r\n\x1a\nlegacy-bytes"
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, "2026-01-15", now, now, "legacy", None, None, "[]", None, 0, None),
        )
        conn.execute(
            "INSERT INTO images VALUES (?, ?, ?, ?, ?, ?)",
            (image_id, entry_id, "old.png", "image/png", blob, now),
        )
        conn.commit()
        conn.close()

        database = db.Database(path)
        database.connect()
        loaded = db.get_image_by_id(database, image_id, load_data=True)
        assert loaded is not None
        assert loaded.data == blob
        assert loaded.storage_path
        assert db.get_image_file_path(database, image_id) is not None
        database.close()
