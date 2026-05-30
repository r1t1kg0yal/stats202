# Recipes + data archetypes

Spoke fetched on demand from the dashboards hub. Worked patterns showing how the primitives compose, plus the canonical data-shape → chart-type lookup. Same chart-type names + mapping keys as `charts.md`.

All chart widgets in these recipes use `w: 6` (or smaller) — chart widgets are never full-width.

---

## 1. Common patterns

### 1.1 Long-form `multi_line` with color

```python
datasets["rates_long"] = df.melt(id_vars=['date'], var_name='series', value_name='yield')
```

```json
[{"widget": "chart", "id": "curve_lvl", "w": 6, "h_px": 380, "title": "UST curve — level",
   "spec": {"chart_type": "multi_line", "dataset": "rates_long",
             "mapping": {"x": "date", "y": "yield", "color": "series",
                         "y_title": "Yield (%)"}}},
 {"widget": "chart", "id": "curve_chg", "w": 6, "h_px": 380, "title": "UST curve — 1d change",
   "spec": {"chart_type": "multi_line", "dataset": "rates_long_diff",
             "mapping": {"x": "date", "y": "diff", "color": "series",
                         "y_title": "Δ (bp)"}}}]
```

### 1.2 Actuals vs estimates via `strokeDash`

```json
[{"widget": "chart", "id": "capex", "w": 6, "h_px": 380,
   "title": "Big Tech capex", "subtitle": "solid = actual, dashed = estimate",
   "spec": {"chart_type": "multi_line", "dataset": "capex",
             "mapping": {"x": "date", "y": "capex", "color": "company",
                         "strokeDash": "type", "y_title": "Capex ($B)"}}},
 {"widget": "chart", "id": "capex_yoy", "w": 6, "h_px": 380,
   "title": "Capex y/y growth",
   "spec": {"chart_type": "multi_line", "dataset": "capex_yoy",
             "mapping": {"x": "date", "y": "yoy", "color": "company",
                         "y_title": "y/y (%)"}}}]
```

### 1.3 Dual axis

```json
[{"widget": "chart", "id": "spx_ism", "w": 6, "h_px": 380, "title": "Equities vs ISM",
   "spec": {"chart_type": "multi_line", "dataset": "macro",
             "mapping": {"x": "date", "y": "value", "color": "series",
                         "dual_axis_series": ["ISM Manufacturing"],
                         "y_title": "S&P 500", "y_title_right": "ISM Index",
                         "invert_right_axis": false}}},
 {"widget": "stat_grid", "id": "spx_ism_stats", "w": 6,
   "items": [{"label": "SPX YTD", "source": "macro.last.spx_ytd"},
             {"label": "ISM latest", "source": "macro.last.ism"},
             {"label": "Corr (3m)", "source": "macro.corr.spx_ism_3m"},
             {"label": "Corr (12m)", "source": "macro.corr.spx_ism_12m"}]}]
```

Before dual-axis: print `df['series'].unique()` and assert the right-axis name is present. Name mismatch is the #1 failure mode.

### 1.4 Bullet: rates RV screen

```python
datasets["rv"] = pd.DataFrame({"metric": [...], "current": [...],
                                "low_5y": [...], "high_5y": [...],
                                "z": [...], "pct": [...]})
```

```json
{"widget": "chart", "id": "rv_screen", "w": 6, "h_px": 480, "title": "Rates RV screen",
  "spec": {"chart_type": "bullet", "dataset": "rv",
            "mapping": {"y": "metric", "x": "current",
                        "x_low": "low_5y", "x_high": "high_5y",
                        "color_by": "z", "label": "pct"}}}
```

### 1.5 Pairing thesis + watch notes (high-leverage opening)

```json
"layout": {"rows": [
  [{"widget": "note", "id": "n_thesis", "w": 6,
     "kind": "thesis", "title": "Bull-steepener resumes",
     "body": "The curve is **bull-steepening** for the third session..."},
   {"widget": "note", "id": "n_watch", "w": 6,
     "kind": "watch", "title": "Levels to watch",
     "body": "| Level | Significance |\n|---|---|\n| 4.10% 10Y | 50dma |\n"}],
  [{"widget": "chart", "id": "curve_lvl", "w": 6, "h_px": 380,
     "title": "Curve — level", "spec": {...}},
   {"widget": "chart", "id": "curve_chg", "w": 6, "h_px": 380,
     "title": "Curve — 1d change", "spec": {...}}]]}
```

