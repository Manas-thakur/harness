"""OpenAI-compatible chat completions provider."""

from collections.abc import AsyncIterator, Mapping
from json import JSONDecodeError, dumps, loads
from typing import Any

import httpx

from phi_agent.messages import AgentMessage, AssistantMessage, ToolResultMessage, UserMessage
from phi_agent.tools import AgentTool, ToolCall
from phi_agent.types import JSONValue
from phi_ai.env import OpenAICompatibleConfig
from phi_ai.events import (
    ProviderErrorEvent,
    ProviderEvent,
    ProviderResponseEndEvent,
    ProviderResponseStartEvent,
    ProviderTextDeltaEvent,
    ProviderThinkingDeltaEvent,
    ProviderToolCallEvent,
    ProviderToolSupportEvent,
)
from phi_ai.provider import CancellationToken
from phi_ai.retry import provider_retry_event, retry_delay_seconds, wait_for_retry


class OpenAICompatibleProvider:
    """Provider adapter for OpenAI-compatible `/chat/completions` APIs."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._owns_client = client is None

    async def aclose(self) -> None:
        """Close the underlying HTTP client if this provider created it."""
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[AgentMessage],
        tools: list[AgentTool],
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        """Stream one chat completion response as provider-neutral events."""

        async def iterator() -> AsyncIterator[ProviderEvent]:
            client = self._get_client()
            payload = _build_chat_payload(
                model=model,
                system=system,
                messages=messages,
                tools=tools,
                reasoning_effort=self._config.reasoning_effort,
                reasoning_effort_parameter=self._config.reasoning_effort_parameter,
            )
            headers = {
                **(dict(self._config.headers or {})),
                "Authorization": f"Bearer {self._config.api_key}",
            }
            url = f"{self._config.base_url.rstrip('/')}/chat/completions"

            attempt = 0
            retried_without_tools = False
            while True:
                emitted_content = False
                try:
                    async with client.stream(
                        "POST", url, json=payload, headers=headers
                    ) as response:
                        if response.status_code >= 400:
                            body = await response.aread()
                            body_text = body.decode(errors="replace")
                            if (
                                response.status_code == 400
                                and not retried_without_tools
                                and "does not support tools" in body_text
                                and tools
                            ):
                                retried_without_tools = True
                                payload = _build_chat_payload(
                                    model=model,
                                    system=system,
                                    messages=messages,
                                    tools=[],
                                    reasoning_effort=self._config.reasoning_effort,
                                    reasoning_effort_parameter=(
                                        self._config.reasoning_effort_parameter
                                    ),
                                )
                                yield ProviderToolSupportEvent(supported=False)
                                continue
                            if self._should_retry(attempt, status_code=response.status_code):
                                delay = retry_delay_seconds(
                                    attempt,
                                    max_delay_seconds=self._config.max_retry_delay_seconds,
                                )
                                yield provider_retry_event(
                                    attempt=attempt,
                                    max_retries=self._config.max_retries,
                                    delay_seconds=delay,
                                    reason=f"HTTP {response.status_code}",
                                    data={
                                        "status_code": response.status_code,
                                        "body": body_text,
                                    },
                                )
                                attempt += 1
                                if not await wait_for_retry(delay, signal=signal):
                                    return
                                continue
                            yield ProviderErrorEvent(
                                message=(
                                    f"Provider request failed with status {response.status_code}"
                                ),
                                data={
                                    "body": body_text,
                                    "attempts": attempt + 1,
                                },
                            )
                            return

                        yield ProviderResponseStartEvent(model=model)
                        content_parts: list[str] = []
                        tool_call_builders: dict[int, _ToolCallBuilder] = {}
                        finish_reason: str | None = None
                        think_splitter = _ThinkTagSplitter()

                        async for line in response.aiter_lines():
                            if signal is not None and signal.is_cancelled():
                                return

                            event = _parse_sse_line(line)
                            if event is None:
                                continue
                            if event == "[DONE]":
                                break

                            chunk = _loads_object(event)
                            if chunk is None:
                                yield ProviderErrorEvent(
                                    message="Provider returned invalid JSON chunk"
                                )
                                return

                            choice = _first_choice(chunk)
                            if choice is None:
                                continue

                            finish_reason = choice.get("finish_reason") or finish_reason
                            delta = choice.get("delta")
                            if not isinstance(delta, Mapping):
                                continue

                            content = delta.get("content")
                            if isinstance(content, str) and content:
                                for kind, segment in think_splitter.feed(content):
                                    emitted_content = True
                                    if kind == "text":
                                        content_parts.append(segment)
                                        yield ProviderTextDeltaEvent(delta=segment)
                                    else:
                                        yield ProviderThinkingDeltaEvent(delta=segment)

                            thinking = _thinking_delta_text(delta)
                            if thinking:
                                emitted_content = True
                                yield ProviderThinkingDeltaEvent(delta=thinking)

                            for tool_call_delta in _tool_call_deltas(delta):
                                emitted_content = True
                                index = int(tool_call_delta.get("index", 0))
                                builder = tool_call_builders.setdefault(index, _ToolCallBuilder())
                                builder.add_delta(tool_call_delta)

                        for kind, segment in think_splitter.flush():
                            emitted_content = True
                            if kind == "text":
                                content_parts.append(segment)
                                yield ProviderTextDeltaEvent(delta=segment)
                            else:
                                yield ProviderThinkingDeltaEvent(delta=segment)

                        tool_calls = [
                            builder.build(index)
                            for index, builder in sorted(tool_call_builders.items())
                        ]
                        for tool_call in tool_calls:
                            yield ProviderToolCallEvent(tool_call=tool_call)

                        message = AssistantMessage(
                            content="".join(content_parts),
                            tool_calls=tool_calls,
                        )
                        yield ProviderResponseEndEvent(message=message, finish_reason=finish_reason)
                        return
                except httpx.HTTPError as exc:
                    if not emitted_content and self._should_retry(attempt):
                        delay = retry_delay_seconds(
                            attempt,
                            max_delay_seconds=self._config.max_retry_delay_seconds,
                        )
                        yield provider_retry_event(
                            attempt=attempt,
                            max_retries=self._config.max_retries,
                            delay_seconds=delay,
                            reason="network error",
                            data={
                                "error": str(exc),
                                "error_type": type(exc).__name__,
                            },
                        )
                        attempt += 1
                        if not await wait_for_retry(delay, signal=signal):
                            return
                        continue
                    yield ProviderErrorEvent(
                        message=str(exc),
                        data={"attempts": attempt + 1},
                    )
                    return

        return iterator()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._config.timeout_seconds)
        return self._client

    def _should_retry(self, attempt: int, *, status_code: int | None = None) -> bool:
        if attempt >= self._config.max_retries:
            return False
        return status_code is None or _is_transient_status(status_code)


class _ToolCallBuilder:
    def __init__(self) -> None:
        self.id = ""
        self.name = ""
        self.arguments_parts: list[str] = []

    def add_delta(self, delta: Mapping[str, Any]) -> None:
        call_id = delta.get("id")
        if isinstance(call_id, str):
            self.id = call_id

        function = delta.get("function")
        if not isinstance(function, Mapping):
            return

        name = function.get("name")
        if isinstance(name, str):
            self.name = name

        arguments = function.get("arguments")
        if isinstance(arguments, str):
            self.arguments_parts.append(arguments)

    def build(self, index: int) -> ToolCall:
        arguments_text = "".join(self.arguments_parts)
        arguments = _loads_object(arguments_text) if arguments_text else {}
        if arguments is None:
            arguments = {"_raw_arguments": arguments_text}

        return ToolCall(
            id=self.id or f"tool-call-{index}",
            name=self.name,
            arguments=arguments,
        )


def _build_chat_payload(
    *,
    model: str,
    system: str,
    messages: list[AgentMessage],
    tools: list[AgentTool],
    reasoning_effort: str | None = None,
    reasoning_effort_parameter: str = "reasoning_effort",
) -> dict[str, JSONValue]:
    payload: dict[str, JSONValue] = {
        "model": model,
        "stream": True,
        "messages": [
            _system_message(system),
            *[_message_to_openai(message) for message in messages],
        ],
    }
    if reasoning_effort is not None:
        if reasoning_effort_parameter == "reasoning.effort":
            payload["reasoning"] = {"effort": reasoning_effort}
        else:
            payload["reasoning_effort"] = reasoning_effort
    if tools:
        payload["tools"] = [_tool_to_openai(tool) for tool in tools]
    return payload


def _system_message(system: str) -> dict[str, JSONValue]:
    return {"role": "system", "content": system}


def _message_to_openai(message: AgentMessage) -> dict[str, JSONValue]:
    if isinstance(message, UserMessage):
        return {"role": "user", "content": message.content}

    if isinstance(message, AssistantMessage):
        item: dict[str, JSONValue] = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            item["tool_calls"] = [
                _tool_call_to_openai(tool_call) for tool_call in message.tool_calls
            ]
        return item

    if isinstance(message, ToolResultMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "name": message.name,
            "content": message.content,
        }


def _tool_to_openai(tool: AgentTool) -> dict[str, JSONValue]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.input_schema),
        },
    }


def _tool_call_to_openai(tool_call: ToolCall) -> dict[str, JSONValue]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": dumps(tool_call.arguments),
        },
    }


def _parse_sse_line(line: str) -> str | None:
    line = line.strip()
    if not line or not line.startswith("data:"):
        return None
    return line.removeprefix("data:").strip()


def _loads_object(value: str) -> dict[str, JSONValue] | None:
    try:
        loaded = loads(value)
    except JSONDecodeError:
        return None
    if isinstance(loaded, dict):
        return loaded
    return None


def _first_choice(chunk: Mapping[str, Any]) -> Mapping[str, Any] | None:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    choice = choices[0]
    if not isinstance(choice, Mapping):
        return None
    return choice


def _tool_call_deltas(delta: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []
    return [tool_call for tool_call in tool_calls if isinstance(tool_call, Mapping)]


def _thinking_delta_text(delta: Mapping[str, Any]) -> str:
    for field_name in ("reasoning_content", "reasoning", "thinking"):
        value = delta.get(field_name)
        if isinstance(value, str) and value:
            return value
    return ""


class _ThinkTagSplitter:
    """Split streamed content into normal text and inline ``<think>`` reasoning.

    Local reasoning models served through Ollama's OpenAI-compatible endpoint
    (qwen3, deepseek-r1, …) emit their chain of thought inline in the content
    stream wrapped in ``<think>``/``</think>`` tags rather than in a separate
    reasoning field. This splitter routes that reasoning to thinking deltas and
    keeps it out of the final answer, correctly handling tags that straddle SSE
    chunk boundaries by holding back a possible partial tag until more text
    arrives.
    """

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self) -> None:
        self._pending = ""
        self._in_think = False

    def feed(self, delta: str) -> list[tuple[str, str]]:
        """Consume a content fragment, returning ordered ``(kind, text)`` parts."""
        self._pending += delta
        return self._drain(final=False)

    def flush(self) -> list[tuple[str, str]]:
        """Return any remaining buffered text once the stream has ended."""
        return self._drain(final=True)

    def _drain(self, *, final: bool) -> list[tuple[str, str]]:
        segments: list[tuple[str, str]] = []
        while self._pending:
            tag, kind = (self._CLOSE, "thinking") if self._in_think else (self._OPEN, "text")
            index = self._pending.find(tag)
            if index != -1:
                if index > 0:
                    segments.append((kind, self._pending[:index]))
                self._pending = self._pending[index + len(tag) :]
                self._in_think = not self._in_think
                continue
            hold = 0 if final else _partial_tag_suffix_len(self._pending, tag)
            cut = len(self._pending) - hold
            if cut > 0:
                segments.append((kind, self._pending[:cut]))
            self._pending = self._pending[cut:]
            break
        return segments


def _partial_tag_suffix_len(text: str, tag: str) -> int:
    """Return the length of the longest text suffix that is a prefix of ``tag``."""
    for length in range(min(len(text), len(tag) - 1), 0, -1):
        if text[-length:] == tag[:length]:
            return length
    return 0


def _is_transient_status(status_code: int) -> bool:
    return status_code in {408, 409, 425, 429} or status_code >= 500
