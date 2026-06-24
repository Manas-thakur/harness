# 📋 Component Specification 4: The Agent Base & Specialist Threads

This component is the **workforce** of your system. While the Coordinator is the "brain" and Hooks are the "nervous system," the Specialist Agents are the "hands" that actually execute tasks. 

The critical challenge here is **simulating a multiagent system on a single local GPU**. We cannot run five 7B models simultaneously on an RTX 4060 8GB. Instead, we implement **Context Isolation and Sequential Execution**—swapping out the system prompt and conversation history (the "thread") for whichever agent is currently active.

---

### **File Locations**
*   `harness/agent_base.py` (Core abstractions)
*   `harness/threads.py` (Context management)
*   `harness/agents.py` (Specialist implementations)

### **Responsibilities**
1.  **Thread Isolation:** Maintain separate, isolated conversation histories (context windows) for each specialist agent.
2.  **Tool Scoping:** Enforce strict allowlists so agents only have access to the tools they need (security + performance).
3.  **Domain Specialization:** Inject specific system prompts that tune the 7B model's behavior for different tasks (e.g., coding vs. teaching).
4.  **Lifecycle Management:** Track agent states (`idle`, `running`, `archived`) to manage resources and prevent context bloat.

---

### **Class Structure & Methods**

#### **1. The Thread (`harness/threads.py`)**
This class manages the isolated context window for a single agent. It's essentially a wrapper around a list of messages, with built-in token counting and state management.

```python
import time
from typing import List, Dict, Any
from enum import Enum

class ThreadState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    ARCHIVED = "archived"

class AgentThread:
    def __init__(self, agent_name: str, max_tokens: int = 28000):
        self.agent_name = agent_name
        self.history: List[Dict[str, str]] = []
        self.state = ThreadState.IDLE
        self.created_at = time.time()
        self.last_active = time.time()
        self.max_tokens = max_tokens # Safety limit for local model
        
        # Metadata for the Coordinator
        self.turn_count = 0
        self.total_tool_calls = 0

    def add_message(self, role: str, content: str):
        """Appends a message to the thread's history."""
        self.history.append({"role": role, "content": content})
        self.last_active = time.time()
        self.turn_count += 1

    def get_context(self) -> List[Dict[str, str]]:
        """Returns the full conversation history for the LLM."""
        return self.history.copy()

    def is_context_full(self) -> bool:
        """Checks if the thread is approaching the local model's context limit."""
        # Simple estimation: 1 token ≈ 4 characters
        total_chars = sum(len(m.get('content', '')) for m in self.history)
        return (total_chars / 4) > self.max_tokens

    def archive(self):
        """Moves the thread to archived state to free up 'active' slots."""
        self.state = ThreadState.ARCHIVED
```

#### **2. The Base Agent (`harness/agent_base.py`)**
This is the abstract class that all specialists inherit from. It defines the contract for how agents interact with the Coordinator and the Tool Registry.

```python
from abc import ABC, abstractmethod
from harness.threads import AgentThread, ThreadState

class BaseAgent(ABC):
    def __init__(self, name: str, allowed_tools: list[str], system_prompt: str):
        self.name = name
        self.allowed_tools = allowed_tools
        self.system_prompt = system_prompt
        self.thread = AgentThread(agent_name=name)

    @abstractmethod
    def run(self, task: str, coordinator) -> str:
        """Execute a task. Implemented by specialists."""
        pass

    def can_use_tool(self, tool_name: str) -> bool:
        """Enforces tool scoping."""
        return tool_name in self.allowed_tools

    def get_active_context(self) -> list:
        """Prepends the system prompt to the thread history for the LLM."""
        if self.thread.state == ThreadState.IDLE:
            self.thread.state = ThreadState.RUNNING
            
        # Inject system prompt as the first message if history is empty
        context = self.thread.get_context()
        if not context or context[0].get('role') != 'system':
            context.insert(0, {"role": "system", "content": self.system_prompt})
            
        return context
```

#### **3. The Specialists (`harness/agents.py`)**
These are the concrete implementations. Notice how the system prompts are highly constrained to prevent the 7B model from hallucinating capabilities it doesn't have.

