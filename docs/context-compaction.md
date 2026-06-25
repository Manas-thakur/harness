# Context Compaction

Context compaction is how Phi keeps a long coding session usable when the
conversation approaches a model's context limit. Phi asks the configured model to
summarize older session messages, stores that summary as a session entry, and
rebuilds future provider context from:

1. one summary message for the compacted history
2. any recent messages Phi deliberately kept
3. new messages added after compaction

The original session JSONL remains append-only. Compaction changes the active
context that Phi sends to the provider; it does not delete prior history from the
session file.

## What Phi Counts

`CodingSession.context_usage` estimates the same provider request shape Phi is
about to send:

- the system prompt
- project context files included in the system prompt, such as `AGENTS.md`
- skill metadata included in the system prompt
- active message history, including user messages, assistant messages, assistant
  tool calls, and tool result messages
- tool schemas sent to the provider

Prompt templates are counted only when their content has been expanded into a
message or the system prompt. Queued follow-up or steering messages are counted
after they are drained into the active harness transcript.

Phi uses a deterministic estimate, not a provider tokenizer:

- text is estimated as `ceil(characters / 4)`
- each message has a small role overhead
- each tool definition has a schema overhead

Pi can use provider-reported usage from the last successful assistant response
and then estimate trailing messages. Phi does not persist provider usage yet, so
this phase keeps the explicit Phi estimate and documents it as approximate.

## Trigger Conditions

Phi checks automatic compaction in three places:

- before a new prompt, to catch context added outside a normal assistant turn
- after a successful prompt or continuation, to compact before the next user turn
- after a context-overflow provider error, to compact and retry once

Automatic threshold compaction is enabled by default. Like Pi, Phi triggers it
when estimated context is greater than:

```text
model context window - reserve tokens
```

The Pi defaults that Phi follows are:

- reserve tokens: `16384`
- recent context to keep: `20000`
- fallback context window for unknown/custom models: `128000`

Built-in providers include per-model context windows where Phi knows them.
Unknown/local models use the fallback window, so their default threshold is
`111616` tokens. You can override the threshold for a run:

```bash
phi --auto-compact-threshold 100000
```

Phi's provider interface does not yet expose a per-request max-output-token
setting for the summarization call.

## What Gets Summarized

Manual compaction:

```text
/compact [instructions]
```

Manual compaction summarizes all active context messages into one model-generated
summary. The optional text after `/compact` is appended to the built-in summary
prompt as an extra focus, not used as the summary itself.

Automatic threshold and overflow compaction summarize older context and keep a
recent suffix of the active context. Phi chooses a cut point around the recent
token budget and prefers to retain from a user-message boundary so tool results
are not kept without their surrounding turn. If the session is too small or Phi
cannot find a useful older section to summarize, automatic compaction is skipped.

When there is already a previous compaction summary in the compacted range, Phi
uses the update prompt and gives the previous summary to the summarizer in
`<previous-summary>` tags.

## Summary Prompt

Phi uses Pi's structured compaction prompt.

System prompt:

```text
You are a context summarization assistant. Your task is to read a conversation between a user and an AI coding assistant, then produce a structured summary following the exact format specified.

Do NOT continue the conversation. Do NOT respond to any questions in the conversation. ONLY output the structured summary.
```

Initial summary prompt:

```text
The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages.
```

Update prompt:

```text
The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. RULES:
- PRESERVE all existing information from the previous summary
- ADD new progress, decisions, and context from the new messages
- UPDATE the Progress section: move items from "In Progress" to "Done" when completed
- UPDATE "Next Steps" based on what was accomplished
- PRESERVE exact file paths, function names, and error messages
- If something is no longer relevant, you may remove it
```

Phi also keeps Pi's split-turn prefix prompt text in code as the target behavior
for future finer-grained cut points. The current implementation avoids most
split-turn retention by preferring user-message boundaries.

## Session Effects

Compaction appends a `CompactionEntry` and a new leaf entry. During replay,
`SessionState` removes the replaced context entry ids and inserts one synthetic
user message:

```text
Previous conversation summary:
<generated summary>
```

When only older messages are replaced, the summary is inserted before the recent
messages Phi kept. This preserves chronological context for the next provider
request.

`/session` shows the current estimate:

```text
Estimated context tokens: <count>
Context token breakdown: system=<count>, messages=<count>, tools=<count>
```

When a raw automatic threshold is configured, `/session` also shows:

```text
Auto compact threshold: <count>
```

## Failure Behavior

Manual compaction fails visibly if the summarization request fails.

Automatic threshold compaction is best-effort: Phi logs diagnostics, keeps the
original context, and continues if summarization fails.

Overflow recovery works once per provider call. Phi surfaces the original
overflow error event, persists the user prompt that caused it, compacts older
context if possible, and retries with the compacted context. If the retry also
fails, Phi surfaces that error and stops instead of looping.

## Known Limitations

- Phi estimates tokens with `chars / 4`; it does not yet store provider usage.
- Phi has provider-configured context windows for built-in models and falls back
  to `128000` tokens for unknown/custom models.
- The provider interface does not yet expose max output tokens for the
  summarization request.
- Split-turn prefix summarization is documented and the prompt is available, but
  this implementation mainly avoids split turns instead of generating a second
  prefix summary.
- Compaction summaries are plain text; structured file-operation metadata like
  Pi's richer compaction details can be added later.

