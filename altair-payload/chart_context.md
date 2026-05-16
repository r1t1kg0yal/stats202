# Altair Charts & Tables (`make_chart`, `make_table`)

- **Module:** `chart_context`
- **Audience:** PRISM (all interfaces, all workflows), developers
- **Tier:** 2 (on-demand)
- **Scope:** All static-PNG chart and table authoring (chat / email / report). Composites ship in this same module. Interactive HTML dashboards use `dashboards` (echarts).

`make_chart()`, `make_table()`, the composite/annotation/profile helpers are auto-injected. Raw matplotlib is blocked. Do NOT import chart functions. `s3_manager`, `session_path`, `user_id` are auto-injected at call time -- never pass them.

**Tables are first-class.** Every table PRISM authors goes through `make_table()` — across every interface (chat / email / report / any artifact for the user). **Markdown tables are forbidden anywhere in PRISM output.** The full table surface lives in the `chart_context_tables.md` spoke (fetched on demand); see "Tables vs Charts" below for the trigger.

---

## Catalog index

| Primitive | Names | Where |
|---|---|---|
| Chart types (12) | `multi_line`, `scatter`, `scatter_multi`, `bar`, `bar_horizontal`, `heatmap`, `histogram`, `boxplot`, `area`, `donut`, `bullet`, `waterfall` | §6 |
| Mapping keys | `x`, `y`, `color`, `value`, `theta`, `y_title`, `y_title_right`, `x_title`, `x_sort`, `y_sort`, `x_type`, `dual_axis_series`, `invert_right_axis`, `dual_axis_config`, `legend`, `trendline`, `trendlines`, `stack`, `strokeDash`, `strokeDashScale`, `strokeDashLegend`, `bins`, `maxbins`, `bin_extent`, `extent`, `scale_type`, `orientation`, `color_sort` (alias `legend_sort`), `value_sort`, `x_low`, `x_high`, `color_by`, `label`, `type` | §7 |
| Annotation classes (11) | `VLine`, `HLine`, `Segment`, `Band`, `Arrow`, `PointLabel`, `PointHighlight`, `Callout`, `LastValueLabel`, `Trendline`, `PlotText` | §8 |
| Composite functions (5) | `make_2pack_horizontal`, `make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid` | §10 |
| Grid mode (small-multiples / facet) | `mapping['facet']`, `facet_cols`, `same_scale`, `share_x` / `share_y` / `share_color` | spoke `chart_context_grids.md` (Spokes index below) |
| Static tables (PNG) | `make_table` + `TableResult`; content-driven canvas (engine-decided width + height); same navy palette and font as `make_chart` | spoke `chart_context_tables.md` (Spokes index below) |
| Skin (only published) | `gs_clean` | §1 |
| Intent values | `'explore'`, `'publish'`, `'monitor'` | §1 |
| Layer types | `regression`, `rule`, `point` | §8.5 |

---

## Spokes (mid-session fetch)

This hub covers the always-needed surface. Deeper specs for narrow topics live in spoke files fetched on demand.

**Do NOT call `get_context()` again — it is one-shot per user message.** Mid-session reads use `list_ai_repo` with `mode="full"`. **Pass ONLY `file_paths` and `mode` — actively omit every other parameter.**

| Spoke | Contents | Verbatim tool call (copy-paste) |
|---|---|---|
| `chart_context_grids.md` | Grid mode (small-multiples / facet): `mapping['facet']`, `facet_cols`, `same_scale` smart-route, `share_x` / `share_y` / `share_color`, scatter phase-space gradient on a temporal / numeric color column, 36-panel hard cap | `list_ai_repo(file_paths=["context/modules/static/chart_context_grids.md"], mode="full")` |
| `chart_context_tables.md` | Static-PNG tables — `make_table()` + `TableResult`; the 3 PRISM-facing color modes (`'rwg'` / `'bw'` / `'rag'`); `heatmap_groups` (column / row / group scope); multi-level `header_levels`; `row_groups` navy bands; `row_indent`, `total_rows`, `subtotal_rows`; sparkline + mini-bar cells. Canvas is engine-decided (content-sized; never preset, never truncated). | `list_ai_repo(file_paths=["context/modules/static/chart_context_tables.md"], mode="full")` |
| `chart_context_colors.md` | Per-chart palette / colour customisation — named palette swap, explicit per-category hex, single-series colour, heatmap ramp override, colourblind-safe set | `list_ai_repo(file_paths=["context/modules/static/chart_context_colors.md"], mode="full")` |

Triggers:
- **Grids spoke** — any cross-sectional dashboard over 8-30 entities sharing the same shape (G20 GDP per country, 12 sector PMIs, 16 FX pairs, country yield curves). Phase-space scatter plots with time-coloured trails also live in this spoke.
- **Tables spoke** — any presentation of structured data with ≥2 columns and ≥2 rows where a chart can't visualise the relationship cleanly: watchlists, term structures, P&L attribution, factor tilts, FX cross-rates, sector tapes, calendars, snapshot dashboards, attribution decompositions.
- **Colors spoke** — any user request to change / customise colours on any chart type: palette swap ("use a colourblind-safe palette"), pin a category to a hex ("make the US line red"), single-series colour ("draw it in green"), heatmap ramp override ("flip to red-blue").

---

## Tables vs Charts: which primitive

Two engines, one module. Pick by question shape, not by aesthetic preference.

| Question shape | Reach for |
|---|---|
| Time series, distribution, scatter, ranking, regime, co-movement, lead-lag | `make_chart` (this hub, §1-12) |
| 8-30 entities sharing one shape (G20 PMIs, country curves, FX cross-rates) | `make_chart` grid mode (`chart_context_grids.md`) |
| Structured rows × columns where a chart can't visualise the relationship cleanly: watchlists, term structures, P&L attribution, factor tilts, sector tapes, calendars, snapshot dashboards, theme trackers, trade-idea lists | `make_table` (`chart_context_tables.md`) |
| Single number / KPI tile | Not in altair — use echarts dashboards |

If the answer is structured tabular content the user wants to read, use `make_table` — never a markdown table, never a code-block dump, never inline prose. Fetch the tables spoke before authoring any non-trivial table (colour modes, heatmap groups, sparkline / mini-bar cells, indent / total / subtotal styling all live there).