```python
from harness.agent_base import BaseAgent

class ResearchAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="researcher",
            allowed_tools=["search_web", "read_file", "read_pdf", "summarize"],
            system_prompt="""You are a research specialist. 
            - Your ONLY job is to find information using search_web and read documents.
            - Do NOT write code or edit files.
            - Cite your sources clearly.
            - If you cannot find the answer, state that explicitly."""
        )

    def run(self, task: str, coordinator) -> str:
        # 1. Get context (system prompt + history)
        context = self.get_active_context()
        context.append({"role": "user", "content": task})
        
        # 2. Call local LLM (handled by coordinator/llm_client)
        # 3. Parse tool calls and execute them via coordinator
        # 4. Return final text response
        return coordinator.execute_agent_loop(self, context)

class TutorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="tutor",
            allowed_tools=["explain", "quiz_me", "create_analogy", "read_memory"],
            system_prompt="""You are a study companion.
            - Your job is to explain concepts simply and adapt to the user's level.
            - Use analogies frequently.
            - Check for understanding by asking follow-up questions.
            - Do NOT search the web or write code."""
        )

    def run(self, task: str, coordinator) -> str:
        context = self.get_active_context()
        context.append({"role": "user", "content": task})
        return coordinator.execute_agent_loop(self, context)

class CoderAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="coder",
            allowed_tools=["bash", "read_file", "write_file", "edit_file", "git_clone", "git_commit"],
            system_prompt="""You are a software engineer.
            - You write, read, and edit code.
            - Always read a file before editing it.
            - Use bash for git operations and running tests.
            - Do NOT search the web or explain concepts like a tutor."""
        )

    def run(self, task: str, coordinator) -> str:
        context = self.get_active_context()
        context.append({"role": "user", "content": task})
        return coordinator.execute_agent_loop(self, context)

class DreamerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="dreamer",
            allowed_tools=["read_sessions", "read_memory", "write_memory"],
            system_prompt="""You are the dreaming agent.
            - You ONLY run during batch consolidation.
            - Your job is to read session transcripts and reorganize the memory store.
            - You do NOT interact with the user directly."""
        )
```

---

### **Key Design Decisions for RTX 4060 (8GB VRAM)**

*   **Sequential Execution, Not Parallel:** We explicitly **do not** use `asyncio.gather()` to run agents concurrently. Running two 7B models simultaneously would cause an Out-Of-Memory (OOM) error on an 8GB card. The Coordinator calls `agent.run()` one at a time.
*   **Context Swapping:** When the Coordinator delegates a task to the `ResearchAgent`, it loads the `ResearchAgent`'s thread into the Ollama context. When that task finishes, the context is cleared, and the `TutorAgent`'s thread is loaded for the next task. This keeps VRAM usage constant.
*   **Strict Tool Scoping:** A 7B model is easily confused if given 20 tools. By giving the `TutorAgent` only 4 tools, we drastically reduce the chance of it hallucinating a tool call or outputting invalid JSON. This is critical for local model reliability.
*   **Stateless Agents, Stateful Threads:** The `BaseAgent` class itself holds no state between runs other than its configuration. All state (conversation history) is stored in the `AgentThread`. This makes it easy to archive old threads to free up RAM.

---

### **Integration Points**

1.  **In the Coordinator (`harness/coordinator.py`):**
    *   The Coordinator holds a registry of all agents: `self.agents = {"researcher": ResearchAgent(), ...}`.
    *   When routing a task, it calls `target_agent.run(task, self)`.
    *   The `execute_agent_loop` method handles the back-and-forth between the local LLM and the Tool Registry, ensuring the agent only calls tools in its `allowed_tools` list.

2.  **In the Tool Registry (`harness/tools.py`):**
    *   Before executing any tool, the registry checks: 
        `if not current_agent.can_use_tool(tool_name): raise PermissionError(...)`
    *   This is the enforcement layer for the scoping defined in the agents.

3.  **In the Hooks (`harness/hooks.py`):**
    *   When `agent.run()` starts, the Coordinator fires the `SubagentStart` hook: 
        `self.hooks.fire("SubagentStart", {"agent_type": agent.name})`
    *   When the agent finishes, it fires `SubagentStop`. This allows hooks to log agent activity or inject context into the agent's thread before it starts.

---

### **Why This Wins the Interview**

✅ **Solves the Local Hardware Problem:** You explicitly address the VRAM limitation by designing a sequential, context-swapping architecture instead of a naive parallel one. This shows deep systems-level thinking.
✅ **Security by Design:** Tool scoping prevents a "Tutor" agent from accidentally deleting files via Bash. This is a mature, production-grade pattern.
✅ **Prompt Engineering for Small Models:** The system prompts are highly constrained. You demonstrate that you understand local 7B models need strict guardrails to perform well.
✅ **Clean Abstraction:** The separation of `Agent` (behavior), `Thread` (state), and `Coordinator` (routing) makes the codebase modular and easy to extend with new specialists.

---

**Ready for Component 5?** 
Component 5 will cover **The Skill Loader & Tool Registry**, detailing exactly how we implement progressive disclosure (Level 1, 2, 3 loading) and the free tools (DuckDuckGo, Git, etc.) that power the agents. Just say the word!