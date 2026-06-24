# In-Band Memory Quick Start

## What is In-Band Memory?

In-band memory stores agent knowledge as **linked markdown files** instead of JSON databases. This approach provides:

✅ **Human-readable** - Open any file in a text editor  
✅ **Git-native** - Full version history with standard git  
✅ **File-level concurrency** - Multiple agents can work simultaneously  
✅ **Natural linking** - Wikilinks connect related memories  
✅ **Permission layers** - OS + application-level access control  

---

## Directory Structure

After initialization, your memory directory looks like:

```
memory/
├── shared/                    # Cross-agent knowledge
│   └── index.md
├── agents/
│   ├── researcher/           # Researcher's private memory
│   │   ├── research_threads/
│   │   └── sources/
│   ├── coder/                # Coder's private memory
│   │   ├── code_patterns/
│   │   └── project_knowledge/
│   └── tutor/                # Tutor's private memory
│       └── teaching_strategies.md
└── permissions/
    └── agent_permissions.yaml
```

---

## Basic Usage

### Initialize for an Agent

```python
from harness.inband_memory import InBandMemory

# Each agent gets its own namespace
researcher = InBandMemory(agent_id="researcher", memory_root="memory")
coder = InBandMemory(agent_id="coder", memory_root="memory")
```

### Create a Memory

```python
# Create a research thread
thread_id = researcher.create(
    memory_type="research_thread",
    content="""# Attention Mechanisms

## Hypothesis
Multi-head attention scales sub-linearly...

## Evidence
- Paper A shows X
- Paper B shows Y
""",
    tags=["attention", "transformers", "active"]
)
print(f"Created: {thread_id}")
```

This creates a file like:
```
memory/agents/researcher/research_threads/research_thread_20260115_143000_researcher.md
```

With frontmatter:
```yaml
---
id: research_thread_20260115_143000_researcher
type: research_thread
agent: researcher
created: '2026-01-15T14:30:00'
version: 1
tags: [attention, transformers, active]
---
```

### Read a Memory

```python
# By ID or path
doc = researcher.read(thread_id)
print(doc.content)
print(f"Version: {doc.version}")
print(f"Tags: {doc.tags}")
```

### Update with Optimistic Concurrency

```python
# Read current version
doc = researcher.read(thread_id)

# Update (checks version automatically)
try:
    researcher.update(
        thread_id,
        content="# Updated content...",
        expected_version=doc.version  # Optional conflict detection
    )
except ConflictError:
    print("Someone else modified this! Handle merge.")
```

### Append to a Section

```python
# Atomic append to specific section
researcher.append(
    thread_id,
    section="Evidence",
    content="New paper shows 40% improvement with sparse attention"
)
```

### Link Memories Together

```python
# Create a new source memory
source_id = researcher.create(
    memory_type="source",
    content="# Vaswani et al. 2017\nAttention Is All You Need..."
)

# Link thread to source
researcher.link_memories(
    source_path=thread_id,
    target_path=source_id,
    link_text="Original Transformer Paper"
)
```

Now the thread contains:
```markdown
See also: [[source_20260115_143500_researcher|Original Transformer Paper]]
```

### Search Across Memories

```python
# Search all accessible memories
results = researcher.search("attention mechanisms", scope="all")

for path, snippet, score in results:
    print(f"{path}: {snippet} (score: {score})")

# Search only agent's own memories
my_results = researcher.search("attention", scope="agent")

# Search shared knowledge only
shared_results = researcher.search("best practices", scope="shared")
```

### Traverse Link Graph

```python
# Get all memories reachable from starting point (max 3 hops)
related = researcher.traverse_links(thread_id, max_depth=3)

print(f"Found {len(related)} related memories")
for doc in related:
    print(f"  - {doc.id}: {doc.content[:50]}...")
```

---

## Permission System

### Default Configuration

By default:
- **Read**: All agents can read all memories
- **Write**: Agents can only write to their own namespace
- **Delete**: Restricted to owner

### Custom Permissions

Create `memory/permissions/agent_permissions.yaml`:

```yaml
global:
  default_read: all_agents
  default_write: owner_only

agents:
  researcher:
    can_read:
      - shared/*
      - agents/researcher/*
      - agents/tutor/teaching_strategies.md
    can_write:
      - agents/researcher/*
      - shared/domain_knowledge/*
    
  coder:
    can_read:
      - shared/*
      - agents/coder/*
    can_write:
      - agents/coder/*
    cannot_access:
      - agents/tutor/student_models/*  # Privacy protection
```

### Check Permissions Programmatically

```python
from harness.inband_memory import PermissionManager

perms = PermissionManager()

allowed, reason = perms.check_permission(
    agent_id="researcher",
    action="write",
    memory_path="agents/coder/project_knowledge/arch.md"
)

if not allowed:
    print(f"Denied: {reason}")
```

---

## Concurrency Model

### File-Level Locking

Each memory file has a `.lock` companion:

