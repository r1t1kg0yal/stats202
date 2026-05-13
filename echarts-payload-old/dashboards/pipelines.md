# Data pipelines + reuse ladder

Spoke fetched on demand from the dashboards hub. Covers the mental model for "how PRISM thinks about dashboard data flow" — the three-surface framing, pipeline cataloging, the reuse decision ladder, and active-pipeline integrity rules.

For the actual READ → MUTATE → WRITE patterns on `pull_data.py` see hub §D. For pickup-time exploration patterns see hub §F. For derived-dataset patterns in `build.py` see `recipes.md` §3.

---

## 1. The three persisted surfaces

A persistent dashboard's true artifact is three files: `scripts/pull_data.py` (the PULLS registry — every CSV under `data/` is the output of one pull function), `manifest_template.json` (the spec), and `scripts/build.py` (the TRANSFORMS hook). Everything else in the dashboard folder is byproduct that the daily / hourly refresh runner regenerates from those three:

```
  scripts/pull_data.py        (PULLS = {<name>: pull_<name>, ...})
     │ runner execs each PULLS entry; engine writes
     ▼
  data/<stem>.csv              (one CSV per pipeline)
     │ runner calls build_dashboard(folder); engine reads
     ▼
  manifest_template.json       (the spec — PRISM CRUDs via raw JSON code)
     │ engine: load template + load CSVs + chain TRANSFORMS + populate + compile
     ▼
  manifest.json + dashboard.html
```

The runner has no PRISM state and no conversation memory. It re-execs `pull_data.py` (each PULLS entry), then calls `build_dashboard(folder)`, then nothing. If the three surfaces produce a dashboard today, they produce the same dashboard tomorrow with fresher data.

| Question | Answer |
|---|---|
| What does "edit my dashboard" mean? | Pick the right surface: spec edit → hub §C raw JSON CRUD on `manifest_template.json`; data-shape edit → READ → MUTATE → WRITE on `pull_data.py` (and `build.py` if dataset shape changes) per hub §D |
| What does "save the change" mean? | The S3 `put` of the script or template. The next `build_dashboard(folder)` (in-process or cron) runs whatever bytes are at `scripts/<name>.py` and reads whatever JSON is at `manifest_template.json` |
| What does "verify the change worked" mean? | `build_dashboard(folder)` recompiles against current data and surfaces compile errors. The Tool 4 subprocess refresh (hub §B) is the canonical end-of-edit verify in a clean interpreter |
| What does "the dashboard broke" mean? | Either one of the two scripts no longer runs cleanly against today's data, OR the manifest_template.json drifted from the data shape PULLS produces. Diagnose in order: pulls first, then template + transforms together |

**Hand-edited derived files do not survive.** Mutating `manifest.json` or `data/<stem>.csv` or `dashboard.html` directly is a no-op against the next refresh: tomorrow morning the runner re-execs the unmodified scripts and produces the pre-edit state. The only durable edit is to one of the three persisted surfaces.

---

## 2. Pipeline cataloging

A "pipeline" inside `pull_data.py` is one source-to-CSV transformation declared as one `def pull_<name>():` function. Each function corresponds to one entry in the `PULLS` dict, one resulting CSV stem, one `manifest.datasets` key.

| Pipeline shape | Example function body | Output |
|----------------|----------------------|--------|
| `pull_market_data` (eod) | `pull_market_data(coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'], name='rates', mode='eod', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/rates_eod.csv` (+ `data/rates_metadata.json`) |
| `pull_market_data` (intraday) | same with `mode='iday'` | `data/rates_intraday.csv` |
| `pull_haver_data` | `pull_haver_data(codes=['JCXFE@USECON', 'PCUSLFE@USECON'], name='cpi', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/cpi.csv` (+ `data/cpi_metadata.json`) |
| `pull_plottool_data` | `pull_plottool_data(expressions=[...], labels=[...], name='swap_curve', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/swap_curve.csv` |
| `pull_fred_data` | `pull_fred_data(series=['UNRATE', 'PAYEMS'], name='labor', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/labor.csv` |
| alt-data + `save_artifact` | `recs = fdic_client.get(...); save_artifact(recs, name='gs_bank', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/gs_bank.csv` |

**Build the graph.** Before any edit, walk the chain bottom-up for every widget — hub §F's DEEP GLANCE script prints exactly this graph (PULLS keys + TRANSFORMS list + per-CSV columns + per-widget dataset/source references). Run it on inheritance.

