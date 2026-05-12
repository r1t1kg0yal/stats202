# ECharts Dashboards

- **Module:** `dashboards`
- **Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
- **Tier:** 2 (on-demand)
- **Scope:** ALL dashboard construction in PRISM. (One-off PNG charts in chat / email / report use Altair `make_chart()`, a separate module.)

A dashboard is a JSON manifest plus two small Python files. PRISM emits Python that produces structured JSON; the engine does the rest. **PRISM never writes HTML, CSS, or JavaScript** — every byte the browser sees is emitted by the rendering engine. The one exception is `tool_def.compute_js` (a JS string LITERAL embedded inside a Python dict that authors the manifest) — see §A's carve-out.

**ECharts is the ONLY sanctioned path for PRISM dashboards.** `compile_dashboard(manifest)` and the v2 entry points (`run_pull` / `build_dashboard` / `refresh_dashboard`) are the entire surface. Hand-rolled HTML / CSS / JS, ad-hoc `make_chart` composites used as dashboards, third-party dashboard frameworks (plotly / bokeh / dash / streamlit / panel), or any "preview" / "quick HTML render" outside this engine produce undefined behaviour: no Refresh button, no portal embedding, no failure modal, no registry hooks, no validation gates, no shared brand, no auto-refresh, no community share. If the user asks for a "dashboard" / "monitor" / "tracker" / "screen" / "wrap", the answer is `compile_dashboard(manifest)` via §B. There is no other path. If a one-off PNG chart is what the user wants, that's Altair's `make_chart()` — not echarts, not a dashboard.

One visual style only — Goldman Sachs brand: GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans, thin grey grid on paper-white. No theme switcher.

The engine surfaces three folder-operation entry points (`run_pull`, `build_dashboard`, `refresh_dashboard`) plus the compile primitives (`compile_dashboard`, `populate_template`, `manifest_template`, `validate_manifest`). Together they carry every dashboard operation. PRISM uses real Python imports — no namespace-injection gymnastics.

For refresh-pipeline operations / failure modal / runner internals see `prism/dashboard-refresh.md`. This file is purely about authoring + the in-folder edit lifecycle.

This hub covers the always-needed contract, schema, recipes, and pre-flight. Per-primitive depth (chart specs, widget specs, filter mechanics, archetypes) lives in spoke files fetched on demand — see §3.

---

## The dashboard folder is your workspace

Every iteration on a dashboard happens at `users/{kerberos}/dashboards/{name}/`. Treat the folder as PRISM's workspace for that dashboard — read everything in it, write the canonical artefacts there, do all scratch work inside it (never under `{SESSION_PATH}/` or anywhere else). The §2.5 audit is the simple "are the canonical files there?" check that keeps the workspace from drifting; anything else in the folder is fine as long as the canonical 5 are present and uncorrupted.

| Need | Where it lives inside the workspace |
|------|--------------------------------------|
| Canonical artefacts (the §2.2 required paths) | top level of the folder |
| Optional history snapshots (when `keep_history=true`) | `history/<UTC>/` (runner-managed) |
| Scratch / archived versions (manual) | `archive/<UTC>/` (audit ignores; runner ignores) |
| Generated data | `data/<stem>.csv` only; no per-source subfolders (Rule 5) |

Two side-effects of treating the folder as workspace:

1. **Read first, then act.** When PRISM picks up a dashboard, the first action is `s3_manager.list({DASHBOARD_PATH})` + `_audit_dashboard_layout` (§2.5). Whatever's there is the current state; the planned change merges into it (see §C for spec edits, §D for script edits, `dashboards/pipelines.md` for the pipeline-aware mental model).
2. **Re-runs overwrite, never create.** Running `pull_data.py` or `build.py` against an existing folder MUST NOT produce any new top-level paths — the §2.2 canonical artefacts are overwritten in place, and nothing else. No timestamped CSVs (`rates_eod.20260503.csv`), no `manifest_v2.json`, no debug `.json` siblings.

---

## §A. The three surfaces cheat sheet + path decision

A persistent dashboard is the trio of edit surfaces below plus the registry entry. Everything else in the folder is **derived** — regenerated from those three by the cron runner. PRISM never edits derived artefacts in place.

| Surface | Role | Edit churn | How PRISM edits |
|---------|------|------------|-----------------|
| `scripts/pull_data.py` | List of named pull functions (`PULLS = {<name>: <fn>, ...}`) — every CSV under `data/` is the output of one pull | **High** — changes whenever a new data source / column / window / lag is needed | Surgical READ → MUTATE → WRITE on the persisted bytes; §D |
| `manifest_template.json` | The dashboard SPEC — layout, widgets, charts, filters, metadata, palettes, header_actions, links. Carries empty dataset slots; data lands at compile time. | **High** — every UX iteration touches it (add chart, edit filter, rename tab, swap chart_type, tweak metadata) | Ephemeral session-folder code that does raw JSON CRUD; §C |
| `scripts/build.py` | Transforms hook — defines `TRANSFORMS = [<fn>, ...]` (cross-dataset joins, derived ratios, YoY, subset projections). Optional — many dashboards have `TRANSFORMS = []` | **Low** — changes only when the analytical SHAPE changes (new derived dataset, new join, new ratio). Never changes for a UX-only edit | Surgical READ → MUTATE → WRITE on the persisted bytes; §D |

The other files in the folder (`data/<stem>.csv`, `manifest.json`, `dashboard.html`, `refresh_status.json`) are **derived** — regenerated on every refresh by the cron runner. PRISM never edits derived artefacts in place.

### A.1 PRISM only writes Python

The hard rule: **PRISM authors `.py` files and `.json` dicts. PRISM does NOT author `.html`, `.css`, or `.js` files.** The rendering engine owns every byte the browser sees. If a render looks wrong, the fix lives in the spec (`manifest_template.json` for layout / widget shape) or in `build.py` (for derived datasets) or in `pull_data.py` (for raw data); never in the rendered HTML.

#### A.1.1 The `tool_def.compute_js` carve-out

`tool_def.compute_js` is a JS string LITERAL embedded inside the Python dict that authors the manifest — the same surface area as authoring SQL strings or JSON literals inside Python. That IS Python code (the file is `.py`, the string is data); it is NOT PRISM authoring a `.js` file. The engine **auto-sanitizes** the equivalence-preserving Python literals (`None` → `null`, `True` → `true`, `False` → `false`, `nan` → `NaN`, `inf` → `Infinity`, numpy scalars cast to native numerics) at compile time — PRISM may type either dialect; the engine emits valid JS and `r.warnings` carries one entry per substitution so the rewrite is observable. The semantic-shifting set (`Timestamp(...)`, `datetime.date(...)`, `datetime.datetime(...)`, `Decimal(...)`) still blocks at validate via `tool_compute_python_literal_in_js` because naive substitution would silently change values (JS `Date` months are 0-indexed; `Number` is float64 — `Decimal` precision lossy); pass these through `inputs[].default = '<isoformat>'` or cast via `float()` first. `tool_compute_missing_output_key` blocks declared output ids that don't appear as `<id>:` keys in the compute return literal. All other widget surfaces are pure JSON dicts authored from Python — already conformant.

### A.2 Path decision by user-ask shape

| User ask | Path | Where the work happens |
|---|---|---|
| First-time creation ("build me a dashboard for X") | Recipe 1 (§B) | All three surfaces authored fresh; registry entry created; subprocess refresh seals it |
| Manifest-only edit ("add a chart / KPI / tab / row", "edit a filter / title / metadata", "change a chart_type", "rename a tab") | Recipe 2 (§C) | `manifest_template.json` only (raw JSON CRUD); scripts untouched; verify via `build_dashboard(folder)` |
| Data-shape edit ("add / rename / drop a column", "add a new pull source") | Recipe 3 (§D) | `pull_data.py` (and `build.py` if dataset shape changes); verify via `run_pull(folder, '<name>')` then `build_dashboard(folder)` |
| Cross-dataset derivation edit ("add a derived ratio / YoY column / cross-dataset join") | Recipe 3 (§D) | `build.py` `TRANSFORMS` only; verify via `build_dashboard(folder)` |
| In-session quick recompile ("rebuild without a fresh pull") | Recipe 4 (§E) | Just call `build_dashboard(folder)` — no edits, surfaces compile errors |
| Inspecting an existing dashboard | Recipe 5 (§F) | HIGH-LEVEL GLANCE then DEEP GLANCE patterns |
| Reverting a recent edit | Recipe 6 (§G) | Re-edit from chat history (or `history/<UTC>/` if `keep_history=true`) |
| Total demolition ("rebuild from scratch", "start over") | Recipe 1 (§B), surface destructive intent first | Full re-author of every surface |

Two preservation rules govern every non-first-build path:

- **`scripts/build.py` and `scripts/pull_data.py` are NEVER re-emitted from a fresh string** for an "add" / "edit" / "extend" ask — that's §D. The only path that re-emits scripts wholesale is first-time creation (Recipe 1) and total demolition (user explicitly asked, was asked to confirm).
- **`manifest_template.json` is NEVER rewritten from a fresh dict** for an "add" / "edit" / "extend" ask — that's §C. The CRUD patterns mutate the loaded template in place; wholesale `tpl = {...}` rewrites drop every widget / tab / filter / dataset PRISM didn't include in the fresh dict.

---

## Catalog index

Every named primitive PRISM picks between, with a pointer to the hub section OR spoke file that carries the per-primitive spec.

| Primitive | Names | Where |
|---|---|---|
| Widgets (10) | `chart`, `kpi`, `table`, `pivot`, `stat_grid`, `tool`, `note`, `markdown`, `image`, `divider` | `dashboards/widgets.md` (most); `dashboards/widget_tool.md` (`tool`); `dashboards/charts.md` (`chart` specs) |
| Chart types (30) | `line`, `multi_line`, `bar`, `bar_horizontal`, `scatter`, `scatter_multi`, `scatter_studio`, `area`, `heatmap`, `correlation_matrix`, `pie`, `donut`, `boxplot`, `histogram`, `bullet`, `sankey`, `treemap`, `sunburst`, `graph`, `candlestick`, `radar`, `gauge`, `calendar_heatmap`, `funnel`, `parallel_coords`, `tree`, `waterfall`, `slope`, `fan_cone`, `marimekko` | `dashboards/charts.md` §2 |
| Filter types (10) | `dateRange`, `select`, `multiSelect`, `numberRange`, `toggle`, `slider`, `radio`, `text`, `number`, `rule` | `dashboards/filters.md` §1 |
| Filter ops (11) | `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`, `in`, `not_in` | `dashboards/filters.md` §5 |
| Note kinds (6) | `insight`, `thesis`, `watch`, `risk`, `context`, `fact` | `dashboards/widgets.md` §8 |
| Annotation types (5) | `hline`, `vline`, `band`, `arrow`, `point` | `dashboards/charts.md` §5 |
| KPI aggregators (8) | `latest`, `first`, `sum`, `mean`, `min`, `max`, `count`, `prev` | `dashboards/widgets.md` §2 |
| Table formats (11) | `text`, `number`, `integer`, `percent`, `currency`, `bps`, `date`, `datetime`, `link`, `signed`, `delta` | `dashboards/widgets.md` §3 |
| Tool input kinds (4) | `scalar`, `sweep`, `expression`, `matrix` | `dashboards/widget_tool.md` §4.1 |
| Tool output kinds (8) | `stat`, `scalar`, `param`, `kpi`, `series`, `table`, `stat_grid`, `distribution` | `dashboards/widget_tool.md` §4.2 |
| Sync modes (4) | `axis`, `tooltip`, `legend`, `dataZoom` | `dashboards/filters.md` §6 |
| Brush types (4) | `rect`, `polygon`, `lineX`, `lineY` | `dashboards/filters.md` §6 |
| Layouts (2) | `grid`, `tabs` | §4 |
| Refresh frequencies (4) | `hourly`, `daily`, `weekly`, `manual` | §2.3 |

Catalog only — pick what you need from this table, then fetch the relevant spoke per the menu in §3.

---

## 0. Contract: eight rules

All eight absolute. A dashboard violating any of them is broken even if `dashboard.html` renders.

### Rule 1 — real data only, every number refreshes

