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
| 4 | Character Creation | ✅ Complete |
| 5 | Single-Agent DM Loop | ✅ Complete |
| 6 | Frontend UI | ✅ Complete |
| 7 | NPC Subagents | ✅ Complete |
| 8 | Memory Summarization | ✅ Complete |
| 9 | Additional LLM Providers | ✅ Complete |
| 10 | Platform Startup Scripts | ✅ Complete |

---

## Prerequisites

- **Python 3.10+** — the only hard requirement
- **LLM Provider** — choose one (all are optional, but at least one is needed to play):
  - **Ollama** (local): Install from [ollama.com](https://ollama.com) and pull a model:
    ```bash
    ollama pull llama3.2
    ```
  - **Unsloth** (local, GPU): Install from [unsloth.ai](https://unsloth.ai); runs on `http://localhost:8000`
  - **llama.cpp** (local): Build from [github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp) and run `llama-server`
  - **Groq** (cloud): Sign up at [groq.com](https://groq.com) for an API key
  - **OpenRouter** (cloud): Sign up at [openrouter.ai](https://openrouter.ai) for an API key

No build tools, no compilers, no Node.js, no Docker. Just Python.

---

## Quick Start

The easiest way to get started is with the one-command startup scripts:

**Linux/macOS:**
```bash
./start.sh
```

**Windows:**
```cmd
start.bat
```

These scripts automatically check for Python 3.10+, create a virtual
environment, install dependencies, start the server on port 5000, and open
your browser.

---

If you prefer to do it manually:

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

# 4. Start the game server
python run.py
```

The server starts on `http://localhost:5000`. Open it in your browser to access the UI.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/health` | Check LLM provider connectivity (takes `base_url`, `model`, optional `api_key`) |
| `POST` | `/api/turn` | Process a player turn through the DM agent |
| `GET` | `/api/game/stream` | SSE streaming endpoint for real-time DM narrative |
| `POST` | `/api/save` | Save current world state to disk |
| `GET` | `/api/saves` | List all saved games with metadata |
| `POST` | `/api/load/<name>` | Load a saved game state |
| `POST` | `/api/reset` | Get a fresh default world state |
| `POST` | `/api/character/generate` | Generate a character via DM-assisted creation |
| `POST` | `/api/character/save` | Save a generated character |
| `GET`  | `/api/characters` | List saved characters |
| `POST` | `/api/models` | Fetch available models from a provider (takes `base_url`, `model`, `provider_type`, optional `api_key`) |

---

## Provider Setup

The game connects to any OpenAI-compatible LLM provider. Configure your
provider in the Connection view when you first open the web UI.

### Ollama (Local)

1. Download and install from [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull llama3.2`
3. Start the server: `ollama serve`
4. In the Connection view, set:
   - **Base URL:** `http://localhost:11434`
   - **Model:** `llama3.2`
   - **Provider Type:** `ollama`

### Unsloth (Local, GPU)

1. Install `unsloth` and run: `unsloth studio`
2. In the Connection view, set:
   - **Base URL:** `http://localhost:8000`
   - **Model:** `unsloth/Qwen3-4B-128K-GGUF:UD-Q4_K_XL`
   - **Provider Type:** `unsloth`

### llama.cpp (Local)

1. Build or download from [github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
2. Start the server with a model:
   ```bash
   llama-server -m <path-to-model>
   ```
3. In the Connection view, set:
   - **Base URL:** `http://localhost:8080`
   - **Model:** `default`
   - **Provider Type:** `llamacpp`

### Groq (Cloud)

1. Sign up at [groq.com](https://groq.com) and get an API key
2. In the Connection view, set:
   - **Base URL:** `https://api.groq.com/openai`
   - **Model:** `llama3-70b-8192` (or another Groq model)
   - **API Key:** Your Groq API key
   - **Provider Type:** `groq`

### OpenRouter (Cloud)

1. Sign up at [openrouter.ai](https://openrouter.ai) and get an API key
2. In the Connection view, set:
   - **Base URL:** `https://openrouter.ai/api`
   - **Model:** `mistralai/mistral-7b-instruct:free` (or any OpenRouter model)
   - **API Key:** Your OpenRouter API key
   - **Provider Type:** `openrouter`

---

## How to Play

1. **Open the game** — Navigate to [http://localhost:5000](http://localhost:5000)

2. **Connect to a provider** — The Connection view is shown first. Select your
   LLM provider (Ollama, Groq, OpenRouter, etc.), enter the base URL and model
   name, provide an API key if needed, and choose the correct Provider Type from
   the dropdown. Click **Test Connection** to verify everything works, then
   click **Connect**.

3. **Create a character** — Choose from four classes (Fighter, Rogue, Mage,
   Cleric) using the manual form, or use the **DM-Assisted Creation** for a
   guided Q&A experience. Your character is saved automatically.

4. **Start playing** — The game view shows the narrative area and an input box.
   Type what your character does (e.g., *"I search the room for traps"* or
   *"I talk to the innkeeper"*) and press **Send**. The DM agent narrates the
   story, dice rolls happen automatically, and the world reacts to your choices.

5. **Save and load** — The game auto-saves your progress. You can also use the
   **Save** / **Load** buttons in the UI to manage your saved games.

6. **Explore** — The world is persistent. Your actions affect the story, NPCs
   remember past interactions, and the DM adapts the narrative to your choices.

---

## Project Structure

```
rpg-with-llm/
├── README.md
├── requirements.txt
├── run.py                        # Flask app entry point
├── app/
│   ├── dice/                     # Dice parser, roller, random tables
│   ├── rules/                    # Skill checks, combat, XP, status effects
│   ├── world/                    # World state model, JSON persistence
│   ├── llm/                      # LLM provider abstraction (Ollama, Groq, OpenRouter)
│   ├── character/                # Character model, creation & persistence
│   ├── server.py                 # Flask server, REST + SSE endpoints
│   ├── agents/                  # DM agent, response parser, tool dispatcher, history
│   └── static/                  # Frontend SPA
│       ├── index.html           # SPA shell with 3 views
│       ├── css/
│       │   └── style.css        # Dark fantasy theme
│       └── js/
│           ├── app.js           # SPA router
│           ├── connection.js    # Connection view
│           ├── character.js     # Character creation/load
│           ├── game.js          # Game view (narrative, input, sidebar)
│           └── sse.js           # SSE streaming client
├── data/
│   ├── tables/                   # Encounters, loot, weather, NPC traits
│   └── saves/                    # Saved games (gitignored)
└── tests/                        # Test suite for all modules
```

---

## Tech Stack

| Component | Technology | Minimum Version |
|-----------|-----------|---------|
| Language | Python | 3.10 |
| Web Server | Flask | 3.0 |
| HTTP Client | Requests | 2.31 |
| Testing | Pytest | 8.0 |
| Linting | Ruff | 0.9 |
| Type Checking | Mypy | 1.15 |
| Coverage | pytest-cov | 6.0 |
| LLM API | OpenAI-compatible chat completions | — |
| Frontend | Vanilla HTML + CSS + JS | — |
| Randomness | `random.SystemRandom` (cryptographic) | — |
| Build Step | None | — |

### Provider Support

| Provider | Type | Default Model |
|----------|------|---------------|
| **Ollama** | Local | `llama3.2` |
| **Unsloth** | Local (GPU) | `unsloth/Qwen3-4B-128K-GGUF:UD-Q4_K_XL` |
| **Groq** | Cloud (fast inference) | `llama3-70b-8192` |
| **OpenRouter** | Cloud (model aggregator) | `mistralai/mistral-7b-instruct:free` |
| **llama.cpp** | Local | `default` |

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

# Run tests with coverage
pytest --cov=app --cov-report=term

# Run a specific test file
pytest -v tests/test_dice.py
```

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| "Connection refused" when testing provider | LLM server not running | Start your provider (e.g., `ollama serve`) |
| "Model not found" | Model not pulled locally | Run `ollama pull <model-name>` for Ollama, or check the model name |
| Port 5000 already in use | Another process on that port | Kill the other process, or change the port in `run.py` (or `PORT=5000` in `start.sh` for Linux/macOS users) |
| "No module named X" | Dependencies not installed | Run `pip install -r requirements.txt` in your virtual environment |
| Server won't start | Python 3.9 or older | Check with `python3 --version`; upgrade to Python 3.10+ |
| Browser doesn't open automatically | No `xdg-open` on Linux | Manually navigate to `http://localhost:5000` |
| Strange or incoherent narration | Weak or small LLM model | Try a larger model (e.g., `llama3.2:11b` instead of `llama3.2:3b`) |
| Game feels slow | Underpowered hardware for local LLM | Try a cloud provider (Groq or OpenRouter) for faster inference |
| Script says "Python not found" on Windows | Python not in PATH | Re-run the Python installer and check **"Add Python to PATH"** |
| Virtual environment activation fails | Corrupted `.venv` directory | Delete the `.venv` folder and re-run the startup script |

---

## Design Decisions

- **Character classes:** Fighter, Rogue, Mage, Cleric — sufficient for MVP.
- **Port collision handling:** Auto-increment starting from port 5000 (up to 10 attempts), then display a clear error.
- **Randomness source:** All randomness flows through `app.dice.roller` using `random.SystemRandom`. No other module calls `random` directly.
- **Save file format:** JSON with atomic writes (write to temp, rename). No migration logic for MVP — saves are ephemeral during development.
- **No build step:** Raw HTML/CSS/JS on the frontend. No webpack, no npm, no node_modules.

---

## Credits

This game is being **developed by goblins** 🧌 — a horde of persona-driven AI agents under the command of the Goblin Chief. Each agent has its own role, personality, and specialty (implementer, tester, reviewer, researcher, planner, mascot).

The persona-agents system used to orchestrate this horde can be found at:
👉 [github.com/las-pinter/persona-agents](https://github.com/las-pinter/persona-agents)

## License

MIT License. See [LICENSE](LICENSE) for full text.
