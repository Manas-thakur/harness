<p align="center">
  <img src="docs/assets/phi-header.svg" alt="Phi — a Python coding-agent harness inspired by Pi" width="100%" />
</p>

<p align="center">
  <strong>A minimalist coding-agent harness in Python, inspired by Pi and built as a teaching project.</strong>
</p>

<p align="center">
  <a href="https://manas-thakur.github.io/phi/">Documentation</a>
  ·
  <a href="docs/getting-started.md">Getting started</a>
  ·
  <a href="docs/architecture/index.md">Architecture notes</a>
</p>

---

## What is Phi?

Phi is a Python implementation of the minimalist coding-agent harness architecture
popularized by **Pi**. It is both:

1. a usable terminal coding agent, and
2. a readable, phase-by-phase reference implementation for learning how coding
   agents are assembled.

The project intentionally keeps the core pieces small and explicit: model
providers stream events, an agent loop turns those events into tool execution and
transcript updates, a reusable harness owns state, and the coding app adds local
files, shell tools, sessions, skills, commands, and terminal frontends.

```text
phi_ai       provider/model streaming layer
phi_agent    portable agent harness, loop, tools, events, sessions
phi_coding   CLI app, resources, skills, commands, sessions, UI integration
```

The central design boundary is:

```text
AgentHarness = reusable agent brain
AgentSession = coding-agent environment
TUI          = one possible frontend
```

Phi should make the architecture legible. If you want to understand how a coding
agent works without starting from a large production codebase, this repository is
for you.

## Why Phi exists

Phi is being built as an effort to teach how to create coding agents.

The philosophy is:

- **Small layers beat magic.** Each package has a clear job and can be explained
  independently.
- **Events are the contract.** The agent harness emits provider-neutral events;
  renderers and TUIs consume them.
- **The core stays portable.** `phi_agent` does not depend on Textual, Rich,
  shell config directories, slash commands, or application-specific resources.
- **Tools are ordinary typed functions.** File and shell capabilities are exposed
  through explicit schemas and deterministic result objects.
- **Sessions are durable and inspectable.** Phi stores append-only JSONL session
  transcripts under `~/.phi/sessions/`.
- **Documentation follows implementation.** The project is developed in small,
  documented phases so readers can trace how the system grows.

Pi is the design inspiration; Phi is the Python learning path.

## Current capabilities

Phi currently includes:

- an installable `phi` console command
- a Textual interactive TUI
- non-interactive print mode for one-shot prompts
- OpenAI-compatible, Anthropic, OpenAI Codex subscription, OpenRouter, and
  Hugging Face provider support through provider configuration
- provider retry/backoff events and thinking/reasoning deltas
- built-in local coding tools: `read`, `write`, `edit`, and `bash`
- durable per-project sessions and session resume
- session tree branching and HTML/JSONL export
- slash commands, model picker, theme picker, and autocomplete
- skills, prompt templates, and `AGENTS.md` project-context discovery
- context accounting, manual compaction, and optional automatic compaction
- Rich/plain/json/transcript rendering paths for print-mode output
- a deterministic fake provider used by tests

Phi is still evolving. Expect the command surface and internals to improve as the
roadmap progresses.

## Install

