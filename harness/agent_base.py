"""
Base Agent Abstract Class
Defines the contract for all specialist agents.
"""

from abc import ABC, abstractmethod
from harness.threads import AgentThread, ThreadState


class BaseAgent(ABC):
    """
    Abstract base class for all specialist agents.
    Defines the contract for tool scoping, system prompts, and execution.
    """
    
    def __init__(
        self, 
        name: str, 
        allowed_tools: list, 
        system_prompt: str
    ):
        """
        Initialize base agent.
        
        Args:
            name: Agent name/identifier
            allowed_tools: List of tool names this agent can use
            system_prompt: System prompt that defines agent behavior
        """
        self.name = name
        self.allowed_tools = allowed_tools
        self.system_prompt = system_prompt
        self.thread = AgentThread(agent_name=name)
    
    @abstractmethod
    def run(self, task: str, coordinator) -> str:
        """
        Execute a task. Must be implemented by specialists.
        
        Args:
            task: Task description from user
            coordinator: Reference to coordinator for tool access
            
        Returns:
            Response string
        """
        pass
    
    def can_use_tool(self, tool_name: str) -> bool:
        """
        Check if agent has permission to use a specific tool.
        
        Args:
            tool_name: Name of tool to check
            
        Returns:
            True if tool is in allowed list
        """
        return tool_name in self.allowed_tools
    
    def get_active_context(self) -> list:
        """
        Prepends the system prompt to the thread history for the LLM.
        
        Returns:
            Full context with system prompt
        """
        if self.thread.state == ThreadState.IDLE:
            self.thread.state = ThreadState.RUNNING
        
        context = self.thread.get_context()
        
        # Inject system prompt as the first message if not present
        if not context or context[0].get('role') != 'system':
            context.insert(0, {"role": "system", "content": self.system_prompt})
        
        return context
    
    def reset_thread(self):
        """Reset the agent's conversation thread."""
        self.thread = AgentThread(agent_name=self.name)
    
    def get_status(self) -> dict:
        """
        Get current agent status.
        
        Returns:
            Status dictionary
        """
        return {
            "name": self.name,
            "allowed_tools": self.allowed_tools,
            "thread_state": self.thread.state.value,
            "turn_count": self.thread.turn_count,
            "token_count": self.thread.get_token_count()
        }
