---
id: skill_file_operations
type: skill
category: tool_use
version: 2
created: '2026-06-25'
updated: '2026-06-25'
tags:
- files
- io
- atomic
agents:
- coder
- researcher
prerequisites: []
---

# Skill: Atomic File Operations

## Purpose
Read, write, and modify files safely using atomic operations to prevent data corruption during concurrent access or system failures.

## Capability Statement
I perform all file operations with proper locking, atomic writes, and version tracking. I handle encoding, large files, and concurrent access patterns safely.

## Core Operations

### Read File (Locked)
**Input:**
```yaml
file_path: <absolute or relative path>
encoding: <optional, default utf-8>
lock_type: <shared|exclusive, default shared>
```

**Output:**
```yaml
content: <file contents as string>
size_bytes: <file size>
modified_time: <ISO timestamp>
read_success: <boolean>
error: <optional error message>
```

**Safety Rules:**
- Acquire shared lock for reading (allows concurrent reads)
- Handle missing files gracefully
- Detect and report binary files
- Truncate large files (>MAX_TOOL_CHARS) with notification

### Write File (Atomic)
**Input:**
```yaml
file_path: <absolute or relative path>
content: <string content to write>
encoding: <optional, default utf-8>
permissions: <optional, default 0o644>
backup: <optional, default true>
```

**Output:**
```yaml
success: <boolean>
file_path: <written path>
size_bytes: <written size>
backup_path: <path to backup if created>
write_timestamp: <ISO timestamp>
```

**Atomic Write Protocol:**
1. Create temporary file in same directory
2. Write all content to temp file
3. Sync to disk (fsync)
4. Rename temp file to target (atomic on POSIX)
5. Set permissions
6. Release locks

### Edit File (String Replacement)
**Input:**
```yaml
file_path: <target file>
old_string: <exact text to replace>
new_string: <replacement text>
occurrence: <optional, which occurrence to replace, default first>
```

**Output:**
```yaml
success: <boolean>
replacements_made: <integer count>
original_size: <before edit>
new_size: <after edit>
error: <optional error if old_string not found>
```

**Edit Safety:**
- Verify old_string exists exactly once (or specify occurrence)
- Preserve file encoding
- Create backup before modification
- Validate resulting file integrity

## Directory Operations

### List Directory
**Input:**
```yaml
directory_path: <path>
pattern: <optional glob pattern, default *>
recursive: <optional, default false>
include_hidden: <optional, default false>
```

**Output:**
```yaml
files: [<list of file paths>]
directories: [<list of directory paths>]
total_count: <integer>
```

### Create Directory Structure
**Input:**
```yaml
path: <directory path to create>
parents: <optional, default true (like mkdir -p)>
permissions: <optional, default 0o755>
```

## Safety Protocols

### Path Validation
- Resolve relative paths to absolute
- Prevent path traversal attacks (../ outside workspace)
- Validate against allowed directories list
- Check for symlink loops

### Permission Management
- Respect existing file permissions
- Apply restrictive defaults (0o644 for files, 0o755 for dirs)
- Never escalate permissions without explicit request
- Document permission changes in audit log

### Backup Strategy
- Create .bak backups before destructive operations
- Timestamp backup files: `filename.YYYYMMDD_HHMMSS.bak`
- Keep last N backups (configurable, default 3)
- Store backups in same directory for easy recovery

## Error Handling

### Common Errors
| Error | Detection | Recovery |
|-------|-----------|----------|
| File not found | FileNotFoundError | Offer to create or search alternatives |
| Permission denied | PermissionError | Suggest permission check or sudo |
| Disk full | OSError ENOSPC | Report available space, suggest cleanup |
| Encoding error | UnicodeDecodeError | Try alternative encodings or binary mode |
| Lock timeout | Timeout waiting for lock | Retry with backoff, report contention |

### Retry Logic
- Transient errors (locks, temporary unavailability): 3 retries with exponential backoff
- Permanent errors (missing files, bad paths): No retry, clear error message

## Examples

### Example 1: Atomic Write
**Input:**
```yaml
operation: write
file_path: /workspace/config.json
content: '{"key": "value"}'
permissions: 0o644
```

**Expected Output:**
```yaml
success: true
file_path: /workspace/config.json
size_bytes: 16
backup_path: null
write_timestamp: '2026-06-25T10:30:00'
```

### Example 2: Safe Edit
**Input:**
```yaml
operation: edit
file_path: /workspace/harness/tools.py
old_string: "MAX_TOOL_CHARS = 2000"
new_string: "MAX_TOOL_CHARS = 4000"
```

**Expected Output:**
```yaml
success: true
replacements_made: 1
original_size: 4521
new_size: 4521
```

### Example 3: Locked Read
**Input:**
```yaml
operation: read
file_path: /workspace/memory.md
lock_type: shared
```

**Expected Output:**
```yaml
content: "# Agent Memory\n\n## Active Topics..."
size_bytes: 15234
modified_time: '2026-06-25T09:15:00'
read_success: true
```

## Related Skills
- [[skill_bash_execution]] - Shell command execution
- [[skill_git_workflow]] - Version control integration
- [[skill_json_processing]] - Structured data handling

## Memory Integration
- Track frequently accessed files in [[fact_file_patterns]]
- Store backup locations in [[fact_backup_locations]]
- Link file structure documentation in [[fact_project_layout]]

## Performance Considerations
- Use memory-mapped I/O for very large files (>10MB)
- Stream processing for line-by-line operations
- Batch operations when possible to reduce I/O overhead
- Cache file metadata to avoid repeated stat calls

## Improvement Notes
- v2: Added comprehensive backup strategy and retry logic
- v1: Initial atomic operations implementation
