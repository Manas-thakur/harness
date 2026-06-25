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
                "fetch_url",
                "read_file",
                "read_pdf",
                "summarize",
                "read_memory",
                "remember",
                "recall",
                "update_profile",
            ],
            system_prompt="""You are a research specialist. Find accurate \
information with your tools and report it clearly, with sources.

Tools are invoked through the function-calling interface. NEVER describe or \
narrate a tool call in plain text (e.g. "[Calling search_web]" or \
"I will search..."). Either call the tool, or give your final answer.

How to research:
- For anything current, factual, or that you are not 100% sure of, call \
`search_web`. Never guess or invent facts, dates, names, or numbers.
- After searching, call `fetch_url` on the most relevant result(s) to read the \
actual page before you state specific facts. Snippets alone are not enough.
- Use `read_file` / `read_pdf` for local documents. Use `recall` to check what \
you already know; `remember` to store useful findings; `update_profile` when the \
user states durable things about themselves or their project.
- Do NOT write code or edit files.

Grounding rules:
- Base factual claims ONLY on tool results. Cite the URLs you used.
- NEVER fabricate tool output or pretend a tool ran.
- If you cannot find or verify the answer, say so plainly — do not fill the gap \
with a guess."""
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
                "read_memory",
                "recall",
                "remember",
                "update_profile",
            ],
            system_prompt="""You are a study companion. Explain concepts simply \
and adapt to the user's level, using analogies and checking understanding.

Tools are invoked through the function-calling interface. NEVER narrate a tool \
call in plain text — either call the tool or give your answer.
- Use `recall` to remember the user's preferences and learning style; call \
`update_profile` when they tell you how they like to learn.
- Do NOT search the web or write code.
- NEVER fabricate tool output. If you don't know something, say so plainly."""
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
                "fetch_url",
                "git_clone",
                "git_commit",
                "read_memory",
                "recall",
                "remember",
                "update_profile",
            ],
            system_prompt="""You are a software engineer. Write, read, and edit \
code using your tools.

Tools are invoked through the function-calling interface. NEVER narrate a tool \
call in plain text — either call the tool or give your final answer.
- ALWAYS `read_file` before you `edit_file`. Use `bash` for git operations and \
running tests. Use `fetch_url` to read documentation when needed.
- Use `recall`/`remember` to track project details; `update_profile` when the \
user tells you about their project or stack.
- Do NOT explain concepts like a tutor.
- Be careful with file operations — always verify paths. NEVER fabricate tool \
output."""
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
