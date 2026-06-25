"""
Coordinator for Agent Orchestration
Routes tasks to specialist agents, manages context, and enforces safety limits.
"""

import json
import time
from typing import Dict, List, Any, Optional
from harness.llm_client import LocalLLMClient
from harness.hooks import HookDispatcher
from harness.token_counter import TokenCounter
from harness.memory import MemoryStore
from harness.tools import ToolRegistry
from harness.agents import ResearchAgent, TutorAgent, CoderAgent, DreamerAgent


class Coordinator:
    """
    Main orchestrator for the AI agent system.
    Handles intent classification, agent routing, and safety enforcement.
    """
    
    def __init__(
        self, 
        model: str = "qwen2.5:7b", 
        max_turns: int = 20
    ):
        """
        Initialize coordinator.
        
        Args:
            model: LLM model name
            max_turns: Maximum turns per session
        """
        self.llm = LocalLLMClient(model=model)
        self.max_turns = max_turns
        self.current_turn = 0
        
        # Initialize subsystems
        self.hooks = HookDispatcher()
        self.token_counter = TokenCounter()
        self.memory = MemoryStore()
        self.tools = ToolRegistry()
        
        # Initialize Specialist Agents (Scoped)
        self.agents = {
            "researcher": ResearchAgent(),
            "tutor": TutorAgent(),
            "coder": CoderAgent(),
            "dreamer": DreamerAgent()
        }
        
        # Two-Strike Rule tracking
        self.recent_tool_calls: List[str] = []
        
        # Session transcript storage
        self.session_transcript: List[Dict] = []
    
    def process_input(self, user_prompt: str) -> str:
        """
        Main entry point for user interaction.
        
        Args:
            user_prompt: User's input text
            
        Returns:
            Agent response
        """
        # 1. Fire Hook: UserPromptSubmit
        hook_decision = self.hooks.fire(
            "UserPromptSubmit", 
            data={"prompt": user_prompt}
        )
        if hook_decision.get("blocked"):
            return f"⚠️ Request blocked: {hook_decision.get('reason')}"
        
        # 2. Safety Check
        if self.current_turn >= self.max_turns:
            return "⚠️ Maximum turn limit reached. Please start a new session."
        
        # 3. Intent Routing
        intent = self._classify_intent(user_prompt)
        target_agent_type = intent.get("agent", "general")
        
        # Map to actual agent
        agent_map = {
            "researcher": "researcher",
            "tutor": "tutor", 
            "coder": "coder",
            "dreamer": "dreamer",
            "general": "researcher"  # Default to researcher for general queries
        }
        target_agent_key = agent_map.get(target_agent_type, "researcher")
        target_agent = self.agents[target_agent_key]
        
        # 4. Execute Agent Loop
        response = self._execute_agent_loop(target_agent, user_prompt)
        
        # 5. Context Compaction Check
        if target_agent.thread.is_context_full():
            target_agent.thread.compact_old_messages(keep_last_n=3)
        
        # 6. Fire Hook: Stop
        self.hooks.fire("Stop", data={"response": response})
        
        self.current_turn += 1
        self._save_transcript_entry("user", user_prompt)
        self._save_transcript_entry("assistant", response)
        
        return response
    
    def _classify_intent(self, prompt: str) -> dict:
        """
        Use local LLM to classify intent and route to correct agent.
        
        Args:
            prompt: User's input
            
        Returns:
            Dict with agent type and reasoning
        """
        classification_prompt = f"""
Classify the user's request into one of these categories:
- researcher: Web search, finding papers, reading documents, summarizing information.
- tutor: Explaining concepts, creating quizzes, studying, learning adaptation.
- coder: GitHub operations, writing code, analyzing repositories, editing files.
- dreamer: Consolidating memory, running batch processing.
- general: Simple chat or questions that don't fit other categories.

User Request: "{prompt}"

Return ONLY JSON: {{"agent": "category_name", "reasoning": "brief reason"}}
"""
        try:
            from harness.llm_client import repair_and_extract_json
            messages = [{"role": "user", "content": classification_prompt}]
            response = self.llm.generate(messages, temperature=0.3)
            return repair_and_extract_json(response)
        except Exception as e:
            # Fallback to researcher for errors
            return {"agent": "researcher", "reasoning": f"Classification error: {e}"}
    
    def _execute_agent_loop(self, agent, user_prompt: str) -> str:
        """
        Execute the agent's tool loop for a task.
        
        Args:
            agent: Target agent instance
            user_prompt: User's task
            
        Returns:
            Final response
        """
        context = agent.get_active_context()
        context.append({"role": "user", "content": user_prompt})
        
        max_agent_turns = 10  # Limit per-agent turns
        agent_turn = 0
        
        while agent_turn < max_agent_turns:
            # Get LLM response
            try:
                response = self.llm.generate(context, temperature=0.7)
            except Exception as e:
                return f"Error: LLM generation failed - {str(e)}"
            
            # Check if response contains tool call
            tool_call = self._parse_tool_call(response)
            
            if tool_call:
                # Two-Strike Rule check
                call_hash = f"{tool_call['name']}:{json.dumps(tool_call['input'], sort_keys=True)}"
                if call_hash in self.recent_tool_calls[-2:]:
                    context.append({
                        "role": "system",
                        "content": "You are repeating yourself. Change your approach."
                    })
                    agent_turn += 1
                    continue
                
                self.recent_tool_calls.append(call_hash)
                if len(self.recent_tool_calls) > 10:
                    self.recent_tool_calls.pop(0)
                
                # Fire PreToolUse hook
                hook_result = self.hooks.fire(
                    "PreToolUse",
                    {
                        "tool_name": tool_call['name'],
                        "tool_input": tool_call['input']
                    }
                )
                
                if hook_result.get("blocked"):
                    context.append({
                        "role": "tool",
                        "content": f"Tool blocked: {hook_result.get('reason')}"
                    })
                    agent_turn += 1
                    continue
                
                # Execute tool
                tool_result = self.tools.execute(
                    tool_call['name'],
                    tool_call['input'],
                    agent
                )
                
                # Add to context
                context.append({
                    "role": "assistant",
                    "content": f"[Calling {tool_call['name']}]"
                })
                context.append({
                    "role": "tool",
                    "content": tool_result
                })
                
                # Fire PostToolUse hook
                self.hooks.fire(
                    "PostToolUse",
                    {
                        "tool_name": tool_call['name'],
                        "tool_result": tool_result
                    }
                )
                
                agent_turn += 1
            else:
                # No tool call, return final response
                return response.strip()
        
        # Reached max turns without final response
        return "I've reached the maximum number of tool calls. Here's what I found so far."
    
    def _parse_tool_call(self, response: str) -> Optional[Dict]:
        """
        Parse tool call from LLM response.
        
        Args:
            response: LLM response text
            
        Returns:
            Tool call dict or None
        """
        try:
            from harness.llm_client import repair_and_extract_json
            
            # Try to extract JSON from response
            data = repair_and_extract_json(response)
            
            if isinstance(data, dict) and 'tool' in data:
                return {
                    'name': data.get('tool', data.get('tool_name')),
                    'input': data.get('input', data.get('arguments', {}))
                }
        except Exception:
            pass
        
        return None
    
    def _save_transcript_entry(self, role: str, content: str):
        """Save entry to session transcript."""
        self.session_transcript.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
    
    def save_session_transcript(self, path: str = "sessions"):
        """Save session transcript to file."""
        from pathlib import Path
        from harness.file_ops import write_atomic
        
        sessions_dir = Path(path)
        sessions_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = time.strftime("%Y-%m-%d_%H-%M")
        filename = f"{timestamp}_session.md"
        filepath = sessions_dir / filename
        
        content = "# Session Transcript\n\n"
        for entry in self.session_transcript:
            role = entry['role'].upper()
            content += f"## {role}\n{entry['content']}\n\n"
        
        write_atomic(str(filepath), content)
    
    def get_status(self) -> dict:
        """Get coordinator status."""
        return {
            "current_turn": self.current_turn,
            "max_turns": self.max_turns,
            "agents": {
                name: agent.get_status() 
                for name, agent in self.agents.items()
            },
            "memory_stats": self.memory.get_summary_stats()
        }