```python
from harness.file_ops import read_locked, write_atomic

# Shared lock for reading (multiple readers OK)
with read_locked('memory/agents/researcher/active.md') as content:
    process(content)

# Exclusive lock for writing (one writer at a time)
write_atomic('memory/agents/researcher/active.md', new_content)
```

### Optimistic Concurrency

For collaborative editing:

```python
def safe_update(memory, path, new_content):
    """Update with automatic retry on conflict."""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            doc = memory.read(path)
            memory.update(path, new_content, expected_version=doc.version)
            return True
        except ConflictError:
            if attempt == max_retries - 1:
                raise
            # Retry with fresh version
            continue
```

---

## Version Control

### Git Integration

The entire `memory/` directory is a git repository:

```bash
cd memory
git init  # If not already initialized

# After each session
git add .
git commit -m "[researcher] Updated attention research thread"

# View history
git log --oneline agents/researcher/research_threads/

# Diff versions
git diff HEAD~1 HEAD -- agents/researcher/active_context.md
```

### Rollback

```python
from harness.versioning import VersioningSystem

versioning = VersioningSystem(versions_dir="memory/versions")

# List snapshots
snapshots = versioning.list_snapshots()
print(f"Available versions: {[s.name for s in snapshots]}")

# Rollback to specific version
versioning.rollback("v_20260115_143000.md")
```

---

## Portability

### Export Memory Bundle

```bash
# Export specific agent memories
agent memory export \
  --output researcher_bundle.tar.gz \
  --include agents/researcher/,shared/ \
  --exclude sessions/
```

### Import Bundle

```bash
# Import with merge strategy
agent memory import \
  researcher_bundle.tar.gz \
  --merge-strategy=three-way \
  --conflict-prompt=true
```

---

## Advanced Features

### Backlink Discovery

Find all memories that reference a specific memory:

```python
link_resolver = LinkResolver("memory")

backlinks = link_resolver.get_backlinks("agents/researcher/sources/paper_001.md")

print("Memories citing this source:")
for path in backlinks:
    print(f"  - {path}")
```

### Memory Graph Analysis

```python
graph = researcher.get_memory_graph()

# Find most connected memories
connection_counts = {k: len(v) for k, v in graph.items()}
top_hubs = sorted(connection_counts.items(), key=lambda x: x[1], reverse=True)[:5]

print("Top 5 memory hubs:")
for memory_id, count in top_hubs:
    print(f"  {memory_id}: {count} links")
```

### Orphaned Link Detection

```python
broken_links = researcher.cleanup_orphaned_links()

if broken_links:
    print("Broken links found:")
    for link in broken_links:
        print(f"  {link}")
else:
    print("✓ All links valid")
```

---

## Migration from JSON Memory

If you have existing JSON-based memory:

```python
from pathlib import Path
from harness.inband_memory import InBandMemory
import json

def migrate_json_to_markdown(json_file: str, output_dir: str):
    """Convert legacy JSON memory to markdown format."""
    memory = InBandMemory(agent_id="migrated", memory_root=output_dir)
    
    with open(json_file) as f:
        data = json.load(f)
    
    # Convert each entry
    for entry in data.get('memories', []):
        memory.create(
            memory_type=entry.get('type', 'fact'),
            content=entry.get('content', ''),
            tags=entry.get('tags', []),
            metadata={
                'migrated_from': json_file,
                'original_id': entry.get('id')
            }
        )
    
    print(f"Migrated {len(data.get('memories', []))} entries")
```

---

## Best Practices

### 1. Use Descriptive Types

```python
# Good
memory.create(memory_type="research_thread", ...)
memory.create(memory_type="verified_fact", ...)
memory.create(memory_type="code_pattern", ...)

# Avoid generic types
memory.create(memory_type="note", ...)  # Too vague
```

### 2. Tag Liberally

```python
tags=["attention", "transformer", "scaling-law", "active-research"]
```

### 3. Link Related Memories

Don't duplicate information—link instead:

```python
# Instead of copying content
researcher.link_memories(thread_id, source_id)
```

### 4. Keep Files Focused

One concept per file. If a file grows beyond ~500 lines, consider splitting.

### 5. Commit Frequently

Commit after each agent session for easy rollback and audit trail.

---

## Troubleshooting

### "Permission Denied"

Check `memory/permissions/agent_permissions.yaml` for restrictions.

### "Link Cannot Be Resolved"

Ensure the target memory exists and hasn't been archived.

### "Version Conflict"

Another agent modified the file. Re-read and merge changes.

### "Lock Timeout"

A previous operation didn't release its lock. Delete the `.lock` file manually.

---

## Next Steps

1. **Read the full architecture**: See `INBAND_MEMORY_ARCHITECTURE.md`
2. **Set up permissions**: Configure `memory/permissions/agent_permissions.yaml`
3. **Initialize git**: `cd memory && git init`
4. **Create your first memories**: Start with agent-specific contexts
5. **Enable dreaming**: Run periodic consolidation cycles
