"""
Tool Registry and Free Tool Implementations
Provides zero-cost tools for web search, file I/O, Git operations, and more.
"""

import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable
from harness.file_ops import write_atomic, read_file_safe


# Default character limit for tool outputs (VRAM protection)
MAX_TOOL_CHARS = 4000


def _fn(name: str, description: str, properties: dict, required: list) -> dict:
    """Build a JSON-schema function definition for native tool calling."""
    return {
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


# Native function-calling schemas, keyed by tool name. Only tools listed here
# are exposed to the model; placeholder names without schemas are skipped.
TOOL_SCHEMAS: Dict[str, dict] = {
    "search_web": _fn(
        "search_web",
        "Search the web for current or factual information. Use this for "
        "anything you are unsure of or that may have changed recently. Never "
        "guess at facts you could look up.",
        {
            "query": {"type": "string", "description": "The search query."},
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (default 5).",
            },
        },
        ["query"],
    ),
    "read_file": _fn(
        "read_file",
        "Read the contents of a file from disk.",
        {"path": {"type": "string", "description": "Path to the file."}},
        ["path"],
    ),
    "write_file": _fn(
        "write_file",
        "Write content to a file atomically (creates or overwrites).",
        {
            "path": {"type": "string", "description": "Path to write."},
            "content": {"type": "string", "description": "File content."},
        },
        ["path", "content"],
    ),
    "edit_file": _fn(
        "edit_file",
        "Replace an exact substring in a file. Read the file first.",
        {
            "path": {"type": "string", "description": "Path to the file."},
            "old_string": {"type": "string", "description": "Text to replace."},
            "new_string": {"type": "string", "description": "Replacement text."},
        },
        ["path", "old_string", "new_string"],
    ),
    "bash": _fn(
        "bash",
        "Run a shell command and return its output. Use for git and tests.",
        {
            "command": {"type": "string", "description": "Command to run."},
            "timeout": {"type": "integer", "description": "Timeout in seconds."},
        },
        ["command"],
    ),
    "git_clone": _fn(
        "git_clone",
        "Clone a git repository to a local path.",
        {
            "url": {"type": "string", "description": "Repository URL."},
            "path": {"type": "string", "description": "Destination path."},
        },
        ["url"],
    ),
    "git_commit": _fn(
        "git_commit",
        "Stage all changes and commit them with a message.",
        {
            "path": {"type": "string", "description": "Repo path (default .)."},
            "message": {"type": "string", "description": "Commit message."},
        },
        ["message"],
    ),
    "read_memory": _fn(
        "read_memory",
        "Read the full long-term memory store.",
        {},
        [],
    ),
    "write_memory": _fn(
        "write_memory",
        "Append a note to a named section of long-term memory.",
        {
            "section": {"type": "string", "description": "Section name."},
            "content": {"type": "string", "description": "Note to append."},
        },
        ["content"],
    ),
    "read_pdf": _fn(
        "read_pdf",
        "Extract text from a PDF file.",
        {"path": {"type": "string", "description": "Path to the PDF."}},
        ["path"],
    ),
    "remember": _fn(
        "remember",
        "Store a specific task fact for later recall. Use for details worth "
        "keeping that are not general profile info.",
        {
            "fact": {"type": "string", "description": "The fact to store."},
            "key": {"type": "string", "description": "Optional short key/id."},
        },
        ["fact"],
    ),
    "recall": _fn(
        "recall",
        "Search stored memory for previously remembered facts.",
        {"query": {"type": "string", "description": "What to search for."}},
        ["query"],
    ),
    "update_profile": _fn(
        "update_profile",
        "Record durable information about the user or their project into "
        "always-loaded profile memory. Call this when the user states who they "
        "are, what they're working on, or a lasting preference.",
        {
            "section": {
                "type": "string",
                "description": "One of: About, Current Work, User Preferences.",
            },
            "content": {"type": "string", "description": "The profile fact."},
        },
        ["content"],
    ),
}


def truncate_output(text: str) -> str:
    """
    Truncate text to fit within character limit.
    
    Args:
        text: Text to truncate
        
    Returns:
        Truncated text with message if needed
    """
    if len(text) > MAX_TOOL_CHARS:
        return text[:MAX_TOOL_CHARS] + "\n\n... [TRUNCATED] ... Use Grep to search specific parts."
    return text


