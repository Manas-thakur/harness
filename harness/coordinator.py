"""
Coordinator for Agent Orchestration
Routes tasks to specialist agents, manages context, and enforces safety limits.
"""

import json
import re
import time
from typing import Dict, List, Optional
from harness.llm_client import LocalLLMClient
from harness.hooks import HookDispatcher
from harness.token_counter import TokenCounter
from harness.memory import MemoryStore
from harness.tools import ToolRegistry, TOOL_SCHEMAS
from harness.threads import AgentThread
from harness.agents import ResearchAgent, TutorAgent, CoderAgent, DreamerAgent


class Coordinator:
    """
    Main orchestrator for the AI agent system.
    Handles intent classification, agent routing, and safety enforcement.
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
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

        # Initialize Specialist Agents (Scoped). These now act as
        # configuration holders (system prompt + allowed tools); conversation
        # history lives in the single shared thread below so switching
        # specialists mid-conversation never drops or duplicates context.
        self.agents = {
            "researcher": ResearchAgent(),
            "tutor": TutorAgent(),
            "coder": CoderAgent(),
            "dreamer": DreamerAgent()
        }

        # One shared conversation thread across all specialists.
        self.conversation = AgentThread(agent_name="conversation")

        # Two-Strike Rule tracking
        self.recent_tool_calls: List[str] = []

        # Stable per-session transcript filename (set on first save).
        self._session_file: Optional[str] = None

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

        # 3. Intent Routing (sticky)
        target_key = self._route(user_prompt)
        target_agent = self.agents[target_key]
        self.last_agent = target_key
        emit("route", {"agent": target_key})

        # 4. Execute streaming agent loop
        response = self._execute_agent_loop_streaming(
            target_agent, user_prompt, emit, on_token
        )

        # 5. Context Compaction Check (shared conversation)
        if self.conversation.is_context_full():
            self.conversation.compact_old_messages(keep_last_n=4)

        # 6. Fire Hook: Stop
        self.hooks.fire("Stop", {"response": response})

        self.current_turn += 1
        self._save_transcript_entry("user", user_prompt)
        self._save_transcript_entry("assistant", response)

        # 7. Self-improvement: persist this session and capture durable facts.
        self._persist_session()
        self._auto_capture(user_prompt, response)
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
        context = self.conversation.get_context()
        # The selected specialist contributes only its system prompt + tools.
        context.insert(0, {"role": "system", "content": agent.system_prompt})
        self._inject_layers(context)
        context.append({"role": "user", "content": user_prompt})
        self.conversation.add_message("user", user_prompt)
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

    def _extract_tool_calls(self, msg: Dict, allowed_tools=None) -> List[Dict]:
        """
        Get tool calls from a chat_with_tools result.

        Resolution order: native ``tool_calls`` → a JSON ``{"tool": ...}`` blob
        in content → a best-effort recovery of a prose/function-syntax call
        (e.g. ``search_web(query="...")``) limited to the agent's allowed tools.
        Returns a list of ``{"name", "arguments"}`` dicts.
        """
        tool_calls = list(msg.get("tool_calls") or [])
        content = msg.get("content") or ""
        if not tool_calls and content:
            parsed = self._parse_tool_call(content)
            if parsed:
                tool_calls = [{"name": parsed["name"], "arguments": parsed["input"]}]
            elif allowed_tools:
                recovered = self._recover_tool_call(content, allowed_tools)
                if recovered:
                    tool_calls = [recovered]
        return tool_calls

    @staticmethod
    def _first_param(tool_name: str) -> Optional[str]:
        """First required (or first declared) parameter name for a tool."""
        schema = TOOL_SCHEMAS.get(tool_name)
        if not schema:
            return None
        params = schema.get("parameters", {})
        required = params.get("required") or []
        if required:
            return required[0]
        props = list(params.get("properties", {}).keys())
        return props[0] if props else None

    def _recover_tool_call(self, content: str, allowed_tools) -> Optional[Dict]:
        """Best-effort recovery of a tool call written as prose / function syntax.

        Handles ``tool_name(key="value", ...)`` and ``tool_name("value")`` where
        ``tool_name`` is one the agent may use. Returns ``{"name","arguments"}``
        or None when no confident call can be extracted (the caller then nudges
        the model rather than inventing arguments).
        """
        m = re.search(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)", content)
        if not m or m.group(1) not in allowed_tools:
            return None
        name, argstr = m.group(1), m.group(2).strip()
        args: Dict[str, str] = {}
        for km in re.finditer(r"(\w+)\s*=\s*[\"']([^\"']*)[\"']", argstr):
            args[km.group(1)] = km.group(2)
        if not args and argstr:
            val = argstr.strip().strip("\"'")
            first = self._first_param(name)
            if first and val:
                args[first] = val
        return {"name": name, "arguments": args}

    @staticmethod
    def _mentions_tool(content: str, allowed_tools) -> bool:
        """True if content references a tool by name without calling it."""
        if not content:
            return False
        if "[calling" in content.lower():
            return True
        return any(re.search(rf"\b{re.escape(t)}\b", content) for t in allowed_tools)

    # Nudge appended when the model describes a tool call in prose instead of
    # invoking it through the function interface.
    _TOOL_NUDGE = (
        "The function-calling interface is active. Do NOT describe or narrate "
        "tool calls in text (e.g. '[Calling search_web]'). Either call the tool "
        "now through the function interface, or give your final answer."
    )

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
        # Feed the call back as STRUCTURED function-calling messages (never the
        # old "[Calling X]" prose, which trained the model to fake tool calls).
        context.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }],
        })
        context.append({"role": "tool", "name": name, "content": tool_result})
        self.conversation.add_tool_call(name, arguments, tool_result)
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

    def _run_tool_loop(self, agent, context, schemas, emit, max_agent_turns: int = 10):
        """Drive chat_with_tools until the model returns a plain answer.

        Executes any tool calls and loops. If the model *describes* a tool call
        in prose instead of invoking it, nudge it once before accepting prose as
        the final answer. Returns the answer string, an ``Error: …`` string, or
        None if the tool budget is exhausted.
        """
        nudged = False
        for _ in range(max_agent_turns):
            try:
                msg = self.llm.chat_with_tools(context, tools=schemas, temperature=0.7)
            except Exception as e:
                emit("error", {"message": str(e)})
                return f"Error: LLM generation failed - {e}"

            tool_calls = self._extract_tool_calls(msg, agent.allowed_tools)
            if tool_calls:
                for tc in tool_calls:
                    self._dispatch_tool(agent, tc["name"], tc.get("arguments", {}), context, emit)
                nudged = False
                continue

            content = (msg.get("content") or "").strip()
            if not nudged and self._mentions_tool(content, agent.allowed_tools):
                context.append({"role": "system", "content": self._TOOL_NUDGE})
                nudged = True
                continue
            return content
        return None

    def _critique(self, context: List[Dict], answer: str) -> Dict:
        """One cheap, low-temp review of a draft answer's grounding/completeness."""
        try:
            from harness.llm_client import repair_and_extract_json
            prompt = (
                "You are a strict reviewer. Given the conversation above and the "
                "draft answer below, decide if the answer is grounded in the tool "
                "results and actually answers the user. If current/factual info "
                "was needed but never gathered with a tool, it is NOT ok.\n\n"
                f"Draft answer:\n{answer}\n\n"
                'Reply with ONLY JSON: {"ok": true|false, "issue": "<problem>", '
                '"suggestion": "<what to search or do>"}'
            )
            msgs = context + [{"role": "user", "content": prompt}]
            data = repair_and_extract_json(self.llm.generate(msgs, temperature=0.1))
            if isinstance(data, dict) and "ok" in data:
                return {
                    "ok": bool(data.get("ok")),
                    "issue": str(data.get("issue", "")),
                    "suggestion": str(data.get("suggestion", "")),
                }
        except Exception:
            pass
        return {"ok": True}

    def _reflect_and_refine(self, agent, context, schemas, final, emit,
                            max_rounds: int = 1) -> str:
        """Self-improvement gate: critique the draft once and, if it's flagged as
        ungrounded/incomplete, gather more via tools and produce a better answer.

        Skipped in offline mock mode and for error strings so tests stay fast and
        deterministic.
        """
        if self.llm.mock or not final or final.startswith("Error:"):
            return final
        for _ in range(max_rounds):
            verdict = self._critique(context, final)
            if verdict.get("ok", True):
                break
            emit("reflect", {"issue": verdict.get("issue", ""),
                             "suggestion": verdict.get("suggestion", "")})
            context.append({"role": "assistant", "content": final})
            context.append({"role": "system", "content": (
                f"A reviewer flagged your draft answer. Issue: "
                f"{verdict.get('issue','')}. Suggestion: "
                f"{verdict.get('suggestion','')}. Use your tools to address this, "
                "then give a corrected final answer.")})
            refined = self._run_tool_loop(agent, context, schemas, emit)
            if refined and not refined.startswith("Error:"):
                final = refined
            else:
                break
        return final

    def _execute_agent_loop_streaming(self, agent, user_prompt, emit, on_token) -> str:
        """
        Agent loop using native tool calling, with a self-improvement gate,
        streaming the final answer.

        Gathers information via the tool loop, runs one reflect/refine pass to
        ground the answer, then chunks the result to ``on_token`` so the TUI
        renders it live.
        """
        emit_token = on_token or (lambda chunk: None)

        context = self._build_context(agent, user_prompt)
        schemas = self.tools.get_schemas(agent.allowed_tools)

        final = self._run_tool_loop(agent, context, schemas, emit)
        if final is None:
            final = "I've reached the maximum number of tool calls for this turn."
        final = self._reflect_and_refine(agent, context, schemas, final, emit)

        for piece in self._chunk_text(final):
            emit_token(piece)
        self.conversation.add_message("assistant", final)
        return final

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

        # 3. Intent Routing (sticky)
        target_agent_key = self._route(user_prompt)
        target_agent = self.agents[target_agent_key]
        self.last_agent = target_agent_key

        # 4. Execute Agent Loop
        response = self._execute_agent_loop(target_agent, user_prompt)

        # 5. Context Compaction Check (shared conversation)
        if self.conversation.is_context_full():
            self.conversation.compact_old_messages(keep_last_n=4)

        # 6. Fire Hook: Stop
        self.hooks.fire("Stop", data={"response": response})

        self.current_turn += 1
        self._save_transcript_entry("user", user_prompt)
        self._save_transcript_entry("assistant", response)

        # 7. Self-improvement: persist + capture durable facts.
        self._persist_session()
        self._auto_capture(user_prompt, response)
        return response

    # Keyword pre-router: cheap, deterministic routing for obvious cases so we
    # don't pay an LLM call (or its variance) on every turn.
    _ROUTE_KEYWORDS = {
        "coder": ("code", "function", "bug", "git", "commit", "repo", "file",
                  "compile", "refactor", "python", "javascript", "script", "test",
                  "debug", "stack trace", "edit", "implement"),
        "researcher": ("search", "web", "google", "latest", "news", "who won",
                       "find", "look up", "research", "paper", "article", "url",
                       "website", "current", "today", "2024", "2025", "2026"),
        "tutor": ("explain", "teach", "what is", "how does", "quiz", "learn",
                  "understand", "concept", "analogy", "study"),
    }

    def _route(self, prompt: str) -> str:
        """Pick a specialist: keyword pre-router → LLM classifier → stickiness.

        Stays on the current specialist when the signal is weak/general, so a
        multi-turn conversation doesn't bounce between agents.
        """
        low = prompt.lower()
        scores = {a: sum(1 for k in kws if k in low)
                  for a, kws in self._ROUTE_KEYWORDS.items()}
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best

        intent = self._classify_intent(prompt)
        key = self.AGENT_MAP.get(intent.get("agent", "general"), "")
        # "general"/unknown → keep the current specialist for continuity.
        if intent.get("agent") in (None, "general") or key not in self.agents:
            return self.last_agent or "researcher"
        return key

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
            response = self.llm.generate(messages, temperature=0.0)
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

        final = self._run_tool_loop(agent, context, schemas, noop)
        if final is None:
            final = "I've reached the maximum number of tool calls. Here's what I found so far."
        final = self._reflect_and_refine(agent, context, schemas, final, noop)
        self.conversation.add_message("assistant", final)
        return final

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
        """Save session transcript to a stable per-session file (overwrite)."""
        from pathlib import Path
        from harness.file_ops import write_atomic

        sessions_dir = Path(path)
        sessions_dir.mkdir(parents=True, exist_ok=True)

        if self._session_file is None:
            stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            self._session_file = str(sessions_dir / f"{stamp}_session.md")

        content = "# Session Transcript\n\n"
        for entry in self.session_transcript:
            role = entry['role'].upper()
            content += f"## {role}\n{entry['content']}\n\n"

        write_atomic(self._session_file, content)

    def _persist_session(self):
        """Best-effort auto-save of the transcript after each turn."""
        try:
            if self.session_transcript:
                self.save_session_transcript()
        except Exception:
            pass

    def _auto_capture(self, user_prompt: str, response: str):
        """Extract durable profile facts from a turn and store them.

        Model-driven; skipped in mock mode. A ``VersioningSystem`` snapshot is
        taken before any write so automatic memory edits are always recoverable.
        """
        if self.llm.mock:
            return
        try:
            from harness.llm_client import repair_and_extract_json
            prompt = (
                "From the exchange below, extract ONLY durable facts about the "
                "user or their project worth remembering long-term (identity, "
                "what they're working on, lasting preferences). Ignore one-off "
                "questions. If nothing durable, return an empty list.\n\n"
                f"User: {user_prompt}\nAssistant: {response}\n\n"
                'Reply with ONLY JSON: {"facts": [{"section": "About|Current '
                'Work|User Preferences", "content": "..."}]}'
            )
            data = repair_and_extract_json(
                self.llm.generate([{"role": "user", "content": prompt}], temperature=0.0)
            )
            facts = data.get("facts") if isinstance(data, dict) else None
            if not facts:
                return
            self._snapshot_memory()
            for f in facts:
                content = (f.get("content") or "").strip()
                if not content:
                    continue
                section = f.get("section") or "About"
                self.tools.execute("update_profile",
                                   {"section": section, "content": content})
        except Exception:
            pass

    def _snapshot_memory(self):
        """Take a recoverable snapshot of memory before an automatic mutation."""
        try:
            from harness.versioning import VersioningSystem
            VersioningSystem().create_snapshot()
        except Exception:
            pass

    def reset_conversation(self):
        """Clear the shared conversation and per-session state (for /clear)."""
        self.conversation = AgentThread(agent_name="conversation")
        self.recent_tool_calls = []
        self.current_turn = 0
        self.session_transcript = []
        self._session_file = None
        self.last_agent = None

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
