"""
Dreaming Engine for Batch Memory Consolidation
Asynchronously processes session transcripts to consolidate and improve agent memory.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, List
from harness.memory import MemoryStore
from harness.llm_client import LocalLLMClient


class DreamingEngine:
    """
    The dreaming engine performs batch consolidation of session transcripts
    into organized, deduplicated long-term memory.
    
    This is an out-of-band process that runs separately from active sessions
    to prevent VRAM thrashing on local hardware.
    """

    DREAM_PROMPT_TEMPLATE = """You are an AI agent consolidating your long-term memory.

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
Return ONLY the updated Markdown memory. Do not include conversational text like "Here is your updated memory". Start directly with "# Agent Memory"."""

    def __init__(
        self, 
        sessions_dir: str = "sessions", 
        dreams_dir: str = "dreams",
        model: str = "qwen2.5:7b"
    ):
        """
        Initialize dreaming engine.
        
        Args:
            sessions_dir: Directory containing session transcripts
            dreams_dir: Directory to store dream outputs
            model: LLM model to use for consolidation
        """
        self.sessions_dir = Path(sessions_dir)
        self.dreams_dir = Path(dreams_dir)
        self.dreams_dir.mkdir(parents=True, exist_ok=True)

        self.memory = MemoryStore()
        self.llm = LocalLLMClient(model=model)

    def run_dreaming_cycle(self, max_sessions: int = 3) -> Optional[str]:
        """
        Run a complete dreaming cycle to consolidate memory.
        
        Args:
            max_sessions: Maximum number of recent sessions to process
            
        Returns:
            Path to dream output file, or None if no sessions found
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
        try:
            response = self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3  # Low temp for factual consolidation
            )
        except Exception as e:
            print(f"❌ Dreaming failed: {str(e)}")
            return None

        consolidated_memory = response.strip()

        # Ensure it starts with the expected header
        if not consolidated_memory.startswith("#"):
            consolidated_memory = "# Agent Memory\n\n" + consolidated_memory

        # 4. Write to Output Store (Dreams directory)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.dreams_dir / f"dream_{timestamp}_output.md"

        from harness.file_ops import write_atomic
        write_atomic(str(output_path), consolidated_memory)

        print(f"✨ Dreaming complete. Output saved to: {output_path}")
        print("Run 'agent activate <path>' to apply the new memory.")

        return str(output_path)

    def _load_recent_transcripts(self, max_sessions: int) -> str:
        """
        Load the N most recent session transcripts.
        
        Args:
            max_sessions: Maximum number of sessions to load
            
        Returns:
            Concatenated transcript content
        """
        if not self.sessions_dir.exists():
            return ""

        # Sort by modification time, newest first
        files = sorted(
            self.sessions_dir.glob("*.md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        transcripts = []
        for f in files[:max_sessions]:
            try:
                content = f.read_text()
                transcripts.append(f"--- TRANSCRIPT: {f.name} ---\n{content}")
            except Exception as e:
                print(f"Warning: Could not read {f.name}: {e}")

        return "\n\n".join(transcripts)

    def _build_dream_prompt(self, memory: str, transcripts: str) -> str:
        """
        Construct the dreaming prompt for the LLM.
        
        Args:
            memory: Current memory content
            transcripts: Recent session transcripts
            
        Returns:
            Formatted prompt string
        """
        return self.DREAM_PROMPT_TEMPLATE.format(
            memory=memory,
            transcripts=transcripts
        )

    def list_dreams(self) -> List[Path]:
        """
        List all available dream outputs.
        
        Returns:
            List of dream file paths sorted by date
        """
        if not self.dreams_dir.exists():
            return []

        return sorted(
            self.dreams_dir.glob("dream_*_output.md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

    def get_dream_preview(self, dream_path: str, lines: int = 20) -> str:
        """
        Get a preview of a dream output.
        
        Args:
            dream_path: Path to dream file
            lines: Number of lines to show
            
        Returns:
            Preview text
        """
        path = Path(dream_path)
        if not path.exists():
            return f"Dream file not found: {dream_path}"

        content = path.read_text()
        preview_lines = content.split('\n')[:lines]
        return '\n'.join(preview_lines) + "\n\n..." if len(content.split('\n')) > lines else content

    def activate_dream(self, dream_path: str) -> bool:
        """
        Activate a dream output, replacing current memory.
        
        Args:
            dream_path: Path to dream file
            
        Returns:
            True if successful
        """
        try:
            self.memory.activate_dream(dream_path)
            print(f"✓ Memory activated from {dream_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to activate dream: {e}")
            return False

    def cleanup_old_dreams(self, keep_count: int = 10) -> int:
        """
        Remove old dream files to save space.
        
        Args:
            keep_count: Number of recent dreams to keep
            
        Returns:
            Number of dreams removed
        """
        dreams = self.list_dreams()
        removed = 0

        for dream in dreams[keep_count:]:
            try:
                dream.unlink()
                removed += 1
            except Exception:
                pass

        return removed
