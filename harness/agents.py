"""
Specialist Agent Implementations
Research, Tutor, Coder, and Dreamer agents with scoped tools.
"""

from harness.agent_base import BaseAgent


class ResearchAgent(BaseAgent):
    """
    Research specialist for web search and document analysis.
    Cannot write code or edit files.
    """

    def __init__(self):
        super().__init__(
            name="researcher",
            allowed_tools=[
                "search_web", 
                "read_file", 
                "read_pdf", 
                "summarize",
                "read_memory"
            ],
            system_prompt="""You are a research specialist.
- Your ONLY job is to find information using search_web and read documents.
- Do NOT write code or edit files.
- Cite your sources clearly.
- If you cannot find the answer, state that explicitly.
- Use the read_memory tool to check what you already know before searching."""
        )

    def run(self, task: str, coordinator) -> str:
        """Execute research task."""
        context = self.get_active_context()
        context.append({"role": "user", "content": task})
        return coordinator.execute_agent_loop(self, context)


class TutorAgent(BaseAgent):
    """
    Study companion for explanations and quizzes.
    Cannot search web or write code.
    """

    def __init__(self):
        super().__init__(
            name="tutor",
            allowed_tools=[
                "explain", 
                "quiz_me", 
                "create_analogy", 
                "read_memory"
            ],
            system_prompt="""You are a study companion.
- Your job is to explain concepts simply and adapt to the user's level.
- Use analogies frequently.
- Check for understanding by asking follow-up questions.
- Do NOT search the web or write code.
- Use read_memory to recall user preferences and learning style."""
        )

    def run(self, task: str, coordinator) -> str:
        """Execute tutoring task."""
        context = self.get_active_context()
        context.append({"role": "user", "content": task})
        return coordinator.execute_agent_loop(self, context)


class CoderAgent(BaseAgent):
    """
    Software engineer agent for code operations.
    Cannot explain concepts like a tutor or search web.
    """

    def __init__(self):
        super().__init__(
            name="coder",
            allowed_tools=[
                "bash", 
                "read_file", 
                "write_file", 
                "edit_file", 
                "git_clone", 
                "git_commit",
                "read_memory"
            ],
            system_prompt="""You are a software engineer.
- You write, read, and edit code.
- Always read a file before editing it.
- Use bash for git operations and running tests.
- Do NOT search the web or explain concepts like a tutor.
- Be careful with file operations - always verify paths."""
        )

    def run(self, task: str, coordinator) -> str:
        """Execute coding task."""
        context = self.get_active_context()
        context.append({"role": "user", "content": task})
        return coordinator.execute_agent_loop(self, context)


class DreamerAgent(BaseAgent):
    """
    Batch consolidation agent for memory improvement.
    Only runs during dreaming cycles, not during active sessions.
    """

    def __init__(self):
        super().__init__(
            name="dreamer",
            allowed_tools=[
                "read_sessions", 
                "read_memory", 
                "write_memory"
            ],
            system_prompt="""You are the dreaming agent.
- You ONLY run during batch consolidation.
- Your job is to read session transcripts and reorganize the memory store.
- You do NOT interact with the user directly.
- Focus on deduplication, verification, and organization."""
        )

    def run(self, task: str, coordinator) -> str:
        """Execute dreaming task (should be called by DreamingEngine)."""
        context = self.get_active_context()
        context.append({"role": "user", "content": task})
        return coordinator.execute_agent_loop(self, context)


# Registry of all available agents
AGENT_REGISTRY = {
    "researcher": ResearchAgent,
    "tutor": TutorAgent,
    "coder": CoderAgent,
    "dreamer": DreamerAgent
}


def get_agent(agent_type: str) -> BaseAgent:
    """
    Factory function to create an agent by type.
    
    Args:
        agent_type: Type of agent to create
        
    Returns:
        Instantiated agent
        
    Raises:
        ValueError: If agent type is unknown
    """
    if agent_type not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent type: {agent_type}")

    return AGENT_REGISTRY[agent_type]()
