"""Local text embeddings via Ollama, used for semantic memory recall.

This keeps menace's zero-setup, no-API-key promise: embeddings are computed by
the same local Ollama the agent already uses, through its native ``/api/embed``
endpoint. Every entry point is best-effort and offline-safe — when Ollama is not
running, the embedding model is missing, or anything else fails, the functions
return ``None`` so callers can fall back to plain substring matching.
"""

from __future__ import annotations

import math
import os

from phi_ai.env import DEFAULT_OLLAMA_BASE_URL

DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_EMBED_TIMEOUT_SECONDS = 10.0


def native_embeddings_url(base_url: str | None = None) -> str:
    """Return the Ollama native ``/api/embed`` URL for the configured host."""
    base = base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
    base = base.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    return f"{base}/api/embed"


async def embed_texts(
    texts: list[str],
    *,
    base_url: str | None = None,
    model: str = DEFAULT_EMBED_MODEL,
    timeout: float = DEFAULT_EMBED_TIMEOUT_SECONDS,
) -> list[list[float]] | None:
    """Embed `texts` with a local Ollama model, or return ``None`` on any failure.

    Returns one float vector per input text, in order. A ``None`` result means
    embeddings are unavailable (Ollama down, model not pulled, malformed
    response); callers should degrade gracefully rather than treat it as an
    error.
    """
    if not texts:
        return []

    import httpx

    url = native_embeddings_url(base_url)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json={"model": model, "input": list(texts)})
            response.raise_for_status()
            payload = response.json()
    except Exception:  # noqa: BLE001 - any failure means "no embeddings", not an error
        return None

    embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        return None

    vectors: list[list[float]] = []
    for vector in embeddings:
        if not isinstance(vector, list) or not all(isinstance(x, (int, float)) for x in vector):
            return None
        vectors.append([float(x) for x in vector])
    return vectors


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity of two equal-length vectors (0.0 if invalid)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
