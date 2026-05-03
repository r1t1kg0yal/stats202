# Data pipelines + session folder health

Spoke fetched on demand from the dashboards hub. Covers the 2-script nucleus framing, pipeline cataloging, the reuse decision ladder, active-pipeline integrity rules, end-to-end re-authoring of `pull_data.py`, and the post-edit session-folder health check.

This spoke is the SSOT for "how PRISM thinks about dashboard scripts and data flow" — fetch when ADDING / EDITING an existing dashboard, before authoring any change. The other dashboards spokes (`charts.md`, `widgets.md`, `widget_tool.md`, `filters.md`, `recipes.md`) are about manifest authoring; this one is about scripts authoring.

---

## 1. The 2-script nucleus

A persistent dashboard's true artifact is two files: `scripts/pull_data.py` (the data pipelines) and `scripts/build.py` (the manifest assembler). Everything else in the dashboard folder is byproduct that the daily / hourly refresh runner regenerates from those two scripts:

```
  scripts/pull_data.py        (the data pipelines)
     │ runner execs daily / hourly
     ▼
  data/<stem>.csv              (one CSV per pipeline)
     │ runner execs build.py
     ▼
  manifest_template.json       (post-data-strip; build.py reads)
     │ populate_template + compile_dashboard
     ▼
  manifest.json + dashboard.html
```

The runner has no PRISM state and no conversation memory. It re-execs `pull_data.py`, then `build.py`, then nothing. If the two scripts produce a dashboard today, they produce the same dashboard tomorrow with fresher data. If a refresh fails, the failure is in one of the two scripts — there is nowhere else for it to live.

| Question | Answer |
|---|---|
| What does "edit my dashboard" mean? | Read the existing `scripts/pull_data.py` and `scripts/build.py`, plan the edit against their current shape, re-author whichever script(s) need to change end-to-end (§5), persist, exec from S3 |
| What does "save the change" mean? | The S3 `put` of the script. The next refresh runs whatever bytes are at `scripts/<name>.py` |
| What does "verify the change worked" mean? | The build flow IS the verify (§6.1 of `dashboards.md`). After Tools 1+2+3 land cleanly, the persisted scripts are proven against today's data; the post-edit health check (§6 here) catches the few failure modes the build flow doesn't |
| What does "the dashboard broke" mean? | One of the two scripts no longer runs cleanly against today's data. Diagnose in that order — pull first, build second |

**Hand-edited derived files do not survive.** Mutating `manifest.json` or `data/<stem>.csv` or `dashboard.html` directly is a no-op against the next refresh: tomorrow morning the runner re-execs the unmodified scripts and produces the pre-edit state. The only durable edit is to the scripts (and to `manifest_template.json` when the edit is a pure layout / widget / filter change — see `recipes.md` §3 READ → MERGE → WRITE).

**Rule 7 (atomicity, hub §0) restated in nucleus terms.** Tool 1 persists `pull_data.py` and execs it; Tool 2 persists `build.py` and execs it; Tool 3 registers the dashboard with the cron runner. All three together = the dashboard exists. Any subset = it doesn't.

---

## 2. Pipeline cataloging

A "pipeline" inside `pull_data.py` is one source-to-CSV transformation. The cleanest unit is one pull-function call (or one alt-data sequence ending in `save_artifact`), one `name=` argument, one resulting CSV stem.

| Pipeline shape | Example | Output |
|----------------|---------|--------|
| `pull_market_data` (eod) | `pull_market_data(coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'], name='rates', mode='eod', output_path=...)` | `data/rates_eod.csv` (+ `data/rates_metadata.json`) |
| `pull_market_data` (intraday) | same with `mode='iday'` | `data/rates_intraday.csv` |
| `pull_haver_data` | `pull_haver_data(codes=['JCXFE@USECON', 'PCUSLFE@USECON'], name='cpi', output_path=...)` | `data/cpi.csv` (+ `data/cpi_metadata.json`) |
| `pull_plottool_data` | `pull_plottool_data(expressions=[...], labels=[...], name='swap_curve', output_path=...)` | `data/swap_curve.csv` |
| `pull_fred_data` | `pull_fred_data(series=['UNRATE', 'PAYEMS'], name='labor', output_path=...)` | `data/labor.csv` |
| alt-data + `save_artifact` | `recs = fdic_client.get(...); save_artifact(recs, name='gs_bank', output_path=...)` | `data/gs_bank.csv` |

**Build the graph.** Before any edit, walk the chain bottom-up for every widget:

```
  widget (in manifest layout)
    └── spec.dataset = "<key>"
          └── manifest.datasets["<key>"]
                └── data/<key>.csv  (pull_market_data appends _eod / _intraday)
                      └── pipeline in pull_data.py (the pull-function call that wrote it)
```

If two widgets reference the same `dataset_key`, they share one pipeline (the cheapest reuse path, §3). If a widget references a `dataset_key` whose CSV stem doesn't match any pipeline's output, the dashboard is broken and an `_audit_dashboard_layout` violation is imminent.