- Auto-saving primitives: `pull_market_data`, `pull_haver_data`, `pull_plottool_data`, `pull_fred_data`.
- Everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, Coalition, Inquiry, scraped DataFrames) lands via `save_artifact()`.
- Forbidden: `np.random.*`, `np.linspace` / `np.arange` as data, hand-typed numeric arrays, synthetic fill for missing values, invented dates / labels.
- If no source exists, do not build the panel — add a data source first.
- **Every visible number on the dashboard must trace to `pull_data.py` output.** Hand-typed `value: <num>` in a KPI / stat_grid item is forbidden — it doesn't refresh, ships stale on day two. The validator hard-rejects (`kpi_static_value_forbidden` / `stat_grid_static_value_forbidden`, both in `ALWAYS_BLOCKING_ERROR_CODES`). Wire every visible number through `source: "<dataset>.<aggregator>.<col>"`.
- **Build-time computation is fine** — a `TRANSFORMS` function in `build.py` can derive a new dataset (YoY, ratios, joins) from the raw CSVs. The KPI / chart references the derived dataset by key; the next refresh re-derives from current pulls.
- **Sense-check every visible number BEFORE persisting.** Every `compile_dashboard()` call prints a `[kpi sense-check]` block listing every KPI / stat_grid item with its resolved value (the exact number the browser will render). PRISM reads that block and asks two questions on every line: (1) is the NUMBER plausible (right column? right aggregator? right units? `count(rows)=8` is rarely what the user wanted), and (2) is the CONCEPT useful (`max(price_5y)` is a clever-sounding stat that almost never tells the user anything; `mean(unrelated_series)` is noise). Items with `|value| > 20` additionally fire a `kpi_value_sense_check` / `stat_grid_value_sense_check` warning so PRISM cannot miss them — the threshold is intentionally low because most macro / rates / vol / probability KPIs sit comfortably below 20 and a fire there is usually a units mismatch, wrong column, or nonsensical aggregator. **The dual purpose is "wrong number" AND "useless concept" — both are PRISM's responsibility to catch before persisting.** When a fire is a true positive, redesign the tile (different column / aggregator / format / concept entirely). When it's a confirmed-correct big number (S&P 4500, VIX 25, probability=68%, HY OAS 285bp), suppress per-tile with `"sense_check": False` and move on.

### Rule 2 — no literal data inside the manifest JSON

- Pass DataFrames; the compiler converts them to canonical on-disk shape.
- Three accepted dataset entry shapes (all normalised):

| Shape | When |
|-------|------|
| `datasets["rates"] = df` | Most common. Zero ceremony. |
| `datasets["rates"] = {"source": df}` | When attaching metadata to the entry. |
| `datasets["rates"] = {"source": df_to_source(df)}` | When the manifest is saved/read before the compiler touches it. |

### Rule 3 — order is non-negotiable

- `pull_data.py` must run end-to-end and produce real CSVs (printed `df.shape` / `df.head()` / `df.dtypes` for verification) before `build.py` is authored.
- Write the manifest against verified shapes, not imagined columns.
- A render bug never gets fixed by editing `dashboard.html` or `manifest.json` directly. Fix the spec (`manifest_template.json`), the transforms (`build.py`), or the data (`pull_data.py`); the next `build_dashboard(folder)` call regenerates the derived files.

### Rule 4 — canonical layout, exclusive whitelist

- The dashboard folder at `users/{kerberos}/dashboards/{name}/` follows a small canonical layout: 5 required files (3 top-level + 2 scripts) plus a `data/` directory. The §2.5 audit confirms every required file exists.
- Cardinality is exact: one `manifest_template.json`, one `manifest.json`, one `dashboard.html`, one `scripts/pull_data.py`, one `scripts/build.py`. No second copies, no `_v2` / `_old` / `_backup` siblings.
- The two LIVE `.py` files under `scripts/` are exactly what the refresh runner re-executes on schedule. Missing live scripts → the [Refresh] button fails immediately with `FileNotFoundError`.
- `history/<UTC>/` and `archive/<UTC>/` are permitted; both are ignored by the runner and the audit. Use `archive/` to quarantine old artefacts you want to keep around for reference.

### Rule 5 — every CSV at `{folder}/data/<dataset>.csv`

- Inside `pull_data.py`, every pull-function call AND every `save_artifact(...)` MUST pass `output_path=f'{SESSION_PATH}/data'`.
- **`pull_data.py` and `build.py` MUST each open with an explicit `SESSION_PATH = "<dashboard-path-literal>"` line.** PRISM substitutes the dashboard path at author time so build-time and refresh-time both resolve to the same `{folder}/data` folder. The engine's `run_pull` / `build_dashboard` / `refresh_dashboard` execute the script bytes verbatim — they don't inject `SESSION_PATH` for you.
- Without `output_path`, CSVs land in per-source subfolders (`market_data/`, `haver/`, `plottool_data/`) — `build_dashboard()` does not look there → refresh fails.
- `pull_market_data` ALWAYS appends `_eod` / `_intraday` to the filename. Pass `name='rates'` → `data/rates_eod.csv`. Use `'rates_eod'` as the manifest dataset key. Pass `name='rates_eod'` → broken `data/rates_eod_eod.csv`.
- The dataset key in `manifest.datasets` matches the on-disk CSV stem byte-for-byte. §6.2 has the per-source pattern.

### Rule 6 — hand off the portal URL, never the HTML file

- The deliverable PRISM surfaces is the **portal URL** (`http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{dashboard_id}/`). Lead with it on the first line of the build success message.
- The S3 path of `dashboard.html` is internal plumbing. Surface it ONLY if the user explicitly asks ("give me the raw HTML", "where on S3 does this land"). Even then, surface the portal URL alongside.
- The portal URL is load-bearing because the serving Django view injects the `window.PRISM_VIEWER` / `PRISM_DASHBOARD_AUTHOR` / `PRISM_DASHBOARD_SHARED` JS globals before `</head>` (§2.3.1). Those globals drive the always-on chrome — Refresh / Share visibility, owner vs viewer state, observatory suppression. Opening the bare `dashboard.html` directly from S3 (or downloading it) skips that injection and the chrome silently degrades.
- The portal URL is also the only path that picks up the hourly refresh runner's updates, the structured failure modal, the share-toggle endpoint, and the per-user community visibility. The bare HTML is a one-shot snapshot.

### Rule 7 — build flow is atomic

- The four steps of Recipe 1 (Tools 1, 2, 3, 4 in §B) are **non-divisible**. PRISM does not return to the user between Tool 1 and Tool 4. The dashboard does not exist as a deliverable until every artefact in §2.2 is on S3, the entry sits in `registry["dashboards"][]` (not as a top-level key), the user-manifest pointer reflects it, the §2.5 audit passes, AND Tool 4's subprocess refresh exits 0 with `refresh_status.json.status == "success"`.
- Forbidden language in any user-facing message before Tool 4 has completed cleanly: "next steps", "would you like me to", "I can also create / register / set up", "to make this fully persistent / auto-refreshing". Each phrase implies the build has opt-in phases the user can decline. There are no phases. The post-Tool-4 portal URL (Rule 6) is the ONLY user-facing message; everything before it is internal plumbing the user does not see.
- Failure handling: if any tool raises, the response to the user is the failure (with its diagnostic), not a rendered HTML preview gated behind a registration question. Do not paper over a failed build by surfacing partial output and asking permission to "complete" it.

### Rule 8 — slice complex requests, check in between slices

A "build me a dashboard" prompt rarely lands as a single buildable specification. PRISM does NOT attempt to fulfil the entire ask in one build flow. The discipline:

- **Slice the request** into the smallest meaningful deliverable that produces a self-contained, registered, renderable dashboard. Natural slices: one tab; one tool widget; one chart-pair + headline KPI; data pull + headline table, defer charts. Pick the slice whose feedback most disambiguates the rest of the request.
- **Build the slice atomically** (Rule 7 governs WITHIN: Tools 1-4 non-divisible; the slice must end with a registered dashboard at a portal URL).
- **Hand off the URL and ASK** "first slice live at <URL>. Structure look right? Want me to add [next chunk]?"
- **Wait for confirmation** before the next slice. Iterate.

Forbidden after a complex prompt:

- Building all 8 tabs / 30 widgets in one mega-build before surfacing anything.
- "Continuing with the rest of the dashboard now…" without explicit user confirmation.
- Surfacing one slice and immediately stacking "let me also add X, Y, Z" without waiting for the user.
- Pre-announcing the slice plan ("I'll do tabs 1-3 first then 4-8") and proceeding through it autonomously — the plan changes after every slice based on feedback.

---

## 1. Engine entry points

Auto-imported into both the `execute_analysis_script` sandbox and the refresh runner. PRISM uses real Python imports — the in-session ephemeral script reads from these names directly, no namespace gymnastics.

```python
from ai_development.dashboards import (
    # Folder operations -- carry every dashboard op
    run_pull,             # run_pull(folder, pull_name)        -- in-process
    build_dashboard,      # build_dashboard(folder)            -- in-process
    refresh_dashboard,    # refresh_dashboard(folder)          -- in-process; runner spawns subprocess

    # Compile primitives (used internally by build_dashboard; PRISM
    # rarely calls these directly under the new model)
    compile_dashboard,    # JSON manifest -> dashboard HTML + JSON
    validate_manifest,    # dry-run structural validator
    manifest_template,    # strip data -> reusable template
    populate_template,    # template + datasets -> manifest (sources normalized)
    df_to_source,         # DataFrame -> canonical list-of-lists
    chart_data_diagnostics,  # post-compile linting
    load_manifest, save_manifest,
)
```

`compile_dashboard()` raises by default (`strict=True`) on any error-severity diagnostic. `strict=False` is an inner-loop discovery mode — it keeps going so PRISM can see every cosmetic / advisory issue in one round-trip. **`strict=False` is for one-shot in-session calls only; the standard `build_dashboard(folder)` always uses `strict=True`.** A short list of load-bearing error codes (`chart_mapping_column_missing`, `chart_dataset_empty`, `chart_too_many_series`, `kpi_source_*`, `kpi_static_value_forbidden`, `stat_grid_static_value_forbidden`, `table_column_field_missing`, `filter_field_missing_in_target`, `chart_build_failed`, …) raise regardless of `strict`. The full list lives in `echart_dashboard.ALWAYS_BLOCKING_ERROR_CODES`. One theme (`gs_clean`); three palettes (`gs_primary`, `gs_blues`, `gs_diverging`).

### 1.1 What `build_dashboard(folder)` does

```python
def build_dashboard(folder, *, s3_manager=None) -> dict:
    """
    1. Read manifest_template.json from <folder>
    2. Read every <folder>/data/<stem>.csv into a datasets dict
    3. Read TRANSFORMS from <folder>/scripts/build.py and chain them
       (each receives + returns the datasets dict)
    4. populate_template(template, datasets) -> manifest
    5. compile_dashboard(manifest, strict=True) -> html + manifest
    6. Write <folder>/manifest.json + <folder>/dashboard.html to S3
    """
```

The same `build_dashboard()` is called by PRISM in-session (after a manifest or transforms edit), by `refresh_dashboard()` (after a fresh pull), and by `refresh_runner.py` (when invoked by the cron / [Refresh] button). One canonical path; no namespace injection; no script-by-script orchestration.

### 1.2 What `run_pull(folder, name)` does

```python
def run_pull(folder, pull_name, *, s3_manager=None) -> None:
    """Execute PULLS[pull_name]() from <folder>/scripts/pull_data.py.

    The pull function writes its CSV to <folder>/data/ as a side effect."""
```

Use from PRISM ephemeral code to refresh ONE pipeline during dev iteration. Fast, in-process — no subprocess, no timeout. For pull+build, use `refresh_dashboard()`.

### 1.3 What `refresh_dashboard(folder)` does

```python
def refresh_dashboard(folder, *, s3_manager=None) -> dict:
    """All PULLS, then build_dashboard.

    Used by refresh_runner.py when the cron / browser [Refresh] fires.
    PRISM may also call this directly when it wants a clean-slate
    refresh from in-session (slow -- every pull runs)."""
```

---

## 2. Manifest

### 2.1 Shape

```python
manifest = {
    "schema_version": 1, "id": "rates_monitor", "title": "Rates monitor",
    "description": "Curve, spread, KPIs.",   # optional subtitle
    "theme": "gs_clean", "palette": "gs_primary",   # both defaults
    "metadata":        { ... },               # see 2.3
    "header_actions":  [ ... ],               # see Section 5
    "datasets":        {"rates": df_rates, "cpi": {"source": df_cpi}},
    "filters":         [ ... ],               # see dashboards/filters.md
    "layout":          {"kind": "tabs",       # or "grid" (default); see Section 4
                         "tabs": [{"id": "overview", "label": "Overview",
                                   "description": "Headline rates + spread",
                                   "rows": [ [ widget, widget, ... ], ... ]}]},
    "links":           [ ... ],               # see dashboards/filters.md §6
}
# SESSION_PATH must already be defined explicitly above this call (Rule 5).
compile_dashboard(manifest, session_path=SESSION_PATH)
```

