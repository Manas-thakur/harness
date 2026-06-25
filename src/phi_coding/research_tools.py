"""Web/research tools: ``search_web``, ``fetch_url``, ``read_pdf``.

Provider-neutral `AgentTool`s that let the agent ground answers in real web
content and local PDFs instead of guessing. Blocking libraries (ddgs, pypdf,
and lxml parsing) run in worker threads via ``anyio.to_thread`` so the async
agent loop is never blocked; ``fetch_url`` uses httpx's native async client.

These keep menace's research capability on phi's typed, async tool protocol.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import anyio

from phi_agent.tools import AgentTool, AgentToolResult, ToolCancellationToken
from phi_agent.types import JSONValue
from phi_coding.tools import ToolDefinition, ToolInputError

MAX_RESEARCH_OUTPUT_CHARS = 6_000
DEFAULT_SEARCH_RESULTS = 8
FETCH_TIMEOUT_SECONDS = 20.0
_USER_AGENT = "Mozilla/5.0 (compatible; menace/1.0)"


def _truncate(text: str, limit: int = MAX_RESEARCH_OUTPUT_CHARS) -> str:
    if len(text) > limit:
        return text[:limit] + "\n\n… [truncated]"
    return text


def _str_arg(arguments: Mapping[str, JSONValue], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} must be a non-empty string")
    return value.strip()


def create_research_tools() -> list[AgentTool]:
    """Create the research tool set: search_web, fetch_url, read_pdf."""
    return [
        create_search_web_tool_definition().to_agent_tool(),
        create_fetch_url_tool_definition().to_agent_tool(),
        create_read_pdf_tool_definition().to_agent_tool(),
    ]


# --- search_web -------------------------------------------------------------


def _run_search(query: str, max_results: int) -> list[dict[str, str]] | None:
    """Blocking DDGS search. Returns None when no backend is installed."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
        except ImportError:
            return None
    with DDGS() as ddgs:
        return list(
            ddgs.text(query, region="wt-wt", safesearch="moderate", max_results=max_results)
        )


def create_search_web_tool_definition() -> ToolDefinition:
    """Create the `search_web` tool definition."""

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        query = _str_arg(arguments, "query")
        raw_max = arguments.get("max_results")
        max_results = int(raw_max) if isinstance(raw_max, (int, float)) else DEFAULT_SEARCH_RESULTS
        max_results = max(1, min(max_results, 20))

        try:
            results = await anyio.to_thread.run_sync(_run_search, query, max_results)
        except Exception as exc:  # noqa: BLE001 - surface backend/network errors
            return AgentToolResult(
                tool_call_id="", name="search_web", ok=False,
                content=f"Search failed (network or backend error): {exc}", error=str(exc),
            )

        if results is None:
            msg = "Web search backend not installed. Run: pip install ddgs"
            return AgentToolResult(tool_call_id="", name="search_web", ok=False,
                                   content=msg, error=msg)
        if not results:
            return AgentToolResult(
                tool_call_id="", name="search_web", ok=True,
                content=(f"No results found for: {query}. Try a simpler or differently "
                         "worded query; do not guess the answer."),
            )

        lines = [
            f"Search results for: {query}",
            "(Use fetch_url on a result's URL to read the full page before stating facts.)\n",
        ]
        for index, item in enumerate(results, 1):
            title = item.get("title", "")
            body = item.get("body") or item.get("description", "")
            url = item.get("href") or item.get("url", "")
            lines.extend([f"{index}. {title}", f"   {body}", f"   URL: {url}\n"])
        return AgentToolResult(
            tool_call_id="", name="search_web", ok=True,
            content=_truncate("\n".join(lines)), data={"count": len(results)},
        )

    return ToolDefinition(
        name="search_web",
        description=(
            "Search the web for current or factual information. Use this for anything you "
            "are unsure of or that may have changed recently — never guess at facts you "
            "could look up. Returns titles, snippets, and URLs; follow up with fetch_url to "
            "read a page before stating specifics."
        ),
        prompt_snippet="Search the web",
        prompt_guidelines=(
            "For anything current or factual you are unsure of, call search_web — never guess.",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
                "max_results": {"type": "integer", "description": "Results to return (default 8)."},
            },
            "required": ["query"],
        },
        executor=execute,
    )


# --- fetch_url --------------------------------------------------------------


def _html_to_text(html: str) -> str:
    """Extract readable text from HTML, dropping script/style/markup."""
    try:
        from lxml import html as lxml_html

        doc = lxml_html.fromstring(html)
        for bad in doc.xpath("//script | //style | //noscript"):
            parent = bad.getparent()
            if parent is not None:
                parent.remove(bad)
        text = doc.text_content()
    except Exception:  # noqa: BLE001 - fall back to a crude tag strip
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\n\s*\n\s*", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def create_fetch_url_tool_definition() -> ToolDefinition:
    """Create the `fetch_url` tool definition."""

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        url = _str_arg(arguments, "url")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        import httpx

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=FETCH_TIMEOUT_SECONDS,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - surface network/HTTP errors
            return AgentToolResult(tool_call_id="", name="fetch_url", ok=False,
                                   content=f"Error fetching {url}: {exc}", error=str(exc))

        text = await anyio.to_thread.run_sync(_html_to_text, response.text)
        if not text.strip():
            return AgentToolResult(tool_call_id="", name="fetch_url", ok=True,
                                   content=f"Fetched {url} but found no readable text.")
        return AgentToolResult(
            tool_call_id="", name="fetch_url", ok=True,
            content=_truncate(f"Content of {url}:\n\n{text}"), data={"url": url},
        )

    return ToolDefinition(
        name="fetch_url",
        description=(
            "Fetch a web page and return its readable text. Use this AFTER search_web to read "
            "a result's actual page before stating facts — never rely on snippets alone for "
            "specific claims."
        ),
        prompt_snippet="Fetch a web page",
        prompt_guidelines=(
            "After searching, fetch_url the most relevant result(s) and ground claims in the "
            "page content; cite the URLs you used.",
        ),
        input_schema={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The full URL to fetch."}},
            "required": ["url"],
        },
        executor=execute,
    )


# --- read_pdf ---------------------------------------------------------------


def _read_pdf(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def create_read_pdf_tool_definition() -> ToolDefinition:
    """Create the `read_pdf` tool definition."""

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        path = _str_arg(arguments, "path")
        from pathlib import Path

        if not Path(path).exists():
            raise ToolInputError(f"PDF not found: {path}")
        try:
            text = await anyio.to_thread.run_sync(_read_pdf, path)
        except ImportError:
            msg = "pypdf not installed. Run: pip install pypdf"
            return AgentToolResult(
                tool_call_id="", name="read_pdf", ok=False, content=msg, error=msg
            )
        except Exception as exc:  # noqa: BLE001 - surface parse errors
            return AgentToolResult(tool_call_id="", name="read_pdf", ok=False,
                                   content=f"Error reading PDF: {exc}", error=str(exc))
        if not text.strip():
            return AgentToolResult(tool_call_id="", name="read_pdf", ok=True,
                                   content=f"Read {path} but found no extractable text.")
        return AgentToolResult(tool_call_id="", name="read_pdf", ok=True,
                               content=_truncate(text), data={"path": path})

    return ToolDefinition(
        name="read_pdf",
        description="Extract text from a local PDF file.",
        prompt_snippet="Read a PDF",
        prompt_guidelines=(),
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path to the PDF file."}},
            "required": ["path"],
        },
        executor=execute,
    )
