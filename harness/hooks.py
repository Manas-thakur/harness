"""
Hook System for Lifecycle Event Dispatching
Mirrors Anthropic's hook architecture for security, automation, and extensibility.
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, Any


class EnvironmentManager:
    """
    Manages persistent environment variables across Bash tool calls.
    Equivalent to Anthropic's CLAUDE_ENV_FILE.
    """

    def __init__(self, env_file: str = ".agent_env.sh"):
        """
        Initialize environment manager.
        
        Args:
            env_file: Path to environment file
        """
        self.env_file = Path(env_file)
        if not self.env_file.exists():
            self.env_file.write_text("# Agent persistent environment\n")

    def get_source_command(self) -> str:
        """Returns the bash command to source the env file."""
        return f"source {self.env_file.absolute()}"

    def update_env(self, key: str, value: str):
        """
        Appends an export statement to the env file.
        
        Args:
            key: Environment variable name
            value: Environment variable value
        """
        with open(self.env_file, "a") as f:
            f.write(f'export {key}="{value}"\n')

    def clear_env(self):
        """Clear all environment variables (keep the file)."""
        self.env_file.write_text("# Agent persistent environment\n")


class HookDispatcher:
    """
    Fires lifecycle events, executes hook scripts, and enforces decisions.
    Mirrors Anthropic's hook event system.
    """

    # Supported hook events
    EVENTS = [
        "SessionStart",
        "UserPromptSubmit", 
        "PreToolUse",
        "PostToolUse",
        "Stop",
        "SessionEnd"
    ]

    def __init__(self, hooks_config_path: str = "hooks.json"):
        """
        Initialize hook dispatcher.
        
        Args:
            hooks_config_path: Path to hooks configuration JSON file
        """
        self.hooks_config = self._load_config(hooks_config_path)
        self.env_manager = EnvironmentManager()

    def _load_config(self, path: str) -> Dict:
        """
        Load hook definitions from a JSON file.
        
        Args:
            path: Path to hooks.json
            
        Returns:
            Hook configuration dictionary
        """
        config_path = Path(path)
        if config_path.exists():
            with open(config_path, "r") as f:
                return json.load(f)
        return {}

    def fire(self, event_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fire a specific event and execute associated hooks.
        
        Args:
            event_name: Name of the event (e.g., "PreToolUse")
            context: Context data to pass to hooks
            
        Returns:
            Dictionary containing final decision and any injected context
        """
        if event_name not in self.EVENTS:
            return {"blocked": False, "error": f"Unknown event: {event_name}"}

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
                    return final_decision  # Stop immediately if blocked

                if result.get("additional_context"):
                    final_decision["additional_context"] += result["additional_context"] + "\n"

                if result.get("error"):
                    final_decision["hook_error"] = result["error"]

        return final_decision

    def _evaluate_matcher(self, matcher: str, context: Dict) -> bool:
        """
        Check if the hook should fire based on the matcher.
        
        Args:
            matcher: Matcher string (e.g., "Bash", "*")
            context: Event context
            
        Returns:
            True if hook should fire
        """
        if matcher == "*":
            return True

        # Simple exact match for tool names (e.g., "Bash", "Write")
        if "tool_name" in context:
            return context["tool_name"] == matcher

        return True

    def _execute_handler(
        self, 
        handler: Dict, 
        event_name: str, 
        context: Dict
    ) -> Dict:
        """
        Execute a single command hook and parse its output.
        
        Args:
            handler: Handler configuration dict
            event_name: Current event name
            context: Event context
            
        Returns:
            Result dictionary with blocked status and context
        """
        if handler.get("type") != "command":
            return {}  # We only support command hooks for local zero-budget

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

    def _parse_hook_output(
        self, 
        process: subprocess.CompletedProcess, 
        event_name: str
    ) -> Dict:
        """
        Parse the hook's stdout and exit code.
        
        Exit Code Meanings:
        - 0: Success. Parse stdout for JSON decisions.
        - 1: Non-blocking error. Log and continue.
        - 2: Hard Block. Read stderr as reason.
        
        Args:
            process: Completed subprocess
            event_name: Current event name
            
        Returns:
            Parsed result dictionary
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
                        result["reason"] = hook_specific.get(
                            "permissionDecisionReason", 
                            "Denied by hook"
                        )
                        return result

                    # Inject context for the LLM
                    if "additionalContext" in hook_specific:
                        result["additional_context"] = hook_specific["additionalContext"]

                # Check for plain additionalContext
                if "additionalContext" in output_json:
                    result["additional_context"] = output_json["additionalContext"]

            except json.JSONDecodeError:
                # If it's not JSON, treat stdout as plain additional context
                result["additional_context"] = process.stdout.strip()

        # For SessionStart and other events, plain stdout is additional context
        elif process.stdout.strip():
            result["additional_context"] = process.stdout.strip()

        return result

    def register_hook(
        self, 
        event_name: str, 
        matcher: str, 
        command: str, 
        timeout: int = 30
    ):
        """
        Programmatically register a hook (for runtime use).
        
        Args:
            event_name: Event to hook into
            matcher: Tool/event matcher
            command: Command to execute
            timeout: Timeout in seconds
        """
        if event_name not in self.hooks_config:
            self.hooks_config[event_name] = []

        self.hooks_config[event_name].append({
            "matcher": matcher,
            "hooks": [{
                "type": "command",
                "command": command,
                "timeout": timeout
            }]
        })

        # Save updated config
        with open("hooks.json", "w") as f:
            json.dump(self.hooks_config, f, indent=2)
