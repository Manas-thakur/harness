# Phase 9: Skills and Prompt Templates

Phase 9 adds Phi's first markdown resource system.

The implementation lives in:

```text
src/phi_coding/resources.py
src/phi_coding/skills.py
src/phi_coding/prompt_templates.py
```

## What was added

Phi can now load and use markdown resources from a Phi resource root:

```text
~/.phi/
  skills/
  prompts/
```

This phase includes:

- resource path helpers
- minimal markdown frontmatter parsing
- skill loading
- `/skill:name` prompt expansion
- skill index generation
- prompt template loading
- `{{ variable }}` template rendering
- light `CodingSession` integration for skill expansion

## Resource paths

`PhiResourcePaths` describes where Phi resources live:

```python
from phi_coding import PhiResourcePaths

paths = PhiResourcePaths()  # ~/.phi
paths.skills_dir            # ~/.phi/skills
paths.prompts_dir           # ~/.phi/prompts
```

Tests and callers can provide a custom root:

```python
paths = PhiResourcePaths(root=Path("/tmp/resources"))
```

## Frontmatter

Skills and prompt templates can include simple frontmatter:

```md
---
description: Write and run Python tests.
---

# Python Testing

Use pytest.
```

The parser intentionally supports only simple `key: value` pairs. It does not execute code or implement a full YAML parser.

## Skills

Phi supports two skill layouts:

```text
~/.phi/skills/python-testing/SKILL.md
~/.phi/skills/git-review.md
```

Load skills with:

```python
from phi_coding import PhiResourcePaths, load_skills

skills = load_skills(PhiResourcePaths())
```

Duplicate skill names raise `ResourceError`.

## Skill expansion

Skill commands use the roadmap syntax:

```text
/skill:python-testing add tests for parser.py
```

Expansion produces prompt text like:

```md
<skill name="python-testing" location="/path/to/python-testing/SKILL.md">
References are relative to /path/to/python-testing.

...skill markdown...
</skill>

add tests for parser.py
```

`CodingSession.prompt()` expands skill commands before sending the prompt to `AgentHarness`. `/skill:name` is not consumed by `handle_command()` because it is a prompt expansion directive, not a command that ends the run.

## Skill index

`build_skill_index()` creates a concise list of available skills for future system prompt assembly:

```md
Available skills:
- python-testing: Write and run Python tests.
- git-review: Review git changes safely.
```

Phase 10 can use this when building the full system prompt.

## Prompt templates

Prompt templates live in:

```text
~/.phi/prompts/review.md
.agents/prompts/review.md
```

Phi treats loaded prompt templates as slash-command prompt expansions. A file
named `.agents/prompts/example.md` can be invoked with:

```text
/example src/app.py
```

Phi expands the command before sending the prompt to the model. Invocation text
after the command is available as `{{ arguments }}` or `{{ args }}`:

```md
Review {{ arguments }} for correctness.
```

If the prompt template has no `{{ arguments }}` or `{{ args }}` placeholder,
Phi appends the invocation arguments after a blank line. Other placeholders are
left blank during slash-command expansion so a custom prompt can include optional
fields without crashing the TUI.

Template variables use simple `{{ variable }}` placeholders:

```md
Review {{ target }} for {{ focus }}.
```

Render templates directly with:

```python
from phi_coding import load_prompt_templates, render_prompt_template

templates = load_prompt_templates(paths)
text = render_prompt_template(
    templates[0],
    {"target": "auth.py", "focus": "security"},
)
```

Missing variables raise `ResourceError`; extra variables are ignored. This strict
behavior applies to direct rendering. Slash-command expansion is more forgiving
and renders missing custom variables as blank text.

## Boundary

This phase does not implement full system prompt assembly. It only adds the resource primitives and a minimal skill-expansion hook in `CodingSession`.

Full prompt assembly remains a later phase and will combine:

- base Phi identity
- tools and tool guidelines
- project instructions
- skills index
- prompt templates
- extension snippets later
- environment context

## Tests

This phase is covered by:

```text
tests/test_resources.py
tests/test_skills.py
tests/test_prompt_templates.py
tests/test_coding_session.py
```

The tests verify:

- resource paths
- frontmatter parsing
- skill loading and duplicate detection
- skill expansion
- skill index output
- prompt template loading
- template rendering
- coding-session skill expansion

## Next phase

The next roadmap phase is system prompt assembly. The resource models and loaders added here give that phase the skill and template inputs it needs.
