#!/usr/bin/env bash
# ============================================================================
# start.sh — LLM-Powered RPG Startup Script
# ============================================================================
# Checks Python 3.10+, creates venv, installs deps, starts the Flask server
# on port 5000, and opens the browser.
# ============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info() { printf "${CYAN}%s${NC}\n" "$*"; }
success() { printf "${GREEN}%s${NC}\n" "$*"; }
warn() { printf "${YELLOW}%s${NC}\n" "$*"; }
error() { printf "${RED}%s${NC}\n" "$*" >&2; }

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
REQUIREMENTS="${PROJECT_ROOT}/requirements.txt"
RUN_SCRIPT="${PROJECT_ROOT}/run.py"
HOST="0.0.0.0"
PORT=5000
URL="http://localhost:${PORT}"

# ---------------------------------------------------------------------------
# Parse command-line arguments
# ---------------------------------------------------------------------------
VERBOSE=false
for arg in "$@"; do
	case "$arg" in
	-v | --verbose)
		VERBOSE=true
		shift
		;;
	-h | --help)
		echo "Usage: $0 [-v|--verbose]"
		echo "  -v, --verbose    Enable debug logging to logs/rpg.log"
		exit 0
		;;
	*)
		error "Unknown argument: $arg"
		exit 1
		;;
	esac
done

# Set log level
if [ "$VERBOSE" = true ]; then
	export RPG_LOG_LEVEL=DEBUG
	info "🔊 Verbose mode enabled — debug logs will be written to logs/rpg.log"
fi

# ---------------------------------------------------------------------------
# Root user check (Flask dev server warns against running as root)
# ---------------------------------------------------------------------------
if [ "$(id -u)" = "0" ]; then
	warn "⚠ Running as root is not recommended. Flask's development server"
	warn "  warns against running with root privileges. Consider using a"
	warn "  non-root user if possible."
fi

# ---------------------------------------------------------------------------
# Step 1: Check Python 3.10+
# ---------------------------------------------------------------------------
info "🔍 Checking Python version..."
PYTHON=""
for candidate in python3 python; do
	if command -v "$candidate" &>/dev/null; then
		PYTHON="$candidate"
		break
	fi
done

if [ -z "$PYTHON" ]; then
	error "❌ Python not found! Please install Python 3.10 or later."
	exit 1
fi

PY_VER="$($PYTHON --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')"
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER#*.}"

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
	error "❌ Python 3.10+ required, found $($PYTHON --version 2>&1)"
	exit 1
fi

success "✓ Found $($PYTHON --version 2>&1)"

# ---------------------------------------------------------------------------
# Step 2: Create virtual environment if missing
# ---------------------------------------------------------------------------
if [ ! -d "$VENV_DIR" ]; then
	info "📦 Creating virtual environment in ${VENV_DIR}..."
	$PYTHON -m venv "$VENV_DIR"
	success "✓ Virtual environment created."
else
	info "✓ Virtual environment already exists."
fi

# ---------------------------------------------------------------------------
# Step 3: Activate venv & install dependencies
# ---------------------------------------------------------------------------
info "🔧 Activating virtual environment..."
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate" || {
	error "❌ Failed to activate virtual environment at ${VENV_DIR}."
	error "  The venv may be corrupted. Try removing ${VENV_DIR} and re-running."
	exit 1
}

if [ -f "$REQUIREMENTS" ]; then
	info "📥 Installing dependencies from requirements.txt..."
	pip install --quiet --upgrade pip
	pip install --quiet -r "$REQUIREMENTS"
	success "✓ Dependencies installed."
else
	warn "⚠ No requirements.txt found at ${REQUIREMENTS}, skipping."
fi

# ---------------------------------------------------------------------------
# Step 4: Check Node.js and npm
# ---------------------------------------------------------------------------
info "🔍 Checking for Node.js and npm..."
if ! command -v node &>/dev/null; then
	error "❌ Node.js is required but not installed."
	error "   Install Node.js from https://nodejs.org/ (v18 or later)"
	exit 1
fi

if ! command -v npm &>/dev/null; then
	error "❌ npm is required but not installed."
	error "   Install npm alongside Node.js from https://nodejs.org/ (v18 or later)"
	exit 1
fi

success "✓ Found Node.js $(node --version) with npm $(npm --version)"

# ---------------------------------------------------------------------------
# Step 5: Install frontend dependencies and build TypeScript
# ---------------------------------------------------------------------------
info "📦 Installing frontend dependencies (npm install)..."
npm --prefix "$PROJECT_ROOT" install || {
	error "npm install failed. Check your network and package.json."
	exit 1
}
success "✓ Frontend dependencies installed."

info "🔨 Compiling TypeScript frontend (npm run build)..."
npm --prefix "$PROJECT_ROOT" run build || {
	error "npm run build failed. Check your TypeScript source files for errors."
	exit 1
}
success "✓ TypeScript compilation complete."

# ---------------------------------------------------------------------------
# Step 6: Start the Flask server in the background
# ---------------------------------------------------------------------------
info "🚀 Starting RPG server on ${URL}..."
$PYTHON "$RUN_SCRIPT" &
SERVER_PID=$!

# Make sure we clean up the server process on exit
cleanup() {
	if kill -0 "$SERVER_PID" 2>/dev/null; then
		info "🛑 Shutting down server (PID ${SERVER_PID})..."
		kill "$SERVER_PID" 2>/dev/null
		wait "$SERVER_PID" 2>/dev/null || true
		success "✓ Server stopped."
	fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Step 7: Wait for the server to be ready
# ---------------------------------------------------------------------------
info "⏳ Waiting for server to become ready..."

if command -v curl &>/dev/null; then
	MAX_RETRIES=30
	RETRY_COUNT=0

	while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
		if curl -s --max-time 2 "http://localhost:${PORT}/api/health" >/dev/null 2>&1; then
			success "✓ Server is ready!"
			break
		fi
		RETRY_COUNT=$((RETRY_COUNT + 1))
		sleep 1
	done

	if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
		warn "⚠ Server may not be fully started yet (health check timed out)."
		warn "  Check ${URL} manually."
	fi
else
	warn "⚠ curl not found — skipping health check. Waiting 3 seconds..."
	sleep 3
fi

# ---------------------------------------------------------------------------
# Step 8: Open browser
# ---------------------------------------------------------------------------
info "🌐 Opening browser to ${URL}..."
if command -v xdg-open &>/dev/null; then
	xdg-open "$URL" &>/dev/null &
elif command -v open &>/dev/null; then
	open "$URL" &>/dev/null &
elif command -v sensible-browser &>/dev/null; then
	sensible-browser "$URL" &>/dev/null &
else
	warn "⚠ Could not find xdg-open or sensible-browser."
	warn "  Please open ${URL} manually in your browser."
fi

# ---------------------------------------------------------------------------
# Step 9: Follow server logs
# ---------------------------------------------------------------------------
echo ""
success "╔══════════════════════════════════════════════════════════╗"
success "║              LLM-Powered RPG is running.                 ║"
success "║           Press Ctrl+C to stop the server.               ║"
success "╚══════════════════════════════════════════════════════════╝"
success "${URL}"
echo ""

# Wait for the server process so logs stream to terminal
wait "$SERVER_PID"
