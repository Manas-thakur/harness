#!/usr/bin/env python3
"""
Agent Bundle Manager - Creates portable agent packages.
Bundles memory, config, and startup scripts into a single directory.
"""

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional


def create_bundle(
    name: str,
    output_dir: Path,
    memory_dir: Optional[Path] = None,
    config_file: Optional[Path] = None
) -> Path:
    """Create a portable agent bundle."""

    bundle_path = output_dir / name
    bundle_path.mkdir(parents=True, exist_ok=True)

    print(f"📦 Creating bundle: {bundle_path}")

    # Copy memory directory
    if memory_dir is None:
        memory_dir = Path("./memory")

    if memory_dir.exists():
        bundle_memory = bundle_path / "memory"
        shutil.copytree(memory_dir, bundle_memory, dirs_exist_ok=True)
        print(f"  ✓ Copied memory ({len(list(bundle_memory.rglob('*.md')))} files)")
    else:
        print("  ⚠ No memory directory found")

    # Create manifest
    manifest = {
        "name": name,
        "version": "1.0.0",
        "created_at": datetime.now().isoformat(),
        "config": {
            "model": "llama3.1",
            "local_mode": True,
            "dashboard": True
        },
        "memory_shards": ["default"],
        "requirements": [
            "rich>=13.0.0",
            "aiohttp>=3.9.0"
        ]
    }

    manifest_path = bundle_path / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print("  ✓ Created manifest.json")

    # Create start script (Unix)
    start_sh = bundle_path / "start.sh"
    start_sh.write_text(f"""#!/bin/bash
# Agent Bundle Launcher: {name}

set -e

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting {name}..."

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo "⚠ Ollama not found. Install from https://ollama.com"
fi

# Launch the TUI (single interface). Ensure the harness package is importable.
export PYTHONPATH="${{PYTHONPATH:-}}:$SCRIPT_DIR"
python3 -m harness.tui

""")
    start_sh.chmod(0o755)
    print("  ✓ Created start.sh")

    # Create start script (Windows)
    start_bat = bundle_path / "start.bat"
    start_bat.write_text(f"""@echo off
REM Agent Bundle Launcher: {name}

echo 🚀 Starting {name}...

REM Check for Ollama
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠ Ollama not found. Install from https://ollama.com
)

REM Launch the TUI (single interface)
set PYTHONPATH=%PYTHONPATH%;%~dp0
python -m harness.tui

pause
""")
    print("  ✓ Created start.bat")

    # Create .agent_env.sh
    env_sh = bundle_path / ".agent_env.sh"
    env_sh.write_text(f"""# Environment variables for {name}
export AGENT_MODEL_NAME="qwen3:8b"
export AGENT_MEMORY_DIR="{bundle_path}/memory"
export AGENT_DASHBOARD_ENABLED="true"
export AGENT_LOCAL_MODE="true"
""")
    print("  ✓ Created .agent_env.sh")

    # Create README
    readme = bundle_path / "README.md"
    readme.write_text(f"""# {name} - Agent Bundle

Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

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
Copy the entire `{name}` folder to another machine. Ensure Ollama is installed, then run `start.sh`.
""")
    print("  ✓ Created README.md")

    print(f"\n✅ Bundle created successfully at: {bundle_path}")
    print(f"   To use: cd {bundle_path} && ./start.sh")

    return bundle_path


def list_bundles(base_dir: Path) -> None:
    """List all available bundles."""
    print("\n📦 Available Bundles:\n")

    if not base_dir.exists():
        print("  No bundles found.")
        return

    bundles = []
    for item in base_dir.iterdir():
        if item.is_dir() and (item / "manifest.json").exists():
            with open(item / "manifest.json") as f:
                manifest = json.load(f)
                bundles.append({
                    "name": item.name,
                    "created": manifest.get("created_at", "Unknown"),
                    "model": manifest.get("config", {}).get("model", "Unknown")
                })

    if not bundles:
        print("  No bundles found.")
        return

    print(f"  {'Name':<30} {'Created':<25} {'Model':<20}")
    print("  " + "-" * 75)
    for b in bundles:
        print(f"  {b['name']:<30} {b['created'][:19]:<25} {b['model']:<20}")


def main():
    parser = argparse.ArgumentParser(description="Agent Bundle Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a new bundle")
    create_parser.add_argument("--name", type=str, required=True, help="Bundle name")
    create_parser.add_argument("--output", type=Path, default=Path("./bundles"), help="Output directory")
    create_parser.add_argument("--memory-dir", type=Path, default=None, help="Custom memory directory")
    create_parser.add_argument("--config", type=Path, default=None, help="Custom config file")

    # List command
    list_parser = subparsers.add_parser("list", help="List available bundles")
    list_parser.add_argument("--dir", type=Path, default=Path("./bundles"), help="Bundles directory")

    args = parser.parse_args()

    if args.command == "create":
        create_bundle(
            name=args.name,
            output_dir=args.output,
            memory_dir=args.memory_dir,
            config_file=args.config
        )
    elif args.command == "list":
        list_bundles(args.dir)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
