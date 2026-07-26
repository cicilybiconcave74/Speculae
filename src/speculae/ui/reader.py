"""
Rich-based display layer for Speculae.

All terminal output goes through here — entries, patterns, insights,
the calendar heatmap. Centralised so the visual language is consistent.
"""

from __future__ import annotations

from datetime import date, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from ..models import Entry, Insight, Pattern
from .theme import (
    AMBER,
    AMBER_DIM,
    BORDER,
    MUTED,
    ROSE,
    SAGE,
    TEXT,
    VIOLET,
    dot_meter,
    make_console,
)

# ── Entry display ─────────────────────────────────────────────────────────────

def print_entry(entry: Entry, console: Console | None = None) -> None:
    c = console or make_console()

    date_str = entry.date.strftime("%A, %d %B %Y")
    c.print(Rule(f"[entry.date]{date_str}[/]", style=f"dim {BORDER}"))
    c.print()

    # Metadata bar
    mood_dots = dot_meter(entry.mood)
    energy_dots = dot_meter(entry.energy)
    meta_parts = []
    author_badge = f"[{AMBER}]human[/]" if not entry.agent_id else f"[{VIOLET}]agent:{entry.agent_id}[/]"
    meta_parts.append(f"[{MUTED}]author[/]  {author_badge}")
    meta_parts.append(f"  [{MUTED}]mood[/]  [{SAGE}]{mood_dots}[/]  [{MUTED}]{entry.mood_label()}[/]")
    meta_parts.append(f"  [{MUTED}]energy[/]  [{VIOLET}]{energy_dots}[/]  [{MUTED}]{entry.energy_label()}[/]")
    if entry.tags:
        tag_str = "  ".join(f"[{AMBER_DIM}]#{t}[/]" for t in entry.tags)
        meta_parts.append(f"  {tag_str}")

    c.print("  " + "".join(meta_parts))
    c.print()

    if entry.content.strip():
        for para in entry.content.strip().split("\n\n"):
            c.print(f"  [{TEXT}]{para.strip()}[/]")
            c.print()
    else:
        c.print(f"  [{MUTED}]— no text written —[/]")
        c.print()

    c.print(Rule(style=f"dim {BORDER}"))


def print_entry_list(entries: list[Entry], console: Console | None = None) -> None:
    c = console or make_console()

    if not entries:
        c.print(f"[{MUTED}]No entries found.[/]")
        return

    table = Table(
        show_header=True,
        header_style=f"bold {AMBER}",
        border_style=BORDER,
        box=None,
        padding=(0, 2),
    )
    table.add_column("Date", style=f"bold {TEXT}", width=18)
    table.add_column("Author", style=f"{VIOLET}", width=12)
    table.add_column("Mood", width=10)
    table.add_column("Energy", width=10)
    table.add_column("Tags", style=f"{AMBER_DIM}")
    table.add_column("Words", justify="right", style=MUTED)

    for e in entries:
        author_str = f"[{AMBER}]human[/]" if not e.agent_id else f"[{VIOLET}]{e.agent_id}[/]"
        mood_str = f"[{SAGE}]{dot_meter(e.mood)}[/]" if e.mood else f"[{MUTED}]——————[/]"
        energy_str = f"[{VIOLET}]{dot_meter(e.energy)}[/]" if e.energy else f"[{MUTED}]——————[/]"
        tags_str = " ".join(f"#{t}" for t in e.tags) if e.tags else ""
        word_count = str(len(e.content.split())) if e.content.strip() else "—"
        date_str = e.date.strftime("%d %b %Y  %a")

        table.add_row(date_str, author_str, mood_str, energy_str, tags_str, word_count)

    c.print(table)


# ── Calendar heatmap ──────────────────────────────────────────────────────────

_MOOD_SHADES = {
    None: f"[{BORDER}]·[/]",
    1: f"[{ROSE}]▪[/]",
    2: f"[{ROSE}]▫[/]",
    3: f"[{MUTED}]▪[/]",
    4: f"[{SAGE}]▫[/]",
    5: f"[{SAGE}]▪[/]",
}


