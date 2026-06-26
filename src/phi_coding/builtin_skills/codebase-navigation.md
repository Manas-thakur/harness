---
description: Build an accurate mental model of an unfamiliar codebase before reading or changing it.
---

# Codebase Navigation

Use this when you need to understand how a project is structured or where a
behavior lives, before editing anything.

## Method

1. **Map the layout.** Use `ls` at the root, then `glob` (e.g. `**/*.py`,
   `**/*.ts`) to see where source, tests, and config live. Read the README,
   `pyproject.toml`/`package.json`, and any `AGENTS.md`/`CONTRIBUTING.md` first —
   they explain intent and conventions.
2. **Find entry points.** Locate `main`, CLI definitions, server/app setup, or
   exported package APIs. These anchor the rest of the system.
3. **Search, don't guess.** Use `grep` to find where a symbol, string, route, or
   error message is defined and used. Follow definitions to their call sites and
   call sites back to definitions.
4. **Trace flow.** Pick the one path most relevant to the task and follow data
   and control through it: input → transformation → output. Note the key types
   and boundaries between layers.
5. **Read tests.** Tests document expected behavior and edge cases faster than
   prose. Read the tests for the area you will touch.

## Output

- Summarize the architecture in a few sentences: the layers, where the relevant
  logic lives (with `path:line` references), and how the pieces connect.
- Call out conventions you must follow (naming, error handling, typing, test
  style) so later changes match the surrounding code.

## Rules

- Prefer `grep`/`glob`/`ls` over `bash` for exploration — they are faster and
  skip noise directories.
- Reference concrete `path:line` locations; never describe code you have not
  actually read.
- Build understanding before editing. A wrong mental model produces wrong edits.