---

## 1. `make_chart()` signature & namespace

```python
result = make_chart(
    df=df, chart_type='multi_line', mapping={...},
    title='Title',                # Required for production
    subtitle='Subtitle',          # Optional (NEVER for source attribution)
    skin='gs_clean', intent='explore',
    annotations=[...], layers=[...],
    caption='note...',            # Optional below-chart italic note
    side_left='...',              # Optional left/right narrative panels
    side_right='...',             # (str or {'text': ..., 'italic': True, ...})
    save_as='charts/name.png',    # Optional fixed path (overwrites, no timestamp)
    auto_beautify=True,           # Date format, label angle, y-domain
    x_title=None, y_title=None,   # Top-level axis-title kwargs (canonical;
    y_title_right=None,           #   equivalent to mapping[...] — see §7.1)
    x_label=None, y_label=None,   # Legacy aliases for x_title / y_title
    filename_prefix=None, filename_suffix=None,
)
```

Canvas size is engine-decided per `chart_type` — PRISM never picks a dimension. `output_dir` is local-mode only; `interactive=True` (default) auto-emits an interactive HTML companion alongside the PNG, exposed on the result via `editor_html_path` / `editor_download_url` / `editor_chart_id`.

**Auto-injected names:** `make_chart`, `make_table` (tables spoke), `profile_df` (§5), `ChartResult`/`ChartSpec`/`TableResult` (tables spoke), `check_charts_quality` (§2), composite functions (§10), all 11 annotation classes (§8).

### `ChartResult` (dataclass, NOT dict)

Access via dot notation only -- `result['png_path']` raises `TypeError`.

| Attribute | Type | Description |
|---|---|---|
| `png_path` / `download_url` | str | PNG S3 path / presigned URL |
| `editor_html_path` / `editor_download_url` | str | Interactive HTML companion S3 path / presigned URL — surface alongside the PNG when the user might want to tweak |
| `editor_chart_id` | str | Stable handle for the editor instance |
| `vegalite_json` | dict | Final Vega-Lite spec |
| `chart_type` / `skin` | str | Echoed |
| `success` / `error_message` | bool / str-None | Render succeeded + details |
| `warnings` | list | Fail-soft annotations (auto-melt, dropped annotations, beautify failures) — caller may want to surface |
| `audit_trail` | list | Informational engine decisions (auto-recovered dual-axis, auto-downsampled, alias resolution) — render-was-fine signals; do NOT surface as failures |

`CompositeResult` (from `make_Npack_*`) adds `layout`, `n_charts`, `chart_errors` (per-sub-chart `df_shape`, `error_type`, `error_message`); `editor_html_path` / `editor_download_url` work the same way for the composite PNG.

---

## 2. Quality gate (MANDATORY)

Every chart passes through `check_charts_quality()`. Fail-open: if Gemini is unavailable, all charts auto-pass. Pass composite results as single PNGs.

```python
results = [r1, r2]
qc_results = check_charts_quality(results)
for r, qc in zip(results, qc_results):
    if not r.success:                       # render itself failed -- nothing to QC
        print(f"BUILD FAIL: {r.error_message}")
        continue
    if not qc['passed']:
        print(f"QC FAIL: {r.png_path} -- {qc['reason']}")
        s3_manager.delete(r.png_path)
    else:
        print(f"PASS PNG: {r.download_url}")
```

Session folders must contain only QC-passed charts. On QC fail, `s3_manager.delete()` the PNG, then fix or remove the offending call. Saying PRISM could not generate a chart is acceptable; showing a failed one is not. **Always check `r.success` before accessing `r.png_path` / `r.download_url`** -- on render failure both are `None` and the engine never wrote a file (no orphan to delete).

---

## 3. Design defaults: compose + annotate + relate

Apply unless the user explicitly asked otherwise.

### 3.1 Default to a composite when there's more than one story

For more than one related story (regional split, level vs change, before/after, mixed types), reach for a composite BEFORE multiple standalone PNGs. **2-panel is the default composite shape for an argument** -- 1 reads as anecdote, 4+ reads as a dashboard (attention splits, through-line dilutes).

| Shape | Layout | Use case |
|---|---|---|
| **2 panels (default)** | `make_2pack_horizontal` / `_vertical` | Compare/contrast: US vs EU, level + change, scatter + supporting time series, before/after, point estimate + range |
| 1 headline + 2 supporting | `make_3pack_triangle` | One main + two supporting angles |
| 4 panels | `make_4pack_grid` | Regional/sector/scenario grid where the grid IS the point |
| 6-panel dashboard | `make_6pack_grid` | True dashboards; not for arguments |
| 8-30 entities sharing one shape | grid mode (`mapping['facet']`) | G20 GDP, 12 sector PMIs, 16 FX pairs -- fetch `chart_context_grids.md` |
| 9+ series on one canvas | aggregate/group, or `heatmap` | Too many for any panel composite |

Composite depth (`ChartSpec`, per-panel rules, patterns): §10. Grid mode (small-multiples): the spoke.

### 3.2 Annotations make charts argue

Default-include the annotation that makes the chart's point legible at-a-glance.

| Intent | Reach for |
|---|---|
| Threshold (Fed 2%, recession 0%, PMI 50) | `HLine` — drop or minimise the label; the line + a directional title carry the meaning (see §8.2) |
| Regime / shaded period | `Band` |
| Point at latest / max / min / event | `Callout` |
| Event date | `VLine` |
| Forecast / regime-change segment | `Segment` |
| Best-fit on scatter | `Trendline` (or `mapping['trendline']=True`) |
| Below-plot note | `PlotText` |

"Is it worth it?" filter + chart-type compatibility: §8. Skip annotations for clean reference plots or exploratory work.

### 3.3 Default to relationship charts in freeform analysis

When the user hands PRISM the chart-type pick ("analysis", "what's interesting"), lean toward charts that DEMONSTRATE A RELATIONSHIP. A single time series narrates what happened; a relationship chart argues what RELATES.