| Top-level field | Purpose |
|-----------------|---------|
| `title` / `description` | Header title + subtitle |
| `theme` / `palette` | `gs_clean` (only theme); `gs_primary` (default) / `gs_blues` (sequential) / `gs_diverging` |
| `metadata` | Provenance + refresh block (§2.3) |
| `header_actions` | Custom header buttons (§5) |
| `datasets` | `{name: DataFrame \| {"source": ...}}` |
| `filters` / `layout` / `links` | `dashboards/filters.md` / §4 / `dashboards/filters.md` §6 |

### 2.2 Folder structure

For **conversational (session-only)** dashboards:

```
{SESSION_PATH}/dashboards/{id}.json     compiled manifest
{SESSION_PATH}/dashboards/{id}.html     compiled dashboard
```

For **persistent user dashboards** (Rule 4):

```
users/{kerberos}/dashboards/{dashboard_name}/
  manifest_template.json    [REQUIRED · 1] LLM-editable spec, NO data
  manifest.json             [REQUIRED · 1] template + fresh data, embedded
  dashboard.html            [REQUIRED · 1] compile_dashboard output
  refresh_status.json       [optional · ≤1] runner-owned runtime state
  thumbnail.png             [optional · ≤1] author-owned preview image
  scripts/
    pull_data.py            [REQUIRED · 1] PULLS = {<name>: <fn>, ...}
    build.py                [REQUIRED · 1] TRANSFORMS = [<fn>, ...]
  data/                     [REQUIRED · CSVs/JSONs whose stems match manifest.datasets keys]
    rates_eod.csv           one CSV per dataset; stem matches manifest key byte-for-byte
    rates_intraday.csv      pull_market_data appends _eod / _intraday
    rates_metadata.json     pull_market_data sidecar uses the bare name
    cpi.csv                 pull_haver_data: no suffix
    cpi_metadata.json
    swap_curve.csv          pull_plottool_data: no suffix
    fdic_gs_bank.csv        save_artifact: no suffix
  history/                  [optional] snapshots when keep_history=true; runner-managed
  archive/<UTC>/            [optional] manual quarantine; ignored by runner + audit
```

The 5 required paths above are what `_audit_dashboard_layout(folder)` checks for. Anything else in the folder is fine — the runner only reads the 5 (and walks `data/` for CSVs). No `scripts/versions/` machinery; reverts use chat history or `history/<UTC>/` snapshots (§G).

### 2.3 Metadata block

Drives the data-freshness badge, methodology popup, summary banner, refresh button, and share button.

Three fields are **required** for every dashboard `compile_dashboard` produces:

| Required field | Type | Purpose |
|----------------|------|---------|
| `kerberos` | str | Owner kerberos. Gates the `Refresh` and `Share` buttons; bound to the S3 path the refresh runner writes |
| `dashboard_id` | str | Stable id under `users/{kerberos}/dashboards/`. Typically equals `manifest.id` — set both to the same value |
| `methodology` | str \| `{title, body}` | Markdown describing how the data is constructed. Drives the always-on `Methodology` popup. Must be non-empty |

The remaining fields are optional but every persistent dashboard should at least carry `data_as_of` / `generated_at` (data-freshness badge) and `sources`:

