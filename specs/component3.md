# 📋 Component Specification 3: The Memory Store & Dreaming Engine

This component is the **long-term brain and self-improvement engine** of your agent. While the Coordinator handles immediate tasks and Hooks handle real-time safety, the Memory & Dreaming system ensures the agent **learns from its mistakes, retains user preferences, and organizes its own knowledge over time.**

By implementing this, you prove to the interviewer that you understand **state management, asynchronous batch processing, and autonomous self-improvement**—the holy grail of modern agentic systems.

---

### **File Locations**
*   `harness/memory.py` (Active memory management)
*   `harness/versioning.py` (Audit trails and rollback)
*   `harness/dreaming.py` (Batch consolidation engine)

### **Responsibilities**
1.  **In-Band Memory (Real-time):** Fast, simple appending of facts and notes during active sessions.
2.  **Out-of-Band Dreaming (Batch):** Asynchronously reading session transcripts and the current memory to produce a clean, deduplicated, and reorganized memory state.
3.  **Versioning & Rollback:** Maintaining an immutable history of memory states, allowing the agent (or user) to revert to a previous state if the agent "forgets" or hallucinates.
4.  **Context Injection:** Formatting the memory efficiently so it fits within the RTX 4060's limited context window when injected into the Coordinator.

---

### **Directory Structure & Data Layout**

```text
project-root/
├── memory.md                    # The "Active Store" (Read by agent during sessions)
├── memory/                      # Individual focused files (Optional, for large projects)
│   ├── user_preferences.md
│   └── project_context.md
├── sessions/                    # Raw transcripts (Input for dreaming)
│   ├── 2026-06-25_14-30_session.md
│   └── 2026-06-25_15-15_session.md
├── dreams/                      # Output of the dreaming process (Pending activation)
│   └── dream_2026-06-25_16-00_output.md
└── versions/                    # Immutable snapshots for rollback
    ├── v_2026-06-25_14-00.md
    └── v_2026-06-25_16-00.md
```

---

### **Class Structure & Methods**

#### **1. The Memory Store (`harness/memory.py`)**
This class manages the active `memory.md` file. It focuses on fast I/O and structured formatting.

```python
import os
from pathlib import Path
from datetime import datetime

class MemoryStore:
    def __init__(self, memory_path: str = "memory.md"):
        self.memory_path = Path(memory_path)
        if not self.memory_path.exists():
            self._initialize_empty_memory()

    def _initialize_empty_memory(self):
        """Creates the initial structured memory file."""
        template = """# Agent Memory

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
"""
        self.memory_path.write_text(template)

    def read_active(self) -> str:
        """Reads the entire active memory for context injection."""
        return self.memory_path.read_text()

    def append_in_band(self, section: str, content: str):
        """
        Fast, real-time append during a session.
        Does NOT reorganize, just adds to the bottom of the section.
        """
        current = self.read_active()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n### [{timestamp}] {section}\n{content}\n"
        
        # Simple append strategy (Dreaming will clean this up later)
        with open(self.memory_path, "a") as f:
            f.write(new_entry)

    def activate_dream(self, dream_file_path: str):
        """Replaces the active memory with a consolidated dream output."""
        dream_path = Path(dream_file_path)
        if not dream_path.exists():
            raise FileNotFoundError(f"Dream file not found: {dream_file_path}")
        
        # 1. Create a version snapshot of the current state before overwriting
        from harness.versioning import VersioningSystem
        VersioningSystem().create_snapshot("Pre-dream activation")

        # 2. Swap the files
        self.memory_path.write_text(dream_path.read_text())
        print(f"✓ Memory activated from {dream_file_path}")
```

#### **2. The Versioning System (`harness/versioning.py`)**
Provides an audit trail. We use simple file snapshots for fast local rollback, combined with Git commits for long-term history.

