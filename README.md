# Local AI Research & Study Agent

A production-grade, self-improving AI agent that runs entirely on your local machine. Built as a research and study companion with multiagent orchestration, persistent memory, and autonomous self-improvement through batch consolidation ("dreaming").

**100% Local • Zero API Costs • RTX 4060 Optimized • Production-Ready**

---

##  What This Is

This is a local AI agent system inspired by Anthropic's Claude Code architecture, but built from scratch to run entirely on consumer hardware. It combines:

- **Multiagent Orchestration** - Coordinator routes tasks to specialist agents (Researcher, Tutor, Coder, Dreamer)
- **Persistent Memory** - File-based memory with versioning and rollback
- **Self-Improvement** - Batch "dreaming" process consolidates session transcripts into organized knowledge
- **Hook System** - Lifecycle events for security, automation, and extensibility
- **Progressive Disclosure** - Skills load metadata → instructions → resources on demand
- **GitHub Integration** - Clone, read, commit, and create pull requests

All running on a single RTX 4060 8GB GPU with Qwen2.5-7B, zero external APIs, and zero cost.

---

## ✨ Features

### Core Capabilities
- **Research Agent** - Web search via DuckDuckGo, PDF reading, document summarization
- **Tutor Agent** - Concept explanations, quiz generation, learning adaptation
- **Coder Agent** - GitHub operations, code analysis, PR creation
- **Dreamer Agent** - Batch memory consolidation and self-improvement
- **Memory System** - Persistent, versioned, file-based memory with rollback
- **Hook System** - Event-driven lifecycle hooks for security and automation
- **Skill System** - Modular capabilities with progressive disclosure
- **Context Compaction** - Automatic conversation summarization to stay within context limits

### Production Features
- **Tool Scoping** - Each agent only accesses tools it needs
- **Turn Limiting** - Prevents infinite loops
- **Atomic File Operations** - Safe concurrent writes with locking
- **Environment Persistence** - Virtual environments persist across Bash calls
- **Two-Strike Rule** - Blocks repeated identical tool calls
- **Git Versioning** - Full audit trail of memory changes

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────
│                      CLI (Typer + Rich)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Coordinator Agent                         │
│  - Intent classification & routing                          │
│  - Context management & compaction                          │
│  - Safety limits & hook dispatching                         │
└─┬──────────┬──────────┬──────────┬──────────────────────────┘
  │          │          │          │
  ▼          ▼          ▼          ▼
┌────────┐┌────────┌────────┐┌────────
│Research││ Tutor  ││Memory  ││Dreamer │
│ Agent  ││ Agent  ││ Agent  ││ Agent  │
│        ││        ││        ││        │
│Scoped  ││Scoped  ││Scoped  ││Scoped  │
│Tools   ││Tools   ││Tools   ││Tools   │
└────────┘└────────┘└────────┘└────────
     │          │          │          │
     └──────────┴──────────┴──────────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    ┌────▼────   ┌─────▼─────┐  ┌────▼────┐
    │ Memory  │   │  Skills   │  │Sessions │
    │ System  │   │ Directory │  │(Trans-  │
    │         │   │           │  │ scripts)│
    │-memory.md│  │-SKILL.md  │  │         │
    │-versions│  │-scripts/  │  │         │
    │-dreams  │  │-reference/│  │         │
    └─────────┘   └───────────┘  └─────────┘
```

---

## 📦 Installation

### Prerequisites
- **OS:** Ubuntu 20.04+ (or similar Linux)
- **GPU:** RTX 4060 8GB VRAM (or equivalent)
- **RAM:** 16GB minimum
- **Python:** 3.10+

### 1. Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
```

### 2. Install System Dependencies
```bash
sudo apt update
sudo apt install git gh
gh auth login  # For GitHub operations (optional)
```

### 3. Clone and Setup
```bash
git clone <your-repo-url>
cd local-ai-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Initialize Git for Versioning
```bash
git init
git add .
git commit -m "Initial commit"
```

---

## 🚀 Usage

### The TUI (main interface)

The agent is driven entirely through a single **opencode-style terminal UI**.
Launch it with no arguments:

```bash
python agent.py          # or: python -m harness.tui
```

You get a streaming chat interface that routes each message to the right
specialist agent (researcher / tutor / coder / dreamer), shows tool calls
inline, and keeps a live status line. Inside the TUI, slash commands manage
everything:

| Command | Action |
| :-- | :-- |
| `/help` | List all commands |
| `/memory` | View long-term memory |
| `/agents` | Show specialist agents and their scoped tools |
| `/tools` | List available tools |
| `/status` | System status (model, backend, turns) |
| `/model [name]` | Show or switch the active Ollama model |
| `/dream [n]` | Consolidate the last *n* sessions into memory |
| `/clear` | Reset the conversation |
| `/quit` | Exit |

> **No Ollama? No problem.** If the Ollama daemon isn't reachable the TUI runs
> in **offline mock mode** so the interface stays fully usable. Start Ollama and
> `ollama pull qwen3:8b` for real answers.

### Scripted commands

The same engine is available non-interactively for scripting/automation:

### Basic Commands

```bash
# Ask the agent anything
agent ask "Research the latest developments in transformer architectures"

