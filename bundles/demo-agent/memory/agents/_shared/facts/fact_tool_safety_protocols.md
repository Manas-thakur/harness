---
id: fact_tool_safety_protocols
type: fact
category: safety
version: 2
created: '2026-06-25'
updated: '2026-06-25'
tags:
- safety
- tools
- security
---

# Fact: Tool Safety Protocols

## Critical Safety Rules

### Bash Execution
1. **NEVER** run destructive commands without explicit confirmation:
   - `rm -rf /` or recursive deletes at root level
   - `dd if=` operations that could overwrite data
   - `chmod -R 777 /` permission wipes
   - Fork bombs or resource exhaustion commands

2. **ALWAYS** use timeouts (default 120s) to prevent hangs

3. **ALWAYS** capture and report both stdout and stderr

4. **VALIDATE** paths are within allowed directories

### File Operations
1. **ALWAYS** use atomic writes (temp file + rename) to prevent corruption

2. **NEVER** modify files without backup for destructive changes

3. **RESPECT** file locks to prevent concurrent access issues

4. **TRUNCATE** large outputs to prevent context overflow (MAX_TOOL_CHARS = 4000)

### Git Operations
1. **NEVER** force push to shared branches without explicit confirmation

2. **ALWAYS** review diffs before committing

3. **CREATE** backup branches before rebasing or resetting

4. **VERIFY** working tree is clean before branch operations

### Information Handling
1. **NEVER** output sensitive data (passwords, tokens, private keys)

2. **REDACT** credentials from logs and outputs

3. **WARN** users when they request potentially dangerous operations

4. **LOG** all tool executions for audit trail

## Two-Strike Rule
If the same tool is called with identical arguments twice in succession:
1. Block the second execution
2. Inject system message: "You are repeating yourself. Change your approach."
3. Require different parameters or tool selection

## Permission Levels

| Level | Tools | Description |
|-------|-------|-------------|
| Read | read_file, list_dir, search | Safe, no modifications |
| Write | write_file, edit, bash (safe) | Modifies workspace |
| Admin | git commit, bash (all) | Requires confirmation |
| Dangerous | rm -rf, force push, chmod | Explicit confirmation required |

## Related Facts
- [[fact_error_handling_patterns]] - How to handle tool failures
- [[fact_audit_logging]] - Tracking tool usage

## Version History
- v2: Added Two-Strike rule and permission levels
- v1: Initial safety protocols
