"""
Insight generation for Speculae.

Two modes:
  - local    : rule-based insight from patterns + statistics (no API)
  - ai       : LLM-generated narrative using the local insight as context (BYOAK)

The local path always runs first. The AI path wraps it in a narrative voice.
The rule: never prescribe. Surface patterns. Let the user draw conclusions.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

logger = logging.getLogger(__name__)

from .config import AIConfig
from .models import Entry, Insight, Pattern

# ── Local insight generation ──────────────────────────────────────────────────

def _stats_block(entries: list[Entry]) -> str:
    """Generate a plain-text stats summary for a list of entries."""
    if not entries:
        return "No entries in this period."

    moods = [e.mood for e in entries if e.mood is not None]
    energies = [e.energy for e in entries if e.energy is not None]
    word_counts = [len(e.content.split()) for e in entries if e.content.strip()]

    lines = []
    lines.append(f"Entries: {len(entries)}")

    if moods:
        avg_mood = sum(moods) / len(moods)
        lines.append(
            f"Mood: avg {avg_mood:.1f}/5  "
            f"(low {min(moods)}, high {max(moods)})"
        )

    if energies:
        avg_energy = sum(energies) / len(energies)
        lines.append(
            f"Energy: avg {avg_energy:.1f}/5  "
            f"(low {min(energies)}, high {max(energies)})"
        )

    if word_counts:
        avg_words = sum(word_counts) / len(word_counts)
        lines.append(f"Avg words written per entry: {avg_words:.0f}")

    # Tag frequency
    tag_counts: dict[str, int] = {}
    for e in entries:
        for tag in e.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    if tag_counts:
        top = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
        top_str = ", ".join(f"#{t} ({n})" for t, n in top)
        lines.append(f"Most frequent tags: {top_str}")

    return "\n".join(lines)


def generate_local(
    entries: list[Entry],
    patterns: list[Pattern],
    period_start: date,
    period_end: date,
) -> str:
    """
    Produce a text insight report without any API call.
    This is always the baseline; AI wraps it if configured.
    """
    period_entries = [
        e for e in entries
        if period_start <= e.date <= period_end
    ]

    lines = []
    lines.append(
        f"Period: {period_start.strftime('%d %B')} – {period_end.strftime('%d %B %Y')}"
    )
    lines.append("")
    lines.append(_stats_block(period_entries))

    if patterns:
        lines.append("")
        lines.append("Patterns detected:")
        for p in patterns:
            lines.append(f"  [{p.severity.upper()}] {p.title}")
            # Indent the description
            for desc_line in p.description.split(". "):
                if desc_line.strip():
                    lines.append(f"    {desc_line.strip()}.")

    if not period_entries:
        lines.append("")
        lines.append(
            "No entries recorded in this period. "
            "The mirror only shows what's put in front of it."
        )

    return "\n".join(lines)


# ── AI-enhanced insight generation ───────────────────────────────────────────

def _resolve_api_key(cfg: AIConfig) -> str:
    """Return the API key appropriate for the configured provider."""
    if cfg.provider == "anthropic":
        return cfg.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if cfg.provider == "gemini":
        return cfg.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
    return cfg.openai_api_key or os.environ.get("OPENAI_API_KEY", "")


# Per-provider sensible defaults — used when the user has not changed the model
# field away from the generic "gpt-4o-mini" placeholder in config.py.
_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini": "gemini-2.5-flash",
}

_OPENAI_CONFIG_DEFAULT = "gpt-4o-mini"  # must match AIConfig.model default in config.py


_SYSTEM_PROMPT = """\
You are the reflection layer of Speculae — a private, local journaling tool.
Your job is to generate a weekly insight report.

Tone: calm, warm, non-prescriptive. You are a mirror, not a therapist.
Never tell the user what to do. Surface patterns and observations.
End with one open question — never more than one. Do not answer it.

Format: plain text, 2–4 short paragraphs. No bullet points. No headers.
No diagnostic language. No "it seems like" or "perhaps you should."
Just honest, clear observations grounded in the data provided.
"""


class _OpenAICompatibleProvider:
    """Handles openai and gemini, both of which speak the OpenAI chat completions API."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        try:
            from openai import OpenAI  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "openai package not installed. "
                "Install it with: pip install 'speculae[llm]'"
            ) from exc
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)
        self._model = model

    def call(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=600,
            temperature=0.4,
        )
        return response.choices[0].message.content or ""


