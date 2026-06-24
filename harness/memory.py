"""
Memory Store for Agent Long-term Memory
Manages active memory with structured sections and atomic operations.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
from harness.file_ops import write_atomic, read_locked, FileLock, append_atomic


class MemoryStore:
    """
    Manages the agent's long-term memory stored in memory.md.
    Supports structured sections, atomic writes, and versioning integration.
    """
    
    DEFAULT_MEMORY_TEMPLATE = """# Agent Memory

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
    
    def __init__(self, memory_path: str = "memory.md"):
        """
        Initialize memory store.
        
        Args:
            memory_path: Path to memory file
        """
        self.memory_path = Path(memory_path)
        if not self.memory_path.exists():
            self._initialize_empty_memory()
    
    def _initialize_empty_memory(self):
        """Creates the initial structured memory file."""
        write_atomic(str(self.memory_path), self.DEFAULT_MEMORY_TEMPLATE)
    
    def read_active(self) -> str:
        """
        Reads the entire active memory for context injection.
        Uses shared lock for safe concurrent reads.
        
        Returns:
            Full memory content
        """
        with read_locked(str(self.memory_path)) as content:
            return content
    
    def get_section(self, section_name: str) -> str:
        """
        Get content of a specific section.
        
        Args:
            section_name: Name of section (e.g., "Active Topics")
            
        Returns:
            Section content
        """
        content = self.read_active()
        lines = content.split('\n')
        
        in_section = False
        section_content = []
        
        for line in lines:
            if line.strip().startswith('##') and section_name in line:
                in_section = True
                continue
            elif line.strip().startswith('##'):
                if in_section:
                    break
                in_section = False
            
            if in_section:
                section_content.append(line)
        
        return '\n'.join(section_content).strip()
    
    def append_in_band(self, section: str, content: str):
        """
        Fast, real-time append during a session.
        Adds content to the specified section.
        
        Args:
            section: Section name to append to
            content: Content to add
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n### [{timestamp}] {section}\n{content}\n"
        
        # Use atomic append with locking
        append_atomic(str(self.memory_path), new_entry)
    
    def update_section(self, section_name: str, new_content: str):
        """
        Replace content of a specific section.
        
        Args:
            section_name: Name of section to update
            new_content: New section content
        """
        content = self.read_active()
        lines = content.split('\n')
        
        result_lines = []
        in_section = False
        section_header_found = False
        skip_until_next_header = False
        
        for line in lines:
            # Check if this is any section header
            is_section_header = line.strip().startswith('##')
            
            if is_section_header:
                # If we were skipping lines for the target section, stop now
                if skip_until_next_header:
                    skip_until_next_header = False
                
                # Check if this is the target section header
                if section_name in line and not section_header_found:
                    section_header_found = True
                    in_section = True
                    skip_until_next_header = True
                    result_lines.append(line)
                    result_lines.append(new_content)
                    continue
            
            # Skip lines that belong to the old target section content
            if skip_until_next_header:
                continue
            
            # Add lines that are not part of the target section
            if not in_section or not skip_until_next_header:
                result_lines.append(line)
        
        # If section wasn't found, append it
        if not section_header_found:
            result_lines.append(f"\n## {section_name}\n{new_content}")
        
        write_atomic(str(self.memory_path), '\n'.join(result_lines))
    
    def activate_dream(self, dream_file_path: str):
        """
        Replaces the active memory with a consolidated dream output.
        Creates a version snapshot before overwriting.
        
        Args:
            dream_file_path: Path to dream output file
        """
        from harness.versioning import VersioningSystem
        
        dream_path = Path(dream_file_path)
        if not dream_path.exists():
            raise FileNotFoundError(f"Dream file not found: {dream_file_path}")
        
        # Create a version snapshot of the current state before overwriting
        versioning = VersioningSystem()
        versioning.create_snapshot("Pre-dream activation")
        
        # Swap the files atomically
        dream_content = dream_path.read_text()
        write_atomic(str(self.memory_path), dream_content)
    
    def clear_section(self, section_name: str):
        """
        Clear all content from a section.
        
        Args:
            section_name: Name of section to clear
        """
        self.update_section(section_name, "")
    
    def search_memory(self, query: str) -> list:
        """
        Search memory for matching entries.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching lines with context
        """
        content = self.read_active()
        lines = content.split('\n')
        matches = []
        
        query_lower = query.lower()
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                # Include context (previous line if it's a header)
                context = ""
                if i > 0 and lines[i-1].strip().startswith('##'):
                    context = lines[i-1].strip() + " > "
                matches.append(context + line.strip())
        
        return matches
    
    def get_summary_stats(self) -> dict:
        """
        Get summary statistics about memory.
        
        Returns:
            Dict with token count, section count, etc.
        """
        content = self.read_active()
        lines = content.split('\n')
        
        sections = [l for l in lines if l.strip().startswith('##')]
        entries = [l for l in lines if l.strip().startswith('###')]
        
        from harness.token_counter import TokenCounter
        counter = TokenCounter()
        
        return {
            "token_count": counter.count_tokens(content),
            "character_count": len(content),
            "section_count": len(sections),
            "entry_count": len(entries),
            "sections": [s.strip().replace('##', '').strip() for s in sections]
        }
