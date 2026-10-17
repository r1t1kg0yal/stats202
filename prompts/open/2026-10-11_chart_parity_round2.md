---
class: context-extraction
topic: chart round 2 -- the sandbox render path, delivery placeholders, the 00-charts-system.md description, the render_charts trust gate, what the NO_ARTIFACTS calls were
expected_reply: ~25-40 KB (sandbox_rollout.py + chart_names.py + tool_path_scope.py whole, short verbatim excerpts, a NO_ARTIFACTS classification)
created_at: 2026-10-11
sent: no
status: OPEN
trigger: >
  Production diverts every attributed render_charts call to the prism-sandbox
  gateway, and the staging harness only runs the in-process path. The sandbox
  side of a diverted call and the placeholder references the delivery block
  carries are both unseen here, and 28.5% of production
  render_charts calls returned NO_ARTIFACTS.
reply_folds_into:
  - projects/altair/prism_mcp/tools/sandbox_rollout.py, prism_mcp/sandbox/chart_names.py, core/configs/tool_path_scope.py (verbatim mirrors or signature-exact stubs)
  - projects/altair/dev/test_chart_exec.py (a 'sandbox' layer)
  - prism/subagents.md (§4 lifecycle, §8.1 what the NO_ARTIFACTS calls were), prism/code-sandbox.md, prism/codebase-tree.md
  - prism/_reference/00-charts-system.md (description line)
  - prism/_changelog.md
---

**Staging-side note -- do NOT paste this header into PRISM.**

Send after the drop and after
`staging/prompts/open/2026-10-12_altair_post_drop_verify.md`. None of this
blocks the promotion, which the go/no-go reply
(`staging/prompts/archive/2026-10-11_altair_promotion_readiness.md`) cleared.
That reply also answered what this prompt used to ask about tests (no
`test_chart_characterization.py`, no chart goldens; the chart test files and
their counts are in `prism/codebase-tree.md` §8), about the sandbox fonts
(`containers/prism-sandbox/Dockerfile:146` copies them), and about ADK plugin
propagation (confirmed at runtime). §4 now asks for the trust gate
`chart_exec.py` gained in `bd1ff5297`: the staging harness stubs
`core.configs.tool_path_scope` from its one call site. Screenshots of
`units.py` (2026-10-17) answered what this prompt asked about it, and staging
now owns that file.

Why this prompt exists.

1. **The production render path is untested here.** `decide()` diverts every
   attributed caller to the gateway sandbox, where `artifacts` comes back empty and
   `chart_paths` arrive through `adopt`. The harness only runs in-process. You
   chose to ask first and build the sandbox layer after: §1 is what it needs.
2. **Engine-side save_as fix (2026-10-11)** slugs whitespace out of keys because
   PRISM's marker regex cannot match one. §2.4 checks whether the Composer
   rewrite path has the same blind spot.
3. **NO_ARTIFACTS is 28.5% of production calls** and almost never the final
   status. §5 asks what those scripts were, to decide between a contract fix
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
   the editable-spec manifest is written? Quote the pins for `altair`, `numpy`,
   `pandas`, `pillow` and `vl-convert-python` from
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

### 3. `00-charts-system.md`

1. Quote the full `description:` value from the front matter of
   `prism-core/context/modules/static/core/charts_system/00-charts-system.md`.
2. Does anything read this file other than the OKF floor in
   `prism-core/context/okf.py`? Cite each reader.

### 4. The `render_charts` trust gate

`chart_exec.py` (`bd1ff5297`, 2026-10-12) calls
`enforce_no_untrusted_content(file_path, tool='render_charts')` on every
`data_files` key and reports `UntrustedContentDenied` as a FATAL load failure,
logged through `get_service_logger("prism.security")`.

1. Paste `core/configs/tool_path_scope.py` **whole**.
2. Paste `get_service_logger` from `core/service_logging.py`, with its
   `path:line`.
3. Which prefixes does the register admit for a `render_charts` key today: the
   session's own prefix only, or others (shared data buckets, other users'
   sessions)? Cite the lines that decide it.

### 5. What the NO_ARTIFACTS calls were

In the 2026-09-10 to 2026-10-11 chart-call records, 498 of 1,746 `render_charts`
calls returned `NO_ARTIFACTS`, but only 1 of 807 invocations ended on it. So
the sub-agent spends calls against `CHART_ATTEMPT_CEILING` on scripts that
render nothing and then goes on to render. Those records predate the change
that names a record by the invocation's call count (`ladder_attempt` beside
it): in them `attempt_NN` is the ladder rung, so a revision after a clean
render overwrote `attempt_01.py`. Count on that, and say where a sampled
invocation shows it.

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
