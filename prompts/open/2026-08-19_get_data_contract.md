---
class: context-extraction
topic: get_data / Details full contract — the replacement for pull_plottool_data
expected_reply: ~20 KB
created_at: 2026-08-19
sent:
status: OPEN
trigger: >
  PRISM commit b6125045 (2026-08-13, Perre — "Stop teaching Prism to write
  pull_plottool_data") removed the helper from every dashboards context module
  in favour of `from prism_mcp.tools.data_tools import Details, get_data`.
  The 2026-08-10..08-19 context diff was folded into the echarts payload on
  2026-08-19, but the diff carried only a five-line call example — not the
  contract. Two WARN sentinels are open in prism/data-functions.md (§1.1, §2.2)
  and the echarts engine still has zero knowledge of get_data.
reply_folded_into:
  - prism/data-functions.md              # resolve the two WARN sentinels
  - prism/mcp-tools.md                   # get_data registered-tool row
  - projects/echarts/echarts-payload/echart_dashboard.py  # _PULL_PRIMITIVES + exec namespace
  - projects/echarts/echarts-payload/dashboards/pipelines.md  # stem table + provenance system value
  - projects/echarts/echarts-payload/dashboards_hub.md   # namespace/helper list
  - projects/echarts/echarts-payload/__init__.py         # module docstring
  - projects/echarts/prism_mcp/tools/data_tools.py       # NEW staging stub
  - projects/echarts/echarts-payload/test_prompts/*.md   # 6 of 8 still teach the retired helper
---

**Staging-side note — do NOT paste this header into PRISM.**

Why this prompt exists: our dashboard compiler infers a dataset's persisted CSV
stem by static-parsing `scripts/pull_data.py` for a known set of pull
primitives. `get_data` is not in that set, so a dashboard authored the new way
gets `dataset_<key>_unattached` or `dataset_<key>_silent_stale` from the
refresh-attachment audit even though the pull is correct. Fixing that needs the
real contract, not the example. Sections 1-4 are the blocking ones; 5-9 are what
we need to teach the skill spokes correctly.

The two open sentinels this reply should close are in `prism/data-functions.md`
§1.1 and §2.2.

---

## Paste everything below into PRISM

This is read-only source introspection for external documentation. Do not build
a dashboard, do not pull any data, do not edit or create any file, and do not
report frictions. Do not answer from remembered context or from documentation
where live source is available — read the source and cite it.

Give repository-relative paths from the `prism-main` root, with `path:line`
citations. Quote signatures, field definitions, docstrings and enum members
**verbatim in fenced code blocks**; do not paraphrase them.

**Reply budget: keep this under roughly 20,000 characters.** If you run long,
stop at a section boundary and name what remains.

### 1. The function

1.1 Locate `get_data`. Give its path and line. Paste its **complete signature
verbatim**, including every parameter, type annotation, and default.

1.2 Paste its **full docstring verbatim**.

1.3 Is it a coroutine (`async def`)? Is there any synchronous wrapper or
alternative entry point that does not require `await` / `asyncio.run`? Name it
if so.

1.4 Is `get_data` registered as an MCP tool, an importable helper, or both? If it
is registered, give the registration site and say whether the docstring is what
becomes the tool schema.

1.5 What does it **return**? Give the exact return type and, if it is a
structured object, its full field list. Specifically: does it return a
`pandas.DataFrame`, a path string, a summary object, or `None`?

### 2. The `Details` model

2.1 Locate `Details`. Give its path and line, and paste the **complete class
definition verbatim** — every field, type, default, and validator.

2.2 Do the same for every nested model it references (the symbols entries appear
to be `{"symbol": ..., "label": ...}` dicts — paste whatever model backs that,
and say whether `label` is required or optional).

2.3 Enumerate **every legal value of `source`**. We have only observed
`tsdb_eod`. Is this an `Enum`, a `Literal`, a validated string, or free text?
Paste the definition. For each legal value, state in one line which backend it
resolves to and whether it is EOD, intraday, or point-in-time.

2.4 Which fields are required and which are optional? Give the full
required/optional split, and note any field that is accepted but currently inert.

2.5 Are `start` / `end` strings, dates, or either? What formats are accepted, and
what happens when `end` is omitted?

2.6 Is `pydantic.TypeAdapter(Details).validate_python({...})` the intended
construction path, or can a caller construct `Details(...)` directly? If both
work, say which the context modules should teach and why.

### 3. Persistence — the part our compiler depends on

Our loader scans `<dashboard folder>/data/*.csv` and uses the **CSV filename stem
as the dataset key**. So the exact bytes on disk matter more to us than the
return value.

3.1 Given `get_data(session_path=f"{SESSION_PATH}/data", name="rates", details=...)`,
enumerate **every object key it writes**. Exact keys, not a description.

3.2 Is `{name}.csv` written? Is `{name}_metadata.json` written? If the metadata
sidecar exists, paste an example of its contents.

3.3 Does `name` reach the filename **verbatim**, or is it transformed —
suffixed (the way the legacy market helper appended `_eod` / `_intraday` from
`mode=`), slugified, lowercased, or namespaced? This is the single most
important answer in this prompt: if `get_data(name="rates")` can produce
anything other than `rates.csv`, say exactly what and when.

3.4 Note that `get_data` takes `session_path=` where the curated helpers take
`output_path=`. Is `session_path` here the **directory to write into**, or a
session root that gets a subdirectory appended? Trace it to the write call and
cite it. State the trailing-slash behaviour.

3.5 What is the **CSV shape**? Name the index/date column exactly as it appears
in the header row, its dtype, and its format. Does each `label` become a column
name verbatim? What happens if `label` is omitted — is the column named after
`symbol`?

3.6 Overwrite semantics: repeated calls to the same `name`, and what happens to a
prior CSV if the pull fails partway.

### 4. Execution context

4.1 Is `get_data` injected into the `execute_analysis_script` sandbox namespace,
or must an authored script import it explicitly? Cite the namespace construction.

4.2 Same question for the two dashboard execution paths:
`prism-core/dashboards/echart_dashboard.py::_build_dashboard_exec_namespace`
and the namespace used by `prism-core/dashboards/refresh_runner.py`. Paste the
current injected-name list for each so I can diff it against my copy.

4.3 Are `asyncio` and `pydantic` importable inside those execution contexts, and
are either of them blocked by the sandbox preprocessor guards?

4.4 **Is there already a running event loop** in any of: the initial sandbox
script exec, the in-process dashboard script exec, the clean refresh subprocess?
If yes for any of them, `asyncio.run()` would raise there — say which, and what
the correct call form is in that context.

4.5 Is there a timeout that a multi-symbol / long-range `get_data` call can
exceed in the ~90-second initial sandbox window? Any internal pagination or
concurrency?

### 5. Status of `pull_plottool_data`

5.1 Does `pull_plottool_data` still exist in `prism_mcp/utils/data_functions.py`?
Is it still injected into each of the three execution namespaces?

5.2 Is it deprecated (warning emitted), retired from authoring only, or removed?
Quote any deprecation shim or warning text.

5.3 Our census found ~100 imports across ~35 owners in persisted
`users/*/dashboards/*/scripts/pull_data.py`. Do those scripts still run today on
refresh? Is there a migration plan or a cutover date?

5.4 Same three questions for `pull_market_data`.

### 6. Discovery — how a symbol is found

6.1 Haver has a mandatory `explore_haver()` step before pulling. What is the
equivalent for `get_data`? Name the discovery helper, tool, or context module
that turns "I want the 10y SOFR swap rate" into a valid `symbol` string.

6.2 Is the symbol namespace the same one PlotTool expressions used (e.g.
`sofrswp2y`, `move_index`), or a new namespace? If a mapping exists, cite it.

6.3 What happens on an **unknown symbol** — raise, skip silently, or return a
column of NaN? What about a valid symbol with no data in the requested window?
Quote the error class and message if it raises.

6.4 Is there a maximum number of symbols per call, or a maximum date range?

### 7. Provenance

Our dashboards carry a `field_provenance` block per dataset column, stamped with
a `system` string. The rendered footer currently recognises `haver`,
`market_data`, `plottool`, `fred`, `bloomberg`, `computed`, `csv`.

7.1 What `system` value should a `get_data`-sourced column carry? Is there a
canonical string used anywhere in PRISM today, or should we mint one?

7.2 Does `get_data` emit anything that identifies the upstream system per symbol
— in the metadata sidecar, in `df.attrs`, or in the return object — that a
dashboard build could read rather than having the author hand-author it?

### 8. Context modules

8.1 List every context module under `prism-core/context/modules/static/` that now
mentions `get_data`, with its registry `order` and whether it is registered or
on-demand.

8.2 For the dashboards family specifically (`dashboards.md`, `dashboards_hub.md`,
`dashboards/*.md`): quote the current `get_data` passage from each file that has
one. I need to confirm my copies are byte-current after the 2026-08-13 change.

8.3 Is there a non-dashboards module that teaches `get_data` in more depth — a
data guide, an instruments module, a tools module? If so, name it and summarise
what it covers that the dashboards family does not.

### 9. One worked example

9.1 Paste a **complete, currently-correct** `scripts/pull_data.py` for a
two-symbol EOD rates pull that lands `data/rates.csv`, exactly as you would
author it today — imports, `SESSION_PATH`, the pull function, and the
module-level `PULLS` registry. This becomes the canonical example in our build
spoke, so it must be copy-paste correct.

9.2 If an intraday pull is possible, paste the one-line diff from 9.1 that makes
it intraday, and state the resulting CSV stem.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
