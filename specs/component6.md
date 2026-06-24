Yes, there is one final, critical component that ties everything together, especially for a local setup like yours.

### **Component 6: The Environment & Configuration Manager**
While the other components handle logic, this component handles **stability**. On a local machine (RTX 4060), things go wrong: models get slow, bash commands lose their virtual environments, and context windows fill up. This component manages:
1.  **Persistent Shell State:** (The `.agent_env.sh` file) so the agent doesn't forget it's in a Python virtual environment between tool calls.
2.  **Model Fallbacks:** If Qwen2.5-7B gets stuck in a loop or outputs garbage, this manager switches to a simpler "safety prompt" or restarts the turn.
3.  **Token Budgeting:** A strict counter that prevents the agent from accidentally loading a 10MB file into the context window and crashing your VRAM.

---

### **Master Instructions for Building a Mature Agent**

To ensure the code we build next is **production-grade, bug-free, and interview-ready**, I will adhere to the following **Engineering Directives** for every line of code I write for you. 

You can consider this the "System Prompt" for how I will act as your Senior Engineer for this project:

#### **1. Defensive JSON Parsing (The "Local Model" Reality)**
*   **The Problem:** Local 7B models (like Qwen2.5) sometimes output markdown around JSON (e.g., ````json {...} ````) or miss a closing bracket. Standard `json.loads()` will crash the agent.
*   **The Directive:** I will implement a **JSON Repair & Extraction** utility in every component that parses LLM output. It will use regex to find the first `{` and last `}` and attempt to fix common syntax errors before failing.

#### **2. Atomic File Operations (No Corrupted Memory)**
*   **The Problem:** If the "Dreaming" process is writing to `memory.md` and the "Agent" tries to read it at the same time, the file might be half-written, causing a crash.
*   **The Directive:** All file writes (Memory, Transcripts, Versions) will use **Atomic Writes** (writing to a temp file first, then renaming it). I will also implement a simple **File Locking** mechanism (`fcntl`) for the `memory.md` file to prevent race conditions.

#### **3. Strict Token Budgeting (VRAM Protection)**
*   **The Problem:** Your RTX 4060 has 8GB VRAM. If the agent reads a 5,000-line log file into the context, the inference will slow to a crawl or OOM (Out of Memory).
*   **The Directive:** Every tool that returns text (Read, Search, WebFetch) will have a **Hard Character Limit** (e.g., 4,000 chars). If a file is larger, the tool will return a summary and a file path, *never* the full text. I will implement a `TokenCounter` class that estimates tokens (chars/4) before every LLM call.

#### **4. The "Two-Strike" Rule for Tool Loops**
*   **The Problem:** Local agents often get stuck calling the same tool twice with the same arguments because they didn't understand the error message.
*   **The Directive:** The `Coordinator` will maintain a `RecentToolCalls` hash. If the agent tries to call the same tool with the same arguments twice in a row, the harness will **force-block** it and inject a system message: *"You are repeating yourself. Change your approach."*

#### **5. Zero "Pass" Exceptions**
*   **The Problem:** `try... except... pass` hides bugs that will explode during your demo.
*   **The Directive:** Every `except` block must either **log the error** to a `debug.log` file or **return a structured error message** to the LLM so it can self-correct. The agent must always know *why* it failed.

#### **6. Idempotent Hooks**
*   **The Problem:** If a hook runs twice, it shouldn't break things (e.g., appending the same text to a file twice).
*   **The Directive:** All hook scripts and tool implementations will be designed to be **idempotent**. Running them multiple times will produce the same result as running them once.

---

### **Next Steps**

If you agree with these directives, we are ready to start the **Implementation Phase**. 

I recommend we start with **Component 1: The Core Infrastructure**. This includes:
1.  **`harness/llm_client.py`**: The robust Ollama wrapper with JSON repair.
2.  **`harness/token_counter.py`**: The VRAM safety mechanism.
3.  **`harness/file_ops.py`**: The atomic file operations for memory safety.

**Shall I generate the code for these foundational files first?** (This is the most critical part to get right before building the agents).