| Shape | Use case | Build with |
|---|---|---|
| Scatter (+ trendline) | Direct X-Y: shape (linear/log/hump), strength, outliers in one frame | `'scatter'` + `mapping['trendline']=True`. Per-group: `'scatter_multi'` + `color=...` + `mapping['trendlines']=True` |
| Dual-axis multi_line in change space | Co-movement over time. Both columns transformed to the SAME change measure (YoY %, MoM %, log-diff) BEFORE charting | `'multi_line'` + `mapping['dual_axis_series']=[...]` (§9). Change-space > levels for correlation |
| Lead-lag | Does X anticipate Y? Scatter quantifies strength; time-shifted dual-axis traces the implied path | Scatter form: `merged['x_lag'] = x.shift(N)` then `'scatter'` + `mapping['trendline']=True`. Time-shift form: shift the predictor's date column `+N` months -> dual-axis + `VLine` at "Today" (full recipe §9.6). Sweep N (1, 3, 6, 12 monthly), then `make_*pack_*` |

**Anti-pattern:** single-series `multi_line` when the question was "is anything happening?" That shape narrates; it doesn't argue.

Engine rejects scatters with < 8 distinct (x, y) coords inside the visible plot region (error mentions "distinct dot(s)") -- expand window, disaggregate, or switch chart type. Pair relationship shapes with a 2-panel composite (§3.1).

For correlation stories with disparate magnitudes (gold + WTI) or disparate levels (FCI components 30/60/10), the engine REJECTS single-y-axis `multi_line` -- pick 2-pack OR dual-axis (§9.1).

---

## 4. Authoring rules

- **Max 4 lines per `multi_line`** (5+ clutters). For >4, use a composite (§10) — yield-curve overlays with 5+ dates: drop a date or split into 2 panels.
- **`y_title` plain English; aim for ≤16 chars (engine hard-fails at 24).** Set if column is coded or wide of the visual sweet spot (`JXCHF@USECON` -> `Core CPI (YoY %)`; `Population (Millions)` (21 chars, fits but reads tight) -> `Pop. (Millions)`). Same 24-char cap applies to `x_title` and `y_title_right`. Series names (the `color` column values on `multi_line` / `timeseries`) get a separate 25-char cap (§6.1) — rename in the DataFrame before melting.
- **X column must be `'date'` for time series, as a column not just index.** `df.rename(columns={'datetime': 'date'}).reset_index()`.
- **Multi-line long format: rename FIRST, then melt.** Or use auto-melt.

  ```python
  df = df.reset_index()
  df.columns = ['date', 'Series A', 'Series B']  # Rename FIRST
  df_long = df.melt(id_vars='date', var_name='series', value_name='value')
  mapping = {'x': 'date', 'y': 'value', 'color': 'series'}
  # OR auto-melt (no `color` key):
  mapping = {'x': 'date', 'y': ['Series A', 'Series B']}
  ```

- **No source attribution in title/subtitle.** Title makes the argument; sources in PRISM metadata. Good: `title='Inflation Has Peaked'`, `subtitle='Core CPI decelerating 6 months'`. Bad: `title='US CPI Data'`, `subtitle='Source: Haver'`.
- **Clean before charting.** `pd.to_numeric(errors='coerce')` then `dropna(subset=['date', 'value'])`. Max 12 color cats, 16 facet cats. >5,000 rows auto-downsample to ~2,000 (warning in `result.warnings`).
- **Never plot `np.zeros()` placeholder.** If data missing, skip the panel or add text annotation -- never a misleading flat line at 0.
- **Title/subtitle: 2-line cap, auto-wrap.** Engine reports the exact char limit on rejection; explicit `\n` honored as manual line break (counts toward cap). On rejection, shorten or move detail into subtitle (more chars per line).

---

## 5. `profile_df`: pre-charting analysis

Use before `make_chart()` to verify columns, dtypes, missingness, cardinality, date coverage. Returns a `DataProfile` dataclass with fields: `columns`, `dtypes`, `shape`, `temporal_columns`, `numeric_columns`, `categorical_columns`, `cardinality`, `missing_pct`, `date_range`, `numeric_stats`. Call `.to_dict()` to serialise.

```python
profile = profile_df(df)
print(profile.shape)           # (rows, cols)
print(profile.cardinality)     # {'series': 4, 'date': 252, ...}
print(profile.missing_pct)     # {'value': 0.0, 'series': 0.0}
print(profile.date_range)      # {'date': {'min': '...', 'max': '...'}}
print(profile.numeric_stats)   # {'value': {'mean':..., 'std':..., ...}}
```

---

## 6. Chart types

### 6.1 Type catalog

| Type | Use case | Required mapping |
|---|---|---|
| `multi_line` | Time series, curve evolution | `x`, `y`, `color` (opt) |
| `scatter` | X-Y relationships | `x`, `y` |
| `scatter_multi` | Grouped scatter + trendlines | `x`, `y`, `color` |
| `bar` | Category comparisons (stacked/grouped via `stack`) | `x` (cat), `y`, `color` (opt) |
| `bar_horizontal` | Horizontal bars | `x`, `y` (cat) |
| `heatmap` | Matrices | `x`, `y`, `value` (NOT `'color'`) |
| `histogram` | Distributions | `x` |
| `boxplot` | Distribution comparison | `x` (cat), `y` |
| `area` | Stacked time series | `x`, `y`, `color` |
| `donut` | Part-to-whole | `theta`, `color` |
| `bullet` | Range dot / percentile | `y` (cat), `x`, `x_low`, `x_high` |
| `waterfall` | Additive decomposition | `x` (cat), `y`, `type` (opt) |

`timeseries` is accepted as an alias inside the `multi_line` builder. `multi_line` auto-detects non-datetime x-axis -> ordinal mode; tenor values (`1M`, `2Y`, `10Y`) auto-sort by maturity.

**`multi_line` / `timeseries` default to end-of-line labels, not a color legend.** Each series's name is painted at the line's right end in the line's own colour (FT/Bloomberg house style); the colour legend is suppressed. This removes the lookup-tax between hex swatch and series name. The engine auto-injects `LastValueLabel()` on every multi-line single panel and every multi-line composite cell. **Series names must be <= 25 characters** -- long names raise `LvlSeriesNameTooLongError` (mirrors `YAxisLabelTooLongError`). Rename the series in the DataFrame before `make_chart()` (`'United States Equities Index 500'` -> `'S&P 500'`). Customise the typography by passing your own `LastValueLabel(dx=..., font_size=..., font_weight=...)` -- your explicit annotation wins. On dual-axis charts LVL is automatically suppressed and the normal colour legend renders (see §9.4).

