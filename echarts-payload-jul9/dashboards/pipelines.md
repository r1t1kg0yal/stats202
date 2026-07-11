# Data pipelines + session folder health

Spoke fetched on demand from the dashboards hub. Covers the three-surface model, pipeline cataloging, the reuse decision ladder, active-pipeline integrity rules, end-to-end re-authoring of `pull_data.py`, and the post-edit session-folder health check.

This spoke is the SSOT for "how PRISM thinks about dashboard data flow" -- fetch when ADDING / EDITING an existing dashboard's data side, before authoring any change. The other dashboards spokes (`charts.md`, `widgets.md`, `widget_tool.md`, `filters.md`) are about per-primitive widget specs; `template_crud.md` is the SSOT for raw JSON CRUD on `manifest_template.json`; `recipes.md` carries long-form worked recipes including derived-dataset patterns in `build.py`.

---

## 1. The three persisted surfaces

A persistent dashboard's true artifact is three files: `scripts/pull_data.py` (the data pipelines), `manifest_template.json` (the spec), and `scripts/build.py` (the recompile recipe). Everything else in the dashboard folder is byproduct that the daily / hourly refresh runner regenerates from those three:

```
  scripts/pull_data.py         (raw data pulls)
     │ runner execs daily / hourly
     ▼
  data/<stem>.csv              (one CSV per pipeline)
     │ runner execs build.py
     ▼
  manifest_template.json       (the spec -- PRISM CRUDs via raw JSON code)
     │ build.py loads + populate_template + compile_dashboard
     ▼
  manifest.json + dashboard.html
```

