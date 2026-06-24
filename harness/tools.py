"""
Tool Registry and Free Tool Implementations
Provides zero-cost tools for web search, file I/O, Git operations, and more.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Callable, Optional
from harness.file_ops import read_locked, write_atomic


# Default character limit for tool outputs (VRAM protection)
MAX_TOOL_CHARS = 4000


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
    
    def __init__(self):
        """Initialize tool registry with built-in tools."""
        self.tools: Dict[str, Callable] = {}
        self._register_builtin_tools()
    
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
        try:
            from duckduckgo_search import DDGS
            
            query = input.get("query", "")
            max_results = input.get("max_results", 5)
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            
            output = []
            for i, r in enumerate(results, 1):
                output.append(f"{i}. {r['title']}")
                output.append(f"   {r['body']}")
                output.append(f"   URL: {r['href']}\n")
            
            return truncate_output("\n".join(output))
        except ImportError:
            return "Error: duckduckgo-search not installed. Run: pip install duckduckgo-search"
        except Exception as e:
            return f"Search failed: {str(e)}"
    
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
            from harness.memory import MemoryStore
            return truncate_output(MemoryStore().read_active())
        except Exception as e:
            return f"Error reading memory: {str(e)}"
    
    def _write_memory(self, input: Dict) -> str:
        """
        Write to memory.md.
        
        Input: {"section": str, "content": str}
        """
        try:
            from harness.memory import MemoryStore
            section = input.get("section", "General")
            content = input.get("content", "")
            MemoryStore().append_in_band(section, content)
            return "Memory updated"
        except Exception as e:
            return f"Error writing to memory: {str(e)}"
    
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
