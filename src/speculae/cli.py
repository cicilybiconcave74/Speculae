"""
Speculae CLI — entry point.

Commands:
  write     Open the TUI writer for today (or --date)
  read      Display an entry
  list      List recent entries
  search    Full-text or semantic search
  patterns  Run pattern detection and display results
  insights  Generate or show the weekly insight report
  calendar  Mood heatmap calendar
  export    Export all data to JSON or Markdown
  import    Import entries from a JSON export file
  breathe   Run a breathing exercise in the terminal
  meditate  Meditation timer
  prompt    Get a journaling prompt
  config    Show or edit configuration
  init      Initialise the database (first run)
  destroy   Delete the database and all data (irreversible)
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import click
import typer
import typer.core

# ── Click 8.4 compatibility ────────────────────────────────────────────────
typer.core.rich = None

_orig_get_metavar = click.ParamType.get_metavar
def _safe_get_metavar(self, param, ctx=None):
    return _orig_get_metavar(self, param, ctx)
click.ParamType.get_metavar = _safe_get_metavar

_orig_arg_mm = typer.core.TyperArgument.make_metavar
_orig_opt_mm = typer.core.TyperOption.make_metavar
def _patched_arg_mm(self, *args, **kwargs):
    return _orig_arg_mm(self, *args, **kwargs)
def _patched_opt_mm(self, *args, **kwargs):
    return _orig_opt_mm(self, *args, **kwargs)
typer.core.TyperArgument.make_metavar = _patched_arg_mm
typer.core.TyperOption.make_metavar = _patched_opt_mm

_orig_typer_opt_init = typer.core.TyperOption.__init__
def _patched_typer_opt_init(self, *args, **kwargs):
    param_type = kwargs.get("type", None)
    if "is_flag" not in kwargs or kwargs["is_flag"] is None:
        if param_type is not None and not (isinstance(param_type, click.types.BoolParamType) or param_type is bool):
            kwargs["is_flag"] = False
    _orig_typer_opt_init(self, *args, **kwargs)
typer.core.TyperOption.__init__ = _patched_typer_opt_init


from . import config as cfg_module
from . import db
from . import insights as insights_module
from . import patterns as patterns_module
from .models import Entry
from .ui import reader, theme

app = typer.Typer(
    name="speculae",
    help="A private mirror for your emotional life.",
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)

console = theme.make_console()


def _get_db(cfg) -> db.Database:
    database = db.Database(cfg.db_file)
    database.connect()
    return database


# ── init ──────────────────────────────────────────────────────────────────────

@app.command()
def init():
    """Initialise the database and config (run once on first install)."""
    cfg = cfg_module.load()
    cfg_module.ensure_dirs(cfg)
    database = db.Database(cfg.db_file)
    database.connect()
    database.close()

    if not cfg_module.CONFIG_FILE.exists():
        cfg_module.save(cfg)
        console.print(f"  Config written to [{theme.AMBER}]{cfg_module.CONFIG_FILE}[/]")

    console.print(f"  Database at [{theme.AMBER}]{cfg.db_file}[/]")
    console.print(f"  [{theme.MUTED}]Ready. Run[/] [{theme.AMBER}]speculae write[/] [{theme.MUTED}]to begin.[/]")


# ── write ─────────────────────────────────────────────────────────────────────

@app.command()
def write(
    entry_date: str | None = typer.Option(
        None, "--date", "-d",
        help="Date to write for (YYYY-MM-DD). Defaults to today.",
    ),
    edit: bool = typer.Option(False, "--edit", "-e", help="Force re-edit an existing entry."),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent ID."),
    star: bool = typer.Option(False, "--star", "-s", help="Star this entry."),
    content: str | None = typer.Option(
        None, "--content", "-c",
        help="Entry content (non-interactive). Reads from stdin if '-'.",
    ),
    mood: int | None = typer.Option(None, "--mood", "-m", help="Mood 1-5."),
    energy: int | None = typer.Option(None, "--energy", "-n", help="Energy 1-5."),
    tags: str | None = typer.Option(None, "--tags", "-t", help="Comma-separated tags."),
):
    """Open the journal writer, or write non-interactively with --content."""
    cfg = cfg_module.load()
    cfg_module.ensure_dirs(cfg)

    try:
        target_date = date.fromisoformat(entry_date) if entry_date else date.today()
    except ValueError:
        console.print(f"  [{theme.ROSE}]Invalid date: {entry_date!r}. Use YYYY-MM-DD.[/]")
        raise typer.Exit(1)

    # ── Non-interactive path ──────────────────────────────────────────────────
    if content is not None:
        import sys
        body = sys.stdin.read() if content == "-" else content
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        entry = Entry(
            date=target_date,
            content=body,
            mood=mood,
            energy=energy,
            tags=tag_list,
            starred=star,
            agent_id=agent,
        )
        with _get_db(cfg) as database:
            db.save_entry(database, entry)
        console.print(
            f"  [{theme.SAGE}]Saved.[/]  [{theme.MUTED}]{len(body.split())} words[/]"
        )
        return

    # ── Interactive TUI path (existing) ──────────────────────────────────────
    with _get_db(cfg) as database:
        existing_entries = db.get_entries_for_date(database, target_date)
        existing = existing_entries[0] if existing_entries else None

    if existing and not edit:
        console.print(
            f"  [{theme.MUTED}]Entry for {target_date} already exists. "
            f"Use [/][{theme.AMBER}]--edit[/] [{theme.MUTED}]to modify it.[/]"
        )
        raise typer.Exit(0)

    from .ui.writer import run_writer
    entry = run_writer(entry_date=target_date, existing=existing)

    if entry is None:
        console.print(f"  [{theme.MUTED}]No changes saved.[/]")
        return

    entry.agent_id = agent
    entry.starred = star

    with _get_db(cfg) as database:
        db.save_entry(database, entry)

    console.print(
        f"  [{theme.SAGE}]Saved.[/]  [{theme.MUTED}]{len(entry.content.split())} words[/]"
    )


# ── read ──────────────────────────────────────────────────────────────────────

@app.command()
def read(
    entry_date: str | None = typer.Argument(
        None, help="Date to read (YYYY-MM-DD). Defaults to today."
    ),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent ID."),
):
    """Display a journal entry."""
    cfg = cfg_module.load()

    try:
        target_date = date.fromisoformat(entry_date) if entry_date else date.today()
    except ValueError:
        console.print(f"  [{theme.ROSE}]Invalid date: {entry_date!r}[/]")
        raise typer.Exit(1)

    with _get_db(cfg) as database:
        entries = db.get_entries_for_date(database, target_date)
        if agent is not None:
            entries = [e for e in entries if e.agent_id == agent]
        entry = entries[0] if entries else None

    if not entry:
        console.print(
            f"  [{theme.MUTED}]No entry for {target_date.strftime('%d %B %Y')}.[/]  "
            f"[{theme.AMBER}]speculae write --date {target_date}[/]"
        )
        return

    reader.print_entry(entry, console)


# ── list ──────────────────────────────────────────────────────────────────────

@app.command(name="list")
def list_entries(
    days: int = typer.Option(14, "--days", "-n", help="How many days back to show."),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent ID."),
    star: bool = typer.Option(False, "--star", "-s", help="Show only starred entries."),
):
    """List recent journal entries."""
    cfg = cfg_module.load()

    since = date.today() - timedelta(days=days - 1)
    with _get_db(cfg) as database:
        entries = db.list_entries(database, limit=days, since=since, agent_id=agent, starred_only=star)
        total = db.entry_count(database)
        first, last = db.date_range(database)

    console.print()
    reader.print_welcome(console)
    reader.print_stats(total, first, last, console)
    console.print()
    reader.print_entry_list(entries, console)


# ── search ────────────────────────────────────────────────────────────────────

@app.command()
def search(
    query: str = typer.Argument(..., help="Search term(s)."),
    semantic: bool = typer.Option(
        False, "--semantic", "-s", is_flag=True,
        help="Use semantic (vector) search instead of full-text.",
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results."),
):
    """Search journal entries."""
    cfg = cfg_module.load()

    with _get_db(cfg) as database:
        if semantic and str(semantic).lower() not in ("false", "0"):
            if not cfg.embeddings.enabled:
                console.print(
                    f"  [{theme.ROSE}]Semantic search requires embeddings to be enabled.[/]\n"
                    f"  [{theme.MUTED}]Set[/] [{theme.AMBER}]embeddings.enabled = true[/] "
                    f"[{theme.MUTED}]in[/] [{theme.AMBER}]{cfg_module.CONFIG_FILE}[/]"
                )
                raise typer.Exit(1)

            from .embeddings import EmbeddingsNotAvailable, semantic_search
            try:
                all_entries = db.list_entries(database, limit=10000)
                pairs = [(e, e.embedding) for e in all_entries if e.embedding]
                scored = semantic_search(query, pairs, top_k=limit, cfg=cfg.embeddings)
                entries = [e for e, _ in scored]
            except EmbeddingsNotAvailable as exc:
                console.print(f"  [{theme.ROSE}]{exc}[/]")
                raise typer.Exit(1)
        else:
            try:
                entries = db.search_entries(database, query, limit=limit)
            except Exception:
                # FTS5 query syntax error — try plain LIKE search
                entries = [
                    e for e in db.list_entries(database, limit=1000)
                    if query.lower() in e.content.lower()
                ][:limit]

    if not entries:
        console.print(f"  [{theme.MUTED}]No results for[/] [bold]{query!r}[/]")
        return

    console.print(
        f"  [{theme.MUTED}]{len(entries)} result(s) for[/] [{theme.AMBER}]{query!r}[/]\n"
    )
    reader.print_entry_list(entries, console)


# ── patterns ──────────────────────────────────────────────────────────────────

@app.command()
def patterns(
    refresh: bool = typer.Option(
        False, "--refresh", "-r",
        help="Re-run detection even if cached results exist.",
    ),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent ID."),
):
    """Detect and display patterns in your journal data."""
    cfg = cfg_module.load()

    with _get_db(cfg) as database:
        cached = db.list_patterns(database)

        if cached and not refresh and not db.patterns_are_stale(database, agent):
            reader.print_patterns(cached, console)
            return

        entries = db.list_entries(database, limit=10000, agent_id=agent)
        if len(entries) < cfg.patterns.min_entries_for_patterns:
            console.print(
                f"  [{theme.MUTED}]Pattern detection needs at least "
                f"{cfg.patterns.min_entries_for_patterns} entries. "
                f"You have {len(entries)}.[/]"
            )
            return

        found = patterns_module.run_all(entries, cfg.patterns)
        db.save_patterns(database, found)

    reader.print_patterns(found, console)


# ── insights ──────────────────────────────────────────────────────────────────

@app.command()
def insights(
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Regenerate even if recent."),
    days: int = typer.Option(7, "--days", "-n", help="Period for the report (default: 7)."),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent ID."),
):
    """Generate or display the weekly insight report."""
    cfg = cfg_module.load()

    with _get_db(cfg) as database:
        cached = db.latest_insight(database)
        if cached and not refresh:
            reader.print_insight(cached, console)
            return

        entries = db.list_entries(database, limit=10000, agent_id=agent)
        found_patterns = patterns_module.run_all(entries, cfg.patterns)

        period_end = date.today()
        period_start = period_end - timedelta(days=days - 1)

        insight = insights_module.generate(
            entries=entries,
            patterns=found_patterns,
            period_start=period_start,
            period_end=period_end,
            ai_cfg=cfg.ai if cfg.ai.enabled else None,
        )
        db.save_insight(database, insight)

    reader.print_insight(insight, console)


# ── calendar ──────────────────────────────────────────────────────────────────

@app.command()
def calendar(
    months: int = typer.Option(3, "--months", "-m", help="Months to display."),
):
    """Show a mood heatmap calendar."""
    cfg = cfg_module.load()

    with _get_db(cfg) as database:
        entries = db.list_entries(database, limit=10000)

    console.print()
    reader.print_calendar(entries, months=months, console=console)


# ── export ────────────────────────────────────────────────────────────────────

@app.command()
def export(
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file path. Defaults to stdout."
    ),
    fmt: str = typer.Option("json", "--format", "-f", help="Format: json | markdown"),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent ID."),
):
    """Export all journal entries (JSON or Markdown)."""
    cfg = cfg_module.load()

    with _get_db(cfg) as database:
        entries = db.list_entries(database, limit=1_000_000, agent_id=agent)

    if not entries:
        console.print(f"  [{theme.MUTED}]No entries to export.[/]")
        return

    if fmt == "json":
        EXPORT_SCHEMA_VERSION = 1
        data = {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "entries": [
                {
                    "date": e.date.isoformat(),
                    "content": e.content,
                    "mood": e.mood,
                    "energy": e.energy,
                    "tags": e.tags,
                    "starred": e.starred,
                    "agent_id": e.agent_id,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "updated_at": e.updated_at.isoformat() if e.updated_at else None,
                }
                for e in entries
            ],
        }
        text = json.dumps(data, indent=2, ensure_ascii=False)

    elif fmt == "markdown":
        lines = ["# Speculae Journal Export\n"]
        for e in reversed(entries):  # chronological
            lines.append(f"## {e.date.strftime('%A, %d %B %Y')}\n")
            if e.mood or e.energy or e.tags:
                meta = []
                if e.mood:
                    meta.append(f"mood: {e.mood}/5")
                if e.energy:
                    meta.append(f"energy: {e.energy}/5")
                if e.tags:
                    meta.append("tags: " + ", ".join(e.tags))
                lines.append(f"*{' · '.join(meta)}*\n")
            if e.content.strip():
                lines.append(e.content.strip() + "\n")
            lines.append("---\n")
        text = "\n".join(lines)

    else:
        console.print(f"  [{theme.ROSE}]Unknown format: {fmt!r}. Use json or markdown.[/]")
        raise typer.Exit(1)

    if output:
        output.write_text(text, encoding="utf-8")
        console.print(
            f"  [{theme.SAGE}]Exported {len(entries)} entries to[/] [{theme.AMBER}]{output}[/]"
        )
    else:
        print(text)


# ── import ────────────────────────────────────────────────────────────────────

@app.command(name="import")
def import_entries(
    source: Path = typer.Argument(..., help="Path to a JSON export file."),
    overwrite: bool = typer.Option(
        False, "--overwrite",
        help="Replace any existing entry with the imported version. Default: merge (skip existing dates).",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n",
        help="Parse and validate without writing anything.",
    ),
):
    """
    Import entries from a JSON export file.

    The JSON file must be the format produced by `speculae export --format json`:
    a top-level array where each element has at least a "date" (YYYY-MM-DD) field.
    All other fields are optional and will be merged gracefully.

    Your data is never deleted — import only adds or updates.
    """
    cfg = cfg_module.load()

    if not source.exists():
        console.print(f"  [{theme.ROSE}]File not found: {source}[/]")
        raise typer.Exit(1)

    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"  [{theme.ROSE}]Invalid JSON: {exc}[/]")
        raise typer.Exit(1)

    if not isinstance(raw, list):
        console.print(
            f"  [{theme.ROSE}]Expected a JSON array at the top level. "
            f"Got: {type(raw).__name__}[/]"
        )
        raise typer.Exit(1)

    # Parse and validate
    parsed: list[Entry] = []
    errors: list[str] = []

    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"Item {i}: expected object, got {type(item).__name__}")
            continue
        if "date" not in item:
            errors.append(f"Item {i}: missing required field 'date'")
            continue
        try:
            entry_date = date.fromisoformat(item["date"])
        except ValueError:
            errors.append(f"Item {i}: invalid date {item['date']!r} (expected YYYY-MM-DD)")
            continue

        mood = item.get("mood")
        energy = item.get("energy")
        if mood is not None and not (isinstance(mood, int) and 1 <= mood <= 5):
            errors.append(f"Item {i} ({item['date']}): mood must be 1–5 or null, got {mood!r}")
            mood = None
        if energy is not None and not (isinstance(energy, int) and 1 <= energy <= 5):
            errors.append(f"Item {i} ({item['date']}): energy must be 1–5 or null, got {energy!r}")
            energy = None

        tags = item.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        created_at = None
        updated_at = None
        try:
            if item.get("created_at"):
                created_at = datetime.fromisoformat(item["created_at"])
            if item.get("updated_at"):
                updated_at = datetime.fromisoformat(item["updated_at"])
        except ValueError:
            pass  # timestamps are advisory; silently ignore malformed ones

        starred_raw = item.get("starred", False)
        starred = bool(starred_raw) if isinstance(starred_raw, (bool, int)) else False

        agent_id = item.get("agent_id")
        if agent_id is not None and not isinstance(agent_id, str):
            agent_id = None

        parsed.append(Entry(
            date=entry_date,
            content=item.get("content", ""),
            mood=mood,
            energy=energy,
            tags=[str(t) for t in tags if t],
            starred=starred,
            agent_id=agent_id,
            created_at=created_at,
            updated_at=updated_at,
        ))

    if errors:
        console.print(f"  [{theme.ROSE}]Validation errors:[/]")
        for err in errors[:10]:
            console.print(f"    [{theme.MUTED}]{err}[/]")
        if len(errors) > 10:
            console.print(f"    [{theme.MUTED}]… and {len(errors) - 10} more[/]")
        if not parsed:
            raise typer.Exit(1)
        console.print(
            f"  [{theme.AMBER}]{len(errors)} item(s) skipped, "
            f"{len(parsed)} valid entries will be imported.[/]"
        )

    if not parsed:
        console.print(f"  [{theme.MUTED}]Nothing to import.[/]")
        return

    if dry_run:
        console.print(
            f"  [{theme.SAGE}]Dry run: {len(parsed)} entries parsed successfully.[/]"
        )
        console.print(
            f"  [{theme.MUTED}]Earliest: {min(e.date for e in parsed)}  "
            f"Latest: {max(e.date for e in parsed)}[/]"
        )
        return

    cfg_module.ensure_dirs(cfg)
    imported = 0
    skipped = 0

    with _get_db(cfg) as database:
        for entry in parsed:
            # Match by created_at for identity; skip if same entry already exists.
            if entry.created_at:
                exact = db.get_entry_by_created_at(database, entry.created_at)
            else:
                exact = None

            if exact and not overwrite:
                skipped += 1
                continue

            db.save_entry(database, entry)
            imported += 1

    msg_parts = [f"[{theme.SAGE}]Imported {imported} entries.[/]"]
    if skipped:
        msg_parts.append(
            f"  [{theme.MUTED}]{skipped} skipped (already exist — use --overwrite to replace).[/]"
        )
    console.print("  " + "  ".join(msg_parts))


# ── breathe ───────────────────────────────────────────────────────────────────

@app.command()
def breathe(
    exercise: str = typer.Option("box", "--exercise", "-e", help="Exercise: box | 4-7-8 | coherent | physiological-sigh"),
    cycles: int | None = typer.Option(None, "--cycles", "-n", help="Override number of cycles."),
):
    """Run a breathing exercise in the terminal."""
    import time

    from .wellness import get_exercise

    ex = get_exercise(exercise)
    if not ex:
        console.print(f"  Unknown exercise: {exercise!r}")
        raise typer.Exit(1)

    n_cycles = cycles if cycles is not None else ex.cycles
    total_s = n_cycles * (sum(d for _, d in ex.pattern))

    console.print(f"\n  {ex.name}")
    console.print(f"  {ex.description}")
    console.print(f"  {n_cycles} cycles · {total_s}s total")
    console.print(f"  [{theme.MUTED}]Press Ctrl+C to end early.[/]\n")

    try:
        for cycle in range(n_cycles):
            console.print(f"  Cycle {cycle + 1}/{n_cycles}")
            for action, duration in ex.pattern:
                console.print(f"    {action} ({duration}s)...", end="")
                time.sleep(duration)
                print(" done")
        console.print("\n  Complete.")
    except KeyboardInterrupt:
        console.print("\n  Ended early.")


# ── meditate ──────────────────────────────────────────────────────────────────

@app.command()
def meditate(
    minutes: int = typer.Option(10, "--minutes", "-m", help="Duration in minutes."),
):
    """Meditation timer."""
    console.print(f"\n  Meditation — {minutes} minutes")
    console.print("  Press Ctrl+C to end early.\n")
    import time
    try:
        time.sleep(minutes * 60)
        console.print("\n  Session complete.")
    except KeyboardInterrupt:
        console.print("\n  Session ended early.")


# ── prompt ────────────────────────────────────────────────────────────────────

@app.command()
def prompt(
    category: str | None = typer.Option(None, "--category", "-c", help="Prompt category."),
    daily: bool = typer.Option(False, "--daily", "-d", help="Get today's daily prompt."),
):
    """Get a journaling prompt."""
    from .wellness import get_daily_prompt, get_prompt
    if daily:
        text, cat = get_daily_prompt()
        console.print(f"\n  [{theme.AMBER}]{cat}[/] prompt for today:")
        console.print(f"  \"{text}\"\n")
    else:
        text, cat = get_prompt(category)
        console.print(f"\n  [{theme.AMBER}]{cat}[/] prompt:")
        console.print(f"  \"{text}\"\n")


# ── agents ───────────────────────────────────────────────────────────────────

@app.command(name="agents")
def list_agents():
    """List distinct agents that have authored entries, with entry counts and latest activity."""
    cfg = cfg_module.load()
    with _get_db(cfg) as database:
        detailed = db.list_agents_detailed(database)

    if not detailed:
        console.print(f"\n  [{theme.MUTED}]No agent entries found in database.[/] [{theme.AMBER}]Human entries only.[/]\n")
        return

    from rich.table import Table
    table = Table(
        show_header=True,
        header_style=f"bold {theme.AMBER}",
        border_style=theme.BORDER,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Agent ID", style=f"bold {theme.VIOLET}", width=18)
    table.add_column("Display Name", style=f"{theme.TEXT}", width=18)
    table.add_column("Entries", justify="right", style=f"{theme.AMBER}")
    table.add_column("Latest Activity", style=f"{theme.MUTED}", width=16)

    for a in detailed:
        table.add_row(a["id"], a["name"], str(a["entry_count"]), a["latest_date"] or "—")

    console.print()
    console.print(f"  [{theme.AMBER}]Registered Agents[/]  [{theme.MUTED}]({len(detailed)} found)[/]")
    console.print()
    console.print(table)
    console.print()


# ── config ────────────────────────────────────────────────────────────────────

@app.command(name="config")
def show_config(
    show: bool = typer.Option(True, "--show", "--no-show", help="Print current config."),
):
    """Show configuration paths and current settings."""
    cfg = cfg_module.load()

    console.print(f"\n  [{theme.AMBER}]Config file:[/]  {cfg_module.CONFIG_FILE}")
    console.print(f"  [{theme.AMBER}]Data dir:[/]     {cfg.data_dir}")
    console.print(f"  [{theme.AMBER}]Database:[/]     {cfg.db_file}")
    console.print()

    if show and cfg_module.CONFIG_FILE.exists():
        text = cfg_module.CONFIG_FILE.read_text()
        for line in text.splitlines():
            if line.startswith("["):
                console.print(f"  [{theme.AMBER}]{line}[/]")
            elif "=" in line:
                k, _, v = line.partition("=")
                key = k.strip()
                val = v.strip()
                # Hide empty secret fields
                if "key" in key.lower() and (val == '""' or val == "''" or val == ""):
                    console.print(
                        f"  [{theme.MUTED}]{key}[/] = [{theme.MUTED}](not set)[/]"
                    )
                else:
                    console.print(
                        f"  [{theme.MUTED}]{key}[/] = [{theme.TEXT}]{val}[/]"
                    )
            else:
                console.print(f"  [{theme.MUTED}]{line}[/]")
    elif show:
        console.print(
            f"  [{theme.MUTED}]No config file yet. "
            f"Defaults in use. Run[/] [{theme.AMBER}]speculae init[/] [{theme.MUTED}]to create it.[/]"
        )


# ── destroy ───────────────────────────────────────────────────────────────────

@app.command()
def destroy(
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Skip the confirmation prompt.",
    ),
):
    """
    Permanently delete the database and all journal data.

    This is irreversible. Export first if you want a backup:
      speculae export --output backup.json
    """
    cfg = cfg_module.load()

    if not cfg.db_file.exists():
        console.print(f"  [{theme.MUTED}]No database found at {cfg.db_file}. Nothing to destroy.[/]")
        return

    if not yes:
        console.print(f"  [{theme.ROSE}]This will permanently delete {cfg.db_file}[/]")
        console.print(f"  [{theme.MUTED}]Consider running[/] [{theme.AMBER}]speculae export --output backup.json[/] [{theme.MUTED}]first.[/]")
        confirm = typer.prompt("  Type 'destroy' to confirm")
        if confirm.strip() != "destroy":
            console.print(f"  [{theme.MUTED}]Aborted.[/]")
            raise typer.Exit(0)

    cfg.db_file.unlink()
    console.print(f"  [{theme.ROSE}]Database deleted.[/] [{theme.MUTED}]All entries are gone.[/]")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    app()


if __name__ == "__main__":
    main()