def print_calendar(
    entries: list[Entry],
    months: int = 3,
    console: Console | None = None,
) -> None:
    """Print a mood heatmap calendar for the last N months."""
    c = console or make_console()
    entry_map = {e.date: e for e in entries}

    today = date.today()
    end_date = today
    # Start from beginning of (today - months) months
    start_date = date(today.year, today.month, 1)
    for _ in range(months - 1):
        start_date = date(
            start_date.year - (1 if start_date.month == 1 else 0),
            12 if start_date.month == 1 else start_date.month - 1,
            1,
        )

    c.print(f"  [{AMBER}]mood calendar[/]  [{MUTED}]{months} months[/]")
    c.print(f"  [{MUTED}]▪ very low  ▫ low  · no entry  ▫ good  ▪ very good[/]")
    c.print()

    # Week header
    days_header = "  " + "  ".join(
        f"[{MUTED}]{d}[/]" for d in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    )
    c.print(days_header)

    current = start_date
    # Align to Monday
    while current.weekday() != 0:
        current -= timedelta(days=1)

    while current <= end_date:
        row_parts = []
        week_month = None

        for _ in range(7):
            if current < start_date or current > end_date:
                row_parts.append(f"[{BORDER}]  [/]")
            else:
                e = entry_map.get(current)
                mood = e.mood if e else None
                cell = _MOOD_SHADES.get(mood, _MOOD_SHADES[None])
                row_parts.append(cell + " ")
                if week_month is None and current.day <= 7:
                    week_month = current.strftime("%b")

            current += timedelta(days=1)

        month_label = f"[{AMBER_DIM}]{week_month:<5}[/]" if week_month else "      "
        c.print("  " + month_label + "  ".join(row_parts))

    c.print()
    c.print(f"  [{MUTED}]Legend: {ROSE}▪[/] very low  [{ROSE}]▫[/] low  [{BORDER}]·[/] no entry  [{SAGE}]▫[/] good  [{SAGE}]▪[/] very good")


# ── Pattern display ───────────────────────────────────────────────────────────

_TYPE_COLORS = {
    "arc":       AMBER,
    "trigger":   ROSE,
    "cycle":     VIOLET,
    "blindspot": MUTED,
}

_TYPE_LABELS = {
    "arc":       "ARC",
    "trigger":   "TRIGGER",
    "cycle":     "CYCLE",
    "blindspot": "BLINDSPOT",
}

_SEVERITY_COLORS = {
    "info":        MUTED,
    "notable":     AMBER,
    "significant": ROSE,
}


def print_patterns(patterns: list[Pattern], console: Console | None = None) -> None:
    c = console or make_console()

    if not patterns:
        c.print(f"  [{MUTED}]No patterns detected yet.[/]")
        c.print(f"  [{MUTED}]Pattern detection improves with at least 7 entries.[/]")
        return

    c.print(Rule(f"[{AMBER}]patterns[/]", style=f"dim {BORDER}"))
    c.print()

    for p in patterns:
        type_color = _TYPE_COLORS.get(p.type, MUTED)
        sev_color = _SEVERITY_COLORS.get(p.severity, MUTED)

        title_line = (
            f"  [{type_color}]{p.emoji()}[/]  "
            f"[{sev_color}][{p.severity}][/]  "
            f"[bold {TEXT}]{p.title}[/]"
        )
        c.print(title_line)

        # Wrap description
        desc_lines = p.description.split(". ")
        for dl in desc_lines:
            dl = dl.strip()
            if dl:
                if not dl.endswith("."):
                    dl += "."
                c.print(f"     [{MUTED}]{dl}[/]")

        if p.entry_date_from and p.entry_date_to:
            date_str = f"{p.entry_date_from.strftime('%d %b')} – {p.entry_date_to.strftime('%d %b %Y')}"
            c.print(f"     [{BORDER}]{date_str}[/]")
        elif p.entry_date_to:
            c.print(f"     [{BORDER}]last: {p.entry_date_to.strftime('%d %b %Y')}[/]")

        c.print()

    c.print(Rule(style=f"dim {BORDER}"))


# ── Insight display ───────────────────────────────────────────────────────────

def print_insight(insight: Insight, console: Console | None = None) -> None:
    c = console or make_console()

    period = (
        f"{insight.period_start.strftime('%d %B')} "
        f"— {insight.period_end.strftime('%d %B %Y')}"
    )
    c.print(Panel(
        f"[{TEXT}]{insight.content}[/]",
        title=f"[{AMBER}]weekly mirror  ·  {period}[/]",
        border_style=BORDER,
        padding=(1, 2),
    ))


# ── Status / welcome ──────────────────────────────────────────────────────────

def print_welcome(console: Console | None = None) -> None:
    c = console or make_console()
    c.print()
    c.print(f"  [bold {AMBER}]speculae[/]  [{MUTED}]a private mirror[/]")
    c.print()


def print_stats(entry_count: int, first: date | None, last: date | None, console: Console | None = None) -> None:
    c = console or make_console()
    if entry_count == 0:
        c.print(f"  [{MUTED}]No entries yet. Run[/] [bold {AMBER}]speculae write[/] [{MUTED}]to begin.[/]")
        return

    span = (last - first).days + 1 if first and last else 0
    c.print(f"  [{MUTED}]{entry_count} entries[/]", end="")
    if span:
        c.print(f"  [{BORDER}]·[/]  [{MUTED}]{span} days[/]", end="")
    if first:
        c.print(f"  [{BORDER}]·[/]  [{MUTED}]since {first.strftime('%d %b %Y')}[/]", end="")
    c.print()