### 6.2 Bar family

`stack=True` (default with color) for parts-of-whole / additive; `stack=False` for grouped side-by-side / benchmarking. Don't add sign-keyed color (`'Positive'`/`'Negative'`) -- bar position vs zero conveys sign. Color encodes a conceptual dimension.

```python
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product'}                  # stacked
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product', 'stack': False}  # grouped
```

Grouped uses Altair 4.x column faceting; engine clamps facet width to cell budget. Below ~3px per bar (~60+ x-categories in compact 4_grid cell, ~200+ standalone), engine raises `GROUPED BAR CELL-BUDGET ERROR` -- switch to `stack=True`, reduce categories, or render standalone. `bar_horizontal` enforces same on height.

| Bar mode | Annotation support |
|---|---|
| Single-series | `HLine`, `VLine`, `Band`, `Arrow`, `PointLabel` |
| Stacked | `HLine` clamped against stacked totals (use when threshold applies to total) |
| `bar_horizontal` | `HLine` renders as vertical threshold |
| Grouped (`stack=False`) | Annotations DO NOT render. Use title/subtitle or switch to `stack=True` |

For datetime x prefer `multi_line`/`area`. If using `bar` + datetime, engine handles temporal encoding; for period bars convert to string labels (`"Q1 2025"`) for nominal encoding.

### 6.3 Heatmap

`value` column renders as cell color. Two recipes, dispatched by dtype:

| `value` dtype | Color scale | Cell label | Cap |
|---|---|---|---|
| numeric | quantitative; sequential, OR diverging-at-zero when min<0<max (correlation matrix, P&L matrix) | `_smart_number_format` (magnitude-aware) | grid size warned >500 cells |
| categorical / string | nominal sequential ramp indexed by sort order | the bin label itself | <=12 distinct bins (engine rejects above) |

For the categorical recipe (continuous data binned into labelled buckets), bin via `pd.cut()` or `np.digitize()` and pass the bin column as `mapping['value']`. Override sort order with `mapping['value_sort']=[...]`.

```python
df['prob_bucket'] = pd.cut(df['Probability'], bins=10,
    labels=[f'{i*10}-{(i+1)*10}%' for i in range(10)])
mapping = {'x': 'meeting_date', 'y': 'fed_funds_rate', 'value': 'prob_bucket'}
```

### 6.4 Bullet chart

Current values within historical ranges; marker color encodes severity via z-score or percentile. Required: `y` (cat), `x` (current), `x_low`, `x_high`. Optional: `color_by` (severity), `label` (label column).

```python
mapping = {
    'y': 'variable', 'x': 'current_value',
    'x_low': 'range_low', 'x_high': 'range_high',
    'color_by': 'z_score', 'label': 'percentile',
}
```

### 6.5 Waterfall chart

Additive decomposition (CPI/GDP, P&L, FCI impulse): bars float, each starts where the previous ended. `type` optional -- if absent, first/last rows are totals, intermediates signed by value. Color: positive = green (`#2EB857`), negative = red (`#DC143C`), totals = skin primary. Engine warns if intermediates don't sum to `(last - first)` within 15%.

```python
df = pd.DataFrame({
    'component': ['Start', 'Energy', 'Food', 'Core Goods', 'Core Services', 'End'],
    'contribution': [3.0, -0.4, -0.2, 0.1, 0.6, 3.1],
    'type': ['total', 'negative', 'negative', 'positive', 'positive', 'total'],
})
mapping = {'x': 'component', 'y': 'contribution', 'type': 'type', 'y_title': 'CPI YoY (%)'}
```

### 6.6 Haver frequency hygiene

Haver stores many monthly/quarterly series at business-daily granularity (same value repeated ~22 days). Symptom: stair-step lines. Fix: resample to native frequency BEFORE charting. Merging mixed-frequency creates NaN gaps -- resample to lowest common frequency before `concat` / `merge`.

| Series type | Resample | Example |
|---|---|---|
| Point-in-time / stock | `.last()` | Housing starts, unemployment rate |
| Flow / cumulative | `.mean()` or `.sum()` | Initial claims (mean), retail sales (sum) |
| Rate / percentage | `.last()` or `.mean()` | CPI YoY, mortgage rate |

---

## 7. Mapping reference

### 7.1 Axis-title kwargs

`x_title` / `y_title` / `y_title_right` are accepted both INSIDE `mapping={}` and as TOP-LEVEL kwargs on `make_chart()` and `ChartSpec(...)`. The engine routes the top-level form into `mapping` automatically; `mapping[...]` wins when both are set. `x_label` / `y_label` are legacy aliases for the top-level form.

```python
make_chart(df=df, chart_type='multi_line',
           mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'})
make_chart(df=df, chart_type='multi_line',
           mapping={'x': 'date', 'y': 'value'}, y_title='Yield (%)')
ChartSpec(df=df, chart_type='multi_line',
          mapping={'x': 'date', 'y': 'value'}, y_title='Yield (%)')
```

Composite-level `title=`/`subtitle=` describe the COMPOSITE; per-panel axis titles set on each panel's `ChartSpec` (top-level OR mapping; never on the composite wrapper).

### 7.2 Basic patterns

```python
# basic
mapping = {'x': 'date', 'y': 'value', 'y_title': 'GDP Growth (%)'}
# multi-series (long format)
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}
# auto-melt (wide)
mapping = {'x': 'date', 'y': ['col_a', 'col_b']}
# profile/curve
mapping = {'x': 'tenor', 'y': 'yield_pct', 'color': 'curve_date'}
# scatter + trendlines
mapping = {'x': 'x_var', 'y': 'y_var', 'color': 'group', 'trendlines': True}
# dual axis (§9)
mapping = {'x': 'date', 'y': 'value', 'color': 'series',
           'dual_axis_series': ['Right Axis Series'],
           'y_title': 'Left Label', 'y_title_right': 'Right Label'}
```

### 7.3 All mapping keys

