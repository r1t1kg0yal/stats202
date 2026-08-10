---
class: context-extraction
topic: 02 — recover the PRISM-side edits to chart_render/core.py as literal patches
expected_reply: ~30 KB, resumable across messages
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

`core.py` diverged: PRISM 1,238,859 B / 29,911 lines against staging 1,233,020 B
/ 29,914. Two commits are known to have edited it inside PRISM (`5ff6e3f`,
`a1620b6`); prompt 01 §3.1 will confirm whether there are others. This prompt
recovers the hunks so we can apply them here exactly, per the housekeeping rule
in `.cursor/rules/viz-platforms.mdc`. Designed to be re-sent verbatim to
continue where a previous reply stopped.

---

## Paste everything below into PRISM

You are being asked to print git patches from your own repository verbatim. Pure
introspection: do not build anything, do not report frictions, do not explain
what the code does.

**Reply budget: keep this reply under roughly 30,000 characters.** This request
will very likely exceed one reply. That is expected and fine. Work through the
patches in order and when you approach the budget, **stop at a hunk boundary**,
then finish with a line of exactly this form:

```
STOPPED AT: <commit sha> <file path> hunk starting line <N>. REMAINING: <list>
```

I will paste this same prompt back to you with a "resume from" line and you
continue from there. Never abbreviate a hunk to save room, never replace context
lines with an ellipsis, never summarize a change in prose instead of showing it.
These are patches I will apply literally, so fidelity matters more than coverage.

### 1. Scope

The file is `prism-core/prism_mcp/chart_render/core.py`.

First print, as a plain list with no diffs, every commit that touched it since
`287311b`:

```bash
git log --format='%h %ad %an  %s' --date=short 287311b..HEAD \
  -- prism-core/prism_mcp/chart_render/core.py
```

### 2. The patches

Then, for each commit in that list, oldest first, print the complete unified
diff restricted to that one file:

```bash
git show <sha> --format='COMMIT %H%nDATE %ad%nAUTHOR %an%nSUBJECT %s%n%n%b' \
  --date=iso -- prism-core/prism_mcp/chart_render/core.py
```

Put each commit's output in its own fenced block, headed by the commit sha.
Use default diff context (3 lines). Do not pass `--stat` instead of the diff.

If a single commit's diff alone exceeds the budget, split it at a hunk boundary
and use the `STOPPED AT:` line described above.

### 3. Verification anchor

After the patches — or in the final message if this spans several — print:

```python
import hashlib
b = open("prism-core/prism_mcp/chart_render/core.py", "rb").read()
if b.endswith(b"\n"):
    b = b[:-1]
print(len(b), b.count(b"\n") + 1, hashlib.sha256(b).hexdigest())
```

That triple is what I will check my patched copy against.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
