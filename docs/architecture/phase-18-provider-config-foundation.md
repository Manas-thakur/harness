# Phase 18: Provider Configuration Foundation

This phase starts Phi's durable provider configuration work without adding an
extension system.

The implementation lives in:

```text
src/phi_coding/provider_config.py
src/phi_coding/cli.py
src/phi_coding/tui/app.py
src/phi_coding/commands.py
src/phi_coding/session.py
```

## What was added

Phi now has a provider settings model under `phi_coding`:

```python
ProviderSettings
OpenAICompatibleProviderConfig
ProviderSelection
```

Settings are stored at:

```text
~/.phi/providers.json
```

If that file does not exist, Phi uses an OpenAI-compatible default:

```text
provider: openai
model: gpt-4.1-mini
api key env var: OPENAI_API_KEY
base URL env var: OPENAI_BASE_URL
timeout env var: OPENAI_TIMEOUT_SECONDS
retry env vars: OPENAI_MAX_RETRIES, OPENAI_MAX_RETRY_DELAY_SECONDS
```

API keys are not stored in the config file. Built-in providers use
`credential_name` to read keys from `~/.phi/credentials.json`; custom providers
without a credential name read the environment variable named by `api_key_env`.

## Example config

```json
{
  "default_provider": "local",
  "providers": [
    {
      "name": "local",
      "type": "openai-compatible",
      "base_url": "http://localhost:11434/v1",
      "api_key_env": "LOCAL_API_KEY",
      "models": ["qwen", "llama"],
      "default_model": "qwen",
      "timeout_seconds": 120,
      "max_retries": 2,
      "max_retry_delay_seconds": 0.5
    }
  ]
}
```

## Runtime resolution

Print mode and TUI startup now resolve provider/model selection from durable
settings:

```text
phi --provider local --model qwen
phi -p "review this" --provider local
```

When `--model` is omitted, Phi uses the configured provider's default model.
When `--provider` is omitted, Phi uses `default_provider`.

## CLI commands

Phi can list configured providers:

```text
phi providers
```

Phi can also create or update an OpenAI-compatible provider entry:

```text
phi --provider local \
  --base-url http://localhost:11434/v1 \
  --api-key-env LOCAL_API_KEY \
  --timeout-seconds 120 \
  --max-retries 2 \
  --max-retry-delay-seconds 0.5 \
  --model qwen \
  setup
```

The setup options are top-level options before the `setup` command word. This
preserves the Pi-style `phi "prompt"` form for starting the TUI with an initial
prompt while still adding a lightweight setup flow. Setup writes provider
metadata only; for custom providers it warns if the named API key environment
variable is not currently set.

Provider HTTP timeouts are configurable through `timeout_seconds` in
`~/.phi/providers.json`. The default OpenAI-compatible provider can also read
`OPENAI_TIMEOUT_SECONDS`. The configured value is passed to the HTTPX streaming
client instead of keeping timeout behavior hardcoded in the provider adapter.

Transient retry behavior is configurable through `max_retries` and
`max_retry_delay_seconds`, or through `OPENAI_MAX_RETRIES` and
`OPENAI_MAX_RETRY_DELAY_SECONDS` for the default provider. Phi retries transient
HTTP statuses such as 429 and 5xx responses, plus HTTP transport errors before
any partial stream content has been emitted.

## Slash commands

Slash commands expose the active model configuration:

```text
/model
/model <name>
/login
```

`/model <name>` switches the active model for future turns in the running
process when the model is known for the active provider.

In the TUI, `/model` opens an interactive picker. The picker can include models
from every configured provider, so selecting a model can switch the active
provider behind the scenes. The model command refreshes provider settings before
validating or showing choices. `/login` is the TUI path for adding or refreshing
a built-in provider, and it refreshes provider settings after credentials are
saved.

The same provider settings file can also store scoped models:

```json
{
  "scoped_models": [
    {"provider": "openai", "model": "gpt-5.5"},
    {"provider": "local", "model": "qwen"}
  ]
}
```

Phi treats these as TUI favorites. The coding session filters the stored list
against currently usable providers before exposing it, so stale entries remain
harmless in the JSON file. This mirrors Pi's scoped-model idea while keeping the
durable config in `phi_coding` and the reusable harness unaware of provider
settings.

## Boundary

Provider settings belong to `phi_coding`, not `phi_agent`.

The reusable harness still receives only a ready `ModelProvider` and a model
name. It does not know about Phi home, JSON config files, credentials,
environment variables, or CLI/TUI setup behavior.

## Limitations

Phase 18 intentionally kept setup minimal. Provider metadata was edited through
the CLI setup command, not an interactive TUI form. Later login work added
`~/.phi/credentials.json` for built-in provider API keys; custom providers still
use environment variables until Phi has a custom-provider credential form.

## Tests

The phase is covered by:

```text
tests/test_provider_config.py
tests/test_cli.py
tests/test_commands.py
tests/test_tui_app.py
```

The tests verify:

- missing config falls back to OpenAI-compatible defaults
- provider settings round-trip through `~/.phi/providers.json`
- provider setup and listing CLI behavior
- provider HTTP timeout and retry parsing plus runtime config forwarding
- default provider/model selection
- configured API key environment variables and stored credentials
- CLI provider/model forwarding
- TUI startup selection
- `/login` and `/model` command behavior
