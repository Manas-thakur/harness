"""Tests for always-loaded core memory and the model-facing memory tools."""
import pytest
from harness.memory import MemoryStore
from harness.tools import ToolRegistry


@pytest.fixture
def store(tmp_path):
    return MemoryStore(str(tmp_path / "memory.md"), use_mesh=False)


class TestCoreMemory:
    def test_read_core_skips_placeholders(self, store):
        # Fresh template has placeholder-only core sections.
        assert store.read_core() == ""

    def test_append_to_section_round_trip(self, store):
        store.append_to_section("About", "User is Manas.")
        core = store.read_core()
        assert "## About" in core
        assert "User is Manas." in core

    def test_stub_file_gets_core_sections(self, tmp_path):
        stub = tmp_path / "memory.md"
        stub.write_text("# Legacy Memory Archived\n\nmigrated.\n")
        MemoryStore(str(stub), use_mesh=False)
        text = stub.read_text()
        for section in ("About", "Current Work", "User Preferences"):
            assert f"## {section}" in text

    def test_existing_file_untouched(self, tmp_path):
        mem = tmp_path / "memory.md"
        original = "# Memory\n\n## Facts\n- Fact 1"
        mem.write_text(original)
        MemoryStore(str(mem), use_mesh=False)
        assert mem.read_text() == original


class TestMemoryTools:
    def test_update_profile_then_read_core(self, store):
        tr = ToolRegistry(memory=store)
        tr.execute("update_profile", {"section": "Current Work", "content": "menace harness"})
        assert "menace harness" in store.read_core()

    def test_update_profile_defaults_to_about(self, store):
        tr = ToolRegistry(memory=store)
        tr.execute("update_profile", {"content": "bare fact"})
        assert "## About" in store.read_core()

    def test_remember_recall_round_trip(self, store):
        tr = ToolRegistry(memory=store)
        tr.execute("remember", {"fact": "Austria GP won by Verstappen."})
        out = tr.execute("recall", {"query": "Austria"})
        assert "Verstappen" in out

    def test_recall_no_match(self, store):
        tr = ToolRegistry(memory=store)
        out = tr.execute("recall", {"query": "zzz-nonexistent"})
        assert "No stored memory" in out

    def test_tools_use_shared_store(self, store):
        # A write through the tool must be visible on the same store instance.
        tr = ToolRegistry(memory=store)
        tr.execute("update_profile", {"section": "About", "content": "shared check"})
        assert "shared check" in store.get_section("About")
