#!/usr/bin/env python3
"""
Terminal UI for the Local AI Agent — a single, opencode-style chat interface.

This is the one and only interactive surface for the agent. It wraps the
Coordinator, streams responses live, surfaces agent routing and tool calls,
and exposes management actions through slash commands. When Ollama is not
reachable it runs in an offline "mock" mode so the interface stays usable.
"""

import os
import sys
from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.rule import Rule
from rich import box

from harness.coordinator import Coordinator
from harness.llm_client import LocalLLMClient


APP_NAME = "harness"
VERSION = "0.1.0"


class AgentTUI:
    """Single-screen, streaming chat TUI for the agent fleet."""

    def __init__(self, model: str = None, mock: bool = None, max_turns: int = 20):
        self.console = Console()
        self.coordinator = Coordinator(
            model=model or os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
            max_turns=max_turns,
            mock=mock,
        )
        self.running = True
        self.message_count = 0

    # -- helpers ----------------------------------------------------------

    @property
    def llm(self) -> LocalLLMClient:
        return self.coordinator.llm

    def _backend_label(self) -> Text:
        if self.llm.mock:
            return Text("offline (mock)", style="bold yellow")
        return Text("ollama · connected", style="bold green")

    # -- rendering --------------------------------------------------------

    def render_banner(self):
        self.console.clear()
        title = Text()
        title.append("  ◆ ", style="bold cyan")
        title.append(APP_NAME, style="bold white")
        title.append(f"  v{VERSION}", style="dim")
        subtitle = Text("local AI research & study agent", style="dim italic")

        meta = Table.grid(padding=(0, 2))
        meta.add_column(justify="right", style="dim")
        meta.add_column()
        meta.add_row("model", Text(self.llm.model, style="cyan"))
        meta.add_row("backend", self._backend_label())
        meta.add_row("agents", Text("researcher · tutor · coder · dreamer", style="white"))

        body = Group(title, subtitle, Text(""), meta, Text(""),
                     Text("Type a message, or /help for commands.", style="dim"))
        self.console.print(Panel(body, border_style="cyan", box=box.ROUNDED,
                                 padding=(1, 2)))
        if self.llm.mock:
            self.console.print(
                "[yellow]⚠ Ollama is not reachable — running in offline mock mode. "
                f"Start Ollama and `ollama pull {self.llm.model}` for real answers.[/yellow]\n"
            )

    def render_user_message(self, text: str):
        self.console.print(
            Panel(Text(text, style="white"), title="[bold blue]you[/bold blue]",
                  title_align="left", border_style="blue", box=box.ROUNDED,
                  padding=(0, 1)))

    def status_footer(self):
        agent = self.coordinator.last_agent or "—"
        parts = (
            f"[dim]model[/dim] [cyan]{self.llm.model}[/cyan]   "
            f"[dim]agent[/dim] [magenta]{agent}[/magenta]   "
            f"[dim]turn[/dim] {self.coordinator.current_turn}/{self.coordinator.max_turns}   "
            f"[dim]msgs[/dim] {self.message_count}"
        )
        self.console.print(Rule(style="grey30"))
        self.console.print(parts)
        self.console.print()

    # -- the streaming turn ----------------------------------------------

    def handle_message(self, text: str):
        self.message_count += 1
        self.render_user_message(text)

        route_info = {"agent": None}
        tool_events = []
        buffer = {"text": ""}

        def on_event(kind, data):
            if kind == "route":
                route_info["agent"] = data.get("agent")
            elif kind == "tool":
                tool_events.append(data)
            elif kind == "blocked":
                self.console.print(f"[red]⛔ Blocked: {data.get('reason')}[/red]")
            elif kind == "error":
                self.console.print(f"[red]⚠ {data.get('message')}[/red]")

        def build_renderable():
            header = Text()
            agent = route_info["agent"]
            if agent:
                header.append(f"◆ {agent}", style="bold magenta")
            else:
                header.append("◆ routing…", style="dim magenta")
            pieces = [header]
            for t in tool_events:
                tag = "🔧" if not t.get("blocked") else "⛔"
                line = Text(f"  {tag} {t['name']}", style="yellow")
                preview = str(t.get("result", "")).strip().splitlines()
                if preview:
                    line.append(f"  → {preview[0][:80]}", style="dim")
                pieces.append(line)
            if buffer["text"]:
                pieces.append(Text(""))
                pieces.append(Markdown(buffer["text"]))
            return Panel(Group(*pieces), title="[bold magenta]agent[/bold magenta]",
                         title_align="left", border_style="magenta",
                         box=box.ROUNDED, padding=(0, 1))

        def on_token(chunk):
            buffer["text"] += chunk
            live.update(build_renderable())

        with Live(build_renderable(), console=self.console, refresh_per_second=12,
                  vertical_overflow="visible") as live:
            try:
                response = self.coordinator.chat(text, on_event=on_event, on_token=on_token)
            except Exception as e:
                response = f"Error: {e}"
                self.console.print(f"[red]{response}[/red]")
            if not buffer["text"]:
                buffer["text"] = response
            live.update(build_renderable())

        self.status_footer()

    # -- slash commands ---------------------------------------------------

    def handle_command(self, raw: str) -> bool:
        """Return True if the app should keep running."""
        parts = raw.strip().split()
        cmd = parts[0].lower().lstrip("/")
        args = parts[1:]

        if cmd in ("quit", "exit", "q"):
            return False
        elif cmd == "help":
            self._cmd_help()
        elif cmd == "memory":
            self._cmd_memory()
        elif cmd == "agents":
            self._cmd_agents()
        elif cmd == "tools":
            self._cmd_tools()
        elif cmd == "status":
            self._cmd_status()
        elif cmd == "model":
            self._cmd_model(args)
        elif cmd == "dream":
            self._cmd_dream(args)
        elif cmd in ("clear", "new"):
            self._cmd_clear()
        else:
            self.console.print(f"[red]Unknown command: /{cmd}[/red] — try [cyan]/help[/cyan]")
        return True

    def _cmd_help(self):
        t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        t.add_column(style="cyan", no_wrap=True)
        t.add_column(style="white")
        rows = [
            ("/help", "Show this help"),
            ("/memory", "View the agent's long-term memory"),
            ("/agents", "List specialist agents and their tools"),
            ("/tools", "List available tools"),
            ("/status", "Show system status"),
            ("/model [name]", "Show or switch the active model"),
            ("/dream [n]", "Consolidate the last n sessions into memory"),
            ("/clear", "Reset the conversation and clear the screen"),
            ("/quit", "Exit"),
        ]
        for k, v in rows:
            t.add_row(k, v)
        self.console.print(Panel(t, title="[bold]commands[/bold]", border_style="cyan",
                                 box=box.ROUNDED))

    def _cmd_memory(self):
        try:
            content = self.coordinator.memory.read_active()
            self.console.print(Panel(Markdown(content or "_empty_"),
                                     title="[bold]🧠 memory[/bold]",
                                     border_style="green", box=box.ROUNDED))
        except Exception as e:
            self.console.print(f"[red]Could not read memory: {e}[/red]")

    def _cmd_agents(self):
        t = Table(box=box.ROUNDED, border_style="magenta")
        t.add_column("agent", style="bold magenta")
        t.add_column("tools", style="white")
        for name, agent in self.coordinator.agents.items():
            t.add_row(name, ", ".join(agent.allowed_tools))
        self.console.print(t)

    def _cmd_tools(self):
        tools = self.coordinator.tools.list_tools()
        self.console.print(Panel(", ".join(sorted(tools)),
                                 title="[bold]🔧 tools[/bold]",
                                 border_style="yellow", box=box.ROUNDED))

    def _cmd_status(self):
        try:
            status = self.coordinator.get_status()
        except Exception as e:
            self.console.print(f"[red]status error: {e}[/red]")
            return
        mem = status.get("memory_stats", {})
        t = Table.grid(padding=(0, 2))
        t.add_column(justify="right", style="dim")
        t.add_column()
        t.add_row("model", self.llm.model)
        t.add_row("backend", self._backend_label())
        t.add_row("turn", f"{status['current_turn']}/{status['max_turns']}")
        t.add_row("memory mode", str(mem.get("mode", "—")))
        if mem.get("mode") == "legacy":
            t.add_row("memory tokens", str(mem.get("token_count", 0)))
            t.add_row("sections", str(mem.get("section_count", 0)))
        self.console.print(Panel(t, title="[bold]📊 status[/bold]", border_style="blue",
                                 box=box.ROUNDED))

    def _cmd_model(self, args):
        if not args:
            installed = self.llm.list_models()
            body = Text(f"current: {self.llm.model}\n", style="cyan")
            if installed:
                body.append("installed: " + ", ".join(installed), style="dim")
            else:
                body.append("no models reported (Ollama offline)", style="dim")
            self.console.print(Panel(body, title="[bold]model[/bold]",
                                     border_style="cyan", box=box.ROUNDED))
            return
        new_model = args[0]
        self.coordinator.llm = LocalLLMClient(model=new_model)
        mode = "offline mock" if self.llm.mock else "connected"
        self.console.print(f"[green]✓ switched to[/green] [cyan]{new_model}[/cyan] [dim]({mode})[/dim]")

    def _cmd_dream(self, args):
        sessions = int(args[0]) if args and args[0].isdigit() else 3
        self.console.print(f"[magenta]🌙 dreaming over last {sessions} session(s)…[/magenta]")
        try:
            from harness.dreaming import DreamingEngine
            result = DreamingEngine().run_dreaming_cycle(max_sessions=sessions)
            if result:
                self.console.print(f"[green]✓ dream saved:[/green] {result}")
                self.console.print("[dim]Review it, then `agent activate <path>` to apply.[/dim]")
            else:
                self.console.print("[yellow]No sessions found to consolidate yet.[/yellow]")
        except Exception as e:
            self.console.print(f"[red]dreaming failed: {e}[/red]")

    def _cmd_clear(self):
        for agent in self.coordinator.agents.values():
            agent.reset_thread()
        self.coordinator.current_turn = 0
        self.coordinator.session_transcript = []
        self.message_count = 0
        self.render_banner()

    # -- main loop --------------------------------------------------------

    def prompt(self) -> str:
        try:
            return self.console.input("[bold cyan]›[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            return "/quit"

    def run(self):
        self.render_banner()
        while self.running:
            try:
                user_input = self.prompt()
            except KeyboardInterrupt:
                break
            if not user_input:
                continue
            if user_input.startswith("/"):
                self.running = self.handle_command(user_input)
                continue
            try:
                self.handle_message(user_input)
            except KeyboardInterrupt:
                self.console.print("\n[yellow]⏹ interrupted[/yellow]\n")
                continue

        # Persist the session transcript on exit so dreaming has material.
        try:
            if self.coordinator.session_transcript:
                self.coordinator.save_session_transcript()
        except Exception:
            pass
        self.console.print("\n[dim]bye 👋[/dim]")


def run_tui(model: str = None, mock: bool = None):
    """Launch the TUI. Used as the default entry point."""
    AgentTUI(model=model, mock=mock).run()


if __name__ == "__main__":
    run_tui()