# Run a study session
agent ask "Explain how attention mechanisms work in transformers"

# Quiz yourself
agent ask "Quiz me on neural network optimization"

# Clone a repository
agent clone https://github.com/fastapi/fastapi

# Analyze code
agent ask "Analyze the code structure in workspace/fastapi"
```

### Memory & Dreaming

```bash
# View current memory
agent memory

# List memory versions
agent versions

# Run dreaming process (batch consolidation)
agent dream --sessions 5

# Activate a dream output
agent activate dreams/dream_20260625_160000_output.md

# Rollback to previous memory state
agent rollback v_20260625_140000.md
```

### Skills & Tools

```bash
# List available skills
agent skills list

# Show skill details
agent skills show research-web

# Run a skill script directly
agent skills run research-web search.py "AI agents" --max-results 3
```

### Session Management

```bash
# List recent sessions
agent sessions --last 10

# Show agent status
agent status

# List active agent threads
agent threads
```

---

## 📁 Project Structure

```
local-ai-agent/
├── agent.py                      # CLI entry point (Typer)
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── .agent_env.sh                 # Persistent bash environment state
├── memory.md                     # Active memory store
│
├── harness/                      # Core agent logic
│   ├── __init__.py
│   ├── llm_client.py             # Ollama wrapper & JSON repair
│   ├── token_counter.py          # VRAM safety mechanism
│   ├── file_ops.py               # Atomic file writes & locking
│   ├── hooks.py                  # Lifecycle event dispatcher
│   ├── memory.py                 # In-band memory operations
│   ├── dreaming.py               # Out-of-band batch consolidation
│   ├── versioning.py             # Git-based audit trail
│   ├── coordinator.py            # Intent routing, streaming & orchestration
│   ├── agents.py                 # Specialist agent definitions
│   ├── agent_base.py             # Shared agent contract
│   ├── threads.py                # Isolated context windows
│   ├── inband_memory.py          # Neural Markdown Mesh store
│   ├── tools.py                  # Free tool implementations
│   └── tui.py                    # The TUI (single user interface)
│
├── skills/                       # Agent capabilities
│   ├── research-web/
│   │   ├── SKILL.md
│   │   ├── reference/
│   │   │   └── search-tips.md
│   │   └── scripts/
│   │       └── search.py
│   ├── study-companion/
│   │   ├── SKILL.md
│   │   ├── reference/
│   │   │   ├── learning-styles.md
│   │   │   └── quiz-templates.md
│   │   └── scripts/
│   │       └── generate_quiz.py
│   ├── code-analysis/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── analyze_structure.py
│   └── memory-management/
│       ├── SKILL.md
│       └── reference/
│           └── consolidation-rules.md
│
── sessions/                     # Raw session transcripts
── versions/                     # Immutable memory snapshots
├── dreams/                       # Pending dream outputs
└── workspace/                    # Cloned Git repositories
```

---

## 🎓 Demo Scenarios

### Scenario 1: Research & Self-Improvement

```bash
# Morning: Research a topic
agent ask "Research quantum computing basics"

# Afternoon: Ask follow-up questions
agent ask "What are the different types of qubits?"
agent ask "How does quantum entanglement work?"

# Evening: Consolidate learning
agent dream --sessions 3

# Next day: Agent is smarter
agent ask "Quiz me on quantum computing"
# Agent uses consolidated memory to generate better questions
```

### Scenario 2: Code Analysis & PR Creation

```bash
# Clone a repository
agent clone https://github.com/fastapi/fastapi

# Analyze code
agent ask "Analyze the authentication flow in workspace/fastapi"

# Make improvements
agent ask "Improve error handling in workspace/fastapi/src/fastapi/security.py"

# Create a pull request
agent pr workspace/fastapi src/fastapi/security.py "Improved error handling" fix/error-handling "Better error messages"
```

### Scenario 3: Study Companion

```bash
# Learn a concept
agent ask "Explain backpropagation in neural networks"

