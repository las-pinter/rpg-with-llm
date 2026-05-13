# LLM-Powered RPG

## Setup commands
- Install deps: `pip install -r requirements.txt`
- Run all tests: `python3 -m pytest tests/ -v`
- Run single module: `python3 -m pytest tests/test_dice.py -v`
- Run game: `python3 run.py` (once Flask server is implemented)

## Project overview
Python-based LLM-powered RPG game. Deterministic engine layers (dice, rules, tables, world state) are complete. LLM provider abstraction (Ollama) is complete. Agent system, frontend, and startup scripts are upcoming phases.

## Code conventions
- Python 3.10+ type hints on all function signatures and dataclass fields
- All randomness flows through `app.dice.roller.roll()` — never call `random` directly
- Return structured dicts from public functions, never print to stdout
- Use `pathlib.Path` for cross-platform paths; avoid hardcoded `/` or `\\`
- Dataclasses with `@dataclass` and `field(default_factory=...)` for mutable defaults
- Atomic file writes: write to `.tmp`, then `os.rename()` to final path
- Use `from __future__ import annotations` at top of files

## Testing standards
- Every module has a `tests/test_<module>.py` file
- Tests use `pytest` framework with `pytest.raises` for error cases
- New code MUST include tests; never drop coverage below existing levels
- Run full suite before committing: `python3 -m pytest tests/`

## Project structure
```
app/
├── dice/     — parser.py, roller.py, tables.py
├── rules/    — checks.py, combat.py, xp.py, status.py
├── world/    — model.py, persistence.py
├── llm/      — base.py, ollama.py, config.py
├── character/  (planned)
├── agents/     (planned)
└── static/     (planned)
data/tables/  — encounters.json, loot.json, weather.json, npc_traits.json
tests/        — test_*.py files mirroring app structure
```

## Important constraints
- No build step: frontend is raw HTML/CSS/JS served from Flask
- This is a proof of concept, not meant to replace human-led RPGs
- License: MIT
