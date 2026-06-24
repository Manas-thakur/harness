# In-Band Memory Architecture for Multi-Agent Fleets

## Overview

This document outlines the production architecture for linked markdown memory files supporting multiple long-running agents with permissioning, versioning, concurrency control, and portability.

## Core Principles

1. **Memory as Files**: Each memory unit is a standalone `.md` file
2. **Linked Knowledge**: Files reference each other via markdown links
3. **Namespace Isolation**: Agents operate in scoped directories
4. **Atomic Operations**: All writes use atomic file operations
5. **Git-Native**: Full version history through Git integration

---

## Directory Structure

```
memory/
├── shared/                    # Cross-agent shared knowledge
│   ├── index.md              # Shared memory index
│   ├── domain_knowledge/     # Domain-specific facts
│   │   ├── python_ecosystem.md
│   │   └── ml_best_practices.md
│   └── user_preferences.md   # User-wide preferences
│
├── agents/                    # Per-agent memory namespaces
│   ├── researcher/
│   │   ├── active_context.md
│   │   ├── sources/          # Cited sources
│   │   │   ├── paper_2024_transformer.md
│   │   │   └── blog_llm_scaling.md
│   │   └── research_threads/
│   │       ├── thread_001_attention.md
│   │       └── thread_002_rlhf.md
│   │
│   ├── coder/
│   │   ├── active_context.md
│   │   ├── code_patterns/
│   │   │   ├── async_io_pattern.md
│   │   │   └── error_handling.md
│   │   └── project_knowledge/
│   │       ├── project_a_architecture.md
│   │       └── project_b_deps.md
│   │
│   └── tutor/
│       ├── active_context.md
│       ├── teaching_strategies.md
│       └── student_models/
│           └── student_john_progress.md
│
├── sessions/                  # Session transcripts (read-only after completion)
│   ├── 2026-01-15/
│   │   ├── session_001_researcher.md
│   │   └── session_002_coder.md
│   └── 2026-01-16/
│       └── session_003_tutor.md
│
├── dreams/                    # Consolidated dream outputs
│   ├── dream_2026-01-15_consolidation.md
│   └── dream_2026-01-16_patterns.md
│
├── versions/                  # Snapshot backups (git-managed)
│   └── (git history)
│
└── permissions/               # Access control definitions
    ├── agent_permissions.yaml
    └── sensitive_topics.yaml
```

---

## Memory File Schema

Each memory file follows a consistent frontmatter + content structure:

```markdown
---
id: mem_20260115_researcher_001
type: research_thread
agent: researcher
created: 2026-01-15T14:30:00Z
updated: 2026-01-15T16:45:00Z
version: 3
tags: [attention-mechanism, transformers, active]
links:
  - [[shared/domain_knowledge/python_ecosystem]]
  - [[../coder/project_knowledge/project_a_architecture]]
permissions:
  read: [researcher, tutor]
  write: [researcher]
  sensitive: false
---

# Research Thread: Attention Mechanisms in LLMs

## Current Hypothesis
Multi-head attention scales sub-linearly with context window...

## Evidence
- Source: [[../sources/paper_2024_transformer]]
- Observation: Performance drops after 32k context

## Open Questions
1. Does sparse attention help?
2. What about sliding window approaches?

## Related
- See also: [[shared/domain_knowledge/ml_best_practices]]
```

### Frontmatter Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Unique identifier (UUID or timestamp-based) |
| `type` | enum | ✅ | Memory type: `fact`, `thread`, `source`, `pattern`, `preference`, `action_item` |
| `agent` | string | ✅ | Owning agent namespace |
| `created` | ISO8601 | ✅ | Creation timestamp |
| `updated` | ISO8601 | ✅ | Last modification timestamp |
| `version` | int | ✅ | Semantic version for conflict detection |
| `tags` | list | ❌ | Searchable tags |
| `links` | list | ❌ | Internal memory references |
| `permissions` | object | ❌ | Override global permissions |
| `sensitive` | bool | ❌ | Marks sensitive content |

---

## Concurrency Model

### File-Level Locking

Each memory file has an associated `.lock` file:

```python
# Example: memory/agents/researcher/active_context.md.lock
```

**Lock Types:**
- **Shared (Read)**: Multiple agents can read simultaneously
- **Exclusive (Write)**: Only one writer at a time

**Implementation:**
```python
from harness.file_ops import FileLock, read_locked, write_atomic

# Reading (shared lock)
with read_locked('memory/agents/researcher/active_context.md') as content:
    process(content)

# Writing (exclusive lock via write_atomic)
write_atomic('memory/agents/researcher/active_context.md', new_content)
```

### Conflict Resolution Strategy

1. **Optimistic Concurrency**: 
   - Check `version` field in frontmatter before write
   - If version mismatch → merge required
   
2. **Merge Protocol**:
   ```python
   def resolve_conflict(base_version, agent_a_changes, agent_b_changes):
       # 1. Auto-merge non-overlapping sections
       # 2. Flag conflicting sections for manual review
       # 3. Create conflict marker in file
       # 4. Notify coordinating agent
   ```

3. **Last-Writer-Wins with Audit**:
   - For simple updates, last write wins
   - All changes logged in Git history
   - Rollback always possible

---

## Permissioning System

### Hierarchical Permissions

```yaml
# memory/permissions/agent_permissions.yaml

global:
  default_read: all_agents
  default_write: owner_only
  sensitive_prefix: "private/"

agents:
  researcher:
    can_read:
      - shared/*
      - agents/researcher/*
      - agents/tutor/teaching_strategies.md
    can_write:
      - agents/researcher/*
      - shared/domain_knowledge/*
    can_delete:
      - agents/researcher/sources/*
    
  coder:
    can_read:
      - shared/*
      - agents/coder/*
    can_write:
      - agents/coder/*
    restricted:
      - memory/sessions/*  # Read-only access
    
  tutor:
    can_read:
      - shared/*
      - agents/tutor/*
      - agents/researcher/active_context.md
    can_write:
      - agents/tutor/*
    cannot_access:
      - agents/coder/project_knowledge/*  # IP protection

sensitive_topics:
  patterns:
    - "API_KEY"
    - "PASSWORD"
    - "TOKEN"
  action: encrypt_and_restrict
```

### Permission Enforcement

```python
class PermissionManager:
    def __init__(self, permissions_path: str = "memory/permissions"):
        self.config = load_yaml(permissions_path / "agent_permissions.yaml")
    
    def check_permission(
        self, 
        agent_id: str, 
        action: str,  # read, write, delete
        memory_path: str
    ) -> Tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str)
        """
        # 1. Check global restrictions
        # 2. Check agent-specific rules
        # 3. Check file-level overrides
        # 4. Check sensitive content markers
        pass
    
    def get_accessible_memories(self, agent_id: str) -> List[str]:
        """Returns list of memory paths agent can access"""
        pass
```

---

## Versioning Strategy

### Git Integration

Every memory directory is a Git repository:

```bash
memory/
  .git/                    # Git repository root
  shared/
  agents/
  sessions/
```

**Commit Strategy:**
- **Per-Session Commits**: One commit per agent session
- **Atomic Multi-File Commits**: Related updates grouped together
- **Dream Consolidation Commits**: Marked with `[dream]` prefix

**Branch Strategy:**
```
main          # Production memory state
├── dev       # Active development (optional)
├── agent/researcher  # Agent-specific branches for long tasks
└── agent/coder
```

### Snapshot Management

```python
class MemoryVersioning:
    def create_snapshot(self, message: str, paths: List[str] = None):
        """Create git snapshot of specified memory files"""
        
    def rollback(self, target_version: str, paths: List[str] = None):
        """Rollback specific files or entire memory to version"""
        
    def diff(self, version_a: str, version_b: str, path: str = None):
        """Show differences between versions"""
        
    def get_history(self, path: str, limit: int = 50):
        """Get version history for a memory file"""
```

---

## Portability Design

### Memory Bundles

Export entire memory states as portable bundles:

```bash
# Export
agent memory export --output bundle_2026-01-15.tar.gz \
  --include shared/,agents/researcher/ \
  --exclude sessions/

# Import
agent memory import bundle_2026-01-15.tar.gz \
  --merge-strategy=three-way \
  --conflict-prompt=true
```

