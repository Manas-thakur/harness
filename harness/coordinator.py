"""
Coordinator for Agent Orchestration
Routes tasks to specialist agents, manages context, and enforces safety limits.
"""

import json
import time
from typing import Dict, List, Optional
from harness.llm_client import LocalLLMClient
from harness.hooks import HookDispatcher
from harness.token_counter import TokenCounter
from harness.memory import MemoryStore
from harness.tools import ToolRegistry
from harness.agents import ResearchAgent, TutorAgent, CoderAgent, DreamerAgent


class Coordinator:
    """
    Main orchestrator for the AI agent system.
    Handles intent classification, agent routing, and safety enforcement.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        max_turns: int = 20,
        mock: bool = None,
    ):
        """
        Initialize coordinator.

        Args:
            model: LLM model name
            max_turns: Maximum turns per session
            mock: Force offline mock mode (None = auto-detect Ollama)
        """
        self.llm = LocalLLMClient(model=model, mock=mock)
        self.max_turns = max_turns
        self.current_turn = 0

        # Initialize subsystems
        self.hooks = HookDispatcher()
        self.token_counter = TokenCounter()
        self.memory = MemoryStore()
        # Share the same MemoryStore with the tools so memory reads/writes
        # (remember/recall/update_profile) and the injected core block agree.
        self.tools = ToolRegistry(memory=self.memory)

        # Load the always-loaded soul/identity layer once.
        self.soul = self._load_soul()

        # Initialize Specialist Agents (Scoped)
        self.agents = {
            "researcher": ResearchAgent(),
            "tutor": TutorAgent(),
            "coder": CoderAgent(),
            "dreamer": DreamerAgent()
        }

        # Two-Strike Rule tracking
        self.recent_tool_calls: List[str] = []

        # Session transcript storage
        self.session_transcript: List[Dict] = []

        # Last agent that handled a request (for the TUI status line)
        self.last_agent: Optional[str] = None

    # Map intent categories to concrete agents.
    AGENT_MAP = {
        "researcher": "researcher",
        "tutor": "tutor",
        "coder": "coder",
        "dreamer": "dreamer",
        "general": "researcher",
    }

    def chat(self, user_prompt: str, on_event=None, on_token=None) -> str:
        """
        Streaming entry point used by the TUI.

        Args:
            user_prompt: User's input text.
            on_event: Optional callback ``fn(event_type, data)`` for routing,
                tool calls, blocks and errors.
            on_token: Optional callback ``fn(chunk)`` for streamed response text.

        Returns:
            The final assistant response.
        """
        emit = on_event or (lambda *a, **k: None)

        # 1. Fire Hook: UserPromptSubmit
        hook_decision = self.hooks.fire("UserPromptSubmit", {"prompt": user_prompt})
        if hook_decision.get("blocked"):
            reason = hook_decision.get("reason", "blocked by hook")
            emit("blocked", {"reason": reason})
            return f"⚠️ Request blocked: {reason}"

        # 2. Safety Check
        if self.current_turn >= self.max_turns:
            return "⚠️ Maximum turn limit reached. Please start a new session."

        # 3. Intent Routing
        intent = self._classify_intent(user_prompt)
        target_key = self.AGENT_MAP.get(intent.get("agent", "general"), "researcher")
        target_agent = self.agents[target_key]
        self.last_agent = target_key
        emit("route", {"agent": target_key, "reasoning": intent.get("reasoning", "")})

        # 4. Execute streaming agent loop
        response = self._execute_agent_loop_streaming(
            target_agent, user_prompt, emit, on_token
        )

        # 5. Context Compaction Check
        if target_agent.thread.is_context_full():
            target_agent.thread.compact_old_messages(keep_last_n=3)

        # 6. Fire Hook: Stop
        self.hooks.fire("Stop", {"response": response})

        self.current_turn += 1
        self._save_transcript_entry("user", user_prompt)
        self._save_transcript_entry("assistant", response)
        return response

    def _load_soul(self, path: str = "soul.md") -> str:
        """Read the always-loaded soul/identity document, if present."""
        try:
            from pathlib import Path
            p = Path(path)
            if p.exists():
                return p.read_text().strip()
        except Exception:
            pass
        return ""

    def _build_context(self, agent, user_prompt: str) -> List[Dict]:
        """
        Assemble the LLM context for a turn and record the user message.

        Layers (front to back): soul · role system prompt · core profile
        block · thread history · this user message. The soul and core block are
        injected into the returned copy only, so they never accumulate in the
        agent's persisted thread.
        """
        context = agent.get_active_context()
        self._inject_layers(context)
        context.append({"role": "user", "content": user_prompt})
        agent.thread.add_message("user", user_prompt)
        return context

    def _inject_layers(self, context: List[Dict]):
        """Prepend the soul and core-memory system messages to ``context``."""
        if self.soul:
            context.insert(0, {"role": "system", "content": self.soul})

        try:
            core = self.memory.read_core()
        except Exception:
            core = ""
        if core:
            # Insert after any leading system messages (soul + role prompt).
            pos = 0
            while pos < len(context) and context[pos].get("role") == "system":
                pos += 1
            context.insert(pos, {
                "role": "system",
                "content": "# Core memory (about the user)\n" + core,
            })

    def _extract_tool_calls(self, msg: Dict) -> List[Dict]:
        """
        Get tool calls from a chat_with_tools result.

        Prefers native ``tool_calls``; falls back to parsing a JSON tool call
        from plain content (for models/servers without function calling).
        Returns a list of ``{"name", "arguments"}`` dicts.
        """
        tool_calls = list(msg.get("tool_calls") or [])
        if not tool_calls and msg.get("content"):
            parsed = self._parse_tool_call(msg["content"])
            if parsed:
                tool_calls = [{"name": parsed["name"], "arguments": parsed["input"]}]
        return tool_calls

    def _dispatch_tool(self, agent, name: str, arguments: Dict, context: List[Dict], emit):
        """
        Execute one tool call with the two-strike guard and hooks.

        Appends the tool result (or block reason) to ``context`` and the agent
        thread. Returns the result string, or None when the call was repeated
        or blocked.
        """
        arguments = arguments or {}
        call_hash = f"{name}:{json.dumps(arguments, sort_keys=True)}"
        if call_hash in self.recent_tool_calls[-2:]:
            context.append({
                "role": "system",
                "content": "You are repeating yourself. Change your approach.",
            })
            return None
        self.recent_tool_calls.append(call_hash)
        if len(self.recent_tool_calls) > 10:
            self.recent_tool_calls.pop(0)

        hook_result = self.hooks.fire("PreToolUse", {
            "tool_name": name, "tool_input": arguments,
        })
        if hook_result.get("blocked"):
            reason = hook_result.get("reason", "blocked")
            emit("tool", {"name": name, "input": arguments,
                          "result": f"BLOCKED: {reason}", "blocked": True})
            context.append({"role": "tool", "content": f"Tool blocked: {reason}"})
            return None

        tool_result = self.tools.execute(name, arguments, agent)
        emit("tool", {"name": name, "input": arguments, "result": tool_result})
        context.append({"role": "assistant", "content": f"[Calling {name}]"})
        context.append({"role": "tool", "content": tool_result})
        agent.thread.add_tool_call(name, arguments, tool_result)
        self.hooks.fire("PostToolUse", {
            "tool_name": name, "tool_result": tool_result,
        })
        return tool_result

    @staticmethod
    def _chunk_text(text: str):
        """Yield a complete string word-by-word to mimic live streaming."""
        if not text:
            return
        words = text.split(" ")
        for i, word in enumerate(words):
            yield word if i == len(words) - 1 else word + " "

    def _execute_agent_loop_streaming(self, agent, user_prompt, emit, on_token) -> str:
        """
        Agent loop using native tool calling, streaming the final answer.

        Each turn is a non-streaming decision via ``chat_with_tools``. When the
        model requests tools they are executed and the loop continues; when it
        returns a plain answer that text is chunked to ``on_token`` so the TUI
        renders it live.
        """
        emit_token = on_token or (lambda chunk: None)

        context = self._build_context(agent, user_prompt)
        schemas = self.tools.get_schemas(agent.allowed_tools)

        max_agent_turns = 10
        for _ in range(max_agent_turns):
            try:
                msg = self.llm.chat_with_tools(context, tools=schemas, temperature=0.7)
            except Exception as e:
                m = f"Error: LLM generation failed - {e}"
                emit("error", {"message": str(e)})
                emit_token(m)
                return m

            tool_calls = self._extract_tool_calls(msg)
            if not tool_calls:
                final = (msg.get("content") or "").strip()
                for piece in self._chunk_text(final):
                    emit_token(piece)
                agent.thread.add_message("assistant", final)
                return final

            for tc in tool_calls:
                self._dispatch_tool(agent, tc["name"], tc.get("arguments", {}), context, emit)

        msg = "I've reached the maximum number of tool calls for this turn."
        emit_token(msg)
        return msg

    def process_input(self, user_prompt: str) -> str:
        """
        Main entry point for user interaction.
        
        Args:
            user_prompt: User's input text
            
        Returns:
            Agent response
        """
        # 1. Fire Hook: UserPromptSubmit
        hook_decision = self.hooks.fire(
            "UserPromptSubmit", 
            data={"prompt": user_prompt}
        )
        if hook_decision.get("blocked"):
            return f"⚠️ Request blocked: {hook_decision.get('reason')}"

        # 2. Safety Check
        if self.current_turn >= self.max_turns:
            return "⚠️ Maximum turn limit reached. Please start a new session."

        # 3. Intent Routing
        intent = self._classify_intent(user_prompt)
        target_agent_type = intent.get("agent", "general")

        # Map to actual agent
        agent_map = {
            "researcher": "researcher",
            "tutor": "tutor", 
            "coder": "coder",
            "dreamer": "dreamer",
            "general": "researcher"  # Default to researcher for general queries
        }
        target_agent_key = agent_map.get(target_agent_type, "researcher")
        target_agent = self.agents[target_agent_key]

        # 4. Execute Agent Loop
        response = self._execute_agent_loop(target_agent, user_prompt)

        # 5. Context Compaction Check
        if target_agent.thread.is_context_full():
            target_agent.thread.compact_old_messages(keep_last_n=3)

        # 6. Fire Hook: Stop
        self.hooks.fire("Stop", data={"response": response})

        self.current_turn += 1
        self._save_transcript_entry("user", user_prompt)
        self._save_transcript_entry("assistant", response)

        return response

    def _classify_intent(self, prompt: str) -> dict:
        """
        Use local LLM to classify intent and route to correct agent.
        
        Args:
            prompt: User's input
            
        Returns:
            Dict with agent type and reasoning
        """
        classification_prompt = f"""
