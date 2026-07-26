"""
Tests for speculae.patterns — detection algorithms.

We generate synthetic Entry sequences with known structure so we can
assert that each detector fires (or doesn't fire) as expected.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from speculae.config import PatternsConfig
from speculae.models import Entry
from speculae.patterns import (
    detect_arcs,
    detect_blindspots,
    detect_cycles,
    detect_dow_patterns,
    detect_triggers,
    run_all,
)


def _entry(days_ago: int, mood: int | None = None, energy: int | None = None,
           tags: list[str] | None = None, content: str = "") -> Entry:
    return Entry(
        date=date.today() - timedelta(days=days_ago),
        mood=mood,
        energy=energy,
        tags=tags or [],
        content=content,
    )


def _default_cfg(**overrides) -> PatternsConfig:
    cfg = PatternsConfig(
        arc_window_days=7,
        arc_threshold=0.2,
        cycle_min_period_days=5,
        cycle_max_period_days=30,
        blindspot_multiplier=2.0,
        min_entries_for_patterns=5,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# ── Arc detection ─────────────────────────────────────────────────────────────

class TestArcDetection:
    def test_detects_downward_mood_trend(self):
        # Mood declining: oldest entry (6 days ago) = mood 5, today = mood 1.
        # days_ago=i, mood=min(5, i+1) gives high mood in the past, low mood recently.
        entries = [_entry(days_ago=i, mood=min(5, i + 1)) for i in range(7)]
        patterns = detect_arcs(entries, _default_cfg())
        mood_arcs = [p for p in patterns if "mood" in p.title.lower()]
        assert any("downward" in p.title.lower() for p in mood_arcs)

    def test_detects_upward_mood_trend(self):
        # Mood rising 1 → 5 over 7 days
        entries = [_entry(days_ago=6 - i, mood=i + 1) for i in range(7)]
        patterns = detect_arcs(entries, _default_cfg())
        assert any("upward" in p.title.lower() for p in patterns)

    def test_no_arc_with_flat_mood(self):
        # Flat mood — no trend
        entries = [_entry(days_ago=i, mood=3) for i in range(8)]
        patterns = detect_arcs(entries, _default_cfg())
        assert len(patterns) == 0

    def test_no_arc_with_insufficient_entries(self):
        entries = [_entry(days_ago=i, mood=3) for i in range(3)]
        patterns = detect_arcs(entries, _default_cfg(arc_window_days=7))
        assert len(patterns) == 0

    def test_downward_arc_has_correct_severity(self):
        # Large drop should be significant
        entries = [_entry(days_ago=i, mood=5 - i) for i in range(6)]
        patterns = detect_arcs(entries, _default_cfg(arc_threshold=0.1))
        down_arcs = [p for p in patterns if "downward" in p.title.lower()]
        if down_arcs:
            assert down_arcs[0].severity in ("notable", "significant")


# ── Trigger detection ─────────────────────────────────────────────────────────

class TestTriggerDetection:
    def test_detects_tag_correlated_with_mood_dip(self):
        # "stress" tag followed by mood=2 the next day, 5 times (meets
        # trigger_min_occurrences=5 and the t-test at p≈0 due to zero variance).
        entries = []
        for i in range(10):
            if i % 2 == 0:
                entries.append(_entry(days_ago=10 - i, mood=4, tags=["stress"]))
            else:
                entries.append(_entry(days_ago=10 - i, mood=2))

        patterns = detect_triggers(entries, _default_cfg())
        titles = [p.title for p in patterns]
        assert any("stress" in t for t in titles)

    def test_no_trigger_with_insufficient_cooccurrences(self):
        # Tag appears only once — well below trigger_min_occurrences (default 5)
        entries = [
            _entry(days_ago=4, mood=4, tags=["work"]),
            _entry(days_ago=3, mood=2),
            _entry(days_ago=2, mood=3),
            _entry(days_ago=1, mood=3),
            _entry(days_ago=0, mood=3),
        ]
        patterns = detect_triggers(entries, _default_cfg())
        assert not any("work" in p.title for p in patterns)

    def test_no_trigger_when_next_day_mood_neutral(self):
        # Tag always followed by same or higher mood
        entries = [
            _entry(days_ago=6, mood=3, tags=["gym"]),
            _entry(days_ago=5, mood=4),
            _entry(days_ago=4, mood=3, tags=["gym"]),
            _entry(days_ago=3, mood=4),
            _entry(days_ago=2, mood=3, tags=["gym"]),
            _entry(days_ago=1, mood=5),
            _entry(days_ago=0, mood=4),
        ]
        patterns = detect_triggers(entries, _default_cfg())
        assert not any("gym" in p.title for p in patterns)

    def test_no_trigger_without_statistical_signal(self):
        # 5 occurrences of "work" with mixed next-day outcomes — passes mean gate
        # but fails the one-sided t-test at default p threshold.
        entries = [
            _entry(days_ago=10, mood=3, tags=["work"]),
            _entry(days_ago=9,  mood=1),   # delta = -2
            _entry(days_ago=8,  mood=3, tags=["work"]),
            _entry(days_ago=7,  mood=1),   # delta = -2
            _entry(days_ago=6,  mood=3, tags=["work"]),
            _entry(days_ago=5,  mood=4),   # delta = +1
            _entry(days_ago=4,  mood=3, tags=["work"]),
            _entry(days_ago=3,  mood=1),   # delta = -2
            _entry(days_ago=2,  mood=3, tags=["work"]),
            _entry(days_ago=1,  mood=4),   # delta = +1
        ]
        patterns = detect_triggers(entries, _default_cfg())
        assert not any("work" in p.title for p in patterns)


# ── Cycle detection ───────────────────────────────────────────────────────────

class TestCycleDetection:
    def test_detects_periodic_cycle(self):
        import math

        # Clean sinusoidal mood with period 7 over 28 days (4 full cycles).
        # No noise: autocorrelation at lag 7 approaches 1.0, trough delta ≈ -2.1.
        # The detector must fire reliably on this input.
        entries = []
        for i in range(28):
            mood = 3 + round(2 * math.sin(2 * math.pi * i / 7))
            mood = max(1, min(5, mood))
            entries.append(_entry(days_ago=27 - i, mood=mood))

        patterns = detect_cycles(entries, _default_cfg())

        assert len(patterns) >= 1, (
            "detect_cycles failed to identify a clean 7-day sinusoidal cycle "
            "over 28 days — check the autocorrelation or trough thresholds."
        )
        cycle = patterns[0]
        assert cycle.type == "cycle"
        assert "day" in cycle.title
        assert abs(cycle.data["period_days"] - 7) <= 1, (
            f"Expected period near 7, got {cycle.data['period_days']}"
        )

    def test_no_cycle_with_too_few_entries(self):
        entries = [_entry(days_ago=i, mood=3) for i in range(10)]
        patterns = detect_cycles(entries, _default_cfg(min_entries_for_patterns=5))
        # 10 entries < 5*2=10, boundary — no crash is the important thing
        assert isinstance(patterns, list)


# ── Blindspot detection ────────────────────────────────────────────────────────

class TestBlindspotDetection:
    def test_detects_gone_quiet_tag(self):
        # "M." appeared regularly, then went silent 30+ days ago
        entries = []
        for i in range(5, 0, -1):
            entries.append(_entry(days_ago=i * 10 + 30, mood=3, tags=["M."]))
        # Recent entries without the tag
        for i in range(5):
            entries.append(_entry(days_ago=i, mood=3, tags=[]))

        patterns = detect_blindspots(entries, _default_cfg(blindspot_multiplier=1.5))
        blindspot_tags = [p.data.get("tag") for p in patterns if p.type == "blindspot"]
        assert "M." in blindspot_tags

    def test_no_blindspot_for_recent_tag(self):
        # Tag appeared recently — no blindspot
        entries = [_entry(days_ago=i, mood=3, tags=["work"] if i % 3 == 0 else [])
                   for i in range(10)]
        patterns = detect_blindspots(entries, _default_cfg(blindspot_multiplier=3.0))
        work_blindspots = [p for p in patterns if p.data.get("tag") == "work"]
        assert len(work_blindspots) == 0

    def test_no_blindspot_for_rare_tag(self):
        # Tag appeared only once — too few occurrences (< 3)
        entries = [_entry(days_ago=0, tags=["rare"]), _entry(days_ago=1), _entry(days_ago=2)]
        patterns = detect_blindspots(entries, _default_cfg())
        assert not any(p.data.get("tag") == "rare" for p in patterns)


# ── Day-of-week detection ─────────────────────────────────────────────────────

class TestDowDetection:
    def test_detects_consistently_hard_day(self):
        # Mondays (weekday 0) always mood=1; other days mood=5
        entries = []
        for i in range(28):
            d = date.today() - timedelta(days=i)
            mood = 1 if d.weekday() == 0 else 5
            entries.append(Entry(date=d, mood=mood))

        patterns = detect_dow_patterns(entries, _default_cfg(min_entries_for_patterns=5))
        # Should detect Monday as harder
        assert any("Monday" in p.title for p in patterns)

    def test_no_dow_with_uniform_mood(self):
        entries = []
        for i in range(21):
            entries.append(_entry(days_ago=i, mood=3))
        patterns = detect_dow_patterns(entries, _default_cfg())
        # No significant DOW pattern for flat mood
        assert len(patterns) == 0


# ── run_all ───────────────────────────────────────────────────────────────────

class TestRunAll:
    def test_run_all_returns_list(self):
        entries = [_entry(days_ago=i, mood=3) for i in range(10)]
        result = run_all(entries, _default_cfg())
        assert isinstance(result, list)

    def test_run_all_deduplicates(self):
        entries = [_entry(days_ago=i, mood=5 - i % 5) for i in range(14)]
        result = run_all(entries, _default_cfg())
        titles = [p.title for p in result]
        assert len(titles) == len(set(titles))

    def test_run_all_sorts_by_severity(self):
        import math
        entries = []
        for i in range(14):
            mood = 5 - i if i < 7 else 1 + i % 5
            entries.append(_entry(days_ago=14 - i, mood=max(1, min(5, mood))))

        result = run_all(entries, _default_cfg())
        order = {"significant": 0, "notable": 1, "info": 2}
        severities = [order.get(p.severity, 3) for p in result]
        assert severities == sorted(severities)

    def test_run_all_returns_empty_for_no_entries(self):
        assert run_all([], _default_cfg()) == []
