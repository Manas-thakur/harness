"""Tests for the read-only codebase exploration tools (glob, grep, ls)."""

from pathlib import Path

import pytest

from phi_coding.codebase_tools import (
    create_codebase_tools,
    create_glob_tool_definition,
    create_grep_tool_definition,
    create_ls_tool_definition,
)
from phi_coding.tools import ToolInputError


def _project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("import os\n\ndef run():\n    return os.getcwd()\n")
    (tmp_path / "src" / "util.py").write_text("def helper():\n    return 42\n")
    (tmp_path / "README.md").write_text("# Project\nrun the app\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.py").write_text("def run():\n    return 'noise'\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.py").write_text("def run():\n    pass\n")
    return tmp_path


def test_create_codebase_tools_names_and_read_only(tmp_path: Path) -> None:
    tools = create_codebase_tools(cwd=tmp_path)
    assert [t.name for t in tools] == ["glob", "grep", "ls"]
    assert all(t.read_only for t in tools)


# --- glob -------------------------------------------------------------------


@pytest.mark.anyio
async def test_glob_finds_python_files_and_skips_noise_dirs(tmp_path: Path) -> None:
    root = _project(tmp_path)
    tool = create_glob_tool_definition(cwd=root)
    result = await tool.executor({"pattern": "**/*.py"})
    assert result.ok
    assert "src/app.py" in result.content
    assert "src/util.py" in result.content
    assert "node_modules" not in result.content
    assert ".git" not in result.content


@pytest.mark.anyio
async def test_glob_reports_no_matches(tmp_path: Path) -> None:
    tool = create_glob_tool_definition(cwd=_project(tmp_path))
    result = await tool.executor({"pattern": "**/*.rs"})
    assert result.ok
    assert "No files match" in result.content


@pytest.mark.anyio
async def test_glob_rejects_missing_directory(tmp_path: Path) -> None:
    tool = create_glob_tool_definition(cwd=tmp_path)
    with pytest.raises(ToolInputError):
        await tool.executor({"pattern": "*.py", "path": "does-not-exist"})


@pytest.mark.anyio
async def test_glob_rejects_absolute_pattern_with_clear_error(tmp_path: Path) -> None:
    tool = create_glob_tool_definition(cwd=tmp_path)
    with pytest.raises(ToolInputError, match="Invalid glob pattern"):
        await tool.executor({"pattern": "/etc/*.conf"})


# --- grep -------------------------------------------------------------------


@pytest.mark.anyio
async def test_grep_finds_matches_with_paths_and_line_numbers(tmp_path: Path) -> None:
    root = _project(tmp_path)
    tool = create_grep_tool_definition(cwd=root)
    result = await tool.executor({"pattern": r"def run"})
    assert result.ok
    assert "src/app.py:3:" in result.content
    # noise directories are excluded from content search
    assert "node_modules" not in result.content


@pytest.mark.anyio
async def test_grep_glob_filter_scopes_to_matching_files(tmp_path: Path) -> None:
    root = _project(tmp_path)
    tool = create_grep_tool_definition(cwd=root)
    result = await tool.executor({"pattern": "run", "glob": "*.md"})
    assert result.ok
    assert "README.md" in result.content
    assert "app.py" not in result.content


@pytest.mark.anyio
async def test_grep_invalid_regex_raises(tmp_path: Path) -> None:
    tool = create_grep_tool_definition(cwd=tmp_path)
    with pytest.raises(ToolInputError):
        await tool.executor({"pattern": "([unclosed"})


@pytest.mark.anyio
async def test_grep_reports_no_matches(tmp_path: Path) -> None:
    tool = create_grep_tool_definition(cwd=_project(tmp_path))
    result = await tool.executor({"pattern": "zzz-not-present"})
    assert result.ok
    assert "No matches" in result.content


@pytest.mark.anyio
async def test_grep_skips_binary_files(tmp_path: Path) -> None:
    (tmp_path / "data.bin").write_bytes(b"\x00\x01match\x00\xff")
    (tmp_path / "ok.txt").write_text("match here\n")
    tool = create_grep_tool_definition(cwd=tmp_path)
    result = await tool.executor({"pattern": "match"})
    assert result.ok
    assert "ok.txt" in result.content
    assert "data.bin" not in result.content


@pytest.mark.anyio
async def test_grep_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("Hello World\n")
    tool = create_grep_tool_definition(cwd=tmp_path)
    sensitive = await tool.executor({"pattern": "hello"})
    insensitive = await tool.executor({"pattern": "hello", "case_insensitive": True})
    assert "No matches" in sensitive.content
    assert "f.txt" in insensitive.content


# --- ls ---------------------------------------------------------------------


@pytest.mark.anyio
async def test_ls_lists_dirs_first_then_files(tmp_path: Path) -> None:
    root = _project(tmp_path)
    tool = create_ls_tool_definition(cwd=root)
    result = await tool.executor({})
    lines = result.content.splitlines()
    assert "src/" in result.content
    assert any(line.startswith("README.md") for line in lines)
    # directory entries (trailing slash) sort before files
    first_file_index = next(i for i, line in enumerate(lines) if not line.endswith("/"))
    assert all(lines[i].endswith("/") for i in range(first_file_index))


@pytest.mark.anyio
async def test_ls_rejects_a_file_path(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")
    tool = create_ls_tool_definition(cwd=tmp_path)
    with pytest.raises(ToolInputError):
        await tool.executor({"path": "file.txt"})


@pytest.mark.anyio
async def test_ls_empty_directory(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    tool = create_ls_tool_definition(cwd=tmp_path)
    result = await tool.executor({"path": "empty"})
    assert result.ok
    assert "is empty" in result.content
