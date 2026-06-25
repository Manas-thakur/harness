# Installation

Phi is packaged as a Python console application named `phi`.

## Install With uv

From a checked-out copy of the repository:

```bash
uv tool install --editable .
```

From GitHub:

```bash
uv tool install git+https://github.com/manas-thakur/phi.git
```

Verify the installed command:

```bash
phi --version
```

## Install With pipx

```bash
pipx install git+https://github.com/manas-thakur/phi.git
```

## First Run

Phi starts the interactive Textual TUI when no prompt is provided:

```bash
phi
```

Passing a positional prompt also starts the TUI and submits that prompt as the
first turn:

```bash
phi "explain this repository"
```

For a one-shot print-mode prompt:

```bash
phi -p "explain this repository"
```

Print-mode prompts create indexed session entries under `~/.phi/sessions/` while
keeping stdout/stderr script-friendly.

Phi includes built-in provider entries for OpenAI, OpenAI Codex subscription,
Anthropic, OpenRouter, and Hugging Face Inference Providers. In the TUI, run
`/login` to see them, `/login openai` to save an API key, or
`/login openai-codex` to authenticate with a Codex subscription account.

Saved API keys and OAuth refresh credentials live in `~/.phi/credentials.json`
with private file permissions. For built-in providers added with `/login`, Phi
uses the credential saved in `credentials.json`. The `api_key_env` field in
`providers.json` is metadata for custom/env-based providers and does not
override a saved Phi login.

Optionally configure a custom provider:

```bash
phi --provider local \
  --base-url http://localhost:11434/v1 \
  --api-key-env LOCAL_API_KEY \
  --model qwen \
  setup
```

Custom providers still read the API key from the configured environment
variable, such as `LOCAL_API_KEY` in the example above.

Then run:

```bash
phi --provider local
```

## Shell Completion

Shell completion is not enabled yet. The Typer application is currently created
with completion disabled so the command surface can stay stable while Phi is
still moving through the roadmap.