| Optional field | Type | Purpose |
|----------------|------|---------|
| `sources` | list[str] | Source names (`["GS Market Data", "Haver"]`) |
| `summary` | str \| `{title, body}` | Always-visible markdown banner above row 1 (today's read) |
| `refresh_frequency` | str | `hourly` / `daily` / `weekly` / `manual`; controls the hourly runner — manual means `Refresh` is button-driven only |
| `live_refresh_seconds` | int | Browser-side live-poll cadence; default `60`, `0` disables, soft floor `15`. See §2.3a |
| `time.data_domain_freq` | str | `daily` / `weekly` / `monthly` / `quarterly` / `annual`; cadence override. Auto-inferred from CSV inter-row spacing — set only when auto-inference picks wrong (mixed-frequency datasets). See §2.3a |
| `tags` / `version` | list[str] / str | Echoed into the registry; manifest version string |
| `api_url` / `status_url` / `data_url` | str | Refresh / status / live-data endpoint overrides |
| `shared` / `shared_at` | bool / str | Compile-time snapshot of community-share state |
| `share_api_url` | str | Optional override of the share toggle endpoint (default `/api/dashboard/share/`) |

`summary` and `methodology` accept the shared markdown grammar (`dashboards/widgets.md` §9). `summary` is always-visible above row 1 (today's read); `methodology` is click-to-open via the always-on header button (how the data is constructed).

The engine auto-stamps these on every build — PRISM does NOT author them:

| Engine-stamped field | What it holds |
|----------------------|---------------|
| `metadata.time.data_domain_end` | Max date across every dataset's date column |
| `metadata.time.data_domain_freq` | Auto-inferred cadence (override in template if wrong) |
| `metadata.time.pull_completed_at` | Max `pull_completed_at` across `data/<stem>_metadata.json` sidecars |
| `metadata.time.build_completed_at` | When `build_dashboard()` compiled the HTML |
| `metadata.time.refresh_cycle_at` | When the cron / `[Refresh]` runner finished (matches registry `last_refreshed` byte-for-byte) |
| `metadata.pill_text` | Server-baked "Data through Q1 2026 — refreshed 12 May 2026 09:25 ET" string |
| `data_as_of` / `generated_at` | Back-compat aliases (deprecated; `metadata.time.*` is canonical) |

```python
metadata = {
    "kerberos":     "goyalri",
    "dashboard_id": "rates_monitor",
    "methodology":  "## Sources\n* US Treasury OTR yields (FRED H.15)\n## Construction\n"
                     "* 2s10s, 5s30s = simple cash differences in bp",
    "data_as_of": "2026-04-24T15:00:00Z",
    "sources":    ["GS Market Data"],
    "summary":    {"title": "Today's read",
                    "body": "Front-end has richened ~6bp on a softer print. Curve "
                             "**bull-steepened**, 2s10s out of inversion."},
}
```

### 2.3a Live refresh

Every served dashboard polls `GET /api/dashboard/data/` every 60 seconds (override via `metadata.live_refresh_seconds`; set to `0` to disable). The endpoint is ETag-gated on the registry's `last_refreshed` — most polls return 304 with no body. On a 200 (cron just wrote a fresh manifest, or the user clicked `[Refresh]`), the chrome swaps datasets + chart specs + metadata IN PLACE: filter state, dataZoom slider position, dark-mode toggle, table sort, and tab position all survive. The user does not need to take any action.

`[Refresh]` button success path no longer reloads the page — it kicks the same in-place swap loop. The error modal + `[Reload anyway]` partial-recovery button still trigger full reloads (intentional UX).

Structural changes (new widget / new tab / new filter — anything that edits `manifest_template.json`) bump the template hash and trigger one clean `location.reload()` via the chrome's `applyLiveData` path — the right semantic since in-place swap can't reconcile a structural change.

#### 2.3.1 Always-on header chrome

The header's right edge is shell-injected (Methodology / Refresh / Share / Download / theme-toggle / data-as-of pill). PRISM does not author these buttons. The validator hard-rejects any manifest missing the three required metadata fields above (`kerberos` / `dashboard_id` / `methodology`); set them and the chrome is functional. `header_actions[]` (§5) injects custom buttons to the LEFT of this chrome bar; the validator rejects any custom `id` colliding with a reserved chrome id (full list in §5).

`compile_dashboard()` returns a `DashboardResult` with `success`, `html`, `manifest`, `error_message`, `warnings`, and `diagnostics` populated. PRISM rule: ALWAYS check `r.success` before using `r.html`. **When `r.success=False`, `r.error_message` carries the full diagnostic body** — every validate error, CDD diagnostic, and shape diagnostic, one per line, prefixed with the same `[severity] code [wid] @ path :: message | fix: <hint>` format that the strict-raise path uses. Canonical PRISM-side raise (used internally by `build_dashboard()`): `raise ValueError(f"compile failed: {r.error_message}")` — that single line surfaces every bug to PRISM's caller in one round-trip.

### 2.4 `compile_dashboard` parameters

| Parameter | Purpose |
|-----------|---------|
| `manifest` | Required dict |
| `session_path` | Where compiled HTML / JSON land. Default cwd. PRISM passes the `SESSION_PATH` it defined explicitly per Rule 5. |
| `output_path` | Override single-file location (advanced) |
| `write_html` / `write_json` | Both default `True`; suppress for OOP-style use (`build_dashboard()` uses `False` and writes via `s3_manager.put`) |
| `strict` | `True` raises on any error-severity diagnostic; `False` reports + continues |
| `make_thumbnails` | `False` default; `True` auto-emits a PNG of the first row for the listing page |

### 2.5 Folder sanctity audit

Before any edit (or any new build), confirm the canonical 5 are present:

```python
import json

REQUIRED = [
    "manifest_template.json", "manifest.json", "dashboard.html",
    "scripts/pull_data.py", "scripts/build.py",
]

def _audit_dashboard_layout(folder, manifest=None):
    """Confirm the canonical 5 paths exist under <folder>. Raises if any
    is missing. Anything else under the folder is fine -- this audit
    intentionally does NOT enforce exclusivity. Use archive/<UTC>/ for
    rogue files you want to keep around for reference.
    """
    folder = folder.rstrip("/")
    listing = {entry["Key"].replace(f"{folder}/", "", 1).lstrip("/")
                for entry in s3_manager.list(folder)}
    missing = [r for r in REQUIRED if r not in listing]
    if missing:
        raise ValueError(
            f"_audit_dashboard_layout: {folder} missing required path(s): "
            f"{missing}"
        )
```

Run the audit at the START of any inheritance (PRISM picking up an existing dashboard to modify) and at the END of every Recipe 1 build. If it raises, surface the missing paths to the user — re-author whatever's missing before proceeding with the requested edit.

---

## 3. On-demand spec fetching

This hub covers every primitive's catalog row + the always-needed contract + the six recipes. For per-primitive depth (chart-type mapping rules, widget specs, filter mechanics, archetypes), fetch the relevant spoke.

**Do NOT call `get_context()` again — it is one-shot per user message.** Mid-session reads use `list_ai_repo` with `mode="full"`. **Pass ONLY `file_paths` and `mode` — actively omit every other parameter.** Each spoke is independent; mix and match.

| Spoke | Contents | Verbatim tool call (copy-paste) |
|-------|----------|--------------------------------|
| `dashboards/charts.md` | 30 chart types; mapping keys; cosmetic / layout knobs; annotations; `scatter_studio`; `correlation_matrix`; computed columns | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md"], mode="full")` |
| `dashboards/widgets.md` | KPI, table (incl. `row_click`), pivot, stat_grid, image, markdown, divider; provenance; `show_when` / `initial_state` / stat strip; markdown grammar | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/widgets.md"], mode="full")` |
| `dashboards/widget_tool.md` | `widget: tool` (form-driven compute) — pricers, scenarios, calculators; tool def shape; input + output kinds; canonical examples | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/widget_tool.md"], mode="full")` |
| `dashboards/filters.md` | 10 filter types + 11 ops; cascading filters; per-chart `dataZoom`; `click_emit_filter`; compound rule filters; links (sync + brush) | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/filters.md"], mode="full")` |
| `dashboards/template_crud.md` | THIN reference — points back at hub §C for the canonical CRUD skeleton; covers per-CRUD-pattern niche cases (multi-target filter rebinding, `show_when` reference cleanup, etc.). Most edits don't need this; §C carries the daily patterns. | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/template_crud.md"], mode="full")` |
| `dashboards/recipes.md` | 21 data-shape archetypes → chart types (the cookbook) + transforms hook patterns (YoY / composition / cross-dataset join / subset projection) for `build.py` | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/recipes.md"], mode="full")` |
| `dashboards/pipelines.md` | The pipeline cataloging mental model + reuse decision ladder (reuse-existing-CSV / extend-existing-pipeline / add-new-pipeline) + active-pipeline integrity rules | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/pipelines.md"], mode="full")` |
| `dashboards/canonical_showcase.json` | Bare templated manifest of `build_showcase` as a structural reference: 8 MECE tabs, 79 widgets, 39 datasets, 13 filters, 2 links — every primitive in the Catalog index above exercised at least once, data stripped to header rows. ~111 KB. **How to use**: fetch when in doubt about how to shape a widget / filter / link / metadata block, find the matching block by keyword search (chart_type / widget id / filter type / aggregator), copy the structural fragment verbatim, then rebind dataset names + column references to your own datasets. | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/canonical_showcase.json"], mode="full")` |

**Common combos** (one call, multiple file_paths):

| Build shape | Single call to copy |
|-------------|---------------------|
| Charts only | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md"], mode="full")` |
| Charts + KPI / table strip | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md", "context/modules/static/tools/dashboards/widgets.md"], mode="full")` |
| Charts + widgets + filters | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md", "context/modules/static/tools/dashboards/widgets.md", "context/modules/static/tools/dashboards/filters.md"], mode="full")` |
| Pricer / scenario tool | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/widget_tool.md", "context/modules/static/tools/dashboards/widgets.md"], mode="full")` |
| "Show me a worked archetype" | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/recipes.md"], mode="full")` |
| Editing data shape (new column / pull source / derived dataset) | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/pipelines.md", "context/modules/static/tools/dashboards/recipes.md"], mode="full")` |

The Catalog index above is enough to PICK a chart type / widget / filter type. Fetch a spoke when you need the per-primitive mapping rules / required keys / cosmetic knobs.

---

## 4. Layouts (grid + tabs)

```python
# Grid (default, simple)
"layout": {"kind": "grid", "cols": 12, "rows": [
    [widget, widget, ...],     # rows of widgets; widths must sum to <= cols
    [widget, ...]]}

# Tabs
"layout": {"kind": "tabs", "cols": 12, "tabs": [
    {"id": "overview", "label": "Overview",
      "description": "Short summary shown under the tab title",
      "rows": [...]},
    {"id": "detail", "label": "Detail", "rows": [...]}]}
```

Tabs lazily initialise charts on first activation; last-active tab persisted in `localStorage` per dashboard id.

| Tab field | Purpose |
|-----------|---------|
| `id` (req) | Stable slug used in DOM ids and localStorage keys |
| `label` | Visible tab text |
| `description` | (1) Italic secondary text below tab bar when active, (2) hover tooltip on the tab button |
| `rows` | List-of-lists of widgets |

### 4.1 Chart widths — exactly 2-up or 3-up

Chart widgets (`widget: "chart"`) must be `w=cols//2` (2-up) or `w=cols//3` (3-up) — i.e. on the default 12-col grid, exactly `w=6` or `w=4`. The validator rejects any other width with `chart widget width must be ... got N`; the rule is non-bypassable from `compile_dashboard`.

| Layout | Per-chart `w` (cols=12) | Use |
|--------|-------------------------|-----|
| 2-up   | `6` | Default for most pairs (price + carry, level + change, primary + benchmark) |
| 3-up   | `4` | Tile rows of comparable single-metric charts (sectors, regions, tenors) |

Default heights are layout-aware (no `h_px` needed in normal use): 400px at `w=6`, 360px at `w=4`. Override per-widget with `h_px` only when the chart has unusual aspect needs.

The rule is chart-only. KPI rows, tables, markdown banners, image headers, `note` widgets, and dividers may span any width including `w=12`.

If a row has only one chart, split it (level + change, nominal + real, US + cross-country) and run 2-up — or pair the chart with a `kpi` strip, `note`, `stat_grid`, `markdown`, or `table` companion.

---

## 5. Header actions

Optional `manifest.header_actions[]` appends custom buttons / links to the header (left of the always-on chrome — Methodology / Refresh / Share / Download — described in §2.3.1).

| Key | Purpose |
|-----|---------|
| `label` (req) | Display text |
| `href` | If set, renders `<a>` (opens in new tab by default) |
| `onclick` | Name of a global JS function. One of `href` / `onclick` is required |
| `target` | `"_self"` to open inline (defaults to `_blank`) |
| `id` | Optional DOM id. Cannot collide with a reserved chrome id (`refresh-btn`, `share-btn`, `download-btn`, `download-menu`, `methodology-btn`, `theme-toggle`, `export-all`, `export-dashboard`, `export-excel`, `data-as-of`, `data-as-of-val`, `header-actions`). The validator rejects collisions because a custom action with one of these ids would silently shadow the live chrome at runtime |
| `primary` | `True` → GS Navy primary button styling |
| `icon` | Optional leading glyph |
| `title` | Hover tooltip |

---

## §B. Recipe 1 — Build a new dashboard

The path for FIRST-TIME CREATION (and total demolition). Four tools in a single uninterrupted sequence (Rule 7); the user sees nothing until Tool 4 exits 0.

```
Tool 1: pull_data.py  Author pull_data.py as a string (PULLS dict + per-pull
                      functions). Persist to {DASHBOARD_PATH}/scripts/pull_data.py.
                      For each pull: run_pull(DASHBOARD_PATH, '<name>') from
                      ephemeral session code; verify the CSV shape.

Tool 2: build.py      Author build.py as a string (TRANSFORMS list + helpers).
                      Compose the initial manifest dict (with embedded data),
                      derive manifest_template.json via manifest_template().
                      Persist BOTH:
                        {DASHBOARD_PATH}/manifest_template.json
                        {DASHBOARD_PATH}/scripts/build.py
                      Then call build_dashboard(DASHBOARD_PATH) to compile +
                      write manifest.json + dashboard.html.

Tool 3: register      Load dashboards_registry.json (seed if missing), append/
                      replace entry by id in registry['dashboards'] (NOT as a
                      top-level key -- runner only iterates the list), save,
                      verify by re-load, then call update_user_manifest(
                      kerberos, artifact_type='dashboard').

Tool 4: subprocess    Spawn refresh_runner.py as a SUBPROCESS (the same script
                      the [Refresh] button + the hourly cron spawn). It calls
                      refresh_dashboard(folder) end-to-end inside a fresh
                      Python interpreter, overwriting manifest.json +
                      dashboard.html on S3. Block until exit; check
                      returncode == 0 AND refresh_status.json status ==
                      "success" before surfacing the portal URL.
```

### Tool 1 — author + persist + run pulls

```python
KERBEROS       = "goyalri"
DASHBOARD_NAME = "rates_monitor"
DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# Author pull_data.py as a string. Refresh runner re-execs these exact
# bytes daily. Rule 5: the script self-defines SESSION_PATH at the top.
# Real Python imports for every helper -- no namespace injection at exec time.
pull_data_py = '''"""pull_data.py for rates_monitor."""
from ai_development.mcp.utils.data_functions import (
    pull_market_data, save_artifact,
)
from ai_development.core.s3_bucket_manager import s3_manager

SESSION_PATH = "{{DASHBOARD_PATH_LITERAL}}"   # Rule 5

def pull_rates():
    pull_market_data(
        coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
        start='2020-01-01', name='rates', mode='eod',
        output_path=f'{SESSION_PATH}/data',
        s3_manager=s3_manager,
    )

PULLS = {
    'rates': pull_rates,
}

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        PULLS[sys.argv[1]]()
    else:
        for name, fn in PULLS.items():
            print(f"[pull_data] {name}")
            fn()
'''.replace("{{DASHBOARD_PATH_LITERAL}}", DASHBOARD_PATH)

s3_manager.put(pull_data_py.encode("utf-8"),
                f"{DASHBOARD_PATH}/scripts/pull_data.py")

# Run each pull in-process; verify the CSV lands.
for name in ('rates',):
    run_pull(DASHBOARD_PATH, name)
    df = pd.read_csv(io.BytesIO(s3_manager.get(
        f"{DASHBOARD_PATH}/data/rates_eod.csv")),
        index_col=0, parse_dates=True)
    print(f"[verify] rates_eod: shape={df.shape}")
    print(df.head())
    print(df.dtypes)
```

### Tool 2 — author + persist + compile

`build.py` is **the transforms hook** — defines `TRANSFORMS = [<fn>, ...]` for any cross-dataset derivations (joins, derived ratios, YoY, subset projections). For dashboards with no derivations, `TRANSFORMS = []`. The engine helper `build_dashboard(folder)` does the rest — load template, load CSVs, run TRANSFORMS in order, populate, compile, write.

**Five non-negotiables** for the persisted `build.py`:

1. Define `TRANSFORMS` as a module-level list (even if empty: `TRANSFORMS = []`). The engine reads it via the script's namespace; no re-exec.
2. Each transform is `def derive_<name>(datasets) -> dict` — receives the loaded datasets dict, returns it (mutated or replaced).
3. Transforms NEVER call `compile_dashboard` / `populate_template` / `s3_manager.put` directly. The engine owns the lifecycle; transforms only mutate the datasets dict.
4. **Every CSV load happens INSIDE the engine**, not in `build.py`. Transforms receive datasets already loaded as DataFrames keyed by CSV stem.
5. `build.py` does NOT concatenate / f-string / `.format()` Python values into a `widget: tool`'s `compute_js`. The compute body lives in `manifest_template.json` (set ONCE at first build, edited via §C surgical CRUD thereafter). See `dashboards/widget_tool.md` §1.

```python
# Compose the initial manifest (with embedded data) just to derive the template.
import io
df_rates = pd.read_csv(io.BytesIO(s3_manager.get(
    f"{DASHBOARD_PATH}/data/rates_eod.csv")),
    index_col=0, parse_dates=True)
df_rates.columns = ['us_2y', 'us_10y']    # plain English (Rule 1)

initial_manifest = {
    "schema_version": 1, "id": DASHBOARD_NAME, "title": "Rates Monitor",
    "metadata": {
        "kerberos":     KERBEROS,
        "dashboard_id": DASHBOARD_NAME,
        "methodology": (
            "## Sources\n* GS Market Data: 2Y + 10Y USD swap rates (EOD)\n"
            "## Construction\n* Daily close pulled via pull_market_data; "
            "no transforms before charting"
        ),
        "data_as_of":        str(df_rates.index.max().date()),
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "sources":           ["GS Market Data"],
        "refresh_frequency": "daily",
        "tags":              ["rates"],
    },
    "datasets": {"rates_eod": df_rates.reset_index()},
    # Default to kind: "tabs" even on a single-tab build so future
    # "add a tab" asks are pure §C.5 surgical inserts, not a grid->tabs
    # restructure first. Cost is one wrapper level; benefit is uniform CRUD.
    "layout": {"kind": "tabs", "cols": 12, "tabs": [{
        "id": "rates", "label": "Rates",
        "description": "UST curve + 2s10s headline charts",
        "rows": [[
            {"widget": "chart", "id": "curve_lvl", "w": 6, "title": "UST Curve",
              "spec": {"chart_type": "multi_line", "dataset": "rates_eod",
                        "mapping": {"x": "date", "y": ["us_2y", "us_10y"],
                                    "y_title": "Yield (%)"}}},
            {"widget": "chart", "id": "spread", "w": 6, "title": "2s10s Spread",
              "spec": {"chart_type": "line", "dataset": "spread",
                        "mapping": {"x": "date", "y": "spread",
                                    "y_title": "2s10s (bp)"}}},
        ]],
    }]}
}

# Derive the template (data stripped, slots preserved).
tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
                f"{DASHBOARD_PATH}/manifest_template.json")

# Author build.py as a string. The TRANSFORMS list is the only PRISM-customised
# part. The engine calls each transform with the datasets dict (CSVs already
# loaded as DataFrames keyed by stem), then populates + compiles + writes.
build_py = '''"""build.py for rates_monitor."""
import pandas as pd

SESSION_PATH = "{{DASHBOARD_PATH_LITERAL}}"   # Rule 5

def derive_spread(datasets):
    """2s10s spread (10Y - 2Y) in bp, keyed by date."""
    df = datasets['rates_eod']
    spread = pd.DataFrame({
        'date': df['date'],
        'spread': (df['us_10y'] - df['us_2y']) * 100,   # bp
    })
    datasets['spread'] = spread
    return datasets

TRANSFORMS = [derive_spread]
'''.replace("{{DASHBOARD_PATH_LITERAL}}", DASHBOARD_PATH)

s3_manager.put(build_py.encode("utf-8"),
                f"{DASHBOARD_PATH}/scripts/build.py")

# Compile: load template, load CSVs, run TRANSFORMS, populate, compile, write.
build_dashboard(DASHBOARD_PATH)

# Folder sanctity audit.
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)
print("[Tool 2] complete; ready for Tool 3 (register)")
```

### Tool 3 — register

There is no `register_dashboard()` helper. The hourly refresh runner iterates `registry["dashboards"]`; a top-level-keyed entry (`registry[DASHBOARD_NAME] = {...}`) is invisible to it, returns 404 on every refresh, and never produces a `refresh_status.json`. The shape is verbatim PRISM-authored:

```python
REGISTRY_PATH = f"users/{KERBEROS}/dashboards/dashboards_registry.json"
PORTAL_URL    = f"http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{DASHBOARD_NAME}/"

now_iso = datetime.now(timezone.utc).isoformat()

try:
    registry = json.loads(s3_manager.get(REGISTRY_PATH).rstrip(b"\x00").decode("utf-8"))
except Exception:
    registry = {"dashboards": [], "last_updated": now_iso}

if "dashboards" not in registry or not isinstance(registry["dashboards"], list):
    registry["dashboards"] = []

new_entry = {
    "id":                  DASHBOARD_NAME,
    "name":                "Rates Monitor",
    "description":         "Daily monitor of the US rates curve.",
    "created_at":          now_iso,
    "last_refreshed":      None,
    "last_refresh_status": None,
    "refresh_enabled":     True,
    "refresh_frequency":   "daily",
    "folder":              DASHBOARD_PATH,
    "html_path":           f"{DASHBOARD_PATH}/dashboard.html",
    "data_path":           f"{DASHBOARD_PATH}/data",
    "tags":                ["rates"],
    "keep_history":        False,
}

existing_ids = [d.get("id") for d in registry["dashboards"]]
if DASHBOARD_NAME in existing_ids:
    idx = existing_ids.index(DASHBOARD_NAME)
    new_entry["created_at"] = registry["dashboards"][idx].get("created_at", now_iso)
    registry["dashboards"][idx] = new_entry
else:
    registry["dashboards"].append(new_entry)

registry["last_updated"] = now_iso
s3_manager.put(json.dumps(registry, indent=2).encode("utf-8"), REGISTRY_PATH)

# Verify by re-loading; raises if the entry isn't in dashboards[].
verify = json.loads(s3_manager.get(REGISTRY_PATH).rstrip(b"\x00").decode("utf-8"))
if DASHBOARD_NAME not in [d.get("id") for d in verify.get("dashboards", [])]:
    raise RuntimeError(f"[Tool 3] {DASHBOARD_NAME} not in registry['dashboards'] after write")

update_user_manifest(KERBEROS, artifact_type="dashboard")
print(f"[Tool 3] complete; ready for Tool 4 (subprocess refresh)")
```

`update_user_manifest` only updates `users/{kerberos}/manifest.json`'s `pointers.dashboards` block (count, active_count, last_refreshed, registry_path). It reads the registry to compute those numbers but never writes the registry itself. The registry must already be saved on S3 with the new entry appended into `dashboards[]` BEFORE this call.

### Tool 4 — subprocess refresh

The build's final action runs the canonical refresh path (`refresh_runner.py`) as a SUBPROCESS — the same script the browser `[Refresh]` button + the hourly cron spawn. The user's first view of the dashboard at the portal URL is byte-identical to what tomorrow's cron will produce.

```python
import os, subprocess, sys, json, time

import ai_development.dashboards.refresh_runner as _rr
REFRESH_RUNNER_PATH = _rr.__file__

print(f"[Tool 4] spawning refresh_runner.py for {KERBEROS}/{DASHBOARD_NAME}...")

log_path = f"/tmp/dashboard_refresh/{KERBEROS}_{DASHBOARD_NAME}_{int(time.time())}.log"
os.makedirs(os.path.dirname(log_path), exist_ok=True)

with open(log_path, "wb") as log_fh:
    proc = subprocess.Popen(
        [sys.executable, REFRESH_RUNNER_PATH,
         "--folder", DASHBOARD_PATH, "--log-path", log_path],
        stdout=log_fh, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )
    rc = proc.wait()

if rc != 0:
    raise RuntimeError(
        f"[Tool 4] refresh_runner subprocess exited rc={rc}; see {log_path}"
    )

status = json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/refresh_status.json")
    .rstrip(b"\x00").decode("utf-8")
)
if status.get("status") != "success":
    raise RuntimeError(
        f"[Tool 4] subprocess returned 0 but refresh_status.json "
        f"status='{status.get('status')}'; errors={status.get('errors')}"
    )
print(f"[Tool 4] subprocess refresh complete "
       f"(rc=0, status=success, elapsed={status.get('elapsed_seconds')}s)")

# User-facing success message (Rule 6 + Rule 7).
DATASETS = ", ".join(json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8")
).get("datasets", {}).keys())
print(f"\n{DASHBOARD_NAME} live at {PORTAL_URL}")
print(f"- Refresh: daily (next cron tick picks it up; on-demand via [Refresh] button)")
print(f"- Datasets: {DATASETS}")
```

**Why subprocess and not in-process.** The runner subprocess re-execs every PULLS entry + `build_dashboard(folder)` inside a fresh Python interpreter using real imports. PRISM's in-session `run_pull` / `build_dashboard` calls use the same engine code via the same imports — but in-session globals (any name PRISM happened to define earlier in the session) could shadow real names. The subprocess proves the persisted scripts work in a clean interpreter. **Per-dashboard subprocess** also means a slow Haver pull on this dashboard cannot stall any other dashboard's refresh on the same cron tick.

**No timeout on the subprocess.** The previous model used `subprocess.run(..., timeout=600, capture_output=True)`. Both flags caused frequent hangs (`capture_output=True` buffers everything in memory; `timeout=600` rejected legitimately slow Haver pulls). The new pattern is `Popen` + log file (the runner streams stdout/stderr to the log) + `wait()` (no arbitrary timeout — let the runner decide). The browser polls `refresh_status.json` separately for liveness.

---

## §C. Recipe 2 — CRUD on `manifest_template.json`

For ADD / EDIT / EXTEND on an existing dashboard's spec — add a chart, append a tab, edit a filter, change a chart_type, swap a dataset key, tweak metadata. **Raw JSON CRUD**, never wholesale rewrite. The §A.2 path-decision table is the trigger: any of those user-asks routes here.

The five-step skeleton:

1. **AUDIT** — `_audit_dashboard_layout(folder)`; raises if folder isn't canonical.
2. **READ** — load template from S3, `deepcopy` for mutation safety.
3. **MUTATE** — surgical mutation per the patterns below.
4. **VALIDATE** — `validate_manifest(tpl)` raises on schema violations.
5. **WRITE** — persist to S3.
6. **VERIFY** — `build_dashboard(folder)` recompiles against current data; surfaces shape errors immediately.

```python
import json, copy

DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# 1. AUDIT
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)

# 2. READ + deepcopy
tpl = copy.deepcopy(json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8")))

# 3. MUTATE (pick the pattern from C.1-C.8 below)
# ...

# 4. VALIDATE
validate_manifest(tpl)

# 5. WRITE
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")

# 6. VERIFY (in-process recompile against current data)
build_dashboard(DASHBOARD_PATH)
```

### C.0 The `_walk_rows` helper

Widgets live in one of two places depending on `tpl["layout"]["kind"]`:

| `kind` | Widgets at | Iterate via |
|---|---|---|
| `"grid"` (default) | `tpl["layout"]["rows"][i][j]` | nested for-loop over rows |
| `"tabs"` | `tpl["layout"]["tabs"][k]["rows"][i][j]` | nested for-loop over tabs → rows |

Inline this small helper at the top of any CRUD script:

```python
def _walk_rows(tpl):
    """Yield (location_dict, row_list) pairs across both layout kinds.
    location_dict carries the route back to the row for in-place mutation:
      {"tab_id": "<id>", "row_idx": i}  for tabs layout
      {"row_idx": i}                    for grid layout
    """
    layout = tpl["layout"]
    if layout.get("kind") == "tabs":
        for tab in layout["tabs"]:
            for i, row in enumerate(tab["rows"]):
                yield {"tab_id": tab["id"], "row_idx": i}, row
    else:
        for i, row in enumerate(layout["rows"]):
            yield {"row_idx": i}, row

def _find_widget(tpl, widget_id):
    for loc, row in _walk_rows(tpl):
        for j, w in enumerate(row):
            if w.get("id") == widget_id:
                return w, {**loc, "col_idx": j}
    raise KeyError(f"widget {widget_id!r} not in manifest_template")
```

### C.1 Append a widget to a tab.row

```python
NEW_WIDGET = {
    "widget": "chart", "id": "curve_real", "w": 6,
    "title": "Real 10y curve",
    "spec": {"chart_type": "line", "dataset": "rates_real",
             "mapping": {"x": "date", "y": "real_10y", "y_title": "Real 10y (%)"}},
}

tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == "overview")
while len(tab["rows"]) <= 2:
    tab["rows"].append([])
tab["rows"][2].append(NEW_WIDGET)
```

### C.2 Insert a widget at a specific column position

When the ask is "put the new chart NEXT TO the curve chart" (not at the end of the row):

```python
w, loc = _find_widget(tpl, "curve_lvl")
tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == loc["tab_id"])
tab["rows"][loc["row_idx"]].insert(loc["col_idx"] + 1, NEW_WIDGET)
```

### C.3 Replace a widget's spec by id

When the ask is "change the curve chart from line to multi_line":

```python
w, _ = _find_widget(tpl, "curve_lvl")
w["spec"]["chart_type"] = "multi_line"
w["spec"]["mapping"]["color"] = "series"
```

In-place mutation on the dict returned by `_find_widget` mutates the template — the helper returns the actual ref, not a copy.

### C.4 Remove a widget by id

```python
w, loc = _find_widget(tpl, "curve_2s10s")
rows = (next(t["rows"] for t in tpl["layout"]["tabs"] if t["id"] == loc["tab_id"])
        if "tab_id" in loc else tpl["layout"]["rows"])
del rows[loc["row_idx"]][loc["col_idx"]]
if not rows[loc["row_idx"]]:
    del rows[loc["row_idx"]]
```

### C.5 Add a new tab

```python
NEW_TAB = {
    "id": "credit", "label": "Credit",
    "description": "IG and HY spreads, default rates, issuance.",
    "rows": [],   # widgets get appended via C.1 / C.2
}

tabs = tpl["layout"]["tabs"]
after_idx = next(i for i, t in enumerate(tabs) if t["id"] == "rates")
tabs.insert(after_idx + 1, NEW_TAB)
```

### C.5b Convert a grid layout to tabs (then add the new tab via C.5)

When the inherited template is `kind: "grid"` (no `tabs` wrapper), C.5 doesn't apply directly — there is no `tabs[]` to insert into. Convert in place first, then run C.5 against the now-tabbed layout. The conversion preserves every widget by promoting the existing `rows` into a single tab.

```python
layout = tpl["layout"]
if layout.get("kind") != "tabs":
    existing_rows = layout.get("rows", [])
    cols = layout.get("cols", 12)
    # Pick a stable id for the inherited content. Use the manifest id
    # (or a domain noun if obvious) so future C.5 inserts don't collide.
    seed_tab_id = tpl.get("id", "main").replace("_", "-")
    tpl["layout"] = {
        "kind": "tabs", "cols": cols,
        "tabs": [{
            "id": seed_tab_id, "label": tpl.get("title", "Overview"),
            "description": "Inherited content (auto-promoted from grid layout).",
            "rows": existing_rows,
        }],
    }
```

After the conversion, the §C.5 add-a-tab pattern works unchanged. Filter `targets`, `show_when` references, and `links[].members` are widget-id keyed, NOT layout-shape keyed — they need no rewrite. The seed tab's `id` becomes part of the URL state (`?tab=<seed>`); pick something durable on first conversion to keep deep links stable.

### C.6 Add / update / remove a filter

```python
NEW_FILTER = {
    "id": "country", "type": "multiSelect", "label": "Country",
    "field": "country",
    "options": ["US", "DE", "JP", "UK"],
    "default": ["US", "DE"],
    "targets": ["fx_curve", "fx_carry_table"],
}
tpl.setdefault("filters", []).append(NEW_FILTER)

# Update an existing filter's default / options
f = next(f for f in tpl["filters"] if f["id"] == "lookback")
f["default"] = "1Y"
f["options"] = ["3M", "6M", "1Y", "2Y", "5Y"]

# Remove
tpl["filters"] = [f for f in tpl.get("filters", []) if f["id"] != "doomed_filter_id"]
```

### C.7 Add / remove a dataset slot

`manifest_template.json` carries dataset SLOTS — each slot's `source` field is empty in the template, populated at compile time by `populate_template(tpl, datasets)` inside `build_dashboard()`. Adding / removing a slot in the template is HALF the change; the other half is editing `pull_data.py` (so a CSV with the matching stem lands in `data/`) or `build.py` (so a transform produces it as a derived dataset).

```python
# Add
tpl.setdefault("datasets", {})
tpl["datasets"]["rates_real"] = {
    "source": [],
    "schema": {"date": "datetime", "real_10y": "float", "real_5y": "float"},
}

# Remove the slot AND every widget that referenced it
del tpl["datasets"]["rates_real"]
referencing_ids = set()
for loc, row in _walk_rows(tpl):
    for w in row:
        if w.get("spec", {}).get("dataset") == "rates_real":
            referencing_ids.add(w["id"])
for wid in referencing_ids:
    w, loc = _find_widget(tpl, wid)
    rows = (next(t["rows"] for t in tpl["layout"]["tabs"] if t["id"] == loc["tab_id"])
            if "tab_id" in loc else tpl["layout"]["rows"])
    rows[loc["row_idx"]].remove(w)
```

### C.8 Patch metadata fields

```python
md = tpl.setdefault("metadata", {})
md["sources"] = ["GS Market Data", "Haver", "FRED"]
md["tags"] = ["rates", "credit"]
md["refresh_frequency"] = "daily"
md["summary"] = {"title": "Today's read",
                  "body": "Front-end has richened ~6bp on a softer print."}
```

The three required fields per §2.3 (`kerberos` / `dashboard_id` / `methodology`) must be non-empty; if the inherited template is missing any, set them BEFORE the rest of the mutation.

### C.9 The CRUD contract (5 rules)

| # | Rule | Consequence of skipping |
|---|---|---|
| 1 | AUDIT before mutating | Edits land on a non-compliant folder; runner picks up wrong bytes |
| 2 | `deepcopy` the loaded template before mutation | In-session re-runs see prior mutation state; bugs are non-reproducible |
| 3 | `validate_manifest(tpl)` BEFORE writing | Schema-broken template ships; refresh runner fails on the next tick |
| 4 | `build_dashboard(folder)` BEFORE surfacing the change | Data-shape break passes validate but breaks at compile; user sees broken render |
| 5 | Surgical mutation on inherited templates; never wholesale rewrite | Mutation drops widgets / tabs / filters PRISM didn't include in this script's dict |

For rare patterns not covered by C.1-C.8 (multi-target filter rebinding, `show_when` reference cleanup, link member rewrites), fetch `dashboards/template_crud.md` — it's a thin spoke that points back here for the daily patterns.

---

## §D. Recipe 3 — Add / edit a pull pipeline

When `pull_data.py` needs to change (Steps 2 or 3 of the reuse ladder in `dashboards/pipelines.md` §3), READ → MUTATE → WRITE on the persisted bytes — never re-emit the whole script from a fresh string for an "add" / "edit" / "extend" ask.

The six steps:

1. **AUDIT** — `_audit_dashboard_layout(folder)`.
2. **READ** — fetch live `pull_data.py` bytes from S3.
3. **MUTATE** — `str.replace` against a unique anchor; `assert new_src != src` so silent no-ops surface as errors.
4. **WRITE** — `s3_manager.put(new_src.encode("utf-8"), f"{folder}/scripts/pull_data.py")`.
5. **VERIFY** — `run_pull(folder, '<new_or_changed_pull>')`; read the resulting CSV to confirm columns / shape.
6. **PROPAGATE** — if the dataset shape changed (column rename, new column needed by a widget), edit `build.py` transforms (same READ → MUTATE → WRITE) and `manifest_template.json` (§C). Then `build_dashboard(folder)` to verify end-to-end.

```python
DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# 1. AUDIT
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)

# 2. READ
src = s3_manager.get(f"{DASHBOARD_PATH}/scripts/pull_data.py").decode("utf-8")

# 3. MUTATE -- add a new pull function + PULLS entry
#    The anchor here is the closing brace of the PULLS dict; we add the
#    new entry just above it. Multi-line anchor with leading whitespace
#    is stable across reformatting.
new_src = src.replace(
    "PULLS = {\n    'rates': pull_rates,\n}",
    "def pull_cpi():\n"
    "    pull_haver_data(\n"
    "        codes=['JCXFE@USECON', 'PCUSLFE@USECON'],\n"
    "        name='cpi', output_path=f'{SESSION_PATH}/data',\n"
    "        s3_manager=s3_manager,\n"
    "    )\n"
    "\n"
    "PULLS = {\n"
    "    'rates': pull_rates,\n"
    "    'cpi':   pull_cpi,\n"
    "}",
)
assert new_src != src, "anchor not found in live pull_data.py"

# Also need to import pull_haver_data if it wasn't already; second mutation
new_src2 = new_src.replace(
    "from ai_development.mcp.utils.data_functions import (\n"
    "    pull_market_data, save_artifact,\n"
    ")",
    "from ai_development.mcp.utils.data_functions import (\n"
    "    pull_market_data, pull_haver_data, save_artifact,\n"
    ")",
)
assert new_src2 != new_src, "import-line anchor not found"

# 4. WRITE
s3_manager.put(new_src2.encode("utf-8"),
                f"{DASHBOARD_PATH}/scripts/pull_data.py")

# 5. VERIFY -- run just the new pull, in-process; read the CSV back
run_pull(DASHBOARD_PATH, "cpi")
df = pd.read_csv(io.BytesIO(s3_manager.get(f"{DASHBOARD_PATH}/data/cpi.csv")),
                  index_col=0, parse_dates=True)
print(f"[verify] cpi: shape={df.shape} cols={df.columns.tolist()}")

# 6. PROPAGATE -- add a new dataset slot to the template + a chart that uses it
tpl = copy.deepcopy(json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8")))
tpl["datasets"]["cpi"] = {"source": [], "schema": {"date": "datetime", "core_cpi": "float"}}
# ... append a chart widget per C.1 ...
validate_manifest(tpl)
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
                f"{DASHBOARD_PATH}/manifest_template.json")

# In-process recompile against current data
build_dashboard(DASHBOARD_PATH)
```

**Anchor selection.** Pick the SMALLEST contiguous string that uniquely identifies the insertion point. Multi-line anchors with leading whitespace are stable across reformatting; single-token anchors collide. Always include enough context (one line above, one line below) that the anchor is unique. The `assert new_src != src` guards against silent no-op when the anchor drifts.

**Multi-anchor sequencing.** When ONE edit needs two or more `str.replace`s (e.g. extending a `pull_*_data` import line AND extending the `PULLS` dict, OR renaming a function AND every caller), CHAIN the assertions against the prior intermediate, never against the original `src`. If both asserts compare to `src`, the second can pass even when the second `replace` was a no-op (because the first already mutated):

```python
src      = s3_manager.get(...).decode("utf-8")
new_src1 = src.replace(IMPORT_OLD, IMPORT_NEW)
assert new_src1 != src,      "import-line anchor not found"
new_src2 = new_src1.replace(PULLS_OLD, PULLS_NEW)
assert new_src2 != new_src1, "PULLS-dict anchor not found"   # against new_src1, NOT src
s3_manager.put(new_src2.encode("utf-8"), ...)
```

The `new_src1` baseline is what catches the second-anchor drift. Asserting both against `src` would silently accept a half-applied edit when the second anchor has been reformatted out from under PRISM since the first build.

**When the dataset shape changes — the build.py transform edit.** If the new pull adds a column that an existing chart needs to render, OR the new pull is meant to feed a derived dataset (a join, a YoY column), the `build.py` edit follows the same READ → MUTATE → WRITE pattern:

```python
src = s3_manager.get(f"{DASHBOARD_PATH}/scripts/build.py").decode("utf-8")
new_src = src.replace(
    "TRANSFORMS = [derive_spread]",
    "def derive_real_yields(datasets):\n"
    "    nominal = datasets['rates_eod']\n"
    "    cpi = datasets['cpi']\n"
    "    inflation_compensation = cpi['core_cpi'].pct_change(12) * 100\n"
    "    real = nominal[['us_10y']].copy()\n"
    "    real['real_10y'] = real['us_10y'] - inflation_compensation\n"
    "    datasets['rates_real'] = real.reset_index()\n"
    "    return datasets\n"
    "\n"
    "TRANSFORMS = [derive_spread, derive_real_yields]",
)
assert new_src != src, "anchor not found in live build.py"
s3_manager.put(new_src.encode("utf-8"), f"{DASHBOARD_PATH}/scripts/build.py")
build_dashboard(DASHBOARD_PATH)   # in-process recompile, runs the new transform
```

**Pipeline reuse decision.** Before authoring a new pull function, walk the reuse ladder in `dashboards/pipelines.md` §3:

- Step 1 — does the widget need columns from a CSV that ALREADY exists in `data/`? Then REUSE — no `pull_data.py` change.
- Step 2 — does the widget need a new column from a SOURCE that's already wired up in `pull_data.py`? Then EXTEND the existing pull function's argument list (one anchor edit on the pull function body).
- Step 3 — does the widget need a NEW SOURCE? Then ADD a new pull function as shown above.

Most "add a column" asks resolve to Step 1 or 2. Step 3 is the rarer case (new vendor, new alt-data source).

---

## §E. Recipe 4 — Refresh discipline

Three operations, one canonical use for each:

| Operation | Use when | In-process or subprocess? | Cost |
|---|---|---|---|
| `run_pull(folder, '<name>')` | Iterating on ONE pipeline during dev — the user just changed `pull_<name>` and wants to see the new CSV | In-process | Fast (one source) |
| `build_dashboard(folder)` | After ANY edit to `manifest_template.json` (§C) or `build.py` `TRANSFORMS` (§D) — recompile against current `data/*.csv` | In-process | Fast (no fresh pulls; just load + populate + compile + write) |
| `refresh_dashboard(folder)` | When the user wants a clean-slate refresh from in-session AND every pull is fast | In-process | Slow (every pull runs sequentially) |
| `subprocess.run(refresh_runner.py)` | Final action of Recipe 1 (Tool 4); after a pipeline-shape change in §D; whenever you want a fresh-interpreter refresh | Subprocess | Slow + isolated (clean Python process) |

**Why in-process for `build_dashboard`.** The build is just JSON + CSV loading + populate + compile + write. ~1-3 seconds for a typical dashboard. There's no reason to spawn a subprocess for it; the in-session iteration loop is fast.

**Why subprocess for the FINAL `refresh_dashboard`.** Recipe 1's Tool 4 spawns `refresh_runner.py` even though it could call `refresh_dashboard(folder)` in-process — the subprocess proves the persisted scripts work in a CLEAN Python interpreter (no in-session globals shadowing real names). The user's first view of the dashboard at the portal URL is byte-identical to what tomorrow's cron will produce. For mid-iteration "let me see the latest", in-process `build_dashboard()` is fine.

**Why per-dashboard subprocess in the cron.** The hourly cron (`refresh_dashboards.py`) walks every user, then per-due-dashboard spawns `refresh_runner.py` as its own subprocess. A slow Haver pull on dashboard A cannot stall dashboard B's refresh on the same cron tick. Per-dashboard isolation is the design.

---

## §F. Recipe 5 — Manifest exploration patterns

When PRISM picks up an existing dashboard, build a mental model of what's there before mutating. Two scripts: a HIGH-LEVEL GLANCE (~30 lines) for routine pickups, a DEEP GLANCE (~60 lines) for substantial changes.

### F.1 HIGH-LEVEL GLANCE — counts + top-level shape

```python
import json

DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
tpl = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8"))

print(f"id:          {m.get('id')}")
print(f"title:       {m.get('title')}")
print(f"theme:       {m.get('theme')}  palette: {m.get('palette')}")
print(f"layout:      {m['layout'].get('kind', 'grid')}")

if m["layout"].get("kind") == "tabs":
    tabs = m["layout"]["tabs"]
    print(f"tabs:        {len(tabs)} -- {[t['id'] for t in tabs]}")
    widget_count = sum(len(row) for tab in tabs for row in tab["rows"])
else:
    widget_count = sum(len(row) for row in m["layout"]["rows"])
print(f"widgets:     {widget_count}")

datasets = m.get("datasets", {})
print(f"datasets:    {len(datasets)} -- {list(datasets)}")

filters = m.get("filters", [])
print(f"filters:     {len(filters)} -- {[(f['id'], f['type']) for f in filters]}")

links = m.get("links", [])
print(f"links:       {len(links)} -- {[(l['id'], l.get('kind')) for l in links]}")

md = m.get("metadata", {})
print(f"refresh:     {md.get('refresh_frequency', 'daily')} "
       f"(last: {md.get('data_as_of')})")
print(f"sources:     {md.get('sources')}")
```

### F.2 DEEP GLANCE — per-widget / per-filter / per-dataset breakdown

```python
import json, io
import pandas as pd

DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))

print("=" * 60)
print("WIDGETS")
print("=" * 60)
def _walk(layout):
    if layout.get("kind") == "tabs":
        for tab in layout["tabs"]:
            for i, row in enumerate(tab["rows"]):
                for j, w in enumerate(row):
                    yield tab["id"], i, j, w
    else:
        for i, row in enumerate(layout["rows"]):
            for j, w in enumerate(row):
                yield None, i, j, w

for tab_id, ri, ci, w in _walk(m["layout"]):
    loc = f"tabs/{tab_id}/r{ri}c{ci}" if tab_id else f"r{ri}c{ci}"
    kind = w.get("widget", "?")
    title = w.get("title") or w.get("label") or w.get("id", "")
    line = f"  {kind:<10} id={w.get('id', '?'):<28} w={w.get('w', '?'):<3} {loc:<22} :: {title}"
    if kind == "chart":
        spec = w.get("spec", {})
        line += f"  type={spec.get('chart_type')} dataset={spec.get('dataset')}"
    elif kind in ("kpi", "stat_grid"):
        line += f"  source={w.get('source') or [it.get('source') for it in w.get('items', [])]}"
    elif kind == "table":
        line += f"  dataset={w.get('dataset')}"
    elif kind == "tool":
        td = w.get("tool_def", {})
        line += f"  tool={td.get('name')} inputs={len(td.get('inputs', []))} outputs={len(td.get('outputs', []))}"
    print(line)

print("\n" + "=" * 60)
print("DATASETS  (CSVs on disk + manifest declarations)")
print("=" * 60)
for entry in s3_manager.list(f"{DASHBOARD_PATH}/data/"):
    key = entry.get("Key") if isinstance(entry, dict) else entry
    if not key or not key.endswith(".csv"):
        continue
    stem = key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    df = pd.read_csv(io.BytesIO(s3_manager.get(key)))
    in_manifest = "  declared" if stem in m.get("datasets", {}) else "  ORPHAN"
    print(f"  {stem:<28} rows={len(df):<6} cols={df.columns.tolist()[:6]}  {in_manifest}")

print("\n" + "=" * 60)
print("FILTERS")
print("=" * 60)
for f in m.get("filters", []):
    print(f"  {f['id']:<24} type={f['type']:<14} field={f.get('field')!r:<22} "
           f"targets={f.get('targets')}")

print("\n" + "=" * 60)
print("PIPELINES  (from scripts/pull_data.py)")
print("=" * 60)
src = s3_manager.get(f"{DASHBOARD_PATH}/scripts/pull_data.py").decode("utf-8")
ns = {"__name__": "_glance", "__builtins__": __builtins__}
exec(compile(src, f"{DASHBOARD_PATH}/scripts/pull_data.py", "exec"), ns)
print(f"  PULLS keys: {list(ns.get('PULLS', {}))}")

src = s3_manager.get(f"{DASHBOARD_PATH}/scripts/build.py").decode("utf-8")
ns = {"__name__": "_glance", "__builtins__": __builtins__}
exec(compile(src, f"{DASHBOARD_PATH}/scripts/build.py", "exec"), ns)
print(f"  TRANSFORMS:  {[fn.__name__ for fn in ns.get('TRANSFORMS', [])]}")
```

The DEEP GLANCE surfaces three kinds of drift PRISM should resolve before the requested edit:
- **Manifest-orphan CSVs** — a CSV in `data/` whose stem isn't in `manifest.datasets`. Either register it or move to `archive/<UTC>/`.
- **Empty `PULLS` / `TRANSFORMS`** — when the script is structurally valid but the registry / list is empty, the next refresh produces nothing useful.
- **Filter targets pointing at non-existent widgets** — the validator catches this at compile time, but the DEEP GLANCE makes it visible before mutation.

---

## §G. Recipe 6 — Revert

Reverting an edit is "re-edit the surface to the prior state". The prior state lives in one of three places, in this preference order:

| Source | When it applies | How |
|---|---|---|
| **Chat history** | The user just asked to undo the most recent edit and PRISM still has the prior version of the changed file in the conversation history | Re-author the surface to the prior bytes via the same READ → MUTATE → WRITE pattern that produced the bad edit. For `manifest_template.json` use §C; for the two scripts use §D. The "edit" here is "set bytes to <prior content>". After WRITE, run `build_dashboard(folder)` to verify. |
| **`history/<UTC>/` snapshots** | The dashboard has `keep_history: true` in its registry entry AND the rollback target is older than the chat history | List `s3_manager.list(f"{DASHBOARD_PATH}/history/")`; each `<UTC>/` subfolder contains the canonical 5 paths as they were at that timestamp. Copy the relevant file into the live path via `s3_manager.put`. After restore, run `build_dashboard(folder)` to recompile against current data. |
| **Re-build from the user's description** | Neither chat history nor `history/` carries the prior state | Author the prior state from the user's description (just like a fresh CRUD edit per §C). Surface a diff vs current state before writing. The user is the source of truth here, not PRISM's memory. |

After any revert, the same `build_dashboard(folder)` recompile + `_audit_dashboard_layout(folder)` audit applies — a botched revert is harder to recover from than the original bad change. Treat a revert as a normal CRUD edit; same gates apply.

**No script versioning machinery.** Earlier iterations of this hub maintained a `scripts/versions/<name>_v<N>.py` chain with lockstep coupling between `pull_data` and `build`. That machinery is retired — the chat history (PRISM's primary memory of what changed) plus optional `history/<UTC>/` snapshots cover the recovery cases that matter, without the audit overhead of monotonic version chains. If you find yourself needing more than chat-history recovery, set `keep_history: true` on the registry entry; the runner will write a snapshot to `history/<UTC>/` on every successful refresh.

---

## 6. Pull primitives + `save_artifact` cheat sheet

Inside `pull_data.py` they all land their CSVs in the same flat folder by passing `output_path=f'{SESSION_PATH}/data'`. Per Rule 5, `SESSION_PATH` is a literal `pull_data.py` self-defines on its first line.

| Function | Call | On-disk CSV | Metadata sidecar | Manifest key |
|---|---|---|---|---|
| `pull_haver_data` | `pull_haver_data(codes=[...], start='YYYY-MM-DD', name='cpi', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/cpi.csv` | `data/cpi_metadata.json` | `'cpi'` |
| `pull_market_data` (eod) | `pull_market_data(coordinates=[...], start='YYYY-MM-DD', name='rates', mode='eod', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/rates_eod.csv` (always `_eod` suffix) | `data/rates_metadata.json` (no suffix) | `'rates_eod'` |
| `pull_market_data` (intraday) | same but `mode='iday'` | `data/rates_intraday.csv` | `data/rates_metadata.json` | `'rates_intraday'` |
| `pull_plottool_data` | `pull_plottool_data(expressions=[...], labels=[...], start='YYYY-MM-DD', name='swap_curve', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/swap_curve.csv` | `data/swap_curve_metadata.json` | `'swap_curve'` |
| `pull_fred_data` | `pull_fred_data(series=[...], start='YYYY-MM-DD', name='unrate', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/unrate.csv` | `data/unrate_metadata.json` | `'unrate'` |
| `save_artifact` | `save_artifact(data, name='gs_bank', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/gs_bank.csv` (or `.json` if dict) | none | `'gs_bank'` |

Three rules from the table that are easy to get wrong:

1. **`name=` does NOT include `_eod` / `_intraday`.** `pull_market_data` appends them. Pass `name='rates'` → `data/rates_eod.csv`. Pass `name='rates_eod'` → `data/rates_eod_eod.csv` (broken).
2. **`pull_market_data` metadata sidecar uses the bare `name`,** not the suffixed CSV stem. So `name='rates'` produces `data/rates_metadata.json` (one file even when both eod and intraday CSVs exist).
3. **`mode='eod'` is the default** but pass it explicitly. The intraday CSV is only written when `mode in ('iday', 'both')`. See §6.1 for the defensive try/except wrap.

### 6.1 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_<name>` function that fetches intraday MUST wrap it in `try/except` with EOD fallback. Every `derive_<name>` transform must handle missing intraday file defensively (the engine loads CSVs that exist; a missing intraday CSV simply doesn't appear in the datasets dict).

```python
def pull_rates():
    pull_market_data(
        coordinates=[...], start='2020-01-01',
        name='rates', mode='eod',
        output_path=f'{SESSION_PATH}/data',
        s3_manager=s3_manager,
    )
    try:
        pull_market_data(
            coordinates=[...], mode='iday',
            start=datetime.now().strftime('%Y-%m-%d'),
            name='rates',
            output_path=f'{SESSION_PATH}/data',
            s3_manager=s3_manager,
        )
    except Exception as e:
        print(f"Intraday unavailable (normal overnight/weekends): {e}")
```

The same `multi_line` chart spec works for daily EOD and intraday minute-bar data — no special manifest configuration. Compact / sparkline-shaped intraday tiles can drop the slider via `spec.chart_zoom = {"slider": false}` to reclaim ~28px (`dashboards/filters.md` §3).

### 6.2 `save_artifact()` for alt data

The four pull primitives only cover Haver / GS Market Data / TSDB expressions / FRED. For everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, scraped tables, hand-built DataFrames), `save_artifact()` is the universal save helper. Same `output_path` semantics; lands a CSV (or JSON for `dict` payloads) at `{output_path}/{name}.{ext}` and is idempotent on re-run.

```python
def pull_gs_bank():
    from ai_development.mcp.clients.fdic_client import fdic_client
    fdic_records = fdic_client.get_bank_financials(cert=33124, quarters=8)
    save_artifact(fdic_records, name='gs_bank',
                   output_path=f'{SESSION_PATH}/data',
                   s3_manager=s3_manager)
    # -> {SESSION_PATH}/data/gs_bank.csv
```

`save_artifact()`'s output extension follows the input: DataFrame / `list[dict]` / object-with-`.to_frame()` → CSV; `dict` (or empty list) → JSON. Transforms in `build.py` read JSON via `json.loads(s3_manager.get(...).decode('utf-8'))` if needed (the engine's CSV-only loader doesn't auto-load JSON files; do the load inside the transform).

---

## 7. Palettes

| Palette | Kind | Use |
|---------|------|-----|
| `gs_primary` | categorical | Default (navy, sky, gold, burgundy, …) |
| `gs_blues` | sequential | Heatmaps, calendar heatmaps, gradients |
| `gs_diverging` | diverging | Correlation matrices, z-score heatmaps |

Categorical → `option.color`. Sequential / diverging → `visualMap.inRange.color` (heatmaps, correlation matrices).

Brand hex anchors for `series_colors`: GS Navy `#002F6C`, GS Sky `#7399C6`, GS Gold `#B08D3F`, GS Burgundy `#8C1D40`, GS Forest `#3E7C17`, GS Positive `#2E7D32`, GS Negative `#B3261E`.

---

## 8. Anti-patterns

**Data integrity:**

| Anti-pattern | Do instead |
|--------------|-----------|
| `np.random.*` / `np.linspace` / `np.arange` / hand-typed arrays as data; `np.zeros()` fill for missing values | Pull real data first (Recipe 1). If no source, don't build the panel; render a note or use a small real slice |
| Authoring `build.py` before any pull function produced a real CSV | Run pulls first, print shapes / heads / dtypes, write transforms against verified columns |
| Literal numbers in manifest JSON | Pass the DataFrame; compiler converts |
| KPI tile authored as `{"widget": "kpi", "label": "Cut prob", "value": 68, "suffix": "%"}` — hand-typed `value` without `source` | Validator rejects with `kpi_static_value_forbidden` (always-blocking). Wire the value through a dataset: `{"widget": "kpi", "label": "Cut prob", "source": "fed.latest.cut_prob", "suffix": "%"}` so the next refresh re-resolves it from `data/fed.csv`. If the number isn't already in a CSV, add a transform in `build.py` that derives it from existing pulls (Rule 1) |
| `stat_grid` items authored with literal `value: <num>` and no `source` | Same fix: `stat_grid_static_value_forbidden` (always-blocking). Each stat must set `source: "<ds>.<aggregator>.<col>"` |
| PRISM hand-writing HTML / CSS / JS, or `build.py` doing anything beyond defining `TRANSFORMS` | Emit manifest dicts; let `compile_dashboard()` do the rest. The one exception: `tool_def.compute_js` is a JS string LITERAL embedded in the Python dict (§A.1.1) |
| Hand-tuning `y_title_gap` / `grid.left` | Just set `x_title` / `y_title`; compiler sizes from real label widths |

**Atomicity of the build flow (Rule 7):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Returning to the user with "Next steps: I can now create `pull_data.py` and `build.py`, register the dashboard, set up daily refresh — would you like me to continue?" after `compile_dashboard()` produced an in-session HTML | Rule 7 violation: there are no "next steps" — Tools 1+2+3+4 are atomic. Run all four tools without returning to the user; only the post-Tool-4 portal URL is user-facing |
| Compiling in-session, surfacing the rendered HTML to the user, then deferring `scripts/pull_data.py` / `scripts/build.py` / registry write to a follow-up turn | The in-session compile and the on-S3 build are two different code paths. Without scripts on S3, the [Refresh] button raises `FileNotFoundError`. Author the scripts FIRST (Tool 1 + Tool 2), then register (Tool 3) |
| Asking the user to choose between a "preview" / "session-only" version and a "persistent" / "production" version of a dashboard | There is no preview state. A dashboard is either fully built (Tools 1-4 all passed) or it does not exist |
| Phrasing user-facing messages with "to make this fully persistent" / "would you like me to set up auto-refresh" / "I can also build pull_data and build.py" | Forbidden language. Strip the phrase; the only message after a successful Tool 4 is the portal URL block |

**Edit discipline (§C / §D):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Wholesale rewrite of `manifest_template.json` from a fresh dict on an "add a chart" ask | §C surgical CRUD — load existing template, deepcopy, mutate in place, validate, write. Rebuilding from scratch silently wipes every widget / tab / filter PRISM didn't include in the fresh dict |
| Re-emitting the WHOLE `pull_data.py` body as a fresh string on an "add a column" ask | §D surgical mutation — fetch live bytes, `str.replace` against an anchor, `assert new_src != src`, write. Re-emission risks dropping in-flight content PRISM partly remembers |
| `str.replace` without `assert new_src != src` | The assert turns silent no-op (anchor drift) into a loud error. Always include it |
| Editing `dashboard.html` or `manifest.json` directly to "fix a render bug" | Both are derived; the next refresh overwrites them. Fix the spec or the transforms instead |
| Persisting `scripts/build.py` with `compile_dashboard(..., strict=False)` inside a transform | The engine's `build_dashboard()` always uses `strict=True`. Transforms only mutate the datasets dict; they don't call `compile_dashboard` themselves |
| `try/except` around a transform that swallows errors | Let exceptions propagate. The runner catches the `ValueError` and records `last_refresh_status="error"`; the structured error modal surfaces the diagnostic |
| Loading CSV files into transforms manually (`pd.read_csv(...)` inside `derive_*`) | The engine loads every CSV in `data/` before calling transforms. Read from the `datasets` dict the engine passes in, keyed by CSV stem |

**Persistence + the build flow:**

| Anti-pattern | Do instead |
|--------------|-----------|
| `registry[DASHBOARD_NAME] = entry` — writing the new dashboard as a TOP-LEVEL key in `dashboards_registry.json` | `registry['dashboards'].append(entry)` (or replace-by-id). The hourly refresh runner only iterates `registry['dashboards']`; a top-level-keyed entry is invisible → 404 → no `refresh_status.json` |
| Treating `update_user_manifest(kerberos, artifact_type='dashboard')` as the registry-write step | It only updates `users/{kerberos}/manifest.json`'s pointer block. Save the registry with `s3_manager.put(...)` FIRST, then call the wrapper |
| Setting `last_refreshed` / `last_refresh_status` to the build timestamp at registration time | Leave both as `null` at registration; the refresh runner owns those fields and overwrites them on the first real refresh |
| S3 paths with leading slash (`/users/...`) or `folder` with trailing slash | Live registry convention: no leading slash, no trailing slash on `folder`; `data_path` points to the `data/` directory, not `manifest.json` |

**Data routing (Rule 5):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Calling any `pull_*_data` / `save_artifact` WITHOUT `output_path=f'{SESSION_PATH}/data'` | Always pass `output_path`. Otherwise CSVs land in per-source subfolders and `build_dashboard()`'s `data/<name>.csv` discovery misses them |
| Passing `name='rates_eod'` to `pull_market_data` (function appends another `_eod` → `data/rates_eod_eod.csv`) | Pass `name='rates'`. Sidecar uses the bare name (`data/rates_metadata.json`) |
| `manifest.datasets` keys NOT matching on-disk CSV stems (key `'rates'` while CSV is `data/rates_eod.csv`) | Make the dataset key the CSV stem byte-for-byte: `'rates_eod'`, `'rates_intraday'`, `'cpi'` |
| Setting `metadata.refresh_enabled = False` to hide the browser `Refresh` button | The field is retired — the button is non-suppressible from the manifest. Drop the field; rely on the structured error modal to surface failures |

**Layout (§4.1):**

| Anti-pattern | Do instead |
|--------------|-----------|
| `widget: "chart"` with any `w` other than `cols//2` (2-up) or `cols//3` (3-up) | Validator rejects with `chart widget width must be 4 or 6...`. Use `w: 6` paired with another chart, or `w: 4` in a 3-up tile row. KPIs, tables, markdown, notes, and dividers may still span any width |
| A single-chart row | Split into two complementary views (level + change, nominal + real, US + cross-country) and run 2-up. The 2-up framing is the dashboard idiom; one-up is the wide-PNG idiom (use Altair's `make_chart` instead) |
| `line` / `multi_line` / `area` with >4 y-series (wide `y: [list]` of len 5+, OR long-form with a `color` column having 5+ distinct values) | Validator rejects with `chart_too_many_series` (always-blocking). Drop to ≤4 series (filter to top-N), bucket tail into "Other", split into small multiples (one widget per category, paired 2-up), or pivot framing (Index=100 normalisation, `correlation_matrix`, aggregate `stat_grid`) |

**Folder sanctity (Rule 4 + §2.5):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Leaving `scripts/build.bak` / `scripts/pull_data_old.py` next to the live files "for reference" | Move to `archive/<UTC>/` instead. The live `scripts/pull_data.py` and `scripts/build.py` are the only two files the runner reads |
| Renaming the live scripts to anything else (`scripts/main.py`, `scripts/refresh.py`, `scripts/build_dashboard.py`) | The runner reads `scripts/pull_data.py` and `scripts/build.py` exactly. No flexibility |
| Multiple manifest copies (`manifest.json` + `manifest_old.json` / `manifest_v2.json` / `manifest.20260424.json`) | Exactly one `manifest.json`. Quarantine the others to `archive/<UTC>/` |
| Per-source data subfolders (`data/haver/cpi.csv`, `data/market_data/rates_eod.csv`) | Flat `data/cpi.csv`, `data/rates_eod.csv`. Driven by `output_path=f'{SESSION_PATH}/data'` on every pull (Rule 5) |
| Self-suffix CSVs from the `pull_market_data` `name=` footgun (`data/rates_eod_eod.csv`) | Pass `name='rates'` (bare); the function appends `_eod`. Rename the broken file to `archive/<UTC>/` and re-run the pull with the right `name=` |
| Inheriting an existing non-compliant dashboard and proceeding directly with the surface change the user asked for | Run `_audit_dashboard_layout(folder)` FIRST; if it raises, re-author the missing canonical files before proceeding with the requested edit. Surface the trade transparently |

---

## 9. Pre-flight checklist

**Folder layout (Rule 4 + §2.5).** Run the sanctity audit; it raises if any of the canonical 5 are missing:

```python
m = json.loads(s3_manager.get(f'{DASHBOARD_PATH}/manifest.json').decode('utf-8'))
_audit_dashboard_layout(DASHBOARD_PATH, m)
```

**Configuration:**

- `metadata.kerberos`, `metadata.dashboard_id`, and `metadata.methodology` all set (validator hard-rejects the build without them — they gate the always-on Methodology / Refresh / Share chrome buttons)
- `metadata.data_as_of` set; `refresh_frequency` set. The browser `Refresh` button is non-suppressible from the manifest; do NOT add `metadata.refresh_enabled` (retired field, silently ignored)
- Registry entry **appended into `registry['dashboards']`** (not written as a top-level key); verify by re-loading and asserting `DASHBOARD_NAME in [d['id'] for d in registry['dashboards']]`
- `update_user_manifest(kerberos, artifact_type='dashboard')` called AFTER the registry write succeeds

**Data integrity:**

- Every dataset traces to a real pull (Rule 1)
- Every `pull_*_data(...)` and `save_artifact(...)` passes `output_path=f'{SESSION_PATH}/data'` (Rule 5)
- Every `pull_market_data` `name=` is the bare base (no `_eod` / `_intraday`)
- Every `manifest.datasets` key matches the on-disk CSV stem byte-for-byte
- Every `pull_<name>` function printed real shapes / heads / dtypes (or PRISM did so via `run_pull(folder, name)` then `pd.read_csv(...)`) before authoring `build.py` transforms; intraday handled defensively (§6.1)
- Datasets cleaned: `df.reset_index()` for DTI-keyed frames, plain English columns, no MultiIndex
- Every dataset backing a chart / table carries `field_provenance` (per-column `system` + `symbol`)
- Time-series pulls preserve full back-history (§10); never clip to the visible window

**Build mechanics:**

- `pull_data.py` defines `PULLS = {<name>: <fn>, ...}` at module level (engine reads this; nothing else)
- `build.py` defines `TRANSFORMS = [<fn>, ...]` at module level (engine reads this; nothing else). Empty list (`TRANSFORMS = []`) is fine for dashboards with no derivations
- Each function in `PULLS` and `TRANSFORMS` follows the contract: pulls take no args; transforms take and return the datasets dict
- Both scripts open with the explicit `SESSION_PATH = "<dashboard-path-literal>"` line (Rule 5)
- Both scripts use real Python imports for their helpers (no namespace dependency on what the runner injects)

**Atomicity (Rule 7):**

- Tools 1+2+3+4 ran in a single uninterrupted sequence; PRISM did NOT return to the user between them
- Tool 4's `subprocess` exited 0 AND `refresh_status.json` shows `status == "success"`
- `_audit_dashboard_layout(...)` ran at end of Tool 2 and passed
- Registry verification (re-load, assert id is in `registry['dashboards']`) passed at end of Tool 3
- The user-facing message is exactly the §B contract: portal URL on line 1, refresh frequency + datasets next; no "next steps", no "would you like me to…", no opt-in language

**Hand-off (Rule 6):** the success message leads with the portal URL (`/profile/dashboards/{id}/`); the `dashboard.html` S3 path is mentioned only if the user explicitly asks for it.

---

## 10. Time horizons

**Pull deep history.** The defaults below are initial zoom windows, not data-layer caps. Every time-series chart ships with a per-chart `dataZoom` slider (`dashboards/filters.md` §3) carrying the full dataset, and `dateRange` filters operate in view-mode by default with intervals `1M/3M/6M/YTD/1Y/2Y/5Y/All` — but both reach back only as far as the data goes.

If `pull_data.py` clips a 30-year FRED series to 2 years before persisting (or a transform slices / resamples / inner-joins it post-merge), those years are gone; the slider can't scroll into history that was never pulled. Loss of back-history at the PRISM transformation layer is irreversible from the dashboard side.

| Frequency | Initial zoom (default) | Rationale |
|-----------|------------------------|-----------|
| Quarterly / monthly | 10 years | Full business cycle |
| Weekly | 5 years | Trend + cycle |
| Daily | 2 years | Regime without noise |
| Intraday | 5 trading days | Event reaction window |

Override: if narrative references "highest since X", the initial window must include X (data still extends back as far as the source allows). For pre-pandemic comparisons set initial start ≥ 2015. Don't open at 12 months of monthly (hides cycle), 30 years of daily (noise), or different ranges for charts meant to be compared.
