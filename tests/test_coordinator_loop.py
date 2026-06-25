"""Tests for the coordinator's native tool-calling loop (offline, fake LLM)."""
import pytest
from harness.coordinator import Coordinator


class FakeLLM:
    """Fake LLM: requests a tool on the first turn, answers on the second."""

    def __init__(self, tool_then_answer=True):
        self.mock = True
        self.model = "fake"
        self.calls = 0
        self.tool_then_answer = tool_then_answer

    def generate(self, messages, temperature=0.3):
        # Used by _classify_intent.
        return '{"agent": "researcher", "reasoning": "test"}'

    def chat_with_tools(self, messages, tools=None, temperature=0.7):
        self.calls += 1
        if self.tool_then_answer and self.calls == 1:
            return {"content": "", "tool_calls": [
                {"name": "search_web", "arguments": {"query": "latest f1"}}
            ]}
        return {"content": "Per the search, Verstappen won.", "tool_calls": []}


@pytest.fixture
def coord(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    co = Coordinator(mock=True)
    co.llm = FakeLLM()
    # Stub the real search tool so no network is touched.
    co.tools.tools["search_web"] = lambda inp: "RESULT: Verstappen won."
    return co


class TestToolLoop:
    def test_tool_then_stream_final(self, coord):
        events, tokens = [], []
        out = coord.chat(
            "who won?",
            on_event=lambda k, d: events.append((k, d)),
            on_token=lambda c: tokens.append(c),
        )
        assert "Verstappen" in out
        # The search tool was executed and surfaced as an event.
        tool_events = [e for e in events if e[0] == "tool"]
        assert tool_events and tool_events[0][1]["name"] == "search_web"
        # Final answer was streamed to on_token.
        assert "".join(tokens).strip() == out

    def test_plain_answer_no_tools(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        co = Coordinator(mock=True)
        co.llm = FakeLLM(tool_then_answer=False)
        out = co.chat("hello")
        assert "Verstappen" in out  # the fake's answer
        assert co.llm.calls == 1    # no tool round-trip

    def test_json_fallback_tool_call(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        co = Coordinator(mock=True)

        class JSONFallbackLLM(FakeLLM):
            def chat_with_tools(self, messages, tools=None, temperature=0.7):
                self.calls += 1
                if self.calls == 1:
                    # No native tool_calls; emit a JSON tool call in content.
                    return {"content": '{"tool": "search_web", "input": {"query": "x"}}',
                            "tool_calls": []}
                return {"content": "Answer from fallback.", "tool_calls": []}

        co.llm = JSONFallbackLLM()
        ran = {"hit": False}

        def fake_search(inp):
            ran["hit"] = True
            return "ok"

        co.tools.tools["search_web"] = fake_search
        out = co.chat("q")
        assert ran["hit"] is True
        assert "fallback" in out
