# Wellness Features

Speculae is a wellness companion, not just a journal. The wellness library sits alongside your journal entries so you can move from reflection to action without leaving the app.

---

## Breathing Exercises

Guided breathing with visual animations. All breathing exercises run locally — no network, no tracking.

### Available Exercises

| Exercise | Pattern | Cycles | Best For |
|----------|---------|--------|----------|
| **Box Breathing** | 4s in, 4s hold, 4s out, 4s hold | 4 | Calming the nervous system |
| **4-7-8** | 4s in, 7s hold, 8s out | 4 | Falling asleep, acute anxiety |
| **Coherent Breathing** | 5s in, 5s out | 10 | Heart rate variability |
| **Physiological Sigh** | 2s in, 1s top-up, 6s out | 5 | Fastest known calm-down |

### How to Use

**Web UI:**
1. Click **Breathe** in the sidebar
2. Choose an exercise from the dropdown
3. Click **Start**
4. Follow the expanding/contracting circle animation
5. Cycle counter tracks your progress

**CLI:**
```bash
speculae breathe                     # box breathing (default)
speculae breathe --exercise 4-7-8    # 4-7-8 breathing
speculae breathe --exercise coherent # coherent breathing
speculae breathe --exercise physiological-sigh  # physiological sigh
```

**API:**
```
GET /api/wellness/breathing          # list all exercises
GET /api/wellness/breathing/box      # get exercise details
```

---

## Meditation Timer

Simple, beautiful meditation timer with ambient sounds.

### Features

- **Duration presets:** 5, 10, 15, 20, 30 minutes
- **Visual countdown:** SVG circular progress ring
- **Ambient sound:** White noise via Web Audio API (lowpass filtered at 400Hz)
- **Ctrl+C to end early**

### How to Use

**Web UI:**
1. Click **Meditate** in the sidebar
2. Pick a duration
3. Click **Start**
4. The circular timer counts down with a progress ring
5. Toggle ambient sound for background noise

**CLI:**
```bash
speculae meditate                 # 10 minutes (default)
speculae meditate --minutes 5     # 5-minute timer
speculae meditate --minutes 20    # 20-minute timer
```

**API:**
```
GET /api/wellness/meditation/presets   # list duration options
```

---

## Journaling Prompts

Gentle questions for when you don't know what to write. Not forced — always optional.

### Prompt Categories

| Category | Example |
|----------|---------|
| **Check-in** | "How are you arriving today? What's the first thing you notice?" |
| **Gratitude** | "What small thing went right today that you almost missed?" |
| **Reflection** | "What would you tell yourself a week ago about this moment?" |
| **Body** | "Where are you holding tension right now? Can you breathe into it?" |
| **Connection** | "Who have you been thinking about but haven't reached out to?" |
| **Growth** | "What's one thing you understand now that you didn't a month ago?" |

18 prompts total (3 per category). Prompts rotate daily.

### How to Use

**Web UI:**
- The dashboard shows today's prompt in the Quote widget
- Click "Give me another" for a random prompt
- The Write view shows today's prompt at the top

**CLI:**
```bash
speculae prompt                         # random prompt
speculae prompt --category gratitude    # specific category
speculae prompt --daily                 # today's deterministic prompt
```

**API:**
```
GET /api/wellness/prompt                # random prompt
GET /api/wellness/prompt?category=gratitude  # by category
GET /api/wellness/prompt/daily          # today's prompt
```

---

## What's Planned (Not Yet Built)

### Yoga Sequences
Guided yoga with visual pose cards. From 5-minute desk stretches to 30-minute flows.

### Session Logging
Link wellness activities to journal entries for pattern detection: *which activities help you most?*

### Custom Breathing Patterns
Define your own inhale/hold/exhale durations.

### Interval Bells
Ring bells at set intervals during meditation.

### Audio Cues
Optional sound cues during breathing exercises.

---

## What Wellness Features Won't Do

- **Diagnose.** No clinical language, no labels, no DSM references.
- **Prescribe.** No "you should do this." Only: "here's what's available."
- **Track for tracking's sake.** Every feature serves the journal, not a dashboard.
- **Replace a teacher.** Yoga sequences are basic. A real teacher is better.
- **Require network.** Everything runs locally. Every sound is generated via Web Audio API.
