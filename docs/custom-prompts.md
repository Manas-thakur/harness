# Custom Prompts

Custom prompts are reusable Markdown files that help you give Phi the same instructions again without retyping them.

These prompts are installed as user-level `.agents` prompt templates:

```text
~/.agents/prompts/
```

That makes them available across projects instead of only in this repository.

## How Phi finds prompts

Phi loads Markdown files from prompt directories. The filename becomes the prompt name.

For example:

```text
~/.agents/prompts/wt.md
```

creates a prompt template named:

```text
wt
```

Conceptually, you can think of it as the `/wt` prompt.

After adding or editing prompt files while the TUI is open, run:

```text
/reload
```

This tells Phi to rediscover local resources.

## Prompt file format

A prompt template is a Markdown file. It can start with frontmatter:

```md
---
description: Short explanation shown by Phi.
---

Prompt instructions go here.
```

The `description` helps identify what the prompt is for.

Prompt templates can also include variables:

```md
Implement this feature:
{{ feature }}
```

Variables are placeholders that can be filled in when the template is rendered by Phi code or future prompt-expansion UI.

## Prompts added to `~/.agents`

### `/wt`

File:

```text
~/.agents/prompts/wt.md
```

Purpose:

Use this when you want the agent to implement a feature safely in a separate Git worktree.

The prompt tells the agent to:

1. create a new branch from `main`
2. create a separate Git worktree for that branch
3. make all code changes inside that worktree
4. run relevant tests
5. commit the changes
6. push the branch
7. create a pull request back to `main`
8. report the branch, worktree path, commit, test results, and PR URL

It has one variable:

```text
{{ feature }}
```

That variable should contain the feature request.

Example rendered prompt idea:

```text
Use the /wt prompt with feature = "Add a /prompts command that lists available prompt templates."
```

### `/prune`

File:

```text
~/.agents/prompts/prune.md
```

Purpose:

Use this when you want the agent to clean up local Git worktrees after their branches have already been merged into `main`.

The prompt tells the agent to:

1. list all Git worktrees
2. fetch updated remote branch metadata
3. identify branches already merged into `main`
4. avoid deleting the main worktree
5. avoid deleting worktrees with uncommitted changes or unmerged branches
6. remove only safe merged worktrees
7. delete safe merged local branches
8. run `git worktree prune`
9. report what was removed and what was skipped

It also tells the agent to ask for confirmation before deleting anything unless deletion was explicitly approved.

## When to use these prompts

Use `/wt` for new implementation work where you want isolation from the current checkout.

Use `/prune` for cleanup after pull requests have been merged.

Together, these prompts support a safe branch workflow:

1. implement work in an isolated worktree
2. open a pull request to `main`
3. after merge, prune the old worktree
