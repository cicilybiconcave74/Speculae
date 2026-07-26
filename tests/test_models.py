"""
Tests for speculae.models — Entry / Pattern / Insight.
"""

from __future__ import annotations

from datetime import date

import pytest

from speculae.models import Entry, Pattern, Insight


class TestEntry:
    def test_is_empty_with_no_content_or_mood(self):
        e = Entry(date=date.today())
        assert e.is_empty() is True

    def test_is_not_empty_with_content(self):
        e = Entry(date=date.today(), content="Some text")
        assert e.is_empty() is False

    def test_is_not_empty_with_mood_only(self):
        e = Entry(date=date.today(), mood=3)
        assert e.is_empty() is False

    def test_mood_label_none(self):
        e = Entry(date=date.today(), mood=None)
        assert e.mood_label() == "—"

    @pytest.mark.parametrize("mood,expected", [
        (1, "very low"),
        (2, "low"),
        (3, "okay"),
        (4, "good"),
        (5, "very good"),
    ])
    def test_mood_labels(self, mood, expected):
        e = Entry(date=date.today(), mood=mood)
        assert e.mood_label() == expected

    @pytest.mark.parametrize("energy,expected", [
        (1, "drained"),
        (2, "tired"),
        (3, "steady"),
        (4, "energised"),
        (5, "vibrant"),
    ])
    def test_energy_labels(self, energy, expected):
        e = Entry(date=date.today(), energy=energy)
        assert e.energy_label() == expected

    def test_energy_label_none(self):
        e = Entry(date=date.today(), energy=None)
        assert e.energy_label() == "—"

    def test_default_tags_is_empty_list(self):
        e = Entry(date=date.today())
        assert e.tags == []

    def test_default_id_is_empty_string(self):
        e = Entry(date=date.today())
        assert e.id == ""


class TestPattern:
    def _make(self, type_="arc", direction="down", severity="notable"):
        return Pattern(
            type=type_,
            title="Test",
            description="Desc",
            severity=severity,
            data={"direction": direction},
        )

    def test_arc_down_emoji(self):
        p = self._make(type_="arc", direction="down")
        assert p.emoji() == "↘"

    def test_arc_up_emoji(self):
        p = self._make(type_="arc", direction="up")
        assert p.emoji() == "↗"

    def test_trigger_emoji(self):
        p = self._make(type_="trigger")
        assert p.emoji() == "⚡"

    def test_cycle_emoji(self):
        p = self._make(type_="cycle")
        assert p.emoji() == "↻"

    def test_blindspot_emoji(self):
        p = self._make(type_="blindspot")
        assert p.emoji() == "◌"

    @pytest.mark.parametrize("severity,color", [
        ("info", "dim"),
        ("notable", "amber"),
        ("significant", "rose"),
    ])
    def test_severity_colors(self, severity, color):
        p = self._make(severity=severity)
        assert p.severity_color() == color
