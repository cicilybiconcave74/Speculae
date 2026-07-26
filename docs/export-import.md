# Export and import

You own your data absolutely. Speculae makes this concrete:

- Export at any time with one command
- Import into a new machine, a fresh install, or another tool
- Delete everything with one command
- The format is plain JSON — readable by humans and every programming language

---

## Export

```bash
# JSON (default) — one object per entry, sorted newest-first
speculae export --output journal.json

# Markdown — human-readable, sorted chronologically
speculae export --format markdown --output journal.md

# Print to stdout (pipe to other tools)
speculae export | jq '.[] | select(.mood < 3)'
```

---

## JSON format

The export format is a top-level JSON array. Each object represents one entry:

```json
[
  {
    "date": "2026-07-20",
    "content": "Had that conversation with M. finally...",
    "mood": 3,
    "energy": 2,
    "tags": ["work", "boundary-setting", "hard day"],
    "created_at": "2026-07-20T22:44:01.123456",
    "updated_at": "2026-07-20T22:44:01.123456"
  },
  {
    "date": "2026-07-19",
    "content": "Quiet day. Walked along the sea wall.",
    "mood": 4,
    "energy": 4,
    "tags": ["solitude", "outdoors"],
    "created_at": "2026-07-19T19:12:30.000000",
    "updated_at": "2026-07-19T19:12:30.000000"
  }
]
```

**Field reference:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `date` | string | Yes | ISO 8601: `YYYY-MM-DD` |
| `content` | string | No | Free-form journal text |
| `mood` | integer or null | No | 1 (very low) – 5 (very good) |
| `energy` | integer or null | No | 1 (drained) – 5 (vibrant) |
| `tags` | array of strings | No | Empty array if no tags |
| `created_at` | string or null | No | ISO 8601 datetime |
| `updated_at` | string or null | No | ISO 8601 datetime |

---

## Import

```bash
# Merge: import only dates not already in the database (default)
speculae import journal.json

# Overwrite: replace any existing entry with the imported version
speculae import journal.json --overwrite

# Dry run: validate the file without writing anything
speculae import journal.json --dry-run
```

### Import behaviour

- Only `date` is required. All other fields are optional.
- Mood and energy values outside 1–5 are cleared (set to null) rather than rejected. A warning is printed.
- Tags that are not strings are silently filtered out.
- Malformed timestamps are ignored; the entry is still imported.
- `--merge` (default) skips any entry whose date already exists in the database.
- `--overwrite` replaces any existing entry. This cannot be undone — export first if you're unsure.
- Import never deletes entries that aren't in the file.

### Error handling

Import is non-destructive. If items in the file have errors, they're reported and skipped; valid items are still imported. A summary is printed at the end showing how many were imported vs. skipped.

---

## Migration from another tool

Any tool that can output a JSON array with at least a `date` (YYYY-MM-DD) and `content` field can be imported:

```json
[
  { "date": "2026-01-01", "content": "New year, new journal." }
]
```

For tools that use different field names, a quick `jq` transform will reformat:

```bash
# Example: tool that uses "timestamp" and "body"
cat other_export.json | jq '[.[] | {date: .timestamp[:10], content: .body}]' > speculae_import.json
speculae import speculae_import.json
```

---

## Deleting everything

```bash
speculae destroy
```

This deletes `journal.db` — all entries, patterns, and insights. It asks you to type `destroy` to confirm, or use `--yes` to skip the prompt in scripts.

The config file is not deleted by `destroy`. Remove it manually if you want a completely clean state:

```bash
rm ~/.config/speculae/config.toml
```
