---
description: Find and fix the root cause of a bug methodically, then prove it with a regression test.
---

# Debugging

Use this when something is broken, failing, or behaving unexpectedly. Fix the
root cause, not the symptom.

## Method

1. **Reproduce first.** Establish the exact failing command or input and run it
   with `bash` to see the real error. A bug you cannot reproduce, you cannot
   confirm fixed.
2. **Read the evidence.** Read the full stack trace / error output carefully. Use
   `grep` to locate the error message or failing symbol in the source, and
   `read` the surrounding code.
3. **Form a hypothesis.** State what you believe is wrong and why, based on the
   evidence — not a guess. Predict what you would observe if it were true.
4. **Isolate.** Narrow the failure: shrink the input, add targeted logging or
   asserts, or bisect recent changes (`bash` with git) until the smallest
   failing case is clear.
5. **Fix the root cause.** Make the minimal change that addresses the underlying
   defect, matching surrounding conventions. Avoid masking the symptom.
6. **Prove it.** Add or update a test that fails before the fix and passes after.
   Re-run the reproduction and the test suite with `bash`.

## Rules

- Confirm the diagnosis before changing code; do not shotgun edits.
- Keep the fix focused — resist unrelated refactors in a bug fix.
- Verify with the actual command output; never claim a fix you have not run.
- If you cannot reproduce or confirm, say so and report what you observed.
