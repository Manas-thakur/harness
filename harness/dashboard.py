#!/usr/bin/env python3
"""
TUI Dashboard with Rich for real-time agent monitoring.
Includes Command Palette (Ctrl+P) for model management.
"""

import asyncio
from typing import List
from datetime import datetime

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.prompt import Prompt
    from rich import box
except ImportError:
    print("Rich not installed. Run: pip install rich")
    raise


class Dashboard:
    """Real-time TUI dashboard for agent monitoring."""

    def __init__(self, coordinator=None):
        self.coordinator = coordinator
        self.console = Console()
        self.running = True
        self.logs: List[str] = []
        self.status = "Idle"
        self.current_model = "Unknown"
        self.memory_nodes = 0
        self.token_count = 0

    async def run(self):
        """Run the dashboard main loop."""
        self.console.print("[bold green]🚀 Starting Agent Dashboard...[/bold green]")
        self.console.print("[dim]Press Ctrl+C to stop, Ctrl+P for Command Palette[/dim]\n")

        # Initialize status
        if self.coordinator and hasattr(self.coordinator, 'llm_client'):
            if self.coordinator.llm_client:
                health = await self.coordinator.llm_client.health_check()
                self.current_model = health.get('model', 'Unknown')
                self.status = "Ready" if health.get('healthy') else "Error"

        # Main interaction loop
        while self.running:
            self._render_status()

            try:
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: Prompt.ask("\n[bold blue]👤 You[/bold blue]")
                )

                if user_input.lower() in ['quit', 'exit', 'q']:
                    break

                # Show thinking indicator
                self.console.print("\n[bold yellow]🤖 Agent thinking...[/bold yellow]")

                if self.coordinator:
                    response = await self.coordinator.process_message(user_input)
                    self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] User: {user_input}")
                    self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Agent: {response}")

                    self.console.print(f"\n[bold green]🤖 Agent[/bold green]: {response}")
                else:
                    self.console.print("[red]No coordinator available[/red]")

            except KeyboardInterrupt:
                break

        self.console.print("\n[bold yellow]Shutting down dashboard...[/bold yellow]")

    def _render_status(self):
        """Render current status panel."""
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Status", f"[green]{self.status}[/green]" if self.status == "Ready" else f"[red]{self.status}[/red]")
        table.add_row("Model", self.current_model)
        table.add_row("Memory Nodes", str(self.memory_nodes))
        table.add_row("Tokens", str(self.token_count))
        table.add_row("Time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        self.console.print(Panel(table, title="[bold]📊 Agent Status[/bold]", border_style="blue"))

    async def show_command_palette(self):
        """Show command palette overlay."""
        self.console.clear()
        self.console.print("[bold reverse] 🎛️  COMMAND PALETTE [/bold reverse]\n")

        commands = [
            ("1", "Switch Model", "Change active LLM model"),
            ("2", "Pull Model", "Download new model from Ollama"),
            ("3", "View Memory Graph", "Visualize memory connections"),
            ("4", "Compact Memory", "Summarize old memories"),
            ("5", "Export Bundle", "Create portable agent bundle"),
            ("6", "Health Check", "Check system status"),
            ("q", "Back", "Return to dashboard"),
        ]

        table = Table(box=box.ROUNDED)
        table.add_column("Key", style="yellow", width=5)
        table.add_column("Command", style="cyan", width=20)
        table.add_column("Description", style="white")

        for key, cmd, desc in commands:
            table.add_row(key, cmd, desc)

        self.console.print(table)

        choice = await asyncio.get_event_loop().run_in_executor(
            None, lambda: Prompt.ask("\n[bold]Select command[/bold]")
        )

        await self._handle_command(choice)

    async def _handle_command(self, choice: str):
        """Handle command palette selection."""
        if choice == '1':
            await self._switch_model()
        elif choice == '2':
            await self._pull_model()
        elif choice == '3':
            self._view_memory_graph()
        elif choice == '4':
            await self._compact_memory()
        elif choice == '5':
            self._export_bundle()
        elif choice == '6':
            await self._health_check()
        elif choice.lower() == 'q':
            return

    async def _switch_model(self):
        """Switch to a different model."""
        if not self.coordinator or not hasattr(self.coordinator, 'llm_client'):
            self.console.print("[red]No LLM client available[/red]")
            return

        models = await self.coordinator.llm_client.list_models()

        if not models:
            self.console.print("[yellow]No models found. Make sure Ollama is running.[/yellow]")
            return

        self.console.print("\n[bold]Available Models:[/bold]")
        for i, model in enumerate(models, 1):
            size_gb = f"{model.size_gb:.1f}GB" if model.size_gb > 0 else "Unknown"
            self.console.print(f"  {i}. {model.name} ({size_gb})")

        choice = await asyncio.get_event_loop().run_in_executor(
            None, lambda: Prompt.ask("\nSelect model number")
        )

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                new_model = models[idx].name
                self.coordinator.llm_client.model_info.name = new_model
                self.current_model = new_model
                self.console.print(f"[green]✓ Switched to {new_model}[/green]")
        except ValueError:
            self.console.print("[red]Invalid selection[/red]")

    async def _pull_model(self):
        """Pull a new model from Ollama."""
        model_name = await asyncio.get_event_loop().run_in_executor(
            None, lambda: Prompt.ask("[bold]Enter model name[/bold] (e.g., llama3.1, codellama:7b)")
        )

        if self.coordinator and hasattr(self.coordinator, 'llm_client'):
            self.console.print(f"\n[yellow]Pulling {model_name}...[/yellow]")
            success = await self.coordinator.llm_client.pull_model(model_name)
            if success:
                self.console.print(f"[green]✓ Successfully pulled {model_name}[/green]")
            else:
                self.console.print(f"[red]✗ Failed to pull {model_name}[/red]")

    def _view_memory_graph(self):
        """Display memory node connections."""
        self.console.print("\n[bold]🧠 Memory Graph[/bold]")
        if self.coordinator and hasattr(self.coordinator, 'memory'):
            # Simplified graph view
            self.console.print("  facts/ ──┬──> skills/")
            self.console.print("           └──> episodes/")
            self.console.print("  [[wikilinks]] connect nodes automatically")
        else:
            self.console.print("[red]Memory system not available[/red]")

    async def _compact_memory(self):
        """Trigger memory compaction."""
        self.console.print("\n[yellow]Compacting memory...[/yellow]")
        if self.coordinator and hasattr(self.coordinator, 'memory'):
            # Call compact method if available
            if hasattr(self.coordinator.memory, 'compact_node'):
                await self.coordinator.memory.compact_node()
                self.console.print("[green]✓ Memory compacted[/green]")
            else:
                self.console.print("[yellow]Compaction not implemented yet[/yellow]")
        else:
            self.console.print("[red]Memory system not available[/red]")

    def _export_bundle(self):
        """Export agent bundle."""
        self.console.print("\n[yellow]Creating bundle...[/yellow]")
        self.console.print("[green]✓ Use: python -m harness.bundler create --name my-agent[/green]")

    async def _health_check(self):
        """Run system health check."""
        self.console.print("\n[bold]🏥 Health Check[/bold]")

        if self.coordinator and hasattr(self.coordinator, 'llm_client'):
            health = await self.coordinator.llm_client.health_check()
            status = "[green]✓ Healthy[/green]" if health.get('healthy') else "[red]✗ Unhealthy[/red]"
            self.console.print(f"  LLM Backend: {status}")
            self.console.print(f"  Model: {health.get('model', 'N/A')}")
            if health.get('error'):
                self.console.print(f"  Error: [red]{health['error']}[/red]")
        else:
            self.console.print("  [yellow]LLM client not available[/yellow]")
