Here is the comprehensive, production-grade architecture for your local AI agent, followed by the detailed specification for the first core component. 

---

# 🏗️ High-Level System Architecture

This architecture is designed to be **lean, modular, and 100% local**, avoiding heavy frameworks like LangChain to ensure it runs smoothly on your RTX 4060 8GB VRAM. It uses an **Event-Driven Multiagent Pattern** inspired by Anthropic's Claude Code.

### **Architecture Diagram**

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LAYER 1: INTERFACE                                │
│  CLI (Typer) + Rich Console (Output formatting, spinners, panels)           │
───────────────────────────────┬─────────────────────────────────────────────┘
                                │ User Input / Commands
┌───────────────────────────────▼─────────────────────────────────────────────
│                      LAYER 2: CORE ORCHESTRATION                            │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │   Coordinator    │  │ Context Compactor│  │   Turn & Safety Limiter  │  │
│  │ (Intent Routing) │  │ (Token Manager)  │  │ (Max Turns, Timeouts)    │  │
│  └─────────────────┘  └──────────────────┘  └──────────────────────────  │
└───────────┼─────────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────────────────┐
│                        LAYER 3: EVENT & LIFECYCLE (HOOKS)                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Hook Dispatcher (Fires: UserPrompt, PreTool, PostTool, Stop, etc.)   │  │
│  │  ↳ Command Hooks, Prompt Hooks, Async Hooks                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└───────────┬─────────────────────────────────────────────────────────────────┘
            │
┌───────────▼─────────────────────────────────────────────────────────────────┐
│                          LAYER 4: AGENT LAYER                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Researcher   │  │    Tutor     │  │   Coder      │  │   Dreamer    │   │
│  │ (Scoped Tools│  │ (Scoped Tools│  │ (Scoped Tools│  │ (Scoped Tools│   │
│  │  + Thread)   │  │  + Thread)   │  │  + Thread)   │  │  + Thread)   │   │
│  └──────┬───────  └──────┬───────  └──────┬───────  └──────┬───────   │
└─────────┼──────────────────┼─────────────────┼─────────────────┼───────────┘
          │                  │                 │                 │
┌─────────▼──────────────────▼─────────────────▼─────────────────▼───────────┐
│                       LAYER 5: TOOLS & SKILLS                              │
│  ┌──────────────────────┐           ┌──────────────────────────────────┐   │
│  │    Tool Registry     │           │         Skill Loader             │   │
│  │ - Bash (Env persist) │           │ - Level 1: Metadata (Always)     │   │
│  │ - Read / Write / Edit│           │ - Level 2: Instructions (On use) │   │
│  │ - GitHub (git/gh)    │           │ - Level 3: Scripts/Refs (On exec)│   │
│  │ - Web Search (DDG)   │           ──────────────────────────────────┘   │
│  └──────────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                       LAYER 6: MEMORY & STATE                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Active Memory│  │   Versioning │  │   Dreaming   │  │   Sessions   │   │
│  │  (memory.md) │  │  (Git/Files) │  │ (Batch Proc) │  │ (Transcripts)│   │
│  └──────────────┘  └──────────────  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────────────┐
│                       LAYER 7: INFRASTRUCTURE                               │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │   Ollama Client  │  │  Local Filesystem│  │   Subprocess Manager     │  │
│  │ (Qwen2.5-7B)     │  │  (I/O, Git, gh)  │  │ (Bash, Python scripts)   │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

# 📋 Component Specification 1: Core Orchestration & Coordinator

This is the "brain" of the system. It receives user input, decides which agent should handle it, manages the context window, and enforces safety limits.

### **File Location**
`harness/coordinator.py`

### **Responsibilities**
1.  **Intent Classification:** Analyze the user's prompt to determine which specialist agent (Researcher, Tutor, Coder, Dreamer) should handle it.
2.  **Context Management:** Track token usage and trigger the `ContextCompactor` when the conversation gets too long for the 7B model's context window.
3.  **Safety & Limits:** Enforce `max_turns` to prevent infinite loops and manage timeouts.
4.  **Event Dispatching:** Act as the trigger for the Hook System (firing `UserPromptSubmit`, `Stop`, etc.).

### **Class Structure & Methods**