The runner has no PRISM state and no conversation memory. It re-execs `pull_data.py`, then `build.py`, then nothing. If the three surfaces produce a dashboard today, they produce the same dashboard tomorrow with fresher data. If a refresh fails, the failure is in one of the two scripts (the spec is JSON; it can't fail at exec time, only at compile time inside `build.py`).

This spoke is about the data side -- `pull_data.py` and the CSVs it produces. For the spec side (`manifest_template.json`) see `template_crud.md`. For cross-dataset derivation in `build.py` see `recipes.md` § 7.

| Question | Answer |
|---|---|
| What does "edit my dashboard" mean? | Pick the right surface: spec edit → `template_crud.md` raw JSON CRUD on `manifest_template.json`; data-shape edit → READ → MUTATE → WRITE on `pull_data.py` (and `build.py` if dataset shape changes) per `recipes.md` § 6 |
| What does "save the change" mean? | The S3 `put` of the script or template. The next refresh runs whatever bytes are at `scripts/<name>.py` and reads whatever JSON is at `manifest_template.json` |
| What does "verify the change worked" mean? | The in-session quick recompile (`dashboards_hub.md` § 6.6 / `template_crud.md` § 9) runs `build.py` against current data and surfaces compile errors. The build flow's Tool 4 subprocess refresh (`dashboards_hub.md` § 6.1) is the canonical end-of-edit verify |
| What does "the dashboard broke" mean? | Either one of the two scripts no longer runs cleanly against today's data, OR the manifest_template.json drifted from the data shape `pull_data.py` produces. Diagnose in order: pull first, then template + build together |

**Hand-edited derived files do not survive.** Mutating `manifest.json` or `data/<stem>.csv` or `dashboard.html` directly is a no-op against the next refresh: tomorrow morning the runner re-execs the unmodified scripts and produces the pre-edit state. The only durable edit is to one of the three persisted surfaces: `pull_data.py`, `manifest_template.json` (raw JSON CRUD per `template_crud.md`), or `build.py`.

**Rule 7 (atomicity, hub § 0) restated in three-surface terms.** Tool 1 persists `pull_data.py` and execs it; Tool 2 persists both `manifest_template.json` and `build.py` and execs the latter; Tool 3 registers the dashboard with the cron runner; Tool 4 spawns the canonical subprocess refresh. All four together = the dashboard exists. Any subset = it doesn't.

---

## 2. Pipeline cataloging

A "pipeline" inside `pull_data.py` is one source-to-CSV transformation. The cleanest unit is one pull-function call (or one alt-data sequence ending in `save_artifact`), one `name=` argument, one resulting CSV stem.

| Pipeline shape | Example | Output |
|----------------|---------|--------|
| `pull_plottool_data` (eod) | `pull_plottool_data(expressions=['sofrswp2y', 'sofrswp10y'], labels=['us_2y', 'us_10y'], name='rates', output_path=...)` | `data/rates.csv` (+ `data/rates_metadata.json`) |
| `pull_plottool_data` (intraday) | `pull_plottool_data(expressions=['chunktick(<COORDINATE>)'], labels=['value'], name='rates_intraday', output_path=...)` | `data/rates_intraday.csv` |
| `pull_haver_data` | `pull_haver_data(codes=['<CODE>@<DB>', '<CODE_2>@<DB>'], name='cpi', output_path=...)` | `data/cpi.csv` (+ `data/cpi_metadata.json`) |
| `pull_plottool_data` | `pull_plottool_data(expressions=[...], labels=[...], name='swap_curve', output_path=...)` | `data/swap_curve.csv` |
| `pull_fred_data` | `pull_fred_data(series=['UNRATE', 'PAYEMS'], name='labor', output_path=...)` | `data/labor.csv` |
| alt-data + `save_artifact` | `recs = fdic_client.get(...); save_artifact(recs, name='gs_bank', output_path=...)` | `data/gs_bank.csv` |

**Build the graph.** Before any edit, walk the chain bottom-up for every widget:

```
  widget (in manifest layout)
    └── spec.dataset = "<key>"
          └── manifest.datasets["<key>"]
                └── data/<key>.csv  (pull_plottool_data / pull_haver_data /
                                     pull_fred_data / save_artifact: stem == name)
                      └── pipeline in pull_data.py (the pull-function call that wrote it)
```

If two widgets reference the same `dataset_key`, they share one pipeline (the cheapest reuse path, §3). If a widget references a `dataset_key` whose CSV stem doesn't match any pipeline's output, the dashboard is broken and an `_audit_dashboard_layout` violation is imminent.

**Naming convention** (Rule 5 cross-ref). Across `pull_plottool_data` / `pull_haver_data` / `pull_fred_data` / `save_artifact`, `name=` is the on-disk CSV stem byte-for-byte. The manifest dataset_key MUST match that stem.

**Pipeline metadata** (lives in the pull-function or `save_artifact` arguments, not the manifest):

| Knob | Effect |
|------|--------|
| `codes` / `series` / `expressions` | Which columns the pipeline produces |
| `start` | History depth -- clipping here is irreversible (`dashboards_hub.md` §11) |
| `name` | The CSV stem byte-for-byte and therefore the dataset_key |
| `output_path` | Always `f"{SESSION_PATH}/data"` (Rule 5); never per-source subfolders |

When PRISM reads an existing `pull_data.py`, the catalog is recoverable in one pass: each top-level pull / alt-data block is one pipeline; its arguments tell you exactly what CSV it produces and which columns the CSV will have. For a dashboard with 4 pipelines and 12 widgets, the full pipeline-graph is ~30 lines of mental model -- cheap to build, expensive to skip.

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
          wired up in pull_data.py?
     │
     ├── YES ─►  EXTEND the existing pipeline. Add the coordinate / code /
     │           expression to the pull-function call's argument list. The
     │           CSV stem stays the same; the dataset_key stays the same;
     │           the column set grows. build.py needs no change unless the
     │           new column gets a non-default rename in the post-pull
     │           cleanup block. Re-author pull_data.py end-to-end (§5);
     │           the script is the SSOT.
     │
     └── NO  ─►  Step 3.
     │
     ▼
  Step 3: Does the widget need a NEW SOURCE not currently in pull_data.py?
     │
     ├── YES ─►  ADD a new pipeline. New pull-function call (or alt-data
     │           sequence), new `name=`, new resulting CSV stem, new
     │           manifest dataset_key. build.py re-authors to load the new
     │           CSV in addition to the existing ones; populate_template
     │           gets a new entry in its dict argument. Audit the
     │           refresh-runner namespace before adding (§6.5 of
     │           dashboards_hub.md) -- alt-data clients and `save_artifact`
     │           are NOT injected today.
     │
     └── (If neither (a) nor (b) is acceptable, surface the gap to the user
          instead of inventing data -- `recipes.md` §4 propose-and-confirm.)
```

**Concrete reuse example.** Existing dashboard has the rates pipeline:

```python
pull_plottool_data(
    expressions=['sofrswp2y', 'sofrswp10y'],
    labels=['us_2y', 'us_10y'],
    name='rates',
    output_path=f'{SESSION_PATH}/data',
)
```

User asks for a 5Y rates chart.

| Ladder step | Decision |
|-------------|----------|
| 1 -- column exists today? | NO (`us_5y` column doesn't exist) → step 2 |
| 2 -- same source? | YES (rates pipeline IS TSDB via PlotTool) → EXTEND |

Action: add `sofrswp5y` and the matching `us_5y` label to the `expressions` / `labels` lists. `name=`, CSV stem, and dataset_key all stay the same; the new plain-English column flows straight into the existing derive.

**Concrete add-new-pipeline example.** Same dashboard. User asks for a table of GS Bank's quarterly call-report financials.

| Ladder step | Decision |
|-------------|----------|
| 1 -- column exists today? | NO (no FDIC data) → step 2 |
| 2 -- same source? | NO (FDIC is not TSDB) → step 3 |
| 3 -- new source? | YES → ADD |

Action: new pipeline using `fdic_client.get(...)` + `save_artifact(name='gs_bank', ...)`. New CSV `data/gs_bank.csv`. New dataset_key `gs_bank`. `build.py` populate_template grows by one entry. Set the registry entry's `refresh_frequency: "manual"` if the runner namespace doesn't yet inject `fdic_client` / `save_artifact` (`dashboards_hub.md` §6.5).

---

## 4. Active-pipeline integrity (5 nevers)

Once a pipeline is in production, other widgets are downstream. The pipeline graph (§2) is implicit but load-bearing -- breaking it silently is the canonical "everything looked fine in-session, the next refresh is empty" failure mode.

| Never | Why | Symptom at refresh time |
|-------|-----|--------------------------|
| Remove a pull-function call (an active pipeline) | Some widget downstream loses its CSV | `chart_mapping_column_missing` (or `_audit_dashboard_layout` violation if the dataset_key was also removed) |
| Rename `name=` | The CSV stem changes (e.g. `rates` → `usd_rates`); every widget referencing the old dataset_key now points to a missing CSV | `_audit_dashboard_layout` raises "manifest-orphan in data/" + missing dataset stem |
| Drop a coordinate / code / expression that other widgets read | The CSV exists but a column another widget needs is gone | `chart_mapping_column_missing` |
| Change `output_path` away from `f"{SESSION_PATH}/data"` | Rule 5 violation; CSVs land in per-source subfolders; `build.py`'s read path doesn't follow | `FileNotFoundError` on every refresh |
| Change post-pull data shape (column rename, MultiIndex re-introduction, dtype shift) without updating `build.py`'s read block | The CSV's columns are the contract between the two scripts; `build.py`'s `df.columns = [...]` rename block is positional -- silently mis-rename and the wrong column ends up in the chart | Wrong values in chart, no error raised; user-detectable only |

**Audit before re-authoring.** Read the FULL `pull_data.py` and `build.py`. For each pipeline:

1. List the columns it produces (argument list + per-pipeline naming convention).
2. List the manifest widgets whose dataset_key matches this pipeline's CSV stem.
3. List, per widget, which columns it reads (mapping `x`, `y`, `color`, `value`, etc.).
4. Confirm the planned edit doesn't drop any column from step 3.

If step 4 fails, the edit is a breaking change, not a delta. Surface to the user, propose a path that preserves the contract, wait for confirmation before re-authoring.

**Cross-script integrity.** A subtle failure mode: `pull_data.py` keeps producing the same CSVs but `build.py`'s post-pull cleanup block (the `df.columns = [...]` rename) gets edited inconsistently with the manifest's `mapping.<key>` references. The CSV is fine; the manifest is fine; the rename block silently maps the wrong column to the wrong widget. Catch this at health-check step 7 (§6).

**Column-contract rule (the single most common dashboard defect).** Every column referenced by `build.py`, a manifest mapping, or a widget source must exist in the persisted `data/<stem>.csv`, not only in the ephemeral DataFrame used while authoring. Otherwise the next refresh produces one of three signatures: a `KeyError` in `build.py`, a blank/`None` chart or table cell, or a missing per-record field that existed only in memory. Filter snapshot datasets to the intended as-of date before persisting, and persist every field the renderer needs explicitly.

---

## 5. Re-authoring `pull_data.py` end-to-end

When `pull_data.py` needs to change (Steps 2 or 3 of the reuse ladder, §3), re-author the FULL script. Inline deltas (an `s3_manager.put` of just the new pipeline appended after the existing file) leave the script in a fragile half-state -- the runner re-execs the whole file, so a syntactically broken middle line breaks every pipeline below it.

```
 Pattern (from §6.1 of dashboards_hub.md, restated in nucleus terms):

 1. READ existing pull_data.py from S3
    src_old = s3_manager.get(f'{DASHBOARD_PATH}/scripts/pull_data.py').decode('utf-8')

 2. CATALOG existing pipelines (§2)
    For each pipeline: source, name, columns, output_path
    For each manifest widget: which pipeline backs it (the graph)

 3. PLAN the edit (Steps 1 / 2 / 3 of the reuse ladder, §3)
    What columns does the new widget need?
    Reuse / extend / add -- pick one path

 4. RE-AUTHOR pull_data.py as a fresh string
    Open with the explicit SESSION_PATH = "<dashboard-path-literal>"
    line (dashboards_hub.md Rule 5) -- neither the in-session sandbox nor
    the refresh runner injects it. Then preserve every existing
    pipeline; modify the one (or add the new one) the plan calls for.
    Keep the script readable: imports at top, pipelines in dependency
    order, print statements between pipelines so refresh-runner logs
    are readable.

 5. BUMP THE SCRIPT VERSION (dashboards_hub.md §2.6)
    SCRIPT_VERSION = _next_script_version(DASHBOARD_PATH)
    Pin once at the start of Tool 1; reuse unchanged through Tool 2.
    Coupled bump: both pull_data and build version together even if
    only pull_data changed in this edit.

 6. PERSIST + EXEC from S3 (Tool 1, §6.1 of dashboards_hub.md)
    _persist_versioned_script(DASHBOARD_PATH, 'pull_data',
                             new_pull_data_py, SCRIPT_VERSION)
    -- writes both scripts/pull_data.py (live) AND
       scripts/versions/pull_data_v{SCRIPT_VERSION}.py (snapshot)
    Then s3_manager.get + exec(compile(...)) on the live path.
    Verify by reading each new / changed CSV back; print shape / head / dtypes.

 7. RE-AUTHOR build.py -- ALWAYS, even if dataset shape didn't change
    Coupled bump (§2.6) means every Tools 1+2 cycle writes both
    scripts/versions/pull_data_v{N}.py AND scripts/versions/build_v{N}.py
    -- the build_v{N} snapshot is required even when build.py's bytes
    are byte-identical to v{N-1} (no functional delta).

    Reuse path:  re-emit build.py with the same bytes as before; the
                 bump is bookkeeping, not a logic change. The
                 _persist_versioned_script call is what makes the
                 coupling valid.
    Extend path: column-rename block needs the new column added (or
                 stays as-is if positional rename caught it).
    Add path:    build.py loads a new CSV + populate_template grows by
                 one entry.

    Either way: _persist_versioned_script(DASHBOARD_PATH, 'build',
                build_py, SCRIPT_VERSION) -- writes both scripts/build.py
                (live) AND scripts/versions/build_v{SCRIPT_VERSION}.py.
                Re-exec end-to-end (Tool 2, §6.1).
```

The `re-author end-to-end` rule is the same one that governs `manifest_template.json` (`template_crud.md` raw JSON CRUD; never put-overwrite a fresh dict). All three surfaces have the same fragility shape; all three follow READ → PLAN → WRITE. The § 2.6 versioning layer adds a third invariant on top of READ → PLAN → WRITE for the two scripts: SNAPSHOT every PLAN → WRITE event, and never bypass `_persist_versioned_script()` once the dashboard has any v1 snapshot on disk.

---

## 6. Session folder health check

After any edit to `pull_data.py` or `build.py` (or both), run the health check before declaring done. The check exists because the in-session build doesn't catch every failure mode the daily refresh will hit; specifically, it doesn't independently verify that the manifest's dataset references match the CSVs the pipelines produced or that no pre-existing pipeline was silently broken.

| Step | What it verifies | How |
|------|------------------|-----|
| 1. Parse | Both scripts are syntactically valid Python | The `s3_manager.get` → `exec(compile(...))` step from §6.1 Tools 1+2 raises `SyntaxError` on parse failure |
| 2. Pull data | `pull_data.py` runs end-to-end against today's data | Tool 1 exec finishes without exception |
| 3. CSVs land | Every pipeline wrote a CSV at `data/<stem>.csv` | Tool 1 verify step (`pd.read_csv(...).head()`) for each new / changed pipeline |
| 4. Build | `build.py` runs end-to-end, manifest + html on S3 | Tool 2 exec ends with `[build.py] success` |
| 5. Folder audit | `_audit_dashboard_layout(folder, manifest)` passes (covers §2.2 layout + §2.6 versioning chain integrity) | `dashboards_hub.md` §2.5 invocation |
| 6. Manifest reference integrity | Every `manifest.datasets[key]` resolves to `data/<key>.csv`; every widget's `mapping.<col>` references a column that exists | The compiler's `chart_data_diagnostics` raises `chart_mapping_column_missing` regardless of `strict` (`dashboards_hub.md` §1 ALWAYS_BLOCKING_ERROR_CODES) |
| 7. Pipeline integrity | No active pipeline silently broken -- every CSV that EXISTED before the edit still exists with at least the columns it had before | Manual: list `data/` before vs after; diff column sets per CSV. Engine companion `_audit_pipeline_integrity()` flagged in `dev/notes.md` |
| 8. Version chain integrity | `scripts/versions/pull_data_v{N}.py` and `scripts/versions/build_v{N}.py` were written for the new `SCRIPT_VERSION = N`; live `scripts/<name>.py` is byte-identical to its `_v{N}.py` snapshot; `manifest.metadata.script_version == N` | Folded into step 5 (`_audit_dashboard_layout` enforces all four §2.6 invariants); also surface explicitly so a failure here flags the §6.1 Tools 1+2 wiring rather than the manifest content |

**Health-check checklist** (run at the bottom of the in-session edit script, after Tool 2's exec):

```python
import io, json, re

# 1-4 are folded into the §6.1 Tool 1 + Tool 2 exec sequence.

# 5: explicit folder audit (covers both §2.5 layout AND §2.6 versioning)
m = json.loads(s3_manager.get(f'{DASHBOARD_PATH}/manifest.json').decode('utf-8'))
_audit_dashboard_layout(DASHBOARD_PATH, m)

# 6: explicit manifest reference check
csvs = {
   entry['Key'].rsplit('/', 1)[-1].rsplit('.', 1)[0]
   for entry in s3_manager.list(f'{DASHBOARD_PATH}/data')
   if entry['Key'].endswith('.csv')
}
for key in m.get('datasets', {}).keys():
   assert key in csvs, f"manifest dataset_key '{key}' has no matching CSV stem"

# 7: pipeline integrity (column-set diff vs pre-edit state)
# Print per-CSV columns; compare against the pre-edit catalog you built in step 2 of §5.
for key in m['datasets']:
   df = pd.read_csv(io.BytesIO(
      s3_manager.get(f'{DASHBOARD_PATH}/data/{key}.csv')))
   print(f"  {key}: {list(df.columns)}")

# 8: explicit version chain print (so failures at the §2.6 layer
# are obvious in PRISM's session log, even though step 5 already
# raises on them).
versioned = {'pull_data': set(), 'build': set()}
for entry in s3_manager.list(f'{DASHBOARD_PATH}/scripts/versions/'):
   name = entry['Key'].rsplit('/', 1)[-1]
   mm = re.match(r'^(pull_data|build)_v(\d+)\.py$', name)
   if mm:
      versioned[mm.group(1)].add(int(mm.group(2)))
print(f"  pull_data versions: {sorted(versioned['pull_data'])}")
print(f"  build versions:    {sorted(versioned['build'])}")
print(f"  manifest.metadata.script_version: "
   f"{m.get('metadata', {}).get('script_version')}")
assert versioned['pull_data'] == versioned['build'], (
   f"§2.6 coupling violation: pull_data versions {sorted(versioned['pull_data'])} "
   f"!= build versions {sorted(versioned['build'])}"
)
```

If any step fails, the dashboard is not in a healthy state. Fix the script (re-author end-to-end per §5), re-run the health check from step 1.

The check is most discriminating on EDITS to existing dashboards (where active pipelines exist and could be silently broken). On fresh builds, steps 1-7 fire -- there are no pre-existing pipelines to protect, so step 7 collapses to "every column is new by definition" and step 8 collapses to "v1 + v1 + script_version=1".
