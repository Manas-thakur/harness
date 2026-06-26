---
description: Restructure code safely in small, behavior-preserving steps verified by tests.
---

# Refactoring

Use this when improving the structure of existing code without changing its
behavior. Safety comes from small steps and a passing test suite.

## Method

1. **Establish a safety net.** Find and run the relevant tests with `bash`. If
   coverage for the area is thin, add characterization tests that capture current
   behavior before changing anything.
2. **Define the target.** State the specific structural improvement (extract a
   function, rename, remove duplication, split a module) and the desired end
   state. Keep the scope narrow.
3. **Work in small steps.** Make one mechanical change at a time with `edit`
   (precise, minimal `oldText`). Run the tests after each step so a regression is
   caught immediately and is easy to localize.
4. **Preserve behavior.** Do not mix behavior changes into a refactor. If you
   discover a bug, note it separately rather than silently changing semantics.
5. **Clean up.** Remove now-dead code and update call sites (`grep` for every
   usage). Keep names and style consistent with the surrounding code.

## Rules

- Never refactor without a way to verify behavior is unchanged.
- Update every caller of anything you rename or move — `grep` to find them all.
- Keep diffs focused; resist unrelated improvements in the same change.
- Re-run the full test suite and linters at the end.