class ToolRegistry:
    """
    Registry of all available tools with validation and execution.
    Enforces tool scoping per agent.
    """

    def __init__(self, memory=None):
        """
        Initialize tool registry with built-in tools.

        Args:
            memory: Optional shared MemoryStore so memory tools and the
                Coordinator operate on the same instance. When None, a store
                is lazily constructed on first use (keeps standalone CLI usage
                working).
        """
        self.tools: Dict[str, Callable] = {}
        self._memory = memory
        self._register_builtin_tools()

    def memory(self):
        """Return the shared MemoryStore, constructing a default if needed."""
        if self._memory is None:
            from harness.memory import MemoryStore
            self._memory = MemoryStore()
        return self._memory

    def _register_builtin_tools(self):
        """Register all built-in free tools."""
        self.tools["search_web"] = self._search_web
        self.tools["read_file"] = self._read_file
        self.tools["write_file"] = self._write_file
        self.tools["edit_file"] = self._edit_file
        self.tools["bash"] = self._bash
        self.tools["git_clone"] = self._git_clone
        self.tools["git_commit"] = self._git_commit
        self.tools["explain"] = self._explain
        self.tools["quiz_me"] = self._quiz_me
        self.tools["read_memory"] = self._read_memory
        self.tools["write_memory"] = self._write_memory
        self.tools["read_pdf"] = self._read_pdf
        self.tools["remember"] = self._remember
        self.tools["recall"] = self._recall
        self.tools["update_profile"] = self._update_profile

    def get_schemas(self, names) -> list:
        """
        Return native function-calling schemas for the named tools.

        Only tools that are both registered AND have a schema in TOOL_SCHEMAS
        are returned — this silently skips placeholder/dangling allowed-tool
        names (e.g. ``summarize``, ``create_analogy``, ``read_sessions``).

        Args:
            names: Iterable of tool names (an agent's allowed_tools).

        Returns:
            List of ``{"type": "function", "function": {...}}`` schema dicts.
        """
        schemas = []
        for name in names:
            if name in self.tools and name in TOOL_SCHEMAS:
                schemas.append({"type": "function", "function": TOOL_SCHEMAS[name]})
        return schemas

    def execute(
        self, 
        tool_name: str, 
        tool_input: Dict[str, Any], 
        agent=None
    ) -> str:
        """
        Execute a tool with validation.
        
        Args:
            tool_name: Name of tool to execute
            tool_input: Tool input arguments
            agent: Optional agent for permission checking
            
        Returns:
            Tool output or error message
        """
        # Security: Check if agent is allowed to use this tool
        if agent and not agent.can_use_tool(tool_name):
            return (
                f"Error: Agent '{agent.name}' does not have permission "
                f"to use tool '{tool_name}'"
            )

        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found"

        try:
            return self.tools[tool_name](tool_input)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"

    # === Free Tool Implementations ===

    def _search_web(self, input: Dict) -> str:
        """
        DuckDuckGo search (free, no API key).

        Input: {"query": str, "max_results": int}
        """
        # The package was renamed `duckduckgo_search` -> `ddgs`; try new first.
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return "Error: web search backend not installed. Run: pip install ddgs"

        query = (input.get("query") or "").strip()
        if not query:
            return "Error: no search query provided."
        max_results = input.get("max_results", 5)

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            return f"Search failed (network or backend error): {str(e)}"

        if not results:
            return f"No results found for: {query}"

        output = []
        for i, r in enumerate(results, 1):
            # Field names differ slightly across backend versions.
            title = r.get("title", "")
            body = r.get("body") or r.get("description", "")
            url = r.get("href") or r.get("url", "")
            output.append(f"{i}. {title}")
            output.append(f"   {body}")
            output.append(f"   URL: {url}\n")

        return truncate_output("\n".join(output))

    def _read_file(self, input: Dict) -> str:
        """
        Read a file from disk.
        
        Input: {"path": str}
        """
        path = Path(input.get("path", ""))

        if not path.exists():
            return f"Error: File not found: {path}"

        try:
            content = read_file_safe(str(path))
            return truncate_output(content)
        except Exception as e:
            return f"Error reading file: {str(e)}"

    def _write_file(self, input: Dict) -> str:
        """
        Write content to a file atomically.
        
        Input: {"path": str, "content": str}
        """
        path = Path(input.get("path", ""))
        content = input.get("content", "")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_atomic(str(path), content)
            return f"File written: {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    def _edit_file(self, input: Dict) -> str:
        """
        Edit a file using search/replace.
        
        Input: {"path": str, "old_string": str, "new_string": str}
        """
        path = Path(input.get("path", ""))
        old_string = input.get("old_string", "")
        new_string = input.get("new_string", "")

        if not path.exists():
            return f"Error: File not found: {path}"

        try:
            content = read_file_safe(str(path))

            if old_string not in content:
                return "Error: old_string not found in file"

            new_content = content.replace(old_string, new_string, 1)
            write_atomic(str(path), new_content)
            return f"File edited: {path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    def _bash(self, input: Dict) -> str:
        """
        Execute a bash command with environment persistence.
        
        Input: {"command": str, "timeout": int}
        """
        command = input.get("command", "")
        timeout = input.get("timeout", 120)

        # Source environment file if it exists
        env_file = Path(".agent_env.sh")
        if env_file.exists():
            command = f"source {env_file} && {command}"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                executable="/bin/bash"
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"

            return truncate_output(output or "Command executed successfully (no output)")
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds"
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _git_clone(self, input: Dict) -> str:
        """
        Clone a Git repository.
        
        Input: {"url": str, "path": str}
        """
        url = input.get("url", "")
        path = input.get("path", "workspace/repo")

        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                ["git", "clone", url, path],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return f"Error: {result.stderr}"

            return f"Repository cloned to {path}"
        except Exception as e:
            return f"Error cloning repository: {str(e)}"

    def _git_commit(self, input: Dict) -> str:
        """
        Commit changes to Git.
        
        Input: {"path": str, "message": str}
        """
        path = input.get("path", ".")
        message = input.get("message", "Update")

        try:
            subprocess.run(
                ["git", "add", "."], 
                cwd=path, 
                capture_output=True
            )
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=path,
                capture_output=True,
                text=True
            )

            return result.stdout or result.stderr or "Changes committed"
        except Exception as e:
            return f"Error committing: {str(e)}"

    def _explain(self, input: Dict) -> str:
        """
        Placeholder for explanation (handled by Tutor agent's LLM).
        
        Input: {"concept": str}
        """
        return "Explanation generated by Tutor agent via LLM"

    def _quiz_me(self, input: Dict) -> str:
        """
        Placeholder for quiz generation (handled by Tutor agent's LLM).
        
        Input: {"topic": str, "num_questions": int}
        """
        return "Quiz generated by Tutor agent via LLM"

    def _read_memory(self, input: Dict) -> str:
        """
        Read from memory.md.

        Input: {} (no args)
        """
        try:
            return truncate_output(self.memory().read_active())
        except Exception as e:
            return f"Error reading memory: {str(e)}"

    def _write_memory(self, input: Dict) -> str:
        """
        Write to memory.md.

        Input: {"section": str, "content": str}
        """
        try:
            section = input.get("section", "General")
            content = input.get("content", "")
            self.memory().append_in_band(section, content)
            return "Memory updated"
        except Exception as e:
            return f"Error writing to memory: {str(e)}"

    # Profile sections that make up the always-loaded "core" memory block.
    PROFILE_SECTIONS = ("About", "Current Work", "User Preferences")

    def _remember(self, input: Dict) -> str:
        """
        Store an explicit task fact for later recall (not always-loaded).

        Input: {"fact": str, "key": str (optional)}
        """
        try:
            fact = (input.get("fact") or input.get("content") or "").strip()
            if not fact:
                return "Error: nothing to remember (empty fact)."
            key = input.get("key") or f"fact_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.memory().save_fact(key, fact)
            return f"Remembered ({key})."
        except Exception as e:
            return f"Error remembering: {str(e)}"

    def _recall(self, input: Dict) -> str:
        """
        Search stored memory for facts matching a query.

        Input: {"query": str}
        """
        try:
            query = (input.get("query") or "").strip()
            if not query:
                return "Error: no recall query provided."
            matches = self.memory().search_memory(query)
            if not matches:
                return f"No stored memory matches: {query}"
            return truncate_output("\n".join(f"- {m}" for m in matches))
        except Exception as e:
            return f"Error recalling: {str(e)}"

    def _update_profile(self, input: Dict) -> str:
        """
        Record durable profile info into the always-loaded core memory.

        Restricted to the profile sections (About / Current Work /
        User Preferences) so model-driven writes can't clobber other memory.

        Input: {"section": str, "content": str}
        """
        try:
            section = (input.get("section") or "About").strip()
            content = (input.get("content") or "").strip()
            if not content:
                return "Error: nothing to update (empty content)."
            # Normalize to a known profile section, defaulting to About.
            match = next(
                (s for s in self.PROFILE_SECTIONS if s.lower() == section.lower()),
                "About",
            )
            self.memory().append_to_section(match, content)
            return f"Profile updated ({match})."
        except Exception as e:
            return f"Error updating profile: {str(e)}"

    def _read_pdf(self, input: Dict) -> str:
        """
        Read text from a PDF file.
        
        Input: {"path": str}
        """
        try:
            from pypdf import PdfReader

            path = Path(input.get("path", ""))
            if not path.exists():
                return f"Error: PDF not found: {path}"

            reader = PdfReader(str(path))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"

            return truncate_output(text)
        except ImportError:
            return "Error: pypdf not installed. Run: pip install pypdf"
        except Exception as e:
            return f"Error reading PDF: {str(e)}"

    def list_tools(self) -> list:
        """Return list of available tool names."""
        return list(self.tools.keys())
