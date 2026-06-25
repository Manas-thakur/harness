---
id: skill_git_workflow
type: skill
category: tool_use
version: 2
created: '2026-06-25'
updated: '2026-06-25'
tags:
- git
- version_control
- collaboration
agents:
- coder
prerequisites:
- skill_bash_execution
---

# Skill: Git Workflow Management

## Purpose
Manage version control operations including cloning, branching, committing, and reviewing changes with best practices for collaborative development.

## Capability Statement
I execute git operations safely with proper review steps, conflict resolution, and commit message standards. I understand branching strategies, rebasing, and remote synchronization.

## Core Operations

### Clone Repository
**Input:**
```yaml
url: <git repository URL>
target_dir: <optional, defaults to repo name>
branch: <optional, specific branch to checkout>
depth: <optional, for shallow clones>
```

**Protocol:**
1. Validate URL format
2. Check available disk space
3. Execute `git clone` with appropriate flags
4. Verify clone integrity
5. Report repository structure

### Status and Diff
**Input:**
```yaml
repo_path: <repository directory>
staged_only: <optional, default false>
stat_format: <optional, default short>
```

**Output Structure:**
```yaml
status: <git status --short output>
changed_files: [<list of modified files>]
untracked_files: [<list of new files>]
diff_stat: <git diff --stat output>
commits_behind: <integer>
commits_ahead: <integer>
```

### Stage and Commit
**Input:**
```yaml
files: [<list of files to stage>, or "all" for -A]
commit_message: <commit message string>
description: <optional, longer description body>
co_authors: [<optional list of co-author emails>]
```

**Commit Message Standards:**
```
<type>(<scope>): <subject>

<body explaining what and why>

Fixes: #issue_number
Co-authored-by: Name <email>
```

**Types:** feat, fix, docs, style, refactor, test, chore, perf, ci, build

### Branch Operations
**Create Branch:**
```yaml
operation: create_branch
branch_name: <new branch name>
base_branch: <optional, default current HEAD>
```

**Checkout Branch:**
```yaml
operation: checkout
branch_name: <existing branch>
create_if_missing: <optional, default false>
```

**Merge Branch:**
```yaml
operation: merge
source_branch: <branch to merge from>
target_branch: <optional, default current>
strategy: <merge|rebase, default merge>
no_ff: <optional, default false>
```

### Remote Synchronization
**Push:**
```yaml
operation: push
remote: <optional, default origin>
branch: <optional, default current>
force: <optional, NEVER default true - requires explicit confirmation>
```

**Pull:**
```yaml
operation: pull
remote: <optional, default origin>
branch: <optional, default current>
rebase: <optional, default false>
```

## Safety Protocols

### Destructive Operation Prevention
**NEVER execute without explicit confirmation:**
- `git reset --hard` (loses commits)
- `git push --force` (rewrites history)
- `git clean -fd` (deletes untracked files)
- `git branch -D` (force delete branches with unmerged work)

**Confirmation Protocol:**
1. Detect destructive operation
2. Show exactly what will be lost/changed
3. Require explicit user confirmation with reason
4. Create backup branch before proceeding

### Conflict Detection and Resolution
**Pre-Merge Checks:**
1. Run `git merge --no-commit --no-ff` to test
2. If conflicts detected, abort and report
3. Show conflicting files and sections
4. Offer resolution strategies

**Resolution Process:**
1. Identify all conflicted files
2. For each conflict, show:
   - Current change (ours)
   - Incoming change (theirs)
   - Context around conflict
3. Propose resolution or ask for guidance
4. After resolution, verify with `git diff --check`

### Commit Quality Gates
Before committing, verify:
- [ ] No debug statements or TODOs without tickets
- [ ] No trailing whitespace
- [ ] No large binary files (unless intentional)
- [ ] Commit message follows convention
- [ ] Changes are logically grouped
- [ ] Tests updated if applicable

## Review Workflow

### Pre-Commit Review
**Show diff summary:**
```bash
git diff --cached --stat
git diff --cached --color-words
```

**Check for common issues:**
- Debug prints (`print(`, `console.log`, `debugger`)
- Commented-out code blocks
- Hardcoded secrets or credentials
- Large files (>1MB without LFS)

### Post-Commit Verification
After commit:
1. Show commit hash and summary
2. Verify files changed match intent
3. Check CI status if configured
4. Suggest next steps (push, more changes, etc.)

## Error Handling

### Common Git Errors
| Error | Cause | Resolution |
|-------|-------|------------|
| "Changes would be overwritten" | Uncommitted changes | Stash or commit first |
| "Conflict in file.X" | Merge conflict | Manual resolution required |
| "Remote rejected" | Hook failure or permissions | Check remote requirements |
| "Detached HEAD" | Checked out commit directly | Create branch or checkout branch |
| "Needs merge" | Unmerged files | Resolve or abort merge |

### Recovery Procedures
**Aborted Merge:**
```bash
git merge --abort  # Return to pre-merge state
```

**Lost Commits:**
```bash
git reflog  # Find lost commit hash
git checkout <hash>  # Recover
```

**Accidental Reset:**
```bash
git reflog
git reset --hard HEAD@{1}  # Restore previous state
```

## Examples

### Example 1: Feature Development Workflow
**Sequence:**
```yaml
# Create feature branch
operation: create_branch
branch_name: feat/add-new-skill
base_branch: main

# After making changes, commit
files: all
commit_message: "feat(skills): add bash execution skill"
description: "Implements comprehensive bash execution with safety protocols"

# Push to remote
operation: push
branch: feat/add-new-skill
```

### Example 2: Safe Rebase
**Input:**
```yaml
operation: rebase
onto_branch: main
preserve_merges: true
interactive: false
```

**Safety Steps:**
1. Ensure working tree is clean
2. Create backup branch: `backup/pre-rebase-timestamp`
3. Perform rebase with autosquash
4. Verify tests pass
5. Force push ONLY if explicitly confirmed

### Example 3: Conflict Resolution
**When conflict detected:**
```yaml
conflict_file: harness/tools.py
conflict_sections: 2
resolution_strategy: manual
```

**Report:**
```
CONFLICT in harness/tools.py (2 sections)

Section 1 (lines 45-52):
<<<<<<< HEAD
    MAX_TOOL_CHARS = 2000
=======
    MAX_TOOL_CHARS = 4000
>>>>>>> feat/increase-limit

Recommendation: Accept incoming change (increases limit as intended)
```

## Related Skills
- [[skill_bash_execution]] - Underlying command execution
- [[skill_file_operations]] - Reading/writing files
- [[skill_code_review]] - Reviewing changes quality

## Memory Integration
- Track active branches in [[fact_active_branches]]
- Store common commit patterns in [[skill_commit_templates]]
- Link project-specific git workflows in [[fact_git_workflow_<project>]]

## Best Practices

### Commit Hygiene
- One logical change per commit
- Write messages in imperative mood ("Add feature" not "Added feature")
- Reference issues in commit messages
- Keep commits small and reviewable

### Branch Naming
- `feat/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code restructuring
- `test/description` - Test additions/changes

### Remote Etiquette
- Pull before pushing to shared branches
- Never force-push to main/master
- Delete merged feature branches
- Keep fork synchronized with upstream

## Improvement Notes
- v2: Added comprehensive conflict resolution and recovery procedures
- v1: Initial git workflow implementation
