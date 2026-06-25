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

# prompt_toolkit powers the Claude-Code-style pinned input box (history, slash
# autocomplete, keybindings). It is optional: when absent we fall back to a
# plain line prompt so the TUI still runs in minimal/offline environments.
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style
    from prompt_toolkit.patch_stdout import patch_stdout
    _HAS_PTK = True
except ImportError:  # pragma: no cover - exercised only without prompt_toolkit
    _HAS_PTK = False


APP_NAME = "menace"
VERSION = "0.1.0"

# Slash commands offered by the autocomplete menu (command -> one-line help).
SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/memory": "View the agent's long-term memory",
    "/agents": "List specialist agents and their tools",
    "/tools": "List available tools",
    "/status": "Show system status",
    "/model": "Show or switch model (local or Ollama Cloud)",
    "/dream": "Consolidate recent sessions into memory",
    "/remember": "Store a fact in long-term memory",
    "/recall": "Search long-term memory",
    "/clear": "Reset the conversation and clear the screen",
    "/quit": "Exit",
}


def slash_completions(text: str):
    """Return ``(command, help)`` pairs matching a partial slash command.

    Completion applies only to the command token itself: an empty string or a
    leading ``/`` with no space yet. Once the user types a space (arguments),
    nothing is suggested. Kept module-level so it is unit-testable without
    prompt_toolkit installed.
    """
    if " " in text:
        return []
    if text and not text.startswith("/"):
        return []
    return [(cmd, help_) for cmd, help_ in SLASH_COMMANDS.items()
            if cmd.startswith(text)]


if _HAS_PTK:
    class _SlashCompleter(Completer):
        """prompt_toolkit completer that pops slash commands after ``/``."""

        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            for cmd, help_ in slash_completions(text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=help_,
                )


