"""Tests for the web/research tools (search_web, fetch_url, read_pdf)."""

import sys
import types
from pathlib import Path

import httpx
import pytest

from phi_coding.research_tools import (
    _html_to_text,
    create_fetch_url_tool_definition,
    create_read_pdf_tool_definition,
    create_research_tools,
    create_search_web_tool_definition,
)


def test_create_research_tools_names() -> None:
    assert [t.name for t in create_research_tools()] == ["search_web", "fetch_url", "read_pdf"]


# --- search_web -------------------------------------------------------------


def _install_fake_ddgs(monkeypatch, *, results=None, raise_exc=None) -> None:
    module = types.ModuleType("ddgs")

    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def text(self, query, max_results=8, **kwargs):
            if raise_exc:
                raise raise_exc
            return results or []

    module.DDGS = FakeDDGS
    monkeypatch.setitem(sys.modules, "ddgs", module)


@pytest.mark.anyio
async def test_search_web_returns_formatted_results(monkeypatch) -> None:
    _install_fake_ddgs(monkeypatch, results=[
        {"title": "F1 News", "body": "Verstappen won.", "href": "http://x"},
    ])
    tool = create_search_web_tool_definition()
    result = await tool.executor({"query": "latest f1"})
    assert result.ok
    assert "F1 News" in result.content
    assert "Verstappen won." in result.content
    assert "http://x" in result.content


@pytest.mark.anyio
async def test_search_web_empty(monkeypatch) -> None:
    _install_fake_ddgs(monkeypatch, results=[])
    result = await create_search_web_tool_definition().executor({"query": "nothing"})
    assert result.ok
    assert "No results found" in result.content


@pytest.mark.anyio
async def test_search_web_network_error(monkeypatch) -> None:
    _install_fake_ddgs(monkeypatch, raise_exc=RuntimeError("boom"))
    result = await create_search_web_tool_definition().executor({"query": "x"})
    assert not result.ok
    assert "Search failed" in result.content and "boom" in result.content


@pytest.mark.anyio
async def test_search_web_missing_backend(monkeypatch) -> None:
    # Make both ddgs and duckduckgo_search un-importable.
    monkeypatch.setitem(sys.modules, "ddgs", None)
    monkeypatch.setitem(sys.modules, "duckduckgo_search", None)
    result = await create_search_web_tool_definition().executor({"query": "x"})
    assert not result.ok
    assert "not installed" in result.content


@pytest.mark.anyio
async def test_search_web_requires_query() -> None:
    from phi_coding.tools import ToolInputError

    with pytest.raises(ToolInputError):
        await create_search_web_tool_definition().executor({"query": "  "})


# --- fetch_url --------------------------------------------------------------


def _install_fake_httpx(monkeypatch, *, html=None, raise_exc=None) -> None:
    class FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            if raise_exc:
                raise raise_exc
            return FakeResponse(html or "")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)


@pytest.mark.anyio
async def test_fetch_url_returns_readable_text(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        html="<html><body><script>evil()</script><p>Hello World</p></body></html>",
    )
    result = await create_fetch_url_tool_definition().executor({"url": "example.com"})
    assert result.ok
    assert "Hello World" in result.content
    assert "evil()" not in result.content


@pytest.mark.anyio
async def test_fetch_url_network_error(monkeypatch) -> None:
    _install_fake_httpx(monkeypatch, raise_exc=RuntimeError("neterr"))
    result = await create_fetch_url_tool_definition().executor({"url": "http://x"})
    assert not result.ok
    assert "Error fetching" in result.content and "neterr" in result.content


def test_html_to_text_strips_markup() -> None:
    text = _html_to_text("<h1>Title</h1><p>Body  text</p>")
    assert "Title" in text and "Body text" in text and "<" not in text


# --- read_pdf ---------------------------------------------------------------


@pytest.mark.anyio
async def test_read_pdf_extracts_text(monkeypatch, tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    module = types.ModuleType("pypdf")

    class FakePage:
        def extract_text(self):
            return "Page text here"

    class FakeReader:
        def __init__(self, path):
            self.pages = [FakePage()]

    module.PdfReader = FakeReader
    monkeypatch.setitem(sys.modules, "pypdf", module)

    result = await create_read_pdf_tool_definition().executor({"path": str(pdf)})
    assert result.ok
    assert "Page text here" in result.content


@pytest.mark.anyio
async def test_read_pdf_missing_file() -> None:
    from phi_coding.tools import ToolInputError

    with pytest.raises(ToolInputError):
        await create_read_pdf_tool_definition().executor({"path": "/no/such.pdf"})