The chart row stays 2-up. If only one curve view exists, pair with a `stat_grid` strip of curve metrics instead.

---

## 2. Data shape prep + archetypes

**Five non-negotiables for DataFrames:**

1. **Tidy.** One row = one observation, one column = one variable. No multi-index, no embedded headers, no totals row.
2. **Date as a column.** Never as `DatetimeIndex`. Use `df.reset_index()`. Compiler emits `date` to ISO-8601; ECharts auto-detects time-axis.
3. **Plain-English columns.** `us_10y`, not `USGG10YR Index`. Compiler humanises `us_10y` → `US 10Y` for legends, tooltips, axis hints.
4. **Datasets named like nouns.** `rates`, `cpi`, `flows`, `bond_screen` — not `df1`, not `usggt10y_panel`.
5. **A dataset earns its name.** Register in `manifest.datasets` if (a) more than one widget reads from it, OR (b) a single widget needs filter-aware re-rendering, OR (c) a table widget displays the rows verbatim. Otherwise inline a one-shot DataFrame is fine.

**Data archetypes → chart types:**

| # | Archetype | DataFrame shape | Chart type |
|---|-----------|-----------------|------------|
| 1 | Univariate time series | `(date, value)` | `line` |
| 2 | Multi-variable TS, fixed | `(date, v1, v2, ...)` wide | `multi_line`, `area` |
| 3 | Multi-variable TS, dynamic | `(date, group, value)` long | `multi_line` color=, `area` color= |
| 4 | Cross-section, 1 metric | `(cat, value)` | `bar`, `bar_horizontal`, `pie`, `donut`, `funnel` |
| 5 | Cross-section, grouped | `(cat, group, value)` long | `bar` stack, `scatter` color= |
| 6 | Bivariate scatter | `(x_num, y_num, [color])` | `scatter`, `scatter_multi` |
| 7 | Distribution | `(value)` one column | `histogram` |
| 8 | Distribution by group | `(group, value)` long | `boxplot` |
| 9 | Range + current marker | `(cat, lo, hi, cur, ...)` | `bullet` |
| 10 | OHLC time series | `(date, open, close, low, high)` | `candlestick` |
| 11 | Daily scalar over a year | `(date, value)` | `calendar_heatmap` |
| 12 | Cat × cat matrix | `(x_cat, y_cat, value)` long | `heatmap` |
| 12b | Wide-form TS correlation | `(date, col_a, col_b, ...)` wide | `correlation_matrix` |
| 13 | Hierarchy | path or `(name, parent, value)` | `treemap`, `sunburst`, `tree` |
| 14 | Flow / network | `(source, target, value)` | `sankey`, `graph` |
| 15 | Multi-dim by entity | `(entity, dim, value)` long | `radar`, `parallel_coords` |
| 16 | Single scalar | one number | `gauge` |
| 17 | Rich row-per-entity | `(id, attr1, attr2, ...)` wide | `table` widget |
| 18 | Latest snapshot from TS | (any TS DF) | `kpi`, source = `<ds>.latest.<col>` |
| 19 | Sparse event list | `(date, label, [color])` | annotations on another chart |
| 20 | Schedule / agenda | `(date, time, event, ...)` | `table` widget |
| 21 | Exploratory bivariate | wide numeric panel | `scatter_studio` |

**Compiler refuses to silently fix:**

- `df.reset_index()` before passing DTI-keyed frame
- Unpack `pull_market_data` tuples: `eod_df, _ = pull_market_data(...)`
- Flatten MultiIndex: `df.columns = ['_'.join(c) for c in df.columns]`
- Rename opaque API codes to plain English
- Resample to native frequency per series

**Data budgets** (enforced by `strict=True`): single dataset 10K rows (warn) / 50K (err); single dataset 1 MB / 2 MB; total manifest 3 MB / 5 MB; table-widget 1K / 5K rows.

**Frequency-mixing trap.** Haver stores many monthly / quarterly series at business-daily granularity. Symptom: stair-step lines. Fix: resample to true native frequency before charting; never chart a DataFrame with mixed-frequency NaN gaps.

