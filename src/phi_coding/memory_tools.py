"""Model-driven memory tools: ``update_profile``, ``remember``, ``recall``.

These let the agent persist durable knowledge across sessions and look it back
up on demand. They are bound to a per-project `MemoryStore`; the profile written
via ``update_profile`` is also injected into every future session's system
prompt, so the agent recalls who the user is and what they're working on.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import anyio

from phi_agent.tools import AgentTool, AgentToolResult, ToolCancellationToken
from phi_agent.types import JSONValue
from phi_coding.memory import PROFILE_SECTIONS, MemoryStore, default_memory_path
from phi_coding.tools import ToolDefinition, ToolInputError


def create_memory_tools(
    *, cwd: str | Path | None = None, store: MemoryStore | None = None
) -> list[AgentTool]:
    """Create the memory tool set bound to the project's `MemoryStore`."""
    if store is None:
        root = Path.cwd() if cwd is None else Path(cwd)
        store = MemoryStore(default_memory_path(root))
    return [
        create_update_profile_tool_definition(store).to_agent_tool(),
        create_remember_tool_definition(store).to_agent_tool(),
        create_recall_tool_definition(store).to_agent_tool(),
    ]


def _str_arg(arguments: Mapping[str, JSONValue], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} must be a non-empty string")
    return value.strip()


def create_update_profile_tool_definition(store: MemoryStore) -> ToolDefinition:
    """Create the `update_profile` tool (durable, always-loaded profile)."""

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        content = _str_arg(arguments, "content")
        raw_section = arguments.get("section")
        section = (
            raw_section.strip() if isinstance(raw_section, str) and raw_section.strip() else "About"
        )
        message = await anyio.to_thread.run_sync(store.append_to_section, section, content)
        return AgentToolResult(tool_call_id="", name="update_profile", ok=True, content=message)

    return ToolDefinition(
        name="update_profile",
        description=(
            "Record durable information about the user or their project into always-loaded "
            "profile memory. Call this when the user states who they are, what they're working "
            f"on, or a lasting preference. Section is one of: {', '.join(PROFILE_SECTIONS)}."
        ),
        prompt_snippet="Save durable profile info",
        prompt_guidelines=(
            "When the user states durable facts about themselves or their project, call "
            "update_profile so you remember them in future sessions.",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The durable fact to record."},
                "section": {
                    "type": "string",
                    "description": f"One of: {', '.join(PROFILE_SECTIONS)} (default About).",
                },
            },
            "required": ["content"],
        },
        executor=execute,
    )


def create_remember_tool_definition(store: MemoryStore) -> ToolDefinition:
    """Create the `remember` tool (on-demand task facts)."""

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        fact = _str_arg(arguments, "fact")
        raw_key = arguments.get("key")
        key = raw_key.strip() if isinstance(raw_key, str) and raw_key.strip() else None
        message = await anyio.to_thread.run_sync(store.save_fact, fact, key)
        return AgentToolResult(tool_call_id="", name="remember", ok=True, content=message)

    return ToolDefinition(
        name="remember",
        description=(
            "Store a specific fact for later recall. Use for useful details that are not "
            "general profile info (kept on demand, not always loaded)."
        ),
        prompt_snippet="Remember a fact",
        prompt_guidelines=(),
        input_schema={
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "The fact to store."},
                "key": {"type": "string", "description": "Optional short key/id."},
            },
            "required": ["fact"],
        },
        executor=execute,
    )


def create_recall_tool_definition(store: MemoryStore) -> ToolDefinition:
    """Create the `recall` tool (search stored memory)."""

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        query = _str_arg(arguments, "query")
        matches = await anyio.to_thread.run_sync(store.search, query)
        if not matches:
            return AgentToolResult(
                tool_call_id="",
                name="recall",
                ok=True,
                content=f"No stored memory matches: {query}",
            )
        body = "\n".join(f"- {m}" for m in matches)
        return AgentToolResult(
            tool_call_id="", name="recall", ok=True, content=body, data={"count": len(matches)}
        )

    return ToolDefinition(
        name="recall",
        description="Search stored memory (profile + facts) for previously saved information.",
        prompt_snippet="Recall stored memory",
        prompt_guidelines=(
            "Before answering questions about the user or prior work, use recall to check "
            "what you already know.",
        ),
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to search for."}},
            "required": ["query"],
        },
        executor=execute,
    )
