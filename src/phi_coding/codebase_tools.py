"""Read-only codebase exploration tools: ``glob``, ``grep``, ``ls``.

These give the research + coding agent fast, structured ways to navigate a local
project without shelling out: ``glob`` finds files by pattern, ``grep`` searches
file contents by regular expression, and ``ls`` lists a directory. All three are
read-only, so the agent loop can run them concurrently, and they prune common
noise directories (``.git``, ``node_modules``, virtualenvs, caches) by default.

They complement the built-in ``read``/``write``/``edit``/``bash`` tools and
activate the system prompt's "prefer grep/find/ls over bash for exploration"
guidance.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator, Mapping
from pathlib import Path

from phi_agent.tools import AgentTool, AgentToolResult, ToolCancellationToken
from phi_agent.types import JSONValue
from phi_coding.tools import ToolDefinition, ToolInputError, format_size

DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".eggs",
        ".idea",
        "dist",
        "build",
    }
)

GREP_MATCH_LIMIT = 200
GLOB_MATCH_LIMIT = 300
LS_ENTRY_LIMIT = 500
GREP_LINE_PREVIEW_CHARS = 300
GREP_MAX_FILE_BYTES = 5 * 1024 * 1024


def create_codebase_tools(*, cwd: str | Path | None = None) -> list[AgentTool]:
    """Create the read-only codebase exploration tool set (glob, grep, ls)."""
    root = Path.cwd() if cwd is None else Path(cwd)
    return [
        create_glob_tool_definition(cwd=root).to_agent_tool(),
        create_grep_tool_definition(cwd=root).to_agent_tool(),
        create_ls_tool_definition(cwd=root).to_agent_tool(),
    ]


# --- shared helpers ---------------------------------------------------------


def _str_arg(arguments: Mapping[str, JSONValue], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} must be a non-empty string")
    return value.strip()


def _optional_str_arg(arguments: Mapping[str, JSONValue], key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"{key} must be a non-empty string when provided")
    return value.strip()


def _optional_int_arg(arguments: Mapping[str, JSONValue], key: str) -> int | None:
    value = arguments.get(key)
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, int):
        raise ToolInputError(f"{key} must be an integer")
    return value


def _bool_arg(arguments: Mapping[str, JSONValue], key: str) -> bool:
    value = arguments.get(key)
    return bool(value) if isinstance(value, bool) else False


def _resolve_path(value: str | None, *, cwd: Path) -> Path:
    if value is None:
        return cwd
    path = Path(value).expanduser()
    return path if path.is_absolute() else cwd / path


def _is_ignored(relative: Path, ignore_dirs: frozenset[str]) -> bool:
    return any(part in ignore_dirs for part in relative.parts)


def _walk_files(
    base: Path,
    *,
    ignore_dirs: frozenset[str],
) -> Iterator[Path]:
    """Yield files under ``base`` (depth-first), pruning ignored directories."""
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(name for name in dirnames if name not in ignore_dirs)
        for filename in sorted(filenames):
            yield Path(dirpath) / filename


def _display_path(path: Path, *, cwd: Path) -> str:
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return path.as_posix()


# --- glob -------------------------------------------------------------------


def create_glob_tool_definition(*, cwd: str | Path | None = None) -> ToolDefinition:
    """Create the `glob` tool: find files by glob pattern, ignoring noise dirs."""
    root = Path.cwd() if cwd is None else Path(cwd)

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        pattern = _str_arg(arguments, "pattern")
        base = _resolve_path(_optional_str_arg(arguments, "path"), cwd=root)
        if not base.exists():
            raise ToolInputError(f"Path not found: {base}")
        if not base.is_dir():
            raise ToolInputError(f"Path is not a directory: {base}")

        try:
            found = sorted(base.glob(pattern))
        except (ValueError, NotImplementedError) as exc:
            raise ToolInputError(
                f"Invalid glob pattern {pattern!r}: {exc}. Use a relative pattern such as "
                "'**/*.py' and pass an absolute directory via 'path' instead."
            ) from exc

        matches: list[str] = []
        truncated = False
        for match in found:
            if not match.is_file():
                continue
            try:
                relative = match.relative_to(base)
            except ValueError:
                relative = match
            if _is_ignored(relative, DEFAULT_IGNORE_DIRS):
                continue
            matches.append(_display_path(match, cwd=root))
            if len(matches) >= GLOB_MATCH_LIMIT:
                truncated = True
                break

        if not matches:
            return AgentToolResult(
                tool_call_id="",
                name="glob",
                ok=True,
                content=f"No files match pattern {pattern!r} under {_display_path(base, cwd=root)}",
            )
        body = "\n".join(matches)
        if truncated:
            body += f"\n\n[Showing first {GLOB_MATCH_LIMIT} matches; narrow the pattern for more.]"
        return AgentToolResult(
            tool_call_id="",
            name="glob",
            ok=True,
            content=body,
            data={"count": len(matches), "truncated": truncated},
        )

    return ToolDefinition(
        name="glob",
        description=(
            "Find files by glob pattern (e.g. '**/*.py', 'src/**/test_*.py'). Returns matching "
            "file paths relative to the working directory. Ignores .git, node_modules, "
            "virtualenvs, and cache directories. Use this to locate files instead of find."
        ),
        prompt_snippet="Find files by glob pattern",
        prompt_guidelines=(
            "Use glob to locate files by name/pattern before reading or editing them.",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern, e.g. '**/*.py'. Supports ** for recursion.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search from (default: working directory).",
                },
            },
            "required": ["pattern"],
        },
        executor=execute,
        read_only=True,
    )


# --- grep -------------------------------------------------------------------


def create_grep_tool_definition(*, cwd: str | Path | None = None) -> ToolDefinition:
    """Create the `grep` tool: regex search across file contents."""
    root = Path.cwd() if cwd is None else Path(cwd)

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        raw_pattern = _str_arg(arguments, "pattern")
        flags = re.IGNORECASE if _bool_arg(arguments, "case_insensitive") else 0
        try:
            regex = re.compile(raw_pattern, flags)
        except re.error as exc:
            raise ToolInputError(f"Invalid regular expression: {exc}") from exc

        base = _resolve_path(_optional_str_arg(arguments, "path"), cwd=root)
        if not base.exists():
            raise ToolInputError(f"Path not found: {base}")
        glob_filter = _optional_str_arg(arguments, "glob")
        max_results = _optional_int_arg(arguments, "max_results") or GREP_MATCH_LIMIT
        max_results = max(1, min(max_results, GREP_MATCH_LIMIT))

        files = [base] if base.is_file() else _walk_files(base, ignore_dirs=DEFAULT_IGNORE_DIRS)
        lines: list[str] = []
        match_count = 0
        truncated = False
        for file_path in files:
            if glob_filter is not None and not _matches_glob(file_path, base, glob_filter):
                continue
            for line_number, text in _search_file(file_path, regex):
                lines.append(f"{_display_path(file_path, cwd=root)}:{line_number}: {text}")
                match_count += 1
                if match_count >= max_results:
                    truncated = True
                    break
            if truncated:
                break

        if not lines:
            return AgentToolResult(
                tool_call_id="",
                name="grep",
                ok=True,
                content=f"No matches for pattern {raw_pattern!r}",
            )
        body = "\n".join(lines)
        if truncated:
            body += f"\n\n[Showing first {max_results} matches; refine the pattern for more.]"
        return AgentToolResult(
            tool_call_id="",
            name="grep",
            ok=True,
            content=body,
            data={"count": match_count, "truncated": truncated},
        )

    return ToolDefinition(
        name="grep",
        description=(
            "Search file contents by regular expression and return matching lines as "
            "'path:line: text'. Searches the working directory by default; optionally scope to a "
            "path and filter files with a glob (e.g. '*.py'). Skips binary files and noise "
            "directories. Use this instead of shelling out to grep/rg."
        ),
        prompt_snippet="Search file contents by regex",
        prompt_guidelines=(
            "Use grep to find where symbols, strings, or patterns appear before editing.",
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regular expression to search for."},
                "path": {
                    "type": "string",
                    "description": "File or directory to search (default: working directory).",
                },
                "glob": {
                    "type": "string",
                    "description": "Only search files matching this glob (e.g. '*.py').",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Match case-insensitively (default false).",
                },
                "max_results": {
                    "type": "integer",
                    "description": f"Max matching lines to return (default {GREP_MATCH_LIMIT}).",
                },
            },
            "required": ["pattern"],
        },
        executor=execute,
        read_only=True,
    )


def _matches_glob(file_path: Path, base: Path, glob_filter: str) -> bool:
    try:
        relative = file_path.relative_to(base)
    except ValueError:
        relative = Path(file_path.name)
    return relative.match(glob_filter) or Path(file_path.name).match(glob_filter)


def _search_file(file_path: Path, regex: re.Pattern[str]) -> Iterator[tuple[int, str]]:
    try:
        if file_path.stat().st_size > GREP_MAX_FILE_BYTES:
            return
        text = file_path.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return
    for line_number, line in enumerate(text.splitlines(), 1):
        if regex.search(line):
            preview = line.strip()
            if len(preview) > GREP_LINE_PREVIEW_CHARS:
                preview = preview[:GREP_LINE_PREVIEW_CHARS] + "…"
            yield line_number, preview


# --- ls ---------------------------------------------------------------------


def create_ls_tool_definition(*, cwd: str | Path | None = None) -> ToolDefinition:
    """Create the `ls` tool: list a directory's immediate entries."""
    root = Path.cwd() if cwd is None else Path(cwd)

    async def execute(
        arguments: Mapping[str, JSONValue],
        signal: ToolCancellationToken | None = None,
    ) -> AgentToolResult:
        del signal
        base = _resolve_path(_optional_str_arg(arguments, "path"), cwd=root)
        if not base.exists():
            raise ToolInputError(f"Path not found: {base}")
        if not base.is_dir():
            raise ToolInputError(f"Path is not a directory: {base}")

        entries = sorted(base.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        rows: list[str] = []
        truncated = False
        for entry in entries:
            if len(rows) >= LS_ENTRY_LIMIT:
                truncated = True
                break
            if entry.is_dir():
                rows.append(f"{entry.name}/")
            else:
                rows.append(f"{entry.name}  ({_safe_size(entry)})")

        if not rows:
            return AgentToolResult(
                tool_call_id="",
                name="ls",
                ok=True,
                content=f"{_display_path(base, cwd=root)} is empty",
            )
        body = "\n".join(rows)
        if truncated:
            body += f"\n\n[Showing first {LS_ENTRY_LIMIT} entries.]"
        return AgentToolResult(
            tool_call_id="",
            name="ls",
            ok=True,
            content=body,
            data={"count": len(rows), "path": str(base), "truncated": truncated},
        )

    return ToolDefinition(
        name="ls",
        description=(
            "List the immediate contents of a directory (directories first, then files with "
            "sizes). Defaults to the working directory. Use this to orient yourself before "
            "reading files."
        ),
        prompt_snippet="List a directory's contents",
        prompt_guidelines=(),
        input_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list (default: working directory).",
                }
            },
            "required": [],
        },
        executor=execute,
        read_only=True,
    )


def _safe_size(entry: Path) -> str:
    try:
        return format_size(entry.stat().st_size)
    except OSError:
        return "?"