| Key | Type | Description |
|---|---|---|
| `x` | str | X-axis column |
| `y` | str / list | Y-axis column(s); list triggers auto-melt |
| `color` | str | Grouping column for multi-series |
| `y_title` / `y_title_right` / `x_title` | str | Axis labels (≤24 chars hard cap, aim ≤16); right Y dual-axis only |
| `x_sort` / `y_sort` | list | Explicit ordinal sort (x) / heatmap y-axis sort |
| `x_type` | str | Force `'ordinal'` on datetime |
| `dual_axis_series` / `invert_right_axis` | list / bool | Right-axis series / flip right axis (higher = bottom) |
| `dual_axis_config` | dict | Pin dual-axis y domains: `{'y_domain_left': [lo, hi], 'y_domain_right': [lo, hi]}` |
| `legend` | bool | Show / hide legend (auto-decides by default) |
| `trendline` / `trendlines` | bool | Overall (scatter) / per-group (scatter_multi) |
| `stack` | bool | Bar+color: `True` stacked (default), `False` grouped |
| `strokeDash` / `strokeDashScale` / `strokeDashLegend` | str/dict/bool | Line-style col / `{domain, range}` / show legend (default `False`) |
| `value` / `theta` | str | Heatmap cell value / donut magnitude |
| `x_low` / `x_high` / `color_by` / `label` | str | Bullet: range bounds / severity / label |
| `type` | str | Waterfall bar type (`total`/`positive`/`negative`) |
| `bins` / `maxbins` | int | Histogram bin count (aliases of each other) |
| `bin_extent` | list | Histogram bin range override `[lo, hi]` |
| `extent` | float | Boxplot whisker IQR multiplier (default `1.5`) |
| `scale_type` | str | `'linear'` / `'log'` override on auto log-scale detection (multi_line / timeseries) |
| `orientation` | str | `'vertical'` opt-out from `bar`'s auto-flip to `bar_horizontal` on long category labels |
| `color_sort` (alias `legend_sort`) | list | Explicit category order in legend (multi-series, bar, area) |
| `value_sort` | list | Heatmap value-driven sort |
| `facet_order` | list | Explicit panel-id order in grid mode (overrides first-appearance) |

### 7.4 strokeDash: per-series line styles