**Bundle Format:**
```
bundle_2026-01-15.tar.gz
├── manifest.json         # Metadata, checksums, version map
├── memory/               # Actual memory files
│   ├── shared/
│   └── agents/
└── signatures/           # Optional GPG signatures
```

### Migration Scripts

For schema evolution:

```python
# memory/migrations/001_add_frontmatter.py
def migrate_v1_to_v2(memory_file: Path):
    """Add YAML frontmatter to legacy memory files"""
    content = memory_file.read_text()
    frontmatter = generate_frontmatter(content)
    new_content = f"{frontmatter}\n\n{content}"
    write_atomic(str(memory_file), new_content)
```

---

## Link Resolution System

### Wikilink Syntax

Agents can reference other memories using:

```markdown
[[memory_id]]                    # Resolve by ID
[[relative/path/to/file]]        # Relative path
[[/absolute/path]]               # Absolute from memory root
[[path#section]]                 # Link to specific section
[[path|Custom Link Text]]        # With custom text
```

### Link Resolution Algorithm

```python
class LinkResolver:
    def __init__(self, memory_root: str = "memory"):
        self.root = Path(memory_root)
        self.index = self._build_link_index()
    
    def resolve(self, link: str, context_path: str) -> Path:
        """
        Resolve a link reference to absolute path.
        
        Args:
            link: Link string (e.g., "../sources/paper_001")
            context_path: Path of file containing the link
        
        Returns:
            Absolute Path object
        """
        # 1. Check if it's a UUID/ID reference
        # 2. Check if it's a relative path
        # 3. Check if it's an absolute path
        # 4. Validate permissions for accessing target
        # 5. Return resolved path or raise LinkResolutionError
    
    def _build_link_index(self) -> Dict[str, Path]:
        """Build index of all memory IDs to paths"""
        index = {}
        for md_file in self.root.rglob("*.md"):
            frontmatter = parse_frontmatter(md_file)
            if frontmatter and 'id' in frontmatter:
                index[frontmatter['id']] = md_file
        return index
    
    def get_backlinks(self, target_path: str) -> List[Path]:
        """Find all files that link to this memory"""
        backlinks = []
        target_id = self._get_id_for_path(target_path)
        
        for md_file in self.root.rglob("*.md"):
            content = md_file.read_text()
            if f"[[{target_id}]]" in content or f"[[{target_path}]]" in content:
                backlinks.append(md_file)
        
        return backlinks
```

---

## Agent Memory API

### High-Level Interface

