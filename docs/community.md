# Community

How to get involved with Speculae.

---

## Where to talk

### GitHub Discussions

The primary place for questions, ideas, and conversation:

**[github.com/0x923041-dotcom/Speculae/discussions](https://github.com/0x923041-dotcom/Speculae/discussions)**

Discussion categories:

| Category | Use it for |
|----------|-----------|
| **Q&A** | Questions about usage, setup, the API |
| **Ideas** | Feature suggestions, roadmap feedback |
| **Show and tell** | Share what you built with Speculae |
| **Agent integrations** | Sharing agent frameworks and workflows |
| **Wellness** | Breathing exercises, prompts, meditation ideas |

### GitHub Issues

Use issues for:
- **Bug reports** — something is broken
- **Feature requests** — something should exist
- **Agent integration problems** — specific to using Speculae with AI frameworks

Use the issue templates — they help diagnose faster.

---

## Contributing code

See [developer-guide.md](developer-guide.md) for the full setup guide. Short version:

```bash
git clone https://github.com/0x923041-dotcom/Speculae
cd Speculae
pip install -e ".[dev]"
pytest -q   # confirm 139 tests pass
```

Open a PR when you're ready. The PR template has a checklist — the main things are:
- All tests pass
- New functionality has tests
- `ruff check` is clean

We merge PRs that add clear value without adding unnecessary complexity.

---

## What we welcome

### Wellness features

New breathing exercises, journaling prompt categories, or meditation presets. These are small, self-contained additions with a clear benefit.

**Breathing exercise:** A new entry in `wellness.py`'s `_EXERCISES` dict with a name, description, and phase pattern.

**Journaling prompts:** New prompts added to existing categories in `PROMPTS`, or a new category. Guidelines: open-ended, body-grounded where possible, no prescriptions.

### Pattern detectors

New statistical detectors over journal history. Must run offline, phrase observations as questions, and avoid clinical language. See [developer-guide.md](developer-guide.md#adding-a-pattern-detector).

### Agent integrations

Example code, SDK wrappers, or integrations with agent frameworks. These can live in a `contrib/` directory or as GitHub Discussions posts.

### Documentation

Typos, unclear explanations, missing examples, better walkthroughs. Documentation PRs are always welcome.

### Bug fixes

Especially welcome: regression tests that demonstrate the bug before the fix.

---

## What we don't build

A few things are out of scope by design:

- **Cloud sync.** Speculae is local-first. Files, Syncthing, and rsync exist for a reason.
- **Subscriptions or accounts.** The software is the product.
- **Analytics or telemetry.** Zero, always.
- **Social features.** Private space means private space.
- **AI that reads your raw entries.** Pattern detection uses statistics. LLM insights use a stats summary. Raw text stays on your machine.

If a proposed feature requires any of these, it won't be merged.

---

## Code of conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

In short: be kind and precise. Disagree on substance, not on people.
Wellness tools serve people in vulnerable moments. Hold that lightly.

---

## Reporting security issues

Do not open a public issue for security vulnerabilities. Email the maintainer directly (see GitHub profile). We aim to respond within 48 hours.


