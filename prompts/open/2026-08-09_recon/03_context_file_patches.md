---
class: context-extraction
topic: 03 — recover PRISM-side edits to the shipped context markdown as patches
expected_reply: ~25 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

`a1620b6` edited four `chart_context_*.md` spokes inside PRISM. Patches are much
cheaper than the ~66 KB of full verbatim files, so try this route first —
prompts 04-06 (full verbatim) only become necessary for files whose divergence
predates the vendor commit and therefore has no recoverable patch.

---

## Paste everything below into PRISM

You are being asked to print git patches from your own repository verbatim. Pure
introspection: do not build anything, do not report frictions, do not explain
what changed in prose.

**Reply budget: keep this reply under roughly 30,000 characters.** If you run
long, stop at a hunk boundary and finish with a line of exactly this form:

```
STOPPED AT: <commit sha> <file path> hunk starting line <N>. REMAINING: <list>
```

Never abbreviate a hunk, never replace context lines with an ellipsis. I apply
these literally.

### 1. Which commits touched the shipped markdown

The files below are authored in a separate staging repo and copied into you. I
need to know every time they were edited here instead. Print, as a plain list:

```bash
git log --format='%h %ad %an  %s' --date=short 287311b..HEAD --name-only -- \
  prism-core/context/modules/static/tools/chart_context.md \
  prism-core/context/modules/static/tools/charts/ \
  prism-core/context/modules/static/tools/dashboards.md \
  prism-core/context/modules/static/tools/dashboards_hub.md \
  prism-core/context/modules/static/tools/dashboards/
```

### 2. The patches

For each commit that list surfaces, oldest first, print the complete unified
diff restricted to those paths:

```bash
git show <sha> --format='COMMIT %H%nDATE %ad%nAUTHOR %an%nSUBJECT %s' \
  --date=iso -- \
  prism-core/context/modules/static/tools/chart_context.md \
  prism-core/context/modules/static/tools/charts/ \
  prism-core/context/modules/static/tools/dashboards.md \
  prism-core/context/modules/static/tools/dashboards_hub.md \
  prism-core/context/modules/static/tools/dashboards/
```

One fenced block per commit, headed by the sha. Default diff context.

### 3. Post-patch anchors

Finish with the measured triple for every file those patches touched, so I can
verify my patched copies:

```python
import hashlib, os
paths = [...]  # the files your patches touched
for p in sorted(paths):
    b = open(p, "rb").read()
    if b.endswith(b"\n"):
        b = b[:-1]
    print(f"{p}  {len(b)}  {b.count(chr(10).encode()) + 1}  "
          f"{hashlib.sha256(b).hexdigest()[:12]}")
```

### 4. One question

Do any of these markdown files get generated, templated, or post-processed on
this side — or is each one a literal copy of the file dropped in? A one-sentence
answer with the code path if generation exists.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
