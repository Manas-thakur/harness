"""
Agent Threads for Context Isolation
Manages isolated conversation histories for each specialist agent.
"""

import time
from typing import List, Dict
from enum import Enum


class ThreadState(Enum):
    """Possible states for an agent thread."""
    IDLE = "idle"
    RUNNING = "running"
    ARCHIVED = "archived"


class AgentThread:
    """
    Manages the isolated context window for a single agent.
    Contains conversation history, state tracking, and token counting.
    """

    def __init__(self, agent_name: str, max_tokens: int = 28000):
        """
        Initialize agent thread.
        
        Args:
            agent_name: Name of the agent owning this thread
            max_tokens: Maximum tokens before compaction is needed
        """
        self.agent_name = agent_name
        self.history: List[Dict[str, str]] = []
        self.state = ThreadState.IDLE
        self.created_at = time.time()
        self.last_active = time.time()
        self.max_tokens = max_tokens

        # Metadata for the Coordinator
        self.turn_count = 0
        self.total_tool_calls = 0

    def add_message(self, role: str, content: str):
        """
        Append a message to the thread's history.
        
        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
        """
        self.history.append({"role": role, "content": content})
        self.last_active = time.time()
        self.turn_count += 1

    def add_tool_call(self, tool_name: str, tool_input: dict, result: str):
        """
        Add a tool call and its result to the history.
        
        Args:
            tool_name: Name of tool called
            tool_input: Tool input arguments
            result: Tool execution result
        """
        self.add_message("assistant", f"[Calling {tool_name}]")
        self.add_message("tool", f"[{tool_name} Result]: {result}")
        self.total_tool_calls += 1

    def get_context(self) -> List[Dict[str, str]]:
        """
        Returns the full conversation history for the LLM.
        
        Returns:
            Copy of message history
        """
        return self.history.copy()

    def is_context_full(self) -> bool:
        """
        Check if the thread is approaching the local model's context limit.
        
        Returns:
            True if context needs compaction
        """
        # Simple estimation: 1 token ≈ 4 characters
        total_chars = sum(len(m.get('content', '')) for m in self.history)
        return (total_chars // 4) > self.max_tokens

    def get_token_count(self) -> int:
        """
        Get current token count estimate.
        
        Returns:
            Estimated token count
        """
        total_chars = sum(len(m.get('content', '')) for m in self.history)
        return total_chars // 4

    def archive(self):
        """Move the thread to archived state to free up 'active' slots."""
        self.state = ThreadState.ARCHIVED

    def unarchive(self):
        """Restore the thread from archived state."""
        self.state = ThreadState.IDLE

    def clear_history(self, keep_system: bool = True):
        """
        Clear conversation history.
        
        Args:
            keep_system: If True, keep system messages
        """
        if keep_system:
            self.history = [
                m for m in self.history 
                if m.get('role') == 'system'
            ]
        else:
            self.history = []

    def get_summary(self) -> dict:
        """
        Get summary information about this thread.
        
        Returns:
            Dictionary with thread statistics
        """
        return {
            "agent_name": self.agent_name,
            "state": self.state.value,
            "turn_count": self.turn_count,
            "tool_calls": self.total_tool_calls,
            "token_count": self.get_token_count(),
            "created_at": time.strftime(
                "%Y-%m-%d %H:%M:%S", 
                time.localtime(self.created_at)
            ),
            "last_active": time.strftime(
                "%Y-%m-%d %H:%M:%S", 
                time.localtime(self.last_active)
            )
        }

    def compact_old_messages(self, keep_last_n: int = 3):
        """
        Compact old messages, keeping only recent turns.
        
        Args:
            keep_last_n: Number of recent turns to keep intact
        """
        if len(self.history) <= keep_last_n:
            return

        # Keep system messages and last N turns
        system_messages = [
            m for m in self.history 
            if m.get('role') == 'system'
        ]
        recent_messages = self.history[-keep_last_n:]

        # Create compacted summary of old messages
        old_messages = self.history[:-keep_last_n]
        "\n".join([
            f"{m['role']}: {m['content']}" 
            for m in old_messages 
            if m.get('role') != 'system'
        ])

        # Replace with summary
        self.history = system_messages + [
            {
                "role": "system", 
                "content": "[COMPACTED CONTEXT]: Previous conversation summarized. Key points were discussed."
            }
        ] + recent_messages
