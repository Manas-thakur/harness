"""
LLM Client for Local Ollama Instance
Handles communication with local Ollama server and JSON repair for unreliable model outputs.
"""

import os
import re
import json
from typing import Dict, List, Any, Iterator

try:
    import ollama
except ImportError:  # pragma: no cover - ollama is optional for offline/mock mode
    ollama = None


def repair_and_extract_json(text: str) -> dict:
    """
    Repair and extract JSON from potentially malformed LLM output.
    Local 7B models often output markdown around JSON or miss closing brackets.
    
    Args:
        text: Raw text output from LLM
        
    Returns:
        Parsed dictionary
        
    Raises:
        ValueError: If no valid JSON can be extracted
    """
    # 1. Find the first { 
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in text")

    # Try to find matching } by counting braces
    open_count = 0
    end = -1
    for i, char in enumerate(text[start:], start):
        if char == '{':
            open_count += 1
        elif char == '}':
            open_count -= 1
            if open_count == 0:
                end = i
                break

    # If no matching brace found, try rfind as fallback
    if end == -1:
        end = text.rfind('}')
        if end == -1:
            # No closing brace at all - add one
            json_str = text[start:] + '}'
        else:
            json_str = text[start:end+1]
    else:
        json_str = text[start:end+1]

    # 2. Attempt to parse directly
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 3. Basic repair: remove trailing commas before } or ]
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 4. Remove markdown code blocks if present
    json_str = re.sub(r'```json\s*', '', json_str)
    json_str = re.sub(r'```\s*', '', json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 5. Try to fix common issues - Add missing closing braces
    open_braces = json_str.count('{')
    close_braces = json_str.count('}')
    if open_braces > close_braces:
        json_str += '}' * (open_braces - close_braces)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 6. Try removing any remaining whitespace issues
    json_str = json_str.strip()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"Failed to repair JSON: {text[:200]}")


