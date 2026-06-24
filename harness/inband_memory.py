"""
In-Band Memory Implementation for Multi-Agent Systems

This module implements the linked markdown memory architecture with:
- File-based memory with YAML frontmatter
- Wikilink resolution between memories
- Permission enforcement
- Optimistic concurrency control
- Git-native versioning
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import yaml

from harness.file_ops import write_atomic, read_locked, append_atomic, FileLock


@dataclass
class MemoryDocument:
    """Represents a memory file with metadata and content."""
    id: str
    type: str
    agent: str
    created: str
    updated: str
    version: int
    tags: List[str]
    links: List[str]
    permissions: Dict[str, Any]
    sensitive: bool
    content: str  # Markdown content after frontmatter
    path: Path
    
    def to_markdown(self) -> str:
        """Serialize to markdown with frontmatter."""
        frontmatter = {
            'id': self.id,
            'type': self.type,
            'agent': self.agent,
            'created': self.created,
            'updated': self.updated,
            'version': self.version,
        }
        
        if self.tags:
            frontmatter['tags'] = self.tags
        if self.links:
            frontmatter['links'] = self.links
        if self.permissions:
            frontmatter['permissions'] = self.permissions
        if self.sensitive:
            frontmatter['sensitive'] = self.sensitive
        
        yaml_frontmatter = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_frontmatter}---\n\n{self.content}"


def parse_frontmatter(content: str) -> Tuple[Dict, str]:
    """
    Parse YAML frontmatter from markdown content.
    
    Returns:
        Tuple of (frontmatter_dict, body_content)
    """
    if not content.startswith('---'):
        return {}, content
    
    # Find end of frontmatter
    match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content
    
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
        body = match.group(2).strip()
        return frontmatter, body
    except yaml.YAMLError:
        return {}, content


class ConflictError(Exception):
    """Raised when optimistic concurrency check fails."""
    pass


class PermissionDeniedError(Exception):
    """Raised when agent lacks permission for operation."""
    pass


class LinkResolutionError(Exception):
    """Raised when a memory link cannot be resolved."""
    pass


class PermissionManager:
    """Manages access control for memory operations."""
    
    def __init__(self, permissions_path: str = "memory/permissions"):
        self.permissions_path = Path(permissions_path)
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load permission configuration from YAML."""
        config_file = self.permissions_path / "agent_permissions.yaml"
        if config_file.exists():
            return yaml.safe_load(config_file.read_text())
        return self._default_config()
    
    def _default_config(self) -> dict:
        """Default permissive configuration."""
        return {
            'global': {
                'default_read': 'all_agents',
                'default_write': 'owner_only'
            },
            'agents': {}
        }
    
    def check_permission(
        self,
        agent_id: str,
        action: str,  # 'read', 'write', 'delete'
        memory_path: str
    ) -> Tuple[bool, str]:
        """
        Check if agent has permission for action on memory.
        
        Returns:
            (allowed: bool, reason: str)
        """
        # Normalize path
        mem_path = Path(memory_path)
        
        # Check agent-specific rules
        agent_config = self.config.get('agents', {}).get(agent_id, {})
        
        # Check explicit restrictions first
        if 'cannot_access' in agent_config:
            for restricted in agent_config['cannot_access']:
                if str(mem_path).startswith(restricted):
                    return False, f"Access denied: {restricted} is restricted"
        
        # Check action-specific permissions
        perm_key = f'can_{action}'
        if perm_key in agent_config:
            allowed_paths = agent_config[perm_key]
            for allowed in allowed_paths:
                if str(mem_path).startswith(allowed) or str(mem_path) == allowed:
                    return True, "Explicitly allowed"
        
        # Fall back to global defaults
        global_config = self.config.get('global', {})
        if action == 'read' and global_config.get('default_read') == 'all_agents':
            return True, "Default read access"
        
        if action in ['write', 'delete'] and global_config.get('default_write') == 'owner_only':
            # Check if agent owns this memory
            if f'agents/{agent_id}' in str(mem_path):
                return True, "Owner access"
            return False, "Write/delete restricted to owner"
        
        return True, "Default allow"


