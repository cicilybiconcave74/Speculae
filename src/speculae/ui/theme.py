"""
Speculae warm-dark palette.

Design intent: aged ink on heavy paper — not a cold terminal, not a
minimalist dashboard. The palette should feel like something you want
to spend time inside.

Avoids the AI-default warm-cream-on-white + terracotta accent.
Instead: dark ink background, amber accent, sage/rose as semantic colours.
"""

from rich.console import Console
from rich.theme import Theme

# ── Named hex values ─────────────────────────────────────────────────────────

INK          = "#1a1713"   # darkest bg — almost-black with warmth
SURFACE      = "#241f1b"   # elevated surface
SURFACE_HIGH = "#332b24"   # tooltip / modal surface
BORDER       = "#4a3f35"   # subtle borders, dividers
MUTED        = "#7a6e62"   # secondary / disabled text
TEXT         = "#e8dfd0"   # primary text — warm ivory
EMPHASIS     = "#f5ede0"   # headings, labels
AMBER        = "#c9a86c"   # accent — old gold, not terracotta
AMBER_DIM    = "#8a7242"   # dimmer amber for decorative elements
SAGE         = "#7a9e7e"   # positive / growth patterns
ROSE         = "#c97870"   # concern / declining patterns
VIOLET       = "#9b8ec4"   # neutral / info accent


# ── Rich theme ────────────────────────────────────────────────────────────────

RICH_THEME = Theme(
    {
        # structural
        "speculae.ink":     f"on {INK}",
        "speculae.dim":     f"{MUTED}",
        "speculae.muted":   f"{MUTED}",
        "speculae.border":  f"{BORDER}",

        # text
        "speculae.text":    f"{TEXT}",
        "speculae.heading": f"bold {EMPHASIS}",
        "speculae.label":   f"{AMBER}",

        # semantic
        "speculae.positive":     f"{SAGE}",
        "speculae.warning":      f"{ROSE}",
        "speculae.info":         f"{VIOLET}",
        "speculae.accent":       f"bold {AMBER}",
        "speculae.accent.dim":   f"{AMBER_DIM}",

        # severity
        "severity.info":         f"{MUTED}",
        "severity.notable":      f"{AMBER}",
        "severity.significant":  f"{ROSE}",

        # entry display
        "entry.date":    f"bold {AMBER}",
        "entry.mood":    f"{SAGE}",
        "entry.energy":  f"{VIOLET}",
        "entry.tag":     f"{AMBER_DIM}",
        "entry.content": f"{TEXT}",

        # pattern display
        "pattern.arc":       f"{AMBER}",
        "pattern.trigger":   f"{ROSE}",
        "pattern.cycle":     f"{VIOLET}",
        "pattern.blindspot": f"{MUTED}",
    }
)


def make_console(**kwargs) -> Console:
    """Create a Rich console with the Speculae theme."""
    import sys
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8")
                except Exception:
                    pass
    return Console(theme=RICH_THEME, **kwargs)


# ── Dot meters ────────────────────────────────────────────────────────────────

def dot_meter(value: int | None, max_value: int = 5, filled: str = "●", empty: str = "○") -> str:
    """Render a 1–5 value as filled/empty dots."""
    if value is None:
        return (empty * max_value)
    v = max(1, min(max_value, value))
    return filled * v + empty * (max_value - v)


# ── Textual TCSS ─────────────────────────────────────────────────────────────

WRITER_CSS = f"""
Screen {{
    background: {INK};
}}

#header {{
    height: 3;
    background: {SURFACE};
    border-bottom: solid {BORDER};
    padding: 1 2;
    content-align: center middle;
    color: {AMBER};
}}

#body {{
    padding: 1 3;
}}

#entry-area {{
    height: 1fr;
    background: {SURFACE};
    border: solid {BORDER};
    color: {TEXT};
    scrollbar-background: {INK};
    scrollbar-color: {BORDER};
    padding: 1 1;
    margin-bottom: 1;
}}

#entry-area:focus {{
    border: solid {AMBER};
}}

#meta-row {{
    height: 3;
    layout: horizontal;
    margin-bottom: 1;
}}

#mood-label {{
    width: 8;
    color: {MUTED};
    content-align: left middle;
}}

#mood-display {{
    width: 14;
    color: {SAGE};
    content-align: left middle;
}}

#energy-label {{
    width: 10;
    color: {MUTED};
    content-align: left middle;
}}

#energy-display {{
    width: 14;
    color: {VIOLET};
    content-align: left middle;
}}

#tags-row {{
    height: 3;
    layout: horizontal;
    margin-bottom: 1;
}}

#tags-label {{
    width: 8;
    color: {MUTED};
    content-align: left middle;
}}

#tags-input {{
    width: 1fr;
    background: {SURFACE};
    border: solid {BORDER};
    color: {TEXT};
    padding: 0 1;
}}

#tags-input:focus {{
    border: solid {AMBER};
}}

#footer {{
    height: 2;
    background: {SURFACE};
    border-top: solid {BORDER};
    padding: 0 2;
    content-align: center middle;
    color: {MUTED};
}}

.key-hint {{
    color: {AMBER};
}}
"""