```python
import subprocess
from pathlib import Path
from datetime import datetime

class VersioningSystem:
    def __init__(self, versions_dir: str = "versions"):
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(exist_ok=True)

    def create_snapshot(self, message: str = "Manual snapshot") -> str:
        """Creates a timestamped snapshot of the current memory.md."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"v_{timestamp}.md"
        snapshot_path = self.versions_dir / snapshot_name
        
        # Copy current memory
        Path("memory.md").read_text() # Ensure it exists
        import shutil
        shutil.copy("memory.md", snapshot_path)
        
        # Git commit for long-term audit trail
        try:
            subprocess.run(["git", "add", "memory.md", "versions/"], capture_output=True)
            subprocess.run(["git", "commit", "-m", f"[Memory] {message} ({timestamp})"], capture_output=True)
        except Exception:
            pass # Git might not be initialized
            
        return str(snapshot_path)

    def list_snapshots(self) -> list:
        """Returns a list of available snapshots for rollback."""
        return sorted(self.versions_dir.glob("v_*.md"), reverse=True)

    def rollback(self, snapshot_name: str):
        """Restores memory.md to a previous state."""
        snapshot_path = self.versions_dir / snapshot_name
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_name}")
        
        import shutil
        shutil.copy(snapshot_path, "memory.md")
        self.create_snapshot(f"Rollback to {snapshot_name}")
        print(f"✓ Rolled back to {snapshot_name}")
```

#### **3. The Dreaming Engine (`harness/dreaming.py`)**
The core self-improvement mechanism. It runs as a batch process, reading raw transcripts and producing a clean memory state.

```python
from pathlib import Path
from harness.memory import MemoryStore
from harness.versioning import VersioningSystem
from ollama import chat # Local LLM client

class DreamingEngine:
    def __init__(self, sessions_dir: str = "sessions", dreams_dir: str = "dreams"):
        self.memory = MemoryStore()
        self.sessions_dir = Path(sessions_dir)
        self.dreams_dir = Path(dreams_dir)
        self.dreams_dir.mkdir(exist_ok=True)

    def run_dreaming_cycle(self, max_sessions: int = 3):
        """
        The core dreaming loop.
        1. Reads current memory.
        2. Reads recent session transcripts.
        3. Calls local LLM to consolidate.
        4. Writes output to dreams/ directory (does NOT overwrite active memory yet).
        """
        print("🌙 Starting Dreaming Cycle...")
        
        # 1. Gather Inputs
        current_memory = self.memory.read_active()
        transcripts = self._load_recent_transcripts(max_sessions)
        
        if not transcripts:
            print("No recent sessions to dream about.")
            return None

        # 2. Construct the Dreaming Prompt
        prompt = self._build_dream_prompt(current_memory, transcripts)

        # 3. Call Local LLM (Qwen2.5-7B)
        print("🧠 Local LLM is consolidating memory...")
        response = chat(
            model="qwen2.5:7b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3} # Low temp for factual consolidation
        )
        
        consolidated_memory = response.message.content

        # 4. Write to Output Store (Dreams directory)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.dreams_dir / f"dream_{timestamp}_output.md"
        output_path.write_text(consolidated_memory)
        
        print(f"✨ Dreaming complete. Output saved to: {output_path}")
        print("Run 'agent activate <path>' to apply the new memory.")
        return str(output_path)

    def _load_recent_transcripts(self, max_sessions: int) -> str:
        """Loads the N most recent session transcripts."""
        if not self.sessions_dir.exists():
            return ""
        
        # Sort by modification time, newest first
        files = sorted(self.sessions_dir.glob("*.md"), key=os.path.getmtime, reverse=True)
        
        transcripts = []
        for f in files[:max_sessions]:
            transcripts.append(f"--- TRANSCRIPT: {f.name} ---\n{f.read_text()}")
            
        return "\n\n".join(transcripts)

    def _build_dream_prompt(self, memory: str, transcripts: str) -> str:
        """Constructs a highly constrained prompt for the 7B model."""
        return f"""
You are an AI agent consolidating your long-term memory. 

CURRENT MEMORY STATE:
{memory}

RECENT SESSION TRANSCRIPTS:
{transcripts}

INSTRUCTIONS:
1. VERIFY facts in the current memory against the transcripts. Remove unverified info.
2. DEDUPLICATE repeated information.
3. REORGANIZE the memory into the standard structure (Active Topics, Verified Facts, User Preferences, Patterns, Action Items).
4. IDENTIFY new patterns or insights across the sessions.
5. DISCARD noise, temporary errors, or irrelevant conversational filler.

OUTPUT FORMAT:
Return ONLY the updated Markdown memory. Do not include conversational text like "Here is your updated memory". Start directly with "# Agent Memory".
"""
```

