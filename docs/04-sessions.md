# 04 — Sessions

Sessions preserve conversations and agent state across runs.

## Design

Phi uses an append-only session tree. Instead of mutating old state, Phi appends entries and reconstructs state by replaying them.

The low-level implementation lives in:

```text
src/phi_agent/session/
```

## Entry types

- `message`
- `model_change`
- `thinking_level_change`
- `compaction`
- `branch_summary`
- `label`
- `leaf`
- `session_info`
- `custom`

## Current capabilities

Phi can now:

- serialize and deserialize session entries as JSONL
- append entries to local session files
- read session files in order
- reconstruct linear session state
- reconstruct a root-to-leaf branch path
- load a `phi_coding.CodingSession` that restores messages and persists new runs

## Durable message boundary

`CodingSession` treats `MessageEndEvent` as the durable-message boundary. When the harness emits a completed message, the coding session appends that message to storage immediately instead of waiting for the whole agent run to finish.

This mirrors Pi's session model and matters for interactive UIs:

- the first user prompt is branchable while the assistant is still responding
- queued steering and follow-up messages become durable when they are injected
- cancellation or process failure preserves completed messages
- the TUI can read tree state that matches the active run

Each persisted message is followed by a `leaf` entry pointing at that message. The leaf entries form an append-only history of the active branch pointer.

Empty sessions are still deferred: loading a new session prepares initial metadata in memory, but Phi does not create the transcript file until the first durable session entry is appended. The first append materializes the pending `session_info`, model, and thinking-level entries before writing the message.

## Boundary

Low-level session primitives belong in `phi_agent`. File locations, slash commands, and coding-agent workflows belong in `phi_coding`.

`CodingSession` is the first `phi_coding` layer on top of the low-level primitives. It wires storage, `AgentHarness`, cwd, and coding tools together while leaving richer commands and resource loading for later phases.
