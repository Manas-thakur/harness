Here is the **Ultimate Master Specification Document**. This version is exhaustively detailed, providing exact JSON schemas, precise algorithmic steps, and strict implementation rules. It is designed to be fed directly into an AI coding assistant to generate a bug-free, production-grade system.

***

# 🏗️ ULTIMATE MASTER SPECIFICATION: Local Self-Improving AI Agent

## 1. Project Overview & Hard Constraints
**Objective:** Build a production-grade, local AI research and study companion agent with self-improvement capabilities (memory consolidation/dreaming), multiagent orchestration, and a hook-based lifecycle system mirroring Anthropic's architecture.

**Hard Constraints (Strictly Enforced):**
*   **Hardware:** RTX 4060 (8GB VRAM), i7 14th Gen, 16GB RAM. Ubuntu Linux.
*   **Model:** `qwen2.5:7b` (Q4_K_M quantization) via local Ollama instance.
*   **Budget:** $0.00. NO external APIs.
*   **Frameworks:** Pure Python. `typer` (CLI), `rich` (UI), `ollama` (LLM), `duckduckgo-search` (Web), `pypdf` (PDFs). **ABSOLUTELY NO LangChain, LlamaIndex, or CrewAI.**
*   **Concurrency:** **Sequential execution only.** Do not use `asyncio.gather` for LLM calls. Use context-swapping for multiagent.

---

## 2. Core Engineering Directives (The "Zero Bug" Rules)

### 2.1 Defensive JSON Parsing (The Local Model Reality)
Local 7B models frequently output markdown around JSON or miss closing brackets.
**Implementation Rule:** Create a `repair_and_extract_json(text: str) -> dict` utility in `harness/llm_client.py`.
```python
import re
import json

def repair_and_extract_json(text: str) -> dict:
    # 1. Find the first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError("No JSON object found")
    
    json_str = text[start:end+1]
    
    # 2. Attempt to parse
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # 3. Basic repair: remove trailing commas before } or ]
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            raise ValueError("Failed to repair JSON")
```

### 2.2 Atomic File Operations
**Implementation Rule:** Never write directly to `memory.md` or transcripts.
```python
import os
import tempfile
import fcntl

def write_atomic(path: str, content: str):
    dir_name = os.path.dirname(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=dir_name, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

def read_locked(path: str) -> str:
    with open(path, 'r') as f:
        fcntl.flock(f, fcntl.LOCK_SH) # Shared lock for reading
        content = f.read()
        fcntl.flock(f, fcntl.LOCK_UN)
    return content
```

### 2.3 Strict Token Budgeting
**Implementation Rule:** Every tool returning text MUST have a hard character limit (default 4,000 chars).
```python
MAX_TOOL_CHARS = 4000

def truncate_output(text: str) -> str:
    if len(text) > MAX_TOOL_CHARS:
        return text[:MAX_TOOL_CHARS] + "\n\n... [TRUNCATED] ... Use Grep to search specific parts."
    return text
```

### 2.4 The "Two-Strike" Rule
**Implementation Rule:** The `Coordinator` must maintain a `RecentToolCalls` hash. If the agent calls the exact same tool with the exact same arguments twice in a row, force-block it and inject a system message: *"You are repeating yourself. Change your approach."*

---

## 3. Detailed Component Specifications

### Component 1: Core Infrastructure (`harness/llm_client.py`, `harness/file_ops.py`)

**Class: `LocalLLMClient`**
*   **Method:** `generate(messages: list, temperature: float = 0.7) -> str`
    *   Calls Ollama API (`http://localhost:11434/api/chat`).
    *   Timeout: 120 seconds.
    *   Streams response to prevent memory spikes.
*   **Method:** `generate_structured(messages: list) -> dict`
    *   Calls `generate`, then passes output through `repair_and_extract_json`.
*   **Method:** `count_tokens(text: str) -> int`
    *   Returns `len(text) // 4`.

### Component 2: Memory & Dreaming (`harness/memory.py`, `harness/dreaming.py`)

