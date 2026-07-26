# Pattern detection

Speculae runs five detectors over your entry history. All are local — no API, no network. The goal of every detector is the same: surface an observation without drawing a conclusion.

---

## Arc detection

**"Your mood has been trending downward for 6 days."**

Fits a linear regression over the last `arc_window_days` of mood and energy scores. Flags the trend if:
- The absolute slope is at least `arc_threshold` (mood points per day)
- The p-value is ≤ 0.15 (suggestive, not strict — low-frequency data)

Severity:
- `significant` — downward with magnitude > 1.5 points over the window
- `notable` — downward with magnitude 0.5–1.5 points
- `info` — upward trend

Upward trends are noted gently. Downward ones are flagged more prominently — a consistent dip over days is worth your attention even if the individual data points felt small.

---

## Trigger detection

**"Days tagged 'work-call' tend to be followed by lower mood."**

For each tag, measures the average mood change on the day *following* an entry with that tag. Surfaces a trigger if:
- The tag appears at least 3 times alongside a mood-logged next day
- The average next-day mood delta is −0.5 or lower

Severity:
- `significant` — average delta < −1.0
- `notable` — average delta −0.5 to −1.0

The key phrase in the pattern description: *"not necessarily a cause, just a correlation."* This is intentional. The detector cannot know causality. It shows you a repeated association and lets you decide what it means.

---

## Cycle detection

**"Your mood follows a roughly 9-day rhythm."**

Computes autocorrelation of the mood series for all lags in `[cycle_min_period_days, cycle_max_period_days]`. Flags the dominant period if the peak autocorrelation exceeds 0.35.

Severity:
- `significant` — autocorrelation > 0.55
- `notable` — 0.35–0.55

Requires at least `2 × min_entries_for_patterns` entries (default: 14). Mood series must have at least 14 data points.

Cycles often reflect sleep rhythms, hormonal cycles, or social patterns. Naming them is the first step to working *with* them.

---

## Blindspot detection

**"You haven't written about 'M.' in 18 days. That's unusual."**

For each tag that has appeared ≥ 3 times, computes the average interval between appearances. If the current silence is greater than `blindspot_multiplier × avg_interval`, surfaces a blindspot.

Severity:
- `notable` — silence > 3× average interval
- `info` — silence > blindspot_multiplier × average interval

This is the most personal detector. It notices what's gone quiet without knowing *why* — which is exactly the point. Sometimes a topic disappears because things are better. Sometimes because they're avoided. The detector doesn't know. You do.

---

## Day-of-week variance

**"Sundays average 0.9 points below your weekly mean (p = 0.04)."**

Runs a one-way ANOVA across seven day-of-week groups. If the overall F-test is significant (p ≤ 0.1) and the worst single day is at least 0.4 points below the overall mean, surfaces the pattern.

Severity:
- `notable` — delta < −0.8
- `info` — delta −0.4 to −0.8

This might reflect your work schedule, social rhythm, or something structural you haven't named yet.

---

## What patterns won't do

- **Diagnose.** No clinical language, no labels.
- **Prescribe.** No "you should." The closest the system gets is: *"here's what I noticed. Does this match your experience?"*
- **Alarm.** No push notifications, no badges. Patterns are available when you ask for them.
- **Leak.** All pattern computation happens locally. No entry text is sent anywhere.