```python
starts = starts.resample('M').last()   # stock: last-of-month
claims = claims.resample('M').mean()   # flow: mean
cpi    = cpi.resample('Q').last()      # rate: last-of-quarter
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
```

---

## 3. Editing an existing dashboard manifest

When the user asks to ADD / EDIT / UPDATE / EXTEND an existing dashboard's spec (vs. building one from scratch), the path is **raw JSON CRUD on `manifest_template.json`** via ephemeral session-folder code. Never rebuild the manifest dict from scratch and overwrite — that wipes any widgets / tabs / filters / datasets PRISM didn't include in this script's dict (the manifest-wipe footgun, see `dashboards.md` § 2.5.4).

**The SSOT for CRUD patterns is `dashboards/template_crud.md`** — read patterns (find / list / inspect), the layout-aware `_walk_rows` traversal helper, widget CRUD (add to tab.row, insert at column, replace spec, remove, move across rows / tabs), tab CRUD (add / remove / reorder / update), filter CRUD (add / update / remove / target manipulation), dataset slot CRUD (add / remove / update schema), metadata + chrome CRUD, the in-session quick recompile (§ 9 of that spoke), the contract (5 rules), and the anti-patterns (6 footguns). Fetch it on demand whenever the user-ask routes through this section.

The same READ → PLAN → WRITE discipline applies to `pull_data.py` and `build.py` themselves; the manifest template is one of three editable surfaces, all with the same fragility shape. See `dashboards/pipelines.md` for the full pipeline-aware editing model: catalog existing pipelines (§ 2), pick a reuse path (§ 3), preserve active-pipeline integrity (§ 4), re-author end-to-end (§ 5), run the post-edit health check (§ 6).

The skeleton (full patterns in `dashboards/template_crud.md`):

```python
import json, copy

DASHBOARD_PATH = f"users/{kerberos}/dashboards/{name}"

# 1. AUDIT (dashboards.md § 2.5.3 — load existing manifest, run audit; raises if non-compliant)
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)

# 2. READ + deepcopy
tpl = copy.deepcopy(json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8")))

# 3. MUTATE in place — pattern from template_crud.md § 3-§ 8
#    e.g. append a chart widget to tab "tips_rv", row 1
tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == "tips_rv")
while len(tab["rows"]) <= 1:
    tab["rows"].append([])
tab["rows"][1].append({
    "widget": "chart", "id": "carry_roll_scatter", "w": 6, "h_px": 380,
    "title": "Carry + Roll vs Modified Duration",
    "spec": {"chart_type": "scatter", "dataset": "carry_roll",
             "mapping": {"x": "ModDur", "y": "CR_k", "color": "maturity_year"}}})

# 4. VALIDATE before writing
validate_manifest(tpl)

# 5. WRITE the merged template back
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")

# 6. VERIFY via in-session quick recompile (dashboards.md § 6.6 / template_crud.md § 9)
#    exec(build.py from S3) confirms the change compiles against current data.
```

`scripts/build.py` is touched only when the dataset shape it builds against has changed (a new dataset key was added, a key was removed, or a column was renamed). Pure widget / filter / layout edits leave `build.py` alone. When `build.py` (or `pull_data.py`) does need to change, the rule is `dashboards.md` § 2.5.5 — surgical READ → MUTATE → WRITE, never wholesale re-emission. See § 6 below for the worked recipe.

When in doubt about whether a request is "edit existing" vs "build new":

| User says... | Path |
|---|---|
| "add a chart / widget / KPI / tab / row to <existing dashboard>" | Raw JSON CRUD on `manifest_template.json` |
| "edit / update / change the title / filter / dataset / metadata" | Raw JSON CRUD on `manifest_template.json` |
| "change a chart_type / mapping" | Raw JSON CRUD on `manifest_template.json` |
| "extend / append to <existing dashboard>" | Raw JSON CRUD on `manifest_template.json` |
| "rebuild from scratch" / "start over" / "delete and recreate" | Fresh-build (Tools 1+2+3+4) — surface the destructive intent first |
| "build me a dashboard for X" (no existing surfaced) | Fresh-build (Tools 1+2+3+4) |