**Memory Schema (`memory.md`):**
```markdown
# Agent Memory

## Active Topics
[Currently researching or working on]

## Verified Facts
[Key information learned from sessions]

## User Preferences
[How the user likes things explained, formatting rules]

## Patterns & Insights
[Cross-session observations]

## Action Items
[Next steps or pending tasks]
```

**Class: `DreamingEngine`**
*   **Method:** `run_dreaming_cycle(max_sessions: int = 3)`
    1. Read `memory.md` using `read_locked`.
    2. Read last 3 transcripts from `sessions/` directory (sorted by mtime).
    3. Construct prompt:
       ```text
       You are an AI agent consolidating your long-term memory.
       CURRENT MEMORY STATE:
       {memory}
       RECENT SESSION TRANSCRIPTS:
       {transcripts}
       INSTRUCTIONS:
       1. VERIFY facts in the current memory against the transcripts. Remove unverified info.
       2. DEDUPLICATE repeated information.
       3. REORGANIZE the memory into the standard structure.
       4. IDENTIFY new patterns or insights across the sessions.
       5. DISCARD noise.
       OUTPUT FORMAT:
       Return ONLY the updated Markdown memory. Start directly with "# Agent Memory".
       ```
    4. Call LLM with `temperature=0.3`.
    5. Write output to `dreams/dream_{timestamp}_output.md` using `write_atomic`. **DO NOT overwrite `memory.md` automatically.**

### Component 3: Hook System (`harness/hooks.py`)

**Architecture:** Mirrors Anthropic's Hook paradigm. Hooks are Python scripts or shell commands executed via `subprocess`.

**Event Mapping:**
| Anthropic Event | Local Python Event | When it fires |
| :--- | :--- | :--- |
| `SessionStart` | `SessionStart` | When agent starts |
| `UserPromptSubmit` | `UserPromptSubmit` | Before processing user input |
| `PreToolUse` | `PreToolUse` | Before tool execution |
| `PostToolUse` | `PostToolUse` | After tool execution |
| `Stop` | `Stop` | When agent finishes turn |
| `SessionEnd` | `SessionEnd` | When CLI exits |

**Hook Execution Protocol:**
1.  **Input:** Pass event context as JSON to `stdin` of the hook command.
2.  **Output:** Parse `stdout` for JSON decisions.
3.  **Exit Codes:**
    *   `0`: Success. Parse `stdout`.
    *   `2`: Hard Block. Read `stderr` as reason. Block action.
    *   `1`: Non-blocking error. Log and continue.

**JSON Input Schema (Example for `PreToolUse`):**
```json
{
  "session_id": "uuid",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "rm -rf /tmp"
  }
}
```

**JSON Output Schema (To block the tool):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Destructive command blocked by security hook"
  }
}
```

**Environment Persistence (`.agent_env.sh`):**
*   Create `EnvironmentManager` class.
*   Before executing ANY Bash tool, prepend `source .agent_env.sh && ` to the command.
*   `SessionStart` hooks can write `export KEY=VALUE` to `.agent_env.sh` to persist state.

### Component 4: Agent Base & Specialist Threads (`harness/agents.py`, `harness/threads.py`)

**Class: `AgentThread`**
*   **Properties:** `history: list[dict]`, `state: str` (idle/running/archived), `turn_count: int`.
*   **Method:** `is_context_full() -> bool`
    *   Returns `True` if `sum(len(m['content']) for m in self.history) // 4 > 24000`.

**Class: `BaseAgent` (Abstract)**
*   **Properties:** `name: str`, `allowed_tools: list[str]`, `system_prompt: str`, `thread: AgentThread`.
*   **Method:** `can_use_tool(tool_name: str) -> bool`
    *   Returns `tool_name in self.allowed_tools`.

**Specialist Agents:**
*   `ResearchAgent`: `allowed_tools=["search_web", "read_file", "read_pdf"]`. Prompt: *"Do NOT write code or edit files."*
*   `TutorAgent`: `allowed_tools=["explain", "quiz_me", "read_memory"]`. Prompt: *"Do NOT search the web or write code."*
*   `CoderAgent`: `allowed_tools=["bash", "read_file", "write_file", "git_clone", "git_commit"]`. Prompt: *"Do NOT explain concepts like a tutor."*