`multi_line` only (single y-axis; NOT dual-axis or profile/curve). Use when lines share color but differ in style (actuals vs estimates) -- keep `color` for the entity, `strokeDash` for the type. Auto-scale: 2 cats -> solid + dashed; 3 -> adds dotted; 4+ Altair auto. Legend suppressed by default; `strokeDashLegend: True` to show.

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'company',
    'strokeDash': 'type',                    # 'Actual' vs 'Estimate'
    'strokeDashScale': {'domain': ['Actual', 'Forecast'], 'range': [[1, 0], [8, 3]]},
    'y_title': 'Capex ($B)',
}
```

---

## 8. Annotations & layers

### 8.1 The "is this annotation worth it?" filter

Annotations must be EXTREMELY useful and core to the chart's argument -- otherwise omit. Default to zero; add only when it sharpens the narrative. Test: "would a PM learn anything new from this?" If no, omit. Avoid `PointLabel` (clutters), generic threshold lines, text stating the obvious.

```python
T = pd.Timestamp
annotations = [
    HLine(y=2.0),                                                # threshold; no label per §8.2
    VLine(x=T('2022-03'), label='Hike start'),
    Segment(x1=T('2015-01'), x2=T('2019-12'), y1=2.0, y2=2.0, label='2015-2019 avg'),
    Band(x1=T('2020-03'), x2=T('2020-06'), label='Recession', opacity=0.3),
    Arrow(x1=T('2020-04'), y1=5, x2=T('2021-03'), y2=8, label='Recovery'),
    PointHighlight(x=T('2022-06'), y=9.1, size=120),
    Callout(x=T('2022-06'), y=9.1, label='Peak 9.1%', background='halo'),
    LastValueLabel(dx=10, font_weight='bold'),  # customise the default LVL; bare LastValueLabel() is redundant on multi_line
]
```

### 8.2 Anti-patterns (do NOT)

| Anti-pattern | Why trivial / engine behaviour |
|---|---|
| `Segment(x1=v, y1=v, x2=w, y2=w)` "y=x / 45-deg / identity" on scatter | Macro/rates axes are different units (bp vs %, $ vs index pts) -- y=x has no analytical meaning AND endpoints stretch frame. Engine drops silently on `scatter`/`scatter_multi`. Use `Trendline` (or `mapping['trendline']=True`) |
| Any annotation outside the visible plot domain (`Band` edge above data; `Segment`/`Arrow` endpoint off-data; `PointLabel`/`PointHighlight`/`Callout` off-data coord) | Vega-Lite's shared scale expands to include the coord, stretching frame and pushing title up. Engine drops silently. Keep coords inside data; for narrative thresholds outside use title/subtitle. For "highlight above X" clamp: `Band(y1=X, y2=df['value'].max())`. `HLine` drops if y outside but doesn't stretch |
| `HLine(y=2.0, label='Fed 2% Target')` — redundant label on a known threshold | The HLine itself is fine. Drop the label (or shrink to `'2%'`) and let the title carry the directional claim ("Core PCE Still 80bp Above Target") |
| `VLine` at right edge labeled "Today"/"Now" | Right edge IS today |
| `PointLabel`/`Callout` describing slope ("rising"/"falling") | Geometry conveys this. Use title for directional claim |
| `Band` covering entire visible range labeled "Sample period" | The whole chart IS the sample |
| Round-number `HLine` on data without regime/target meaning (`HLine(y=100)` on a price chart) | Round numbers carry no info unless policy/regime/target. Fed 2%, PMI 50, recession 0% ARE regime / target lines and welcome (§3.2) |
| Multiple annotations crowding < 6 months of x-axis | Pick most important; demote rest to subtitle |

**Principle:** annotate regime changes, policy shifts, event dates, structural breaks, threshold crossings that change interpretation. Never decorate. If you cannot finish "this annotation shows [X], which the reader would not otherwise see", omit.

### 8.3 Annotation parameter reference

All inherit `label`, `label_color`, `color`, `axis` (where applicable). Use `style=` or `stroke_dash=` for dash patterns -- no `dash` / `line_style` / `linestyle` / `line_type` exists.

| Annotation | Key parameters & notes |
|---|---|
| `VLine` | `x`, `style` (`'solid'`/`'dashed'`/`'dotted'`), `stroke_dash`, `stroke_width`. Full y-axis rule; auto-staggers labels when multiple cluster. Default color `"#666666"` |
| `HLine` | `y`, `axis` (`'left'`/`'right'`, default `'left'`; right only for dual), `style`, `stroke_dash`, `stroke_width`. Full x-axis. Default `stroke_dash=[4,4]` |
| `Segment` | `x1`/`x2`, `y1`/`y2`, `style`, `stroke_dash`, `stroke_width`, `label_position` (`'start'`/`'middle'`/`'end'`), `label_offset_x`/`_y`. Finite line (NOT full-axis). Patterns: `y1==y2` windowed avg, `x1==x2` finite event, diagonal connector |
| `Band` | `x1`/`x2` (vertical) OR `y1`/`y2` (horizontal), `opacity` (default `0.3`), `axis` (horizontal only) |
| `Arrow` | `x1`/`y1`, `x2`/`y2`, `stroke_width`, `stroke_dash`, `head_size`, `head_type` (`'triangle'`/`'none'`), `label_position` |
| `PointLabel` | `x`, `y`, `dx`/`dy` (pixel offsets), `font_size`, `align`. Plain floating text. Use sparingly |
| `PointHighlight` | `x`, `y`, `size` (default `100`), `opacity`, `shape` (`'circle'`/`'square'`/`'diamond'`/`'triangle'`/`'cross'`/`'stroke'`), `filled`, `stroke_color`, `stroke_width`. Default color `"#C00000"`. Often combined with Callout/PointLabel |
| `Callout` | `x`, `y`, `background` (`'halo'`/`'box'`/`'none'`), `background_color` (default `'#FFFFFF'`), `halo_width`, `box_padding_x`/`_y`, `box_opacity`, `box_corner_radius`, `dx`/`dy`, `font_size`, `font_weight`, `align`. Default `'halo'` keeps the label legible against chart lines and dense data. `dx` 0-60; `abs(dx)>80` risks off-canvas (warns) |
| `LastValueLabel` | `dx`, `font_size` (default 15), `font_weight`. FT/Bloomberg end-of-line labels for `multi_line` / `timeseries` -- the series identity only; no numeric value is rendered. **Auto-injected by default** (§6.1) on every multi-line single panel and every multi-line composite cell; pass an explicit instance to customise typography (e.g. `LastValueLabel(dx=10, font_weight='bold')`). Auto-derives series names from the color column. `label` ignored on multi-series; for single-series overrides the y-field name. Endpoint-pixel collisions auto-stagger vertically. **Series names > 25 chars raise `LvlSeriesNameTooLongError`** -- rename in the DataFrame. Suppressed on dual-axis (§9.4). Text-only — no endpoint dot |
| `Trendline` | `method` (`'linear'`/`'exp'`/`'log'`/`'pow'`/`'poly'`/`'quad'`), `stroke_width`, `stroke_dash`. Regression overlay on scatter |
| `PlotText` | `text`, `position` (`'auto'` / `'left'` / `'right'` / `'bottom'`; `'auto'` routes to right → bottom → left depending on what's already populated; `'bottom'` renders in the caption band; `'left'` / `'right'` render in the side narrative panels), `font_size`, `italic`, `color`, `align`, `width_pct`. **`text` MUST be ≤8 words** (one-line takeaway; engine hard-caps at 10 with a 2-word buffer). For longer prose pass `make_chart(caption=...)` / `side_left=...` / `side_right=...` directly (no word cap). Explicit `caption=` / `side_*=` wins against PlotText on the same slot (PlotText reroutes; warning logged). Inside-plot anchor values were removed in the 2026-05-10 outside-only rewire and now raise `ValidationError` with a migration hint |

### 8.4 Chart-type compatibility

Rule-style annotations (`HLine`, `VLine`, `Band`, `Callout`, `PointLabel`, `PointHighlight`) are silently dropped on non-Cartesian chart types (`donut`, `pie`, `bullet`) -- use `title`/`subtitle` instead. `LastValueLabel` only on `multi_line`/`area`; `Trendline` only on scatter. Bar-chart compatibility: see §6.2.

### 8.5 Layers

Stackable overlays applied AFTER the base chart. Use `annotations=[...]` for VLine/HLine/Band/Arrow; `layers=[...]` only for regression / threshold rule / secondary point cloud.

```python
layers = [
    {'type': 'regression', 'x': 'x_var', 'y': 'y_var', 'method': 'linear'},
    {'type': 'rule', 'y': 2.0, 'color': '#FF0000', 'stroke_dash': [4, 4]},
    {'type': 'point', 'x': 'x_var', 'y': 'y_var', 'data': highlight_df, 'size': 200},
]
```

---

## 9. Dual-axis charts

### 9.1 When to use dual-axis

Two series belong together but in very different scales -- equity vs ISM, 2s10s vs WTI, mortgage rates vs starts. Eye lands on co-movement; two axis labels make scale separation explicit. Always declare with explicit long format -- `y: [list]` (auto-melt) is incompatible with `dual_axis_series`.

```python
df_long = df.melt(id_vars=['date'], var_name='series', value_name='value')
result = make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value', 'color': 'series',
        'dual_axis_series': ['ISM Manufacturing'],
        'y_title': 'S&P 500', 'y_title_right': 'ISM Index',
    },
    title='Equities Track Manufacturing',
)
```

**Engine y-scale gate (two complementary checks).** Multi-series single-y-axis `multi_line` / `timeseries` charts get REJECTED when either fires:

| Failure | Trigger | Error prefix | Canonical example |
|---|---|---|---|
| **Flatness** | any single series's data span < 10% of visible y-axis | `Y-AXIS SCALE MISMATCH` | gold ($2000) + WTI ($70) -- WTI ~2% of span; equity index + 2Y yield |
| **Level disparity** | every series has visible variation, but gap between two series's means > 3x the largest individual span | `Y-AXIS LEVEL DISPARITY` | corporate saving (~2.5%) vs investment (~9.9%) of GDP -- each spans ~0.8 pp, gap ~7.4 |

**2-series cases auto-recover.** When exactly two series trigger either gate, the engine routes the smaller-|mean| series to a right axis (`dual_axis_series=[smallest]` + `y_title_right=<smallest>`), re-renders, and emits an `AUTO-RECOVERED:` entry on `result.audit_trail` (NOT `result.warnings` — chart is fine; do not surface as a failure; see §1.1). PRISM doesn't have to do anything; override by setting `dual_axis_series` explicitly or switching shape (`make_2pack_*`).

**3+ series cases stay rejected.** The choice between the four reshape options below is editorial -- the engine refuses to silently transform 3+ series. Pick one:

| Fix | Best when |
|---|---|
| **2-panel composite** (`make_2pack_horizontal` / `_vertical`) | Each panel gets its own y-axis. Canonical for 2 series; for 3+ split into a 2-panel where each panel's content shares a scale |
| **Dual-axis** -- `mapping['dual_axis_series']=['<name>']` + `mapping['y_title_right']='...'` | 2-3 series, argument is co-movement of differently-scaled/-levelled shapes |
| **Normalize** -- z-score, rebase-to-100, or pct-change every series before plotting | 3+ series; loses absolute level but preserves co-movement |
| **Small-multiples / facet** -- `mapping['facet']='<color_col>'` (drop `color`) | 3+ series with their own y-axis per panel; argument is the SHAPE of each component, not co-movement. See `chart_context_grids.md` |

The error message names the offending series and provides the exact `dual_axis_series=[...]` / `facet=...` payload to drop in.

### 9.2 Series-name discipline

`dual_axis_series` lists names that exactly match values in the `color` column. Cleanest pattern: define LEFT/RIGHT constants, use them as DataFrame values AND title source -- keeps the four places these names appear (DataFrame, `dual_axis_series`, left title, right title) in lockstep.

```python
LEFT_SERIES, RIGHT_SERIES = '2s10s Curve (bp)', 'WTI Crude ($/bbl)'
curve_df['series'] = LEFT_SERIES
oil_df['series'] = RIGHT_SERIES
df_long = pd.concat([curve_df, oil_df], ignore_index=True)
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': [RIGHT_SERIES],
    'y_title': '2s10s (bp)', 'y_title_right': 'WTI ($/bbl)',
}
```

Hygiene: rename DataFrame columns BEFORE melting; `.str.strip()` series columns read from CSV (trailing whitespace silently disqualifies the right-axis row); re-check `df['series'].value_counts()` after any `dropna()`.

### 9.3 Inverted right axis

`invert_right_axis: True` flips the right axis (higher = bottom). Standard rates pattern where "up = bullish" on both axes (equities up + yields down both read as risk-on). Vega-Lite uses reversed domains natively; no value negation needed.

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': ['UST 10Y'], 'invert_right_axis': True,
    'y_title': 'S&P 500', 'y_title_right': 'UST 10Y (%)',
}
```

