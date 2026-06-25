"""Tests for LocalLLMClient tool-call normalization and mock behavior."""
from harness.llm_client import LocalLLMClient


class TestChatWithToolsMock:
    def test_mock_returns_no_tool_calls(self):
        llm = LocalLLMClient(mock=True)
        out = llm.chat_with_tools([{"role": "user", "content": "hi"}], tools=[])
        assert out["tool_calls"] == []
        assert isinstance(out["content"], str) and out["content"]


class TestNormalizeToolCalls:
    def test_none(self):
        assert LocalLLMClient._normalize_tool_calls(None) == []

    def test_dict_form(self):
        raw = [{"function": {"name": "search_web", "arguments": {"query": "x"}}}]
        assert LocalLLMClient._normalize_tool_calls(raw) == [
            {"name": "search_web", "arguments": {"query": "x"}}
        ]

    def test_string_arguments_parsed(self):
        raw = [{"function": {"name": "f", "arguments": '{"a": 1}'}}]
        assert LocalLLMClient._normalize_tool_calls(raw) == [
            {"name": "f", "arguments": {"a": 1}}
        ]

    def test_bad_string_arguments_become_empty(self):
        raw = [{"function": {"name": "f", "arguments": "not json"}}]
        assert LocalLLMClient._normalize_tool_calls(raw) == [
            {"name": "f", "arguments": {}}
        ]

    def test_object_form(self):
        class Fn:
            name = "f"
            arguments = {"k": "v"}

        class Call:
            function = Fn()

        assert LocalLLMClient._normalize_tool_calls([Call()]) == [
            {"name": "f", "arguments": {"k": "v"}}
        ]
