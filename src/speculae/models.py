"""
Domain models for Speculae.
Plain dataclasses — no ORM, no magic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone


@dataclass
class Entry:
    """A single journal entry (multiple per day allowed)."""
    date: date
    content: str = ""
    mood: int | None = None        # 1..5
    energy: int | None = None      # 1..5
    tags: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    starred: bool = False
    agent_id: str | None = None    # NULL = human, string = agent name
    id: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_empty(self) -> bool:
        return not self.content.strip() and self.mood is None and self.energy is None

    def mood_label(self) -> str:
        if self.mood is None:
            return "—"
        return {1: "very low", 2: "low", 3: "okay", 4: "good", 5: "very good"}[self.mood]

    def energy_label(self) -> str:
        if self.energy is None:
            return "—"
        return {1: "drained", 2: "tired", 3: "steady", 4: "energised", 5: "vibrant"}[self.energy]


@dataclass
class Pattern:
    """A detected pattern in journal data."""
    type: str                          # 'arc' | 'trigger' | 'cycle' | 'blindspot'
    title: str
    description: str
    severity: str = "info"             # 'info' | 'notable' | 'significant'
    entry_date_from: date | None = None
    entry_date_to: date | None = None
    data: dict = field(default_factory=dict)
    id: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str | None = None     # None = human patterns, string = agent-specific

    def emoji(self) -> str:
        return {
            "arc":       "↗" if self.data.get("direction") == "up" else "↘",
            "trigger":   "⚡",
            "cycle":     "↻",
            "blindspot": "◌",
        }.get(self.type, "·")

    def severity_color(self) -> str:
        return {
            "info":        "dim",
            "notable":     "amber",
            "significant": "rose",
        }.get(self.severity, "dim")


@dataclass
class Insight:
    """A generated insight report covering a time period."""
    period_start: date
    period_end: date
    content: str
    type: str = "weekly"
    id: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Image:
    """An image attached to a journal entry."""
    entry_id: str
    filename: str
    mime_type: str = "image/png"
    storage_path: str = ""           # relative to data_dir/images/
    file_size: int = 0
    data: bytes = b""                # transient: populated only when serving/ uploading
    id: str = ""
    created_at: datetime | None = None
