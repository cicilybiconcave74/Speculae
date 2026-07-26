"""
Database layer for Speculae.

Schema:
  entries      — one or more rows per (date, agent_id), keyed by UUID;
                 the journal entry and its structured metadata
  entries_fts  — SQLite FTS5 virtual table for full-text search
  patterns     — cached pattern results (invalidated when entries change)
  insights     — generated insight reports

Embeddings are stored as JSON blobs in entries.embedding when semantic
search is enabled. For hundreds–thousands of entries this is fast enough;
we do cosine similarity in NumPy rather than a separate vector DB.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from . import image_storage
from .models import Entry, Image, Insight, Pattern

logger = logging.getLogger(__name__)


# ── Schema ───────────────────────────────────────────────────────────────────

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS entries (
    id          TEXT PRIMARY KEY,
    date        TEXT NOT NULL,             -- YYYY-MM-DD (multiple per day)
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    mood        INTEGER,                  -- 1..5, NULL if not set
    energy      INTEGER,                  -- 1..5, NULL if not set
    tags        TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
    embedding   TEXT,                      -- JSON array of floats, nullable
    starred     INTEGER NOT NULL DEFAULT 0, -- 0 or 1
    agent_id    TEXT                        -- NULL = human, string = agent name
);

CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(date);
CREATE INDEX IF NOT EXISTS idx_entries_starred ON entries(starred);
CREATE INDEX IF NOT EXISTS idx_entries_agent ON entries(agent_id);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    content,
    tags,
    content='entries',
    content_rowid='rowid'
);

-- Keep FTS in sync with entries
CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO entries_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;

CREATE TABLE IF NOT EXISTS images (
    id           TEXT PRIMARY KEY,
    entry_id     TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    mime_type    TEXT NOT NULL DEFAULT 'image/png',
    storage_path TEXT NOT NULL,            -- relative to {data_dir}/images/
    file_size    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_images_entry ON images(entry_id);

CREATE TABLE IF NOT EXISTS patterns (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL,        -- 'arc'|'trigger'|'cycle'|'blindspot'|'dow'
    detected_at     TEXT NOT NULL,
    entry_date_from TEXT,
    entry_date_to   TEXT,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'info',  -- 'info'|'notable'|'significant'
    data            TEXT NOT NULL DEFAULT '{}',    -- JSON blob
    agent_id        TEXT                         -- NULL = human, string = agent-specific
);

CREATE INDEX IF NOT EXISTS idx_patterns_agent ON patterns(agent_id);

CREATE TABLE IF NOT EXISTS insights (
    id              TEXT PRIMARY KEY,
    generated_at    TEXT NOT NULL,
    period_start    TEXT NOT NULL,
    period_end      TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'weekly',
    content         TEXT NOT NULL
);

-- meta is created by _ensure_meta() before migrations run; not repeated here.
"""


# Each tuple is (target_version: int, sql: str).
# Version 1 is the initial schema; add new entries for every future change.
MIGRATIONS: list[tuple[int, str]] = [
    (1, SCHEMA),  # initial schema — idempotent thanks to IF NOT EXISTS
]


# ── Connection management ────────────────────────────────────────────────────

