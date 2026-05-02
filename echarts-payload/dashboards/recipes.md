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

When the user asks to ADD / EDIT / UPDATE / EXTEND an existing dashboard (vs. building one from scratch), follow READ → MERGE → WRITE on `manifest_template.json`. Never rebuild the manifest dict from scratch and overwrite — that wipes any widgets / tabs / filters / datasets PRISM didn't include in this script's dict (the canonical manifest-wipe footgun, see `dashboards.md` §2.5.4).

```python
import json
from copy import deepcopy

DASHBOARD_PATH = f"users/{kerberos}/dashboards/{name}"

# 1. AUDIT (per dashboards.md §2.5.3 — load existing manifest, run audit; raises if folder is non-compliant)
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)

# 2. READ the template (the post-data-strip version that build.py re-populates)
tpl = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8"))
tpl = deepcopy(tpl)  # mutate a copy; never the loaded ref

# 3. MERGE — surgical mutations only. Three common shapes:

# 3a. Append a widget to a tab.row (or grid.row)
def _add_widget(tpl, *, tab_id, row_idx, widget):
    """Append `widget` to tpl.layout.tabs[<tab_id>].rows[row_idx], or create the row."""
    tabs = tpl["layout"]["tabs"] if tpl["layout"]["kind"] == "tabs" else None
    if tabs:
        tab = next(t for t in tabs if t["id"] == tab_id)
        rows = tab["rows"]
    else:
        rows = tpl["layout"]["rows"]
    while len(rows) <= row_idx:
        rows.append([])
    rows[row_idx].append(widget)

# 3b. Add or replace a dataset key (template carries empty source; build.py populates)
def _set_dataset(tpl, key, *, schema=None):
    """Register a new dataset key. build.py needs a matching pull + populate_template entry."""
    tpl["datasets"][key] = {"source": []}  # build.py will fill via populate_template
    if schema:
        tpl["datasets"][key]["schema"] = schema

# 3c. Edit an existing filter's range / default / targets
def _update_filter(tpl, filter_id, **changes):
    f = next(f for f in tpl["filters"] if f["id"] == filter_id)
    f.update(changes)

# Concrete usage:
_add_widget(tpl, tab_id="tips_rv", row_idx=1, widget={
    "widget": "chart", "id": "carry_roll_scatter", "w": 6, "h_px": 380,
    "title": "Carry + Roll vs Modified Duration",
    "spec": {"chart_type": "scatter", "dataset": "carry_roll",
             "mapping": {"x": "ModDur", "y": "CR_k", "color": "maturity_year"}}})
_set_dataset(tpl, "carry_roll")
_update_filter(tpl, "max_maturity_year", max=2056, default=2056)

# 4. VALIDATE before writing — catches schema breakage at the script boundary
validate_manifest(tpl)

# 5. WRITE the merged template back. manifest.json + dashboard.html will be regenerated by the next build.py run; the runner picks that up on schedule, or trigger it manually with the next refresh.
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")
```

`scripts/build.py` is RE-AUTHORED only when the dataset shape it builds against has changed (a new dataset key was added in step 3b, a key was removed, or a column was renamed). Pure widget / filter / layout edits leave `build.py` alone.

When in doubt about whether a request is "edit existing" vs "build new":

| User says... | Path |
|---|---|
| "add a chart / widget / KPI / tab / row to <existing dashboard>" | READ → MERGE → WRITE |
| "edit / update / change the title / filter / dataset / metadata" | READ → MERGE → WRITE |
| "extend / append to <existing dashboard>" | READ → MERGE → WRITE |
| "rebuild from scratch" / "start over" / "delete and recreate" | Fresh-build (Tools 1+2+3) — surface the destructive intent first |
| "build me a dashboard for X" (no existing surfaced) | Fresh-build (Tools 1+2+3) |

When user intent is ambiguous ("can you also show <metric>?" on a dashboard with prior history), treat as MERGE by default — the surgical change is recoverable; a fresh-build is not.
