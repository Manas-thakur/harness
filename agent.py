#!/usr/bin/env python3
"""
Local AI Research & Study Agent CLI
Main entry point for interacting with the agent system.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table

app = typer.Typer(help="Local AI Research & Study Agent")
console = Console()


@app.command("ask")
def ask(
    task: str = typer.Argument(..., help="Task or question for the agent"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
):
    """Ask the agent a question or give it a task."""
    console.print(Panel(f"[bold blue]Asking:[/bold blue] {task}", title="🤖 Agent"))
    
    with console.status("[bold green]Agent is thinking..."):
        try:
            from harness.coordinator import Coordinator
            
            coordinator = Coordinator()
            response = coordinator.process_input(task)
            
            # Save session transcript
            coordinator.save_session_transcript()
            
            console.print(Panel(response, title="💬 Response"))
            
        except Exception as e:
            console.print(f"[red]Error:[/red] {str(e)}")
            if debug:
                import traceback
                traceback.print_exc()


@app.command("dream")
def dream(
    sessions: int = typer.Option(3, "--sessions", "-s", help="Number of recent sessions to process")
):
    """Run batch memory consolidation (dreaming)."""
    console.print("[bold purple]🌙 Starting Dreaming Cycle...[/bold purple]")
    
    try:
        from harness.dreaming import DreamingEngine
        
        engine = DreamingEngine()
        result = engine.run_dreaming_cycle(max_sessions=sessions)
        
        if result:
            console.print(f"[green]✨ Dreaming complete![/green]")
            console.print(f"Output saved to: {result}")
            console.print("\n[yellow]Run 'agent activate <path>' to apply the new memory.[/yellow]")
        else:
            console.print("[yellow]No sessions found to consolidate.[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Error during dreaming:[/red] {str(e)}")


@app.command("activate")
def activate(
    dream_path: str = typer.Argument(..., help="Path to dream output file")
):
    """Activate a dream output, replacing current memory."""
    console.print(f"[bold]Activating dream:[/bold] {dream_path}")
    
    try:
        from harness.dreaming import DreamingEngine
        
        engine = DreamingEngine()
        success = engine.activate_dream(dream_path)
        
        if success:
            console.print("[green]✓ Memory activated successfully![/green]")
        else:
            console.print("[red]✗ Failed to activate dream.[/red]")
            
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("memory")
def show_memory():
    """View current agent memory."""
    try:
        from harness.memory import MemoryStore
        
        memory = MemoryStore()
        content = memory.read_active()
        
        console.print(Panel(content, title="🧠 Agent Memory"))
        
        # Show stats
        stats = memory.get_summary_stats()
        console.print(f"\n[dim]Tokens: {stats['token_count']} | Sections: {stats['section_count']} | Entries: {stats['entry_count']}[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("versions")
def list_versions():
    """List memory version snapshots."""
    try:
        from harness.versioning import VersioningSystem
        
        vs = VersioningSystem()
        snapshots = vs.list_snapshots()
        
        if not snapshots:
            console.print("[yellow]No snapshots found.[/yellow]")
            return
        
        table = Table(title="Memory Versions")
        table.add_column("Name", style="cyan")
        table.add_column("Created", style="magenta")
        table.add_column("Size", style="green")
        
        for snap in snapshots[:10]:  # Show last 10
            info = vs.get_snapshot_info(snap.name)
            table.add_row(
                snap.name,
                info['created_at'],
                f"{info['size_bytes']} bytes"
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("rollback")
def rollback(
    snapshot_name: str = typer.Argument(..., help="Snapshot name to restore")
):
    """Rollback memory to a previous version."""
    console.print(f"[bold]Rolling back to:[/bold] {snapshot_name}")
    
    try:
        from harness.versioning import VersioningSystem
        
        vs = VersioningSystem()
        restored = vs.rollback(snapshot_name)
        console.print(f"[green]✓ Restored to {snapshot_name}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("clone")
def clone_repo(
    url: str = typer.Argument(..., help="Git repository URL"),
    path: str = typer.Option("workspace/repo", "--path", "-p", help="Destination path")
):
    """Clone a Git repository to workspace."""
    console.print(f"[bold]Cloning:[/bold] {url}")
    
    try:
        from harness.tools import ToolRegistry
        
        tools = ToolRegistry()
        result = tools.execute("git_clone", {"url": url, "path": path})
        console.print(result)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("threads")
def list_threads():
    """List active agent threads."""
    try:
        from harness.agents import AGENT_REGISTRY
        
        table = Table(title="Agent Threads")
        table.add_column("Agent", style="cyan")
        table.add_column("State", style="magenta")
        table.add_column("Turns", style="green")
        table.add_column("Tokens", style="yellow")
        
        for agent_name, agent_class in AGENT_REGISTRY.items():
            agent = agent_class()
            status = agent.get_status()
            table.add_row(
                agent_name,
                status['thread_state'],
                str(status['turn_count']),
                str(status['token_count'])
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


@app.command("status")
def show_status():
    """Show overall agent system status."""
    try:
        from harness.coordinator import Coordinator
        
        coordinator = Coordinator()
        status = coordinator.get_status()
        
        console.print(Panel(
            f"""
Current Turn: {status['current_turn']}/{status['max_turns']}

Memory:
  - Tokens: {status['memory_stats']['token_count']}
  - Sections: {status['memory_stats']['section_count']}
  - Entries: {status['memory_stats']['entry_count']}
""",
            title="📊 Agent Status"
        ))
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")


if __name__ == "__main__":
    app()
