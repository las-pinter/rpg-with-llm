# LLM-Powered RPG Game

A local-first, browser-based single-player RPG powered by LLMs. Features a Dungeon Master agent, deterministic dice/rules engine, persistent world state, streaming narrative, and NPC subagents — all running locally with no build step.

Built entirely in Python, the game connects to any OpenAI-compatible LLM provider (Ollama, Groq, OpenRouter) to drive dynamic storytelling while a deterministic engine handles dice rolls, skill checks, combat, and rules enforcement. No JavaScript build tools, no external game engines, no cloud dependencies.

> **⚠️ Proof of Concept:** This project is an experimental prototype exploring LLM-driven game mechanics. It is **not** intended to replace tabletop RPGs, human game masters, or traditional roleplaying experiences with real people. The randomness, nuance, and creativity of human-led games cannot—and should not—be replicated by software.

---

## Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Deterministic Tools | ✅ Complete |
| 2 | LLM Provider Abstraction | ✅ Complete |
| 3 | World State Persistence | ✅ Complete |
| 4 | Character Creation | ⬜ Not started |
| 5 | Single-Agent DM Loop | ⬜ Not started |
| 6 | Frontend UI | ⬜ Not started |
| 7 | NPC Subagents | ⬜ Not started |
| 8 | Memory Summarization | ⬜ Not started |
| 9 | Additional LLM Providers | ⬜ Not started |
| 10 | Platform Startup Scripts | ⬜ Not started |

---

## Prerequisites

- **Python 3.10+** — the only hard requirement
- **Ollama** (optional) — for running LLMs locally; install from [ollama.ai](https://ollama.ai) and pull a model:
  ```bash
  ollama pull llama3.2
  ```
- **Groq / OpenRouter** (optional) — cloud provider alternatives; requires an API key

No build tools, no compilers, no Node.js, no Docker. Just Python.

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url> rpg-with-llm
cd rpg-with-llm

# 2. (Recommended) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the game (once the Flask server is implemented)
python run.py
```

> **Note:** The Flask server, frontend, and startup scripts are in Phases 5–10. For now, the project provides the core engine libraries and can be used programmatically or tested via `pytest`.

---

## Project Structure

```
rpg-with-llm/
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── run.py                        # Main entry point (Flask app launch)
├── app/
│   ├── __init__.py
│   ├── dice/
│   │   ├── __init__.py
│   │   ├── parser.py             # Dice notation parser (2d6+3, d20 adv, 4d6k3)
│   │   ├── roller.py             # Dice engine with audit trail
│   │   └── tables.py             # Random encounter/loot/NPC tables
│   ├── rules/
│   │   ├── __init__.py
│   │   ├── checks.py             # Skill checks, saving throws, DCs
│   │   ├── combat.py             # Combat resolution, damage, AC
│   │   ├── xp.py                 # XP awards and leveling
│   │   └── status.py             # Status effects, conditions
│   ├── world/
│   │   ├── __init__.py
│   │   ├── model.py              # World state data model (dataclasses)
│   │   └── persistence.py        # JSON file save/load with atomic writes
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract provider (call, stream, health)
│   │   ├── ollama.py             # Ollama provider implementation
│   │   └── config.py             # Provider configuration management
│   ├── character/                # (Phase 4)
│   ├── agents/                   # (Phase 5, 7)
│   └── static/                   # (Phase 6)
├── data/
│   ├── tables/
│   │   ├── encounters.json       # Encounter tables
│   │   ├── loot.json             # Loot tables
│   │   ├── weather.json          # Weather tables
│   │   └── npc_traits.json       # NPC trait tables
│   └── saves/                    # Saved game files (gitignored)
└── tests/
    ├── test_dice.py              # Dice parser + roller tests
    ├── test_rules.py             # Rules engine tests
    ├── test_tables.py            # Random tables tests
    ├── test_world.py             # World state model tests
    ├── test_persistence.py       # World state persistence tests
    ├── test_llm.py               # LLM provider abstraction tests
    └── test_config.py            # Provider config management tests
```

See the plan document for detailed task breakdown.

---

## Tech Stack

| Component | Technology | Minimum Version |
|-----------|-----------|---------|
| Language | Python | 3.10 |
| Web Server | Flask | 3.0 |
| HTTP Client | Requests | 2.31 |
| Testing | Pytest | 8.0 |
| LLM API | OpenAI-compatible chat completions | — |
| Frontend | Vanilla HTML + CSS + JS | — |
| Randomness | `random.SystemRandom` (cryptographic) | — |
| Build Step | None | — |

### Provider Support

| Provider | Type | Default Model |
|----------|------|---------------|
| **Ollama** | Local | `llama3.2` |
| **Groq** | Cloud (fast inference) | `llama3-70b-8192` |
| **OpenRouter** | Cloud (model aggregator) | `mistralai/mistral-7b-instruct:free` |

---

## Architecture Overview

```
Browser (SPA)
  ├── Connection View
  ├── Character Create/Load
  └── Game View (Narrative + Input)
        │ SSE / REST API
Flask Server
  ├── Health Endpoint
  ├── Turn/Game Endpoints
  └── Save/Load/Reset Endpoints
        │
Game Engine
  ├── DM Agent (long-lived)
  ├── NPC Agents (ephemeral)
  └── Summarizer (compression)
        │
  ├── Deterministic Layer
  │     ├── Dice Roller
  │     ├── Tables (JSON)
  │     ├── Rules Engine
  │     └── World State (JSON File)
  └── LLM Provider Layer
        ├── Ollama
        ├── Groq
        └── OpenRouter
```

---

## Running Tests

```bash
# Run all tests
pytest -v

# Run tests for a specific module
pytest -v tests/test_dice.py
pytest -v tests/test_rules.py
pytest -v tests/test_llm.py
pytest -v tests/test_world.py
```

---

## Design Decisions

- **Character classes:** Fighter, Rogue, Mage, Cleric — sufficient for MVP.
- **Port collision handling:** Auto-increment starting from port 5000 (up to 10 attempts), then display a clear error.
- **Randomness source:** All randomness flows through `app.dice.roller` using `random.SystemRandom`. No other module calls `random` directly.
- **Save file format:** JSON with atomic writes (write to temp, rename). No migration logic for MVP — saves are ephemeral during development.
- **No build step:** Raw HTML/CSS/JS on the frontend. No webpack, no npm, no node_modules.

---

## License

MIT License. See [LICENSE](LICENSE) for full text.
