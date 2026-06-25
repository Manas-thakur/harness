# Phase 20: Installation and Configuration Docs

This phase starts Phi's packaging and installation polish.

The project already exposes the user-facing console command through:

```toml
[project.scripts]
phi = "phi_coding.cli:app"
```

This slice documents how to install and operate that command as a normal tool.

## What was added

New user-facing docs:

```text
docs/installation.md
docs/configuration.md
```

Updated docs:

```text
README.md
docs/getting-started.md
docs/index.md
docs/providers.md
mkdocs.yml
```

## Covered Workflows

The docs now cover:

- installing Phi with `uv tool install`
- installing Phi with `pipx`
- verifying the installed `phi` command
- first-run provider setup
- opening the TUI with `phi`
- running one prompt in print mode
- provider config under `~/.phi/providers.json`
- session storage under `~/.phi/sessions`
- skills and prompt template locations
- project context file discovery
- currently disabled shell completion

## Boundary

This phase does not change `phi_agent` or provider/runtime behavior. It makes
the current user-facing application install and configuration paths explicit.

## Tests

The docs slice is verified by:

```text
uv run phi --version
uv build
uv run --group docs mkdocs build --strict
```
