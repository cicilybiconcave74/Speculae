"""
Tests for speculae.insights — local (rule-based) insight generation.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from speculae.insights import generate, generate_local, _stats_block
from speculae.models import Entry, Pattern


def _entry(days_ago: int, mood: int | None = 3, energy: int | None = 3,
           content: str = "test", tags: list[str] | None = None) -> Entry:
    return Entry(
        date=date.today() - timedelta(days=days_ago),
        mood=mood,
        energy=energy,
        content=content,
        tags=tags or [],
    )


class TestStatsBlock:
    def test_empty_returns_no_entries_message(self):
        result = _stats_block([])
        assert "No entries" in result

    def test_includes_entry_count(self):
        entries = [_entry(i) for i in range(3)]
        result = _stats_block(entries)
        assert "Entries: 3" in result

    def test_includes_mood_stats_when_present(self):
        entries = [_entry(i, mood=m) for i, m in enumerate([1, 3, 5])]
        result = _stats_block(entries)
        assert "Mood" in result
        assert "3.0/5" in result

    def test_omits_mood_stats_when_absent(self):
        entries = [_entry(i, mood=None) for i in range(3)]
        result = _stats_block(entries)
        assert "Mood" not in result

    def test_includes_top_tags(self):
        entries = [_entry(i, tags=["work", "rest"]) for i in range(3)]
        result = _stats_block(entries)
        assert "#work" in result


class TestGenerateLocal:
    def _period(self):
        return date.today() - timedelta(days=6), date.today()

    def test_returns_non_empty_string(self):
        entries = [_entry(i) for i in range(7)]
        start, end = self._period()
        result = generate_local(entries, [], start, end)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_period_in_output(self):
        entries = [_entry(i) for i in range(7)]
        start, end = self._period()
        result = generate_local(entries, [], start, end)
        assert str(end.year) in result

    def test_includes_pattern_titles(self):
        entries = [_entry(i) for i in range(7)]
        p = Pattern(
            type="arc",
            title="Mood trending downward",
            description="Your mood has been declining.",
            severity="notable",
        )
        start, end = self._period()
        result = generate_local(entries, [p], start, end)
        assert "Mood trending downward" in result

    def test_empty_period_includes_mirror_message(self):
        start, end = self._period()
        result = generate_local([], [], start, end)
        assert "mirror" in result.lower()


class TestGenerate:
    def _entries(self, n=7):
        return [_entry(i, mood=3, energy=3, content="test entry") for i in range(n)]

    def test_returns_insight_object(self):
        insight = generate(self._entries(), [])
        assert insight.content
        assert insight.period_start is not None
        assert insight.period_end is not None

    def test_defaults_to_last_7_days(self):
        insight = generate(self._entries(), [])
        expected_start = date.today() - timedelta(days=6)
        assert insight.period_start == expected_start
        assert insight.period_end == date.today()

    def test_respects_custom_period(self):
        start = date.today() - timedelta(days=13)
        end = date.today()
        insight = generate(self._entries(14), [], period_start=start, period_end=end)
        assert insight.period_start == start
        assert insight.period_end == end

    def test_ai_disabled_by_default(self):
        # Without ai_cfg, should still produce content (local path)
        insight = generate(self._entries(), [], ai_cfg=None)
        assert insight.content
        assert "Period:" in insight.content or "Entries:" in insight.content
