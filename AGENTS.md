# LLM-Powered RPG

## Setup commands
- Install deps: `pip install -r requirements.txt`
- Install frontend deps: `npm install` (in `client/`)
- Build frontend: `npm run build` (in `client/`)
- Run all tests: `python3 -m pytest tests/ -v`
- Run tests with coverage: `python3 -m pytest tests/ --cov=app --cov-report=term`
- Run lint check: `ruff check app/ tests/`
- Run format check: `ruff format --check app/ tests/`
- Run Python type check: `mypy app/ --ignore-missing-imports`
- Run TypeScript type check: `npx tsc --noEmit` (in `client/`)
- Run frontend tests: `npx vitest run` (in `client/`)
- Run full pre-commit check: `ruff check app/ tests/ && ruff format --check app/ tests/ && python3 -m pytest tests/ --cov=app --cov-fail-under=60`
- Run game: `python3 run.py` (starts Flask dev server on port 5000)
- Run single module: `python3 -m pytest tests/test_dice.py -v`

## Project overview
Python-based LLM-powered RPG game. Phases 1-8 complete (dice, rules, tables, LLM provider abstraction with health endpoint, world state persistence, character creation, single-agent DM loop with game endpoints, frontend SPA with SSE streaming, NPC subagents with parallel spawning, memory summarization). Phases 1-10 complete (dice, rules, tables, all LLM providers including Ollama/Groq/OpenRouter/Unsloth/llama.cpp with multi-provider per-agent config, world state persistence, character creation, single-agent DM loop with game endpoints, frontend SPA with SSE streaming, NPC subagents with parallel spawning, memory summarization, provider model list fetching, and cross-platform startup scripts). Flask server running at `http://localhost:5000`. CI pipeline enforces lint, format, type checking, and test coverage.

## Code conventions
- Python 3.10+ type hints on all function signatures and dataclass fields
- All randomness flows through `app.dice.roller.roll()` — never call `random` directly
- Return structured dicts from public functions, never print to stdout
- Use `pathlib.Path` for cross-platform paths; avoid hardcoded `/` or `\\`
- Dataclasses with `@dataclass` and `field(default_factory=...)` for mutable defaults
- Atomic file writes: write to `.tmp`, then `os.rename()` to final path
- Use `from __future__ import annotations` at top of files
- Maximum line length: 88 characters (enforced by Ruff)

## Commit naming conventions
- Use the `type: description` format (e.g., `fix:`, `feat:`, `refactor:`, `docs:`, `test:`)
- First line is a short summary (max 72 chars) describing WHAT changed, not the ticket number
- Body (after blank line) explains WHY the change was made, not how
- Bad: `fix: Bug 1 — toggle CSS specificity conflict`
- Good: `fix: toggle label text hidden behind slider due to CSS specificity conflict`
- Use imperative mood: "fix" not "fixed", "add" not "added"
- Keep it descriptive enough that someone reading `git log --oneline` understands the change

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
└── static/     — Static assets (CSS served by Flask)
    └── css/
        └── style.css    # Dark fantasy theme
client/         — React SPA frontend
├── package.json
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── main.tsx              # React entry point
    ├── App.tsx               # Router setup
    ├── api/                  # Backend client
    ├── stores/               # Zustand stores
    ├── hooks/                # Custom hooks
    ├── components/           # React components
    ├── pages/                # Page components
    ├── styles/               # CSS modules
    └── test/                 # Test setup
data/tables/    — Encounters, loot, weather, NPC traits
tests/          — Test suite mirroring app structure
```

## Important constraints
- Frontend is a React SPA in `client/`: run `npm run build` (in `client/`) after changes
- This is a proof of concept, not meant to replace human-led RPGs
- License: MIT