When user intent is ambiguous ("can you also show <metric>?" on a dashboard with prior history), treat as CRUD by default — the surgical change is recoverable; a fresh-build is not.

---

## 4. Data-pipeline coupling detection

When a chart redesign references a column / lag / window / aggregation that doesn't exist in the current dataset, the change is NOT manifest-only — `scripts/pull_data.py` must be edited too. The detection rule below is the gating step before the deeper pipeline-aware path in `dashboards/pipelines.md` §3 (the reuse decision ladder: reuse-existing-CSV / extend-existing-pipeline / add-new-pipeline). Use this section to detect that pipeline work is needed; use `pipelines.md` to pick which of the three paths.

Decision rule before authoring `_add_widget` / `_set_dataset` (§3) on an existing dashboard:

| Asked-for column / window exists in `df.columns`? | Route |
|---|---|
| YES | manifest-only — READ → MERGE → WRITE per §3 |
| NO; the closest existing column is an acceptable proxy | propose the existing column as a partial fix; let the user accept or override |
| NO; pipeline edit is the only path | propose the `pull_data.py` change; wait for user confirmation before re-authoring |
| NO; neither acceptable | skip the chart; surface that the data isn't there |

Detection cue: every Tool 1 verify prints `df.columns`. Reference any `mapping.<key>` against that set before authoring. The compiler raises `chart_mapping_column_missing` regardless, but pre-author detection saves a round-trip and keeps the user in the loop on the trade-off.

**Pipeline-edit propose-and-confirm.** Before re-authoring `pull_data.py`:

> "The current dataset has [<existing columns>]. To implement [<asked-for column / lag / window>] I'd need to add [<derivation>] to `scripts/pull_data.py` (and re-author `scripts/build.py` if the dataset shape changes). Want me to proceed with the pipeline change, or ship the simpler version using existing data?"

Wait for confirmation. After confirming, mutate `pull_data.py` surgically per §6 below (READ → MUTATE → WRITE; the `_persist_versioned_script` write bumps v(N+1)), exec from S3 to verify the new CSV, then surgically mutate `build.py` only if dataset shape changed (column rename, drop, key add). The "re-author end-to-end" framing in `dashboards/pipelines.md` §5 applies only to first-time creation; for edits, §6 below is the path.

**Refresh-runner namespace audit.** Before re-authoring `pull_data.py`, confirm every helper used is in the runner namespace (`dashboards.md` §6.5). Runner injects `pd` / `np` / `io` / `json` / `os` / `datetime` / `s3_manager` plus the four pull primitives plus compile / populate / template / validate helpers. NOT `SESSION_PATH` (the script self-defines it on its first line per `dashboards.md` Rule 5), NOT `save_artifact`, NOT alt-data clients (`fdic_client`, `sec_edgar_client`, `bis_client`, ...). Using a not-injected name lets the in-session build pass and breaks the daily refresh — set the registry entry's `refresh_frequency: "manual"` if you can't avoid them; the browser `Refresh` button stays available.

---

## 5. Revert workflow

`scripts/pull_data.py` and `scripts/build.py` carry a first-class versioned history under `scripts/versions/<name>_v<N>.py` (`dashboards.md` §2.6). For script-level reverts, that history IS the revert primitive — there is no need to author a recovery script from scratch or rely on `archive/<UTC>/` quarantine. For non-script state (`manifest_template.json` mutations via §3 READ → MERGE → WRITE; `data/*.csv` corruption; `manifest.json` hand-edits), the historical recovery paths still apply because they're not captured in the script-version chain.

| Source of prior state | When it applies | Path |
|---|---|---|
| `scripts/versions/<pull_data\|build>_v<K>.py` snapshot pair | The user wants to revert script behaviour to "what version K did" | First-class versioning primitive — see Path 1 below |
| Dashboard has `keep_history: true` in its registry entry | The user wants to restore both scripts AND the rendered manifest from a snapshot the runner produced; or revert a `manifest_template.json` change that didn't go through Tools 1+2 | Load the most recent `{DASHBOARD_PATH}/history/<UTC>/` snapshot (runner-managed); restore its files via §3 WRITE step + (for scripts) Path 1 to enter the version chain at v(N+1) |
| Prior `manifest_template.json` was quarantined to `archive/<UTC>/` (§5.2 of dashboards.md) — Pure-template edit (no script change) made via §3 WRITE that the user wants to undo | Read the archived file, validate it, restore via §3 WRITE step. Scripts are unaffected; no version bump |
| User can describe the prior layout in chat | The user-described prior state has neither a script-version snapshot nor a `history/` / `archive/` source | Re-build the prior `manifest_template.json` from scratch following the description; surface alt vs current state before writing. If the description implies a script change, route through Path 1 by treating the rebuild as a fresh Tools 1+2 cycle |
| None of the above | Genuinely no recoverable prior state exists | Surface the limitation: "no script-version snapshot, no `history/` snapshot, no `archive/` artefact for what you're describing — can you describe the prior state, or point me at a known-good manifest file?" |