class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None

    @property
    def data_dir(self) -> Path:
        """Parent directory of the journal database (Speculae data root)."""
        return self.path.parent

    def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        self._ensure_meta()
        self._run_migrations()
        self._upgrade_legacy_image_blobs()

    def _ensure_meta(self) -> None:
        """Create meta table on the very first run."""
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '0')"
        )
        self._conn.commit()

    def _run_migrations(self) -> None:
        """Apply every migration whose version is greater than the stored schema_version.

        Design principles:
        - Forward-only: no rollback support.
        - Each migration runs in its own transaction and updates schema_version atomically.
        - Failure raises immediately; no silent recovery.
        """
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        current_version = int(row["value"]) if row else 0

        for version, sql in sorted(MIGRATIONS, key=lambda t: t[0]):
            if version <= current_version:
                continue

            try:
                self._conn.executescript(sql)
                self._conn.execute(
                    "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                    (str(version),),
                )
                self._conn.commit()
            except Exception as exc:
                self._conn.rollback()
                raise RuntimeError(
                    f"Schema migration to version {version} failed: {exc}"
                ) from exc

    def _upgrade_legacy_image_blobs(self) -> None:
        """One-time upgrade for pre-release DBs that stored images as BLOBs.

        Fresh installs use file paths from the start (schema version 1).
        This runs silently on connect when an old ``data`` column is detected.
        """
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(images)").fetchall()}
        if "data" not in cols:
            return

        rows = self.conn.execute(
            "SELECT id, entry_id, filename, mime_type, data, created_at FROM images"
        ).fetchall()

        migrated: list[tuple] = []
        for row in rows:
            blob = row["data"]
            if not blob:
                continue
            entry_row = self.conn.execute(
                "SELECT date FROM entries WHERE id = ?", (row["entry_id"],)
            ).fetchone()
            entry_date = (
                date.fromisoformat(entry_row["date"])
                if entry_row
                else date.today()
            )
            rel_path = image_storage.build_relative_path(
                entry_date,
                row["entry_id"],
                row["id"],
                row["mime_type"],
                row["filename"],
            )
            image_storage.write_file(self.data_dir, rel_path, blob)
            migrated.append((
                row["id"], row["entry_id"], row["filename"], row["mime_type"],
                rel_path, len(blob), row["created_at"],
            ))

        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS images_new (
                id           TEXT PRIMARY KEY,
                entry_id     TEXT NOT NULL REFERENCES entries(id) ON DELETE CASCADE,
                filename     TEXT NOT NULL,
                mime_type    TEXT NOT NULL DEFAULT 'image/png',
                storage_path TEXT NOT NULL,
                file_size    INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT NOT NULL
            );
            DROP TABLE images;
            ALTER TABLE images_new RENAME TO images;
            CREATE INDEX IF NOT EXISTS idx_images_entry ON images(entry_id);
        """)
        for rec in migrated:
            self.conn.execute(
                "INSERT INTO images "
                "(id, entry_id, filename, mime_type, storage_path, file_size, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rec,
            )
        self.conn.commit()
        if migrated:
            logger.info("Upgraded %d legacy inline image BLOB(s) to file-based storage.", len(migrated))

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if not self._conn:
            raise RuntimeError("Database not connected. Use as context manager.")
        return self._conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise


# ── Entry CRUD ───────────────────────────────────────────────────────────────

def _row_to_entry(row: sqlite3.Row) -> Entry:
    return Entry(
        id=row["id"],
        date=date.fromisoformat(row["date"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        content=row["content"],
        mood=row["mood"],
        energy=row["energy"],
        tags=json.loads(row["tags"]),
        embedding=json.loads(row["embedding"]) if row["embedding"] else None,
        starred=bool(row["starred"]),
        agent_id=row["agent_id"],
    )


def get_entry_by_id(db: Database, entry_id: str) -> Entry | None:
    """Fetch a single entry by its ID."""
    row = db.conn.execute(
        "SELECT * FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()
    return _row_to_entry(row) if row else None


def get_entries_for_date(db: Database, entry_date: date) -> list[Entry]:
    """Fetch all entries for a specific date, newest first."""
    rows = db.conn.execute(
        "SELECT * FROM entries WHERE date = ? ORDER BY created_at DESC",
        (entry_date.isoformat(),)
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def save_entry(db: Database, entry: Entry) -> Entry:
    """Persist an entry.

    Behaviour:
    - If ``entry.id`` is empty, a new UUID is assigned and the entry is inserted.
    - If ``entry.id`` is set and the entry exists, it is updated in-place.
    - If ``entry.id`` is set but does not exist, ``ValueError`` is raised.
      Fetch the entry first (``get_entry_by_id``) or omit the id to create a new one.

    Returns the saved entry (with ``id``, ``created_at``, and ``updated_at`` populated).
    """
    now = datetime.now(timezone.utc)
    if entry.id:
        existing = db.conn.execute(
            "SELECT id FROM entries WHERE id = ?", (entry.id,)
        ).fetchone()
        if not existing:
            raise ValueError(
                f"Entry id {entry.id!r} not found — use save_entry with a new "
                "entry (no id) to create, or fetch the existing entry first to update."
            )
        entry.updated_at = now
        with db.transaction():
            db.conn.execute(
                """
                UPDATE entries SET
                    updated_at = ?, content = ?, mood = ?, energy = ?, tags = ?,
                    embedding = ?, starred = ?, agent_id = ?
                WHERE id = ?
                """,
                (
                    entry.updated_at.isoformat(),
                    entry.content,
                    entry.mood,
                    entry.energy,
                    json.dumps(entry.tags),
                    json.dumps(entry.embedding) if entry.embedding else None,
                    int(entry.starred),
                    entry.agent_id,
                    entry.id,
                ),
            )
        return entry

    entry.id = str(uuid.uuid4())
    entry.created_at = now
    entry.updated_at = now

    with db.transaction():
        db.conn.execute(
            """
            INSERT INTO entries (id, date, created_at, updated_at, content, mood, energy, tags, embedding, starred, agent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.date.isoformat(),
                entry.created_at.isoformat(),
                entry.updated_at.isoformat(),
                entry.content,
                entry.mood,
                entry.energy,
                json.dumps(entry.tags),
                json.dumps(entry.embedding) if entry.embedding else None,
                int(entry.starred),
                entry.agent_id,
            ),
        )
    return entry


