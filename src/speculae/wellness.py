"""
Wellness tools — breathing exercises, meditation presets, and journaling prompts.

Pure Python, no external dependencies.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

# ---------------------------------------------------------------------------
# Breathing exercises
# ---------------------------------------------------------------------------

@dataclass
class BreathingExercise:
    name: str
    description: str
    pattern: list[tuple[str, int]]  # (action_name, duration_seconds)
    cycles: int

    @property
    def total_seconds(self) -> int:
        return sum(d for _, d in self.pattern) * self.cycles


_EXERCISES: dict[str, BreathingExercise] = {
    "box": BreathingExercise(
        name="Box Breathing",
        description="Equal inhale, hold, exhale, hold — calming and stabilising.",
        pattern=[("Inhale", 4), ("Hold", 4), ("Exhale", 4), ("Hold", 4)],
        cycles=4,
    ),
    "4-7-8": BreathingExercise(
        name="4-7-8",
        description="Inhale 4, hold 7, exhale 8 — promotes relaxation and sleep.",
        pattern=[("Inhale", 4), ("Hold", 7), ("Exhale", 8)],
        cycles=4,
    ),
    "coherent": BreathingExercise(
        name="Coherent",
        description="Equal inhale and exhale at ~6 breaths/min — synchronises heart rate.",
        pattern=[("Inhale", 5), ("Exhale", 5)],
        cycles=10,
    ),
    "physiological-sigh": BreathingExercise(
        name="Physiological Sigh",
        description="Double inhale followed by a long exhale — fast stress relief.",
        pattern=[("Inhale", 2), ("Sip", 1), ("Exhale", 6)],
        cycles=5,
    ),
}

_VALID_ACTIONS = {"Inhale", "Exhale", "Hold", "Sip"}


def get_exercises() -> dict[str, BreathingExercise]:
    """Return all pre-defined exercises keyed by slug."""
    return dict(_EXERCISES)


def get_exercise(name: str) -> BreathingExercise | None:
    """Return a single exercise by key, or None if unknown."""
    return _EXERCISES.get(name)


# ---------------------------------------------------------------------------
# Journaling prompts
# ---------------------------------------------------------------------------

PROMPTS: dict[str, list[str]] = {
    "check-in": [
        "How are you arriving in this moment — body, mind, and mood?",
        "What emotion is loudest right now, and where do you feel it?",
        "Rate your energy 1–5 and describe what shaped it today.",
    ],
    "gratitude": [
        "Name three things you are grateful for today, however small.",
        "Who did something kind for you recently, and how did it feel?",
        "What part of your routine do you secretly enjoy?",
    ],
    "reflection": [
        "What pattern from this week would you like to understand better?",
        "When did you feel most like yourself today?",
        "What would you tell last-week-you about this moment?",
    ],
    "body": [
        "Where is tension hiding in your body right now?",
        "Describe your posture and breath without trying to change them.",
        "What did your body ask for today that you listened to — or ignored?",
    ],
    "connection": [
        "Who made you feel seen this week, and how?",
        "Is there a conversation you've been avoiding? What holds you back?",
        "How did you show care for someone else today?",
    ],
    "growth": [
        "What small risk did you take recently, and what happened?",
        "Name one belief you held a year ago that has shifted.",
        "What skill or quality are you quietly developing?",
    ],
}


def get_prompt(category: str | None = None) -> tuple[str, str]:
    """Return a (prompt, category) tuple. Random from *category* or all."""
    if category is not None:
        if category not in PROMPTS:
            raise ValueError(f"Unknown category: {category!r}. Valid: {list(PROMPTS)}")
        return random.choice(PROMPTS[category]), category
    cat = random.choice(list(PROMPTS))
    return random.choice(PROMPTS[cat]), cat


def get_daily_prompt() -> tuple[str, str]:
    """Deterministic daily prompt — same result on the same calendar date."""
    today_str = date.today().isoformat()  # e.g. "2026-07-22"
    idx = int.from_bytes(today_str.encode(), "big")
    cats = sorted(PROMPTS)
    cat = cats[idx % len(cats)]
    prompts = PROMPTS[cat]
    prompt = prompts[idx // len(cats) % len(prompts)]
    return prompt, cat


def get_categories() -> list[str]:
    """Return all prompt category names."""
    return list(PROMPTS)


# ---------------------------------------------------------------------------
# Meditation presets
# ---------------------------------------------------------------------------

MEDITATION_PRESETS: list[dict[str, object]] = [
    {"minutes": 5, "label": "5 minutes — a quick reset"},
    {"minutes": 10, "label": "10 minutes — a short sit"},
    {"minutes": 15, "label": "15 minutes — settling in"},
    {"minutes": 20, "label": "20 minutes — a proper session"},
    {"minutes": 30, "label": "30 minutes — deep practice"},
]