class _AnthropicProvider:
    """Handles Anthropic's native SDK (messages API)."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            import anthropic as anthropic_sdk  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "anthropic package not installed. "
                "Install it with: pip install 'speculae[llm]'"
            ) from exc
        self._client = anthropic_sdk.Anthropic(api_key=api_key)
        self._model = model

    def call(self, system: str, user: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=600,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text


def _build_provider(
    cfg: AIConfig,
) -> _OpenAICompatibleProvider | _AnthropicProvider:
    """Instantiate the right provider from config.

    Raises ValueError if no API key is available.
    Raises ImportError if the required SDK is not installed.
    """
    key = _resolve_api_key(cfg)
    if not key:
        raise ValueError(
            f"No API key configured for provider {cfg.provider!r}. "
            "Set it in the Config panel or via the matching environment variable."
        )

    # If the user left the model at the generic OpenAI default and is using a
    # different provider, substitute a sensible per-provider default instead of
    # sending "gpt-4o-mini" to Anthropic or Gemini.
    model = cfg.model
    if model == _OPENAI_CONFIG_DEFAULT and cfg.provider != "openai":
        model = _PROVIDER_DEFAULT_MODELS.get(cfg.provider, model)

    if cfg.provider == "anthropic":
        return _AnthropicProvider(api_key=key, model=model)

    if cfg.provider == "gemini":
        base_url = cfg.base_url or "https://generativelanguage.googleapis.com/v1beta/openai/"
        return _OpenAICompatibleProvider(api_key=key, model=model, base_url=base_url)

    # Default: openai (or any custom OpenAI-compatible endpoint via base_url)
    return _OpenAICompatibleProvider(api_key=key, model=model, base_url=cfg.base_url or None)


def generate_ai(
    stats_text: str,
    patterns: list[Pattern],
    period_start: date,
    period_end: date,
    cfg: AIConfig,
) -> tuple[str, bool]:
    """
    Ask the configured AI to write a narrative insight from the local stats.
    Returns (text, success). Falls back to the local text if the API call fails.
    """
    try:
        provider = _build_provider(cfg)
    except (ImportError, ValueError) as exc:
        logger.debug("Cannot initialise AI provider: %s", exc)
        return stats_text, False

    pattern_text = ""
    if patterns:
        pattern_text = "\n\nPatterns detected:\n" + "\n".join(
            f"- [{p.severity}] {p.title}: {p.description}" for p in patterns
        )

    user_content = (
        f"Weekly report for {period_start.strftime('%d %B')} "
        f"\u2013 {period_end.strftime('%d %B %Y')}.\n\n"
        f"{stats_text}{pattern_text}"
    )

    try:
        text = provider.call(_SYSTEM_PROMPT, user_content)
        return text or stats_text, bool(text)
    except Exception as exc:
        logger.warning(
            "AI insight generation failed (provider=%r, model=%r): %s: %s",
            cfg.provider,
            cfg.model,
            type(exc).__name__,
            exc,
        )
        return stats_text, False


# ── Public API ────────────────────────────────────────────────────────────────

def generate(
    entries: list[Entry],
    patterns: list[Pattern],
    period_start: date | None = None,
    period_end: date | None = None,
    ai_cfg: AIConfig | None = None,
) -> Insight:
    """
    Generate an Insight for the given period.
    Uses AI if configured; always produces local baseline first.
    """
    today = date.today()
    if period_end is None:
        period_end = today
    if period_start is None:
        period_start = today - timedelta(days=6)

    local_text = generate_local(entries, patterns, period_start, period_end)

    if ai_cfg and ai_cfg.enabled and _resolve_api_key(ai_cfg):
        content, ai_success = generate_ai(local_text, patterns, period_start, period_end, ai_cfg)
        if not ai_success:
            content += "\n\n[AI narrative unavailable — using local analysis]"
    else:
        content = local_text

    return Insight(
        period_start=period_start,
        period_end=period_end,
        content=content,
        type="weekly",
    )