### 9.4 Annotations against the right axis

`HLine`, `Segment`, `PointHighlight`, `Callout`, `Arrow`, `Band` (horizontal), `PointLabel` accept `axis='right'` -- pass y-values in right-axis units. `VLine` is axis-agnostic (spans both); label auto-anchors left. Out-of-domain values silently dropped. `LastValueLabel` and `Trendline` do not apply on dual-axis -- the engine strips both with a non-fatal warning and the normal color legend renders; build single-axis charts and combine via `make_2pack_vertical()` for end-of-line labels or trendlines alongside two y-scales.

```python
annotations = [
    HLine(y=4.25, axis='left', label='Fed funds upper bound'),
    HLine(y=3.50, axis='right', label='Q1 ISM trough'),
    Segment(x1=T('2022-01'), x2=T('2022-12'), y1=50, y2=50, axis='right', label='ISM expansion'),
    PointHighlight(x=T('2023-06'), y=48.5, axis='right', size=120),
    Arrow(x1=T('2023-01'), y1=46, x2=T('2023-06'), y2=48.5, axis='right', label='ISM rebound'),
    Band(y1=48, y2=52, axis='right', label='Neutral zone', opacity=0.3),
]
```

### 9.5 When to switch off dual-axis

| Intent | Better shape |
|---|---|
| Compare magnitudes side-by-side (not co-movement) | `make_2pack_vertical()` -- two stacked panels with own axes |
| 3+ series with scale problems | z-score normalize, single axis `multi_line` |
| Per-series regime annotations | one `multi_line` per series in a composite |

### 9.6 Lead-lag pattern

When the question is "does X anticipate Y?" -- ISM PMI ahead of equity returns by ~6m, jobless claims ahead of the unemployment rate by ~3m, HY spreads ahead of defaults by ~12m -- the dual-axis chart becomes a lead-lag chart by shifting the predictor's date column forward by the lead horizon. The visual: the predictor's line extends past the predicted series's last actual; past co-movement implies the predicted series's near-term direction. High-leverage shape because it both shows the relationship AND argues a forecast in one frame.

| Form | Question | Build |
|---|---|---|
| Time-shifted dual-axis | "What does X imply for Y over the next N months?" | Shift predictor `+N` months -> dual-axis + `VLine` at "Today" |
| Scatter `Y_t` vs `X_{t-N}` | "How tight is the lag-N relationship?" | `merged['x_lag'] = x.shift(N)` then `'scatter'` + `mapping['trendline']=True` |
| Combine | "Strength + path in one frame" | `make_2pack_horizontal(scatter_spec, time_shift_spec)` |

```python
predictor_shift = predictor.copy()
predictor_shift['date'] = predictor_shift['date'] + pd.DateOffset(months=6)
df_long = pd.concat([
    predicted.rename(columns={'spx_yoy_pct': 'value'}).assign(series='SPX YoY (%)'),
    predictor_shift.rename(columns={'ism': 'value'}).assign(series='ISM (lead 6m)'),
])
today = predicted['date'].max()
future_end = predictor_shift['date'].max()

make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value', 'color': 'series',
        'dual_axis_series': ['ISM (lead 6m)'],
        'y_title': 'SPX YoY (%)', 'y_title_right': 'ISM (lead 6m)',
    },
    title='ISM Leads SPX by 6 Months',
    annotations=[
        VLine(x=today, label='Today', style='dashed'),
        Band(x1=today, x2=future_end, label='Implied', opacity=0.18),
    ],
)
```

The x-axis extends naturally to the predictor's last shifted date (Vega-Lite's domain union). Annotations placed inside the future zone render correctly because the predictor's data fills it -- the off-data-stretches-frame anti-pattern (§8.2) does NOT apply here.

