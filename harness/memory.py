"""
Memory Store for Agent Long-term Memory
Supports Hybrid Mode: Legacy memory.md OR Neural Markdown Mesh
Manages active memory with structured sections and atomic operations.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from harness.file_ops import write_atomic, read_locked, append_atomic


class MemoryStore:
    """
    Manages the agent's long-term memory.
    Supports dual mode: Legacy (memory.md) or Mesh (markdown files with wikilinks).
    Provides unified API for both modes with migration path.
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

    def __init__(self, memory_path: str = "memory.md", use_mesh: bool = False, 
                 memory_dir: str = "./memory", config=None):
        """
        Initialize memory store.
        
        Args:
            memory_path: Path to legacy memory file
            use_mesh: If True, use Neural Markdown Mesh instead of legacy file
            memory_dir: Directory for mesh storage (if use_mesh=True)
            config: Optional Config object for advanced settings
        """
        self.memory_path = Path(memory_path)
        self.use_mesh = use_mesh
        self.memory_dir = Path(memory_dir)
        self.config = config

        # Import mesh only if needed
        self.mesh_store = None
        if self.use_mesh:
            from harness.inband_memory import InBandMemoryStore
            self.mesh_store = InBandMemoryStore(str(self.memory_dir))
            self.mesh_store.initialize()
        else:
            # Legacy mode - ensure memory file exists
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
        if self.use_mesh and self.mesh_store:
            # In mesh mode, return concatenated index or summary
            return self._get_mesh_summary()

        with read_locked(str(self.memory_path)) as content:
            return content

    def _get_mesh_summary(self) -> str:
        """Get a summary of mesh contents for legacy-compatible reading"""
        if not self.mesh_store:
            return ""

        # Build summary from all nodes
        summary_parts = ["# Agent Memory (Mesh Mode)\n"]

        for node_type in ["facts", "skills", "episodes"]:
            nodes = self.mesh_store.list_by_type(node_type)
            if nodes:
                summary_parts.append(f"\n## {node_type.title()}\n")
                for node_id in nodes[:10]:  # Limit to first 10 per type
                    node = self.mesh_store.get(node_id)
                    if node:
                        # MemoryDocument uses attributes, not metadata dict
                        title = getattr(node, 'title', None) or \
                                node.content.split('\n')[0][:50] if node.content else node_id
                        summary_parts.append(f"- [[{node_id}]]: {title}\n")

        return "".join(summary_parts)

    def get_section(self, section_name: str) -> str:
        """
        Get content of a specific section.
        
        Args:
            section_name: Name of section (e.g., "Active Topics")
            
        Returns:
            Section content
        """
        if self.use_mesh and self.mesh_store:
            # In mesh mode, map sections to node types
            section_map = {
                "Active Topics": "episodes",
                "Verified Facts": "facts",
                "User Preferences": "facts",
                "Patterns & Insights": "facts",
                "Action Items": "episodes",
            }
            node_type = section_map.get(section_name, "facts")
            nodes = self.mesh_store.list_by_type(node_type)

            if nodes:
                contents = []
                for node_id in nodes[:5]:  # Return top 5
                    node = self.mesh_store.get(node_id)
                    if node:
                        contents.append(f"### {node_id}\n{node.content}\n")
                return "\n".join(contents)
            return ""

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

        if self.use_mesh and self.mesh_store:
            # In mesh mode, create/update a node for this section
            node_id = f"{section.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            node_type_map = {
                "Active Topics": "episodes",
                "Verified Facts": "facts",
                "User Preferences": "facts",
                "Patterns & Insights": "facts",
                "Action Items": "episodes",
            }
            node_type = node_type_map.get(section, "facts")

            self.mesh_store.save(
                node_id=node_id,
                content=content,
                node_type=node_type,
                metadata={
                    "title": section,
                    "created_at": timestamp,
                    "source": "append_in_band"
                }
            )
        else:
            new_entry = f"\n### [{timestamp}] {section}\n{content}\n"
            append_atomic(str(self.memory_path), new_entry)

    def update_section(self, section_name: str, new_content: str):
        """
        Replace content of a specific section.
        
        Args:
            section_name: Name of section to update
            new_content: New section content
        """
        if self.use_mesh and self.mesh_store:
            # In mesh mode, update/create a consolidated node for this section
            node_id = f"{section_name.lower().replace(' ', '_')}"
            node_type_map = {
                "Active Topics": "episodes",
                "Verified Facts": "facts",
                "User Preferences": "facts",
                "Patterns & Insights": "facts",
                "Action Items": "episodes",
            }
            node_type = node_type_map.get(section_name, "facts")

            self.mesh_store.save(
                node_id=node_id,
                content=new_content,
                node_type=node_type,
                metadata={
                    "title": section_name,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": "update_section"
                }
            )
            return

        content = self.read_active()
        lines = content.split('\n')

        result_lines = []
        in_section = False
        section_header_found = False

        for line in lines:
            # Check if this is the target section header
            if line.strip().startswith('##') and section_name in line:
                if not section_header_found:
                    section_header_found = True
                    in_section = True
                    result_lines.append(line)
                    # Add new content after header
                    result_lines.append(new_content)
                    continue
            elif line.strip().startswith('##'):
                if in_section:
                    in_section = False
                result_lines.append(line)
                continue

            if not in_section:
                result_lines.append(line)

        if not section_header_found:
            # Section doesn't exist, append it
            result_lines.append(f"\n## {section_name}\n{new_content}")

        write_atomic(str(self.memory_path), '\n'.join(result_lines))

    def save_skill(self, skill_name: str, content: str, metadata: Optional[Dict] = None):
        """
        Save a skill to memory (unified API for both modes).
        
        Args:
            skill_name: Name/ID of the skill
            content: Skill content/description
            metadata: Optional metadata dict
        """
        if self.use_mesh and self.mesh_store:
            self.mesh_store.save(
                node_id=f"skill_{skill_name}",
                content=content,
                node_type="skills",
                metadata={
                    "title": skill_name,
                    "type": "skill",
                    "created_at": datetime.now().isoformat(),
                    **(metadata or {})
                }
            )
        else:
            # Legacy mode: append to a skills section
            self.append_in_band("Skills", f"**{skill_name}**: {content}")

    def save_fact(self, fact_id: str, content: str, metadata: Optional[Dict] = None):
        """
        Save a fact to memory (unified API for both modes).
        
        Args:
            fact_id: Unique identifier for the fact
            content: Fact content
            metadata: Optional metadata dict
        """
        if self.use_mesh and self.mesh_store:
            self.mesh_store.save(
                node_id=f"fact_{fact_id}",
                content=content,
                node_type="facts",
                metadata={
                    "title": fact_id,
                    "type": "fact",
                    "created_at": datetime.now().isoformat(),
                    **(metadata or {})
                }
            )
        else:
            # Legacy mode: append to Verified Facts section
            self.append_in_band("Verified Facts", f"**{fact_id}**: {content}")

    def search_memory(self, query: str) -> list:
        """
        Search memory for matching entries.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching lines with context
        """
        if self.use_mesh and self.mesh_store:
            # Use mesh search - returns list of (path, snippet, score) tuples
            results = self.mesh_store.search(query)
            return [f"{r[0].stem}: {r[1]}" for r in results]  # r is (Path, snippet, score)

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

    def migrate_to_mesh(self, archive_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Migrate from legacy memory.md to Neural Markdown Mesh.
        Parses the legacy file, creates mesh nodes, and archives the old file.
        
        Args:
            archive_path: Optional path to archive the legacy file
            
        Returns:
            Migration statistics
        """
        if not self.use_mesh or not self.mesh_store:
            raise RuntimeError("Mesh mode must be enabled to migrate")

        if not self.memory_path.exists():
            return {"status": "no_legacy_file", "migrated": 0}

        stats = {
            "sections_migrated": 0,
            "entries_created": 0,
            "archive_path": None,
            "errors": []
        }

        # Read legacy content
        legacy_content = self.read_active()
        lines = legacy_content.split('\n')

        # Parse sections
        current_section = None
        current_content = []
        sections = {}

        for line in lines:
            if line.strip().startswith('## '):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()

                # Start new section
                current_section = line.replace('##', '').strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()

        # Migrate each section to mesh nodes
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for section_name, content in sections.items():
            if not content.strip():
                continue

            try:
                # Map section to node type
                node_type_map = {
                    "Active Topics": "episodes",
                    "Verified Facts": "facts",
                    "User Preferences": "facts",
                    "Patterns & Insights": "facts",
                    "Action Items": "episodes",
                }
                node_type = node_type_map.get(section_name, "facts")
                node_id = f"legacy_{section_name.lower().replace(' ', '_')}_{timestamp}"

                self.mesh_store.save(
                    node_id=node_id,
                    content=content,
                    node_type=node_type,
                    metadata={
                        "title": section_name,
                        "source": "legacy_migration",
                        "migrated_at": datetime.now().isoformat(),
                        "original_section": section_name
                    }
                )
                stats["sections_migrated"] += 1
                stats["entries_created"] += 1

            except Exception as e:
                stats["errors"].append(f"Failed to migrate '{section_name}': {str(e)}")

        # Archive legacy file
        if archive_path:
            archive_dest = Path(archive_path)
        else:
            archive_dest = self.memory_path.parent / f"memory_archived_{timestamp}.md"

        try:
            import shutil
            shutil.copy2(str(self.memory_path), str(archive_dest))
            stats["archive_path"] = str(archive_dest)

            # Optionally clear or mark the legacy file
            write_atomic(str(self.memory_path), 
                        f"# Legacy Memory Archived\n\nThis file has been migrated to the Neural Markdown Mesh.\nArchive location: {archive_dest}\nMigration date: {datetime.now().isoformat()}\n")
        except Exception as e:
            stats["errors"].append(f"Failed to archive legacy file: {str(e)}")

        return stats

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

        if self.use_mesh and self.mesh_store:
            # In mesh mode, create a new episode node from the dream
            dream_content = dream_path.read_text()
            node_id = f"dream_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            self.mesh_store.save(
                node_id=node_id,
                content=dream_content,
                node_type="episodes",
                metadata={
                    "title": "Dream Consolidation",
                    "source": "dream_activation",
                    "created_at": datetime.now().isoformat()
                }
            )
        else:
            # Legacy mode
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

    def get_summary_stats(self) -> dict:
        """
        Get summary statistics about memory.
        
        Returns:
            Dict with token count, section count, etc.
        """
        if self.use_mesh and self.mesh_store:
            # Return mesh-specific stats
            all_nodes = self.mesh_store.list_all()
            return {
                "mode": "mesh",
                "node_count": len(all_nodes),
                "nodes": all_nodes[:20],  # First 20 nodes
                "memory_dir": str(self.memory_dir)
            }

        content = self.read_active()
        lines = content.split('\n')

        sections = [l for l in lines if l.strip().startswith('##')]
        entries = [l for l in lines if l.strip().startswith('###')]

        from harness.token_counter import TokenCounter
        counter = TokenCounter()

        return {
            "mode": "legacy",
            "token_count": counter.count_tokens(content),
            "character_count": len(content),
            "section_count": len(sections),
            "entry_count": len(entries),
            "sections": [s.strip().replace('##', '').strip() for s in sections]
        }
