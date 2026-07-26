# User Guide

A complete reference for Speculae — the local-first journal for humans and agents.

---

## Contents

1. [Installation](#installation)
2. [First run](#first-run)
3. [Writing entries](#writing-entries)
4. [Reading and searching](#reading-and-searching)
5. [Mood and energy](#mood-and-energy)
6. [Tags](#tags)
7. [Starred entries](#starred-entries)
8. [Image attachments](#image-attachments)
9. [Markdown formatting](#markdown-formatting)
10. [Web interface](#web-interface)
11. [Dashboard](#dashboard)
12. [Calendar](#calendar)
13. [Patterns](#patterns)
14. [Insights](#insights)
15. [Wellness — breathing](#wellness--breathing)
16. [Wellness — meditation](#wellness--meditation)
17. [Wellness — journaling prompts](#wellness--journaling-prompts)
18. [Export and import](#export-and-import)
19. [Configuration](#configuration)
20. [AI insights (optional)](#ai-insights-optional)
21. [Accessibility](#accessibility)
22. [Data and privacy](#data-and-privacy)
23. [Troubleshooting](#troubleshooting)

---

## Installation

**Requirements:** Python 3.10 or newer.

```bash
# Install from PyPI (when published)
pip install speculae

# Or from source
git clone https://github.com/0x923041-dotcom/Speculae
cd Speculae
pip install -e .
```

Flask is a core dependency — the web interface works out of the box.

---

## First run

```bash
speculae init
```

This creates:
- **Config file** — `%APPDATA%\speculae\config.toml` (Windows) or `~/.config/speculae/config.toml`
- **Database** — `%LOCALAPPDATA%\speculae\journal.db` (Windows) or `~/.local/share/speculae/journal.db`

Run `speculae config` at any time to see the exact paths on your system.

---

## Writing entries

### Terminal editor

```bash
speculae write
```

Opens a full-screen terminal editor for today. Write freely. The editor has no required fields — a blank entry with a timestamp is a valid entry.

**Date navigation:**
```bash
speculae write --date 2026-07-15   # write for a specific past date
```

**Multiple entries per day** are supported. Each `write` call opens a new entry for the same day. You can have as many entries on one day as you like.

### Web interface

Open the **Write** view. Click **+ New entry** to start a fresh entry for today. Navigate to a past date using the arrow keys in the date header.

---

## Reading and searching

```bash
# List the last 14 days
speculae list

# Last 60 days
speculae list --days 60

# Full-text search
speculae search "sea wall"

# Read a specific date
speculae read
speculae read 2026-07-15
```

### Web interface

The **Read** view shows entries in reverse chronological order with filters:

- **Search** — full-text search across all entry content
- **tag:** — filter by a specific tag
- **mood:** — filter by exact mood score (1–5)
- **☆ starred** — show only starred entries

Click any entry row to open it in the Write view for editing.

---

## Mood and energy

Both are optional integers from 1 to 5.

| Value | Mood | Energy |
|-------|------|--------|
| 1 | Very low | Drained |
| 2 | Low | Tired |
| 3 | Neutral | Normal |
| 4 | Good | Alert |
| 5 | Great | Vibrant |

### Terminal

Type a digit key (1–5) while the text area is focused to set mood. Use Shift+digit (i.e. `!`, `@`, `#`, `$`, `%` on US keyboards) to set energy.

### Web interface

Click the dots in the **mood** and **energy** rows below the editor. A second click on the active dot clears the value. Keyboard users: Tab to the dot group, then use **arrow keys** to move between dots and **Enter/Space** to select.

---

## Tags

Tags are short, lowercase labels attached to entries. They power the trigger correlation detector and let you filter entries by topic.

```bash
# In the terminal editor: the tags field accepts comma-separated values
# Type "work, hard day, M." and press Enter
```

### Web interface

Type in the **tags** field and press **comma** or **Enter** to add a tag. Backspace on an empty field removes the last tag. Tags are normalised to lowercase and stripped of special characters.

**Useful tagging patterns:**
- People: `m`, `dad`, `team`
- Activities: `running`, `reading`, `cooking`
- Emotional themes: `grief`, `pride`, `exhaustion`
- Projects: `speculae`, `novel`, `apartment`

---

## Starred entries

Star an entry to mark it as significant — a milestone, a day worth remembering, or an insight you want to find again.

```bash
speculae write --star           # write a starred entry
speculae list --star            # show only starred entries
```

### Web interface

Click the **☆** button in the bottom toolbar to toggle the star on the current entry. Starred entries show **★** in the entry list.

---

## Image attachments

Images are stored locally in the database — they never leave your machine.

### Web interface

With an entry loaded in the Write view:
1. Save the entry first (images require an entry ID)
2. Drag and drop an image onto the drop zone
3. Or paste an image from clipboard (Ctrl+V)
4. Or click the drop zone to browse files

Thumbnails appear below the editor. Click a thumbnail to view full-size. Hover over a thumbnail to reveal the delete button.

**Supported formats:** PNG, JPEG, GIF, WebP, and any other format your browser supports for `<img>`.

### File size

There is no enforced size limit, but large images (>5MB) will make the database grow quickly. Resize before attaching if you want to keep the database compact.

> **Note on database size:** Images are stored as binary blobs directly in SQLite. A few photos per day is fine; hundreds of high-res photos will noticeably bloat the database file. If you journal heavily with photos, consider compressing images before attaching or using a lower resolution.

---

## Markdown formatting

Entry content supports full Markdown via the [marked](https://marked.js.org/) library.

### Supported syntax

| Syntax | Result |
|--------|--------|
| `**bold**` | **bold** |
| `_italic_` | _italic_ |
| `## Heading` | Section heading |
| `- item` | Bullet list |
| `- [ ] task` | Task list item |
| `- [x] done` | Completed task |
| `` `code` `` | Inline code |
| `> quote` | Blockquote |
| `[text](url)` | Link |

### Editor modes

The markdown toolbar in the Write view has three modes:

- **Edit** — plain textarea, full markdown syntax
- **Split** — editor on the left, live preview on the right
- **Preview** — rendered preview only

Switch modes with the Edit/Split/Preview buttons in the toolbar, or use the toolbar buttons to insert markdown formatting at the cursor.

---

## Web interface

Start the web interface:

```bash
speculae-web
```

Opens `http://127.0.0.1:7730` in your browser. The server binds exclusively to localhost — it is not accessible from other machines.

**Stop:** Press `Ctrl+C` in the terminal where you started the server.

**Port conflict:** If port 7730 is taken, it will fail to start. Kill whatever is using it or change the port in the source (not yet configurable via config file).

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+D` | Go to Dashboard |
| `Ctrl+W` | Go to Write |
| `Ctrl+R` | Go to Read |
| `Ctrl+P` | Go to Patterns |
| `Ctrl+C` | Go to Calendar |
| `Ctrl+I` | Go to Insights |
| `Ctrl+B` | Go to Breathe |
| `Ctrl+M` | Go to Meditate |
| `Ctrl+S` | Save entry |
| `Escape` | Exit focus mode |
| `←` / `→` | Navigate to previous/next day (Write view) |

**Keyboard-only navigation:** Every interactive element is reachable via Tab. Nav items, mood/energy dots, filter chips, and toolbar buttons all respond to Enter and Space. Mood/energy dots also support arrow keys for moving between values.

---

## Dashboard

The home view. Shows four widgets at a glance:

- **Mood today** — mood from the most recent entry today, if any
- **Streak** — consecutive days with at least one entry; also shows the longest streak
- **Words this week** — total words written in the last 7 days
- **Journaling prompt** — today's prompt; click "Give me another" for a different one

**Quick actions** below the widgets take you directly to Write, Breathe, or Calendar.

---

## Calendar

A colour-coded heatmap of your moods over the past 6 months. Darker cells indicate higher mood; grey cells indicate an entry with no mood logged; empty cells have no entry.

**Clicking a cell** opens that day in the Write view.

Below the heatmap, four statistics:
- **entries** — total days with at least one entry in the displayed range
- **mean mood** — average across all entries with a logged mood
- **longest streak** — maximum consecutive days with an entry
- **dim day** — the day of the week with the lowest average mood

---

## Patterns

Speculae detects five types of patterns over your entry history. All run locally. See [pattern-detection.md](pattern-detection.md) for full technical detail.

**Minimum data:** 7 entries before pattern detection produces results.

```bash
# Detect and display patterns
speculae patterns

# Force a fresh detection (ignore cache)
speculae patterns --refresh
```

### Web interface

Click **Patterns** in the sidebar. Results are cached — click the `$ speculae patterns --refresh` hint at the bottom to force a refresh, or use the URL parameter `?refresh=true`.

### Pattern types

| Type | What it notices |
|------|----------------|
| Arc | Mood or energy trending up or down over a window |
| Trigger | Tags followed by lower mood the next day |
| Cycle | Repeating mood rhythm (weekly, biweekly, etc.) |
| Blindspot | A topic gone quiet longer than usual |
| Day-of-week | A specific day that consistently runs lower |

---

## Insights

A weekly mirror report: a short summary of the past 7 days drawn from your entries, detected patterns, and statistics. No network calls unless you've configured AI insights.

```bash
speculae insights
speculae insights --days 14    # extend the window
```

**What the report contains:**
- Entry count and total words for the period
- Mood and energy averages
- Most frequent tags
- Any active patterns
- One open question

The question is the point. Not "you should do X." Just: "here's what I noticed — does this match your experience?"

---

## Wellness — breathing

Four evidence-based breathing exercises with animated visual guides.

```bash
speculae breathe                                   # box breathing (default)
speculae breathe --exercise 4-7-8
speculae breathe --exercise coherent
speculae breathe --exercise physiological-sigh
```

| Exercise | Pattern | Best for |
|----------|---------|----------|
| Box | 4s in, 4s hold, 4s out, 4s hold | General calm |
| 4-7-8 | 4s in, 7s hold, 8s out | Sleep, acute anxiety |
| Coherent | 5s in, 5s out | Heart rate variability |
| Physiological sigh | 2s in, 1s top-up, 6s out | Fast stress relief |

### Web interface

Click **Breathe** in the sidebar. Select an exercise, then click **Start**. The circle expands on inhale, holds, contracts on exhale. A cycle counter tracks your progress.

**Screen reader:** A live region announces each phase (Inhale, Hold, Exhale) as it begins.

---

## Wellness — meditation

A simple countdown timer with an optional ambient white-noise generator.

```bash
speculae meditate                  # 10 minutes (default)
speculae meditate --minutes 5
speculae meditate --minutes 20
```

Press `Ctrl+C` to end early.

### Web interface

Click **Meditate** in the sidebar. Select a duration (5, 10, 15, 20, or 30 minutes) and click **Begin**. An SVG circular countdown shows remaining time. Toggle **Ambient** for a low-pass filtered white noise.

**Screen reader:** The timer announces remaining time at each whole minute boundary.

---

## Wellness — journaling prompts

18 prompts across 6 categories. Useful when you want to write but don't know where to start.

```bash
speculae prompt                           # random prompt
speculae prompt --category gratitude
speculae prompt --daily                   # today's deterministic prompt
```

**Categories:** check-in, gratitude, reflection, body, connection, growth.

The daily prompt is deterministic — the same calendar date always shows the same prompt. It rotates through the full set across days.

---

## Export and import

See [export-import.md](export-import.md) for the full reference.

Quick summary:

```bash
speculae export --output journal.json                   # JSON (all entries)
speculae export --format html --output journal.html     # standalone HTML
speculae export --format markdown --output journal.md   # Markdown
speculae export --agent agent-1 --format json            # one agent's entries

speculae import journal.json                            # merge (default)
speculae import journal.json --overwrite                # replace existing
speculae import journal.json --dry-run                  # validate only
```

---

## Configuration

The config file is at `~/.config/speculae/config.toml` (Linux/macOS) or `%APPDATA%\speculae\config.toml` (Windows). Print the path and all current values:

```bash
speculae config
```

See [configuration.md](configuration.md) for all configurable options.

---

## AI insights (optional)

By default, the weekly insight report uses local statistics only. You can optionally connect an AI provider to generate a narrative report.

**Privacy guarantee:** Only a statistical summary is sent to the API — never your raw entry text.

### Setup

1. Open the web interface
2. Click **Config** in the sidebar
3. Toggle **AI-powered insights** on
4. Choose a provider (OpenAI, Gemini, Anthropic, or Custom)
5. Paste your API key
6. Save

Supported providers and their default models:

| Provider | Default model |
|----------|--------------|
| OpenAI | `gpt-4o-mini` |
| Google Gemini | `gemini-2.0-flash` |
| Anthropic | `claude-3-haiku-20240307` |
| Custom (Ollama, etc.) | you choose |

---

## Accessibility

Speculae's web interface is designed to be usable without a mouse.

- **Skip link:** The first Tab stop is a "Skip to main content" link, visible only when focused.
- **Keyboard navigation:** All interactive elements are reachable via Tab. Nav items, mood/energy dots, and filter chips respond to Enter and Space. Mood and energy dots also support arrow keys.
- **Focus indicators:** A visible focus ring (ochre colour) appears on every focused element.
- **ARIA labels:** All regions, controls, and dynamic content are labelled for screen readers.
- **Live regions:** Dynamic content (widget values, save status, search results) is announced automatically.
- **High contrast theme:** Cycles through light → dark → high-contrast via the theme button. High contrast removes background textures and uses fully saturated accent colours.
- **Font size scaling:** Use the **A−** / **A+** / **⟳** controls in the sidebar to scale text from 80% to 150%. Your preference is saved across sessions.
- **Reduced motion:** If your OS has reduced motion enabled, all animations are disabled.

---

## Data and privacy

- **Zero telemetry.** No analytics, no crash reports, no pings.
- **Local only.** The web server binds to `127.0.0.1`. No data leaves your machine by default.
- **AI insights.** If enabled, only a statistics summary is sent — never raw entries.
- **Your database.** SQLite at `%LOCALAPPDATA%\speculae\journal.db`. Back it up like any file.

**Delete everything:**

```bash
speculae destroy
```

Type `destroy` to confirm. This deletes the database only. The config file remains.

---

## Troubleshooting

### The web interface won't start

**Port already in use:**
```
OSError: [Errno 48] Address already in use
```
Something is on port 7730. Find it: `lsof -i :7730` (Linux/macOS) or `netstat -ano | findstr :7730` (Windows). Kill it and retry.

**Flask not installed:**
```
Flask is a core dependency — this shouldn't happen.
Reinstall with: pip install -e .
```

---

### Pattern detection returns nothing

Pattern detection requires at least 7 entries. Run `speculae list` to confirm your entry count.

---

### Images aren't uploading

You must save the entry before attaching images — the upload requires an entry ID. Click **Save** or press `Ctrl+S`, then attach images.

---

### The database seems corrupted

SQLite databases rarely corrupt, but if you see errors like `database disk image is malformed`, try:

```bash
# Make a backup first
cp ~/.local/share/speculae/journal.db ~/journal-backup.db

# Check and repair
sqlite3 ~/.local/share/speculae/journal.db "PRAGMA integrity_check;"
```

If integrity_check returns anything other than `ok`, export whatever you can with `speculae export`, then `speculae destroy` and reimport.

---

### AI insights give unhelpful responses

The AI receives a statistics summary, not your raw entries. If the response feels generic, try switching to a larger model (e.g. `gpt-4o` instead of `gpt-4o-mini`) in the settings overlay.

---

*See also: [getting-started.md](getting-started.md) for a quick-start walkthrough, [agent-usage.md](agent-usage.md) for the agent API, [pattern-detection.md](pattern-detection.md) for detector internals.*
