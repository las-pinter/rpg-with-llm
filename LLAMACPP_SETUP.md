# llama.cpp Setup Guide — Running the RPG with a Local LLM

> **Grubnik sez:** This guide'll get you from zero to telling stories with a local
> brain in your machine. No cloud credits, no API keys, no funny business. Just
> you, your GPU (or CPU, we don't judge), and a GGUF file.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Installing llama.cpp](#2-installing-llamacpp)
3. [Downloading a Model](#3-downloading-a-model)
4. [Starting llama-server](#4-starting-llama-server)
5. [Understanding the Flags](#5-understanding-the-flags)
6. [Setting Up the RPG Application](#6-setting-up-the-rpg-application)
7. [Configuring the RPG to Use llama.cpp](#7-configuring-the-rpg-to-use-llamacpp)
8. [Advanced: Multi-Agent Configuration](#8-advanced-multi-agent-configuration)
9. [Troubleshooting](#9-troubleshooting)
10. [Performance Tips](#10-performance-tips)

---

## 1. Prerequisites

Before we start hammering things together, make sure you've got these bits:

| Requirement | Minimum Version | Why You Need It |
|---|---|---|
| **Python** | 3.10+ | Runs the Flask RPG server |
| **Node.js** | 18+ | Compiles the TypeScript frontend |
| **npm** | 9+ (ships with Node) | Installs frontend dependencies |
| **llama.cpp** | Latest (bleeding edge recommended) | Hosts the local LLM |
| **A GGUF model file** | Any size your hardware can stomach | The actual brain |

> On Linux you'll also want `cmake`, `make`, and a C++ compiler (`gcc` or `clang`).
> On Windows you'll want either Visual Studio Build Tools or the pre-built binaries.

---

## 2. Installing llama.cpp

### Linux — Build from Source

```bash
# Clone the repo
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Build with CMake
cmake -B build
cmake --build build --config Release -j

# Confirm the server binary exists
ls -lh build/bin/llama-server
```

The `-j` flag uses all your CPU cores — if you want to be specific, use `-j4` for
4 cores, `-j$(nproc)` for all of them.

> **Tip:** If you have a CUDA-capable GPU, add `-DGGML_CUDA=ON` to the cmake
> command:
> ```bash
> cmake -B build -DGGML_CUDA=ON
> cmake --build build --config Release -j
> ```
> For AMD ROCm: `-DGGML_HIPBLAS=ON`. For Apple Metal: `-DGGML_METAL=ON`.

> **Where's the binary?** After building, `llama-server` lives in
> **`build/bin/llama-server`**. You can either:
> - Reference it directly in your launcher script (e.g., `$HOME/llama.cpp/build/bin/llama-server`)
> - Copy it to the llama.cpp root folder for convenience:
>   ```bash
>   cp build/bin/llama-server .
>   ```

### Windows — Option A: Pre-built Binaries (Easiest)

1. Go to the [llama.cpp releases page](https://github.com/ggerganov/llama.cpp/releases)
2. Download the latest `llama-bin-win-*.zip`
3. Extract it somewhere like `D:\Programs\llama.cpp\`
4. The `llama-server.exe` is right there in the extraction folder

> **Where's the binary?** Pre-built releases put everything in the root folder,
> so `llama-server.exe` is directly at
> **`D:\Programs\llama.cpp\llama-server.exe`**.

### Windows — Option B: Build with CMake

Open a **Developer Command Prompt for VS 2022** (or whatever Visual Studio you
have), then:

```batch
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
cmake -B build
cmake --build build --config Release -j
```

> **Where's the binary?** After building, `llama-server.exe` is in
> **`build\bin\Release\llama-server.exe`**. You can either:
> - Reference it directly (e.g., `D:\Programs\llama.cpp\build\bin\Release\llama-server.exe`)
> - Copy it to the root for convenience:
>   ```batch
>   copy build\bin\Release\llama-server.exe .
>   ```

For CUDA support, add `-DGGML_CUDA=ON` to the first cmake command.

---

## 3. Downloading a Model

llama.cpp speaks **GGUF** — a quantized model format that runs efficiently on
consumer hardware.

### Where to Get GGUF Models

- **[Hugging Face](https://huggingface.co/)** — The main hub. Search for "GGUF"
  to find quantized models.
- Look for reputable quantizers like **TheBloke**, **MaziyarPanahi**, or
  **Bartowski** — they publish well-tested GGUF conversions.

### The Example Model

This guide uses **Gemma-4-E4B** in a Q8 quant, but you can swap it for any GGUF
model you like.

| Property | Value |
|---|---|
| Model | Gemma-4-E4B-it |
| Quant | Q8_K_XL (High quality, ~8 bits per weight) |
| Size | Varies — check the Hugging Face repo |
| Hugging Face | [Search for "gemma-4-E4B-gguf"](https://huggingface.co/models?search=gemma-4-E4B-gguf) |

### Download Steps

**Linux:**
```bash
# Make a models directory
mkdir -p ~/models

# Download using wget or curl (replace URL with your actual model URL)
wget -O ~/models/gemma-4-E4B-it-UD-Q8_K_XL.gguf \
    "https://huggingface.co/username/model-name/resolve/main/file.gguf"
```

**Windows:**
```batch
mkdir D:\Programs\AIModels\Gemma
:: Download the GGUF file from Hugging Face into this folder
:: (use your browser or a tool like wget/aria2)
```

> **Heads up:** GGUF files can be **huge** (10–60 GB depending on the model and
> quantization). Make sure you've got the disk space before downloading!

---

## 4. Starting llama-server

llama.cpp ships with `llama-server` — a lightweight HTTP server that exposes an
**OpenAI-compatible API** at `/v1/chat/completions`. The RPG app talks to this
endpoint, so you need `llama-server` running before you start the game.

### Windows — Batch File

Create a file called `run-llama.bat` next to your model (or wherever you like).
Edit the `LLAMA_SERVER` and `MODEL` paths to match **your system**.

> **Important:** The `LLAMA_SERVER` path depends on how you installed llama.cpp
> (see [Section 2](#2-installing-llamacpp)). If you built from source, the binary
> is in `build\bin\Release\llama-server.exe`. If you used a pre-built release,
> it's in the root folder.

```batch
@echo off
setlocal

:: ============================================================
::  llama-server launcher for Gemma-4-E4B
::  Edit the variables below to change parameters
:: ============================================================

:: --- Paths ---
:: Point this to your llama-server.exe.
::   Pre-built release:  D:\Programs\llama.cpp\llama-server.exe
::   Built from source:  D:\Programs\llama.cpp\build\bin\Release\llama-server.exe
set LLAMA_SERVER=D:\Programs\llama.cpp\build\bin\Release\llama-server.exe
set MODEL="D:\Programs\AIModels\Gemma\E4B-id-UD-Q8_K_XL\gemma-4-E4B-it-UD-Q8_K_XL.gguf"

:: --- Server ---
set ALIAS=gemma-4
set HOST=0.0.0.0
set PORT=8001

:: --- Context & Output ---
set CONTEXT=33000
set MAX_TOKENS=16384

:: --- Memory / Cache ---
set CACHE_TYPE_K=q8_0
set CACHE_TYPE_V=q8_0

:: --- Batch ---
set BATCH_SIZE=2048
set UBATCH_SIZE=512

:: --- Sampling ---
set TEMPERATURE=0.7
set TOP_K=20
set TOP_P=0.95
set MIN_P=0.0
set PRESENCE_PENALTY=0.0
set REPEAT_PENALTY=1.1


:: ============================================================
::  Launch (no need to edit below this line)
:: ============================================================

echo.
echo  Starting llama-server...
echo  Model  : %MODEL%
echo  Host   : %HOST%:%PORT%
echo  Context: %CONTEXT%  ^|  Max tokens: %MAX_TOKENS%
echo.

"%LLAMA_SERVER%" ^
    --model "%MODEL%" ^
    --alias "%ALIAS%" ^
    --host %HOST% ^
    --port %PORT% ^
    --jinja ^
    --reasoning-format deepseek ^
    -fa on ^
    -c %CONTEXT% ^
    -n %MAX_TOKENS% ^
    --no-context-shift ^
    --cache-type-k %CACHE_TYPE_K% ^
    --cache-type-v %CACHE_TYPE_V% ^
    --temp %TEMPERATURE% ^
    --top-k %TOP_K% ^
    --top-p %TOP_P% ^
    --min-p %MIN_P% ^
    --batch-size %BATCH_SIZE% ^
    --ubatch-size %UBATCH_SIZE% ^
    --presence-penalty %PRESENCE_PENALTY% ^
    --repeat-penalty %REPEAT_PENALTY% ^
    --reasoning on

:: Keep the window open if the server exits or crashes
echo.
echo  Server stopped. Press any key to close...
pause > nul
```

**To use it:** Double-click `run-llama.bat`. Watch the output. If everything's
happy, you'll see `llama server listening on http://0.0.0.0:8001`.

### Linux — Shell Script

Create a file called `run-llama.sh` and make it executable:

> **Important:** The `LLAMA_SERVER` path depends on how you installed llama.cpp
> (see [Section 2](#2-installing-llamacpp)). If you built from source, the binary
> is in `build/bin/llama-server`. If you copied it to the root for convenience,
> adjust the path accordingly.

```bash
#!/usr/bin/env bash
# ============================================================
#  llama-server launcher for Gemma-4-E4B
#  Edit the variables below to change parameters
# ============================================================

# Point this to your llama-server binary.
#   Built from source:  $HOME/llama.cpp/build/bin/llama-server
#   Pre-built release:  $HOME/llama.cpp/llama-server
LLAMA_SERVER="$HOME/llama.cpp/build/bin/llama-server"
MODEL="$HOME/models/gemma-4-E4B-it-UD-Q8_K_XL.gguf"

ALIAS="gemma-4"
HOST="0.0.0.0"
PORT=8001

CONTEXT=33000
MAX_TOKENS=16384

CACHE_TYPE_K="q8_0"
CACHE_TYPE_V="q8_0"

BATCH_SIZE=2048
UBATCH_SIZE=512

TEMPERATURE=0.7
TOP_K=20
TOP_P=0.95
MIN_P=0.0
PRESENCE_PENALTY=0.0
REPEAT_PENALTY=1.1

echo ""
echo "Starting llama-server..."
echo "Model  : $MODEL"
echo "Host   : $HOST:$PORT"
echo "Context: $CONTEXT | Max tokens: $MAX_TOKENS"
echo ""

"$LLAMA_SERVER" \
    --model "$MODEL" \
    --alias "$ALIAS" \
    --host "$HOST" \
    --port "$PORT" \
    --jinja \
    --reasoning-format deepseek \
    -fa on \
    -c "$CONTEXT" \
    -n "$MAX_TOKENS" \
    --no-context-shift \
    --cache-type-k "$CACHE_TYPE_K" \
    --cache-type-v "$CACHE_TYPE_V" \
    --temp "$TEMPERATURE" \
    --top-k "$TOP_K" \
    --top-p "$TOP_P" \
    --min-p "$MIN_P" \
    --batch-size "$BATCH_SIZE" \
    --ubatch-size "$UBATCH_SIZE" \
    --presence-penalty "$PRESENCE_PENALTY" \
    --repeat-penalty "$REPEAT_PENALTY" \
    --reasoning on
```

Then run it:

```bash
chmod +x run-llama.sh
./run-llama.sh
```

### What You Should See

```
Starting llama-server...
Model  : /home/you/models/gemma-4-E4B-it-UD-Q8_K_XL.gguf
Host   : 0.0.0.0:8001
Context: 33000 | Max tokens: 16384

llama_model_loader: loaded meta data with X key-value pairs
...
llama server listening on http://0.0.0.0:8001
```

Once you see `llama server listening`, it's ready to accept connections. Leave
this terminal window open while you play.

---

## 5. Understanding the Flags

Here's what each flag does — useful when you want to tweak things:

| Flag | Example Value | What It Does |
|---|---|---|
| `--model` | `"/path/to/model.gguf"` | **Path to your GGUF model file.** Must be an absolute path or relative to where you run the command. |
| `--alias` | `"gemma-4"` | **This is the model name/ID** that the RPG app sees. Whatever you put here, you'll type into the connection screen's "Model" field. |
| `--host` | `0.0.0.0` | Listen on all network interfaces. Lets you connect from other machines or Docker containers on the same network. |
| `--port` | `8001` | The port your server listens on. The RPG app connects to `http://<host>:<port>`. |
| `--jinja` | *(flag)* | Use Jinja2 template for chat formatting. Ensures the model gets properly formatted conversation history. |
| `--reasoning-format` | `deepseek` | Format for reasoning/chain-of-thought traces. DeepSeek format works well with most modern instruct models. |
| `-fa` / `--flash-attn` | `on` | **Flash attention** — significantly speeds up inference and reduces memory usage. Keep this ON. |
| `-c` / `--ctx-size` | `33000` | **Context size** in tokens. Higher = more conversation history, but uses more memory. |
| `-n` / `--predict` | `16384` | **Max tokens to generate** per response. The model stops after this many tokens. |
| `--no-context-shift` | *(flag)* | Disable context shifting. Better for long conversations where you don't want earlier context sliding out. |
| `--cache-type-k` | `q8_0` | Quantization type for the K cache — saves VRAM. `q8_0` is good quality, `q4_0` saves more memory. |
| `--cache-type-v` | `q8_0` | Quantization type for the V cache — same deal as above. |
| `--temp` | `0.7` | **Temperature** — randomness of output. 0.0 = greedy/deterministic, 1.0 = very random. RPGs work well around 0.7–0.9. |
| `--top-k` | `20` | Limit the next token selection to the top K most likely tokens. |
| `--top-p` | `0.95` | Nucleus sampling — considers tokens whose cumulative probability reaches this threshold. |
| `--min-p` | `0.0` | Minimum probability for a token to be considered. 0.0 = no minimum. |
| `--batch-size` | `2048` | Number of tokens processed in parallel during prompt evaluation. Higher = faster prompt processing (if your hardware can handle it). |
| `--ubatch-size` | `512` | "Micro batch" size — tokens processed per step during generation. Keep lower than batch-size. |
| `--presence-penalty` | `0.0` | Penalize tokens that have already appeared (0.0 = disabled). |
| `--repeat-penalty` | `1.1` | Penalize repetition of token sequences. 1.0 = no penalty, 1.1 = mild penalty. |
| `--reasoning` | `on` | Enable the model's reasoning mode (for models that support it, like DeepSeek-R1 or Gemma-4). |

### Quick Tuning Guide

| If You Want To... | Change This |
|---|---|
| Make responses more creative | Raise `--temp` to 0.9 |
| Make responses more focused | Lower `--top-k` to 10 |
| Save memory | Lower `-c` to 8192, use `--cache-type-k q4_0` |
| Speed up prompt processing | Increase `--batch-size` to 4096 |
| Run on a low-end GPU | Add `-ngl 99` (offload all layers to GPU) |
| Run on CPU only | Omit `-ngl` entirely (or set to 0) |

---

## 6. Setting Up the RPG Application

With `llama-server` humming along, it's time to get the RPG app on its feet.

### Clone the Repository

```bash
git clone <your-repo-url> rpg-with-llm
cd rpg-with-llm
```

### Python Virtual Environment & Dependencies

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (cmd / PowerShell):**
```batch
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend — Install & Build TypeScript

```bash
npm install
npm run build
```

> `npm run build` compiles TypeScript from `app/static/ts/` into `app/static/js/`.
> If you change any `.ts` files later, re-run `npm run build` (or `npm run watch`
> during development to auto-rebuild on changes).

### Start the RPG Server

**Simplest — use the startup script:**

Linux:
```bash
./start.sh
```

Windows:
```batch
start.bat
```

**Or manually:**
```bash
python run.py
```

The server starts on `http://localhost:5000`. You'll see output like:

```
 * Running on http://0.0.0.0:5000
 * Press CTRL+C to quit
```

---

## 7. Configuring the RPG to Use llama.cpp

Now for the fun bit — connecting the RPG to your local model.

### Step-by-Step

1. **Open your browser** to `http://localhost:5000`

2. **You'll see the Connection view.** Fill it in like this:

   | Field | What to Put |
   |---|---|
   | **Provider** | Select `llama.cpp` from the dropdown |
   | **Base URL** | `http://localhost:8001` (or whatever port you set) |
   | **API Key** | Leave blank — llama.cpp doesn't need one |
   | **Model** | Type the `--alias` you set (e.g., `gemma-4`) |

3. **Click "Test Connection"** — you should see a green success with latency
   in milliseconds. If it fails, check the [Troubleshooting](#9-troubleshooting)
   section.

4. **Click "Start Adventure!"** — this takes you to character creation.

5. **Create a character**, then start playing!

### What "Test Connection" Checks

The app sends a lightweight request to `llama-server` at
`POST /v1/chat/completions`. If it gets back a valid response, the connection
is good and you're ready to play.

---

## 8. Advanced: Multi-Agent Configuration

The RPG has three agents that can each use a **different** LLM provider — or the
**same** one. Here's how they break down:

| Agent | Role | Default Settings |
|---|---|---|
| **DM** (Dungeon Master) | Narrates the story, runs the game | Max tokens: 4096, Temp: 0.8 |
| **NPC** | Speaks for non-player characters | Max tokens: 1024, Temp: 0.8 |
| **Summarizer** | Compresses conversation history | Max tokens: 4096, Temp: 0.3 |

### All Agents — Same llama.cpp Server

The simplest setup: all three agents talk to the same `llama-server` instance.
Just configure the main provider as described above, and you're done. The NPC
and Summarizer will use the same settings by default.

### Separate Configurations Per Agent

In the Connection view, click the **"▶ Advanced"** toggle to reveal per-agent
settings:

1. **Enable the agent** — check the box next to NPC or Summarizer
2. **Choose a provider** — you could use `llama.cpp` for DM but a cloud provider
   for summarization
3. **Set per-agent generation settings**:
   - **Max Tokens**: How long the response can be
   - **Temperature**: Creativity level (lower = more deterministic)
   - **Timeout**: Max seconds to wait for a response

**Why would you do this?**
- Offload summarization to a faster/smaller model
- Use a different model for NPC dialogue
- Keep the DM on your local machine but use a cloud API for heavy lifting

### Multiple llama.cpp Instances

You can run multiple `llama-server` instances on different ports with different
models:

```bash
# Terminal 1 — Large DM model on port 8001
./run-llama.sh          # gemma-4 alias

# Terminal 2 — Small NPC model on port 8002
llama-server --model ~/models/small-model.gguf --alias fast-npc --port 8002 ...
```

Then in the RPG connection screen, point each agent to its respective server.

---

## 9. Troubleshooting

### Connection Fails

| Symptom | Likely Cause | Fix |
|---|---|---|
| "Connection refused" | `llama-server` isn't running | Start it! Check terminal for errors |
| "Timeout" | Wrong host/port | Verify the URL in the app matches `--host` and `--port` |
| "Model not found" | The `--alias` doesn't match | The "Model" field must match `--alias` exactly |
| "401 Unauthorized" | API key required | llama.cpp doesn't need keys — leave the field blank |
| "Cross-Origin Request Blocked" | CORS issue | Try `llama-server` with `--cors-allow "http://localhost:5000"` |

### Model Not Found / Wrong Model

llama.cpp reports models using the `--alias` you provided. If you set
`--alias my-cool-model`, type `my-cool-model` in the RPG's model field. Don't
use the filename of the GGUF — use the alias.

Click **"Fetch Models"** next to the model field to auto-discover available
models from the running server.

### Out of Memory (OOM)

The example uses a 33K context window — that eats a LOT of RAM/VRAM.

| What To Do | How |
|---|---|
| **Reduce context size** | Change `CONTEXT` to `8192` |
| **Use a lighter quant** | Download Q4_K_M instead of Q8_K_XL |
| **Lower batch sizes** | Set `BATCH_SIZE=1024`, `UBATCH_SIZE=256` |
| **Switch to CPU** | Remove any GPU flags or set `-ngl 0` |
| **Add `--mlock`** | Locks memory to prevent swapping (Linux) |

### Slow Responses

| Tweak | Expected Improvement |
|---|---|
| Enable `-fa on` (flash attention) | 2–4× faster inference |
| Increase `--batch-size` to 4096 | Faster prompt processing |
| Use GPU offloading `-ngl 99` | Dramatic speedup if you have a GPU |
| Use a smaller model | Q4_K_M is 2× faster than Q8_K_XL on memory-bound hardware |
| Reduce `-c` (context) | Less tokens to process = faster per-turn |

### Server Won't Start

```text
llama_model_loader: error loading model: file not found
```

The `--model` path is wrong — double-check it's an absolute path that exists.

```text
CUDA error: out of memory
```

Your GPU can't fit the model + context. Reduce context size, use a smaller
quant, or run on CPU (`-ngl 0`).

```text
llama.cpp: unknown argument: --foobar
```

You've got a typo in a flag. Check the flag name matches your version of
`llama-server` (`./llama-server --help`).

### GPU Not Being Used

If you built llama.cpp **without** GPU support, it defaults to CPU. Rebuild
with the appropriate flag for your hardware:

| Hardware | CMake Flag |
|---|---|
| NVIDIA (CUDA) | `-DGGML_CUDA=ON` |
| AMD (ROCm) | `-DGGML_HIPBLAS=ON` |
| Apple Silicon | `-DGGML_METAL=ON` |
| Intel GPU | `-DGGML_SYCL=ON` |

Then add `-ngl 99` to your llama-server flags to offload ALL layers to the GPU.

---

## 10. Performance Tips

### Pick the Right Quantization

| Quant | Quality | Speed | VRAM Usage | Best For |
|---|---|---|---|---|
| Q8_K_XL | Excellent | Good | High | High-end GPUs (24 GB+) |
| Q6_K | Very good | Better | Medium-High | Mid-range GPUs (16 GB) |
| Q5_K_M | Good | Good | Medium | Most setups |
| Q4_K_M | Decent | Great | Low | Low-end GPUs, 8 GB cards |
| Q3_K_M | Okay | Fastest | Very low | CPU-only, 6 GB GPUs |
| Q2_K | Passable | Fastest | Minimal | Emergency mode |

### Context Size vs Memory

| Context Size | Approx VRAM (Q8, 7B model) | Approx VRAM (Q4, 7B model) |
|---|---|---|
| 4096 | ~8 GB | ~5 GB |
| 8192 | ~10 GB | ~6 GB |
| 16384 | ~14 GB | ~8 GB |
| 33000 | ~22 GB | ~12 GB |

### Recommended Launch Configurations

**"I've got a beefy GPU (24 GB VRAM)"**
```
-c 32768 -fa on -ngl 99 --batch-size 4096 --cache-type-k q8_0 --cache-type-v q8_0
```

**"I've got a mid-range GPU (12 GB VRAM)"**
```
-c 8192 -fa on -ngl 99 --batch-size 2048 --cache-type-k q8_0 --cache-type-v q8_0
```
Use a Q4_K_M quantized model.

**"I'm running on CPU only"**
```
-c 4096 --batch-size 512 --ubatch-size 256 --threads 8
```
Use a Q4_K_M or Q3_K_M quant. Lower context to 4096 for reasonable speed.

### General Tips

- **Flash attention (`-fa on`) is almost always worth it** — free speed with no
  quality loss
- **GPU offloading (`-ngl`) is linear** — `-ngl 99` puts all layers on GPU,
  `-ngl 20` puts only 20 layers (mix of CPU/GPU). Even partial offloading helps
- **Batch size** affects prompt processing speed. Higher = faster evaluation of
  the initial prompt (your conversation history). Don't go above what your GPU
  memory allows
- **Cache quantization** (`--cache-type-k/q8_0`) saves ~50% on KV cache memory
  with minimal quality loss. Drop to `q4_0` for extreme memory savings
- **Watch your temperatures** — literally. Monitor GPU temps with `nvidia-smi`
  (Linux) or GPU-Z (Windows). If it's hitting 85°C+, improve cooling or lower
  power limits

---

> **Grubnik's final words:** That's it! You've got a local brain running your
> RPG. No clouds, no bills, no tracking. Just you, your model, and the
> adventure. If something breaks, check the logs. If it still breaks, come find
> me and I'll bash it with a wrench until it works.
>
> Now go play! The Dark One commands it!
