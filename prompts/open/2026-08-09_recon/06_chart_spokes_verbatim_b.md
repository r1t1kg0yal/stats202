---
class: context-extraction
topic: 06 — chart spokes verbatim, batch B (annotations, dual_axis, composites)
expected_reply: ~23 KB
sent:
status: OPEN
send_only_if: prompt 01 classifies these as DIFFERS and prompt 03's patches do not fully explain the delta
---

**Staging-side note — do NOT paste this header into PRISM.**

Second half of the six Altair spokes: annotations (7,791 B) + dual_axis
(7,229 B) + composites (6,647 B) = 21,667 B newline-stripped. My sha256
prefixes are `1af059c6a29d`, `c745e896a912`, `c37fe279a38f` respectively.

---

## Paste everything below into PRISM

You are being asked to print three files from your own repository verbatim. Pure
introspection: do not build anything, do not report frictions, do not comment on
the content.

**Reply budget: these three total about 22 KB and should fit in one reply under
roughly 30,000 characters.** If not, finish the files you can and name the one
you did not reach — do not truncate a file mid-way without saying so.

Paste each of these in full, each in its own fenced block, exactly as it exists
on disk — every blank line, every trailing space, every code fence. Do not
reflow, do not fix typos, do not normalise whitespace.

```
prism-core/context/modules/static/tools/charts/chart_context_annotations.md
prism-core/context/modules/static/tools/charts/chart_context_dual_axis.md
prism-core/context/modules/static/tools/charts/chart_context_composites.md
```

Head each block with one line: path, byte count, line count, and `sha256[:12]`,
all measured with any single trailing newline stripped.

Then one closing question, answered in a sentence: these six spoke files are
fetched on demand rather than through the registry. What is the exact
`list_ai_repo` call that resolves one of them today — does the short form
`charts/chart_context_tables.md` still work, or is a path rooted at
`context/modules/static/tools/...` now required?

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
