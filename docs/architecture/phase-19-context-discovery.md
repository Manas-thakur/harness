# Phase 19: Project Context Discovery and Reload

This phase adds Phi's project instruction discovery and reload command. It stays in
`phi_coding`, beside resources, commands, and session startup.

The implementation lives in:

```text
src/phi_coding/context.py
src/phi_coding/session.py
src/phi_coding/cli.py
src/phi_coding/commands.py
```

## What was added

Phi now discovers markdown instruction files automatically and inserts them into
the existing `ProjectContextFile` system-prompt section.

The current discovery order is:

```text
~/.phi/AGENTS.md
~/.agents/AGENTS.md
<project root>/AGENTS.md
<project root>/.../<cwd>/AGENTS.md
<cwd>/.phi/AGENTS.md
<cwd>/.agents/AGENTS.md
```

The project root is the nearest ancestor containing a common project marker such
as `.git`, `pyproject.toml`, `uv.lock`, `setup.py`, or `package.json`. If no
marker exists, Phi treats the session cwd as the project root.

## System Prompt Integration

Both normal `CodingSession` startup and non-interactive print mode pass
discovered context files into:

```python
BuildSystemPromptOptions(context_files=...)
```

That preserves the Phase 10 prompt boundary:

```text
phi_coding discovers local files
phi_coding.system_prompt formats them
phi_agent receives only a ready system string
```

`phi_agent` still has no dependency on local resource discovery, Phi home,
project paths, slash commands, Rich, or Textual.

## Slash Command

Phi now has:

```text
/context
/reload
```

`/context` lists the active project context files in the running session.

`/reload` refreshes Phi-owned resources for future turns:

- skills
- prompt templates
- project context files
- resource diagnostics

When the session is using Phi's generated system prompt, reload rebuilds the
harness system string only when the resources that feed that prompt changed.
The transcript and session tree are left untouched.

`/reload` does not refresh provider configuration. Provider/model settings are
refreshed by the provider-specific flows that use them, such as `/login` after
saving credentials and `/model` before validating choices or opening the model
picker.

`/status` and `/resources` also include the current context-file count.

## Boundary

Reload is a `phi_coding` operation. It updates the coding-session environment
around the harness, then gives the harness a rebuilt system string for future
turns when needed. `phi_agent` does not know where skills, prompts, or context
files come from.

## Tests

The phase is covered by:

```text
tests/test_context.py
tests/test_coding_session.py
tests/test_cli.py
tests/test_commands.py
```

The tests verify:

- user, project, nested, `.phi`, and `.agents` context discovery
- discovered context included in session system prompts
- discovered context included in print-mode system prompts
- `/context`, `/status`, and `/resources` command output
- `/reload` command output
- reload updating resources and the next-turn system prompt only when prompt
  inputs changed