```python
class InBandMemory:
    """
    Primary interface for agents to interact with linked memory.
    """
    
    def __init__(self, agent_id: str, memory_root: str = "memory"):
        self.agent_id = agent_id
        self.root = Path(memory_root)
        self.permissions = PermissionManager()
        self.links = LinkResolver(memory_root)
        self.versioning = MemoryVersioning()
    
    # === READ OPERATIONS ===
    
    def read(self, memory_path: str, include_links: bool = False) -> MemoryDocument:
        """
        Read a memory file with permission checking.
        
        Args:
            memory_path: Path or ID of memory to read
            include_links: If True, resolve and fetch linked memories
        
        Returns:
            MemoryDocument object with content and metadata
        """
        
    def search(self, query: str, scope: str = "all") -> List[MemoryHit]:
        """
        Search across accessible memories.
        
        Args:
            query: Search string (supports boolean operators)
            scope: Restrict search: "shared", "agent", "all"
        
        Returns:
            List of matches with relevance scores
        """
    
    def traverse_links(self, start_path: str, max_depth: int = 3) -> List[MemoryDocument]:
        """
        Follow links from starting memory to build context graph.
        
        Args:
            start_path: Starting memory path
            max_depth: Maximum link depth to traverse
        
        Returns:
            List of all reachable memories
        """
    
    # === WRITE OPERATIONS ===
    
    def create(self, memory_type: str, content: str, metadata: dict = None) -> str:
        """
        Create a new memory file.
        
        Args:
            memory_type: Type of memory (fact, thread, source, etc.)
            content: Markdown content
            metadata: Additional frontmatter fields
        
        Returns:
            ID of created memory
        """
    
    def update(self, memory_path: str, content: str, version: int = None) -> bool:
        """
        Update existing memory with optimistic concurrency control.
        
        Args:
            memory_path: Path or ID of memory to update
            content: New content
            version: Expected version (for conflict detection)
        
        Returns:
            True if successful, raises ConflictError on version mismatch
        """
    
    def append(self, memory_path: str, section: str, content: str):
        """
        Append content to a specific section atomically.
        
        Args:
            memory_path: Target memory
            section: Section header to append under
            content: Content to append
        """
    
    def link(self, source_path: str, target_path: str, link_text: str = None):
        """
        Create a link between two memories.
        
        Args:
            source_path: Memory to add link to
            target_path: Memory to link to
            link_text: Optional display text
        """
    
    def delete(self, memory_path: str, soft_delete: bool = True):
        """
        Delete or archive a memory.
        
        Args:
            memory_path: Memory to delete
            soft_delete: If True, move to archive instead of permanent delete
        """
    
    # === MAINTENANCE OPERATIONS ===
    
    def consolidate(self, target_path: str, source_paths: List[str], summary: str):
        """
        Merge multiple memories into one consolidated memory.
        
        Args:
            target_path: Destination memory
            source_paths: Memories to consolidate
            summary: Summary of consolidation reasoning
        """
    
    def cleanup_orphaned_links(self) -> List[str]:
        """
        Find and report broken links across all memories.
        
        Returns:
            List of broken link references
        """
    
    def get_memory_graph(self) -> Dict[str, List[str]]:
        """
        Build adjacency list representation of memory link graph.
        
        Returns:
            Dict mapping memory IDs to lists of linked memory IDs
        """
```

---

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Implement `InBandMemory` class with basic CRUD
- [ ] Add YAML frontmatter parsing/generation
- [ ] Implement `LinkResolver` with wikilink support
- [ ] Set up Git integration for versioning
- [ ] Create directory structure scaffolding

### Phase 2: Concurrency & Permissions
- [ ] Implement `PermissionManager` with YAML config
- [ ] Add file-level locking to all operations
- [ ] Implement optimistic concurrency control
- [ ] Add conflict detection and resolution
- [ ] Create permission enforcement middleware

### Phase 3: Advanced Features
- [ ] Implement link traversal for context building
- [ ] Add backlink tracking
- [ ] Create memory bundle export/import
- [ ] Build migration framework for schema evolution
- [ ] Implement orphaned link detection

### Phase 4: Production Hardening
- [ ] Add comprehensive logging and audit trails
- [ ] Implement monitoring and alerting
- [ ] Create backup and disaster recovery procedures
- [ ] Performance optimization (caching, indexing)
- [ ] Documentation and runbooks

---

## Benefits Over JSON-Based Memory

| Aspect | JSON Memory | In-Band Markdown |
|--------|-------------|------------------|
| **Human Readability** | Requires parser | Instantly readable |
| **Diff Quality** | Poor (structure-sensitive) | Excellent (line-based) |
| **Linking** | Requires external graph DB | Native markdown links |
| **Concurrency** | Single file bottleneck | File-level parallelism |
| **Permissions** | Application-level only | OS + application layers |
| **Versioning** | Custom implementation | Git-native |
| **Portability** | Requires schema knowledge | Universal format |
| **Agent Reasoning** | Must parse structure | Can read like documents |
| **Debugging** | Tool-dependent | Any text editor |
| **Scalability** | Degrades with size | Scales horizontally |

---

## Conclusion

In-band markdown memory provides superior characteristics for production multi-agent systems:

✅ **Better for Humans**: Inspectable, editable, understandable  
✅ **Better for Agents**: Natural language format matches training data  
✅ **Better for Operations**: Git-native, file-level concurrency, OS permissions  
✅ **Better for Scale**: Horizontal scaling through file distribution  
✅ **Better for Maintenance**: No database migrations, universal tools  

This architecture transforms memory from a technical implementation detail into a first-class citizen of your agent system.