def delete_entry(db: Database, entry_id: str) -> bool:
    """Delete entry by ID. Returns True if something was deleted."""
    with db.transaction():
        cur = db.conn.execute(
            "DELETE FROM entries WHERE id = ?", (entry_id,)
        )
    return cur.rowcount > 0


def delete_entries_batch(db: Database, entry_ids: list[str]) -> int:
    """Delete multiple entries by IDs. Returns total number of deleted entries."""
    if not entry_ids:
        return 0
    with db.transaction():
        placeholders = ",".join("?" for _ in entry_ids)
        db.conn.execute(
            f"DELETE FROM images WHERE entry_id IN ({placeholders})", entry_ids
        )
        cur = db.conn.execute(
            f"DELETE FROM entries WHERE id IN ({placeholders})", entry_ids
        )
    return cur.rowcount


def list_entries(
    db: Database,
    limit: int = 50,
    offset: int = 0,
    since: date | None = None,
    until: date | None = None,
    starred_only: bool = False,
    agent_id: str | None = None,
    human_only: bool = False,
) -> list[Entry]:
    """Fetch entries in reverse-chronological order, starred first.

    agent_id / human_only interaction
    ----------------------------------
    human_only=True  → WHERE agent_id IS NULL   (human journal only; agent_id ignored)
    agent_id="foo"   → WHERE agent_id = 'foo'   (one specific agent)
    both omitted     → no agent_id clause        (fleet-wide: all agents + human)
    """
    clauses = []
    params: list = []

    if since:
        clauses.append("date >= ?")
        params.append(since.isoformat())
    if until:
        clauses.append("date <= ?")
        params.append(until.isoformat())
    if starred_only:
        clauses.append("starred = 1")
    if human_only:
        clauses.append("agent_id IS NULL")
    elif agent_id is not None:
        clauses.append("agent_id = ?")
        params.append(agent_id)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = db.conn.execute(
        f"SELECT * FROM entries {where} ORDER BY starred DESC, date DESC, created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return [_row_to_entry(r) for r in rows]


def list_entries_by_tag(
    db: Database,
    tag: str,
    limit: int = 400,
    since: date | None = None,
    agent_id: str | None = None,
) -> list[Entry]:
    """Return entries that contain *tag* in their tags array.

    Filters in SQL via json_each() so no rows are loaded unnecessarily.
    Falls back gracefully to an empty list if json_each is unavailable
    (SQLite < 3.38 or very old Python builds).
    """
    clauses = ["j.value = ?"]
    params: list = [tag]

    if since:
        clauses.append("e.date >= ?")
        params.append(since.isoformat())
    if agent_id is not None:
        clauses.append("e.agent_id = ?")
        params.append(agent_id)

    where = " AND ".join(clauses)
    try:
        rows = db.conn.execute(
            f"""
            SELECT e.*
            FROM entries e, json_each(e.tags) j
            WHERE {where}
            ORDER BY e.starred DESC, e.date DESC, e.created_at DESC
            LIMIT ?
            """,
            params + [limit],
        ).fetchall()
    except sqlite3.OperationalError as exc:
        logger.warning("json_each unavailable (%s); falling back to Python-side tag filter.", exc)
        all_entries = list_entries(db, limit=limit, since=since, agent_id=agent_id)
        return [e for e in all_entries if tag in e.tags]

    return [_row_to_entry(r) for r in rows]


def _sanitize_fts_query(query: str) -> str:
    """Sanitize a user-supplied string for safe FTS5 use.

    - Removes or balances unmatched double-quotes.
    - Strips leading/trailing FTS5 operator tokens that would cause a parse error.
    - Collapses runs of whitespace.
    """
    if query.count('"') % 2 != 0:
        query = query.replace('"', "")

    query = re.sub(r"^\s*(AND|OR|NOT)\s+", "", query, flags=re.IGNORECASE)
    query = re.sub(r"\s+(AND|OR|NOT)\s*$", "", query, flags=re.IGNORECASE)

    query = " ".join(query.split())

    return query.strip()


def search_entries(db: Database, query: str, limit: int = 20) -> list[Entry]:
    """Full-text search via FTS5 with pre-sanitisation.

    Sanitises the query before sending it to FTS5 so that ranking is
    preserved for virtually all user input. Falls back to LIKE only when
    FTS5 still rejects the sanitised query, and logs a warning when that
    happens.
    """
    sanitized = _sanitize_fts_query(query)

    try:
        rows = db.conn.execute(
            """
            SELECT e.* FROM entries e
            JOIN entries_fts f ON e.rowid = f.rowid
            WHERE entries_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (sanitized, limit),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]
    except Exception as exc:
        logger.warning(
            "FTS5 query failed even after sanitisation (query=%r, sanitized=%r): %s — "
            "falling back to LIKE search.",
            query,
            sanitized,
            exc,
        )
        rows = db.conn.execute(
            "SELECT * FROM entries WHERE content LIKE ? ORDER BY date DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]


def entry_count(db: Database) -> int:
    row = db.conn.execute("SELECT COUNT(*) FROM entries").fetchone()
    return row[0] if row else 0


def date_range(db: Database) -> tuple[date | None, date | None]:
    """Return (earliest, latest) entry dates."""
    row = db.conn.execute("SELECT MIN(date) as mn, MAX(date) as mx FROM entries").fetchone()
    if not row or not row["mn"]:
        return None, None
    return date.fromisoformat(row["mn"]), date.fromisoformat(row["mx"])


# ── Pattern CRUD ─────────────────────────────────────────────────────────────

def _row_to_pattern(row: sqlite3.Row) -> Pattern:
    return Pattern(
        id=row["id"],
        type=row["type"],
        detected_at=datetime.fromisoformat(row["detected_at"]),
        entry_date_from=date.fromisoformat(row["entry_date_from"]) if row["entry_date_from"] else None,
        entry_date_to=date.fromisoformat(row["entry_date_to"]) if row["entry_date_to"] else None,
        title=row["title"],
        description=row["description"],
        severity=row["severity"],
        data=json.loads(row["data"]),
        agent_id=row["agent_id"],
    )


def save_patterns(db: Database, patterns: list[Pattern], agent_id: str | None = None) -> None:
    """Replace patterns for a specific agent (or all if agent_id is None)."""
    with db.transaction():
        if agent_id is not None:
            db.conn.execute("DELETE FROM patterns WHERE agent_id = ?", (agent_id,))
        else:
            db.conn.execute("DELETE FROM patterns WHERE agent_id IS NULL")
        for p in patterns:
            if not p.id:
                p.id = str(uuid.uuid4())
            p.agent_id = agent_id
            db.conn.execute(
                """
                INSERT INTO patterns
                    (id, type, detected_at, entry_date_from, entry_date_to, title, description, severity, data, agent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p.id,
                    p.type,
                    p.detected_at.isoformat(),
                    p.entry_date_from.isoformat() if p.entry_date_from else None,
                    p.entry_date_to.isoformat() if p.entry_date_to else None,
                    p.title,
                    p.description,
                    p.severity,
                    json.dumps(p.data),
                    agent_id,
                ),
            )


def list_patterns(db: Database, agent_id: str | None = None) -> list[Pattern]:
    if agent_id is not None:
        rows = db.conn.execute(
            "SELECT * FROM patterns WHERE agent_id = ? ORDER BY detected_at DESC",
            (agent_id,),
        ).fetchall()
    else:
        rows = db.conn.execute(
            "SELECT * FROM patterns WHERE agent_id IS NULL ORDER BY detected_at DESC"
        ).fetchall()
    return [_row_to_pattern(r) for r in rows]


def patterns_are_stale(db: Database, agent_id: str | None = None) -> bool:
    """Return True if this agent's entries contain any writes newer than their
    most recent pattern run. Each agent's staleness is evaluated independently.
    """
    if agent_id is not None:
        latest_entry = db.conn.execute(
            "SELECT MAX(updated_at) FROM entries WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()[0]
        latest_pattern = db.conn.execute(
            "SELECT MAX(detected_at) FROM patterns WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()[0]
    else:
        latest_entry = db.conn.execute(
            "SELECT MAX(updated_at) FROM entries WHERE agent_id IS NULL"
        ).fetchone()[0]
        latest_pattern = db.conn.execute(
            "SELECT MAX(detected_at) FROM patterns WHERE agent_id IS NULL"
        ).fetchone()[0]

    if not latest_pattern:
        return True
    if not latest_entry:
        return False
    return latest_entry > latest_pattern


def get_entry_by_created_at(db: Database, created_at: datetime) -> Entry | None:
    """Find an entry by its created_at timestamp."""
    row = db.conn.execute(
        "SELECT * FROM entries WHERE created_at = ?",
        (created_at.isoformat(),),
    ).fetchone()
    return _row_to_entry(row) if row else None


# ── Insight CRUD ─────────────────────────────────────────────────────────────

def save_insight(db: Database, insight: Insight) -> None:
    if not insight.id:
        insight.id = str(uuid.uuid4())
    with db.transaction():
        db.conn.execute(
            """
            INSERT OR REPLACE INTO insights
                (id, generated_at, period_start, period_end, type, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                insight.id,
                insight.generated_at.isoformat(),
                insight.period_start.isoformat(),
                insight.period_end.isoformat(),
                insight.type,
                insight.content,
            ),
        )


def latest_insight(db: Database) -> Insight | None:
    row = db.conn.execute(
        "SELECT * FROM insights ORDER BY generated_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    return Insight(
        id=row["id"],
        generated_at=datetime.fromisoformat(row["generated_at"]),
        period_start=date.fromisoformat(row["period_start"]),
        period_end=date.fromisoformat(row["period_end"]),
        type=row["type"],
        content=row["content"],
    )


# ── Image CRUD ──────────────────────────────────────────────────────────────

def _row_to_image(row: sqlite3.Row, *, load_data: bool = False, db: Database | None = None) -> Image:
    """Deserialise an image row. Loads bytes from disk only when load_data=True."""
    img = Image(
        id=row["id"],
        entry_id=row["entry_id"],
        filename=row["filename"],
        mime_type=row["mime_type"],
        storage_path=row["storage_path"],
        file_size=row["file_size"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
    if load_data and db and img.storage_path:
        try:
            img.data = image_storage.read_file(db.data_dir, img.storage_path)
        except FileNotFoundError:
            logger.warning("Image file missing for id=%s path=%s", img.id, img.storage_path)
            img.data = b""
    return img


def _row_to_image_meta(row: sqlite3.Row) -> Image:
    """Metadata-only deserialisation (no disk read)."""
    return Image(
        id=row["id"],
        entry_id=row["entry_id"],
        filename=row["filename"],
        mime_type=row["mime_type"],
        storage_path=row["storage_path"],
        file_size=row["file_size"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


_IMAGE_META_COLS = "id, entry_id, filename, mime_type, storage_path, file_size, created_at"


# ── Storage thresholds ────────────────────────────────────────────────────────

_IMAGE_WARN_BYTES = 100 * 1024 * 1024   # 100 MB total images → warn
_IMAGE_CRIT_BYTES = 500 * 1024 * 1024   # 500 MB total images → critical
_DB_WARN_BYTES    = 200 * 1024 * 1024   # 200 MB overall DB file → warn


def db_size_warning(db: Database) -> list[str]:
    """Return a (possibly empty) list of human-readable storage warnings."""
    warnings: list[str] = []

    total_image_bytes = _total_image_bytes(db)

    if total_image_bytes >= _IMAGE_CRIT_BYTES:
        mb = total_image_bytes // (1024 * 1024)
        warnings.append(
            f"Critical: image storage is {mb} MB — well above the 500 MB threshold. "
            "Consider removing large attachments."
        )
    elif total_image_bytes >= _IMAGE_WARN_BYTES:
        mb = total_image_bytes // (1024 * 1024)
        warnings.append(
            f"Warning: image storage is {mb} MB and growing. "
            "Run `speculae db-stats` for a full breakdown."
        )

    try:
        db_size_bytes = db.path.stat().st_size
        if db_size_bytes >= _DB_WARN_BYTES:
            mb = db_size_bytes // (1024 * 1024)
            warnings.append(
                f"Warning: total database size is {mb} MB. "
                "Run `speculae db-stats` for details."
            )
    except OSError:
        pass

    return warnings


def _total_image_bytes(db: Database) -> int:
    """Sum stored image sizes from DB metadata (file_size column)."""
    row = db.conn.execute(
        "SELECT COALESCE(SUM(file_size), 0) FROM images"
    ).fetchone()
    return int(row[0]) if row else 0


def _entry_date_for_image(db: Database, entry_id: str) -> date:
    row = db.conn.execute(
        "SELECT date FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if row:
        return date.fromisoformat(row["date"])
    return date.today()


def save_image(db: Database, entry_id: str, filename: str, data: bytes,
               mime_type: str = "image/png") -> Image:
    """Save an image attached to an entry. Writes bytes to disk, metadata to DB."""
    image_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    entry_date = _entry_date_for_image(db, entry_id)
    rel_path = image_storage.build_relative_path(
        entry_date, entry_id, image_id, mime_type, filename
    )
    image_storage.write_file(db.data_dir, rel_path, data)

    image = Image(
        id=image_id,
        entry_id=entry_id,
        filename=filename,
        mime_type=mime_type,
        storage_path=rel_path,
        file_size=len(data),
        data=data,
        created_at=created_at,
    )
    with db.transaction():
        db.conn.execute(
            "INSERT INTO images "
            "(id, entry_id, filename, mime_type, storage_path, file_size, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                image.id, image.entry_id, image.filename, image.mime_type,
                image.storage_path, image.file_size, image.created_at.isoformat(),
            ),
        )

    for msg in db_size_warning(db):
        logger.warning(msg)

    return image


def get_images_for_entry(db: Database, entry_id: str) -> list[Image]:
    """Fetch metadata for all images attached to an entry, oldest first."""
    rows = db.conn.execute(
        f"SELECT {_IMAGE_META_COLS} FROM images WHERE entry_id = ? "
        "ORDER BY created_at ASC",
        (entry_id,),
    ).fetchall()
    return [_row_to_image_meta(r) for r in rows]


def get_image_by_id(db: Database, image_id: str, *, load_data: bool = True) -> Image | None:
    """Fetch a single image by ID, optionally loading bytes from disk."""
    row = db.conn.execute(
        f"SELECT {_IMAGE_META_COLS} FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_image(row, load_data=load_data, db=db)


def get_image_file_path(db: Database, image_id: str) -> Path | None:
    """Return the absolute filesystem path for an image, or None if missing."""
    row = db.conn.execute(
        "SELECT storage_path FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    if not row or not row["storage_path"]:
        return None
    try:
        path = image_storage.resolve_path(db.data_dir, row["storage_path"])
    except ValueError:
        return None
    return path if path.is_file() else None


def delete_image(db: Database, image_id: str) -> bool:
    """Delete an image by ID (file + DB row). Returns True if deleted."""
    row = db.conn.execute(
        "SELECT storage_path FROM images WHERE id = ?", (image_id,)
    ).fetchone()
    if not row:
        return False
    with db.transaction():
        cur = db.conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
    if row["storage_path"]:
        image_storage.delete_file(db.data_dir, row["storage_path"])
    return cur.rowcount > 0


def delete_images_for_entry(db: Database, entry_id: str) -> None:
    """Delete all images for an entry (files + DB rows)."""
    rows = db.conn.execute(
        "SELECT storage_path FROM images WHERE entry_id = ?", (entry_id,)
    ).fetchall()
    with db.transaction():
        db.conn.execute("DELETE FROM images WHERE entry_id = ?", (entry_id,))
    for row in rows:
        if row["storage_path"]:
            image_storage.delete_file(db.data_dir, row["storage_path"])


def db_stats(db: Database) -> dict:
    """Return a summary of database storage usage.

    Suitable for a 'database diagnostics' CLI command or UI panel.
    The returned dict now includes a 'warnings' key (list[str], possibly empty).
    """
    entry_count = db.conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    image_count = db.conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    total_image_bytes = _total_image_bytes(db)

    avg_image_bytes = (total_image_bytes // image_count) if image_count else 0

    db_size_bytes: int = 0
    try:
        db_size_bytes = db.path.stat().st_size
    except OSError:
        pass

    return {
        "db_path": str(db.path),
        "db_size_bytes": db_size_bytes,
        "entry_count": entry_count,
        "image_count": image_count,
        "total_image_bytes": total_image_bytes,
        "avg_image_bytes": avg_image_bytes,
        "warnings": db_size_warning(db),
    }


def list_agents(db: Database) -> list[str]:
    """List all distinct agent_id values that have entries."""
    rows = db.conn.execute(
        "SELECT DISTINCT agent_id FROM entries WHERE agent_id IS NOT NULL AND agent_id != '' ORDER BY agent_id"
    ).fetchall()
    return [row["agent_id"] for row in rows]


def get_agent_display_name(db: Database, agent_id: str) -> str | None:
    """Return the explicit display name for an agent, or None if not set."""
    row = db.conn.execute(
        "SELECT value FROM meta WHERE key = ?",
        (f"agent_display:{agent_id}",),
    ).fetchone()
    return row["value"] if row else None


def set_agent_display_name(db: Database, agent_id: str, display_name: str) -> None:
    """Persist a human-friendly display name for an agent."""
    with db.transaction():
        db.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (f"agent_display:{agent_id}", display_name),
        )


def _resolve_display_name(db: Database, agent_id: str) -> str:
    """Return the explicit display name if set, otherwise derive one from the id."""
    explicit = get_agent_display_name(db, agent_id)
    if explicit:
        return explicit
    return agent_id.replace("_", " ").replace("-", " ").title()


def list_agents_detailed(db: Database) -> list[dict]:
    """List all distinct agent_id values with entry counts and latest dates."""
    rows = db.conn.execute(
        "SELECT agent_id, COUNT(*) as cnt, MAX(date) as latest FROM entries WHERE agent_id IS NOT NULL AND agent_id != '' GROUP BY agent_id ORDER BY agent_id"
    ).fetchall()
    return [
        {
            "id": row["agent_id"],
            "name": _resolve_display_name(db, row["agent_id"]),
            "entry_count": row["cnt"],
            "latest_date": row["latest"],
        }
        for row in rows
    ]


def agent_entry_count(db: Database, agent_id: str) -> int:
    """Count entries for a specific agent."""
    row = db.conn.execute(
        "SELECT COUNT(*) as cnt FROM entries WHERE agent_id = ?", (agent_id,)
    ).fetchone()
    return row["cnt"] if row else 0
