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
