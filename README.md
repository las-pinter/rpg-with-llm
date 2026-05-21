# 🧙 LLM-Powered RPG

**A browser-based, single-player RPG where an AI Dungeon Master runs the show.**

Talk to innkeepers, loot dungeons, slay monsters — all driven by an LLM
storyteller with a real dice engine underneath. No human GM required.
No setup fuss. Just you, a browser, and an adventure.

> ⚠️ **Experimental Prototype:** This is a proof of concept exploring what
> LLM-driven games can look like. It's meant for curious tinkerers and
> solo adventurers — not a replacement for tabletop RPGs or human GMs.

---

## 🚀 Quick Start

The fastest way to get playing is with the one-click startup scripts.
You just need **Python 3.10+** and an **LLM provider** (see below).

**Linux/macOS:**
```bash
./start.sh
```

**Windows:**
```cmd
start.bat
```

That's it. The script checks your Python version, creates a virtual
environment, installs everything, fires up the server on **port 5000**,
and opens your browser for you.

---

### Manual Setup (if you like doing things the hard way)

```bash
# 1. Grab the code
git clone <repo-url> rpg-with-llm
cd rpg-with-llm

# 2. Set up a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate       # Linux/macOS
# .venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python run.py
```

Then open **http://localhost:5000** in your browser and the adventure begins!

---

## 🔌 LLM Provider Setup

The game needs an LLM (Large Language Model) to act as your Dungeon Master.
You have options — run one locally on your machine, or use a cloud service
for faster responses.

### Ollama (Local — Easiest)

1. Download and install from [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull llama3.2`
3. Start the server: `ollama serve`
4. In the game's **Connection** screen, set:
   - **Base URL:** `http://localhost:11434`
   - **Model:** `llama3.2`
   - **Type:** `ollama`

### llama.cpp (Local)

1. Build or download from [github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
2. Start the server: `llama-server -m <path-to-your-model>`
3. In the **Connection** screen, set:
   - **Base URL:** `http://localhost:8080`
   - **Model:** `default`
   - **Type:** `llamacpp`

### Unsloth (Local, GPU)

1. Install `unsloth` and run: `unsloth studio`
2. In the **Connection** screen, set:
   - **Base URL:** `http://localhost:8000`
   - **Model:** `unsloth/Qwen3-4B-128K-GGUF:UD-Q4_K_XL`
   - **Type:** `unsloth`

### Groq (Cloud — Fast)

1. Sign up at [groq.com](https://groq.com) and grab an API key
2. In the **Connection** screen, set:
   - **Base URL:** `https://api.groq.com/openai`
   - **Model:** `llama3-70b-8192` (or pick another Groq model)
   - **API Key:** Your Groq key
   - **Type:** `groq`

### OpenRouter (Cloud — Many Models)

1. Sign up at [openrouter.ai](https://openrouter.ai) and get an API key
2. In the **Connection** screen, set:
   - **Base URL:** `https://openrouter.ai/api`
   - **Model:** `mistralai/mistral-7b-instruct:free` (or any OpenRouter model)
   - **API Key:** Your OpenRouter key
   - **Type:** `openrouter`

---

**Pro tip:** Click **Test Connection** in the UI to make sure everything's
talking before you dive in. Saves a lot of head-scratching!

---

## 🎮 How to Play

### 1. Connect
Open your browser to **http://localhost:5000**. The first screen asks you
to connect to your LLM provider. Fill in the details from the setup guide
above, hit **Test Connection**, then **Start Adventure**.

### 2. Create Your Hero
Choose your class — **Fighter**, **Rogue**, **Mage**, or **Cleric** —
and roll up your stats. You can use the manual form or try the
**DM-Assisted Creation** for a guided Q&A session that builds your
character through conversation. Your hero gets saved automatically.

### 3. Adventure!
The game view shows you the world through the DM's narration. At the
bottom there's an input box. Type what you want your character to do:

> *"I search the room for traps"*
>
> *"I introduce myself to the innkeeper"*
>
> *"I draw my sword and demand they surrender!"*

The DM responds, dice are rolled behind the scenes, and the story moves
forward based on your choices. The world remembers what you've done —
NPCs recall past conversations, locations stay changed, and your actions
have consequences.

### 4. Save & Load
The game auto-saves as you go. You can also hit **Save** or **Load**
in the UI anytime to manage your adventures.

### 5. Explore!
The world is persistent. Visit a town, clear a dungeon, accept a quest,
get cursed by a witch — every decision matters. The DM adapts the story
to whatever you throw at it.

---

## ❓ Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Connection refused" | LLM provider isn't running | Start your provider (e.g., `ollama serve`) |
| "Model not found" | Model not downloaded | Run `ollama pull <model-name>` or check the name |
| Port 5000 already in use | Another program is using it | Kill the other program, or set `PORT=5000` in `start.sh` (Linux/macOS) |
| "No module named X" | Dependencies not installed | Run `pip install -r requirements.txt` in your virtual environment |
| Server won't start | Python too old | Run `python3 --version` — needs **3.10+** |
| Browser doesn't open | Missing `xdg-open` on Linux | Manually go to **http://localhost:5000** |
| Weird/boring narration | Small or weak model | Try a bigger one (e.g., `llama3.2:11b` instead of `llama3.2:3b`) |
| Game feels sluggish | Local model too heavy for your hardware | Switch to a cloud provider (Groq or OpenRouter) |
| "Python not found" on Windows | Python not in PATH | Re-run the Python installer and check **"Add Python to PATH"** |
| Virtual environment broken | Corrupted `.venv` | Delete the `.venv` folder and re-run the startup script |

---

## 🛠 Need More Help?

If you're stuck or something's broken, check the issues page or open a
new one. Goblin-made, but we try our best!

---

## 🧌 Made by Goblins

Crafted by **Bossnik's Goblin Horde** under the Dark One's command, powered by
the **[Persona Agents](https://github.com/las-pinter/persona-agents)** framework.

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for the fine print.