### Component 5: Skills & Tools (`harness/tools.py`)

**Tool Implementation Schemas (Mirroring Anthropic):**

**1. Bash Tool**
*   **Input:** `{"command": "string", "timeout": int (default 120)}`
*   **Execution:**
    ```python
    full_command = f"source .agent_env.sh && {input['command']}"
    result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=input.get('timeout', 120))
    ```
*   **Output:** `{"stdout": str, "stderr": str, "exit_code": int}` (Truncated to 4000 chars).

**2. Read Tool**
*   **Input:** `{"file_path": "string"}`
*   **Execution:** `content = read_locked(input['file_path'])`
*   **Output:** `truncate_output(content)`

**3. Write Tool**
*   **Input:** `{"file_path": "string", "content": "string"}`
*   **Execution:** `write_atomic(input['file_path'], input['content'])`
*   **Output:** `{"success": True, "file_path": str}`

**4. Edit Tool**
*   **Input:** `{"file_path": "string", "old_string": "string", "new_string": "string"}`
*   **Execution:**
    ```python
    content = read_locked(input['file_path'])
    if input['old_string'] not in content:
        return {"success": False, "error": "old_string not found"}
    new_content = content.replace(input['old_string'], input['new_string'], 1)
    write_atomic(input['file_path'], new_content)
    ```
*   **Output:** `{"success": True}`

**Skill Loader (Progressive Disclosure):**
*   **Level 1:** Parse YAML frontmatter from `SKILL.md` at startup. Inject into system prompt.
*   **Level 2:** Load full `SKILL.md` body only when skill is triggered.
*   **Level 3:** Execute scripts in `scripts/` via `subprocess`. **Never load script code into LLM context.**

### Component 6: Orchestration & CLI (`harness/coordinator.py`, `agent.py`)

**Class: `Coordinator`**
*   **Method:** `process_input(user_prompt: str) -> str`
    1. Fire `UserPromptSubmit` hook. If blocked, return reason.
    2. Check `max_turns` (default 20). If exceeded, return error.
    3. Classify intent using LLM (JSON output: `{"agent": "researcher", "reasoning": "..."}`).
    4. Select target agent. Check if `agent.thread.is_context_full()`. If yes, run `ContextCompactor`.
    5. Execute agent loop. Enforce "Two-Strike" rule.
    6. Fire `Stop` hook.
    7. Return response.

**Context Compaction Algorithm:**
1.  Identify messages older than the last 3 turns.
2.  Summarize them using LLM: *"Summarize this conversation, preserving key facts, decisions, and next steps. Output as a single paragraph."*
3.  Replace old messages with `{"role": "system", "content": f"[COMPACTED CONTEXT]: {summary}"}`.

**CLI Commands (`agent.py` using Typer):**
*   `agent ask <task>`: Main interaction loop.
*   `agent dream [--sessions N]`: Trigger batch consolidation.
*   `agent activate <dream_path>`: Apply dream output to memory.
*   `agent memory`: View current memory.
*   `agent clone <url>`: Clone repo to workspace.
*   `agent threads`: List agent context states.

---

## 4. Implementation Order for AI Coder

*Execute the code generation in this exact order to ensure dependencies are met:*

1.  **Phase 1: Foundation.** Write `requirements.txt`, `harness/llm_client.py` (with JSON repair), `harness/token_counter.py`, and `harness/file_ops.py` (atomic writes).
2.  **Phase 2: Memory & Hooks.** Write `harness/memory.py`, `harness/versioning.py`, `harness/dreaming.py`, and `harness/hooks.py`.
3.  **Phase 3: Agents & Tools.** Write `harness/threads.py`, `harness/agents.py`, and `harness/tools.py`.
4.  **Phase 4: Orchestration & Skills.** Write `harness/skills_loader.py` and `harness/coordinator.py`.
5.  **Phase 5: Interface.** Write `agent.py` (CLI) and create the default `skills/` directory structure with example scripts.
6.  **Phase 6: Polish.** Add the "Two-Strike" loop prevention and context compaction logic to the Coordinator.

***