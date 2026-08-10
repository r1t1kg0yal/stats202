---
class: context-extraction
topic: 04 — chart_context.md verbatim (the registered router)
expected_reply: ~23 KB
sent:
status: OPEN
send_only_if: prompt 01 classifies chart_context.md as DIFFERS and prompt 03's patches do not fully explain the delta
---

**Staging-side note — do NOT paste this header into PRISM.**

Full-file fallback for the one registered Altair context module. Only needed if
the divergence predates the vendor commit, since anything after it comes back
more cheaply as a patch through prompt 03. My copy: 22,223 bytes / 385 lines
newline-stripped, sha256 `bdf45ae81509`.

---

## Paste everything below into PRISM

You are being asked to print one file from your own repository verbatim. Pure
introspection: do not build anything, do not report frictions, do not comment on
the content.

**Reply budget: this file is about 22 KB, so it should fit in a single reply
under roughly 30,000 characters.** If it does not, stop at a heading boundary,
state the exact line number you stopped at, and I will ask for the remainder.

Paste `prism-core/context/modules/static/tools/chart_context.md` in full, inside
a single fenced block, exactly as it exists on disk — every blank line, every
trailing space, every code fence. Do not reflow, do not fix typos, do not
normalise whitespace, do not add or remove a trailing newline.

Before the block, give one line: byte count and line count measured with any
single trailing newline stripped, plus `sha256[:12]` of those same bytes.

After the block, answer in one sentence each:

1. Is this file served to the model exactly as it appears on disk, or is it
   templated, trimmed, or wrapped by the context loader before delivery? If it
   is transformed, name the function and file that does it.
2. What is its registry entry — `module_id`, `pillar`, `order`, `source`, and
   any `footer_note` — pasted verbatim from the registry.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
