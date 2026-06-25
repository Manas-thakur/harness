# Phi Agent Architecture

Phi is a Python implementation of **Pi's minimalist coding-agent harness**. It replicates Pi's core separation of concerns — a portable agent brain, a coding-specific environment, and an interchangeable UI layer — built incrementally with documented phases and deterministic tests at each step.

---

## Mental Model

Pi's design draws a clean line between three responsibilities:

```
AgentHarness   →   the reusable agent brain (loop, tools, events)
AgentSession   →   the coding-agent environment (files, shell, state)
TUI            →   one possible frontend among many
```

Phi preserves that line. Nothing in the agent brain knows about terminals, file paths, or Rich/Textual. The TUI is a consumer, not a collaborator.

---

## Package Structure

Phi is split into three packages, each with a defined scope:

```
phi_ai        Provider and model layer — streaming, retries, API adapters
phi_agent     Portable agent harness — loop, tool protocol, events, sessions
phi_coding    CLI application — resources, skills, commands, TUI integration
```

**The critical constraint:** `phi_agent` must stay independent of `phi_coding`. It cannot import from `phi_coding`, cannot reference CLI paths or session file locations, and cannot depend on Textual or Rich. If the agent harness needs something from the app layer, that is a design smell — push it back through events or inject it via a dependency.

```
phi_ai ──────────────────────────────────────────┐
                                                  ▼
phi_agent   [loop] → [tools] → [events] ──────► consumers
                                                  ▲
phi_coding  [CLI] [TUI] [resources] ─────────────┘
```

---

## TUI Architecture

The interactive terminal UI is built with **Textual**, but lives entirely behind an adapter boundary.

The harness never renders — it emits events. The UI layer subscribes to those events and renders them however it likes. This means you can run Phi with a plain `print` loop, a Rich renderer, or the full Textual app, and the agent brain does not change.

```
AgentHarness
    │
    │  emits: ToolCallEvent, StreamChunkEvent, ErrorEvent, ...
    ▼
EventBus
    ├── PrintAdapter     (phase 1 — no dependencies)
    ├── RichAdapter      (phase 2 — Rich only)
    └── TextualAdapter   (phase 3 — full interactive TUI)
```

**Phase priority for UI work:**
1. Print-mode CLI — proves the loop works with zero rendering overhead
2. Rich renderers — readable output for daily use
3. Textual interactive app — the full experience

Do not introduce Textual into `phi_agent` at any phase. The adapter boundary is not optional.

---

## Development Workflow

### Work in phases

Each phase has a single coherent goal. Finish it, document it, test it, then move on. Mixing concerns across phases makes the architecture harder to reason about and test.

### Keep commits atomic

One commit = one thing: a feature, a fix, a refactor, a docs update, or a cleanup. A commit that does all of these is harder to review and harder to revert.

### Write tests before expanding

Add behavioral tests before adding new capabilities. Use fake providers and fake tools — the agent loop tests should be deterministic and require no network access.

### Run everything through `uv`

```bash
uv run pytest
uv run python -m phi_coding ...
```

Using `uv` ensures all commands run inside the project environment with the correct dependencies.

### Prefer explicit over clever

Simple, typed abstractions over framework-heavy designs. The codebase should be readable by someone unfamiliar with the project.

---

## Python Guidelines

- **Python version:** use whatever is declared in `pyproject.toml`
- **Core types:** prefer typed dataclasses or Pydantic/msgspec models for messages, events, tools, and sessions — avoid raw dicts at the boundary between layers
- **Async:** keep async/sync boundaries explicit; do not silently mix them
- **Testing:** fake providers and fake tools for all agent-loop tests — no live API calls in CI
- **Provider neutrality:** `phi_agent` must not assume any specific provider's API shape or behavior

---

## Documentation

Every substantial phase should leave a doc under `docs/` that covers:

- **What was added** — the concrete change
- **Why it exists** — the problem it solves or the constraint it enforces
- **How it maps to Pi's design** — where it sits in the AgentHarness / AgentSession / TUI model
- **How to use or test it** — a runnable example or test command

Write for a reader who understands Python but is new to agent harness design. The docs are part of the architecture, not an afterthought.