**Naming convention** (Rule 5 cross-ref). `name=` is the bare base. `pull_market_data` appends `_eod` / `_intraday` to the CSV stem; `pull_haver_data` / `pull_plottool_data` / `pull_fred_data` / `save_artifact` use the bare name. The manifest dataset_key MUST match the on-disk CSV stem byte-for-byte.

**Pipeline metadata** (lives in the pull-function or `save_artifact` arguments, not the manifest):

| Knob | Effect |
|------|--------|
| `coordinates` / `codes` / `series` / `expressions` | Which columns the pipeline produces |
| `start` | History depth — clipping here is irreversible (`dashboards.md` §11) |
| `name` | The CSV stem (post-suffix for market_data) and therefore the dataset_key |
| `output_path` | Always `f"{SESSION_PATH}/data"` (Rule 5); never per-source subfolders |

When PRISM reads an existing `pull_data.py`, the catalog is recoverable in one pass: each top-level pull / alt-data block is one pipeline; its arguments tell you exactly what CSV it produces and which columns the CSV will have. For a dashboard with 4 pipelines and 12 widgets, the full pipeline-graph is ~30 lines of mental model — cheap to build, expensive to skip.

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
     │           dashboards.md) — alt-data clients and `save_artifact`
     │           are NOT injected today.
     │
     └── (If neither (a) nor (b) is acceptable, surface the gap to the user
          instead of inventing data — `recipes.md` §4 propose-and-confirm.)
```

**Concrete reuse example.** Existing dashboard has the rates pipeline:

```python
pull_market_data(
    coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
    name='rates', mode='eod',
    output_path=f'{SESSION_PATH}/data',
)
```

User asks for a 5Y rates chart.

| Ladder step | Decision |
|-------------|----------|
| 1 — column exists today? | NO (`us_5y` column doesn't exist) → step 2 |
| 2 — same source? | YES (rates pipeline IS market data) → EXTEND |

Action: add `'IR_USD_Swap_5Y_Rate'` to `coordinates`. `name=`, CSV stem, dataset_key all stay the same. `build.py`'s post-pull rename block needs the new column added (`df.columns = ['us_2y', 'us_10y', 'us_5y']`).

**Concrete add-new-pipeline example.** Same dashboard. User asks for a table of GS Bank's quarterly call-report financials.

| Ladder step | Decision |
|-------------|----------|
| 1 — column exists today? | NO (no FDIC data) → step 2 |
| 2 — same source? | NO (FDIC is not market_data) → step 3 |
| 3 — new source? | YES → ADD |

Action: new pipeline using `fdic_client.get(...)` + `save_artifact(name='gs_bank', ...)`. New CSV `data/gs_bank.csv`. New dataset_key `'gs_bank'`. `build.py` populate_template grows by one entry. Set the registry entry's `refresh_frequency: "manual"` if the runner namespace doesn't yet inject `fdic_client` / `save_artifact` (`dashboards.md` §6.5).

---

## 4. Active-pipeline integrity (5 nevers)

Once a pipeline is in production, other widgets are downstream. The pipeline graph (§2) is implicit but load-bearing — breaking it silently is the canonical "everything looked fine in-session, the next refresh is empty" failure mode.

| Never | Why | Symptom at refresh time |
|-------|-----|--------------------------|
| Remove a pull-function call (an active pipeline) | Some widget downstream loses its CSV | `chart_mapping_column_missing` (or `_audit_dashboard_layout` violation if the dataset_key was also removed) |
| Rename `name=` | The CSV stem changes (e.g. `'rates'` → `'usd_rates'`); every widget referencing the old dataset_key now points to a missing CSV | `_audit_dashboard_layout` raises "manifest-orphan in data/" + missing dataset stem |
| Drop a coordinate / code / expression that other widgets read | The CSV exists but a column another widget needs is gone | `chart_mapping_column_missing` |
| Change `output_path` away from `f"{SESSION_PATH}/data"` | Rule 5 violation; CSVs land in per-source subfolders; `build.py`'s read path doesn't follow | `FileNotFoundError` on every refresh |
| Change post-pull data shape (column rename, MultiIndex re-introduction, dtype shift) without updating `build.py`'s read block | The CSV's columns are the contract between the two scripts; `build.py`'s `df.columns = [...]` rename block is positional — silently mis-rename and the wrong column ends up in the chart | Wrong values in chart, no error raised; user-detectable only |

**Audit before re-authoring.** Read the FULL `pull_data.py` and `build.py`. For each pipeline:

1. List the columns it produces (argument list + per-pipeline naming convention).
2. List the manifest widgets whose dataset_key matches this pipeline's CSV stem.
3. List, per widget, which columns it reads (mapping `x`, `y`, `color`, `value`, etc.).
4. Confirm the planned edit doesn't drop any column from step 3.

If step 4 fails, the edit is a breaking change, not a delta. Surface to the user, propose a path that preserves the contract, wait for confirmation before re-authoring.

**Cross-script integrity.** A subtle failure mode: `pull_data.py` keeps producing the same CSVs but `build.py`'s post-pull cleanup block (the `df.columns = [...]` rename) gets edited inconsistently with the manifest's `mapping.<key>` references. The CSV is fine; the manifest is fine; the rename block silently maps the wrong column to the wrong widget. Catch this at health-check step 7 (§6).

---

## 5. Re-authoring `pull_data.py` end-to-end

When `pull_data.py` needs to change (Steps 2 or 3 of the reuse ladder, §3), re-author the FULL script. Inline deltas (an `s3_manager.put` of just the new pipeline appended after the existing file) leave the script in a fragile half-state — the runner re-execs the whole file, so a syntactically broken middle line breaks every pipeline below it.

```
  Pattern (from §6.1 of dashboards.md, restated in nucleus terms):

  1. READ existing pull_data.py from S3
     src_old = s3_manager.get(f'{DASHBOARD_PATH}/scripts/pull_data.py').decode('utf-8')

  2. CATALOG existing pipelines (§2)
     For each pipeline: source, name, columns, output_path
     For each manifest widget: which pipeline backs it (the graph)

  3. PLAN the edit (Steps 1 / 2 / 3 of the reuse ladder, §3)
     What columns does the new widget need?
     Reuse / extend / add — pick one path

  4. RE-AUTHOR pull_data.py as a fresh string
     Preserve every existing pipeline; modify the one (or add the new one)
     the plan calls for. Keep the script readable: imports at top,
     pipelines in dependency order, print statements between pipelines so
     refresh-runner logs are readable.

  5. PERSIST + EXEC from S3 (Tool 1, §6.1 of dashboards.md)
     s3_manager.put + s3_manager.get + exec(compile(...))
     Verify by reading each new / changed CSV back; print shape / head / dtypes.

  6. RE-AUTHOR build.py only if dataset shape changed
     Reuse path: build.py unchanged.
     Extend path: build.py column-rename block needs the new column added
                  (or stays as-is if positional rename caught it).
     Add path:    build.py loads a new CSV + populate_template grows by
                  one entry. Re-author end-to-end (Tool 2, §6.1).