**`VLine` at "Today" is the canonical demarcation; `Band` over the future zone is an optional second hint.** The predictor's line crosses into the demarcated zone; the predicted series stops at "Today". For a single implied-target callout, add one of:

```python
Arrow(x1=today, y1=last_actual, x2=future_end, y2=implied_target, label='Implied')
PointHighlight(x=future_end, y=implied_target, axis='left', size=140)
Callout(x=future_end, y=implied_target, axis='left', label=f'Implied: {implied_target:+.1f}%')
```

`implied_target` comes from the predictor's calibration (e.g. linear fit of predicted on lagged predictor); compute it before charting -- the engine does not derive it.

| Don't | Why |
|---|---|
| `strokeDash` on the predicted series to switch from solid (past) to dashed (implied future) on dual-axis | Silently dropped on dual-axis (§9.4). `VLine` + `Band` on the LEFT axis is cleaner anyway and works |
| `layers=[{'type':'point', 'data': future_df, ...}]` for forecast dots on a dual-axis chart | Custom-data point layers don't pin reliably to either axis on dual-axis; the dots disappear. Use `Arrow` / `PointHighlight` / `Callout` for the implied target instead |
| Single-axis `multi_line` on disparate scales without z-score | Engine y-scale gate rejects (§9.1). Dual-axis is the canonical container for lead-lag |
| Stacked `make_2pack_vertical` of predictor + predicted | Loses the visual co-movement that's the whole point. Reserve composites for lead-lag + its scatter quantification |

---

## 10. Composite layouts

### 10.1 When to compose

Composites are almost always better than individuals for related data (shared x-axis, y-concept, or comparison dimension). Use individuals only for unrelated topics. For 8-30 entities sharing the same shape, use grid mode (`mapping['facet']`, see Spokes index) instead of `make_*pack_*`.

| Series count | Approach |
|---|---|
| 2-4 | Single `multi_line` (ideal) |
| 5-6 | `make_2pack_horizontal()`, 2-3 lines each |
| 7-8 | `make_4pack_grid()`, 2 lines each |
| 9+ | Aggregate / group, or `heatmap` |

### 10.2 ChartSpec & layout functions

```python
spec = ChartSpec(df=df, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'},
    title='Title', subtitle='Subtitle',
    annotations=[...], layers=[...])
```

Per-panel axis titles (`y_title`, `y_title_right`, `x_title`) work either INSIDE each `ChartSpec.mapping` OR as top-level `ChartSpec(...)` kwargs (engine routes top-level into mapping; see §7.1). Composite-level `title=`/`subtitle=` describe the COMPOSITE.

| Function | Layout | Args |
|---|---|---|
| `make_2pack_horizontal(c1, c2, ...)` | Side-by-side | 2 ChartSpecs |
| `make_2pack_vertical(top, bottom, ...)` | Stacked | 2 ChartSpecs |
| `make_3pack_triangle(top, bl, br, ...)` | 1 top + 2 bottom | 3 ChartSpecs |
| `make_4pack_grid(tl, tr, bl, br, ...)` | 2x2 | 4 ChartSpecs |
| `make_6pack_grid(r1l, r1r, r2l, r2r, r3l, r3r, ...)` | 3x2 | 6 ChartSpecs (also accepts `specs=[c1..c6]`) |

All accept kwargs (`title`, `subtitle`, `caption`, `side_left`, `side_right`, `save_as`, `spacing`, `filename_prefix`, `filename_suffix`) and return `CompositeResult` (same fields as `ChartResult` plus `chart_errors`). `caption` sits below the entire pack; `side_left` / `side_right` flank the whole pack — same shape as `make_chart` (str or `{'text': ..., 'italic': True, ...}` dict). Sub-chart-level text panels live on each `ChartSpec` instead.

### 10.3 Composite rules

- ChartSpec args positional, metadata keyword-only (never `top=spec_a`).
- `save_as` works on all chart functions (`{session_path}/{save_as}`, overwrites, no timestamp).
- QC the composite PNG, not sub-specs: `check_charts_quality([composite_result])`.
- "Completely empty" QC fail usually means date still in index, y column all-NaN, or DataFrame empty after filtering.
- Color/x/y scales resolve independently per sub-chart.
- Up to N-1 sub-charts can fail; survivors render. Failures land in `result.chart_errors`.

### 10.4 Common patterns

| Situation | Layout |
|---|---|
| US vs EU inflation | `make_2pack_horizontal` (same y-concept, different region) |
| Level + decomposition (rates path + 2s10s) | `make_2pack_vertical` |
| 4 regional PMIs | `make_4pack_grid` (each panel a region) |
| Headline + 2 supporting | `make_3pack_triangle` |
| Sector dashboard (6 panels) | `make_6pack_grid` |
| 8-30 entities (G20, sectors, FX) | grid mode via `mapping['facet']` -- fetch `chart_context_grids.md` |

`make_*pack_*` is for ARGUMENTS (compare/contrast 2-6 specific panels). For cross-sectional dashboards over many entities sharing the same shape (one chart per country / sector / FX pair), use grid mode -- trigger with `mapping['facet']='<col>'` and fetch the spoke for the full surface.

---

## 11. Chart time horizon

| Frequency | Default | Horizon class | Use case |
|---|---|---|---|
| Quarterly / Monthly | 10 years | Medium | Cyclical patterns, regime comparisons -- default |
| Weekly | 5 years | -- | Trend + cycle (also YoY series, to show cycle) |
| Daily | 2-3 years | Short | Recent acceleration, event reactions |
| Intraday | 5 trading days | Very Short | Event reaction window, data releases |

Override rules: "highest since 2008" -> chart MUST include 2008. Pre-pandemic -> start >= 2015. Percentile claims require a full percentile window. Don't show 1-2y of monthly data (hides cycle); don't show 30+y of daily (noise); don't use different ranges for charts meant to be compared. For structural shifts ("not seen since X"), use Long (20-50y) regardless of frequency.

---

## 12. Failure transparency

Never silently substitute a different layout or rationalize a substitution. If a requested chart shape isn't feasible, tell the user and offer alternatives. Max 2 retries per chart concept; after 2 failures, deliver the best version with a note or ask the user about alternatives.
