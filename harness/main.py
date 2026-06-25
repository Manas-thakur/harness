#!/usr/bin/env python3
"""
Main entry point for the Local Agent Fleet.
Supports local LLM, TUI dashboard, and command palette.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from .config import load_config, AgentConfig
from .coordinator import Coordinator
from .inband_memory import InBandMemory
from .local_llm import LocalLLMProvider
from .dashboard import Dashboard


def parse_args():
    parser = argparse.ArgumentParser(description="Local Agent Fleet")
    parser.add_argument("--local", action="store_true", help="Run in local mode with local LLM")
    parser.add_argument("--dashboard", action="store_true", help="Enable TUI dashboard")
    parser.add_argument("--model", type=str, default=None, help="Path to local model (GGUF) or Ollama model name")
    parser.add_argument("--agent-id", type=str, default="default", help="Agent ID for sharding")
    parser.add_argument("--shard", type=str, default="default", help="Memory shard name")
    parser.add_argument("--palette", action="store_true", help="Open command palette immediately")
    parser.add_argument("--bundle", type=str, default=None, help="Path to agent bundle directory")
    return parser.parse_args()


async def run_agent(config: AgentConfig, args):
    """Run the agent loop."""
    # Initialize memory
    memory = InBandMemory(
        agent_id=args.agent_id,
        memory_root=config.memory.memory_dir
    )
    memory.initialize()

    # Initialize LLM
    llm = None
    if args.local:
        llm = LocalLLMProvider(model_path=args.model)
        await llm.initialize()

    # Initialize coordinator
    coordinator = Coordinator(
        model=config.model.model_name,
        max_turns=config.agent.max_iterations
    )

    # Run dashboard if enabled
    if args.dashboard:
        dashboard = Dashboard(coordinator=coordinator)
        await dashboard.run()
    else:
        # Simple CLI mode
        print(f"Agent {args.agent_id} started in CLI mode.")
        print("Type 'quit' to exit.")

        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break

                response = await coordinator.process_message(user_input)
                print(f"\n🤖 Agent: {response}")

            except KeyboardInterrupt:
                break
            except EOFError:
                break

    await coordinator.shutdown()


def main():
    args = parse_args()

    # Load config
    if args.bundle:
        # Load from bundle
        bundle_path = Path(args.bundle)
        if not bundle_path.exists():
            print(f"Error: Bundle not found at {bundle_path}")
            sys.exit(1)

        config = load_config(bundle_path / "manifest.json")
        os.chdir(bundle_path)
    else:
        config = load_config()

    # Override config with args
    if args.model:
        config.model.model_name = args.model

    # Run async
    try:
        asyncio.run(run_agent(config, args))
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
