# Agent Soul Architecture & Skill System

## Overview

This document describes the **Agent Soul** (`agent.md`) architecture and the **Skill System** that powers the agentic harness. These components define agent identity, capabilities, and operational patterns using markdown-based in-band memory.

---

## 1. Agent Soul (`agent.md`)

### What is the Agent Soul?

The `agent.md` file is the **core identity document** for each agent. It defines:
- Core identity and personality
- Operating principles and values
- Forbidden actions (hard constraints)
- Expertise domains
- Decision-making frameworks
- Self-improvement protocols

### Location Structure

```
memory/
└── agents/
    ├── coder/
    │   └── agent.md          # Coder's soul
    ├── researcher/
    │   └── agent.md          # Researcher's soul
    ├── tutor/
    │   └── agent.md          # Tutor's soul
    └── _shared/              # Shared resources
        ├── skills/
        ├── facts/
        └── archive/
```

### Agent Soul Schema

```markdown
---
id: agent_soul_<agent_name>
type: agent_soul
agent: <agent_name>
version: <integer>
created: 'YYYY-MM-DD'
updated: 'YYYY-MM-DD'
tags:
- identity
- core
- <agent_type>
---

# <Agent Name> Agent Soul

## Core Identity
[Description of who the agent is and primary drive]

## Operating Principles
[Numbered list of guiding principles with subsections]

## Forbidden Actions
[Never-ever list - hard constraints]

## Expertise Domains
[List of skill areas and proficiency levels]

## Decision Framework
[Step-by-step decision process for typical tasks]

## Memory Integration
[How this agent uses wikilinks to connect to skills/facts]

## Self-Improvement
[Post-session reflection protocol]
```

### Example: Coder Agent Soul

The Coder agent's soul defines it as a "pragmatic software engineer" with principles around code quality, systematic approaches, and tool mastery. Key sections include:

- **Forbidden Actions**: Never modify files without confirmation, never commit without review
- **Decision Framework**: Understand → Explore → Plan → Execute → Review
- **Memory Integration**: Links to `[[skill_*]]` nodes for patterns, `[[fact_*]]` for insights

---

## 2. Skill System

### What are Skills?

Skills are **reusable capability documents** that define:
- Purpose and capability statements
- Input/output schemas
- Safety protocols
- Error handling procedures
- Examples and best practices
- Related skills via wikilinks

### Skill Categories

#### Tool Use Skills
Execute specific tools with safety and best practices:
- `skill_bash_execution.md` - Shell command execution
- `skill_file_operations.md` - Atomic file I/O
- `skill_git_workflow.md` - Version control operations

#### Cognitive Skills
Mental operations and reasoning patterns:
- `skill_summarization.md` - Condensing information
- `skill_analysis.md` - Breaking down complex topics
- `skill_synthesis.md` - Combining information sources

#### Domain Skills
Specialized knowledge areas:
- `skill_python_patterns.md` - Python coding patterns
- `skill_research_methods.md` - Information gathering techniques
- `skill_teaching_strategies.md` - Pedagogical approaches

### Skill Schema

```markdown
---
id: skill_<skill_name>
type: skill
category: <tool_use|cognitive|domain>
version: <integer>
created: 'YYYY-MM-DD'
updated: 'YYYY-MM-DD'
tags:
- <tag1>
- <tag2>
agents:
- <agent1>
- <agent2>
prerequisites:
- skill_<prereq_skill>
---

# Skill: <Human Readable Name>

## Purpose
[One sentence describing what this skill does]

## Capability Statement
[Paragraph describing expertise and approach]

## Usage Pattern
### Input Format
[YAML schema for inputs]

### Output Structure
[YAML schema for outputs]

## Safety Protocols
[Safety checks, validation rules, forbidden operations]

## Error Handling
[Common failure modes and recovery strategies]

## Examples
[Concrete examples with input/output]

## Related Skills
[Wikilinks to complementary skills]

## Memory Integration
[Which fact nodes to update, what to archive]

## Improvement Notes
[Version history and changes]
```

---

## 3. Facts System

### What are Facts?

Facts are **verified information nodes** that store:
- Core knowledge and guidelines
- Configuration constants
- Best practices and patterns
- Historical learnings

### Fact Schema

```markdown
---
id: fact_<fact_name>
type: fact
category: <context|safety|configuration|domain_knowledge>
version: <integer>
created: 'YYYY-MM-DD'
updated: 'YYYY-MM-DD'
tags:
- <tag1>
- <tag2>
---

# Fact: <Human Readable Title>

## Core Information
[Bullet points of key facts]

## Best Practices
[Numbered or bulleted guidelines]

## Related Skills
[Wikilinks to skills that use this fact]

## Notes
[Additional context, caveats, or references]
```

### Example Facts

- `fact_llm_context.md` - Context window management guidelines
- `fact_tool_safety_protocols.md` - Critical safety rules
- `fact_project_layout.md` - Project-specific directory structure

---

## 4. Wikilink Navigation

### Link Syntax

```markdown
[[node_id]]           # Link to node by ID
[[node_id|Text]]      # Link with custom text
[[skill_bash_execution]]  # Example: link to bash skill
```

### Link Resolution

The in-band memory system automatically:
1. Parses all `[[wikilinks]]` from content
2. Resolves links to actual file paths
3. Tracks backlinks (which nodes link TO this node)
4. Enables graph traversal for related content

### Graph Traversal Example

```python
from harness.inband_memory import InBandMemory

memory = InBandMemory(agent_id="coder")

# Get all links from a node
links = memory.get_links("agent_soul_coder")
# Returns: ['skill_bash_execution', 'skill_file_operations', ...]

# Traverse to linked nodes
for link in links:
    node = memory.get(link)
    print(node.content[:100])

# Get backlinks (who links TO this node)
backlinks = memory.get_backlinks("skill_bash_execution")
# Returns: ['agent_soul_coder', 'agent_soul_researcher']
```

