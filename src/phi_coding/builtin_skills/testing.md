---
description: Write thorough, deterministic tests that cover the happy path and the edge cases that actually break code.
---

# Testing

Use this when writing or strengthening tests. Good tests assert real behavior and
target the cases most likely to fail.

## Method

1. **Match the project's style.** Read existing tests with `read`/`grep` first:
   the framework, fixtures, naming, and how providers/IO are faked. New tests
   must look like the ones around them.
2. **Identify the units.** List the behaviors to cover for the code under test —
   each public function/path, not just one happy case.
3. **Cover the edges.** For each unit, add cases for: empty/zero input,
   boundaries (first, last, off-by-one), `None`/missing fields, invalid input and
   error paths, large input/truncation, unicode, and concurrency or ordering when
   relevant.
4. **Keep tests deterministic.** No live network or real clocks — use fakes,
   temp dirs, and injected dependencies. The same test must pass every run.
5. **Assert behavior, not coincidence.** Check the actual outputs, side effects,
   and error messages — not merely that the code ran without raising.
6. **Run them.** Execute the suite with `bash` and confirm the new tests pass
   (and fail when the behavior is broken).

## Rules

- Prefer many small, focused tests over one large test.
- Name tests for the behavior they verify.
- A test that cannot fail is not a test — make sure each assertion can break.
- Never weaken an assertion just to make a test pass; fix the cause.
