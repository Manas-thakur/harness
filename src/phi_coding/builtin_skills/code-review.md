---
description: Review code for correctness, edge cases, security, performance, and clarity with concrete, located findings.
---

# Code Review

Use this when asked to review a change, file, or diff. Produce specific,
actionable findings — not vague impressions.

## What to examine

1. **Correctness.** Does it do what it claims? Walk the logic. Check edge cases:
   empty input, boundaries (0, 1, max), `None`/null, unicode, concurrency, and
   error paths. Look for off-by-one and incorrect early returns.
2. **Failure handling.** Are errors caught at the right boundary? Are resources
   (files, sockets, locks) released on every path? Is cancellation honored?
3. **Security.** Untrusted input validation, injection (shell, SQL, path
   traversal), secrets in code/logs, unsafe deserialization, missing authz.
4. **Performance.** Obvious quadratic loops, N+1 calls, unbounded memory, work
   that could be batched or done concurrently.
5. **Clarity & conventions.** Naming, dead code, duplication, and consistency
   with the surrounding codebase. Read neighboring files with `read`/`grep` to
   learn the conventions before judging.
6. **Tests.** Are the new behaviors and edge cases covered? Do the tests actually
   assert the behavior, or just run it?

## Output

- Group findings by severity: **blocking**, **should-fix**, **nit**.
- For each, give the `path:line`, what is wrong, why it matters, and a concrete
  suggested fix.
- Note what is good too, briefly, so the signal is balanced.

## Rules

- Anchor every finding to code you actually read (`path:line`).
- Prefer specific fixes over general advice.
- Do not invent issues; if the code is fine, say so.