class LocalLLMClient:
    """
    Client for interacting with local Ollama LLM instance.
    Optimized for RTX 4060 8GB VRAM with Qwen2.5-7B.
    """

    def __init__(
        self,
        model: str = None,
        host: str = None,
        timeout: int = 120,
        mock: bool = None,
        num_ctx: int = None,
    ):
        """
        Initialize the LLM client.

        Args:
            model: Model name to use (default: env OLLAMA_MODEL or qwen3:8b)
            host: Ollama server host URL (default: env OLLAMA_HOST or localhost)
            timeout: Request timeout in seconds
            mock: Force offline mock mode. If None, mock is used automatically
                  whenever Ollama is not reachable.
            num_ctx: Ollama context window (tokens). Ollama otherwise defaults to
                ~2048, which silently truncates the soul/memory/tool context and
                makes the model fabricate. Default: env OLLAMA_NUM_CTX or 8192.
        """
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen3:8b")
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.timeout = timeout
        try:
            self.num_ctx = int(num_ctx if num_ctx is not None
                               else os.environ.get("OLLAMA_NUM_CTX", 8192))
        except (TypeError, ValueError):
            self.num_ctx = 8192

        # Build a dedicated client bound to this host (avoids mutating globals).
        self._client = None
        if ollama is not None:
            try:
                self._client = ollama.Client(host=self.host, timeout=timeout)
            except Exception:
                self._client = None

        # Decide mock mode. If not explicitly requested, probe the server:
        # the Ollama client constructor is lazy and won't fail when the
        # daemon is down, so we actively check reachability here.
        if mock is not None:
            self.mock = bool(mock)
        elif self._client is None:
            self.mock = True
        else:
            self.mock = not self._reachable()

    def _reachable(self) -> bool:
        """Quick probe to see if the Ollama daemon answers."""
        if self._client is None:
            return False
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """
        Generate text response from LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            stream: Whether to stream response internally

        Returns:
            Generated text content
        """
        if self.mock:
            return self._mock_generate(messages)

        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": 4096,   # Limit max tokens
                    "num_ctx": self.num_ctx,
                },
                stream=stream
            )

            if stream:
                content = ""
                for chunk in response:
                    content += chunk.get('message', {}).get('content', '')
                return self._strip_think(content)
            return self._strip_think(response['message']['content'])

        except Exception as e:
            raise RuntimeError(f"LLM request failed: {str(e)}")

    @staticmethod
    def _strip_think(text: str) -> str:
        """Remove qwen3-style ``<think>…</think>`` reasoning blocks from output.

        Qwen3 and other reasoning models emit an internal monologue wrapped in
        ``<think>`` tags. It must never reach the transcript or the tool parser.
        """
        if not text:
            return text
        # Drop complete think blocks, then any dangling unterminated opener.
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        cleaned = re.sub(r"<think>.*$", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Single non-streaming decision turn with native function-calling.

        Passes ``tools`` (a list of JSON-schema function definitions) to the
        Ollama ``chat`` endpoint and returns a normalized message so callers
        don't depend on the raw client object shape.

        Args:
            messages: Conversation context (role/content dicts, plus optional
                ``tool`` role results).
            tools: Tool/function schemas, or None to disable tool calling.
            temperature: Sampling temperature.

        Returns:
            ``{"content": str, "tool_calls": [{"name": str, "arguments": dict}, ...]}``
            ``tool_calls`` is an empty list when the model returns a plain answer
            or when running in offline mock mode.
        """
        if self.mock:
            # Mock mode never calls tools so offline tests stay deterministic.
            return {"content": self._mock_generate(messages), "tool_calls": []}

        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                tools=tools or None,
                options={
                    "temperature": temperature,
                    "num_predict": 4096,
                    "num_ctx": self.num_ctx,
                },
                stream=False,
            )
        except Exception as e:
            raise RuntimeError(f"LLM tool-call request failed: {str(e)}")

        message = response.get("message", {}) if isinstance(response, dict) else {}
        # ollama returns Message objects in newer clients; support both.
        if not message and hasattr(response, "message"):
            message = response.message

        content = ""
        raw_calls = None
        if isinstance(message, dict):
            content = message.get("content", "") or ""
            raw_calls = message.get("tool_calls")
        else:
            content = getattr(message, "content", "") or ""
            raw_calls = getattr(message, "tool_calls", None)

        return {"content": self._strip_think(content),
                "tool_calls": self._normalize_tool_calls(raw_calls)}

    @staticmethod
    def _normalize_tool_calls(raw_calls) -> List[Dict[str, Any]]:
        """Normalize Ollama tool-call entries to ``{name, arguments}`` dicts."""
        normalized: List[Dict[str, Any]] = []
        for call in raw_calls or []:
            # Each call may be a dict or an object with a ``.function`` attr.
            func = None
            if isinstance(call, dict):
                func = call.get("function", call)
            else:
                func = getattr(call, "function", call)

            if isinstance(func, dict):
                name = func.get("name")
                args = func.get("arguments", {})
            else:
                name = getattr(func, "name", None)
                args = getattr(func, "arguments", {})

            # Arguments may arrive as a JSON string from some servers.
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, ValueError):
                    args = {}
            if not isinstance(args, dict):
                args = {}

            if name:
                normalized.append({"name": name, "arguments": args})
        return normalized

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """
        Stream a text response token-by-token.

        Yields:
            Incremental content chunks as they are produced.
        """
        if self.mock:
            yield from self._mock_stream(messages)
            return

        try:
            response = self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": 4096,
                    "num_ctx": self.num_ctx,
                },
                stream=True,
            )
            in_think = False
            for chunk in response:
                piece = chunk.get('message', {}).get('content', '')
                if not piece:
                    continue
                # Suppress any <think>…</think> reasoning while streaming.
                if in_think:
                    if "</think>" in piece:
                        piece = piece.split("</think>", 1)[1]
                        in_think = False
                    else:
                        continue
                if "<think>" in piece:
                    before, _, after = piece.partition("<think>")
                    if "</think>" in after:
                        piece = before + after.split("</think>", 1)[1]
                    else:
                        piece = before
                        in_think = True
                if piece:
                    yield piece
        except Exception as e:
            raise RuntimeError(f"LLM streaming failed: {str(e)}")

    # === Offline mock mode ===============================================
    # When Ollama is unavailable (no GPU / not installed) the client falls
    # back to a deterministic responder so the TUI stays fully usable for
    # demos and development.

    def _mock_generate(self, messages: List[Dict[str, str]]) -> str:
        return "".join(self._mock_stream(messages))

    def _mock_stream(self, messages: List[Dict[str, str]]) -> Iterator[str]:
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break
        text = (
            "[offline mock] Ollama isn't reachable, so I'm echoing a stub "
            "response. Start Ollama and pull a model "
            f"(`ollama pull {self.model}`) to get real answers.\n\n"
            f"You said: {last_user.strip()[:280]}"
        )
        for word in text.split(" "):
            yield word + " "

    def generate_structured(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output from LLM.
        Uses JSON repair to handle malformed outputs.
        
        Args:
            messages: List of message dicts
            temperature: Lower temperature for more deterministic output
            
        Returns:
            Parsed dictionary from LLM response
        """
        response_text = self.generate(messages, temperature=temperature)
        return repair_and_extract_json(response_text)

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Simple estimation: 1 token ≈ 4 characters for English text.
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // 4

    def is_available(self) -> bool:
        """
        Check if the Ollama server is reachable and the model is loaded.

        Returns:
            True if server is reachable and the configured model exists.
        """
        if self.mock or self._client is None:
            return False
        try:
            models = self.list_models()
            return any(self.model in name for name in models)
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Return the names of models available on the Ollama server."""
        if self._client is None:
            return []
        try:
            data = self._client.list()
            names = []
            for m in data.get('models', []):
                # ollama>=0.4 uses `model`, older uses `name`
                names.append(m.get('model') or m.get('name') or '')
            return [n for n in names if n]
        except Exception:
            return []