---

## 5. Agent-Skill Integration

### How Agents Use Skills

1. **Startup**: Agent loads its `agent.md` soul document
2. **Capability Discovery**: Parse wikilinks to find available skills
3. **Skill Loading**: Load full skill documents when needed
4. **Execution**: Follow skill protocols for tool use
5. **Learning**: Update facts and archive results

### Skill Selection Logic

When faced with a task:
1. Check soul's `Expertise Domains` for relevance
2. Look at `Decision Framework` for approach
3. Find matching `skill_*` nodes via wikilinks
4. Execute skill's `Usage Pattern`
5. Apply `Safety Protocols` before action
6. Handle errors per `Error Handling` section

### Example Flow: Coder Executing Bash

```
Task: "Run tests and commit the changes"

1. Load agent_soul_coder → See "Tool Mastery" principle
2. Find [[skill_bash_execution]] link
3. Load skill_bash_execution.md
4. Check Safety Protocols → Validate command
5. Execute with timeout, capture output
6. If success, find [[skill_git_workflow]]
7. Stage, review diff, commit per protocol
8. Archive session results
```

---

## 6. Memory Directory Structure

```
memory/
├── agents/
│   ├── _shared/              # Cross-agent resources
│   │   ├── index.md          # Navigation index
│   │   ├── skills/           # Shared skills
│   │   │   ├── skill_bash_execution.md
│   │   │   ├── skill_file_operations.md
│   │   │   └── skill_git_workflow.md
│   │   ├── facts/            # Shared facts
│   │   │   ├── fact_llm_context.md
│   │   │   └── fact_tool_safety_protocols.md
│   │   └── archive/          # Historical records
│   │
│   ├── coder/                # Coder agent namespace
│   │   ├── agent.md          # Soul document
│   │   ├── skills/           # Coder-specific skills
│   │   ├── facts/            # Coder-specific facts
│   │   ├── episodes/         # Session transcripts
│   │   └── archive/          # Coder's completed work
│   │
│   ├── researcher/           # Researcher agent namespace
│   │   ├── agent.md
│   │   ├── research_threads/ # Active investigations
│   │   └── ...
│   │
│   └── tutor/                # Tutor agent namespace
│       ├── agent.md
│       └── ...
│
└── _index.md                 # Global memory index (auto-generated)
```

---

## 7. Creating New Agents

### Step 1: Create Agent Directory

```bash
mkdir -p memory/agents/<agent_name>/{skills,facts,episodes,archive}
```

### Step 2: Write Agent Soul

Create `memory/agents/<agent_name>/agent.md` following the soul schema.

### Step 3: Define Specialized Skills

Add agent-specific skills to `memory/agents/<agent_name>/skills/`.

### Step 4: Link to Shared Resources

Use wikilinks in the soul document to reference shared skills:
```markdown
## Memory Integration
- Use [[skill_bash_execution]] for shell commands
- Reference [[fact_tool_safety_protocols]] for safety rules
```

### Step 5: Test Agent Initialization

```python
from harness.inband_memory import InBandMemory

agent = InBandMemory(agent_id="<agent_name>")
soul = agent.get("agent_soul_<agent_name>")
print(soul.content)
```

---

## 8. Best Practices

### For Agent Souls
- Keep identity statements clear and actionable
- Define forbidden actions explicitly (never ambiguous)
- Include concrete decision frameworks
- Link to relevant skills and facts

### For Skills
- Always include input/output schemas
- Document safety protocols thoroughly
- Provide multiple worked examples
- Link to related skills bidirectionally

### For Facts
- Keep facts atomic (one concept per file)
- Version facts when they change
- Link facts to skills that use them
- Archive outdated facts, don't delete

### For Wikilinks
- Use consistent naming: `type_description`
- Link liberally to build knowledge graph
- Update links when nodes are renamed
- Use the index files for navigation

---

## 9. Comparison to Claude Code

| Feature | Claude Code | Our Implementation |
|---------|-------------|-------------------|
| Identity | System prompt | `agent.md` soul document |
| Skills | Hardcoded | Markdown skill documents |
| Memory | Vector DB | In-band markdown with wikilinks |
| Versioning | Opaque | Git-native, human-readable |
| Extensibility | Limited | Add new `.md` files |
| Debugging | Black box | Inspect any file directly |
| Portability | Proprietary | Pure markdown + Python |

### Advantages of Our Approach
1. **Human-readable**: Edit skills with any text editor
2. **Git-friendly**: Full version history, branching, merging
3. **Inspectable**: No black boxes, see exactly how agents work
4. **Extensible**: Add new skills by creating `.md` files
5. **Portable**: Works offline, no API dependencies
6. **Composable**: Wikilinks create rich knowledge graphs

---

## 10. Next Steps

### Immediate Tasks
- [ ] Create more specialized skills (summarization, analysis)
- [ ] Build skill loader to inject skills into agent prompts
- [ ] Implement automatic index generation
- [ ] Add backlink visualization

### Future Enhancements
- [ ] Skill discovery via LLM ("what skill do I need?")
- [ ] Automatic skill improvement suggestions
- [ ] Cross-agent skill sharing protocols
- [ ] Skill performance metrics and ranking

---

## References

- [[INBAND_MEMORY_ARCHITECTURE.md]] - Overall memory system design
- [[INBAND_MEMORY_QUICKSTART.md]] - Quick start guide
- [[specs/master_spec.md]] - Full system specification
