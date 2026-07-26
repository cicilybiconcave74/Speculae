"""
Pattern detection engine for Speculae.

Five detection algorithms — all run on local data, no API required:

  1. arc          — emotional or energy trend over a rolling window
  2. trigger      — tag ↔ next-day mood correlation
  3. cycle         — recurring mood valleys at regular intervals
  4. blindspot     — long absence of a previously-frequent tag
  5. dow_pattern   — day-of-week mood variance (are Sundays hard?)

Each detector returns a list of Pattern objects.
run_all() collects them and deduplicates by type+title.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from scipy import stats

from .config import PatternsConfig
from .models import Entry, Pattern

# ── helpers ──────────────────────────────────────────────────────────────────

def _consecutive_entries(entries: list[Entry]) -> list[list[Entry]]:
    """Split entries into groups of consecutive (no-gap) days."""
    if not entries:
        return []
    sorted_e = sorted(entries, key=lambda e: e.date)
    groups: list[list[Entry]] = [[sorted_e[0]]]
    for e in sorted_e[1:]:
        prev = groups[-1][-1].date
        if (e.date - prev).days == 1:
            groups[-1].append(e)
        else:
            groups.append([e])
    return groups


def _mood_series(entries: list[Entry]) -> tuple[list[date], list[float]]:
    """Extract (dates, moods) for entries that have mood set."""
    pairs = [(e.date, float(e.mood)) for e in entries if e.mood is not None]
    if not pairs:
        return [], []
    dates, moods = zip(*pairs)
    return list(dates), list(moods)


def _energy_series(entries: list[Entry]) -> tuple[list[date], list[float]]:
    pairs = [(e.date, float(e.energy)) for e in entries if e.energy is not None]
    if not pairs:
        return [], []
    dates, energies = zip(*pairs)
    return list(dates), list(energies)


# ── Arc detection ─────────────────────────────────────────────────────────────

def detect_arcs(entries: list[Entry], cfg: PatternsConfig) -> list[Pattern]:
    """
    Detect sustained upward or downward trends in mood / energy
    over the configured window.
    """
    if len(entries) < cfg.arc_window_days:
        return []

    # Collapse to one entry per date: latest human entry wins, or latest overall.
    by_date: dict[date, Entry] = {}
    for e in sorted(entries, key=lambda e: e.created_at or e.date):
        if e.agent_id is None or e.date not in by_date:
            by_date[e.date] = e

    daily = sorted(by_date.values(), key=lambda e: e.date)

    if len(daily) < cfg.arc_window_days:
        return []

    patterns: list[Pattern] = []
    recent = daily[-cfg.arc_window_days:]

    for metric, series_fn, label in [
        ("mood", _mood_series, "mood"),
        ("energy", _energy_series, "energy"),
    ]:
        dates, values = series_fn(recent)
        if len(values) < 4:
            continue

        x = np.arange(len(values))
        slope, _, r_value, p_value, _ = stats.linregress(x, values)

        # Only flag if statistically suggestive and slope meaningful
        if abs(slope) < cfg.arc_threshold or p_value > cfg.arc_p_value_threshold:
            continue

        direction = "up" if slope > 0 else "down"
        magnitude = abs(slope * len(values))  # total change over window

        if direction == "down" and magnitude > 0.5:
            severity = "significant" if magnitude > 1.5 else "notable"
        elif direction == "up":
            severity = "info"
        else:
            severity = "info"

        title = f"{label.capitalize()} trending {'upward' if direction == 'up' else 'downward'}"
        description = (
            f"Your {label} has been {'rising' if direction == 'up' else 'declining'} "
            f"over the past {len(recent)} days "
            f"(change ≈ {magnitude:+.1f} points on a 1–5 scale). "
            + (
                "A consistent dip over this window is worth noticing."
                if direction == "down"
                else "A consistent rise — something in the environment may be supporting you."
            )
        )

        patterns.append(
            Pattern(
                type="arc",
                title=title,
                description=description,
                severity=severity,
                entry_date_from=dates[0],
                entry_date_to=dates[-1],
                data={
                    "metric": metric,
                    "direction": direction,
                    "slope": round(float(slope), 4),
                    "magnitude": round(float(magnitude), 2),
                    "window_days": len(recent),
                },
            )
        )

    return patterns


# ── Trigger detection ─────────────────────────────────────────────────────────

def detect_triggers(entries: list[Entry], cfg: PatternsConfig) -> list[Pattern]:
    """
    Look for tags that consistently precede a mood dip the following day.
    Requires cfg.trigger_min_occurrences co-occurrences and a statistically
    significant negative mean delta (one-sided t-test,
    p ≤ cfg.trigger_p_value_threshold) before surfacing a pattern.
    """
    if len(entries) < cfg.min_entries_for_patterns:
        return []

    sorted_e = sorted(entries, key=lambda e: e.date)

    # Aggregate mood per date: average across all entries for each date.
    entries_for_date: dict[date, list[Entry]] = defaultdict(list)
    for e in sorted_e:
        entries_for_date[e.date].append(e)

    mood_by_date: dict[date, float] = {}
    for d, day_entries in entries_for_date.items():
        moods = [float(e.mood) for e in day_entries if e.mood is not None]
        if moods:
            mood_by_date[d] = sum(moods) / len(moods)

    # Build tag → list of next-day mood deltas
    tag_next_day: dict[str, list[float]] = defaultdict(list)

    for e in sorted_e:
        next_day = e.date + timedelta(days=1)
        next_mood = mood_by_date.get(next_day)
        current_mood = mood_by_date.get(e.date)
        if next_mood is None or current_mood is None:
            continue
        delta = next_mood - current_mood
        for tag in e.tags:
            tag_next_day[tag].append(delta)

    patterns: list[Pattern] = []
    for tag, deltas in tag_next_day.items():
        if len(deltas) < cfg.trigger_min_occurrences:
            continue
        mean_delta = float(np.mean(deltas))
        # Only surface if mean next-day mood drops by at least 0.5
        if mean_delta > -0.5:
            continue

        # One-sided t-test: is the mean delta significantly negative?
        _, p_value = stats.ttest_1samp(deltas, 0, alternative="less")

        # Zero-variance case (all deltas identical): scipy returns nan.
        if math.isnan(p_value):
            p_value = 0.0 if mean_delta < 0 else 1.0

        if p_value > cfg.trigger_p_value_threshold:
            continue

        std_err = float(np.std(deltas, ddof=1) / np.sqrt(len(deltas)))

        severity = "significant" if (mean_delta < -1.0 and p_value < 0.05) else "notable"

        patterns.append(
            Pattern(
                type="trigger",
                title=f'Days tagged "{tag}" tend to precede lower mood',
                description=(
                    f'On {len(deltas)} days tagged "{tag}", '
                    f"your mood the following day averaged {mean_delta:+.1f} points "
                    f"(±{std_err:.2f} SE, p={p_value:.2f}). "
                    "This is a pattern worth sitting with — not necessarily a cause, "
                    "just a correlation the data keeps returning to."
                ),
                severity=severity,
                data={
                    "tag": tag,
                    "occurrences": len(deltas),
                    "mean_next_day_delta": round(mean_delta, 2),
                    "std_err": round(std_err, 3),
                    "p_value": round(float(p_value), 3),
                    "deltas": [round(d, 2) for d in deltas],
                },
            )
        )

    return patterns


# ── Cycle detection ──────────────────────────────────────────────────────────

def detect_cycles(entries: list[Entry], cfg: PatternsConfig) -> list[Pattern]:
    """
    Look for periodic dips using autocorrelation of the mood series.
    Flags if a significant autocorrelation peak falls in [min_period, max_period].
    """
    if len(entries) < cfg.min_entries_for_patterns * 2:
        return []

    sorted_e = sorted(entries, key=lambda e: e.date)
    _, moods = _mood_series(sorted_e)

    if len(moods) < 14:
        return []

    arr = np.array(moods) - np.mean(moods)

    # Autocorrelation for lags in our window
    min_lag = cfg.cycle_min_period_days
    max_lag = min(cfg.cycle_max_period_days, len(arr) // 2)
    if min_lag >= max_lag:
        return []

    lags = range(min_lag, max_lag + 1)
    autocorrs = []
    for lag in lags:
        if lag >= len(arr):
            autocorrs.append(0.0)
            continue
        corr = float(np.corrcoef(arr[:-lag], arr[lag:])[0, 1])
        autocorrs.append(corr if not math.isnan(corr) else 0.0)

    if not autocorrs:
        return []

    best_idx = int(np.argmax(autocorrs))
    best_corr = autocorrs[best_idx]
    best_lag = list(lags)[best_idx]

    if best_corr < 0.35:
        return []

    # Phase analysis: are the troughs actually negative?
    mood_arr = np.array(moods)

    # Trough positions: samples where the cycle is expected to be at its lowest.
    first_period = mood_arr[:best_lag] if best_lag <= len(mood_arr) else mood_arr
    phase_offset = int(np.argmin(first_period))

    trough_indices = list(range(phase_offset, len(mood_arr), best_lag))
    trough_values = [mood_arr[i] for i in trough_indices if i < len(mood_arr)]

    if not trough_values:
        return []

    overall_mean = float(np.mean(mood_arr))
    trough_mean = float(np.mean(trough_values))

    # Only surface the insight when trough mood is meaningfully below baseline.
    TROUGH_DELTA_THRESHOLD = -0.3
    if trough_mean - overall_mean >= TROUGH_DELTA_THRESHOLD:
        return []

    trough_delta = trough_mean - overall_mean
    severity = "significant" if best_corr > 0.55 else "notable"

    return [
        Pattern(
            type="cycle",
            title=f"~{best_lag}-day emotional cycle",
            description=(
                f"Your mood appears to follow a roughly {best_lag}-day rhythm "
                f"(autocorrelation {best_corr:.2f}). "
                f"Mood during expected low points averages {trough_delta:+.1f} points "
                "below your baseline. "
                "Cycles like this often reflect sleep, social, or hormonal rhythms. "
                "Naming the cycle is the first step to working with it rather than against it."
            ),
            severity=severity,
            data={
                "period_days": best_lag,
                "autocorrelation": round(best_corr, 3),
                "trough_mean_mood": round(trough_mean, 2),
                "overall_mean_mood": round(overall_mean, 2),
                "trough_delta": round(trough_delta, 2),
            },
        )
    ]


# ── Blindspot detection ───────────────────────────────────────────────────────

def detect_blindspots(
    entries: list[Entry],
    cfg: PatternsConfig,
    today: date | None = None,
) -> list[Pattern]:
    """
    Flag topics (tags) that used to appear regularly but have gone quiet.
    'Silence' = gap > blindspot_multiplier × average interval for that tag.
    """
    if len(entries) < cfg.min_entries_for_patterns:
        return []

    if today is None:
        today = date.today()
    sorted_e = sorted(entries, key=lambda e: e.date)

    # Collect dates per tag
    tag_dates: dict[str, list[date]] = defaultdict(list)
    for e in sorted_e:
        for tag in e.tags:
            tag_dates[tag].append(e.date)

    patterns: list[Pattern] = []
    for tag, dates in tag_dates.items():
        if len(dates) < 3:
            continue

        # Average interval between appearances
        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        avg_interval = float(np.mean(intervals))
        last_seen = dates[-1]
        silence = (today - last_seen).days

        # Skip if all appearances were on the same day (avg_interval < 1)
        # — that's not a recurring pattern, just a tag used multiple times in one session.
        if avg_interval < 1:
            continue

        if silence < avg_interval * cfg.blindspot_multiplier:
            continue

        severity = "notable" if silence > avg_interval * 3 else "info"
        patterns.append(
            Pattern(
                type="blindspot",
                title=f'"{tag}" has gone quiet',
                description=(
                    f'You used to write about "{tag}" roughly every {avg_interval:.0f} days. '
                    f"It's been {silence} days since the last mention. "
                    "This may mean nothing — or it may be something worth checking in on."
                ),
                severity=severity,
                entry_date_to=last_seen,
                data={
                    "tag": tag,
                    "last_seen": last_seen.isoformat(),
                    "days_silent": silence,
                    "avg_interval_days": round(avg_interval, 1),
                    "occurrences": len(dates),
                },
            )
        )

    return patterns


# ── Day-of-week pattern ──────────────────────────────────────────────────────

def detect_dow_patterns(entries: list[Entry], cfg: PatternsConfig) -> list[Pattern]:
    """
    Check if mood is significantly lower on a particular day of the week.
    Uses a one-way ANOVA across day groups, then flags the worst day.
    """
    if len(entries) < cfg.min_entries_for_patterns * 2:
        return []

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_dow: dict[int, list[float]] = defaultdict(list)
    for e in entries:
        if e.mood is not None:
            by_dow[e.date.weekday()].append(float(e.mood))

    # Need at least 3 days populated with 2+ entries each
    populated = {d: v for d, v in by_dow.items() if len(v) >= 2}
    if len(populated) < 3:
        return []

    groups = list(populated.values())
    try:
        f_stat, p_value = stats.f_oneway(*groups)
    except Exception:
        return []

    if p_value > 0.1:
        return []

    # Find the worst day
    day_means = {d: float(np.mean(v)) for d, v in populated.items()}
    worst_day = min(day_means, key=lambda d: day_means[d])
    overall_mean = float(np.mean([v for vals in populated.values() for v in vals]))
    delta = day_means[worst_day] - overall_mean

    if delta > -0.4:
        return []

    day_name = DAY_NAMES[worst_day]
    severity = "notable" if delta < -0.8 else "info"
    return [
        Pattern(
            type="dow",
            title=f"{day_name}s tend to be harder",
            description=(
                f"Your mood on {day_name}s averages {delta:+.1f} points below your weekly mean "
                f"(p = {p_value:.3f}). "
                "This might reflect your schedule, social rhythm, or something more structural. "
                "Worth knowing either way."
            ),
            severity=severity,
            data={
                "day": day_name,
                "mean_mood": round(day_means[worst_day], 2),
                "overall_mean": round(overall_mean, 2),
                "delta": round(delta, 2),
                "p_value": round(float(p_value), 4),
            },
        )
    ]


# ── Main runner ───────────────────────────────────────────────────────────────

def run_all(entries: list[Entry], cfg: PatternsConfig) -> list[Pattern]:
    """
    Run all detectors and return a deduplicated, severity-sorted list.
    """
    if not entries:
        return []

    found: list[Pattern] = []
    found.extend(detect_arcs(entries, cfg))
    found.extend(detect_triggers(entries, cfg))
    found.extend(detect_cycles(entries, cfg))
    found.extend(detect_blindspots(entries, cfg))
    found.extend(detect_dow_patterns(entries, cfg))

    # Deduplicate by (type, title, date range)
    seen: set[tuple[str, str, date, date]] = set()
    deduped: list[Pattern] = []
    for p in found:
        key = (p.type, p.title, p.entry_date_from, p.entry_date_to)
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    # Sort: significant → notable → info
    order = {"significant": 0, "notable": 1, "info": 2}
    deduped.sort(key=lambda p: order.get(p.severity, 3))

    return deduped
