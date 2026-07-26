#!/usr/bin/env python3
"""
Standalone JSON import helper for Speculae.

Use this if you want to import data without the full `speculae` CLI installed,
or as a script reference for building your own import pipeline.

Usage:
  python scripts/import_json.py journal.json
  python scripts/import_json.py journal.json --db /path/to/journal.db
  python scripts/import_json.py journal.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path


DEFAULT_DB = Path.home() / ".local" / "share" / "speculae" / "journal.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS entries (
            id          TEXT PRIMARY KEY,
            date        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            content     TEXT NOT NULL DEFAULT '',
            mood        INTEGER,
            energy      INTEGER,
            tags        TEXT NOT NULL DEFAULT '[]',
            embedding   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date);

        CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
            content,
            tags,
            content='entries',
            content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
            INSERT INTO entries_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
        END;
        CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, content, tags)
            VALUES ('delete', old.rowid, old.content, old.tags);
        END;
        CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
            INSERT INTO entries_fts(entries_fts, rowid, content, tags)
            VALUES ('delete', old.rowid, old.content, old.tags);
            INSERT INTO entries_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
        END;

        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '2');
        INSERT OR IGNORE INTO meta (key, value) VALUES ('entry_count', '0');
    """)
    conn.commit()
    return conn


def _upsert(conn: sqlite3.Connection, item: dict, overwrite: bool) -> str:
    """Insert or update one entry. Returns 'inserted', 'updated', or 'skipped'."""
    date_str = item["date"]

    if overwrite:
        existing = conn.execute(
            "SELECT id, created_at FROM entries WHERE date = ? ORDER BY created_at DESC LIMIT 1",
            (date_str,),
        ).fetchone()
    else:
        existing = None  # skip check happens below

    if existing and not overwrite:
        return "skipped"

    entry_id = existing["id"] if existing else str(uuid.uuid4())
    created_at = (existing["created_at"] if existing
                  else (item.get("created_at") or datetime.now(timezone.utc).isoformat()))
    updated_at = item.get("updated_at") or datetime.now(timezone.utc).isoformat()

    if existing:
        conn.execute(
            "UPDATE entries SET updated_at=?, content=?, mood=?, energy=?, tags=? WHERE id=?",
            (updated_at, item.get("content", ""), item.get("mood"),
             item.get("energy"), json.dumps(item.get("tags", [])), entry_id),
        )
        return "updated"
    else:
        conn.execute(
            "INSERT INTO entries (id, date, created_at, updated_at, content, mood, energy, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (entry_id, date_str, created_at, updated_at, item.get("content", ""),
             item.get("mood"), item.get("energy"), json.dumps(item.get("tags", []))),
        )
        return "inserted"


def main():
    parser = argparse.ArgumentParser(description="Import Speculae JSON export into a database.")
    parser.add_argument("source", type=Path, help="Path to JSON export file")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to journal.db")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing entries (default: skip)")
    parser.add_argument("--dry-run", "-n", action="store_true",
                        help="Parse without writing")
    args = parser.parse_args()

    if not args.source.exists():
        print(f"Error: file not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    try:
        raw = json.loads(args.source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw, list):
        print(f"Error: expected a JSON array, got {type(raw).__name__}", file=sys.stderr)
        sys.exit(1)

    # Validate
    valid = []
    errors = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or "date" not in item:
            errors.append(f"Item {i}: missing 'date' field")
            continue
        try:
            date.fromisoformat(item["date"])
        except ValueError:
            errors.append(f"Item {i}: invalid date {item['date']!r}")
            continue
        valid.append(item)

    if errors:
        for e in errors:
            print(f"  WARN: {e}")

    if not valid:
        print("Nothing to import.")
        sys.exit(0)

    if args.dry_run:
        print(f"Dry run: {len(valid)} valid entries found ({len(errors)} errors).")
        print(f"  Earliest: {min(v['date'] for v in valid)}")
        print(f"  Latest:   {max(v['date'] for v in valid)}")
        sys.exit(0)

    conn = _connect(args.db)
    counts = {"inserted": 0, "updated": 0, "skipped": 0}

    try:
        with conn:
            for item in valid:
                result = _upsert(conn, item, args.overwrite)
                counts[result] += 1

            conn.execute(
                "UPDATE meta SET value = (SELECT COUNT(*) FROM entries) WHERE key = 'entry_count'"
            )
    finally:
        conn.close()

    total = counts["inserted"] + counts["updated"]
    print(f"Imported {total} entries ({counts['inserted']} new, {counts['updated']} updated).")
    if counts["skipped"]:
        print(f"  {counts['skipped']} skipped (already exist — use --overwrite to replace).")


if __name__ == "__main__":
    main()
