"""Ollama local-model discovery helpers."""

from dataclasses import dataclass

from httpx import get

DEFAULT_OLLAMA_TAGS_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class OllamaModel:
    """One locally installed Ollama model with its capabilities."""

    name: str
    supports_tools: bool


def ollama_tags_url(base_url: str) -> str:
    """Return the native ``/api/tags`` URL for an OpenAI-compatible Ollama base URL."""
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/v1"):
        trimmed = trimmed[: -len("/v1")]
    return f"{trimmed}/api/tags"


def discover_ollama_models(
    base_url: str,
    *,
    timeout_seconds: float = DEFAULT_OLLAMA_TAGS_TIMEOUT_SECONDS,
) -> list[str]:
    """Return the names of models installed in the local Ollama daemon.

    Returns an empty list if Ollama is not reachable or returns an unexpected
    payload. This is best-effort: callers should fall back to a configured
    default model when discovery yields nothing.
    """
    return [model.name for model in discover_ollama_models_with_capabilities(base_url)]


def discover_ollama_models_with_capabilities(
    base_url: str,
    *,
    timeout_seconds: float = DEFAULT_OLLAMA_TAGS_TIMEOUT_SECONDS,
) -> list[OllamaModel]:
    """Return installed Ollama models with their tool-support capabilities.

    Returns an empty list if Ollama is not reachable or returns an unexpected
    payload. This is best-effort: callers should fall back to a configured
    default model when discovery yields nothing.
    """
    try:
        response = get(ollama_tags_url(base_url), timeout=timeout_seconds)
    except Exception:
        return []
    if response.status_code >= 400:
        return []
    try:
        payload = response.json()
    except ValueError:
        return []
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    result: list[OllamaModel] = []
    for entry in models:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        capabilities = entry.get("capabilities")
        supports_tools = isinstance(capabilities, list) and "tools" in capabilities
        result.append(OllamaModel(name=name.strip(), supports_tools=supports_tools))
    return result


def model_supports_tools(
    model_name: str,
    base_url: str,
    *,
    timeout_seconds: float = DEFAULT_OLLAMA_TAGS_TIMEOUT_SECONDS,
) -> bool | None:
    """Return whether an installed Ollama model supports tool calling.

    Returns ``True``/``False`` when the model is found. Returns ``None`` when
    Ollama is unreachable or the model is not installed, so callers can decide
    whether to warn or proceed optimistically.
    """
    for model in discover_ollama_models_with_capabilities(
        base_url, timeout_seconds=timeout_seconds
    ):
        if model.name == model_name:
            return model.supports_tools
    return None