```

The `re-author end-to-end` rule is the same one that governs `manifest_template.json` (`recipes.md` §3 READ → MERGE → WRITE; never put-overwrite a fresh dict). Both surfaces have the same fragility shape; both follow READ → PLAN → WRITE.

---

## 6. Session folder health check

After any edit to `pull_data.py` or `build.py` (or both), run the health check before declaring done. The check exists because the in-session build doesn't catch every failure mode the daily refresh will hit; specifically, it doesn't independently verify that the manifest's dataset references match the CSVs the pipelines produced or that no pre-existing pipeline was silently broken.

| Step | What it verifies | How |
|------|-----------------|-----|
| 1. Parse | Both scripts are syntactically valid Python | The `s3_manager.get` → `exec(compile(...))` step from §6.1 Tools 1+2 raises `SyntaxError` on parse failure |
| 2. Pull data | `pull_data.py` runs end-to-end against today's data | Tool 1 exec finishes without exception |
| 3. CSVs land | Every pipeline wrote a CSV at `data/<stem>.csv` | Tool 1 verify step (`pd.read_csv(...).head()`) for each new / changed pipeline |
| 4. Build | `build.py` runs end-to-end, manifest + html on S3 | Tool 2 exec ends with `[build.py] success` |
| 5. Folder audit | `_audit_dashboard_layout(folder, manifest)` passes | `dashboards.md` §2.5 invocation |
| 6. Manifest reference integrity | Every `manifest.datasets[key]` resolves to `data/<key>.csv`; every widget's `mapping.<col>` references a column that exists | The compiler's `chart_data_diagnostics` raises `chart_mapping_column_missing` regardless of `strict` (`dashboards.md` §1 ALWAYS_BLOCKING_ERROR_CODES) |
| 7. Pipeline integrity | No active pipeline silently broken — every CSV that EXISTED before the edit still exists with at least the columns it had before | Manual: list `data/` before vs after; diff column sets per CSV. Engine companion `_audit_pipeline_integrity()` flagged in `dev/notes.md` |

**Health-check checklist** (run at the bottom of the in-session edit script, after Tool 2's exec):

```python
import io, json

# 1-4 are folded into the §6.1 Tool 1 + Tool 2 exec sequence.

# 5: explicit folder audit
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
```

If any step fails, the dashboard is not in a healthy state. Fix the script (re-author end-to-end per §5), re-run the health check from step 1.

The check is most discriminating on EDITS to existing dashboards (where active pipelines exist and could be silently broken). On fresh builds, steps 1-6 are all that fire — there are no pre-existing pipelines to protect, so step 7 collapses to "every column is new by definition".
