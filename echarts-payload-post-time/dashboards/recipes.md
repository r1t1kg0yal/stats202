# Recipes + data archetypes

Spoke fetched on demand from the dashboards hub. Worked patterns showing how the primitives compose, the canonical data-shape → chart-type lookup, and transforms-hook patterns for `scripts/build.py`. Same chart-type names + mapping keys as `charts.md`.

All chart widgets in these recipes use `w: 6` (or smaller) — chart widgets are never full-width.

For first-time creation see hub §B; for raw JSON CRUD on `manifest_template.json` see hub §C; for `pull_data.py` / `build.py` edits see hub §D; for revert see hub §G; for refresh discipline see hub §E.

---

## 1. Common widget-pair patterns

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

## 3. Transforms hook patterns (`scripts/build.py`)

`build.py` defines `TRANSFORMS = [<fn>, ...]` — a list of `def derive_<name>(datasets) -> dict` functions. The engine (`build_dashboard`) loads every `data/<stem>.csv` into a `datasets` dict keyed by stem, runs each transform in order (chained — each receives the dict and returns it), then `populate_template` + `compile_dashboard`. Transforms are how derived datasets land in the manifest without PRISM hand-typing numbers (Rule 1).

Hand-typed `value: <num>` in a KPI / stat_grid is forbidden (`kpi_static_value_forbidden` / `stat_grid_static_value_forbidden`, both always-blocking). Derivation in `build.py` replaces that footgun with refresh-safe computation.

**Canonical patterns:**

| Need | Pattern | Resulting dataset |
|---|---|---|
| YoY change | `df[f"{col}_yoy"] = df[col].pct_change(52) * 100` (weekly) or `pct_change(12)` (monthly) | enrich existing dataset in place |
| Composition % | `df["a_pct"] = df["a"] / (df["a"] + df["b"] + df["c"]) * 100` | new `<thing>_composition` |
| Funding ratio | `df["loan_to_deposit"] = df_a["loans"] / df_b["deposits"] * 100` | new cross-dataset ratio after `.join` |
| Cross-dataset join | `combined = df_a.join(df_b, how="outer").join(df_c, how="outer")` | new `<thing>_combined` for multi-axis charts |
| Subset projection | `subset = df[["col_a", "col_b", "col_c"]].copy()` | trim to chart-relevant columns |

Each derivation writes into the `datasets` dict under its own key. The KPI / chart / stat_grid widgets in the manifest reference the derived key via `source: "<key>.latest.<col>"` or `mapping.x/y`. Next refresh re-derives from current pulls — the surface auto-updates without PRISM touching the manifest.

### 3.1 In-place enrichment (YoY / pct_change)

```python
def derive_cpi_yoy(datasets):
    df = datasets['cpi']
    df['core_yoy'] = df['core_cpi'].pct_change(12) * 100
    df['headline_yoy'] = df['headline_cpi'].pct_change(12) * 100
    return datasets
```

The `cpi` dataset gains two columns (`core_yoy`, `headline_yoy`) without changing its key. Charts that bind `mapping.y="core_yoy"` against `dataset="cpi"` work directly.

### 3.2 New derived dataset (composition / ratios)

```python
def derive_funding(datasets):
    bs = datasets['bank_bs']        # total_assets, loans_leases
    health = datasets['bank_health']  # total_deposits, borrowings
    funding = pd.DataFrame(index=bs.index)
    funding["total_assets"]        = bs["total_assets"]
    funding["total_deposits"]      = health["total_deposits"]
    funding["borrowings"]          = health["borrowings"]
    funding["deposit_funding_pct"] = funding["total_deposits"] / funding["total_assets"] * 100
    funding["loan_to_deposit"]     = bs["loans_leases"] / health["total_deposits"] * 100
    funding = funding.dropna()
    datasets["funding"] = funding.reset_index()
    return datasets
```

The KPI tile then reads `source: "funding.latest.loan_to_deposit"` instead of a hand-typed `value`. Every refresh re-derives from current pulls.

### 3.3 Cross-dataset join (multi-axis chart)

```python
def derive_macro_panel(datasets):
    spx = datasets['equities'][['date', 'spx']]
    ism = datasets['ism'][['date', 'manufacturing']].rename(columns={'manufacturing': 'ism'})
    panel = spx.merge(ism, on='date', how='outer').sort_values('date')
    datasets['macro'] = panel
    return datasets
```

The dual-axis chart spec then references `dataset="macro"` with `mapping.dual_axis_series=["ism"]`.

### 3.4 Subset projection (table-friendly slice)

```python
def derive_top_movers(datasets):
    universe = datasets['stocks']
    movers = (universe
              .assign(abs_ret=lambda x: x['daily_return'].abs())
              .nlargest(20, 'abs_ret')[['ticker', 'price', 'daily_return', 'volume']])
    datasets['top_movers'] = movers
    return datasets
```

A `widget: table` then references `dataset="top_movers"` and renders the 20 rows directly.

### 3.5 Multi-step transform chain

Transforms compose. The engine calls each in declared order, passing the (mutated) datasets dict forward. So a derive that depends on a prior derive is a separate `def`, declared after its dependency in `TRANSFORMS`:

```python
def derive_funding(datasets):
    # ... computes 'funding' dataset
    return datasets

def derive_funding_yoy(datasets):
    df = datasets['funding']
    df['loan_to_deposit_yoy'] = df['loan_to_deposit'].pct_change(4) * 100  # quarterly
    return datasets

TRANSFORMS = [derive_funding, derive_funding_yoy]
```

### 3.6 Reuse decision (when does the data need a NEW pull vs a transform?)

| If the data is... | Path |
|---|---|
| Already a column in an existing CSV | Just reference it from the manifest — no transform needed |
| Computable from existing CSV columns (YoY, ratio, join, subset, rename) | Transform in `build.py` (this section) |
| Not in any CSV but available from a source already wired up in `pull_data.py` | Extend the existing pull (per hub §D, Step 2 of the reuse ladder) |
| Not in any CSV and needs a new vendor / source | Add a new `pull_<name>` function (per hub §D, Step 3) |

The full reuse-decision ladder lives in `dashboards/pipelines.md` §3.
