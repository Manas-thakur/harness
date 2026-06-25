# Getting Started

This page explains how to install Phi, run the TUI, and work on the project.

## Requirements

Phi targets the Python version declared in `pyproject.toml` and uses `uv` for
dependency management.

## Install As a Tool

From GitHub:

```bash
uv tool install git+https://github.com/manas-thakur/phi.git
```

From a local checkout:

```bash
uv tool install --editable .
```

Verify the installed command:

```bash
phi --version
```

## Local Development Setup

```bash
uv sync --dev --group docs
```

## Verify the CLI

```bash
uv run phi --version
```

Expected output:

```text
phi 0.1.0
```

## Configure a Provider

Phi includes built-in provider entries for OpenAI, OpenAI Codex subscription,
Anthropic, OpenRouter, and Hugging Face Inference Providers. In the TUI, run
`/login` to see the list, `/login openai` to save an API key, or
`/login openai-codex` to authenticate with a Codex subscription account.

Provider metadata is written to `~/.phi/providers.json`. API keys and OAuth
refresh credentials saved with `/login` are written to `~/.phi/credentials.json`
with private file permissions. For built-in providers added with `/login`, Phi
uses the credential saved in `credentials.json`. The `api_key_env` field in
`providers.json` is metadata for custom/env-based providers and does not
override a saved Phi login.

To add a custom OpenAI-compatible provider:

```bash
uv run phi --provider local \
  --base-url http://localhost:11434/v1 \
  --api-key-env LOCAL_API_KEY \
  --model qwen \
  setup
```

## Open the TUI

```bash
uv run phi
```

Installed as a tool:

```bash
phi
```

Phi stores indexed sessions under `~/.phi/sessions/`.

## Run an Initial Prompt in the TUI

```bash
uv run phi "explain this repository"
```

This opens the interactive TUI and submits the prompt as the first turn.

For a one-shot print-mode prompt, use `-p`:

```bash
uv run phi -p "explain this repository"
```

Print-mode prompts are non-interactive, but they still use the shared
coding-session environment. Phi stores their session entries under
`~/.phi/sessions/`.

## Run tests and checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Run the documentation site locally

```bash
uv run --group docs mkdocs serve
```

Then open:

```text
http://127.0.0.1:8000
```

## Build the documentation site

```bash
uv run --group docs mkdocs build
```

The generated static website is written to `site/`.

## Deployment

Documentation is deployed to GitHub Pages from the `main` branch using the workflow in:

```text
.github/workflows/docs.yml
```

The public site is configured for:

```text
https://manas-thakur.github.io/phi/
```