### Path 1 — first-class script revert via §2.6

When the user asks to revert to a specific script version (`v3`), or to "go back to before the last edit" (= revert to `v(max-1)`), or to "the last working version" (= the highest version whose `manifest.metadata.script_version` corresponds to a green `refresh_status.json`):

```python
import re

DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# 1. AUDIT current state (per dashboards.md §2.5.3)
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)

# 2. LIST available versions (the user's choice set)
versions = set()
for entry in s3_manager.list(f"{DASHBOARD_PATH}/scripts/versions/"):
    mm = re.match(r'^(?:pull_data|build)_v(\d+)\.py$',
                  entry['Key'].rsplit('/', 1)[-1])
    if mm:
        versions.add(int(mm.group(1)))
print(f"available versions: {sorted(versions)}")
print(f"current live version: {max(versions)}")

# 3. PICK the rollback target (e.g. K = max(versions) - 1 for "the last edit")
ROLLBACK_TO = ...   # integer from the user / from chat context
if ROLLBACK_TO not in versions:
    raise ValueError(
        f"no v{ROLLBACK_TO} snapshot in scripts/versions/; "
        f"available: {sorted(versions)}"
    )

# 4. READ the rollback target bytes
src_pull_data = s3_manager.get(
    f'{DASHBOARD_PATH}/scripts/versions/pull_data_v{ROLLBACK_TO}.py'
).decode('utf-8')
src_build = s3_manager.get(
    f'{DASHBOARD_PATH}/scripts/versions/build_v{ROLLBACK_TO}.py'
).decode('utf-8')

# 5. BUMP + PERSIST as the new live version (rollback IS a new version,
#    content = vK; the chain stays monotonically increasing; vK never moves).
SCRIPT_VERSION = _next_script_version(DASHBOARD_PATH)
print(f"rolling back to v{ROLLBACK_TO}; persisting as v{SCRIPT_VERSION}")
_persist_versioned_script(DASHBOARD_PATH, 'pull_data',
                          src_pull_data, SCRIPT_VERSION)
_persist_versioned_script(DASHBOARD_PATH, 'build',
                          src_build, SCRIPT_VERSION)

# 6. RUN Tools 1+2+3+4 (dashboards.md §6.1) to validate against today's
#    data and refresh the rendered dashboard. Tool 1+2 EXEC the live
#    scripts/<name>.py (which now carries the rollback bytes); Tool 4
#    spawns the subprocess refresh; the user's first view is byte-
#    identical to what tomorrow's cron will produce.
```

The chain is monotonically increasing; vK never moves; v(N+1) is the rollback's audit trail (`scripts/versions/pull_data_v{N+1}.py` is byte-identical to `pull_data_v{K}.py`, providing a permanent record that "we rolled back to K at this point in the timeline"). This is by design: rolling back doesn't erase history, it records the rollback as the next event.

**Why bump-and-persist rather than just overwrite live with vK bytes.** A non-bumped rollback (just `s3_manager.put(src_pull_data, ...scripts/pull_data.py)`) immediately violates the §2.6 "live = highest version" invariant because `scripts/pull_data.py` now contains v3 bytes while `scripts/versions/pull_data_v(max).py` contains the bytes that were the live version a moment ago. The next §2.5 audit raises `§2.6 live-vs-version drift`. Bumping makes the rollback a first-class event in the chain — the audit stays clean, and the historical record is preserved.