```
  widget (in manifest layout)
    └── spec.dataset = "<key>"
          └── manifest.datasets["<key>"]
                └── data/<key>.csv  (pull_market_data appends _eod / _intraday)
                      └── pipeline in pull_data.py = PULLS["<name>"]()
                                                     where <name> ≈ <key> (modulo _eod suffix)
```

If two widgets reference the same `dataset_key`, they share one PULLS entry (the cheapest reuse path, §3). If a widget references a `dataset_key` whose CSV stem doesn't match any pipeline's output, the dashboard is broken.

**Naming convention** (Rule 5 cross-ref). The pull function name follows the bare base (`pull_rates`, not `pull_rates_eod`). `pull_market_data` appends `_eod` / `_intraday` to the CSV stem; `pull_haver_data` / `pull_plottool_data` / `pull_fred_data` / `save_artifact` use the bare name. The PULLS key (`'rates'`) maps to the function (`pull_rates`). The manifest dataset_key (`'rates_eod'`) matches the on-disk CSV stem byte-for-byte. The PULLS key and the dataset_key need NOT match — `'rates'` in PULLS produces `data/rates_eod.csv` mapped as `'rates_eod'` in the manifest.

**Pipeline metadata** (lives in the pull-function body, not the manifest):

| Knob | Effect |
|------|--------|
| `coordinates` / `codes` / `series` / `expressions` | Which columns the pipeline produces |
| `start` | History depth — clipping here is irreversible (`dashboards.md` §10) |
| `name` | The CSV stem (post-suffix for market_data) and therefore the dataset_key |
| `output_path` | Always `f"{SESSION_PATH}/data"` (Rule 5); never per-source subfolders |

When PRISM reads an existing `pull_data.py`, the catalog is recoverable in one pass: each `def pull_<name>()` is one pipeline; its arguments tell you exactly what CSV it produces and which columns the CSV will have. PULLS keys enumerate them. For a dashboard with 4 pipelines and 12 widgets, the full pipeline-graph is ~30 lines of mental model — cheap to build, expensive to skip.

---

## 3. Pipeline reuse decision ladder

When the user asks for a new widget on an existing dashboard, walk the ladder. The right answer is almost always Step 1 or Step 2; Step 3 is for genuinely new sources.

```
  NEW WIDGET ASK
     │
     ▼
  Step 1: Does the widget need columns from a CSV that ALREADY exists in data/?
     │
     ├── YES ─►  REUSE. Reference the existing dataset_key in the manifest.
     │           No pull_data.py change. No build.py change beyond layout.
     │           This is the cheapest path; it's also the right path most
     │           of the time.
     │
     └── NO  ─►  Step 2.
     │
     ▼
  Step 2: Does the widget need a new column from a SOURCE that's already
          wired up in pull_data.py (i.e. an existing PULLS entry)?
     │
     ├── YES ─►  EXTEND the existing pipeline. Surgically edit the matching
     │           pull_<name>() body to add the coordinate / code / expression
     │           to the pull-function call's argument list. The CSV stem
     │           stays the same; the dataset_key stays the same; the column
     │           set grows. Hub §D is the canonical mutation pattern.
     │           build.py needs no change unless a transform depends on the
     │           new column.
     │
     └── NO  ─►  Step 3.
     │
     ▼
  Step 3: Does the widget need a NEW SOURCE not currently in pull_data.py?
     │
     ├── YES ─►  ADD a new pipeline. New pull_<name>() function (or alt-data
     │           sequence ending in save_artifact), new PULLS entry, new
     │           CSV stem, new manifest dataset_key. Hub §D is the canonical
     │           mutation pattern. build.py grows a transform only if the
     │           new dataset feeds a derived dataset (e.g. a join across
     │           the new pull and an existing one).
     │
     └── (If neither (a) nor (b) is acceptable, surface the gap to the user
          instead of inventing data — hub §D's propose-and-confirm.)
```

**Concrete reuse example.** Existing dashboard has the rates pipeline:

```python
def pull_rates():
    pull_market_data(
        coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
        name='rates', mode='eod',
        output_path=f'{SESSION_PATH}/data',
        s3_manager=s3_manager,
    )

PULLS = {'rates': pull_rates}
```

User asks for a 5Y rates chart.

