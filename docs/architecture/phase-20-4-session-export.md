# Phase 20.4: Session Export and Visualization

Phase 20.4 adds a durable way to inspect Phi sessions outside the TUI.

## What was added

Phi can export any indexed session id or JSONL session file to a standalone
HTML document:

```bash
phi export <session-id>
phi export <session-id> session.html
phi export <session-id> --format jsonl
phi export ~/.phi/sessions/<project>/<session-id>.jsonl
```

When no destination is provided, `phi export` writes to the current working
directory instead of Phi's internal session storage directory. Interactive
sessions expose the same export flow through:

```text
/export [--format html|jsonl] [destination]
```

The export contains two coordinated views:

- a session tree that preserves parent-child relationships, branches, leaf
  pointers, and the active branch path
- a storage-order transcript/details view for messages, tool calls, tool
  results, compactions, labels, model changes, thinking changes, and custom
  entries

The generated file is self-contained HTML and CSS, so it can be opened without
running Phi or the Textual app.

## Why it exists

Phi sessions are append-only trees, not a single flat chat log. That matters for
future fork and branch workflows because multiple candidate branches can share
the same root. A plain transcript would hide that shape and make it hard to
debug replay, compaction, or branch selection.

The exporter keeps the visualization in `phi_coding` because it is an
application workflow over persisted session data. The reusable `phi_agent`
session models remain provider-neutral and frontend-neutral.

## How it maps to Pi

Pi has an HTML session export flow for inspecting conversation state outside the
interactive interface. Phi mirrors the core product behavior while keeping the
implementation smaller: the exporter renders static HTML from the existing
`SessionEntry` JSONL records instead of adding a separate client-side app.

## How to test it

Run the focused tests:

```bash
uv run pytest tests/test_session_export.py tests/test_cli.py -k export
```

Run the full gate before shipping:

```bash
uv run pytest
uv run ruff check src tests
uv run mypy
uv run --group docs mkdocs build --strict
```
