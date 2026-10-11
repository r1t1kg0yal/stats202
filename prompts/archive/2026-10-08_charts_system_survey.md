---
class: context-extraction
topic: the whole production charts system as it is today -- inventory, entry points, briefing, delivery, studio, QC, runtime, tests, telemetry, measured behaviour
expected_reply: ~100-150 KB; may be split across messages at section boundaries
created_at: 2026-10-08
sent: yes
status: ANSWERED
answered_at: 2026-10-11 (screenshots of PRISM's reply, folded the same day)
follow_up: 2026-10-11_chart_parity_round2.md (sandbox-side namespace, delivery
  placeholders, units.py, test_chart_characterization status)
companion: 2026-10-08_chart_agent_loose_ends.md (byte parity of the agent pair,
  image promotion, the sub-agent deadline, 00-charts-system.md, the core.py
  offset). This prompt does not repeat those questions.
trigger: >
  prism/subagents.md is current as of 2026-10-08, but almost everything around
  it that describes charts is stamped July or August: codebase-tree.md §8
  (inventory 2026-08-09, with an open WARN on where the studios live),
  vision-qc.md (2026-07-11), mcp-utils.md (2026-07-11), context-system.md and
  mcp-tools.md (2026-08-09), the §2.1 briefing-seam audit (2026-08-20), and
  the §8 "no telemetry" claim (2026-08-20). We have also never had production
  numbers for how the chart agent actually behaves.
reply_folds_into:
  - prism/codebase-tree.md (§8 inventory, §10.1 pins, §12 sandbox)
  - prism/subagents.md (§1 topology, §2.1 briefing seam, §4 lifecycle, §8 telemetry, §10.4-10.6)
  - prism/vision-qc.md
  - prism/code-sandbox.md (§1.3, §6.3)
  - prism/mcp-utils.md (§5 studio)
  - prism/dashboards-portal.md (if the studio routes moved)
  - prism/_changelog.md
  - staging/README.md and projects/altair/README.md (priorities, from §11)
---

**Staging-side note -- do NOT paste this header into PRISM.**

Why this prompt exists. Staging develops the chart engine and the sub-agent
pair, but it has been reasoning about the system around them from snapshots
that are one to three months old. Four decisions depend on a fresh survey:

1. **Where to spend the next staging cycle.** §11 asks for measured production
   behaviour: status mix, retries, timeouts, top findings, which chart types
   are used. That replaces guesswork with a ranking.
2. **Whether the main agent's briefing seam is still empty.** In August it was
   one sentence in `code_sandbox_context.md`. Since then the `chart_agent`
   description grew and a Core Context file appeared. §4 re-walks every
   surface.
3. **Whether vision QC still runs on the chart path at all**, now that the
   sub-agent is told to look at its own renders (§7).
4. **Which `prism/` files need a WARN or a rewrite.** Every section states the
   belief we hold, with its date.

---

## Paste everything below into PRISM

This is read-only source introspection so we can update external
documentation about how you work. Do not build a chart, do not run an
analysis beyond the read-only measurements §11 asks for, do not edit or create
any file, and do not report frictions.

Answer from live source and stored data, not from remembered context, a
context module, or a previous turn's summary. Open the file and cite it. Each
section opens with what we currently believe and when we last checked it.
Where your live source disagrees, say so explicitly and correct it. The
beliefs may be stale; that is why we are asking.

Give repository-relative paths from the `prism-main` root, with `path:line`
citations. Quote signatures, constants, dict literals and short code blocks
**verbatim in fenced code blocks**; do not paraphrase them. For numbers, say
how you measured and over what window.

If the reply is long, split it across messages at section boundaries and end
each part with "continued". If part of this prompt cannot be answered, add a
brief `## Could not resolve` section at the end listing what you tried and
what blocked it.

---

## 1. Inventory of the charts system

*Our belief (2026-08-09, partly 2026-09-04).* The engine is
`prism-core/prism_mcp/chart_render/` (`core.py`, `house_style.py`, `units.py`,
`__init__.py`). The trusted-side wrapper is
`prism-core/prism_mcp/utils/chart_functions.py`. The two studios
(`chart_functions_studio.py`, `chart_functions_studio_tables.py`) moved from
`prism_mcp/utils/` to `prism_mcp/chart_render/` in a 2026-09-04 MR. We do not
know whether a `utils/` shim was left for `composer_views.py`, or where
`vega_node_check.py` lives now. The sub-agent pair is `core/chart_agent_tool.py`
and `prism-core/prism_mcp/tools/chart_exec.py`, with
`prism_mcp/tools/artifact_report.py`, `prism_mcp/tools/sandbox_rollout.py`,
`prism_mcp/sandbox/chart_names.py` and `prism_mcp/utils/chart_call_log.py`
around it.

1. List every file that is part of the charts system today: engine, wrapper,
   studios, units, render checks, the agent pair and its helpers, context and
   corpus files, Core Context files, tests and golden fixtures, and any
   Composer view or template that exists only for charts. For each, give the
   path, bytes, line count, and last commit date and author if you can read
   history.
2. Is there anything under `prism_mcp/utils/` that re-exports or forwards to a
   studio module? Who imports each studio module? Give `path:line` for each
   importer.
3. Paste the public surface of `prism-core/prism_mcp/chart_render/units.py`:
   every top-level function and constant, with signatures. It is PRISM-owned
   and staging runs against a stub.
4. Paste `prism-core/prism_mcp/chart_render/__init__.py` and
   `prism-core/prism_mcp/utils/chart_functions.py` verbatim. Both are small.

## 2. Every way a chart gets made in production

*Our belief (2026-08-20 / 2026-09-26).* The only live path is main agent ->
`chart_agent` -> `render_charts`. `execute_analysis_script` binds no chart
symbols. `prism_mcp/utils/background_execution.py:276` injects a chart import
line into detached scripts. Dashboards (ECharts) are a separate system.

1. Search for every call of `make_chart`, `make_table`, `make_2pack_*`,
   `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid`, `build_charts`,
   `ChartSpec(` and `register_studio` outside `chart_exec.py` and the engine
   itself. Give `path:line` for each, and say what code path reaches it.
2. Is `background_execution.py:276` still live? What runs detached scripts
   today, and can one of them render a chart?
3. Which non-Composer flows produce charts: report mode, email replies,
   scheduled jobs, the observatory, others? For each, name the agent or
   specialization that calls `chart_agent`, and cite the line that puts
   `chart_agent` into that flow's tool list.
4. What is the infographic engine that shares `artifact_report.py`? Give its
   entry point, how it is invoked, whether it is reachable in production today
   (and behind which flag, if any), and whether it renders through
   `chart_render` or something else.
5. Does any code path turn an Altair chart into a dashboard component or the
   reverse: a Composer drag of a chart PNG into a dashboard, or a dashboard
   embedding an Altair PNG?

## 3. Agent topology and models

*Our belief (2026-08-21 / 2026-10-08).* The main agent (`ClaudeWithMCP`) plus
three sub-agents appended in the tool-list builder: `chart_agent` (AgentTool,
`CHART_AGENT_MODEL_KEY = "opus"`, `CHART_AGENT_EFFORT = "low"`),
`web_search_agent` (AgentTool, hardcoded `gpt-3.5-turbo`) and `ticket_agent`
(FunctionTool). The builder lives at `core/adk_local_tools.py:188-192`,
mirrored at `core/adk_tool_source.py:189-195`.

1. Paste the current tool-list builder lines on both paths. Is there any
   sub-agent beyond these three?
2. For each agent, give the model id it resolves to today and the effort
   level, with the line that sets each.
3. Which model and effort does the main agent use for a default Composer turn,
   for report mode, and for email?

## 4. How the main agent is told to brief `chart_agent`

*Our belief (2026-08-20).* Apart from the tool description, these surfaces
shape a `chart_agent` request:

- `context/modules/static/core/code_sandbox_context.md:83`, always-on, one
  sentence;
- `prism_mcp/tools/global_tools.py:91-93`, L1;
- `prism_mcp/tools/context_tool.py:351-352`;
- `composer_prompt.py:194-198` (`_IMAGE_RENDERING_RULE`);
- report-mode instruction files, which say only to give `chart_agent` the
  exact title.

No few-shot example exists, nothing tells the main agent to name columns,
date range or units, and the request is one free-text `request` string with
no `input_schema`.

1. Re-walk the repository and list every surface the main agent can see that
   mentions `chart_agent`, charts or tables, other than `00-charts-system.md`
   (asked separately). For each, give `path:line`, whether it is always-on,
   registered or L1, and the exact text.
2. Does any of them now contain an example request, or tell the main agent to
   describe columns, date range, units or the data source?
3. Is `chart_agent` still declared with no `input_schema`, so ADK synthesises a
   single `request: string`?
4. How does report mode brief `chart_agent` today? Paste the relevant passages
   from the report instruction files.

## 5. Delivery: how a rendered PNG reaches a person

*Our belief (2026-08-20).* On Composer, `generate_download_links_for_sandbox`
mints short links, the reply carries `![title](short_url)`, and
`composer_views._rewrite_answer_chart_imgs` (`composer_views.py:210`) rewrites
image refs for the browser. Other media get S3 paths only. `"gsai"` folds into
`COMPOSER`.

1. For each medium (Composer, email, report, CLI or scheduled), trace how a
   chart PNG ends up in front of a person. Name the functions, with
   `path:line`.
2. Paste the signature and return shape of
   `generate_download_links_for_sandbox`. What does a short link resolve to,
   how long does it live, and who can open it (session owner only, anyone
   with the link, Kerberos-gated)?
3. In email, are charts inline attachments, links, or both? Which code
   decides?
4. If `===CHART_DELIVERY_START===` / `===CHART_DIAGNOSTICS_START===`
   sentinels, an `===CHART_IMAGE_TRANSPORT===` block, or a `[[image: ...]]`
   marker survives into a final answer, does any code strip or rewrite it
   before a person sees it? Cite the lines, or answer "none".
5. Paste `_rewrite_answer_chart_imgs` and `_IMAGE_RENDERING_RULE` as they are
   now.

## 6. The studio: click-to-edit

*Our belief (2026-08-21).* Each render persists `{chart_id}.spec.json`,
`{chart_id}.meta.json` and `{name}_editor.html`, plus a `png_path -> chart_id`
entry in `{session}/charts/chart_manifest.json` (tables:
`table_manifest.json`). `composer_views.py:236` resolves click-to-edit through
that manifest. The merge is a naked get/mutate/put. `S3BucketManager.put`
has no conditional-put parameter.

1. Trace click-to-edit end to end: the Composer route, the view function, how
   it finds the spec, what it renders, and how an edit is saved and
   re-rendered. Give `path:line` at each hop.
2. Is the manifest merge (`_persist_editable_spec` and
   `persist_editable_table`) still a naked get/mutate/put in production, or is
   it serialised (lock, ETag, retry)? Does `S3BucketManager.put` accept an
   `IfMatch` or ETag argument today?
3. How often is the studio actually used? Count editor opens and saves over
   whatever window is recorded, and say where you counted them.

## 7. Vision QC on charts

*Our belief (2026-07-11).* `chart_functions.py::_check_chart_quality_safe` ->
`vision_functions.py::check_chart_quality` is an active post-render gate. It
fails open on service errors and returns false on an explicit BAD verdict.
`describe_images` is a separate path. We have not checked whether QC runs on
the `render_charts` path since the sub-agent migration.

1. Is `_check_chart_quality_safe` (or any vision call) reachable from
   `render_charts` today? Trace it, or say "not reachable" and cite where the
   chain breaks.
2. If it is reachable: which model, what prompt (paste it), what latency and
   cost per chart if recorded, and what happens to a BAD verdict? Does the
   chart still ship? Does the sub-agent hear about it?
3. Is `describe_images` called on charts anywhere in production?

## 8. Runtime: where chart code actually executes

*Our belief (2026-08-20 / 2026-09-26).* `render_charts` asks
`sandbox_rollout.decide()`. With no `sandbox.analysis` config it runs
in-process through `core.code_execution._execute_sync` on a worker thread,
under `CHART_EXECUTION_TIMEOUT_SECONDS`. There is no separate sandbox image;
the Lambda/Fargate target in `docs/analysis-sandbox.md` is not built. Pins:
`altair==4.2.2`, `numpy==1.26.4`, `pandas==2.0.3`, `pillow==12.2.0`,
`vl-convert-python==1.9.0.post1`. `google-adk` 2.4.0, `google-genai` 2.11.0,
`litellm` 1.91.3.

1. What does production's sandbox configuration say today? Is any user,
   environment or percentage diverted to `run_in_sandbox`? Paste the config
   block and the `decide()` branch that reads it.
2. Does `run_in_sandbox` have a working executor in production, or does it
   fail closed? Has the Lambda/Fargate decision in `docs/analysis-sandbox.md`
   moved?
3. Which fonts do production chart renders actually use? Does the directory
   `_gs_font_dir()` resolves to exist and contain GS Sans? Paste the resolved
   path and a directory listing.
4. Are `node` and the vega packages that `vega_node_check` calls installed in
   the production image? What happens when they are missing?
5. Report the installed versions, read from the running environment, of:
   `altair`, `vl-convert-python`, `pandas`, `numpy`, `pillow`, `google-adk`,
   `google-genai`, `litellm`, `jsonschema`.
6. What is `CHART_EXECUTION_TIMEOUT_SECONDS` today?

## 9. Tests and CI for charts

*Our belief (2026-08-09).* `prism-core/tests/test_chart_characterization.py`
with 24 golden spec fixtures under `prism-core/tests/golden/chart_specs/` is
the only chart test, and it enforces the import closure of `chart_render`.

1. List every test file in `prism-main` that exercises the engine, the
   wrapper, the studios, `chart_exec.py`, `chart_agent_tool.py` or
   `artifact_report.py`, with its test count.
2. How many golden fixtures exist today, and when were they last regenerated?
3. Does CI run these tests? Cite the CI config lines. What was the most
   recent result?

## 10. Telemetry and logs

*Our belief (2026-08-20, with a 2026-08-21 qualifier).* There is no telemetry
on the chart path beyond one `logger.info` line in `chart_exec.py`.
`telemetry.record_tool_call` counts `chart_agent` invocations by name at
`gs_llm2.py:2777-2803`. Nothing records calls per invocation, attempts to
success, timeout rate or failure classes. Staging's copy of `chart_exec.py`
calls `record_render_call` from `prism_mcp.utils.chart_call_log`.

1. Paste the public surface of `prism_mcp/utils/chart_call_log.py`: every
   function signature, what each call records, and where the records are
   stored.
2. List every other place that records anything about chart rendering
   (metrics, thought trail, usage telemetry, S3 logs), with `path:line`.
3. Does anything aggregate those records into a dashboard, report or metric?

## 11. Measured production behaviour

Compute these from whatever production records you can read: the call log
from §10, thought trails, telemetry. State the window, the source and the
query or script you used. Report only what the data supports, and say which
items are not recorded at all rather than estimating them.

1. Number of `chart_agent` invocations, and the number of distinct users and
   sessions behind them.
2. `render_charts` calls per invocation: the distribution, plus the share of
   invocations that hit the five-call ceiling.
3. Status mix across all `render_charts` calls: OK, RETRYABLE, NO_ARTIFACTS,
   FATAL. Within FATAL, how many were timeouts, blocked by a pre-exec gate, or
   a bad CSV path.
4. The 15 most frequent RETRYABLE findings, with their message text as
   recorded and their counts.
5. Wall-clock latency of a `chart_agent` invocation: median, p90, max.
6. PNGs delivered per invocation, and the share of turns that fan out to two
   or more `chart_agent` calls.
7. Usage by API: `make_chart` by `chart_type`, `make_table`, each composite
   (`make_2pack_*` ... `make_6pack_grid`), facet grids, `build_charts`.
8. Invocations that ended with no PNG at all: the count, and the reply text
   from five examples.

## 12. The chart agent's context, measured now

*Our belief (2026-08-20).* `_CORPUS_SOURCES` is a hardcoded tuple of seven
files in the order hub, colors, dual_axis, annotations, composites, grids,
tables. The full instruction (contract + corpus) was 69,988 chars as
installed. `CACHE_TTL = "1h"`. Token counts are not instrumented.

1. Paste `_CORPUS_SOURCES` as it is now.
2. Measure `len(_OPERATING_CONTRACT)`, `len(_chart_corpus())` and the full
   instruction string in chars, and the corpus in bytes. Label which figure is
   chars and which is bytes.
3. Is there any record of prompt-cache reads versus writes for the
   `chart_agent` model calls? If so, give the hit rate over a recent window.
4. Is a token count for the sub-agent's input recorded anywhere now?

## 13. Reported problems

1. Search the ticket store, or wherever `ticket_agent` files tickets, for
   tickets in the last 30 days that mention charts, tables, `chart_agent`,
   `render_charts`, the studio or images. List each with date, title and
   status.
2. Is there any user feedback signal (thumbs, ratings, comments) attached to
   Composer turns that produced charts? Give counts, and quote up to ten
   negative comments verbatim.

## 14. Change history across the charts system

If you can read history, list every commit since 2026-09-01 that touches any
file from your §1 inventory. Give the short sha, date, author, MR number,
subject and the files touched. We will work out which ones are staging
promotions; we just need the full list.

---

## Reply structure

Use one `##` heading per section, numbered as above, with the sub-answers in
order. Lead each section with one line: **CONFIRMED**, **CORRECTED** or
**PARTLY CORRECTED** against the stated belief. Put measurements in tables.
Put long verbatim pastes in fenced blocks at the end of the section they
belong to.
