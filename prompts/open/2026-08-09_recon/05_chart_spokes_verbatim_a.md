---
class: context-extraction
topic: 05 — chart spokes verbatim, batch A (tables, colors, grids)
expected_reply: ~24 KB
sent:
status: OPEN
send_only_if: prompt 01 classifies these as DIFFERS and prompt 03's patches do not fully explain the delta
---

**Staging-side note — do NOT paste this header into PRISM.**

Batched by size to land near 30 KB: tables (12,802 B) + colors (6,530 B) +
grids (3,804 B) = 23,136 B newline-stripped. My sha256 prefixes are
`b416f11fe307`, `b8291188a9f1`, `b3f03b5840d3` respectively.

---

## Paste everything below into PRISM

You are being asked to print three files from your own repository verbatim. Pure
introspection: do not build anything, do not report frictions, do not comment on
the content.

**Reply budget: these three total about 23 KB and should fit in one reply under
roughly 30,000 characters.** If not, finish the files you can and name the one
you did not reach — do not truncate a file mid-way without saying so.

Paste each of these in full, each in its own fenced block, exactly as it exists
on disk — every blank line, every trailing space, every code fence. Do not
reflow, do not fix typos, do not normalise whitespace.

```
prism-core/context/modules/static/tools/charts/chart_context_tables.md
prism-core/context/modules/static/tools/charts/chart_context_colors.md
prism-core/context/modules/static/tools/charts/chart_context_grids.md
```

Head each block with one line: path, byte count, line count, and `sha256[:12]`,
all measured with any single trailing newline stripped.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
