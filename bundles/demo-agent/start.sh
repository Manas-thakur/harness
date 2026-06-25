#!/bin/bash
# Agent Bundle Launcher: demo-agent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting demo-agent..."

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠ Ollama not found. Install from https://ollama.com"
fi

# Launch the TUI (single interface). Ensure the harness package is importable.
export PYTHONPATH="${PYTHONPATH:-}:$SCRIPT_DIR"
python3 -m harness.tui

