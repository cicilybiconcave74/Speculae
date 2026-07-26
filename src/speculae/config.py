"""
Configuration management for Speculae.
Follows XDG base directory spec on Linux/macOS, AppData on Windows.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore[assignment]


# ── XDG / platform paths ────────────────────────────────────────────────────

def _xdg_config_home() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
    return Path(base)


def _xdg_data_home() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    return Path(base)


CONFIG_DIR: Path = _xdg_config_home() / "speculae"
DATA_DIR: Path = _xdg_data_home() / "speculae"

CONFIG_FILE: Path = CONFIG_DIR / "config.toml"
DB_FILE: Path = DATA_DIR / "journal.db"
EMBEDDINGS_DIR: Path = DATA_DIR / "embeddings"


# ── Config schema ────────────────────────────────────────────────────────────

@dataclass
class JournalConfig:
    """User-facing journal settings."""
    prompt: str = "How are you?"
    editor: str = "internal"          # 'internal' | path to external editor
    date_format: str = "%d %B %Y"
    locale: str = ""                  # empty = system default


@dataclass
class EmbeddingsConfig:
    """Vector embedding settings."""
    enabled: bool = False             # disabled until user opts in
    model: str = "all-MiniLM-L6-v2"  # sentence-transformers model id
    backend: str = "local"            # 'local' | 'openai'
    openai_model: str = "text-embedding-3-small"


@dataclass
class AIConfig:
    """Optional AI-powered insight generation."""
    enabled: bool = False
    provider: str = "openai"          # 'openai' | 'anthropic' | 'gemini'
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""          # dedicated Gemini field, not aliased to openai
    base_url: str = ""                # custom endpoint (Ollama / etc.)
    model: str = "gpt-4o-mini"
    # Model strings are provider-specific. For Anthropic, see:
    # https://docs.anthropic.com/en/docs/about-claude/models/overview
    # Keys can also be set via OPENAI_API_KEY / ANTHROPIC_API_KEY env vars.


@dataclass
class PatternsConfig:
    """Pattern detection tuning.

    cycle_min_period_days sets the shortest repeating cycle the detector
    will surface. Values below 5 increase false-positive risk on short
    data series; values above 7 will miss common weekly rhythms.
    The day-of-week detector (detect_dow_patterns) handles sub-weekly
    patterns independently of this setting.
    """
    arc_window_days: int = 7              # look-back for emotional arc
    arc_threshold: float = 0.3            # min slope to call an arc
    arc_p_value_threshold: float = 0.05   # max p-value for significance
    cycle_min_period_days: int = 5        # shortest cycle to detect (see docstring)
    cycle_max_period_days: int = 30       # longest cycle to detect
    blindspot_multiplier: float = 2.0     # silence = N × avg_interval
    min_entries_for_patterns: int = 7     # need at least this many entries
    trigger_min_occurrences: int = 5      # minimum tag co-occurrences before t-test
    trigger_p_value_threshold: float = 0.10  # one-sided t-test max p-value


@dataclass
class Config:
    """Root configuration object."""
    journal: JournalConfig = field(default_factory=JournalConfig)
    embeddings: EmbeddingsConfig = field(default_factory=EmbeddingsConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    patterns: PatternsConfig = field(default_factory=PatternsConfig)

    # resolved at load time, not stored
    data_dir: Path = field(default_factory=lambda: DATA_DIR, repr=False)
    db_file: Path = field(default_factory=lambda: DB_FILE, repr=False)


# ── TOML serialisation helpers ───────────────────────────────────────────────

def _load_toml_section(mapping: dict, dataclass_type) -> object:
    """Instantiate a dataclass from a dict, ignoring unknown keys."""
    known = {f for f in dataclass_type.__dataclass_fields__}
    filtered = {k: v for k, v in mapping.items() if k in known}
    return dataclass_type(**filtered)


def _to_toml_string(cfg: Config) -> str:
    """Serialize config to TOML string."""
    data = {
        "journal": asdict(cfg.journal),
        "embeddings": asdict(cfg.embeddings),
        "ai": asdict(cfg.ai),
        "patterns": asdict(cfg.patterns),
    }
    if tomli_w is not None:
        return tomli_w.dumps(data)

    # Fallback: hand-rolled serializer for basic types only
    lines = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        for key, val in values.items():
            if isinstance(val, bool):
                lines.append(f'{key} = {"true" if val else "false"}')
            elif isinstance(val, str):
                escaped = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
            elif isinstance(val, (int, float)):
                lines.append(f"{key} = {val}")
        lines.append("")
    return "\n".join(lines)


# ── Public API ───────────────────────────────────────────────────────────────

def load() -> Config:
    """Load config from file, falling back to defaults."""
    cfg = Config()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            raw = tomllib.load(f)

        if "journal" in raw:
            cfg.journal = _load_toml_section(raw["journal"], JournalConfig)
        if "embeddings" in raw:
            cfg.embeddings = _load_toml_section(raw["embeddings"], EmbeddingsConfig)
        if "ai" in raw:
            cfg.ai = _load_toml_section(raw["ai"], AIConfig)
        if "patterns" in raw:
            cfg.patterns = _load_toml_section(raw["patterns"], PatternsConfig)

    # Env-var overrides for API keys (safer than storing in file)
    if not cfg.ai.openai_api_key:
        cfg.ai.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    if not cfg.ai.anthropic_api_key:
        cfg.ai.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not cfg.ai.gemini_api_key:
        cfg.ai.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    return cfg


def save(cfg: Config) -> None:
    """Write config to file, creating directories as needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(_to_toml_string(cfg), encoding="utf-8")


def ensure_dirs(cfg: Config) -> None:
    """Create data directories if they don't exist."""
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
