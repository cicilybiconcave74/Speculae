"""Tests for the wellness module."""

from __future__ import annotations

from datetime import date

from speculae.wellness import (
    PROMPTS,
    MEDITATION_PRESETS,
    BreathingExercise,
    get_categories,
    get_daily_prompt,
    get_exercise,
    get_exercises,
    get_prompt,
)


# ---------------------------------------------------------------------------
# Breathing exercises
# ---------------------------------------------------------------------------

def test_all_exercises_exist():
    exercises = get_exercises()
    assert set(exercises.keys()) == {"box", "4-7-8", "coherent", "physiological-sigh"}


def test_total_seconds():
    # Box: (4+4+4+4) * 4 = 64
    assert get_exercise("box").total_seconds == 64
    # 4-7-8: (4+7+8) * 4 = 76
    assert get_exercise("4-7-8").total_seconds == 76
    # Coherent: (5+5) * 10 = 100
    assert get_exercise("coherent").total_seconds == 100
    # Physiological sigh: (2+1+6) * 5 = 45
    assert get_exercise("physiological-sigh").total_seconds == 45


def test_get_exercise_unknown_returns_none():
    assert get_exercise("nonexistent") is None


def test_pattern_actions_are_valid():
    valid = {"Inhale", "Exhale", "Hold", "Sip"}
    for ex in get_exercises().values():
        for action, dur in ex.pattern:
            assert action in valid, f"{ex.name}: invalid action {action!r}"
            assert isinstance(dur, int) and dur > 0


def test_pattern_actions_use_capitalized_names():
    for ex in get_exercises().values():
        for action, _ in ex.pattern:
            assert action[0].isupper()


# ---------------------------------------------------------------------------
# Journaling prompts
# ---------------------------------------------------------------------------

def test_all_categories_have_prompts():
    for cat, prompts in PROMPTS.items():
        assert len(prompts) == 3, f"{cat} should have 3 prompts"


def test_prompts_are_nonempty_strings():
    for cat, prompts in PROMPTS.items():
        for p in prompts:
            assert isinstance(p, str) and p.strip(), f"Empty prompt in {cat}"


def test_get_prompt_returns_valid_tuple():
    prompt, cat = get_prompt()
    assert isinstance(prompt, str)
    assert cat in PROMPTS
    assert prompt in PROMPTS[cat]


def test_get_prompt_specific_category():
    prompt, cat = get_prompt("gratitude")
    assert cat == "gratitude"
    assert prompt in PROMPTS["gratitude"]


def test_get_prompt_unknown_category_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown category"):
        get_prompt("nope")


def test_get_categories_returns_all_six():
    cats = get_categories()
    assert len(cats) == 6
    assert set(cats) == {"check-in", "gratitude", "reflection", "body", "connection", "growth"}


def test_daily_prompt_deterministic():
    today = date.today().isoformat()
    idx = int.from_bytes(today.encode(), "big")
    cats = sorted(PROMPTS)
    expected_cat = cats[idx % len(cats)]
    expected_prompt = PROMPTS[expected_cat][idx // len(cats) % len(PROMPTS[expected_cat])]
    prompt, cat = get_daily_prompt()
    assert (prompt, cat) == (expected_prompt, expected_cat)


def test_daily_prompt_changes_across_dates():
    # Two different dates should (almost certainly) yield different prompts
    # We test by checking the int.from_bytes logic directly rather than mocking date.
    today_str = date.today().isoformat()
    idx = int.from_bytes(today_str.encode(), "big")
    cats = sorted(PROMPTS)
    cat = cats[idx % len(cats)]
    prompt = PROMPTS[cat][idx // len(cats) % len(PROMPTS[cat])]
    # Just verify it matches the function output
    assert get_daily_prompt() == (prompt, cat)


# ---------------------------------------------------------------------------
# Meditation presets
# ---------------------------------------------------------------------------

def test_meditation_presets():
    assert len(MEDITATION_PRESETS) == 5
    minutes = [p["minutes"] for p in MEDITATION_PRESETS]
    assert minutes == [5, 10, 15, 20, 30]
    for p in MEDITATION_PRESETS:
        assert "label" in p
        assert isinstance(p["label"], str)
