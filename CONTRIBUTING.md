# Contributing to Speculae

Speculae is open source. We welcome contributions of all kinds.

---

## Ways to Contribute

### Wellness Features

Add a breathing exercise, yoga sequence, or meditation timer. The wellness library is designed to be extended — each exercise is a self-contained module.

### Pattern Detectors

Improve existing detectors or add new ones. The pattern system is plugin-based — each detector takes entries and returns observations.

### Agent Integration

Build integrations with agent frameworks, memory systems, or visualization tools. The agent API is the same as the human API — same data format, same endpoints.

### Documentation

Fix typos, improve explanations, add examples. Good documentation is how people discover Speculae.

### Bug Reports

Open an issue with steps to reproduce. Include your OS, Python version, and `speculae config` output.

---

## Development Setup

```bash
git clone https://github.com/0x923041-dotcom/Speculae
cd Speculae
pip install -e ".[dev]"
pytest -q
```

### Code Style

- Line length: 100 (enforced by ruff)
- Python 3.10+ (match statements, type hints)
- No external services in core (SQLite only)
- All pattern detectors must work offline

### Testing

```bash
pytest -q                    # run all tests
pytest tests/test_patterns.py  # run pattern tests only
```

Tests must run without network access. Mock external services.

---

## Pull Requests

1. Fork the repo
2. Create a branch (`git checkout -b feature/my-feature`)
3. Add tests for new functionality
4. Ensure `pytest -q` passes
5. Open a PR with a clear description

### What We Look For

- Does it respect the local-first philosophy?
- Does it add value without adding complexity?
- Does it work offline?
- Is it documented?
