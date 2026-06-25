# Providers

Phi's provider layer lives in `phi_ai`.

Providers translate external model APIs into Phi's provider-neutral event stream.

## Ollama (local models)

Phi ships with a built-in `ollama` provider that targets a local
[Ollama](https://ollama.com) daemon. This is the default provider, so Phi works
out of the box with local models and **no API key**.

Prerequisites:

1. Install and start Ollama (`ollama serve` or the desktop app).
2. Pull a model, for example `ollama pull qwen2.5:7b`.

Phi auto-discovers installed models by querying Ollama's `/api/tags` endpoint,
so the model picker (`/model`) and `phi providers` list only what you have
pulled. The first installed model becomes the default.

Run:

```bash
phi -p "explain this repo"
```

Optionally override the Ollama base URL (defaults to `http://localhost:11434/v1`):

```bash
export OLLAMA_BASE_URL="http://localhost:11434/v1"
```

Ollama does not require an API key. If you set `OLLAMA_API_KEY`, Phi sends it
as the bearer token; otherwise it sends the placeholder `ollama`.

## OpenAI-compatible provider

Phi currently includes an OpenAI-compatible chat completions adapter.

Set:

```bash
export OPENAI_API_KEY="..."
```

Optionally set a custom compatible endpoint:

```bash
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

Optionally tune the HTTP timeout used by the default OpenAI-compatible provider:

```bash
export OPENAI_TIMEOUT_SECONDS="120"
```

Optionally tune transient request retries:

```bash
export OPENAI_MAX_RETRIES="2"
export OPENAI_MAX_RETRY_DELAY_SECONDS="0.5"
```

The provider uses `/chat/completions` with streaming enabled.

## OpenAI Codex Subscription Provider

Phi also includes an `openai-codex` provider for Codex / ChatGPT subscription
accounts. This is separate from the `openai` API-key provider.

In the TUI, run:

```text
/login openai-codex
```

Phi opens the OpenAI OAuth URL, listens for the local callback at
`http://localhost:1455/auth/callback`, and also accepts a pasted redirect URL or
authorization code as a fallback. Refreshable OAuth credentials are saved in
`~/.phi/credentials.json` with private file permissions.

The provider sends requests to the ChatGPT backend Codex Responses endpoint and
uses the OAuth access token plus the ChatGPT account id required by that API.
Expired access tokens are refreshed automatically before a model request.

## Durable Provider Config

Phi stores provider metadata in:

```text
~/.phi/providers.json
```

List configured providers:

```bash
phi providers
```

`phi providers` shows whether each provider will use a stored Phi credential,
an environment-variable fallback, or has missing credentials. Stored API keys
and OAuth credentials in `~/.phi/credentials.json` take precedence over
provider-specific environment variables such as `OPENAI_API_KEY`.

Create or update a provider:

```bash
phi --provider local \
  --base-url http://localhost:11434/v1 \
  --api-key-env LOCAL_API_KEY \
  --timeout-seconds 120 \
  --max-retries 2 \
  --max-retry-delay-seconds 0.5 \
  --model qwen \
  setup
```

Provider entries can also include `headers`, `timeout_seconds`, `max_retries`,
and `max_retry_delay_seconds` in `~/.phi/providers.json`. `headers` must be an
object with string keys and string values. Timeout must be greater than zero;
retry count and retry delay must be zero or greater.

Example:

```json
{
  "name": "huggingface",
  "type": "openai-compatible",
  "base_url": "https://router.huggingface.co/v1",
  "api_key_env": "HF_TOKEN",
  "credential_name": "huggingface",
  "models": ["openai/gpt-oss-120b"],
  "default_model": "openai/gpt-oss-120b",
  "headers": {
    "X-HF-Bill-To": "my-org"
  }
}
```

Run Phi with a configured provider:

```bash
phi --provider local
phi --provider local "summarize this project"
phi --provider local -p "summarize this project"
```

The positional prompt starts the TUI with an initial prompt. The `-p` form runs
non-interactive print mode.

Inside the TUI:

```text
/model
/model qwen
/login
/logout
```

`/model` opens the interactive model picker. The picker includes models from
configured providers, so selecting a model can also switch the active runtime
provider. The model flow refreshes provider settings before it validates or
shows choices. `/login` adds or refreshes a built-in provider, including
OAuth-backed providers such as `openai-codex`, and refreshes provider settings
after saving credentials. `/logout` opens a picker for providers with saved Phi
credentials, while `/logout <provider>` removes a specific saved credential. It
does not change environment variables, `providers.json`, billing, or defaults.

When Phi loads `~/.phi/providers.json`, it merges the current built-in model
catalog into built-in provider entries such as Hugging Face. Custom models and
headers in the file are preserved. If `credentials.json` already contains stored
credentials for a built-in provider that is missing from `providers.json`, Phi
adds that provider back in memory so a stale provider file does not hide saved
logins.

When Phi writes provider settings after `/login`, `/model`, or scoped-model
changes, it reloads the latest file first, applies the narrow requested change,
writes atomically, and keeps a best-effort `providers.json.bak` backup.

## Fake provider

Phi also includes `FakeProvider` for deterministic tests. It replays scripted provider events and never makes network requests.

It is used heavily by agent-loop, session, command, and TUI tests.
