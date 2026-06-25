"""Tests for Ollama Cloud support + model-agnostic selection (offline)."""
import pytest

import harness.llm_client as llc
from harness.llm_client import LocalLLMClient


needs_ollama = pytest.mark.skipif(llc.ollama is None,
                                  reason="ollama package not installed")


class TestCloudDetection:
    def test_local_model_is_not_cloud(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        c = LocalLLMClient(model="qwen3:8b", mock=True)
        assert c.is_cloud is False
        assert c.host == "http://localhost:11434"

    def test_cloud_suffix_is_cloud(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        c = LocalLLMClient(model="qwen3-coder:480b-cloud", mock=True)
        assert c.is_cloud is True
        # With no explicit host, a -cloud model targets the cloud host.
        assert c.host == LocalLLMClient.CLOUD_HOST

    def test_explicit_cloud_host(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        c = LocalLLMClient(model="anything", host="https://ollama.com", mock=True)
        assert c.is_cloud is True

    def test_env_host_overrides_default(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")
        c = LocalLLMClient(model="qwen3-coder:480b-cloud", mock=True)
        # Explicit local host wins (cloud model via local proxy/signin).
        assert c.host == "http://localhost:11434"

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_API_KEY", "secret")
        c = LocalLLMClient(model="qwen3:8b", mock=True)
        assert c.api_key == "secret"


@needs_ollama
class TestAuthHeaders:
    def _capture_client(self, monkeypatch):
        captured = {}

        class FakeClient:
            def __init__(self, **kwargs):
                captured.update(kwargs)
            def list(self):
                return {"models": []}

        monkeypatch.setattr(llc.ollama, "Client", FakeClient)
        return captured

    def test_api_key_sets_auth_header(self, monkeypatch):
        captured = self._capture_client(monkeypatch)
        LocalLLMClient(model="gpt-oss:120b-cloud", api_key="KEY", mock=True)
        assert captured["headers"]["Authorization"] == "Bearer KEY"
        assert captured["host"] == LocalLLMClient.CLOUD_HOST

    def test_no_key_no_headers(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
        captured = self._capture_client(monkeypatch)
        LocalLLMClient(model="qwen3:8b", mock=True)
        assert "headers" not in captured


class TestModelSwitchPreservesCtx:
    def test_num_ctx_carried_on_switch(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        c1 = LocalLLMClient(model="qwen3:8b", num_ctx=12345, mock=True)
        # Mirror how the TUI rebuilds the client on /model.
        c2 = LocalLLMClient(model="qwen3-coder:480b-cloud", num_ctx=c1.num_ctx, mock=True)
        assert c2.num_ctx == 12345
        assert c2.is_cloud is True
