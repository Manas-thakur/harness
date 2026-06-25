"""Tests for tool schema generation and web search (offline / mocked)."""
import sys
import types
import pytest
from harness.tools import ToolRegistry, TOOL_SCHEMAS


class TestToolSchemas:
    def test_get_schemas_shape(self):
        tr = ToolRegistry()
        schemas = tr.get_schemas(["search_web"])
        assert len(schemas) == 1
        fn = schemas[0]
        assert fn["type"] == "function"
        assert fn["function"]["name"] == "search_web"
        assert "query" in fn["function"]["parameters"]["properties"]

    def test_get_schemas_scopes_and_skips_dangling(self):
        tr = ToolRegistry()
        # `summarize` is an allowed-tool name with no registration/schema.
        schemas = tr.get_schemas(["search_web", "summarize", "update_profile"])
        names = [s["function"]["name"] for s in schemas]
        assert "search_web" in names
        assert "update_profile" in names
        assert "summarize" not in names

    def test_every_schema_is_registered(self):
        tr = ToolRegistry()
        for name in TOOL_SCHEMAS:
            assert name in tr.tools, f"schema {name} has no registered tool"


class TestWebSearch:
    def _install_fake_ddgs(self, monkeypatch, results=None, raise_exc=None):
        """Install a fake `ddgs` module exposing a DDGS context manager."""
        mod = types.ModuleType("ddgs")

        class FakeDDGS:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def text(self, query, max_results=5, **kwargs):
                if raise_exc:
                    raise raise_exc
                return results or []

        mod.DDGS = FakeDDGS
        monkeypatch.setitem(sys.modules, "ddgs", mod)

    def test_search_returns_results(self, monkeypatch):
        self._install_fake_ddgs(monkeypatch, results=[
            {"title": "F1 News", "body": "Verstappen won.", "href": "http://x"},
        ])
        tr = ToolRegistry()
        out = tr.execute("search_web", {"query": "latest f1"})
        assert "F1 News" in out and "Verstappen won." in out and "http://x" in out

    def test_search_empty(self, monkeypatch):
        self._install_fake_ddgs(monkeypatch, results=[])
        tr = ToolRegistry()
        out = tr.execute("search_web", {"query": "nothing"})
        assert "No results found" in out

    def test_search_network_error(self, monkeypatch):
        self._install_fake_ddgs(monkeypatch, raise_exc=RuntimeError("boom"))
        tr = ToolRegistry()
        out = tr.execute("search_web", {"query": "x"})
        assert "Search failed" in out and "boom" in out

    def test_search_empty_query(self, monkeypatch):
        self._install_fake_ddgs(monkeypatch, results=[])
        tr = ToolRegistry()
        out = tr.execute("search_web", {"query": "   "})
        assert "no search query" in out.lower()
