# demo-agent - Agent Bundle

Created: 2026-06-25 08:42:34

## Quick Start

### Linux/macOS
```bash
./start.sh
```

### Windows
```bash
start.bat
```

## Requirements
- Python 3.10+
- Ollama (recommended) or local GGUF model
- Dependencies: `pip install rich aiohttp`

## Configuration
Edit `manifest.json` to change settings.

## Memory
Memory files are in the `memory/` directory. Edit `.md` files directly to teach the agent.

## Moving This Bundle
Copy the entire `demo-agent` folder to another machine. Ensure Ollama is installed, then run `start.sh`.