class AgentTUI:
    """Single-screen, streaming chat TUI for the agent fleet."""

    def __init__(self, model: str = None, mock: bool = None, max_turns: int = 20):
        self.console = Console()
        self.coordinator = Coordinator(
            model=model or os.environ.get("OLLAMA_MODEL", "qwen3:8b"),
            max_turns=max_turns,
            mock=mock,
        )
        self.running = True
        self.message_count = 0
        self.session = self._build_session()

    # -- input layer (prompt_toolkit) -------------------------------------

    def _build_session(self):
        """Create the pinned-input prompt session, or None if unavailable."""
        if not _HAS_PTK:
            return None

        kb = KeyBindings()

        @kb.add("c-l")
        def _(event):
            # Ctrl+L: clear the conversation and redraw the banner.
            event.app.exit(result="/clear")

        style = Style.from_dict({
            "prompt": "bold cyan",
            "bottom-toolbar": "bg:#222222 #888888",
            "bottom-toolbar.name": "bold #5fd7ff",
        })

        return PromptSession(
            history=InMemoryHistory(),
            completer=_SlashCompleter(),
            complete_while_typing=True,
            key_bindings=kb,
            bottom_toolbar=self._bottom_toolbar,
            style=style,
            placeholder=HTML('<style fg="#666666">Type a message, or / for commands…</style>'),
        )

    def _bottom_toolbar(self):
        """Pinned status line below the input box."""
        if self.llm.mock:
            backend = "offline·mock"
        elif self.llm.is_cloud:
            backend = "cloud"
        else:
            backend = "local"
        agent = self.coordinator.last_agent or "—"
        return HTML(
            f' <b><style fg="#5fd7ff">{APP_NAME}</style></b> '
            f' model <b>{self.llm.model}</b> '
            f' backend <b>{backend}</b> '
            f' agent <b>{agent}</b> '
            f' turn <b>{self.coordinator.current_turn}/{self.coordinator.max_turns}</b> '
        )

    # -- helpers ----------------------------------------------------------

    @property
    def llm(self) -> LocalLLMClient:
        return self.coordinator.llm

    def _backend_label(self) -> Text:
        if self.llm.mock:
            return Text("offline (mock)", style="bold yellow")
        if self.llm.is_cloud:
            return Text("ollama cloud · connected", style="bold magenta")
        return Text("ollama local · connected", style="bold green")

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
        elif cmd == "remember":
            self._cmd_remember(args)
        elif cmd == "recall":
            self._cmd_recall(args)
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
            ("/model [name]", "Show or switch model (local or -cloud)"),
            ("/dream [n] [--activate]", "Consolidate recent sessions into memory"),
            ("/remember <fact>", "Store a fact in long-term memory"),
            ("/recall <query>", "Search long-term memory"),
            ("/clear", "Reset the conversation and clear the screen"),
            ("/quit", "Exit"),
        ]
        for k, v in rows:
            t.add_row(k, v)
        keys = Text()
        keys.append("keys  ", style="dim")
        keys.append("↑/↓", style="cyan"); keys.append(" history   ", style="dim")
        keys.append("\\ + Enter", style="cyan"); keys.append(" newline   ", style="dim")
        keys.append("Ctrl+C", style="cyan"); keys.append(" cancel   ", style="dim")
        keys.append("Ctrl+L", style="cyan"); keys.append(" clear   ", style="dim")
        keys.append("Ctrl+D", style="cyan"); keys.append(" exit", style="dim")
        self.console.print(Panel(Group(t, Text(""), keys), title="[bold]commands[/bold]",
                                 border_style="cyan", box=box.ROUNDED))

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
            body = Text()
            body.append("current: ", style="dim")
            body.append(f"{self.llm.model}", style="cyan")
            body.append("  (cloud)\n" if self.llm.is_cloud else "  (local)\n",
                        style="magenta" if self.llm.is_cloud else "green")
            if installed:
                body.append("local models: ", style="dim")
                body.append(", ".join(installed) + "\n")
            else:
                body.append("no local models reported (daemon offline?)\n", style="dim")
            body.append("\nswitch with ", style="dim")
            body.append("/model <name>", style="cyan")
            body.append("  — any model on the target host works.\n", style="dim")
            body.append("cloud: ", style="magenta")
            body.append("run `ollama signin` (or set OLLAMA_API_KEY), then pick a "
                        "cloud model, e.g. ", style="dim")
            body.append("/model qwen3-coder:480b-cloud", style="cyan")
            self.console.print(Panel(body, title="[bold]model[/bold]",
                                     border_style="cyan", box=box.ROUNDED))
            return

        new_model = args[0]
        # Preserve the tuned context window across the switch; host/API key are
        # resolved from the environment (and the -cloud suffix) automatically.
        self.coordinator.llm = LocalLLMClient(model=new_model, num_ctx=self.llm.num_ctx)
        if self.llm.mock:
            if self.llm.is_cloud and not self.llm.api_key:
                hint = "offline — cloud needs `ollama signin` or OLLAMA_API_KEY"
            else:
                hint = "offline mock — backend unreachable"
        else:
            hint = "cloud" if self.llm.is_cloud else "local"
        self.console.print(
            f"[green]✓ switched to[/green] [cyan]{new_model}[/cyan] [dim]({hint})[/dim]")

    def _cmd_dream(self, args):
        activate = "--activate" in args
        nums = [a for a in args if a.isdigit()]
        sessions = int(nums[0]) if nums else 3
        # Persist the current session so dreaming has fresh material.
        try:
            if self.coordinator.session_transcript:
                self.coordinator.save_session_transcript()
        except Exception:
            pass
        self.console.print(f"[magenta]🌙 dreaming over last {sessions} session(s)…[/magenta]")
        try:
            from harness.dreaming import DreamingEngine
            engine = DreamingEngine()
            result = engine.run_dreaming_cycle(max_sessions=sessions)
            if result:
                self.console.print(f"[green]✓ dream saved:[/green] {result}")
                if activate:
                    if engine.activate_dream(result):
                        self.console.print("[green]✓ memory activated (snapshot saved first).[/green]")
                    else:
                        self.console.print("[red]✗ activation failed.[/red]")
                else:
                    self.console.print("[dim]Review it, then `/dream --activate` or `agent activate <path>` to apply.[/dim]")
            else:
                self.console.print("[yellow]No sessions found to consolidate yet.[/yellow]")
        except Exception as e:
            self.console.print(f"[red]dreaming failed: {e}[/red]")

    def _cmd_remember(self, args):
        fact = " ".join(args).strip()
        if not fact:
            self.console.print("[yellow]usage: /remember <fact>[/yellow]")
            return
        result = self.coordinator.tools.execute("remember", {"fact": fact})
        self.console.print(f"[green]🧠 {result}[/green]")

    def _cmd_recall(self, args):
        query = " ".join(args).strip()
        if not query:
            self.console.print("[yellow]usage: /recall <query>[/yellow]")
            return
        result = self.coordinator.tools.execute("recall", {"query": query})
        self.console.print(Panel(result or "_nothing found_",
                                 title="[bold]🧠 recall[/bold]",
                                 border_style="green", box=box.ROUNDED))

    def _cmd_clear(self):
        for agent in self.coordinator.agents.values():
            agent.reset_thread()
        self.coordinator.reset_conversation()
        self.message_count = 0
        self.render_banner()

    # -- main loop --------------------------------------------------------

    def _read_line(self, continuation: bool = False) -> str:
        """Read a single physical line from the pinned box (or fallback)."""
        if self.session is None:
            mark = "[bold cyan]…[/bold cyan] " if continuation else "[bold cyan]›[/bold cyan] "
            try:
                return self.console.input(mark)
            except EOFError:
                return "/quit"
            except KeyboardInterrupt:
                return ""
        marker = '<style fg="#5fd7ff">… </style>' if continuation else '<style fg="#5fd7ff">› </style>'
        try:
            # patch_stdout keeps rich output above the pinned input box.
            with patch_stdout(raw=True):
                text = self.session.prompt(HTML(marker))
            return text if text is not None else ""
        except EOFError:
            return "/quit"          # Ctrl+D
        except KeyboardInterrupt:
            return ""               # Ctrl+C at the prompt: cancel the line

    def prompt(self) -> str:
        """Read user input, honoring trailing-backslash line continuation.

        Returns the assembled input, or sentinel strings: ``/quit`` on EOF
        (Ctrl+D) and ``""`` on an empty Ctrl+C (cancel, stay in the loop).
        """
        line = self._read_line()
        if line in ("", "/quit"):
            return line.strip()
        # Backslash at end of a line means "continue on the next line".
        while line.rstrip().endswith("\\"):
            cont = self._read_line(continuation=True)
            if cont == "/quit":
                break
            line = line.rstrip()[:-1] + "\n" + cont
        return line.strip()

    def run(self):
        self.render_banner()
        while self.running:
            user_input = self.prompt()
            if not user_input:
                continue
            if user_input.startswith("/"):
                self.running = self.handle_command(user_input)
                continue
            try:
                self.handle_message(user_input)
            except KeyboardInterrupt:
                # Ctrl+C during generation cancels the turn without quitting.
                self.console.print("\n[yellow]⏹ generation cancelled[/yellow]\n")
                continue

        # Persist the session transcript on exit so dreaming has material.
        try:
            if self.coordinator.session_transcript:
                self.coordinator.save_session_transcript()
        except Exception:
            pass
        self._auto_consolidate_on_exit()
        self.console.print("\n[dim]bye 👋[/dim]")

    def _auto_consolidate_on_exit(self):
        """Close the self-improvement loop: consolidate this session into memory.

        Best-effort and flag-guarded (set AGENT_AUTO_DREAM=0 to disable). Snapshots
        memory via VersioningSystem before activating, so it's always recoverable.
        Skipped in offline mock mode and when there was nothing to consolidate.
        """
        if os.environ.get("AGENT_AUTO_DREAM", "1").lower() in ("0", "false", "no"):
            return
        if self.llm.mock or not self.coordinator.session_transcript:
            return
        try:
            from harness.dreaming import DreamingEngine
            self.console.print("\n[magenta]🌙 consolidating this session into memory…[/magenta]")
            engine = DreamingEngine()
            result = engine.run_dreaming_cycle(max_sessions=3)
            if result and engine.activate_dream(result):
                self.console.print("[green]✓ memory updated (snapshot saved first).[/green]")
        except Exception as e:
            self.console.print(f"[dim]consolidation skipped: {e}[/dim]")


def run_tui(model: str = None, mock: bool = None):
    """Launch the TUI. Used as the default entry point."""
    AgentTUI(model=model, mock=mock).run()


if __name__ == "__main__":
    run_tui()