In all paths above, run `_audit_dashboard_layout` (§2.5.3 of dashboards.md) on the restored folder before declaring revert complete. Then run the full session-folder health check (`dashboards/pipelines.md` §6) including step 8 (version chain integrity). A revert is just a special case of script editing where the "edit" is "carry forward the bytes from a prior version", and every pipeline-integrity rule still applies. The pre-edit catalog (§5.2 of pipelines.md) and post-restore CSV-column diff are the load-bearing checks.

PRISM rule: never silently rebuild a "best-guess" prior version. The §2.6 versioning chain is the source of truth for script-level history; if the user asks for "the prior version" it almost always means a specific `scripts/versions/<name>_vK.py` they can name (or that PRISM can disambiguate by listing). Either restore from a real source (versioning chain / `history/` / `archive/` / chat description) or surface the limitation. A botched revert is harder to recover from than the original bad change.

---

## 6. Surgical script edit (`scripts/build.py` / `scripts/pull_data.py`)

When the dataset shape changes (new column, new pull source, new derived dataset, column rename, pull-fn swap), scripts are mutated SURGICALLY — never re-emitted from a fresh string (`dashboards.md` §2.5.5). The script-rebuild path is reserved for first-time creation (Tools 1+2+3+4) and total demolition.

Six steps:

1. AUDIT (`dashboards.md` §2.5.3) — folder must be compliant before any mutation
2. PIN `SCRIPT_VERSION = _next_script_version(...)` (§2.6.1) — same as Tools 1+2
3. READ live bytes from S3
4. MUTATE via `str.replace` against a unique anchor; `assert` non-zero diff so silent no-ops surface as errors
5. WRITE via `_persist_versioned_script` (live + versioned snapshot in lockstep)
6. EXEC from S3 with refresh-runner namespace to verify the new bytes run cleanly

```python
DASHBOARD_PATH = f"users/{kerberos}/dashboards/{name}"
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)

SCRIPT_VERSION = _next_script_version(DASHBOARD_PATH)

# Mutate pull_data.py: add a new Haver code to an existing pipeline
src = s3_manager.get(f"{DASHBOARD_PATH}/scripts/pull_data.py").decode("utf-8")
new_src = src.replace(
    "codes=[\n        'FFED@DAILY', # Effective Fed Funds Rate\n"
    "        'SOFR@DAILY', # SOFR\n   ],",
    "codes=[\n        'FFED@DAILY', # Effective Fed Funds Rate\n"
    "        'SOFR@DAILY', # SOFR\n"
    "        'FRBM3@DAILY', # 3-month T-bill\n   ],",
)
assert new_src != src, "anchor not found in live pull_data.py"
_persist_versioned_script(DASHBOARD_PATH, 'pull_data', new_src, SCRIPT_VERSION)

# Exec from S3 to verify (refresh-runner namespace; same as Tool 1).
# SESSION_PATH is NOT in ns: pull_data.py self-defines it on its first
# line (dashboards.md Rule 5).
src = s3_manager.get(f"{DASHBOARD_PATH}/scripts/pull_data.py").decode("utf-8")
ns = {'pd': pd, 'np': np, 'io': io, 'json': json, 'os': os,
      'datetime': datetime, 's3_manager': s3_manager,
      'pull_haver_data': pull_haver_data, 'pull_market_data': pull_market_data,
      'pull_plottool_data': pull_plottool_data, 'pull_fred_data': pull_fred_data,
      'save_artifact': save_artifact}
exec(compile(src, f'{DASHBOARD_PATH}/scripts/pull_data.py', 'exec'), ns)

# Verify the new column shape lands in the CSV
df = pd.read_csv(io.BytesIO(
    s3_manager.get(f'{DASHBOARD_PATH}/data/fed_rates.csv')),
    index_col=0, parse_dates=True)
assert 'FRBM3@DAILY' in df.columns or 'tbill_3m_pct' in df.columns
```

**Anchor selection.** Pick the SMALLEST contiguous string that uniquely identifies the insertion point. Multi-line anchors with leading whitespace are stable across reformatting; single-token anchors collide with multiple sites. Always include enough surrounding context (one line above, one line below) that the anchor is unique. The `assert new_src != src` guards against silent no-op when the anchor drifts.

**Multi-mutation chain.** If the edit needs multiple insertion points, chain `.replace()` calls in sequence and assert against each:

```python
src1 = src.replace(OLD_A, NEW_A);  assert src1 != src
src2 = src1.replace(OLD_B, NEW_B); assert src2 != src1
_persist_versioned_script(DASHBOARD_PATH, 'build', src2, SCRIPT_VERSION)
```

**Edit + manifest pair.** When the script edit implies a `manifest_template.json` edit (PRISM is asked to surface a new column as a chart), do BOTH in the same Tools 1+2 cycle. Tool 1 mutates `pull_data.py` + execs; Tool 2 mutates `build.py` (only if dataset shape changed) AND mutates `manifest_template.json` (per §3) to surface the new column. Both scripts version-bump in lockstep (§2.6 coupled-bump invariant).

**Anti-pattern (the script-rebuild footgun):**

```python
# WRONG -- regenerates the whole script as a fresh string for an
# "add a column" ask. Drops in-flight content PRISM partly remembers,
# re-introduces previously-fixed bugs, and re-triggers Python-into-JS
# interpolation footguns if any inline-string content survives (e.g.
# a tool widget's compute_js authored at first build).
build_py = '''
... 200 lines, half from memory, half newly authored ...
'''
_persist_versioned_script(DASHBOARD_PATH, 'build', build_py, SCRIPT_VERSION)
```

---

## 7. Derived datasets in `build.py`

`build.py` is not a thin loader. After loading raw CSVs from `pull_data.py`'s output, `build.py` is the right surface for **derivation** — anything that can be computed from existing pulls without another network call. Hand-typed `value: <num>` in the manifest is forbidden (`dashboards.md` Rule 1; codes `kpi_static_value_forbidden` / `stat_grid_static_value_forbidden`). Derivation in `build.py` replaces that footgun with refresh-safe computation.

Canonical patterns:

| Need | Pattern | Resulting dataset |
|---|---|---|
| YoY change | `df[f"{col}_yoy"] = df[col].pct_change(52) * 100` (weekly) or `pct_change(12)` (monthly) | `yoy_changes` keyed by date |
| Composition % | `df["a_pct"] = df["a"] / (df["a"] + df["b"] + df["c"]) * 100` | `<thing>_composition` (rows × pct columns) |
| Funding ratio | `df["loan_to_deposit"] = df_a["loans"] / df_b["deposits"] * 100` | cross-dataset ratio after `.join` |
| Cross-dataset join | `combined = df_a.join(df_b, how="outer").join(df_c, how="outer")` | `<thing>_combined` for multi-axis charts |
| Subset projection | `subset = df[["col_a", "col_b", "col_c"]].copy()` | trim to chart-relevant columns only |

Each derivation becomes its own `manifest.datasets[<key>]` entry, populated via `populate_template`. The KPI / chart / stat_grid widgets reference the derived key by `source: "<key>.latest.<col>"` or `mapping.x/y`, and the next refresh re-derives from current pulls — the surface auto-updates without PRISM touching the manifest.

Worked example. `bank_health` has `total_deposits` + `borrowings`; `bank_bs` has `total_assets` + `loans_leases`. To surface a "loan-to-deposit" KPI plus a "deposit funding %" chart, derive in `build.py`:

```python
funding = pd.DataFrame(index=bank_bs.index)
funding["total_assets"]      = bank_bs["total_assets"]
funding["total_deposits"]    = bank_health["total_deposits"]
funding["borrowings"]        = bank_health["borrowings"]
funding["deposit_funding_pct"] = funding["total_deposits"] / funding["total_assets"] * 100
funding["loan_to_deposit"]    = bank_bs["loans_leases"] / bank_health["total_deposits"] * 100
funding = funding.dropna()

datasets["funding"] = funding.reset_index()    # surfaces as manifest.datasets["funding"]
```

The KPI tile then reads `source: "funding.latest.loan_to_deposit"` instead of a hand-typed `value`. Every refresh re-derives from current pulls.

**Reuse decision.** If the data is in EXISTING pulls, derive in `build.py` (this section). If the data needs a NEW pull, surgically edit `pull_data.py` per §6 — but only after confirming no existing column suffices. The full reuse-decision ladder lives in `dashboards/pipelines.md` §3 (reuse-existing-CSV / extend-existing-pipeline / add-new-pipeline); this section covers the "derive in build.py" branch.
