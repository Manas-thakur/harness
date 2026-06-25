#!/usr/bin/env python3
"""
Ollama Manager - Command-line interface for Ollama model management.
Provides easy model switching, pulling, and health checks.
"""

import argparse
import asyncio
import json
import subprocess
from typing import Optional


async def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        proc = await asyncio.create_subprocess_exec(
            'curl', '-s', 'http://localhost:11434/api/tags',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        if proc.returncode == 0:
            data = json.loads(stdout)
            return 'models' in data
    except Exception:
        pass
    return False


async def list_models():
    """List all available Ollama models."""
    print("\n📋 Available Models:\n")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            'curl', '-s', 'http://localhost:11434/api/tags',
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        data = json.loads(stdout)
        
        if not data.get('models'):
            print("  No models found.")
            return
        
        print(f"  {'Name':<40} {'Size':<15} {'Family':<20}")
        print("  " + "-" * 75)
        
        for model in data['models']:
            name = model['name']
            size = f"{model.get('size', 0) / (1024**3):.1f} GB"
            family = model.get('details', {}).get('family', 'Unknown')
            print(f"  {name:<40} {size:<15} {family:<20}")
            
    except Exception as e:
        print(f"  Error: {e}")
        print("  Make sure Ollama is running: ollama serve")


async def pull_model(model_name: str):
    """Pull a model from Ollama registry."""
    print(f"\n⬇️  Pulling {model_name}...\n")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            'ollama', 'pull', model_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        async for line in proc.stdout:
            decoded = line.decode().strip()
            if decoded:
                print(f"  {decoded}")
        
        await proc.wait()
        
        if proc.returncode == 0:
            print(f"\n✅ Successfully pulled {model_name}")
        else:
            print(f"\n❌ Failed to pull {model_name}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")


async def switch_model(model_name: str, config_path: Optional[str] = None):
    """Switch the active model in config."""
    print(f"\n🔄 Switching to {model_name}...")
    
    # Update environment variable for current session
    print(f"  Set AGENT_MODEL_NAME={model_name}")
    
    # Try to update config file if exists
    if config_path:
        try:
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            config['model']['name'] = model_name
            
            with open(config_path, 'w') as f:
                yaml.safe_dump(config, f)
            
            print(f"  ✓ Updated config file: {config_path}")
        except Exception as e:
            print(f"  ⚠ Could not update config: {e}")
    
    print(f"\n✅ Active model is now: {model_name}")
    print("   Restart the agent to apply changes, or use the dashboard palette.")


async def delete_model(model_name: str):
    """Delete a local model."""
    print(f"\n🗑️  Deleting {model_name}...")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            'ollama', 'rm', model_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        
        if proc.returncode == 0:
            print(f"✅ Successfully deleted {model_name}")
        else:
            print(f"❌ Failed: {stdout.decode()}")
            
    except Exception as e:
        print(f"❌ Error: {e}")


async def show_info(model_name: str):
    """Show detailed info about a model."""
    print(f"\nℹ️  Model Info: {model_name}\n")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            'ollama', 'show', model_name,
            stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        print(stdout.decode())
        
    except Exception as e:
        print(f"Error: {e}")


async def health_check():
    """Run Ollama health check."""
    print("\n🏥 Ollama Health Check\n")
    
    # Check if service is running
    is_running = await check_ollama()
    
    if is_running:
        print("  ✓ Ollama service: Running")
        
        # Get version
        try:
            proc = await asyncio.create_subprocess_exec(
                'ollama', '--version',
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            print(f"  ✓ Version: {stdout.decode().strip()}")
        except:
            print("  ⚠ Version: Unknown")
        
        # Count models
        try:
            proc = await asyncio.create_subprocess_exec(
                'curl', '-s', 'http://localhost:11434/api/tags',
                stdout=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            data = json.loads(stdout)
            count = len(data.get('models', []))
            print(f"  ✓ Models installed: {count}")
        except:
            print("  ⚠ Models: Unknown")
        
        print("\n✅ Ollama is healthy and ready!")
        
    else:
        print("  ✗ Ollama service: Not running")
        print("\n💡 Start Ollama with: ollama serve")
        print("   Or install from: https://ollama.com")


def main():
    parser = argparse.ArgumentParser(description="Ollama Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    subparsers.add_parser("list", help="List available models")
    
    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Pull a new model")
    pull_parser.add_argument("--model", type=str, required=True, help="Model name (e.g., llama3.1)")
    
    # Switch command
    switch_parser = subparsers.add_parser("switch", help="Switch active model")
    switch_parser.add_argument("--model", type=str, required=True, help="Model name")
    switch_parser.add_argument("--config", type=str, default=None, help="Config file path")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a model")
    delete_parser.add_argument("--model", type=str, required=True, help="Model name")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show model info")
    info_parser.add_argument("--model", type=str, required=True, help="Model name")
    
    # Health command
    subparsers.add_parser("health", help="Check Ollama health")
    
    args = parser.parse_args()
    
    if args.command == "list":
        asyncio.run(list_models())
    elif args.command == "pull":
        asyncio.run(pull_model(args.model))
    elif args.command == "switch":
        asyncio.run(switch_model(args.model, args.config))
    elif args.command == "delete":
        asyncio.run(delete_model(args.model))
    elif args.command == "info":
        asyncio.run(show_info(args.model))
    elif args.command == "health":
        asyncio.run(health_check())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
