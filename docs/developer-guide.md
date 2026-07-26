# Developer Guide

How to work on Speculae: architecture, adding features, testing, and releasing.

---

## Contents

1. [Repository layout](#repository-layout)
2. [Development setup](#development-setup)
3. [Running tests](#running-tests)
4. [Code style](#code-style)
5. [Architecture overview](#architecture-overview)
6. [Database layer](#database-layer)
7. [Adding a pattern detector](#adding-a-pattern-detector)
8. [Adding a breathing exercise](#adding-a-breathing-exercise)
9. [Adding a journaling prompt](#adding-a-journaling-prompt)
10. [Adding an API endpoint](#adding-an-api-endpoint)
11. [The web frontend](#the-web-frontend)
12. [Building the Windows executable](#building-the-windows-executable)
13. [Release process](#release-process)
14. [CI pipeline](#ci-pipeline)

---

## Repository layout

```
Speculae/
├── src/speculae/           # Python package
│   ├── cli.py              # Typer CLI commands
│   ├── config.py           # TOML config loader
│   ├── db.py               # SQLite + FTS5 database layer
│   ├── embeddings.py       # Optional vector search
│   ├── insights.py         # Weekly mirror report generator
│   ├── models.py           # Entry, Pattern, Insight, Image dataclasses
│   ├── patterns.py         # Five pattern detectors
│   ├── wellness.py         # Breathing, meditation, prompts
│   ├── web/
│   │   ├── server.py       # Flask REST API (38+ endpoints)
│   │   └── index.html      # Single-page frontend (~3500 lines)
│   └── ui/                 # Textual TUI (terminal editor)
├── tests/                  # pytest suite (153 tests)
│   ├── conftest.py         # Shared fixtures
│   ├── test_api_smoke.py   # Flask test client — all endpoints
│   ├── test_db.py          # Database layer
│   ├── test_models.py      # Dataclass behaviour
│   ├── test_patterns.py    # Pattern detectors
│   ├── test_insights.py    # Insight generation
│   ├── test_export_import.py
│   └── test_wellness.py    # Breathing, prompts, meditation
├── docs/                   # Documentation
├── scripts/                # build_exe.py, import_json.py
├── .github/workflows/      # CI (pytest + ruff) and build (PyInstaller)
└── pyproject.toml          # Package config, deps, tool config
```

---

## Development setup

```bash
git clone https://github.com/0x923041-dotcom/Speculae
cd Speculae
pip install -e ".[dev]"
```

The `[dev]` extra installs pytest, ruff, and mypy.

Confirm it works:

```bash
pytest -q
# 153 passed
speculae --help
speculae-web   # opens http://127.0.0.1:7730
```

---

## Running tests

```bash
# All tests
pytest -q

# Specific test file
pytest tests/test_patterns.py -v

# With coverage
pip install pytest-cov
pytest --cov=speculae --cov-report=term-missing
```

**Test database:** Tests use a temp-file SQLite database via the `tmp_db` fixture in `conftest.py`. No persistent state between test runs.

**No network required:** All tests run offline. External services are either unused or mocked. Do not write tests that require network access.

**Flask client:** API tests use Flask's built-in test client — no server process needed.

> [!IMPORTANT]
> Always override `cfg.db_file` with a `tmp_path` fixture to prevent test entries from polluting
> the user's real journal database.

```python
from speculae.web.server import app, cfg

@pytest.fixture
def client(tmp_path):
    cfg.db_file = tmp_path / "test_api_journal.db"
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
```

---

## Code style

Enforced by ruff (configured in `pyproject.toml`):

```bash
ruff check src/speculae/
ruff check src/speculae/ --fix   # auto-fix safe issues
```

Key rules:
- Line length: 100 characters (`E501` ignored — soft limit only)
- Python 3.10+ features allowed (`target-version = "py310"`)
- Imports sorted (`I` ruleset)
- `from __future__ import annotations` at the top of every file
- Type hints on all public functions (not strictly enforced, but preferred)

---

## Architecture overview

Speculae has three interfaces over a shared database:

```
┌──────────┐   ┌────────────┐   ┌──────────┐
│  CLI     │   │  Web API   │   │  TUI     │
│ (Typer)  │   │  (Flask)   │   │ (Textual)│
└────┬─────┘   └─────┬──────┘   └────┬─────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
              ┌──────▼──────┐
              │   db.py     │
              │  (SQLite)   │
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    patterns.py  insights.py  wellness.py
```

All three interfaces (`cli.py`, `web/server.py`, and `ui/`) call `db.py` directly. There is no intermediate service layer — the database functions are the API.

### Data flow for a journal write

1. User submits content + mood + energy + tags (via CLI, web, or TUI)
2. An `Entry` dataclass is constructed (`models.py`)
3. `db.upsert_entry(database, entry)` writes it to SQLite and updates the FTS5 index
4. The saved entry (with its generated ID, timestamps) is returned

### Database schema (v1)

```sql
-- Core entries table
CREATE TABLE entries (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    mood INTEGER,
    energy INTEGER,
    tags TEXT NOT NULL DEFAULT '[]',
    starred INTEGER NOT NULL DEFAULT 0,
    agent_id TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- FTS5 full-text search index (content + tags both searchable)
CREATE VIRTUAL TABLE entries_fts USING fts5(content, tags, content='entries', content_rowid='rowid');

-- Image attachments
CREATE TABLE images (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES entries(id),
    filename TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'image/png',
    storage_path TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

-- Pattern cache
CREATE TABLE patterns (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    entry_date_from TEXT,
    entry_date_to TEXT,
    detected_at TEXT
);

-- Insight cache
CREATE TABLE insights (
    id TEXT PRIMARY KEY,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    content TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'weekly',
    generated_at TEXT
);
```

---

## Database layer

`db.py` contains all SQL. Key functions:

| Function | Purpose |
|----------|---------|
| `upsert_entry(db, entry)` | Insert or update an entry |
| `get_entry_by_id(db, id)` | Fetch one entry by UUID |
| `get_entries_for_date(db, date)` | All entries on a date |
| `list_entries(db, limit, since, until, starred_only, agent_id)` | Paginated list with filters |
| `search_entries(db, query, limit)` | FTS5 full-text search |
| `delete_entry(db, id)` | Delete by ID |
| `delete_entries_batch(db, ids)` | Delete multiple entries by IDs in one transaction |
| `save_image(db, entry_id, filename, data, mime_type)` | Store image bytes |
| `get_image_by_id(db, id)` | Fetch image by ID |
| `list_agents(db)` | Distinct agent_ids (list of strings) |
| `list_agents_detailed(db)` | Agents with entry counts and latest date (list of dicts) |

The `Database` class is a context manager:

```python
with _db() as database:
    entries = db_module.list_entries(database, limit=100)
# connection closed automatically
```

Tags are stored as JSON arrays in SQLite (`TEXT` column). They are serialised/deserialised in `upsert_entry` and the `Entry` dataclass.

**Schema:** The database uses schema version `v1`. All tables, columns, and indexes are created by the `SCHEMA` SQL in `db.py` using `IF NOT EXISTS` guards. When adding a column, add it to the `SCHEMA` block directly.

---

## Adding a pattern detector

Pattern detectors live in `patterns.py`. Each is a function that takes a list of `Entry` objects and a `PatternsConfig`, and returns a list of `Pattern` objects.

### 1. Write the detector function

```python
def detect_my_pattern(entries: list[Entry], cfg: PatternsConfig) -> list[Pattern]:
    """
    Detect something interesting in the entries.
    Returns an empty list if the pattern is not present or data is insufficient.
    """
    if len(entries) < cfg.min_entries_for_patterns:
        return []

    # ... your detection logic ...

    if pattern_found:
        return [Pattern(
            type="my_pattern",
            title="Short, interesting observation as a question",
            description="Slightly longer explanation of what was found and what it might mean.",
            severity="notable",  # or "significant" or "info"
            entry_date_from=first_relevant_date,
            entry_date_to=last_relevant_date,
            data={"key": "value"},  # any supporting data as a dict
        )]
    return []
```

### 2. Register it in `run_all`

```python
def run_all(entries: list[Entry], cfg: PatternsConfig) -> list[Pattern]:
    results: list[Pattern] = []
    results.extend(detect_arc(entries, cfg))
    results.extend(detect_triggers(entries, cfg))
    results.extend(detect_cycles(entries, cfg))
    results.extend(detect_blindspots(entries, cfg))
    results.extend(detect_day_of_week(entries, cfg))
    results.extend(detect_my_pattern(entries, cfg))  # ← add here
    return results
```

### 3. Write tests

Add a test class in `tests/test_patterns.py`. Tests must run offline — no network, no external dependencies.

```python
class TestMyPattern:
    def test_detects_when_present(self, default_patterns_cfg):
        entries = [...]  # construct entries that trigger the pattern
        result = detect_my_pattern(entries, default_patterns_cfg)
        assert len(result) == 1
        assert result[0].type == "my_pattern"

    def test_no_false_positive(self, default_patterns_cfg):
        entries = [...]  # normal entries, no pattern
        result = detect_my_pattern(entries, default_patterns_cfg)
        assert result == []

    def test_insufficient_data(self, default_patterns_cfg):
        entries = []
        result = detect_my_pattern(entries, default_patterns_cfg)
        assert result == []
```

### Pattern design principles

- **Phrase as a question, not a conclusion.** "Your mood tends to dip after 'deadline' entries — does that match your experience?" not "You have deadline anxiety."
- **No clinical language.** Never use diagnostic terms.
- **Return nothing rather than noise.** A detector that fires too often is worse than one that fires rarely. Precision over recall.
- **Stay local.** Detectors must work with no network access.

---

## Adding a breathing exercise

Breathing exercises are defined in `wellness.py` in the `_EXERCISES` dict.

```python
_EXERCISES: dict[str, BreathingExercise] = {
    "box": BreathingExercise(...),
    # Add your exercise here:
    "wim-hof": BreathingExercise(
        name="Wim Hof",
        description="30 deep breaths, then exhale and hold — builds CO2 tolerance.",
        pattern=[("Inhale", 2), ("Exhale", 2)],  # one cycle of the 30-breath phase
        cycles=30,
    ),
}
```

The pattern is a list of `(action_name, duration_seconds)` tuples. Valid action names are `"Inhale"`, `"Exhale"`, `"Hold"`, and `"Sip"` (used by the physiological sigh exercise).

The web frontend (in `index.html`) reads exercises from the `/api/wellness/breathing` endpoint — new exercises appear automatically without any frontend changes.

**Add a test** in `tests/test_wellness.py`:

```python
def test_new_exercise_accessible():
    ex = get_exercise("wim-hof")
    assert ex is not None
    assert ex.total_seconds > 0
```

**Add a CLI option** in `cli.py` if appropriate — the `--exercise` flag accepts any key in `_EXERCISES`.

---

## Adding a journaling prompt

Prompts live in `wellness.py` in the `PROMPTS` dict. Each category is a list of strings.

```python
PROMPTS: dict[str, list[str]] = {
    "check-in": [...],
    "gratitude": [...],
    # Add to an existing category:
    "growth": [
        "What small risk did you take recently, and what happened?",
        "Name one belief you held a year ago that has shifted.",
        "What skill or quality are you quietly developing?",
        # ↓ new prompt:
        "What conversation changed how you see something?",
    ],
    # Or add a new category:
    "creativity": [
        "What did you make today, even if it was small?",
        "What idea has been sitting in the back of your mind?",
        "What would you build if you knew it would work?",
    ],
}
```

No other changes needed — the API and web frontend enumerate categories dynamically.

**Prompt writing guidelines:**
- Open-ended questions, not yes/no
- Body-grounded where possible ("where do you feel it?", "what did your hands do?")
- No prescriptions ("what should you do" → "what do you notice")
- Short enough to hold in one breath

---

## Adding an API endpoint

API endpoints are Flask routes in `web/server.py`.

```python
@app.route("/api/my-resource", methods=["GET"])
def get_my_resource():
    """One-line docstring."""
    param = request.args.get("param", "").strip()

    with _db() as database:
        result = db_module.my_db_function(database, param)

    return jsonify({"result": result})
```

**Conventions:**
- Use `_db()` as a context manager for every database access
- Use `_valid_mood_energy()` for mood/energy validation
- Return `jsonify({"error": "message"}), 400` for validation errors
- Return `jsonify({"error": "not found"}), 404` for missing resources
- Never return raw exceptions to the client

**Add a smoke test** in `tests/test_api_smoke.py`:

```python
class TestMyResource:
    def test_get_my_resource(self, client):
        r = client.get("/api/my-resource?param=test")
        assert r.status_code == 200
        assert "result" in r.get_json()
```

**Update the OpenAPI spec** (`docs/openapi.yaml`) with the new endpoint.

---

## The web frontend

The frontend is a single HTML file: `src/speculae/web/index.html`. There is no build step, no bundler, no framework — it is plain HTML, CSS, and JavaScript.

**External dependencies (CDN, loaded at runtime):**
- [Tailwind CSS](https://tailwindcss.com/) — utility classes
- [marked](https://marked.js.org/) — Markdown rendering
- [Google Fonts](https://fonts.google.com/) — Fraunces + JetBrains Mono

**Architecture:**
- CSS custom properties (`--paper`, `--ink`, etc.) for all colours — one set per theme
- Theme stored in `localStorage` as `speculae-theme`
- Font scale stored in `localStorage` as `speculae-font-scale`
- All state is module-level `let` variables (no framework state)
- Views are `<section>` elements with `display: none` toggled via CSS class
- All API calls use the `api()` async helper function

**Adding a new view:**
1. Add a `<section id="view-myview" class="view" ...>` in the main content area
2. Add a `<div class="nav-item" data-view="myview" role="button" tabindex="0">` in the sidebar nav
3. Add a case in the view-switcher's `navItems.forEach` handler if the view needs to load data on show
4. Add a `Ctrl+?` keyboard shortcut in the keydown handler map

**Editing the stylesheet:**
All styles are in the single `<style>` block in `<head>`. Variables are defined in `:root` (light theme), `[data-theme="dark"]`, and `[data-theme="high-contrast"]` blocks. Add new component styles below the variable blocks.

---

## Building the Windows executable

### PyInstaller CLI server (speculae-web.exe)

Built with PyInstaller via the spec file:

```bash
python scripts/build_exe.py
```

This runs PyInstaller with `scripts/speculae-web.spec` and produces `dist/speculae-web.exe`.

The build bundles:
- All Python source files from `src/speculae/`
- Flask and its dependencies
- `src/speculae/web/index.html` (referenced in the spec as a data file)

The CI pipeline (`.github/workflows/build.yml`) runs this automatically on any tag push
matching `v*` and uploads the result as a release artifact.

### Tauri desktop wrapper (speculae-desktop.exe)

The desktop app wraps `speculae-web.exe` as a sidecar binary inside a native WebView2
window. It lives in the `desktop/` directory and is built separately from the Python code.

**Architecture:** sidecar pattern. The Rust binary spawns `speculae-web.exe` as a child
process, polls `127.0.0.1:7730` until Flask accepts connections, then opens a WebView2
window at that URL. The web UI is completely unchanged.

**Prerequisites (Windows):**
- Rust stable 1.78+ with the `x86_64-pc-windows-msvc` target
- MSVC Build Tools 2022 (`link.exe` in PATH or configured via `~/.cargo/config.toml`)
- Windows SDK 10.0.26100+ (for `kernel32.lib`)
- WebView2 runtime (ships with Windows 10/11)

See `desktop/README.md` for full setup and build instructions.

**Quick build (after prerequisites):**

```powershell
# 1. Build the sidecar
python scripts/build_exe.py

# 2. Copy it with the required target-triple suffix
New-Item -ItemType Directory -Force -Path desktop\binaries
Copy-Item dist\speculae-web.exe desktop\binaries\speculae-web-x86_64-pc-windows-msvc.exe

# 3. Build the Tauri wrapper
cd desktop
cargo build --release
# Output: desktop/target/release/speculae-desktop.exe
```

**Build the installer (optional, requires tauri-cli):**

```powershell
cargo install tauri-cli --version "^2"
cargo tauri build
# Output: desktop/target/release/bundle/nsis/Speculae Journal_0.1.0_x64-setup.exe
```

---

## Release process

1. **Update version** in `pyproject.toml`:
   ```toml
   version = "0.3.0"
   ```

2. **Update `CHANGELOG.md`** with all changes since the last release.

3. **Run the full test suite:**
   ```bash
   pytest -q
   ruff check src/speculae/
   ```

4. **Commit and tag:**
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "chore: release v0.3.0"
   git tag v0.3.0
   git push origin main --tags
   ```

5. **CI builds the `.exe` automatically** and creates a GitHub Release with auto-generated notes.

6. **Publish to PyPI** (when ready):
   ```bash
   pip install build twine
   python -m build
   twine upload dist/*
   ```

---

## CI pipeline

Two workflows in `.github/workflows/`:

### ci.yml — runs on every push and PR

- Tests on Python 3.10, 3.11, and 3.12 (in parallel)
- `pip install -e ".[dev]"` then `pytest tests/ -v --tb=short`
- Ruff lint check on `src/speculae/`

### build.yml — runs on version tags (`v*`)

- Builds Windows `.exe` on `windows-latest`
- Uploads as a GitHub artifact
- Creates a GitHub Release with the `.exe` attached

**Adding a new Python dependency:**
1. Add it to `pyproject.toml` under `dependencies` (core) or the appropriate optional extra
2. Add the import to the relevant module
3. The CI will pick it up automatically on next push

**The test suite must pass on all three Python versions** before merging. Any failing test on 3.10 is a bug, even if it passes on 3.12.
