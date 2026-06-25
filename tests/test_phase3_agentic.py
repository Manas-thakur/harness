"""Tests for Phase 3: reliable tool calling, grounded fetch, reflection, routing.

All offline / mocked — no Ollama, no network.
"""
import sys
import types
import pytest

from harness.coordinator import Coordinator
from harness.llm_client import LocalLLMClient
from harness.threads import AgentThread
from harness.tools import ToolRegistry, TOOL_SCHEMAS


# --- A. Structured tool messages (no more "[Calling X]" prose) --------------

class TestStructuredToolMessages:
    def test_add_tool_call_is_structured(self):
        t = AgentThread(agent_name="x")
        t.add_tool_call("search_web", {"query": "f1"}, "RESULT")
        assert len(t.history) == 2
        assistant, tool = t.history
        assert assistant["role"] == "assistant"
        assert assistant["tool_calls"][0]["function"]["name"] == "search_web"
        assert assistant["tool_calls"][0]["function"]["arguments"] == {"query": "f1"}
        assert tool["role"] == "tool" and tool["content"] == "RESULT"
        # The old prose form must never appear.
        assert "[Calling" not in assistant["content"]
        assert "[Calling" not in tool["content"]


# --- B. Prose / function-syntax tool-call recovery --------------------------

class TestProseRecovery:
    def _coord(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        return Coordinator(mock=True)

    def test_recover_function_syntax(self, tmp_path, monkeypatch):
        co = self._coord(tmp_path, monkeypatch)
        rec = co._recover_tool_call('search_web(query="latest f1")', ["search_web"])
        assert rec == {"name": "search_web", "arguments": {"query": "latest f1"}}

    def test_recover_positional_maps_to_first_param(self, tmp_path, monkeypatch):
        co = self._coord(tmp_path, monkeypatch)
        rec = co._recover_tool_call('fetch_url("https://x.com")', ["fetch_url"])
        assert rec == {"name": "fetch_url", "arguments": {"url": "https://x.com"}}

    def test_recover_ignores_unallowed_tool(self, tmp_path, monkeypatch):
        co = self._coord(tmp_path, monkeypatch)
        assert co._recover_tool_call('bash("ls")', ["search_web"]) is None

    def test_mentions_tool_detects_bracket_prose(self, tmp_path, monkeypatch):
        co = self._coord(tmp_path, monkeypatch)
        assert co._mentions_tool("[Calling search_web]", ["search_web"]) is True
        assert co._mentions_tool("just chatting", ["search_web"]) is False

    def test_first_param_from_schema(self, tmp_path, monkeypatch):
        co = self._coord(tmp_path, monkeypatch)
        assert co._first_param("search_web") == "query"
        assert co._first_param("fetch_url") == "url"


class TestProseNudgeLoop:
    """A model that emits prose '[Calling search_web]' should be nudged, then
    succeed on the structured retry instead of leaking prose to the user."""

    def test_prose_then_nudge_then_tool(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        co = Coordinator(mock=True)

        class ProseLLM:
            mock = True
            model = "fake"
            def __init__(self): self.calls = 0
            def generate(self, messages, temperature=0.3):
                return '{"agent": "researcher"}'
            def chat_with_tools(self, messages, tools=None, temperature=0.7):
                self.calls += 1
                if self.calls == 1:            # prose, no structured call, no args
                    return {"content": "[Calling search_web]", "tool_calls": []}
                if self.calls == 2:            # after nudge: real call
                    return {"content": "", "tool_calls": [
                        {"name": "search_web", "arguments": {"query": "f1"}}]}
                return {"content": "Verstappen won, per the result.", "tool_calls": []}

        co.llm = ProseLLM()
        co.tools.tools["search_web"] = lambda inp: "RESULT: Verstappen won."
        out = co.chat("who won the race")
        assert "Verstappen" in out
        assert "[Calling" not in out
        assert co.llm.calls == 3   # prose -> nudge -> tool -> answer


# --- C. num_ctx + think-strip ----------------------------------------------

class _CapturingClient:
    def __init__(self):
        self.last_options = None
    def chat(self, model, messages, tools=None, options=None, stream=False):
        self.last_options = options
        return {"message": {"content": "hi", "tool_calls": None}}
    def list(self):
        return {"models": []}


class TestNumCtxAndThink:
    def test_num_ctx_passed_to_chat_with_tools(self):
        c = LocalLLMClient(mock=False, num_ctx=4242)
        c._client = _CapturingClient()
        c.mock = False
        c.chat_with_tools([{"role": "user", "content": "x"}], tools=[])
        assert c._client.last_options["num_ctx"] == 4242

    def test_num_ctx_passed_to_generate(self):
        c = LocalLLMClient(mock=False, num_ctx=1234)
        c._client = _CapturingClient()
        c.mock = False
        c.generate([{"role": "user", "content": "x"}])
        assert c._client.last_options["num_ctx"] == 1234

    def test_num_ctx_default(self):
        assert LocalLLMClient(mock=True).num_ctx == 8192

    def test_strip_think_block(self):
        s = LocalLLMClient._strip_think("<think>secret reasoning</think>Answer.")
        assert s == "Answer."

    def test_strip_unterminated_think(self):
        s = LocalLLMClient._strip_think("before <think>dangling")
        assert s == "before"


# --- D. fetch_url tool ------------------------------------------------------

class TestFetchUrl:
    def _fake_httpx(self, monkeypatch, html=None, raise_exc=None):
        mod = types.ModuleType("httpx")

        class Resp:
            text = html or ""
            def raise_for_status(self): pass

        def get(url, **kwargs):
            if raise_exc:
                raise raise_exc
            return Resp()

        mod.get = get
        monkeypatch.setitem(sys.modules, "httpx", mod)

    def test_fetch_returns_readable_text(self, monkeypatch):
        self._fake_httpx(monkeypatch,
                         html="<html><body><script>evil()</script>"
                              "<p>Hello World</p></body></html>")
        tr = ToolRegistry()
        out = tr.execute("fetch_url", {"url": "example.com"})
        assert "Hello World" in out
        assert "evil()" not in out   # script content stripped

    def test_fetch_network_error(self, monkeypatch):
        self._fake_httpx(monkeypatch, raise_exc=RuntimeError("neterr"))
        tr = ToolRegistry()
        out = tr.execute("fetch_url", {"url": "http://x"})
        assert "Error fetching" in out and "neterr" in out

    def test_fetch_empty_url(self):
        tr = ToolRegistry()
        assert "no url" in tr.execute("fetch_url", {"url": ""}).lower()

    def test_fetch_url_has_schema_and_registered(self):
        tr = ToolRegistry()
        assert "fetch_url" in tr.tools
        assert "fetch_url" in TOOL_SCHEMAS

    def test_html_to_text_collapses_markup(self):
        txt = ToolRegistry._html_to_text("<h1>Title</h1><p>Body  text</p>")
        assert "Title" in txt and "Body text" in txt and "<" not in txt


# --- E. Reflection / critique gate ------------------------------------------

class TestReflectionGate:
    def test_refine_runs_when_critique_flags(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        co = Coordinator(mock=True)

        class ReflectLLM:
            mock = False     # reflection only runs for non-mock
            model = "fake"
            def generate(self, messages, temperature=0.3):
                # The critique call: flag the draft as ungrounded.
                return '{"ok": false, "issue": "no source", "suggestion": "search"}'
            def chat_with_tools(self, messages, tools=None, temperature=0.7):
                return {"content": "Refined grounded answer.", "tool_calls": []}

        co.llm = ReflectLLM()
        agent = co.agents["researcher"]
        schemas = co.tools.get_schemas(agent.allowed_tools)
        out = co._reflect_and_refine(agent, [{"role": "user", "content": "q"}],
                                     schemas, "weak draft", emit=lambda *a: None)
        assert out == "Refined grounded answer."

    def test_reflection_skipped_in_mock(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        co = Coordinator(mock=True)   # real mock LLM
        agent = co.agents["researcher"]
        out = co._reflect_and_refine(agent, [], [], "draft answer", emit=lambda *a: None)
        assert out == "draft answer"


# --- F. Routing: keyword pre-router + stickiness ----------------------------

class TestRouting:
    def test_keyword_routes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        co = Coordinator(mock=True)
        assert co._route("write a python function to sort") == "coder"
        assert co._route("explain how recursion works") == "tutor"
        assert co._route("search the web for latest news") == "researcher"

    def test_general_sticks_to_last_agent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        co = Coordinator(mock=True)

        class GeneralLLM:
            mock = True
            model = "fake"
            def generate(self, messages, temperature=0.3):
                return '{"agent": "general"}'
        co.llm = GeneralLLM()
        co.last_agent = "coder"
        # No keyword hits + general classification -> stay on coder.
        assert co._route("ok thanks, sounds good") == "coder"


# --- G. reset_conversation --------------------------------------------------

def test_reset_conversation_clears_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    co = Coordinator(mock=True)
    co.conversation.add_message("user", "hi")
    co.current_turn = 5
    co.session_transcript = [{"role": "user", "content": "x"}]
    co.reset_conversation()
    assert co.conversation.history == []
    assert co.current_turn == 0
    assert co.session_transcript == []
    assert co.last_agent is None
