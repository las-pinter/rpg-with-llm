# LLM-Powered RPG

## Setup commands
- Install deps: `pip install -r requirements.txt`
- Run all tests: `python3 -m pytest tests/ -v`
- Run tests with coverage: `python3 -m pytest tests/ --cov=app --cov-report=term`
- Run lint check: `ruff check app/ tests/`
- Run format check: `ruff format --check app/ tests/`
- Run type check: `mypy app/ --ignore-missing-imports`
- Run full pre-commit check: `ruff check app/ tests/ && ruff format --check app/ tests/ && python3 -m pytest tests/ --cov=app --cov-fail-under=60`
- Run single module: `python3 -m pytest tests/test_dice.py -v`
- Run game: `python3 run.py` (starts Flask dev server on port 5000)

## Project overview
Python-based LLM-powered RPG game. Phases 1-8 complete (dice, rules, tables, LLM provider abstraction with health endpoint, world state persistence, character creation, single-agent DM loop with game endpoints, frontend SPA with SSE streaming, NPC subagents with parallel spawning, memory summarization). Phases 1-9 complete (dice, rules, tables, all LLM providers including Ollama/Groq/OpenRouter/Unsloth/llama.cpp with multi-provider per-agent config, world state persistence, character creation, single-agent DM loop with game endpoints, frontend SPA with SSE streaming, NPC subagents with parallel spawning, memory summarization, and provider model list fetching). Flask server running at `http://localhost:5000`. Phase 10 (startup scripts) upcoming. CI pipeline enforces lint, format, type checking, and test coverage.

## Code conventions
- Python 3.10+ type hints on all function signatures and dataclass fields
- All randomness flows through `app.dice.roller.roll()` — never call `random` directly
- Return structured dicts from public functions, never print to stdout
- Use `pathlib.Path` for cross-platform paths; avoid hardcoded `/` or `\\`
- Dataclasses with `@dataclass` and `field(default_factory=...)` for mutable defaults
- Atomic file writes: write to `.tmp`, then `os.rename()` to final path
- Use `from __future__ import annotations` at top of files
- Maximum line length: 88 characters (enforced by Ruff)

## Testing & quality standards
- Every module has a `tests/test_<module>.py` file
- Tests use `pytest` framework with `pytest.raises` for error cases
- New code MUST include tests; never drop coverage below existing levels
- Run full suite before committing: `ruff check app/ tests/ && ruff format --check app/ tests/ && python3 -m pytest tests/ --cov=app --cov-fail-under=60`
- Minimum coverage threshold: 60%

## Project structure
```
app/
├── dice/       — Parser, roller, random tables
├── rules/      — Checks, combat, XP, status effects
├── world/      — State model, JSON persistence
├── llm/        — Provider abstraction (Ollama, Groq, OpenRouter)
├── character/  — Character model, creation & persistence
├── agents/     — DM agent, response parser, tool dispatcher, turn history
└── static/     — Frontend SPA
    ├── index.html       # SPA shell
    ├── css/
    │   └── style.css    # Dark fantasy theme
    └── js/
        ├── app.js       # SPA router
        ├── connection.js# Connection view
        ├── character.js # Character creation/load
        ├── game.js      # Game view
        └── sse.js       # SSE streaming client
data/tables/    — Encounters, loot, weather, NPC traits
tests/          — Test suite mirroring app structure
```

## Important constraints
- No build step: frontend is raw HTML/CSS/JS served from Flask
- This is a proof of concept, not meant to replace human-led RPGs
- License: MIT
