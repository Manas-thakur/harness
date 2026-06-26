"""Tests for local embedding helpers used by semantic memory recall."""

import pytest

from phi_coding.embeddings import cosine_similarity, embed_texts, native_embeddings_url


def test_native_embeddings_url_strips_openai_v1_suffix() -> None:
    assert native_embeddings_url("http://localhost:11434/v1") == "http://localhost:11434/api/embed"
    assert native_embeddings_url("http://host:1234") == "http://host:1234/api/embed"
    assert native_embeddings_url("http://host:1234/v1/") == "http://host:1234/api/embed"


def test_cosine_similarity_basic() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


@pytest.mark.anyio
async def test_embed_texts_empty_returns_empty_without_network() -> None:
    assert await embed_texts([]) == []


@pytest.mark.anyio
async def test_embed_texts_returns_none_when_backend_unreachable() -> None:
    # No Ollama at this port; the helper must degrade to None rather than raise.
    result = await embed_texts(["hello"], base_url="http://127.0.0.1:9", timeout=0.2)
    assert result is None