```python
class Coordinator:
    def __init__(self, model: str = "qwen2.5:7b", max_turns: int = 20):
        self.llm = OllamaClient(model)
        self.max_turns = max_turns
        self.current_turn = 0
        
        # Initialize subsystems
        self.hooks = HookSystem()
        self.compactor = ContextCompactor(max_tokens=28000) # ~80% of 32k window
        self.memory = MemoryStore()
        self.skills = SkillLoader()
        
        # Initialize Specialist Agents (Scoped)
        self.agents = {
            "researcher": ResearchAgent(allowed_tools=["search_web", "read_file"]),
            "tutor": TutorAgent(allowed_tools=["explain", "quiz_me"]),
            "coder": CoderAgent(allowed_tools=["bash", "git_clone", "git_commit"]),
            "dreamer": DreamerAgent(allowed_tools=["read_sessions", "rewrite_memory"])
        }

    async def process_input(self, user_prompt: str) -> str:
        """Main entry point for user interaction."""
        # 1. Fire Hook: UserPromptSubmit
        hook_decision = self.hooks.fire("UserPromptSubmit", data={"prompt": user_prompt})
        if hook_decision.get("blocked"):
            return hook_decision["reason"]

        # 2. Safety Check
        if self.current_turn >= self.max_turns:
            return "⚠️ Maximum turn limit reached. Please start a new session."

        # 3. Intent Routing
        intent = await self._classify_intent(user_prompt)
        target_agent = self.agents[intent["agent"]]

        # 4. Execute Agent Loop
        response = await target_agent.run(user_prompt)
        
        # 5. Context Compaction Check
        if self.compactor.should_compact(target_agent.thread.history):
            target_agent.thread.history = self.compactor.compact(target_agent.thread.history)
            console.print("[yellow] Context compacted to save memory.[/]")

        # 6. Fire Hook: Stop
        self.hooks.fire("Stop", data={"response": response})
        
        self.current_turn += 1
        return response

    async def _classify_intent(self, prompt: str) -> dict:
        """Uses the local LLM to classify intent and route to the correct agent."""
        # Lightweight prompt to save tokens
        classification_prompt = f"""
        Classify the user's request into one of these categories:
        - researcher: Web search, finding papers, reading documents.
        - tutor: Explaining concepts, creating quizzes, studying.
        - coder: GitHub operations, writing code, analyzing repositories.
        - dreamer: Consolidating memory, running batch processing.
        - general: Simple chat or questions.

        User Request: "{prompt}"
        
        Return ONLY JSON: {{"agent": "category_name", "reasoning": "brief reason"}}
        """
        response = await self.llm.generate(classification_prompt)
        return json.loads(response)
```

### **Key Design Decisions for RTX 4060 (8GB VRAM)**
*   **No LangChain/LlamaIndex:** We use raw Python and the `ollama` python library. This saves ~500MB of RAM and prevents framework overhead from slowing down the 7B model.
*   **Lightweight Classification:** The `_classify_intent` method uses a highly constrained prompt. We don't use a separate embedding model for routing; we just ask the 7B model to output JSON. It's fast and accurate enough for this use case.
*   **Aggressive Compaction:** The `ContextCompactor` is set to trigger at 28,000 tokens. Local 7B models degrade in performance and speed when the context gets too full. Compacting early keeps inference fast.

### **Integration Points**
*   **Hooks:** The `process_input` method explicitly calls `self.hooks.fire()`. If a hook returns a "block" decision, the Coordinator halts execution immediately.
*   **Memory:** The Coordinator doesn't read the memory directly; it passes the relevant memory context to the Specialist Agent during the `run()` phase.
*   **CLI:** The Typer CLI (`agent.py`) simply instantiates the `Coordinator` and calls `process_input()`.

---

### **Next Steps**

This is **Component 1**. To keep this highly detailed and digestible, I will provide the specs for the remaining components one by one. 

**Which component would you like the detailed spec for next?**
1.  **Component 2: The Hook System & Event Dispatcher** (Crucial for the lifecycle events you researched).
2.  **Component 3: The Memory Store & Dreaming Engine** (The core "self-improving" feature).
3.  **Component 4: The Agent Base & Specialist Threads** (How multiagent scoping and isolation works).
4.  **Component 5: The Skill Loader & Tool Registry** (Progressive disclosure and free tools).

*(Reply with the number, and I will write the next detailed spec!)*