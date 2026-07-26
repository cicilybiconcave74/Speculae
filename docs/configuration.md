# Configuration

Speculae stores its config at:
- **Linux/macOS:** `~/.config/speculae/config.toml`
- **Windows:** `%APPDATA%\speculae\config.toml`

Run `speculae config` to print the current file path and all active settings.

---

## `[journal]`

```toml
[journal]
prompt = "How are you?"       # opening prompt in the writer (currently decorative)
editor = "internal"           # "internal" = built-in TUI; or a path to $EDITOR
date_format = "%d %B %Y"      # Python strftime format for displayed dates
locale = ""                   # empty = system default
```

---

## `[embeddings]`

Local semantic search powered by `sentence-transformers`. Runs fully offline after the first model download.

```toml
[embeddings]
enabled = false                 # set true to enable
model = "all-MiniLM-L6-v2"     # any sentence-transformers model ID
backend = "local"               # "local" or "openai"
openai_model = "text-embedding-3-small"  # used only when backend = "openai"
```

Enable:
```bash
pip install "speculae[semantic]"
# then in config.toml:
# [embeddings]
# enabled = true
```

> **Note:** Embeddings are stored as JSON blobs in the entries table and similarity is computed in NumPy. This works well for personal journals (up to a few thousand entries). For larger datasets, consider an external vector store.

Use:
```bash
speculae search "feeling disconnected" --semantic
```

---

## `[ai]`

Optional LLM-generated narrative for weekly insights. BYOAK — bring your own API key.

```toml
[ai]
enabled = false
provider = "openai"           # "openai", "anthropic", "gemini", or "custom"
model = "gpt-4o-mini"
openai_api_key = ""           # or set OPENAI_API_KEY env var
anthropic_api_key = ""        # or set ANTHROPIC_API_KEY env var
base_url = ""                 # custom endpoint (e.g., http://localhost:11434/v1 for Ollama)
```

**Security note:** API keys in `config.toml` are stored in plaintext. Prefer environment variables:

```bash
export OPENAI_API_KEY="sk-..."
```

When AI insights are enabled, only a statistical summary is sent to the API — not your raw entry text.

Configure via the web UI: click **Config** in the sidebar.

---

## `[patterns]`

Tune the detection algorithms:

```toml
[patterns]
arc_window_days = 7          # rolling window for trend detection
arc_threshold = 0.3          # minimum slope (mood points/day) to flag a trend
cycle_min_period_days = 5    # shortest detectable cycle
cycle_max_period_days = 30   # longest detectable cycle
blindspot_multiplier = 2.0   # silence = N × average tag interval
min_entries_for_patterns = 7 # minimum entries before detection runs
```

**Tuning tips:**
- Lower `arc_threshold` (e.g., 0.15) to surface subtler trends — more noise
- Raise `blindspot_multiplier` (e.g., 3.0) to reduce false blindspot alerts
- Raise `min_entries_for_patterns` to wait for more data before pattern detection

---

## Data paths

```
~/.config/speculae/config.toml       # configuration
~/.local/share/speculae/journal.db   # all your journal data (SQLite)
~/.local/share/speculae/embeddings/  # cached vector embeddings
```

On Windows:
```
%APPDATA%\speculae\config.toml
%LOCALAPPDATA%\speculae\journal.db
%LOCALAPPDATA%\speculae\embeddings\
```

To delete everything:

```bash
speculae destroy
```

---

## Planned Config Sections

These sections are planned but not yet implemented:

- **`[wellness]`** — breathing defaults, meditation bells, yoga settings
- **`[agent]`** — default agent ID, shared instance mode
