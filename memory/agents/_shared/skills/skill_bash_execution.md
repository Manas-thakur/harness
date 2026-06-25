---
id: skill_bash_execution
type: skill
category: tool_use
version: 2
created: '2026-06-25'
updated: '2026-06-25'
tags:
- shell
- automation
- execution
agents:
- coder
- researcher
prerequisites: []
---

# Skill: Bash Command Execution

## Purpose
Execute shell commands safely and effectively for system automation, file operations, and process management.

## Capability Statement
I can run any bash command with proper error handling, timeout management, and output parsing. I understand shell scripting, pipes, redirection, and environment management.

## Usage Pattern

### Input Format
```yaml
command: <bash command string>
timeout: <optional, default 120 seconds>
working_dir: <optional, defaults to current>
environment: <optional, additional env vars>
```

### Output Structure
```yaml
stdout: <command standard output>
stderr: <command standard error>
exit_code: <integer exit code>
duration: <execution time in seconds>
truncated: <boolean, true if output exceeded limits>
```

## Safety Protocols

### Pre-Execution Checks
1. **Destructive Command Detection**: Block or confirm commands containing:
   - `rm -rf /` or similar recursive deletes at root
   - `dd if=` without explicit confirmation
   - `chmod -R 777 /` or permission wipes
   - `:(){ :|:& };:` fork bombs
   
2. **Path Validation**: Ensure paths are within allowed directories unless explicitly authorized

3. **Environment Sanitization**: Source `.agent_env.sh` before execution for consistent environment

### Execution Rules
- Always use timeouts (default 120s)
- Capture both stdout and stderr
- Return structured results with exit codes
- Truncate output at MAX_TOOL_CHARS (4000) with notification

### Post-Execution Actions
- Log command and result for audit trail
- Check for sensitive data in output
- Update environment file if exports detected

## Error Handling

### Common Failure Modes
| Error Type | Detection | Recovery Action |
|------------|-----------|-----------------|
| Command not found | exit_code=127 | Suggest installation or alternative |
| Permission denied | exit_code=1, "Permission denied" in stderr | Suggest sudo or path check |
| Timeout | Custom timeout handling | Kill process, report partial output |
| Syntax error | exit_code=2, bash error messages | Offer to fix syntax |

### Retry Strategy
- For transient failures (network, locks): retry up to 3 times with exponential backoff
- For permanent failures (syntax, permissions): do not retry, report error clearly

## Examples

### Example 1: Simple File Operation
**Input:**
```bash
ls -la /workspace/harness/
```

**Expected Output:**
```yaml
stdout: "total 84\ndrwxr-xr-x ..."
stderr: ""
exit_code: 0
```

### Example 2: Git Operations
**Input:**
```bash
git status --short && git diff --stat
```

**Expected Output:**
```yaml
stdout: "M harness/tools.py\n M memory.md\n..."
stderr: ""
exit_code: 0
```

### Example 3: Process Management
**Input:**
```bash
ps aux | grep python | grep -v grep
```

**Expected Output:**
```yaml
stdout: "root 1234 ... python agent.py ..."
stderr: ""
exit_code: 0
```

## Related Skills
- [[skill_file_operations]] - Read/write files atomically
- [[skill_git_workflow]] - Version control operations
- [[skill_process_monitoring]] - Track and manage processes

## Memory Integration
- Store frequently used commands in [[fact_command_snippets]]
- Record environment setup in [[fact_shell_environment]]
- Link troubleshooting guides in [[fact_bash_debugging]]

## Improvement Notes
- v2: Added destructive command detection and safety protocols
- v1: Initial implementation