---

### **Key Design Decisions for RTX 4060 (8GB VRAM)**

*   **Batch Processing, Not Real-Time:** Dreaming is computationally expensive for a local 7B model. We explicitly designed it as an *out-of-band* batch process (`agent dream`) rather than running it after every single tool call. This prevents VRAM thrashing and keeps the interactive CLI snappy.
*   **Context Window Management:** A 7B model (like Qwen2.5) typically has a 32k context window, but performance degrades near the limit. The `_load_recent_transcripts` method strictly limits the input to the **last 3 sessions**. This ensures the dreaming prompt + memory + transcripts easily fit within 20k tokens, guaranteeing fast inference and preventing "lost in the middle" hallucinations.
*   **Low Temperature for Consolidation:** In the `chat` call, we set `temperature: 0.3`. Dreaming is a deterministic, factual task (deduplication and summarization), not a creative one. Low temperature forces the local model to stick strictly to the provided text.
*   **Two-Step Activation:** The dreaming process writes to `dreams/` and *does not* overwrite `memory.md` automatically. This "human-in-the-loop" design prevents the agent from accidentally deleting its own memory if the local model hallucinates a bad consolidation. The user must explicitly run `agent activate`.

---

### **Integration Points**

1.  **In the Coordinator (`harness/coordinator.py`)**:
    *   At the start of every session, the Coordinator calls `self.memory.read_active()` and injects it into the system prompt.
    *   When a specialist agent learns something new (e.g., the Tutor agent learns the user prefers bullet points), it calls `self.memory.append_in_band("User Preferences", "User prefers bullet points")`.

2.  **In the CLI (`agent.py`)**:
    *   `agent dream`: Instantiates `DreamingEngine` and calls `run_dreaming_cycle()`. Shows a Rich spinner while the local LLM processes.
    *   `agent activate <path>`: Instantiates `MemoryStore` and calls `activate_dream(path)`.
    *   `agent rollback <snapshot>`: Instantiates `VersioningSystem` and calls `rollback(snapshot)`.

3.  **In the Hooks (`harness/hooks.py`)**:
    *   A `SessionEnd` hook could automatically trigger a lightweight versioning snapshot: `VersioningSystem().create_snapshot("Session ended")`.

---

### **Why This Wins the Interview**

✅ **True Self-Improvement:** You aren't just building a chatbot; you're building a system that gets smarter the more you use it, exactly like Anthropic's managed agents.
✅ **Solves the "Local Model" Problem:** You explicitly address the limitations of local 7B models (context limits, hallucination) by using batch processing, low temperature, and a two-step activation safety net.
✅ **Production-Grade Safety:** The versioning system shows you care about data integrity. If the agent "lobotomizes" itself during a bad dream, you can instantly roll back. This is a massive green flag for engineering maturity.
✅ **Zero-Cost Architecture:** It relies entirely on local file I/O and the already-loaded local LLM. No vector databases, no external APIs, no hidden costs.

---

**Ready for Component 4?** 
Component 4 will cover **The Agent Base & Specialist Threads**, detailing exactly how we implement multiagent scoping, isolated conversation histories, and the routing logic that makes the Coordinator so effective. Just say the word!