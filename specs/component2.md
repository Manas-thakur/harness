# 📋 Component Specification 2: The Hook System & Event Dispatcher

This component is the **nervous system** of your agent. While the Coordinator is the "brain" deciding what to do, the Hook System is the autonomous reflex arc that enforces rules, automates repetitive tasks, and injects context without the main LLM needing to be explicitly prompted. 

By implementing this, you prove to the interviewer that you understand **event-driven architecture, security guardrails, and extensible plugin systems**—exactly how production agents like Claude Code operate.

---

### **File Location**
`harness/hooks.py` (Core logic) and `.claude/hooks/` or `hooks/` (Executable scripts).

### **Responsibilities**
1.  **Lifecycle Event Dispatching:** Fire events at exact moments (`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, `SessionEnd`).
2.  **Script Execution & I/O:** Pass JSON context to external scripts via `stdin`, and parse structured JSON decisions or exit codes from `stdout`.
3.  **Decision Enforcement:** Block dangerous tool calls, inject `additionalContext` into the LLM, or halt the agent loop based on hook outputs.
4.  **Environment Persistence:** Manage the `.agent_env.sh` file (equivalent to Anthropic's `CLAUDE_ENV_FILE`) so environment variables persist across isolated Bash tool calls.

---

### **Class Structure & Methods**

```python
import subprocess
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

class EnvironmentManager:
    """
    Manages persistent environment variables across Bash tool calls.
    Equivalent to Anthropic's CLAUDE_ENV_FILE.
    """
    def __init__(self, env_file: str = ".agent_env.sh"):
        self.env_file = Path(env_file)
        if not self.env_file.exists():
            self.env_file.write_text("# Agent persistent environment\n")

    def get_source_command(self) -> str:
        """Returns the bash command to source the env file."""
        return f"source {self.env_file.absolute()}"

    def update_env(self, key: str, value: str):
        """Appends an export statement to the env file."""
        with open(self.env_file, "a") as f:
            f.write(f'export {key}="{value}"\n')

class HookDispatcher:
    """
    Fires lifecycle events, executes hook scripts, and enforces decisions.
    """
    def __init__(self, hooks_config_path: str = "hooks.json"):
        self.hooks_config = self._load_config(hooks_config_path)
        self.env_manager = EnvironmentManager()

    def _load_config(self, path: str) -> Dict:
        """Loads hook definitions from a JSON file."""
        if Path(path).exists():
            with open(path, "r") as f:
                return json.load(f)
        return {}

    def fire(self, event_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fires a specific event. 
        Returns a dictionary containing the final decision and any injected context.
        """
        event_hooks = self.hooks_config.get(event_name, [])
        final_decision = {"blocked": False, "additional_context": ""}

        for hook_group in event_hooks:
            matcher = hook_group.get("matcher", "")
            
            # 1. Evaluate Matcher (e.g., does this hook apply to the current tool?)
            if matcher and not self._evaluate_matcher(matcher, context):
                continue

            # 2. Execute all handlers in this group
            for handler in hook_group.get("hooks", []):
                result = self._execute_handler(handler, event_name, context)
                
                # 3. Process the result (Exit codes and JSON output)
                if result.get("blocked"):
                    final_decision["blocked"] = True
                    final_decision["reason"] = result.get("reason", "Blocked by hook")
                    return final_decision # Stop immediately if blocked
                
                if result.get("additional_context"):
                    final_decision["additional_context"] += result["additional_context"] + "\n"

        return final_decision

    def _evaluate_matcher(self, matcher: str, context: Dict) -> bool:
        """
        Checks if the hook should fire based on the matcher.
        E.g., matcher="Bash" matches context={"tool_name": "Bash"}
        """
        if matcher == "*":
            return True
        # Simple exact match for tool names (e.g., "Bash", "Write")
        if "tool_name" in context:
            return context["tool_name"] == matcher
        return True

    def _execute_handler(self, handler: Dict, event_name: str, context: Dict) -> Dict:
        """Executes a single command hook and parses its output."""
        if handler.get("type") != "command":
            return {} # We only support command hooks for local zero-budget

        command = handler.get("command")
        timeout = handler.get("timeout", 30)
        
        # Inject environment manager path into context so hooks can persist vars
        context["env_file"] = str(self.env_manager.env_file.absolute())
        
        try:
            # Pass context as JSON via stdin
            process = subprocess.run(
                command,
                shell=True,
                input=json.dumps(context),
                capture_output=True,
                text=True,
                timeout=timeout,
                executable="/bin/bash"
            )
            
            return self._parse_hook_output(process, event_name)
            
        except subprocess.TimeoutExpired:
            return {"blocked": False, "error": f"Hook timed out after {timeout}s"}
        except Exception as e:
            return {"blocked": False, "error": str(e)}

    def _parse_hook_output(self, process: subprocess.CompletedProcess, event_name: str) -> Dict:
        """
        Parses the hook's stdout and exit code.
        Exit 0 + JSON = Structured decision.
        Exit 2 = Hard block (stderr is the reason).
        """
        result = {"blocked": False}
        
        # EXIT CODE 2: Hard Block
        if process.returncode == 2:
            result["blocked"] = True
            result["reason"] = process.stderr.strip() or "Blocked by hook (Exit 2)"
            return result

        # EXIT CODE 0: Parse JSON for structured decisions
        if process.returncode == 0 and process.stdout.strip():
            try:
                output_json = json.loads(process.stdout)
                
                # Check for top-level block (used by UserPromptSubmit, Stop, etc.)
                if output_json.get("decision") == "block":
                    result["blocked"] = True
                    result["reason"] = output_json.get("reason", "Blocked by hook")
                    return result

                # Check for tool-specific decisions (PreToolUse)
                hook_specific = output_json.get("hookSpecificOutput", {})
                if hook_specific.get("hookEventName") == event_name:
                    if hook_specific.get("permissionDecision") == "deny":
                        result["blocked"] = True
                        result["reason"] = hook_specific.get("permissionDecisionReason", "Denied by hook")
                        return result
                    
                    # Inject context for the LLM
                    if "additionalContext" in hook_specific:
                        result["additional_context"] = hook_specific["additionalContext"]

            except json.JSONDecodeError:
                # If it's not JSON, treat stdout as plain additional context
                result["additional_context"] = process.stdout.strip()

        return result
```

---

### **Key Design Decisions for RTX 4060 (8GB VRAM)**

*   **Zero LLM Overhead for Hooks:** Unlike Anthropic's `type: "prompt"` or `type: "agent"` hooks which consume API tokens, our local implementation strictly uses `type: "command"` (Python/Bash scripts). This ensures hooks execute in milliseconds without waking up the 7B model, saving precious VRAM and latency.
*   **Strict Timeouts:** Local models are slow. If a hook hangs, the whole agent hangs. Every hook has a strict `timeout` (default 30s). 
*   **Environment Persistence:** The `EnvironmentManager` is critical. When the agent runs `source .venv/bin/activate` in a Bash tool, the `EnvironmentManager` catches that export and writes it to `.agent_env.sh`. The next Bash tool call automatically sources it, so the virtual environment stays active across isolated tool calls.

---

### **Configuration Schema (`hooks.json`)**

To prove you understand Anthropic's configuration paradigm, your agent will read this exact JSON structure:

```json
{
  "SessionStart": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python scripts/load_context.py",
          "timeout": 10
        }
      ]
    }
  ],
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

### **Example Hook Scripts (The "Muscle")**

#### **1. Security Guardrail (`scripts/block_dangerous_commands.py`)**
This script fires on `PreToolUse` for the `Bash` tool. It reads the JSON from `stdin` and blocks destructive commands.

```python
#!/usr/bin/env python3
import sys
import json

# Read context from stdin
context = json.load(sys.stdin)
command = context.get("tool_input", {}).get("command", "")

# Check for dangerous patterns
if "rm -rf /" in command or "mkfs" in command:
    # EXIT CODE 2 = Hard Block. Stderr is shown to the LLM as the error.
    print("Destructive command blocked by security hook.", file=sys.stderr)
    sys.exit(2)

# EXIT CODE 0 = Allow. We can also inject JSON to give the LLM more context.
output = {
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": "Note: You are running in a sandboxed Ubuntu environment. Use 'python3' instead of 'python'."
    }
}
print(json.dumps(output))
sys.exit(0)
```

#### **2. Context Injector (`scripts/load_context.py`)**
This script fires on `SessionStart`. It reads the current git branch and injects it into the LLM's context so the agent knows where it is.

```python
#!/usr/bin/env python3
import subprocess
import json

# Get current git branch
try:
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
except:
    branch = "unknown"

# Plain stdout is automatically added to context for SessionStart hooks
print(f"Current Git Branch: {branch}. The user is working locally on an RTX 4060 Ubuntu machine.")
```

---

### **Integration Points**

1.  **In the Coordinator (`harness/coordinator.py`)**:
    *   Before processing the user's prompt, the Coordinator calls: 
        `hook_result = self.hooks.fire("UserPromptSubmit", {"prompt": user_prompt})`
    *   If `hook_result["blocked"]` is True, the Coordinator aborts and shows the `reason` to the user.
    *   If `hook_result["additional_context"]` exists, it is prepended to the system prompt.

2.  **In the Tool Registry (`harness/tools.py`)**:
    *   Before executing *any* tool (Bash, Read, Write), the tool wrapper calls:
        `hook_result = self.hooks.fire("PreToolUse", {"tool_name": "Bash", "tool_input": tool_args})`
    *   If blocked, the tool returns the `reason` as a tool error to the LLM, preventing the actual execution.
    *   After successful execution, it fires `PostToolUse` to allow hooks to run linters, tests, or format code.

3.  **In the Bash Tool (`harness/tools_bash.py`)**:
    *   The Bash tool *must* prepend the environment manager's source command to every execution:
        `full_command = f"{self.hooks.env_manager.get_source_command()} && {user_command}"`

---

### **Why This Wins the Interview**

✅ **Exact Parity with Industry Standards:** You aren't just writing `if "rm" in command:` in your main loop. You've built an extensible, event-driven middleware layer exactly like Anthropic's.
✅ **Security by Design:** You demonstrate that you understand agents shouldn't be trusted blindly. The `PreToolUse` hook is the industry-standard way to sandbox agents.
✅ **State Management:** Implementing the `CLAUDE_ENV_FILE` equivalent (`.agent_env.sh`) solves a massive pain point in local agents (losing virtual environments between Bash calls) and shows deep systems-level thinking.
✅ **Zero-Cost Extensibility:** By using Python scripts for hooks instead of LLM calls, you add powerful automation (linting, testing, security) without consuming your RTX 4060's limited VRAM or context window.

---

**Ready for Component 3?** 
Component 3 will cover **The Memory Store & Dreaming Engine**, detailing exactly how we implement the file-based memory, the batch consolidation process, and the Git-based versioning to create the "self-improving" aspect of the agent. Just say the word!