# Get an analogy
agent ask "Give me an analogy for how gradient descent works"

# Test your knowledge
agent ask "Quiz me on backpropagation"

# Agent adapts to your level
agent ask "I didn't understand the chain rule part. Explain again."
# Next time, agent remembers your weak spots
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` file (optional):

```bash
# Ollama settings
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
OLLAMA_NUM_CTX=8192            # context window (must be set; Ollama defaults to ~2048)

# Ollama Cloud (optional, opt-in — see below)
OLLAMA_API_KEY=               # your Ollama API key for cloud inference

# Tool limits
MAX_TOOL_CHARS=4000
MAX_TURNS=20
CONTEXT_COMPACT_THRESHOLD=24000

# GitHub (optional)
GITHUB_TOKEN=ghp_your_token_here
```

### Choosing a model

menace works with **any** model available to your Ollama host. Set one at launch
(`OLLAMA_MODEL=…`) or switch live in the TUI:

```
/model                       # show current + locally installed models
/model qwen3:4b              # switch to any local model (pull it first)
```

### Ollama Cloud (faster, larger models — opt-in)

For more speed/quality than an 8GB GPU allows, run a hosted model on **Ollama
Cloud** instead of degrading the local experience. This is **opt-in** and changes
the project's "fully local / private" property: prompts are sent to Ollama's
servers, and cloud usage requires an Ollama account (free tier with limits).

```bash
ollama signin                       # or: export OLLAMA_API_KEY=<your key>
```

Then pick a cloud model (conventionally suffixed `-cloud`):

```
/model qwen3-coder:480b-cloud
```

The status line shows **cloud** vs **local** so you always know where inference
runs. Local stays the default; nothing is sent anywhere until you choose a cloud
model or set an API key.

### Hook Configuration

Create `hooks.json` for custom lifecycle hooks:

```json
{
  "PreToolUse": [
    {
      "matcher": "Bash",
      "hooks": [
        {
          "type": "command",
          "command": "python scripts/block_dangerous_commands.py",
          "timeout": 5
        }
      ]
    }
  ],
  "PostToolUse": [
    {
      "matcher": "Write",
      "hooks": [
        {
          "type": "command",
          "command": "python scripts/auto_lint.py",
          "timeout": 15
        }
      ]
    }
  ]
}
```

---

##  Development

### Running Tests

```bash
pytest tests/
```

### Debug Mode

```bash
agent ask "test query" --debug
```

### Adding New Skills

1. Create directory: `skills/my-skill/`
2. Add `SKILL.md` with YAML frontmatter
3. Add scripts to `skills/my-skill/scripts/`
4. Add references to `skills/my-skill/reference/`

Example `SKILL.md`:

```yaml
---
name: my-skill
description: Description of what this skill does and when to use it
---

# My Skill

## Instructions
Step-by-step guidance...

## Scripts
**script.py**: Description

```bash
python scripts/script.py arg1 arg2
```
```

---

## 📊 Performance

### Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU VRAM | 8GB | 12GB+ |
| RAM | 16GB | 32GB |
| Storage | 10GB | 20GB |

### Inference Speed

- **Model:** Qwen2.5-7B (Q4_K_M quantization)
- **Tokens/sec:** ~30-50 tokens/sec on RTX 4060
- **Context Window:** 32K tokens (compaction at 24K)

### Memory Usage

- **Base System:** ~2GB RAM
- **Ollama Model:** ~5GB VRAM
- **Peak Usage:** ~8GB VRAM during dreaming

---

## 🔒 Security

### Built-in Safeguards

- **Tool Scoping** - Agents only access permitted tools
- **Hook Validation** - PreToolUse hooks can block dangerous commands
- **Turn Limiting** - Prevents infinite loops
- **File Locking** - Atomic writes prevent corruption
- **Environment Isolation** - Bash commands run in controlled environment

### Best Practices

1. **Review hooks** before enabling them
2. **Use read-only memory** for shared reference material
3. **Limit agent permissions** to minimum required
4. **Monitor dreaming output** before activating
5. **Keep backups** in `versions/` directory

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for all public methods
- Keep functions under 50 lines

---

##  License

MIT License - see LICENSE file for details

---

## 🙏 Acknowledgments

This project is inspired by:
- Anthropic's Claude Code architecture
- LangChain/LlamaIndex concepts (but implemented from scratch)
- The local AI community

---

## 📧 Contact

For questions or issues, please open an issue on GitHub.

---

**Built with ❤️ for the local AI community**