---
class: context-extraction
topic: chart_agent pair after the seven October MRs -- byte parity, image promotion, deadline, Core Context, core.py offset
expected_reply: ~80-120 KB (whole-file pastes on any parity miss, plus a def table for core.py)
created_at: 2026-10-08
sent: yes
status: ANSWERED
answered_at: 2026-10-11 (screenshots of PRISM's reply, folded the same day)
follow_up: 2026-10-11_chart_parity_round2.md (chunk-hash parity for core.py and
  the context files, the two inferred hashes, ADK plugin propagation)
trigger: >
  Staging folded !1846 / !1887 / !1880 / !1896 / !1895 / !1939 / !2004 into
  projects/altair/altair-payload/ from review-page screenshots. Line counts
  match the review pages, but no whole file has been byte-verified, and
  several behaviours the new code depends on live in files staging has never
  seen (gs_llm2 image promotion, the sub-agent deadline, 00-charts-system.md).
reply_folds_into:
  - prism/subagents.md (§1.1 open item, §1.2, §7, §10)
  - prism/context-system.md (if 00-charts-system.md is a registered or always-on module)
  - prism/_changelog.md
  - projects/altair/altair-payload/ (any file that comes back DIFFER)
  - projects/altair/core/configs/file_types.py, prism_mcp/tools/artifact_report.py (mirrors)
  - projects/altair/README.md parity table
---

**Staging-side note -- do NOT paste this header into PRISM.**

Why this prompt exists. Five things are unresolved after the 2026-10-08 pass.

1. **Byte parity is claimed by line count only.** The hashes in §1 let PRISM
   answer MATCH / DIFFER per file instead of us transcribing more screenshots.
   A DIFFER on the four files we believe are verbatim gets a whole-file paste.
2. **`attach_renders` may not do anything.** The new contract tells the
   sub-agent to LOOK AT its renders, but the code that turns `[[image: key]]`
   into pixels lives in `core.gs_llm2`, the *main* agent's class. The chart
   agent runs on its own ADK Runner. If promotion never runs there, the sub-agent
   is told to look at pictures it never receives.
3. **The description promises a deadline and a cancellation line** that nothing
   in `prism/` documents.
4. **`00-charts-system.md` is the main agent's half of the chart contract**, and
   we have only seen fragments of it (!1895 moved it, !2004 edited it).
5. **PRISM's `core.py` has `_auto_melt_for_multiline` 4 lines lower** than our
   last promotion snapshot. Something we never received sits above it.

Sections 1-4 are blocking. 5-9 are loose ends the curated docs need.

---

## Paste everything below into PRISM

This is read-only source introspection so we can update external
documentation about how you work. Do not build a chart, do not run an
analysis, do not edit or create any file, and do not report frictions.

Answer from live source, not from remembered context, a context module, or a
previous turn's summary. Open the file and cite it. Where your live source
disagrees with a belief stated below, say so explicitly and correct it; the
beliefs are what we currently have written down, and they may be stale.

Give repository-relative paths from the `prism-main` root, with `path:line`
citations. Quote signatures, constants, dict literals and code blocks
**verbatim in fenced code blocks**; do not paraphrase them.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end listing what you tried and what blocked it.

---

### What we already have -- do not re-derive it

We hold copies of these files as they look after the seven merge requests
!1846, !1887, !1880, !1896, !1895, !1939 and !2004:

- `core/chart_agent_tool.py`: `_OPERATING_CONTRACT`, `MAX_TRAILER_RENDERS = 20`,
  `_image_transport_trailer`, the `chart_agent` description, and
  `result_trailer=_image_transport_trailer` on `subagent_tool(...)`.
- `prism-core/prism_mcp/tools/chart_exec.py`: `ChartInvocation` with `calls` and
  `rendered`, `delivered` as a property, `adopt_renders`, the two-bound
  ceiling, the refusal that re-lists earlier renders with `attach=False`, and
  `_SHAPE` with `attach_renders=True`.
- `prism-core/prism_mcp/tools/artifact_report.py`: all 153 lines.
- `core/configs/file_types.py`: we read the file down to `EMAIL_EXTS` and do
  not know whether anything follows.

You do not need to explain any of that. Section 1 checks that our copies are
the same bytes as yours.

---

## 1. Byte parity (blocking)

For each path below, report: the path you resolved, byte size, line count as
`len(text.splitlines())`, the last byte as a Python `repr`, and the first 16 hex
digits of `sha256` over the raw bytes. Then mark it **MATCH** or **DIFFER**
against our numbers. Say how you measured; for example:

```python
import hashlib, pathlib
b = pathlib.Path(path).read_bytes()
print(path, len(b), len(b.decode("utf-8").splitlines()), repr(b[-1:]),
      hashlib.sha256(b).hexdigest()[:16])
```

**Group A -- we believe these are verbatim. On DIFFER, paste the whole file.**

| Path | Bytes | Lines | Last byte | sha256[:16] |
|---|---|---|---|---|
| `core/chart_agent_tool.py` | 12698 | 241 | `b')'` | `be3d98ef4fcd2deb` |
| `prism-core/prism_mcp/tools/chart_exec.py` | 42209 | 895 | `b'\n'` | `1fc52bd1ba71da3a` |
| `prism-core/prism_mcp/tools/artifact_report.py` | 6693 | 153 | `b'\n'` | `fcdbce1d1c7d3932` |
| `core/configs/file_types.py` (paste whole file regardless) | 1842 | 41 | `b'\n'` | `794a0aaee0754d4e` |
| `prism-core/prism_mcp/chart_render/__init__.py` | 882 | 18 | `b')'` | `a2d6203351e2f500` |
| `prism-core/prism_mcp/utils/chart_functions.py` | 1393 | 33 | `b'\n'` | `c176f4ba3adb467f` |
| `prism-core/prism_mcp/utils/vega_node_check.py` | 3899 | 123 | `b'\n'` | `1d9a5f18bf60b175` |

**Group B -- our copies carry edits we have not promoted, so DIFFER is
expected. Report the numbers only; do not paste.**

| Path | Bytes | Lines | sha256[:16] |
|---|---|---|---|
| `prism-core/prism_mcp/chart_render/core.py` | 1711074 | 40438 | `8f2c58ea769fec64` |
| `prism-core/prism_mcp/chart_render/house_style.py` | 25860 | 673 | `7a0f326a32cea63b` |
| `prism-core/prism_mcp/chart_render/chart_functions_studio.py` | 505482 | 12593 | `5122e0eb5257f113` |
| `prism-core/prism_mcp/chart_render/chart_functions_studio_tables.py` | 243262 | 5878 | `29309f77d82d50a2` |
| `prism-core/context/modules/static/tools/chart_context.md` | 41878 | 550 | `35cfcd6a65a10588` |
| `.../static/tools/charts/chart_context_annotations.md` | 10955 | 195 | `691791e3c38c67d6` |
| `.../static/tools/charts/chart_context_dual_axis.md` | 7621 | 205 | `efb7394a4b40af14` |
| `.../static/tools/charts/chart_context_composites.md` | 8987 | 197 | `7abdbb568a2eab99` |
| `.../static/tools/charts/chart_context_tables.md` | 15270 | 362 | `29eb2c14f759a646` |
| `.../static/tools/charts/chart_context_grids.md` | 5157 | 131 | `a01e1553a562f3d1` |
| `.../static/tools/charts/chart_context_colors.md` | 10132 | 223 | `2b5e6e240172cc0f` |

Also for Group B context files: paste every line of `chart_context.md` and
`chart_context_tables.md` that contains `source=` or `Source:`, with its line
number. We transcribed one wrapped line of the !2004 hunk by eye.

## 2. Does image promotion reach the chart sub-agent? (blocking)

Our belief: `core.gs_llm2` holds `_IMAGE_MARKER_RE` and a promotion block. It
finds `[[image: <s3 key>]]` in a tool result and moves the image onto a
user-role item the model can see. `render_charts` now ends its diagnostics block
with one marker per PNG it wrote, so that the chart agent sees its own output.
The `chart_agent` runs on its own ADK `Runner` built by
`core.agent_base.subagent_tool`.

1. Paste `_IMAGE_MARKER_RE` and the whole promotion code path verbatim, with
   `path:line`. Include whatever fetches the S3 object and decides its MIME
   type, and say whether it reads `PROMOTABLE_IMAGE_MIME_BY_EXT` or `IMAGE_EXTS`
   from `core.configs.file_types`.
2. For each of these three cases, say whether the promotion code runs, and
   cite the line that makes it so:
   - (a) a tool result in the main agent's own loop;
   - (b) a `render_charts` result inside the `chart_agent` sub-agent's loop on
     its separate Runner;
   - (c) the `AgentTool` result the main agent receives from `chart_agent`, which
     carries the `===CHART_IMAGE_TRANSPORT===` trailer.
3. If (b) runs through code other than `gs_llm2`, such as `agent_base`,
   `subagent_model`, `_install_cache_and_io` or a LiteLlm hook, paste that path
   instead.
4. Is there a cap on promoted images per tool result, per model request, or
   per turn? Give the constant names, values and `path:line`, and what happens
   past each cap (oldest dropped, newest dropped, error, or silent). If one turn
   fans out to five `chart_agent` calls of up to 20 renders each, what does the
   main agent actually receive?
5. After promotion, does the `[[image: ...]]` text stay in the text the model
   reads, or is it stripped? Does the model see each image next to its key,
   or with no key?

## 3. The sub-agent deadline and the cancellation line (blocking)

The `chart_agent` description now says: "A run that produces no PNG answers one
plain sentence naming what stopped it, and a run past its deadline answers a
cancellation line."

1. Where is that deadline enforced? Give the file, the constant name, the value
   and `path:line`. Is it per `chart_agent` invocation, per model call, or per
   turn? How does it relate to `CHART_EXECUTION_TIMEOUT_SECONDS` in
   `chart_exec.py`, and what is that value now?
2. Paste the code that produces the cancellation line, and the exact string
   the main agent receives.
3. On that path, does `result_trailer` (`_image_transport_trailer`) still run?
   Do PNGs written before the deadline reach the main agent as pictures, as
   paths, or not at all? Paste the `run_async` region of
   `core/agent_base.py` (or wherever `result_trailer` is applied), including any
   `try` / `except` / `finally` and `CancelledError` handling around it.
4. "A run that produces no PNG answers one plain sentence": is that enforced in
   code anywhere, or only by `_OPERATING_CONTRACT`?

## 4. `00-charts-system.md` -- the main agent's half of the contract (blocking)

Our belief: `prism-core/context/modules/static/core/charts_system/00-charts-system.md`
carries YAML front matter with `type: Core Context`. !1895 moved it there and
!2004 edited it.

1. Paste the whole file verbatim, front matter included. Give its byte size and
   sha256[:16].
2. Where did !1895 move it from? List every other file in `charts_system/`.
3. What reads `type: Core Context`? Paste the loader code that branches on it.
   Is the file a `MODULE_REGISTRY` entry? Give its `order`, which bundles or
   specializations load it, and whether it is always-on. If it is not a
   registry entry, paste the code path that puts it into the main agent's
   context.
4. Does anything in it tell the main agent what to do with pictures in the
   `===CHART_IMAGE_TRANSPORT===` block, or with renders that appear there but
   not in the delivery block?

## 5. `core.py`: the 4-line offset and the !1939 call paths

In our last promoted snapshot, `def _auto_melt_for_multiline` sits 4 lines
higher than in yours (your !1939 page shows it at 29848).

1. If you can read history, list every commit since 2026-09-20 that touches
   `prism-core/prism_mcp/chart_render/core.py`. Give the short sha, date,
   author, MR number and subject. For any commit other than !1939, paste its
   diff.
2. Regardless, print the line number and name of every top-level `def` and
   `class` in `core.py`, one per line, as `<line> <name>`.
3. List every call site of `_auto_melt_for_multiline`, with `path:line` and its
   enclosing function. For each, say whether `_promote_index_to_x_column` runs
   on the same frame first. Does `_promote_index_to_x_column` exist in your
   `core.py`? If it does, give its line number.
4. If the !1939 MR description or commit message says which call path failed,
   paste it.

## 6. Other readers and consumers of the new surface

1. Search the repo for importers of `core.configs.file_types` and readers of
   `image_marker`, `IMAGE_EXTS`, `PROMOTABLE_IMAGE_MIME_BY_EXT` and
   `EMAIL_EXTS`. Give `path:line` for each.
2. Is `_IMAGE_MARKER` in `core/chart_agent_tool.py` referenced anywhere? We read
   it as dead since !1880.
3. Who reads `baggage_specialization_var` now that the trailer does not? Give
   `path:line` for each reader.
4. `artifact_report.py` has a second consumer, the infographic engine. Give its
   path and paste its `ReportShape(...)` construction verbatim. Does it set
   `attach_renders`?

## 7. History of the chart pair since 2026-09-26

If you can read history, list every commit since 2026-09-26 that touches any
of these:

- `core/chart_agent_tool.py`
- `prism-core/prism_mcp/tools/chart_exec.py`
- `prism-core/prism_mcp/tools/artifact_report.py`
- `core/configs/file_types.py`
- `prism-core/context/modules/static/tools/chart_context*.md`
- `prism-core/context/modules/static/tools/charts/*.md`
- `prism-core/context/modules/static/core/charts_system/`

Give the short sha, date, author, MR number and subject. Mark any commit that
is not one of !1846, !1887, !1880, !1896, !1895, !1939 or !2004.

## 8. Renders that reach the trailer but not the delivery block

In the current code, take one `chart_agent` invocation where call 1 is
RETRYABLE after writing chart A, and call 2 is OK and writes only chart B.
As we read it, the second report's delivery block lists only B's path and
link, while the trailer attaches pictures of both A and B. Confirm or correct
that from your live source. Then answer: is there anywhere else in the live
code (`gs_llm2`, the promotion path, Composer rendering, or
`00-charts-system.md`) where the main agent gets a path or link for chart A?
Cite `path:line`, or answer "nowhere".

## 9. The sandbox divert and `adopt_renders`

`adopt_renders` keys renders by the artifact `title` it reads from
`artifacts`. When `sandbox_rollout.decide()` diverts a run:

1. Do `recorder.chart_paths` and `artifacts` come back populated, titles
   included, the same as an in-process run? Paste the lines in `chart_exec.py`
   that rebuild them from the sandbox result.
2. What does `decide()` return in production today: divert or not, and with
   what reason string?

---

## Reply structure

Use one `##` heading per section above, numbered the same, with the
sub-answers in order. Put the §1 results in two tables mirroring ours, with a
MATCH / DIFFER column. Put whole-file pastes at the end, under
`## Appendix: whole files`, one fenced block per file headed by its path.