| Ladder step | Decision |
|-------------|----------|
| 1 — column exists today? | NO (`us_5y` column doesn't exist) → step 2 |
| 2 — same source? | YES (rates pipeline IS market data) → EXTEND |

Action: add `'IR_USD_Swap_5Y_Rate'` to `pull_rates()`'s `coordinates` list. PULLS key, CSV stem, dataset_key all stay the same. The new column is `us_5y`. If a transform in `build.py` does column renames, add `'us_5y'` to that rename block too.

**Concrete add-new-pipeline example.** Same dashboard. User asks for a table of GS Bank's quarterly call-report financials.

| Ladder step | Decision |
|-------------|----------|
| 1 — column exists today? | NO (no FDIC data) → step 2 |
| 2 — same source? | NO (FDIC is not market_data) → step 3 |
| 3 — new source? | YES → ADD |

Action: new function `pull_gs_bank()` using `fdic_client.get(...)` + `save_artifact(name='gs_bank', ...)`. New PULLS entry: `'gs_bank': pull_gs_bank`. New CSV `data/gs_bank.csv`. New dataset_key `'gs_bank'`. `build.py` doesn't need a change unless the new dataset feeds a join.

---

## 4. Active-pipeline integrity (5 nevers)

Once a pipeline is in production, other widgets are downstream. The pipeline graph (§2) is implicit but load-bearing — breaking it silently is the canonical "everything looked fine in-session, the next refresh is empty" failure mode.

| Never | Why | Symptom at refresh time |
|-------|-----|--------------------------|
| Remove a `def pull_<name>()` (an active pipeline) without checking downstream | Some widget downstream loses its CSV | `chart_mapping_column_missing` (or the audit fails to find the matching CSV) |
| Rename `name=` inside an existing `pull_<name>()` body | The CSV stem changes (e.g. `'rates'` → `'usd_rates'`); every widget referencing the old dataset_key now points to a missing CSV | Compile fails: `chart_dataset_empty` for every widget bound to the old key |
| Drop a coordinate / code / expression that other widgets read | The CSV exists but a column another widget needs is gone | `chart_mapping_column_missing` |
| Change `output_path` away from `f"{SESSION_PATH}/data"` | Rule 5 violation; CSVs land in per-source subfolders; the engine's `data/` discovery doesn't follow | `FileNotFoundError`-class failure; `build_dashboard()` finds no datasets |
| Edit a transform in `build.py` so it produces a DIFFERENT shape (column rename, drop, dtype shift) without updating the manifest's `mapping.<col>` references | The CSV is fine; the transform is fine; the manifest's chart specs silently bind to wrong / missing columns | Wrong values in chart, no error raised; user-detectable only |

**Audit before re-authoring.** Read the FULL `pull_data.py` and `build.py` (use the DEEP GLANCE in hub §F). For each pipeline:

1. List the columns it produces (argument list + per-pipeline naming convention).
2. List the manifest widgets whose dataset_key matches this pipeline's CSV stem.
3. List, per widget, which columns it reads (mapping `x`, `y`, `color`, `value`, etc.).
4. Confirm the planned edit doesn't drop any column from step 3.

If step 4 fails, the edit is a breaking change, not a delta. Surface to the user, propose a path that preserves the contract, wait for confirmation before re-authoring.

**Cross-script integrity.** A subtle failure mode: `pull_data.py` keeps producing the same CSVs but a `build.py` transform's column rename gets edited inconsistently with the manifest's `mapping.<key>` references. The CSV is fine; the manifest is fine; the rename block silently maps the wrong column to the wrong widget. Catch this by running `build_dashboard(folder)` after EVERY transform edit — the validator's `chart_mapping_column_missing` catches a missing column; for wrong-but-existing columns, the symptom is "wrong numbers in the chart" which only the user can spot.

---

## Pointer index

| Topic | Where |
|---|---|
| The READ → MUTATE → WRITE pattern for `pull_data.py` | hub §D |
| The READ → MUTATE → WRITE pattern for `build.py` transforms | hub §D |
| In-session quick recompile via `build_dashboard(folder)` | hub §E |
| Pickup-time exploration (HIGH-LEVEL GLANCE / DEEP GLANCE) | hub §F |
| Derived dataset patterns (YoY / composition / cross-dataset join / subset) | `recipes.md` §3 |
| Three-surface mental model | this spoke §1 |
| Pipeline cataloging | this spoke §2 |
| Pipeline reuse decision ladder | this spoke §3 |
| Active-pipeline integrity rules (5 nevers) | this spoke §4 |