Phi targets the Python version declared in `pyproject.toml` and uses
[`uv`](https://docs.astral.sh/uv/) for the recommended workflow.

Install from GitHub:

```bash
uv tool install git+https://github.com/manas-thakur/phi.git
phi --version
```

Install from a local checkout:

```bash
git clone https://github.com/manas-thakur/phi.git
cd phi
uv tool install --editable .
phi --version
```

For development:

```bash
uv sync --dev --group docs
uv run phi --version
```

## First run

Start the interactive terminal UI:

```bash
phi
```

Start the TUI and submit the first prompt immediately:

```bash
phi "explain this repository"
```

Run a one-shot non-interactive prompt:

```bash
phi -p "summarize the architecture"
```

Choose a configured provider/model:

```bash
phi --provider openai --model gpt-4.1 "review this codebase"
phi --provider local --model qwen -p "list the main modules"
```

Use another working directory for coding tools:

```bash
phi --cwd /path/to/project "find the CLI entry point"
```

## Configure a model provider

The easiest path is from inside the TUI:

```text
/login
/login openai
/login openai-codex
/logout
/logout openai
/model
```

`/login` can save API-key credentials for built-in providers or authenticate an
OpenAI Codex subscription account with OAuth. Credentials are stored in
`~/.phi/credentials.json` with private file permissions. Provider metadata lives
in `~/.phi/providers.json`. `/logout` removes only credentials saved in Phi's
`credentials.json`; environment variables and provider configuration are
unchanged.

You can also configure an OpenAI-compatible provider from the CLI:

```bash
phi --provider local \
  --base-url http://localhost:11434/v1 \
  --api-key-env LOCAL_API_KEY \
  --model qwen \
  setup
```

Then run:

```bash
export LOCAL_API_KEY="..."
phi --provider local
```

Useful provider commands:

```bash
phi providers
```

See [docs/providers.md](docs/providers.md) and
[docs/configuration.md](docs/configuration.md) for details.

## Working in the TUI

Common slash commands:

| Command | Purpose |
| --- | --- |
| `/login [provider]` | Save or refresh provider credentials. |
| `/logout [provider]` | Remove Phi-saved provider credentials. |
| `/model` | Choose the active provider/model. |
| `/scoped-models` | Pick models available for quick cycling. |
| `/session` | Show session and context information. |
| `/resume [session-id]` | Resume a previous session. |
| `/tree` | Branch from a previous session entry. |
| `/name <new name>` | Rename the current session. |
| `/compact <summary>` | Replace active context with a manual summary. |
| `/export [--format html\|jsonl] [destination]` | Export the current session. |
| `/reload` | Reload local resources and project context. |
| `/theme [name]` | Show or set the TUI theme. |
| `/hotkeys` | Show common keyboard shortcuts. |
| `/quit` | Exit the session. |

Important TUI behavior:

- Click anywhere in the main TUI to return keyboard focus to the prompt input.

Common shortcuts:

| Shortcut | Action |
| --- | --- |
| `Enter` | Submit prompt. |
| `Shift+Enter` | Insert newline. |
| `Alt+Enter` | Queue a follow-up while the agent is running. |
| `Esc` | Cancel active run. |
| `Ctrl+K` | Open slash-command completions. |
| `Ctrl+R` | Open session picker. |
| `Shift+Tab` | Cycle thinking mode. |
| `Ctrl+T` | Toggle thinking-token display. |
| `Ctrl+O` | Collapse or expand tool output. |
| `Ctrl+P` | Cycle scoped models. |
| `Ctrl+D` | Quit. |

## Sessions, resources, and files

Phi stores durable app state in your home directory:

```text
~/.phi/providers.json       provider metadata
~/.phi/credentials.json     saved API keys and OAuth credentials
~/.phi/tui.json             TUI theme/keybinding settings
~/.phi/sessions/            append-only JSONL session transcripts
~/.phi/skills/              user Phi skills
~/.phi/prompts/             user prompt templates
~/.phi/AGENTS.md            user Phi instructions
```

Phi also reads user-level `.agents` resources and project-local resources from
the active working directory, including `AGENTS.md`, `.phi/`, and `.agents/`
locations. This lets a project teach Phi how it should behave without changing
Phi's core harness.

## Use Phi as a library

Phi's reusable brain lives in `phi_agent`:

```python
from phi_agent import AgentHarness, AgentHarnessConfig

harness = AgentHarness(
    AgentHarnessConfig(
        provider=provider,
        model="my-model",
        system="You are a helpful coding agent.",
        tools=tools,
    )
)

async for event in harness.prompt("Explain this package"):
    print(event)
```

That harness is deliberately independent of the CLI/TUI. You can build another
frontend by consuming the same event stream.

## Development

Set up the repository:

```bash
uv sync --dev --group docs
```

Run checks:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Run Phi locally:

```bash
uv run phi
uv run phi -p "explain this repo"
```

Run the documentation site:

```bash
uv run --group docs mkdocs serve
```

Then open `http://127.0.0.1:8000`.

## Documentation map

- [Getting Started](docs/getting-started.md)
- [Installation](docs/installation.md)
- [Configuration and Files](docs/configuration.md)
- [Providers](docs/providers.md)
- [Architecture](docs/01-architecture.md)
- [Architecture phase notes](docs/architecture/index.md)
- [Agent Loop](docs/agent-loop.md)
- [Agent Harness](docs/harness.md)
- [Tools](docs/03-tools.md)
- [Sessions](docs/04-sessions.md)
- [Building a Custom TUI](docs/custom-tui.md)
- [Roadmap](docs/00-roadmap.md)

## Project status

Phi is under active development. The docs under `docs/architecture/` record the
completed phases.

The goal is not to hide complexity. The goal is to make each part of a coding
agent visible, testable, and understandable.