class LinkResolver:
    """Resolves wikilinks between memory files."""
    
    def __init__(self, memory_root: str = "memory"):
        self.root = Path(memory_root)
        self.index: Dict[str, Path] = {}
        self._rebuild_index()
    
    def _rebuild_index(self):
        """Build index mapping memory IDs to file paths."""
        self.index = {}
        if not self.root.exists():
            return
        
        for md_file in self.root.rglob("*.md"):
            try:
                content = md_file.read_text()
                frontmatter, _ = parse_frontmatter(content)
                if 'id' in frontmatter:
                    self.index[frontmatter['id']] = md_file
            except Exception:
                continue
    
    def resolve(self, link: str, context_path: str = None) -> Path:
        """
        Resolve a wikilink to an absolute path.
        
        Args:
            link: Link reference (e.g., [[mem_id]], [[path]], [[path#section]])
            context_path: Path of file containing the link (for relative resolution)
        
        Returns:
            Absolute Path object
        """
        # Strip wikilink syntax if present
        link = link.strip('[]')
        
        # Remove section anchors
        if '#' in link:
            link = link.split('#')[0]
        
        # Remove custom link text
        if '|' in link:
            link = link.split('|')[0]
        
        # Try ID lookup first
        if link in self.index:
            return self.index[link].absolute()
        
        # Try as absolute path from memory root
        abs_path = self.root / link.lstrip('/')
        if abs_path.exists():
            return abs_path.absolute()
        
        # Try as relative path from context
        if context_path:
            context_dir = Path(context_path).parent
            rel_path = (context_dir / link).resolve()
            if rel_path.exists():
                return rel_path
        
        raise LinkResolutionError(f"Cannot resolve link: {link}")
    
    def extract_links(self, content: str) -> List[str]:
        """Extract all wikilinks from markdown content."""
        pattern = r'\[\[([^\]]+)\]\]'
        return re.findall(pattern, content)
    
    def get_backlinks(self, target_path: str) -> List[Path]:
        """Find all files that link to this memory."""
        backlinks = []
        target_path = str(target_path)
        
        # Get target ID if it's a file
        target_file = Path(target_path)
        target_id = None
        if target_file.exists():
            frontmatter, _ = parse_frontmatter(target_file.read_text())
            target_id = frontmatter.get('id')
        
        for md_file in self.root.rglob("*.md"):
            try:
                content = md_file.read_text()
                links = self.extract_links(content)
                
                for link in links:
                    # Clean link for comparison
                    clean_link = link.split('#')[0].split('|')[0]
                    
                    if clean_link == target_id or clean_link == target_path:
                        backlinks.append(md_file)
            except Exception:
                continue
        
        return backlinks


