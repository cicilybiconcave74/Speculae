# Changelog

All notable changes to Speculae will be documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Speculae uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-07-22

### Added — Initial Public Release

- **Local-first journaling sanctuary** — Markdown editor with split-view live preview, toolbar, mood and energy tracking (1–5 scales), image attachments with lightbox, starred entries (☆/★), and advanced search.
- **Natively multi-agentic architecture** — Shared schema, agent identity tracking (`agent_id`), fleet context switching in Web UI and CLI, and per-agent pattern detection.
- **Emotional pattern detection** — Five automated detectors: Emotional Arc (trend over configurable window), Trigger Correlation (tag → next-day mood delta), Cycle Detection (autocorrelation of mood series), Blindspot Flagging (gone-quiet topics), and Day-of-Week Variance.
- **Wellness companion** — Guided breathing exercises (box, 4-7-8, coherent, physiological sigh) with animated circle guide, customizable meditation timer with Web Audio API ambient sounds, and 18 journaling prompts across 6 categories with daily prompt rotation.
- **AI insight interpreting engine** — Weekly mirror report interpreting statistics and detected patterns; optional local-only LLM narrative (BYOAK — supports OpenAI and Google Gemini).
- **Themes & UI polish** — Four built-in themes (Dark, Light, Aqua & Gold, High Contrast), Focus Mode (distraction-free full-screen writing), keyboard navigation, and font size scaling.
- **Desktop application** — Native Windows x64 desktop installer built via Tauri v2 with WebView2 integration.
- **CLI & REST API** — Full command-line interface (`speculae write`, `read`, `list`, `search`, `patterns`, `insights`, `breathe`, `meditate`, `prompt`, `agents`, `export`, `import`) and 38+ local REST API endpoints.
- **Export & Import** — Full data portability in JSON, Markdown, and standalone HTML formats with dry-run and overwrite modes.
- **Privacy & Security** — 100% local storage via SQLite FTS5 with WAL mode. Zero cloud sync, zero telemetry, zero external network calls required.
