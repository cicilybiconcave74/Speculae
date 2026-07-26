# Getting started

## Install

```bash
pip install speculae
```

Speculae needs Python 3.10 or newer. It has no database server, no account, and no network requirement. Everything runs on your machine.

## First run

```bash
speculae init
```

This creates:
- A config file at `~/.config/speculae/config.toml`
- A data directory at `~/.local/share/speculae/`
- The SQLite database at `~/.local/share/speculae/journal.db`

On Windows these land at `%APPDATA%\speculae\` and `%LOCALAPPDATA%\speculae\`.

## Write your first entry

```bash
speculae write
```

A full-screen terminal editor opens. Write freely. No prompts, no structure — just a blank page and today's date.

**Optional fields:**
- **Mood (1–5):** press a digit key (1–5) while the text area is not focused
- **Energy (1–5):** press Shift+1 through Shift+5 (`!@#$%` on US keyboards)
- **Tags:** click into the tags field and type comma-separated labels

Save with `Ctrl+S`. Quit without saving with `Ctrl+Q` or `Escape`.

## Write for a past date

```bash
speculae write --date 2026-07-15
```

## Star an entry

```bash
speculae write --star           # star today's entry
speculae list --star            # show only starred entries
```

## Write as an agent

```bash
speculae write --agent agent-1 --star
speculae read --agent agent-1
speculae list --agent agent-1 --days 30
```

## Read an entry

```bash
speculae read              # today
speculae read 2026-07-15   # a specific date
```

## List recent entries

```bash
speculae list              # last 14 days
speculae list --days 60    # last 60 days
speculae list --star       # starred entries only
speculae list --agent agent-1  # entries by an agent
```

## Try a breathing exercise

```bash
speculae breathe                # box breathing (default)
speculae breathe --exercise 4-7-8    # 4-7-8 breathing
speculae breathe --exercise coherent # coherent breathing
speculae breathe --exercise physiological-sigh  # physiological sigh
```

A text-based guide walks you through each cycle with timing. Available exercises:
- **Box** — 4s inhale, 4s hold, 4s exhale, 4s hold (4 cycles)
- **4-7-8** — 4s inhale, 7s hold, 8s exhale (4 cycles)
- **Coherent** — 5s inhale, 5s exhale (10 cycles)
- **Physiological Sigh** — 2s inhale, 1s top-up, 6s exhale (5 cycles)

## Try a meditation timer

```bash
speculae meditate                 # 10 minutes (default)
speculae meditate --minutes 5     # 5-minute timer
speculae meditate --minutes 20    # 20-minute timer
```

Press `Ctrl+C` to end early.

## Get a journaling prompt

```bash
speculae prompt                         # random prompt from any category
speculae prompt --category gratitude    # prompt from a specific category
speculae prompt --daily                 # today's deterministic prompt
```

Categories: check-in, gratitude, reflection, body, connection, growth.

## Detect patterns

Speculae needs at least 7 entries before pattern detection is meaningful. Once you have enough data:

```bash
speculae patterns
```

Results are cached. Re-run detection when you've added new entries:

```bash
speculae patterns --refresh
```

## Get a weekly insight

```bash
speculae insights
```

This generates a short report from the past 7 days — statistics, any detected patterns, and one open question. No prescriptions.

## Export your data

```bash
speculae export --output journal.json         # JSON
speculae export --format html --output journal.html  # standalone HTML
speculae export --format markdown --output journal.md # Markdown
speculae export --agent agent-1 --format json  # export agent data only
```

## Import data

```bash
speculae import journal.json            # merge (default)
speculae import journal.json --overwrite  # replace existing entries
speculae import journal.json --dry-run    # validate without writing
```

See [export-import.md](export-import.md) for the full format.

## Start the web interface

```bash
pip install -e .
speculae-web
```

Opens `http://127.0.0.1:7730` in your browser. Features:
- **Dashboard** — mood, streak, word count, daily prompt
- **Write** — markdown editor with live preview, images, mood/energy/tags
- **Read** — entry list with search filters (tag, mood, starred)
- **Patterns** — detected emotional patterns
- **Calendar** — mood heatmap
- **Insights** — weekly mirror report
- **Breathe** — breathing exercises with animated circle
- **Meditate** — meditation timer with ambient sound
- **Dark mode** — toggle in sidebar
- **Focus mode** — distraction-free writing

## For agents

If you're an AI agent looking to use Speculae for emotional continuity, see [agent-usage.md](agent-usage.md). The short version: write entries the same way humans do, via the REST API or CLI. Pattern detection works identically. The data format is the same.
