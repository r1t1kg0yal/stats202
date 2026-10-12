---
class: context-extraction
topic: chart round 2 -- the sandbox render path, delivery placeholders, units.py, the 00-charts-system.md description, chart tests, what the NO_ARTIFACTS calls were
expected_reply: ~25-40 KB (sandbox_rollout.py + chart_names.py + units.py whole, short verbatim excerpts, a NO_ARTIFACTS classification)
created_at: 2026-10-11
sent: no
status: OPEN
trigger: >
  Production diverts every attributed render_charts call to the prism-sandbox
  gateway, and the staging harness only runs the in-process path. The sandbox
  side of a diverted call, the placeholder references the delivery block
  carries, and PRISM's units.py are all unseen here, and 28.5% of production
  render_charts calls returned NO_ARTIFACTS.
reply_folds_into:
  - projects/altair/prism_mcp/tools/sandbox_rollout.py, prism_mcp/sandbox/chart_names.py, prism_mcp/chart_render/units.py (verbatim mirrors)
  - projects/altair/dev/test_chart_exec.py (a 'sandbox' layer)
  - prism/subagents.md (§4 lifecycle, §8.1 what the NO_ARTIFACTS calls were), prism/code-sandbox.md, prism/codebase-tree.md
  - prism/_reference/00-charts-system.md (description line)
  - prism/_changelog.md
---

**Staging-side note -- do NOT paste this header into PRISM.**

None of this blocks promoting the engine; that is
`2026-10-11_altair_promotion_readiness.md`. Two earlier sections left this
prompt: the chunk-hash parity check (PRISM's `old/` comparison answered it for
`core.py`, and the readiness prompt covers the context files) and ADK plugin
propagation (answered by the 2026-10-11 OKF reply §4.1; the runtime check is
readiness §6).

Why this prompt exists.

1. **The production render path is untested here.** `decide()` diverts every
   attributed caller to the gateway sandbox, where `artifacts` comes back empty and
   `chart_paths` arrive through `adopt`. The harness only runs in-process. You
   chose to ask first and build the sandbox layer after: §1 is what it needs.
2. **Engine-side save_as fix (2026-10-11)** slugs whitespace out of keys because
   PRISM's marker regex cannot match one. §2.4 checks whether the Composer
   rewrite path has the same blind spot.
3. **NO_ARTIFACTS is 28.5% of production calls** and almost never the final
   status. §6 asks what those scripts were, to decide between a contract fix
   (stop probing through `render_charts`), an engine fix, or a PRISM-side
   change to what counts against the ceiling.

---

## Paste everything below into PRISM

This is read-only source introspection so we can keep external documentation
and a staging copy of the chart engine in sync with you. Do not build a chart,
do not edit or create any file in the repository, and do not report frictions.
You may run read-only Python in `execute_analysis_script` to read files and
compute hashes.

Answer from live source, not from remembered context, a context module, or a
previous turn's summary. Open the file and cite it. Where your live source
disagrees with a belief stated below, say so and correct it.

Give repository-relative paths from the `prism-main` root, with `path:line`
citations. Quote signatures, constants and code **verbatim in fenced code
blocks**; do not paraphrase them.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end listing what you tried and what blocked it.

---

### 1. The sandbox render path

Our belief: `core/config/environments/prod/common.yaml:247-252` enables
`sandbox.analysis` with a `gateway` executor (`prism-sandbox/execute_analysis_script`)
and no allow or deny list, so `decide()` diverts every attributed caller. On
divert, `render_charts` reads only `stdout`; `chart_paths` come back through
`adopt=recorder.adopt`; `artifacts` is empty because `_wrap_chart_func` and
`recorder.record` exist only in the in-process namespace.

1. Paste `prism-core/prism_mcp/tools/sandbox_rollout.py` **whole**.
2. Paste `prism-core/prism_mcp/sandbox/chart_names.py` **whole**.
3. On a diverted `render_charts` call, which code builds the namespace the chart
   script runs in on the sandbox side, and where does it live (repository path,
   or a separate image)? Paste the function. Specifically: are `make_chart`,
   `make_table` and the packs wrapped there, and if so with what; how does the
   sandbox side tell `render_charts` which PNGs it wrote (a stdout protocol, a
   manifest key, a listing); and what does `adopt` receive.
4. Inside the sandbox image: does `chart_render.core.register_studio()` run, so
   the editable-spec manifest is written? Is `web/backend_django/fonts` present,
   or does `_gs_font_dir()` return None and fall to system fonts? Quote the
   pins for `altair`, `numpy`, `pandas`, `pillow` and `vl-convert-python` from
   `requirements-sandbox-arm64.txt` (path and line).
5. The chart-call records for 2026-09-10 to 2026-10-11 carried 1,654 artifact
   records over 1,746 calls, which does not fit "artifacts is empty on divert".
   Which field of the chart-call manifest records whether a call ran in the
   sandbox or in-process, and how many calls in that window ran each way?

### 2. Delivery placeholders

1. Paste `_defers_to_the_renderer()` and the branch of
   `generate_download_links_for_sandbox` that returns placeholder references,
   verbatim, with one example of the placeholder string it produces.
2. Paste the regexes `composer_views._sentinel_artifact_paths` and
   `_resolve_link_sentinels` use.
3. Which surfaces take the placeholder branch, and which get real `short_url`s?
4. If a chart's S3 key contains a space (`sessions/x/US 10y yield_ab12cd01.png`),
   does `_rewrite_answer_chart_imgs` still resolve `![title](<reference>)` for
   it? Answer from the regexes.

### 3. `units.py`

Paste `prism-core/prism_mcp/chart_render/units.py` **whole**.

### 4. `00-charts-system.md`

1. Quote the full `description:` value from the front matter of
   `prism-core/context/modules/static/core/charts_system/00-charts-system.md`.
2. Does anything read this file other than the OKF floor in
   `prism-core/context/okf.py`? Cite each reader.

### 5. Tests

1. Does `prism-core/tests/test_chart_characterization.py` exist? If yes, its
   test count and the number of golden files under `tests/golden/chart_specs/`.
2. List every test file that imports `prism_mcp.chart_render`,
   `prism_mcp.utils.chart_functions` or `prism_mcp.tools.chart_exec`, with its
   test count.

### 6. What the NO_ARTIFACTS calls were

In the 2026-09-10 to 2026-10-11 chart-call records, 498 of 1,746 `render_charts`
calls returned `NO_ARTIFACTS`, but only 1 of 807 invocations ended on it. So
the sub-agent spends calls against `CHART_ATTEMPT_CEILING` on scripts that
render nothing and then goes on to render.

1. Pick 10 `NO_ARTIFACTS` attempts from that window, spread across sessions,
   and for each give the `chart_calls/<agent_id>__<token>/attempt_NN.py` path,
   its attempt number, the status of the next attempt in the same invocation,
   and the script **verbatim** if it is 40 lines or fewer (first 40 lines
   otherwise).
2. Classify all 498 by what the script did, using the code itself: inspected
   the data only (`print`, `.head()`, `.describe()`, `.columns`), built a
   chart object without calling a chart function, called a chart function
   that raised before writing, wrote a PNG whose key does not end `.png`, or
   other. Give the count per class, and say how you classified (a regex over
   the scripts is fine; name it).
3. Quote the text `render_charts` returns for a `NO_ARTIFACTS` call, and the
   line that counts it toward `CHART_ATTEMPT_CEILING`.

---

## Reply structure

Use one `##` heading per section above, numbered the same, with sub-answers in
order. Put whole-file pastes under `## Appendix: whole files`, one fenced block
per file headed by its path.