class InBandMemory:
    """
    Primary interface for agents to interact with linked markdown memory.
    
    Features:
    - File-based memory with YAML frontmatter
    - Wikilink resolution
    - Permission enforcement
    - Optimistic concurrency control
    - Atomic operations
    """
    
    def __init__(self, agent_id: str, memory_root: str = "memory"):
        self.agent_id = agent_id
        self.root = Path(memory_root)
        self.permissions = PermissionManager()
        self.links = LinkResolver(memory_root)
        
        # Ensure root exists
        self.root.mkdir(parents=True, exist_ok=True)
    
    def _generate_id(self, memory_type: str) -> str:
        """Generate unique memory ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{memory_type}_{timestamp}_{self.agent_id}"
    
    def _check_permission(self, action: str, memory_path: str):
        """Check permissions and raise if denied."""
        allowed, reason = self.permissions.check_permission(
            self.agent_id, action, memory_path
        )
        if not allowed:
            raise PermissionDeniedError(reason)
    
    # === READ OPERATIONS ===
    
    def read(self, memory_path: str, include_links: bool = False) -> MemoryDocument:
        """
        Read a memory file with permission checking.
        
        Args:
            memory_path: Path or ID of memory to read
            include_links: If True, also fetch linked memories
        
        Returns:
            MemoryDocument object
        """
        # Resolve path if it's an ID
        path_obj = Path(memory_path)
        if not path_obj.exists():
            try:
                path_obj = self.links.resolve(memory_path)
            except LinkResolutionError:
                path_obj = self.root / memory_path
                if not path_obj.exists():
                    raise FileNotFoundError(f"Memory not found: {memory_path}")
        
        # Check permission
        self._check_permission('read', str(path_obj))
        
        # Read with shared lock
        with read_locked(str(path_obj)) as content:
            frontmatter, body = parse_frontmatter(content)
            
            doc = MemoryDocument(
                id=frontmatter.get('id', ''),
                type=frontmatter.get('type', 'unknown'),
                agent=frontmatter.get('agent', ''),
                created=frontmatter.get('created', ''),
                updated=frontmatter.get('updated', ''),
                version=frontmatter.get('version', 1),
                tags=frontmatter.get('tags', []),
                links=frontmatter.get('links', []),
                permissions=frontmatter.get('permissions', {}),
                sensitive=frontmatter.get('sensitive', False),
                content=body,
                path=path_obj
            )
            
            return doc
    
    def search(self, query: str, scope: str = "all") -> List[Tuple[Path, str, float]]:
        """
        Search across accessible memories.
        
        Args:
            query: Search string
            scope: Restrict search: "shared", "agent", "all"
        
        Returns:
            List of (path, matching_snippet, relevance_score) tuples
        """
        results = []
        query_lower = query.lower()
        
        # Determine search scope
        patterns = []
        if scope == "shared":
            patterns = ["shared/**/*.md"]
        elif scope == "agent":
            patterns = [f"agents/{self.agent_id}/**/*.md"]
        else:
            patterns = ["**/*.md"]
        
        for pattern in patterns:
            for md_file in self.root.glob(pattern):
                try:
                    # Check read permission
                    allowed, _ = self.permissions.check_permission(
                        self.agent_id, 'read', str(md_file)
                    )
                    if not allowed:
                        continue
                    
                    content = md_file.read_text()
                    
                    # Simple relevance scoring
                    matches = content.lower().count(query_lower)
                    if matches > 0:
                        # Find best matching snippet
                        lines = content.split('\n')
                        best_line = ""
                        best_count = 0
                        for line in lines:
                            count = line.lower().count(query_lower)
                            if count > best_count:
                                best_count = count
                                best_line = line
                        
                        results.append((md_file, best_line.strip(), matches))
                except Exception:
                    continue
        
        # Sort by relevance
        results.sort(key=lambda x: x[2], reverse=True)
        return results
    
    def traverse_links(self, start_path: str, max_depth: int = 3) -> List[MemoryDocument]:
        """
        Follow links from starting memory to build context graph.
        
        Args:
            start_path: Starting memory path
            max_depth: Maximum link depth to traverse
        
        Returns:
            List of all reachable MemoryDocuments
        """
        visited = set()
        documents = []
        
        def traverse(path: str, depth: int):
            if depth > max_depth or path in visited:
                return
            
            visited.add(path)
            
            try:
                doc = self.read(path)
                documents.append(doc)
                
                # Follow links
                for link in doc.links:
                    try:
                        resolved = self.links.resolve(link, str(doc.path))
                        traverse(str(resolved), depth + 1)
                    except (LinkResolutionError, PermissionDeniedError):
                        continue
            except (FileNotFoundError, PermissionDeniedError):
                pass
        
        traverse(start_path, 0)
        return documents
    
    # === WRITE OPERATIONS ===
    
    def create(
        self,
        memory_type: str,
        content: str,
        metadata: dict = None,
        tags: List[str] = None
    ) -> str:
        """
        Create a new memory file.
        
        Args:
            memory_type: Type of memory (fact, thread, source, etc.)
            content: Markdown content
            metadata: Additional frontmatter fields
            tags: List of tags
        
        Returns:
            ID of created memory
        """
        # Determine storage location based on type
        if memory_type in ['source', 'research_thread']:
            base_dir = self.root / "agents" / self.agent_id / f"{memory_type}s"
        else:
            base_dir = self.root / "agents" / self.agent_id
        
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate ID and filename
        memory_id = self._generate_id(memory_type)
        filename = f"{memory_id}.md"
        filepath = base_dir / filename
        
        # Check write permission
        self._check_permission('write', str(filepath))
        
        # Create document
        now = datetime.now().isoformat()
        doc = MemoryDocument(
            id=memory_id,
            type=memory_type,
            agent=self.agent_id,
            created=now,
            updated=now,
            version=1,
            tags=tags or [],
            links=[],
            permissions={},
            sensitive=False,
            content=content.strip(),
            path=filepath
        )
        
        # Add any extra metadata
        if metadata:
            for key, value in metadata.items():
                setattr(doc, key, value)
        
        # Write atomically
        write_atomic(str(filepath), doc.to_markdown())
        
        # Update link index
        self.links._rebuild_index()
        
        return memory_id
    
    def update(self, memory_path: str, content: str, expected_version: int = None) -> bool:
        """
        Update existing memory with optimistic concurrency control.
        
        Args:
            memory_path: Path or ID of memory to update
            content: New content
            expected_version: Expected version number (for conflict detection)
        
        Returns:
            True if successful
        
        Raises:
            ConflictError: If version mismatch detected
        """
        # Read current state
        doc = self.read(memory_path)
        
        # Check version for optimistic concurrency
        if expected_version is not None:
            if doc.version != expected_version:
                raise ConflictError(
                    f"Version conflict: expected {expected_version}, "
                    f"found {doc.version}"
                )
        
        # Check write permission
        self._check_permission('write', str(doc.path))
        
        # Update document
        doc.content = content.strip()
        doc.version += 1
        doc.updated = datetime.now().isoformat()
        
        # Write atomically
        write_atomic(str(doc.path), doc.to_markdown())
        
        return True
    
    def append(self, memory_path: str, section: str, content: str):
        """
        Append content to a specific section atomically.
        
        Args:
            memory_path: Target memory
            section: Section header to append under
            content: Content to append
        """
        doc = self.read(memory_path)
        self._check_permission('write', str(doc.path))
        
        # Format entry with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n### [{timestamp}]\n{content}\n"
        
        # Find section and append
        lines = doc.content.split('\n')
        result_lines = []
        in_section = False
        appended = False
        
        for line in lines:
            result_lines.append(line)
            
            if line.strip().startswith('##') and section in line:
                in_section = True
            elif line.strip().startswith('##') and in_section:
                if not appended:
                    result_lines.append(new_entry)
                    appended = True
                in_section = False
        
        # If section not found or at end, append to end
        if not appended:
            result_lines.append(f"\n## {section}\n{new_entry}")
        
        doc.content = '\n'.join(result_lines)
        doc.version += 1
        doc.updated = datetime.now().isoformat()
        
        write_atomic(str(doc.path), doc.to_markdown())
    
    def link_memories(self, source_path: str, target_path: str, link_text: str = None):
        """
        Create a link between two memories.
        
        Args:
            source_path: Memory to add link to
            target_path: Memory to link to
            link_text: Optional display text
        """
        source_doc = self.read(source_path)
        self._check_permission('write', str(source_doc.path))
        
        # Verify target exists and is readable
        target_doc = self.read(target_path)
        
        # Create link syntax
        if link_text:
            link = f"[[{target_path}|{link_text}]]"
        else:
            link = f"[[{target_path}]]"
        
        # Add to frontmatter links if not already present
        if target_path not in source_doc.links:
            source_doc.links.append(target_path)
        
        # Also append to content as reference
        source_doc.content += f"\n\nSee also: {link}"
        source_doc.version += 1
        source_doc.updated = datetime.now().isoformat()
        
        write_atomic(str(source_doc.path), source_doc.to_markdown())
    
    def delete(self, memory_path: str, soft_delete: bool = True):
        """
        Delete or archive a memory.
        
        Args:
            memory_path: Memory to delete
            soft_delete: If True, move to archive instead of permanent delete
        """
        doc = self.read(memory_path)
        self._check_permission('delete', str(doc.path))
        
        if soft_delete:
            # Move to archive
            archive_dir = self.root / ".archive" / self.agent_id
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            archived_path = archive_dir / doc.path.name
            doc.path.rename(archived_path)
        else:
            # Permanent delete
            doc.path.unlink()
        
        # Update link index
        self.links._rebuild_index()
    
    # === MAINTENANCE OPERATIONS ===
    
    def cleanup_orphaned_links(self) -> List[str]:
        """
        Find and report broken links across all memories.
        
        Returns:
            List of broken link references
        """
        broken = []
        
        for md_file in self.root.rglob("*.md"):
            try:
                content = md_file.read_text()
                links = self.links.extract_links(content)
                
                for link in links:
                    clean_link = link.split('#')[0].split('|')[0]
                    try:
                        self.links.resolve(clean_link, str(md_file))
                    except LinkResolutionError:
                        broken.append(f"{md_file}: {link}")
            except Exception:
                continue
        
        return broken
    
    def get_memory_graph(self) -> Dict[str, List[str]]:
        """
        Build adjacency list representation of memory link graph.
        
        Returns:
            Dict mapping memory IDs to lists of linked memory IDs
        """
        graph = {}
        
        for md_file in self.root.rglob("*.md"):
            try:
                content = md_file.read_text()
                frontmatter, _ = parse_frontmatter(content)
                memory_id = frontmatter.get('id', str(md_file))
                
                links = self.links.extract_links(content)
                graph[memory_id] = links
            except Exception:
                continue
        
        return graph


# Example usage
if __name__ == "__main__":
    # Initialize memory system for researcher agent
    memory = InBandMemory(agent_id="researcher", memory_root="memory")
    
    # Create a new research thread
    thread_id = memory.create(
        memory_type="research_thread",
        content="""# Attention Mechanisms in LLMs

## Current Hypothesis
Multi-head attention scales sub-linearly with context window...

## Evidence
- Need to verify against recent papers

## Open Questions
1. Does sparse attention help?
""",
        tags=["attention", "transformers", "active"]
    )
    
    # Search for related memories
    results = memory.search("attention mechanisms", scope="agent")
    print(f"Found {len(results)} related memories")
    
    # Append new finding
    memory.append(
        f"agents/researcher/research_threads/{thread_id}.md",
        section="Evidence",
        content="New paper shows 40% improvement with sliding window attention"
    )
    
    # Get memory graph
    graph = memory.get_memory_graph()
    print(f"Memory graph has {len(graph)} nodes")