Classify the user's request into one of these categories:
- researcher: Web search, finding papers, reading documents, summarizing information.
- tutor: Explaining concepts, creating quizzes, studying, learning adaptation.
- coder: GitHub operations, writing code, analyzing repositories, editing files.
- dreamer: Consolidating memory, running batch processing.
- general: Simple chat or questions that don't fit other categories.

User Request: "{prompt}"

Return ONLY JSON: {{"agent": "category_name", "reasoning": "brief reason"}}
"""
        try:
            from harness.llm_client import repair_and_extract_json
            messages = [{"role": "user", "content": classification_prompt}]
            response = self.llm.generate(messages, temperature=0.3)
            return repair_and_extract_json(response)
        except Exception as e:
            # Fallback to researcher for errors
            return {"agent": "researcher", "reasoning": f"Classification error: {e}"}

    def _execute_agent_loop(self, agent, user_prompt: str) -> str:
        """
        Execute the agent's tool loop for a task (non-streaming).

        Mirrors the streaming loop using native tool calling, for callers like
        ``agent ask`` that don't stream tokens.

        Args:
            agent: Target agent instance
            user_prompt: User's task

        Returns:
            Final response
        """
        noop = lambda *a, **k: None
        context = self._build_context(agent, user_prompt)
        schemas = self.tools.get_schemas(agent.allowed_tools)

        max_agent_turns = 10  # Limit per-agent turns
        for _ in range(max_agent_turns):
            try:
                msg = self.llm.chat_with_tools(context, tools=schemas, temperature=0.7)
            except Exception as e:
                return f"Error: LLM generation failed - {str(e)}"

            tool_calls = self._extract_tool_calls(msg)
            if not tool_calls:
                final = (msg.get("content") or "").strip()
                agent.thread.add_message("assistant", final)
                return final

            for tc in tool_calls:
                self._dispatch_tool(agent, tc["name"], tc.get("arguments", {}), context, noop)

        # Reached max turns without final response
        return "I've reached the maximum number of tool calls. Here's what I found so far."

    def _parse_tool_call(self, response: str) -> Optional[Dict]:
        """
        Parse tool call from LLM response.
        
        Args:
            response: LLM response text
            
        Returns:
            Tool call dict or None
        """
        try:
            from harness.llm_client import repair_and_extract_json

            # Try to extract JSON from response
            data = repair_and_extract_json(response)

            if isinstance(data, dict) and 'tool' in data:
                return {
                    'name': data.get('tool', data.get('tool_name')),
                    'input': data.get('input', data.get('arguments', {}))
                }
        except Exception:
            pass

        return None

    def _save_transcript_entry(self, role: str, content: str):
        """Save entry to session transcript."""
        self.session_transcript.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

    def save_session_transcript(self, path: str = "sessions"):
        """Save session transcript to file."""
        from pathlib import Path
        from harness.file_ops import write_atomic

        sessions_dir = Path(path)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y-%m-%d_%H-%M")
        filename = f"{timestamp}_session.md"
        filepath = sessions_dir / filename

        content = "# Session Transcript\n\n"
        for entry in self.session_transcript:
            role = entry['role'].upper()
            content += f"## {role}\n{entry['content']}\n\n"

        write_atomic(str(filepath), content)

    def get_status(self) -> dict:
        """Get coordinator status."""
        return {
            "current_turn": self.current_turn,
            "max_turns": self.max_turns,
            "agents": {
                name: agent.get_status() 
                for name, agent in self.agents.items()
            },
            "memory_stats": self.memory.get_summary_stats()
        }
