"""Tests for the persistent memory store and model-driven memory tools."""

from pathlib import Path

import pytest

from phi_coding.memory import MemoryStore
from phi_coding.memory_tools import create_memory_tools
from phi_coding.system_prompt import BuildSystemPromptOptions, build_system_prompt


def _store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(tmp_path / "memory.md")


# --- MemoryStore ------------------------------------------------------------


def test_empty_core_is_blank(tmp_path: Path) -> None:
    assert _store(tmp_path).read_core() == ""


def test_profile_round_trips_into_core(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_to_section("About", "Manas, a developer")
    store.append_to_section("Current Work", "porting menace onto phi")
    core = store.read_core()
    assert "Manas, a developer" in core
    assert "porting menace onto phi" in core
    assert "## About" in core and "## Current Work" in core


def test_section_name_is_normalized(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_to_section("about", "lowercase section")
    assert "## About" in store.read_core()


def test_facts_save_and_search(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save_fact("The deploy command is `make ship`", key="deploy")
    store.save_fact("Prefers pytest over unittest")
    assert any("make ship" in m for m in store.search("deploy"))
    assert store.search("PYTEST")  # case-insensitive
    assert store.search("nonexistent") == []


def test_duplicate_entries_are_ignored(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_to_section("About", "same")
    store.append_to_section("About", "same")
    assert store.read_core().count("- same") == 1


def test_snapshot_written_before_overwrite(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_to_section("About", "first")
    store.append_to_section("About", "second")  # triggers a snapshot of the first write
    versions = list((tmp_path / "memory.versions").glob("memory_*.md"))
    assert len(versions) >= 1


# --- memory tools -----------------------------------------------------------


def test_create_memory_tools_names(tmp_path: Path) -> None:
    tools = create_memory_tools(store=_store(tmp_path))
    assert [t.name for t in tools] == ["update_profile", "remember", "recall"]


@pytest.mark.anyio
async def test_update_profile_tool_persists(tmp_path: Path) -> None:
    store = _store(tmp_path)
    tools = {t.name: t for t in create_memory_tools(store=store)}
    result = await tools["update_profile"].executor(
        {"section": "Current Work", "content": "migrating to phi"}
    )
    assert result.ok
    assert "migrating to phi" in store.read_core()


@pytest.mark.anyio
async def test_remember_then_recall(tmp_path: Path) -> None:
    store = _store(tmp_path)
    tools = {t.name: t for t in create_memory_tools(store=store)}
    await tools["remember"].executor({"fact": "API key lives in vault X"})
    result = await tools["recall"].executor({"query": "vault"})
    assert result.ok
    assert "vault X" in result.content


@pytest.mark.anyio
async def test_recall_miss(tmp_path: Path) -> None:
    tools = {t.name: t for t in create_memory_tools(store=_store(tmp_path))}
    result = await tools["recall"].executor({"query": "nothing here"})
    assert result.ok
    assert "No stored memory matches" in result.content


@pytest.mark.anyio
async def test_update_profile_requires_content(tmp_path: Path) -> None:
    from phi_coding.tools import ToolInputError

    tools = {t.name: t for t in create_memory_tools(store=_store(tmp_path))}
    with pytest.raises(ToolInputError):
        await tools["update_profile"].executor({"content": "  "})


# --- system-prompt injection ------------------------------------------------


def test_core_memory_injects_into_system_prompt(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.append_to_section("About", "Manas, building menace")
    core = store.read_core()
    prompt = build_system_prompt(
        BuildSystemPromptOptions(cwd=tmp_path, append_system_prompt=core)
    )
    assert "Manas, building menace" in prompt
