# Altair Charts (`make_chart`)

- **Module:** `chart_context`
- **Audience:** PRISM (all interfaces, all workflows), developers
- **Tier:** 2 (on-demand)
- **Scope:** All static-PNG chart authoring in PRISM (chat / email / report flows). Composites (n-pack helpers) ship in this same module. Interactive HTML dashboards use the separate `dashboards` module (echarts).

`make_chart()` and the composite/annotation/profile helpers are auto-injected
into `execute_analysis_script()`. Raw matplotlib is blocked. Do NOT import
chart functions.

---

## Catalog index

Every named primitive PRISM picks between, with a pointer to the section that carries the per-primitive spec.

| Primitive | Names | Where |
|---|---|---|
| Chart types (12) | `multi_line`, `scatter`, `scatter_multi`, `bar`, `bar_horizontal`, `heatmap`, `histogram`, `boxplot`, `area`, `donut`, `bullet`, `waterfall` | §6 |
| Mapping keys (~20) | `x`, `y`, `color`, `y_title`, `y_title_right`, `x_title`, `x_sort`, `y_sort`, `x_type`, `dual_axis_series`, `invert_right_axis`, `trendline`, `trendlines`, `stack`, `strokeDash`, `strokeDashScale`, `strokeDashLegend`, `value`, `theta`, `x_low`, `x_high`, `color_by`, `label`, `type` | §7 |
| Annotation classes (11) | `VLine`, `HLine`, `Segment`, `Band`, `Arrow`, `PointLabel`, `PointHighlight`, `Callout`, `LastValueLabel`, `Trendline`, `PlotText` | §8 |
| Composite functions (5) | `make_2pack_horizontal`, `make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid` | §10 |
| Dimension presets (6) | `wide`, `square`, `tall`, `compact`, `presentation`, `thumbnail` | §12 |
| Skin (1, only published) | `gs_clean` | §1 (signature) |
| Intent values (3) | `'explore'`, `'publish'`, `'monitor'` | §1 (signature) |
| Layer types (3) | `regression`, `rule`, `point` | §8.5 |
| Chart Center themes (5) | `gs_clean`, `bridgewater`, `minimal`, `dark`, `print` | §11 |
| Chart Center palettes (14) | `gs_primary`, `bridgewater`, `mono_blue`, `mono_grey`, `vivid`, `tableau`, `okabe_ito`, `viridis`, `blues`, `reds`, `greens`, `gs_diverging`, `redblue`, `spectral` | §11 |

---

## 1. Auto-injected namespace

| Function / Class | Purpose |
|------------------|---------|
| `make_chart()` | Build a single chart |
| `profile_df()` | Analyze a DataFrame pre-charting |
| `ChartResult` / `ChartSpec` | `make_chart()` return type / composite sub-chart spec |
| `check_charts_quality()` | MANDATORY post-chart QC gate |
| `make_2pack_horizontal/vertical()`, `make_3pack_triangle()`, `make_4pack_grid()`, `make_6pack_grid()` | Composite layouts (2-h, 2-v, 1+2, 2x2, 3x2) |
| `VLine`, `HLine`, `Segment`, `Band`, `Arrow` | Line/region annotations |
| `PointLabel`, `PointHighlight`, `Callout` | Point/text annotations |
| `LastValueLabel`, `Trendline`, `PlotText` | Series-aware / in-plot text annotations |

`s3_manager`, `session_path`, and `user_id` are auto-injected at call
time -- never pass them explicitly.

### `make_chart()` signature

```python
result = make_chart(
    df=df, chart_type='multi_line', mapping={...},
    title='Title',                # Required for production charts
    subtitle='Subtitle',          # Optional (NEVER for source attribution)
    skin='gs_clean',              # Only published skin
    intent='explore',             # 'explore' | 'publish' | 'monitor'
    dimensions='wide',            # See §12 Dimensions
    annotations=[...], layers=[...],  # Optional; layers = regression / rule / point
    save_as='charts/name.png',    # Optional fixed path (overwrites, no timestamp)
    auto_beautify=True,           # Date format, label angle, y-domain (default True)
    x_label=None, y_label=None,   # Aliases for mapping['x_title' / 'y_title']
    filename_prefix=None, filename_suffix=None,  # Optional slug pre/suffix
)
```

`SESSION_PATH` and `s3_manager` are wired by the sandbox. `output_dir` is
local-mode only. `interactive=True` is reserved.

### `ChartResult` (dataclass, NOT dict)

Access via dot notation only (`result.png_path`). `result['png_path']` raises `TypeError`.

| Attribute | Type | Description |
|-----------|------|-------------|
| `png_path` / `download_url` | str | PNG S3 path / presigned URL |
| `editor_html_path` / `editor_download_url` | str | Chart Center HTML S3 path / presigned URL |
| `editor_chart_id` | str | Chart Center chart ID (sha1 of spec) |
| `vegalite_json` | dict | Final Vega-Lite spec |
| `chart_type` / `skin` | str | Echoed chart type / skin |
| `success` / `error_message` | bool / str-None | Render succeeded? + error details |
| `warnings` | list | Non-fatal warnings (auto-melt, downsample, beautify failures, ...) |

`CompositeResult` (returned by all `make_Npack_*` helpers) carries the same
PNG/editor fields plus `layout`, `n_charts`, and `chart_errors` (per-sub-chart
failures with `df_shape`, `error_type`, `error_message`).

---

## 2. Quality gate (MANDATORY)

Every chart must pass through `check_charts_quality()`. Fail-open: if
Gemini is unavailable, all charts auto-pass. Pass composite results as
single PNGs.

```python
results = [r1, r2]  # list of ChartResults
qc_results = check_charts_quality(results)
for r, qc in zip(results, qc_results):
    if not qc['passed']:
        print(f"FAIL: {r.png_path} -- {qc['reason']}")
        s3_manager.delete(r.png_path)
        if r.editor_html_path:
            s3_manager.delete(r.editor_html_path)
    elif r.success:
        print(f"PASS PNG: {r.download_url}\n  Chart Center: {r.editor_download_url}")
```

### Failed chart cleanup

Session folders must contain only QC-passed charts (failed PNGs mislead
reports, dashboards, session reloads). On QC fail, `s3_manager.delete()`
BOTH the PNG and its `editor_html_path` companion, then fix or remove the
offending `make_chart()`. Saying Prism could not generate a chart is
acceptable; showing a failed one is not.

---

## 3. Design defaults: compose + annotate + relate

Three LLM-default behaviours that distinguish a published chart from
a data dump. Apply unless the user has explicitly asked otherwise.

### 3.1 Default to a composite when there's more than one story

If the data tells more than one related story (regional split,
level vs change, before/after, mixed chart types), reach for a
composite BEFORE producing multiple standalone PNGs. Single PNG,
single QC call, per-panel scales / palettes independent. Up to
N-1 sub-charts can fail and survivors still render.

**2-panel side-by-side is the default composite shape for making
an argument.** One chart is a narrative (a single observation);
4+ panels become a dashboard (audience attention splits across
panels and the through-line dilutes). 2 panels lets the eye land
on ONE comparison: US vs EU, level vs change, before vs after,
scatter + supporting time series, lead-lag at two horizons.
Reach for the larger composites only when the topic genuinely
demands them.

| Shape | Layout | Use case |
|---|---|---|
| **2 panels (default for arguments)** | `make_2pack_horizontal` / `_vertical` | Compare / contrast: US vs EU, level + change, scatter + supporting time series, before vs after, point estimate + range |
| 1 headline + 2 supporting | `make_3pack_triangle` | One main chart with two supporting angles -- when one comparison would lose context |
| 4 panels | `make_4pack_grid` | Regional / sector / scenario grid where each panel adds an independent fact and the grid IS the point |
| 6-panel dashboard | `make_6pack_grid` | True dashboards (cross-asset / cross-region monitor); not for arguments |
| 9+ series | aggregate / group, or `heatmap` | Too many for any panel-based composite |

Single charts only for genuinely unrelated topics, when the
question is about one series' trajectory, or when the user
explicitly asked for one. Composite design depth (`ChartSpec`,
per-panel mapping rules, common patterns): see §10.

### 3.2 Annotations make charts argue

A published chart almost always benefits from at least one
annotation -- a line at a threshold, a band over a regime, a callout
on the latest print, direct labels via `LastValueLabel`. Default-
include the annotation that makes the chart's point legible at-a-
glance.

| Intent | Reach for |
|---|---|
| Threshold (Fed 2%, recession 0%, PMI 50) | `HLine` |
| Regime / shaded period | `Band` |
| Point at latest / max / min / event | `Callout` |
| Direct-label series, drop the legend | `LastValueLabel` |
| Event date | `VLine` |
| Forecast / regime-change segment | `Segment` |
| Best-fit on scatter | `Trendline` (or `mapping['trendline']=True`) |
| Corner caption | `PlotText` |

Annotation specs + per-class params + the "is this annotation worth
it?" filter + chart-type compatibility: see §8.

A chart with no annotation is appropriate when the user asked for a
clean reference plot OR the purpose is exploratory (looking for
patterns rather than arguing for one). Otherwise, annotate.

### 3.3 Default to relationship charts in freeform analysis

When the user asks for "analysis", "what's interesting", or
otherwise hands PRISM the chart-type pick (no `chart_type` specified
and no shape implied by the prompt), lean toward charts that
DEMONSTRATE A RELATIONSHIP between variables. A single time series
of one variable narrates what happened; a relationship chart argues
what RELATES. The three go-to shapes:

| Shape | Use case | Reach for |
|---|---|---|
| Scatter (+ trendline) | Direct X-Y relationship: is X correlated with Y? Shows shape (linear / log / hump), strength (tight cloud vs loose), and outliers in one frame | `chart_type='scatter'` + `mapping['trendline']=True`. For per-group fits use `chart_type='scatter_multi'` + `color=...` + `mapping['trendlines']=True` |
| Dual-axis multi_line in change space | Co-movement over time: do X and Y move together? Both columns transformed to the SAME change measure (YoY %, MoM %, log-diff) BEFORE charting so magnitudes line up; dual axes preserve the per-series scale while the eye lands on co-movement | `chart_type='multi_line'` + `mapping['dual_axis_series']=[...]`. See §9 for the long-format declaration pattern. Levels-on-dual-axis is a weaker default than change-space-on-dual-axis when the question is correlation |
| Lead-lag | Does X anticipate Y? Either as scatter (`Y_t` vs `X_{t-N}`) or as dual-axis line with one series shifted on the time axis | Scatter form: `df['x_lagged'] = df['x'].shift(N)` then plot `y` vs `x_lagged`. Time-shift form: `.shift(-N)` one series and rebuild the long-format DataFrame, then dual-axis line. Sweep N (1, 3, 6, 12 periods for monthly data) when the lag is unknown -- one chart per N, then `make_*pack_*` to compose |

Anti-pattern: a single-series `multi_line` of one variable across
time when the question was "is anything happening?" That shape tells
the user what happened, not what relates. Use it only when the
question is about a single series' trajectory.

The engine rejects scatters that would render < 8 distinct (x, y)
coords inside the visible plot region (sparse scatter reads as
anecdote, not pattern). If `make_chart()` returns
`success=False, error_message=...` mentioning "distinct dot(s)
inside the visible plot area", expand the data window, disaggregate,
or switch to a chart type that suits sparse data.

Pair the relationship shape with a 2-panel composite by default
(see §3.1): scatter + supporting time series, level + change,
US + EU, lead-lag at two horizons, point estimate + range. 2 panels
is the argument sweet spot -- 1 reads as anecdote, 4+ reads as a
dashboard.

For correlation-on-time-series stories where the two series have
very different magnitudes (gold + WTI; equity + yield) or sit at
clustered-but-different levels (FCI components 30 / 60 / 10), the
engine REJECTS the single-y-axis `multi_line` rather than letting
one series flatten -- pick a 2-pack composite OR a dual-axis with
`mapping['dual_axis_series']=[...]` instead. See §9.1.

---

## 4. Authoring rules

### 4.1 Max lines per chart (soft guideline)

<= 4 lines per `multi_line` chart; 5+ lines cause clutter. For >4-series
data, use a composite (§10).

### 4.2 Y-axis labels: plain English, max 16 chars

Always set `y_title` if the column name is coded or exceeds 16 chars
(`JXCHF@USECON` -> `Core CPI (YoY %)`; `Population (Millions)` (21 chars)
-> `Pop. (Millions)`).

### 4.3 Date column requirements

X column must be named `'date'` for time series and must be a column (not
just the index): `df = df.rename(columns={'datetime': 'date'}).reset_index()`.

### 4.4 Multi-line long-format pattern (with rename discipline)

For multi-series with `color`: melt to long format AFTER renaming columns
(`reset_index()` uses the original index name; rename immediately after
reset, before any melt). Or use the auto-melt shortcut.

```python
df = df.reset_index()
df.columns = ['date', 'Series A', 'Series B']  # Rename FIRST
df_long = df.melt(id_vars='date', var_name='series', value_name='value')
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}
# OR auto-melt shortcut (no `color` key):
mapping = {'x': 'date', 'y': ['Series A', 'Series B']}
```

### 4.5 No source attribution in title/subtitle

Title/subtitle make the argument; source tracking lives in Prism metadata.
Good: `title='Inflation Has Peaked'`, `subtitle='Core CPI decelerating 6
months'`. Bad: `title='US CPI Data'`, `subtitle='Source: Haver'`.

### 4.6 Data cleaning before charting

```python
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
assert len(df) > 0, "DataFrame is empty"
```

Max 12 color categories, 16 facet categories. Time series above 5,000 rows
auto-downsample to ~2,000 (warning in `result.warnings`).

### 4.7 Never plot placeholder/zero-fill data

If data is unavailable, skip the panel (smaller composite) or add a text
annotation. Never use `np.zeros()` as fallback -- it produces misleading
flat lines at 0.

---

## 5. profile_df: pre-charting DataFrame analysis

Use before `make_chart()` to verify columns, dtypes, missingness,
cardinality, and date coverage. Returns a `DataProfile` (dataclass) with
fields: `columns`, `dtypes`, `shape`, `temporal_columns`, `numeric_columns`,
`categorical_columns`, `cardinality`, `missing_pct`, `date_range`,
`numeric_stats`. Call `profile.to_dict()` to serialise.

```python
profile = profile_df(df)
print(profile.shape)              # (rows, cols)
print(profile.cardinality)        # {'series': 4, 'date': 252, ...}
print(profile.missing_pct)        # {'value': 0.0, 'series': 0.0}
print(profile.date_range)         # {'date': {'min': '...', 'max': '...'}}
print(profile.numeric_stats)      # {'value': {'mean':..., 'std':..., ...}}
```

---

## 6. Chart types

### 6.1 Type catalog

| Type | Use Case | Required Mapping |
|------|----------|------------------|
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
| `bullet` | Range dot / percentile position | `y` (cat), `x` (val), `x_low`, `x_high` |
| `waterfall` | Additive decomposition / attribution | `x` (cat), `y`, `type` (opt) |

`timeseries` is accepted as an alias path inside the `multi_line` builder.

For `multi_line`, `multi_line` auto-detects non-datetime x-axis -> ordinal mode. Tenor-like values (`1M`, `2Y`, `10Y`) auto-sort by maturity, so curve-evolution charts (yields by tenor across snapshot dates) just work.

### 6.2 Bar chart family

#### Stacked vs grouped

`stack=True` (default with color, sums components into a total) vs
`stack=False` (side-by-side). Applies to `bar` and `bar_horizontal`.

| Data Relationship | `stack` | Example |
|-------------------|---------|---------|
| Parts of a whole / additive decomposition | `True` | Revenue by product, GDP decomposition |
| Independent comparisons / benchmarking | `False` | OLS vs LASSO coefficients, actual vs forecast |

```python
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product'}                  # stacked (default)
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product', 'stack': False}  # grouped
```

Grouped mode uses Altair 4.x column faceting internally. The engine
clamps facet width to the cell budget so a grouped bar inside an
n-pack composite stays inside its 2x2 / 3x2 cell. If per-bar pixel
width would drop below ~3 px (~60+ x-categories in a compact 4_grid
cell, ~200+ in a wide standalone cell), the engine raises a
`GROUPED BAR CELL-BUDGET ERROR` -- switch to `stack=True`, reduce
x-categories, or render the chart standalone (larger budget) instead
of inside a composite. `bar_horizontal` enforces the same on the
height axis.

#### No redundant positive/negative color coding

Do NOT add a color column encoding sign (`'Positive'`/`'Negative'`) -- the
bar's position relative to zero already conveys sign. Color should encode
a conceptual dimension (sector, region, model type).

#### Annotation compatibility

| Bar Mode | Annotation Support |
|----------|--------------------|
| Single-series | `HLine`, `VLine`, `Band`, `Arrow`, `PointLabel` work |
| Stacked (default w/ color) | `HLine` works; clamped against stacked totals |
| `bar_horizontal` | `HLine` renders as a vertical threshold |
| Grouped (`stack=False`) | Annotations DO NOT render (Altair faceting + layering incompatibility) |

For grouped bars, convey thresholds via title/subtitle, or switch to
`stack=True` if acceptable. For stacked bars, `HLine` encodes the stacked
TOTAL (use when the threshold applies to the total -- e.g. "regional
target = $100B" -- not a single component).

#### Datetime x-axes

Prefer `multi_line` or `area` for time-series. If using `bar` + datetime
x, the engine handles temporal encoding automatically; for period-based
bars, convert dates to string labels (e.g., `"Q1 2025"`) for nominal
encoding.

### 6.3 Heatmap

`value` column is rendered as cell color. `MAX_COLOR_CARDINALITY=12`
applies -- continuous numeric values MUST be binned to <=12 categories
BEFORE `make_chart()`, else `check_charts_quality` rejects and the
chart is dropped. Bin via `pd.cut()` (equal-width) or `np.digitize()`
(custom edges); set `mapping['color_scheme']` to a sequential scheme
(`'blues'`, `'viridis'`, etc.) keyed to the binned values.

```python
df['prob_bucket'] = pd.cut(
    df['Probability'], bins=10,
    labels=[f'{i*10}-{(i+1)*10}%' for i in range(10)],
)
mapping = {
    'x': 'meeting_date', 'y': 'fed_funds_rate', 'value': 'prob_bucket',
    'color_scheme': 'blues',
}
```

### 6.4 Bullet chart

Current values within historical ranges. Marker color encodes severity via
z-score or percentile.

```python
df = pd.DataFrame({
    'variable': ['2s10s', '5s30s', '10Y Spd'],
    'current_value': [38, -5, -33], 'range_low': [-20, -10, -45], 'range_high': [45, 60, -20],
    'z_score': [1.2, -1.5, 0.1], 'percentile': [85, 12, 45],
})
mapping = {
    'y': 'variable', 'x': 'current_value',
    'x_low': 'range_low', 'x_high': 'range_high',
    'color_by': 'z_score', 'label': 'percentile',
}
```

### 6.5 Waterfall chart

Additive decomposition / attribution -- bars float, each starts where the
previous ended. Use for CPI / GDP decomposition, P&L attribution, FCI
impulse, any additive breakdown. `type` is optional (if absent, first/last
rows are totals, intermediates signed by value). Color: positive = green
(`#2EB857`), negative = red (`#DC143C`), totals = skin primary. The engine
warns if intermediates do not sum to `(last - first)` within 15%.

```python
df = pd.DataFrame({
    'component': ['Start', 'Energy', 'Food', 'Core Goods', 'Core Services', 'End'],
    'contribution': [3.0, -0.4, -0.2, 0.1, 0.6, 3.1],
    'type': ['total', 'negative', 'negative', 'positive', 'positive', 'total'],
})
mapping = {'x': 'component', 'y': 'contribution', 'type': 'type', 'y_title': 'CPI YoY (%)'}
```

### 6.6 Haver frequency & mixed-frequency DataFrames

Haver stores many monthly/quarterly series at business-daily granularity
(same value repeated ~22 days, then jumps). Symptom: stair-step lines.
Fix: resample business-daily to true native frequency as the first step.
Merging series of different frequencies creates NaN gaps -- resample
everything to the lowest common frequency before `concat` / `merge`.
Comment the resampling method for auditability; never chart a DataFrame
with mixed-frequency NaN gaps.

```python
starts = starts.resample('M').last()             # Monthly
gdp = gdp.resample('Q').last()                   # Quarterly
claims_monthly = claims.resample('M').mean()     # Weekly -> Monthly
df = pd.concat([claims_monthly, nfp_monthly], axis=1).dropna()
```

| Series Type | Resample Method | Example |
|-------------|-----------------|---------|
| Point-in-time / stock | `.last()` | Housing starts, unemployment rate |
| Flow / cumulative | `.mean()` or `.sum()` | Initial claims (mean), retail sales (sum) |
| Rate / percentage | `.last()` or `.mean()` | CPI YoY, mortgage rate |

---

## 7. Mapping reference

### 7.1 Axis-title keys live INSIDE `mapping={}`

`y_title`, `y_title_right`, `x_title` are NEVER top-level kwargs on
`make_chart()` or `ChartSpec(...)` -- passing them outside `mapping={}`
raises `TypeError: __init__() got an unexpected keyword argument
'y_title'`. Composites are the same shape: `make_2pack_horizontal`,
`make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`,
`make_6pack_grid` accept composite-level `title=` / `subtitle=`, but
per-panel axis titles live inside each panel's `ChartSpec.mapping`.

```python
make_chart(df=df, chart_type='multi_line',
           mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'})

ChartSpec(df=df, chart_type='multi_line',
          mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'})

# WRONG -- raises TypeError on `y_title=`:
ChartSpec(df=df, chart_type='multi_line', y_title='Yield (%)',
          mapping={'x': 'date', 'y': 'value'})

# Composite -- composite-level title=, per-panel y_title in spec.mapping:
make_2pack_horizontal(
    spec_left, spec_right,
    title='Composite title', subtitle='Composite subtitle',
)
```

### 7.2 Basic patterns

```python
# Basic
mapping = {'x': 'date', 'y': 'value', 'y_title': 'GDP Growth (%)'}
# Multi-series (long format)
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}
# Auto-melt (wide format)
mapping = {'x': 'date', 'y': ['col_a', 'col_b']}
# Profile/curve (ordinal x auto-detected)
mapping = {'x': 'tenor', 'y': 'yield_pct', 'color': 'curve_date'}
# Scatter with trendlines
mapping = {'x': 'x_var', 'y': 'y_var', 'color': 'group', 'trendlines': True}
# Dual axis (see §9 for depth)
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': ['Right Axis Series'],
    'y_title': 'Left Label', 'y_title_right': 'Right Label',
}
```

### 7.3 All mapping keys

| Key | Type | Description |
|-----|------|-------------|
| `x` | str | X-axis column |
| `y` | str / list | Y-axis column(s); list triggers auto-melt |
| `color` | str | Grouping column for multi-series |
| `y_title` / `y_title_right` / `x_title` | str | Y-axis label (max 20 chars) / right y-axis label (dual only) / x-axis label |
| `x_sort` / `y_sort` | list | Explicit ordinal sort order (x) / heatmap y-axis sort order |
| `x_type` | str | Force `'ordinal'` on datetime columns |
| `dual_axis_series` / `invert_right_axis` | list / bool | Series names for right y-axis / flip right y-axis (higher = bottom; standard rates pattern) |
| `trendline` / `trendlines` | bool | Overall trendline (scatter) / per-group trendlines (scatter_multi) |
| `stack` | bool | Bar with color: `True` (default) = stacked, `False` = grouped |
| `strokeDash` / `strokeDashScale` / `strokeDashLegend` | str / dict / bool | Column for per-series line style / explicit `{domain: [...], range: [...]}` / show legend (default `False`) |
| `value` / `theta` | str | Value column (heatmap) / magnitude column (donut) |
| `x_low` / `x_high` / `color_by` / `label` | str | Bullet only: range bounds / severity column / label column |
| `type` | str | Bar-type column (waterfall: `total` / `positive` / `negative`) |

### 7.4 strokeDash: per-series line styles

For `multi_line` only (single y-axis); not supported on dual-axis or
profile/curve charts. Uses Altair 4.1+ `alt.StrokeDash()`. Use when lines
share the same color but differ in style (actuals vs estimates) -- keep
`color` for the entity, `strokeDash` for the type, do NOT combine them
into one series name.

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'company',
    'strokeDash': 'type',                    # 'Actual' vs 'Estimate'
    'strokeDashScale': {                     # Optional explicit scale
        'domain': ['Actual', 'Forecast'], 'range': [[1, 0], [8, 3]],
    },
    'y_title': 'Capex ($B)',
}
```

Auto-scale: 2 categories -> solid `[1,0]` + dashed `[6,4]`; 3 -> adds
dotted `[2,2]`; 4+ -> Altair auto-assigns. Legend suppressed by default
(color identifies series); set `strokeDashLegend: True` to show it.

---

## 8. Annotations & layers

### 8.1 The "is this annotation worth it?" filter

Annotations must be EXTREMELY useful, interesting, and core to the argument
the chart is making -- otherwise omit. Default to zero annotations and only
add one when it actively sharpens the narrative. The bar is high: every
annotation must reveal something the line/bar geometry alone cannot. Avoid
`PointLabel` (clutters), generic threshold lines, and text stating the obvious.

```python
T = pd.Timestamp
annotations = [
    HLine(y=2.0, label='Target', color='#00AA00'),
    VLine(x=T('2022-03'), label='Hike start', color='#003359'),
    Segment(x1=T('2015-01'), x2=T('2019-12'), y1=2.0, y2=2.0, label='2015-2019 avg'),
    Band(x1=T('2020-03'), x2=T('2020-06'), label='Recession', color='#CCCCCC', opacity=0.3),
    Arrow(x1=T('2020-04'), y1=5, x2=T('2021-03'), y2=8, label='Recovery', color='#0066CC'),
    PointHighlight(x=T('2022-06'), y=9.1, color='#C00000', size=120),
    Callout(x=T('2022-06'), y=9.1, label='Peak 9.1%', background='halo'),
    LastValueLabel(show_value=True),
]
```

### 8.2 Anti-patterns

Do NOT annotate visually obvious or universally known facts. Skip anything
the chart already conveys via geometry, axis labels, or basic reader
literacy. Test: "would a portfolio manager learn anything new from this
annotation?" If no, omit.

| Anti-Pattern | Why It's Trivial | Do Instead |
|---|---|---|
| `HLine(y=0, ...)` on any chart (with or without label) | The y-axis grid line at zero is the implicit baseline; an explicit rule on top adds nothing | Engine drops it silently, label included. Same applies to `Segment(y1=0, y2=0)` (windowed zero baseline). If zero matters narratively, call it out in the title / subtitle |
| `Segment(x1=v, y1=v, x2=w, y2=w)` "y=x / 45-degree / identity" line on a scatter | PRISM's macro / rates scatters have axes in DIFFERENT units (basis points vs %, dollars vs index points) — a `y=x` line has no analytical meaning, and the endpoints typically extend outside the data range, stretching the chart frame and creating large whitespace blocks | Engine drops it silently on `scatter` / `scatter_multi`, label included. Use `Trendline` (or `mapping['trendline']=True`) for a regression overlay, or an `HLine` at a meaningful threshold |
| Any annotation whose data coordinate falls outside the visible plot domain — `Band(y1=A, y2=B)` with one edge above the data, `Segment` / `Arrow` with an endpoint above the data, `PointLabel` / `PointHighlight` / `Callout` at an off-data coordinate | Vega-Lite's shared scale expands to include the offending coordinate, stretching the chart frame and pushing the title up to make room | Engine drops the annotation silently. Keep all annotation coordinates inside the data range; for narrative thresholds outside the data, use the title / subtitle. For full-axis horizontal lines use `HLine` (drops if `y` is outside but doesn't stretch). For "highlight a band above X" patterns, clamp the band's upper edge to the data's max — `Band(y1=X, y2=df['value'].max())` — instead of using an arbitrary upper bound |
| `HLine(y=2.0, label='Fed 2% Target')` on inflation chart | Every macro reader knows the 2% target | Use the title: "Core PCE Still 80bp Above Target" |
| `HLine(y=last_value)` to label the latest reading | `LastValueLabel` already does this | Use `LastValueLabel(show_value=True)` |
| `VLine` at the latest data point labeled "Today" / "Now" | The chart's right edge IS today | Omit |
| `PointLabel` / `Callout` describing slope ("rising", "falling", "flat") | The line's slope conveys this | Omit; use the title to make the directional claim |
| `Band` covering the entire visible range, labeled "Sample period" | The whole chart IS the sample | Omit |
| Threshold lines at round numbers (`HLine(y=50)`, `HLine(y=100)`) chosen for visual reference | Round numbers carry no information unless they are policy / regime / target levels | Omit unless the threshold itself is the story |
| Multiple annotations crowding < 6 months of x-axis | Visual clutter beats narrative clarity | Pick the single most important; demote the rest to subtitle |

**Principle:** Annotate regime changes, policy shifts, hard event dates,
structural breaks, and threshold crossings that change interpretation.
Never decorate; never restate what the geometry already says. If you
cannot finish the sentence "this annotation shows the reader [X], which
they would not otherwise see", omit it.

### 8.3 Annotation parameter reference

| Annotation | Key Parameters & Notes |
|------------|------------------------|
| `VLine` | `x`, `label`, `color` (default `"#666666"`), `style` (`'solid'`/`'dashed'`/`'dotted'`), `stroke_dash`, `stroke_width`, `label_color`. Vertical rule spanning the full y-axis. Auto-staggers labels when multiple VLines cluster together. |
| `HLine` | `y`, `axis` (`'left'`/`'right'`), `label`, `color`, `style`, `stroke_dash`, `stroke_width`, `label_color`. Spans the FULL x-axis. `axis` only for dual-axis (default `'left'`). Default `stroke_dash` is `[4,4]`. |
| `Segment` | `x1`, `x2`, `y1`, `y2`, `label`, `color`, `style`, `stroke_dash`, `stroke_width`, `axis` (`'left'`/`'right'`), `label_position` (`'start'`/`'middle'`/`'end'`), `label_offset_x`, `label_offset_y`, `label_color`. Finite line segment (NOT full-axis). Common patterns: horizontal segment (`y1==y2`) for windowed average, vertical segment (`x1==x2`) for finite event mark, diagonal for ad-hoc connector. Aliases: `x_start`/`x_end`, `y_start`/`y_end`. |
| `Band` | `x1`/`x2` (vertical) OR `y1`/`y2` (horizontal), `label`, `color`, `opacity` (default `0.3`), `axis` (`'left'`/`'right'`, horizontal bands only), `label_color`. Aliases: `x_start`/`x_end`, `y_start`/`y_end`, `start_x`/`end_x`. |
| `Arrow` | `x1`/`y1` (start), `x2`/`y2` (end), `label`, `color`, `stroke_width`, `stroke_dash`, `head_size`, `head_type` (`'triangle'`/`'none'`), `label_position` (`'start'`/`'middle'`/`'end'`), `axis` (`'left'`/`'right'`), `label_color`. Aliases: `x_start`/`x_end`, `y_start`/`y_end`. |
| `PointLabel` | `x`, `y`, `label`, `dx`, `dy` (pixel offsets), `font_size`, `align`, `axis` (`'left'`/`'right'`), `label_color`. Plain floating text. Use sparingly. |
| `PointHighlight` | `x`, `y`, `label`, `color` (default `"#C00000"`), `size` (default `100`), `opacity`, `shape` (`'circle'`/`'square'`/`'diamond'`/`'triangle'`/`'cross'`/`'stroke'`), `filled`, `stroke_color`, `stroke_width`, `axis` (`'left'`/`'right'`), `label_color`. Filled marker at a specific point. Often combined with `Callout` or `PointLabel` for a "labeled marker" effect. |
| `Callout` | `x`, `y`, `label`, `background` (`'halo'`/`'box'`/`'none'`), `background_color` (default `'#FFFFFF'`), `halo_width`, `box_padding_x`/`box_padding_y`, `box_opacity`, `box_corner_radius`, `color`, `dx`, `dy`, `font_size`, `font_weight`, `align`, `axis` (`'left'`/`'right'`), `label_color`. Text annotation with halo (text-stroke trick) or box background. Solves the "PointLabel fights gridlines" readability problem. Default `'halo'` is best for most charts. Keep `dx` in 0-60 (typical); `abs(dx) > 80` risks off-canvas labels and the engine emits a warning. |
| `LastValueLabel` | `show_value` (default `False`), `value_format` (default `None` -- auto-pick magnitude-aware decimals; or pass a Python format like `"{:+.2f}"`/`"{:.0%}"`), `show_dot` (default `True`), `dot_size`, `dot_color`, `dx`, `font_size`, `font_weight`, `include_right_axis` (default `False`), `label_color`. Direct end-of-line labels for `multi_line` charts (FT/Bloomberg style; replaces the legend). Auto-derives labels from the color column. `label` is ignored on multi-series charts; for single-series it overrides the y-field name. |
| `Trendline` | `method` (`'linear'`/`'exp'`/`'log'`/`'pow'`/`'poly'`/`'quad'`), `label`, `color`, `stroke_width`, `stroke_dash`, `label_color`. Regression overlay on scatter charts. |
| `PlotText` | `text`, `position` (default `'auto'`; or any of 9 corner / edge anchors), `padding_x`, `padding_y`, `font_size`, `color`, `italic`, `align`, `max_width_pct`. In-plot narrative anchored to a corner. `position='auto'` picks the corner that collides least with the data (scores TL / TR / BL / BR by how far the data extends into each); bar / waterfall disqualify bottom corners. `middle-*` anchors (`middle-left`/`middle-center`/`middle-right`) sit INSIDE the plot region with no auto-collision detection vs data / axes / legend; the engine warns when they're used. Prefer `'auto'` or a corner anchor. |

No `dash` / `line_style` / `linestyle` / `line_type` parameter exists --
use `style=` or `stroke_dash=`. All classes inherit `label` and
`label_color` from base `Annotation`.

### 8.4 Chart-type compatibility

Rule-style annotations (`HLine`, `VLine`, `Band`, `Callout`, `PointLabel`,
`PointHighlight`) are silently dropped on chart types without Cartesian
axes (`donut`, `pie`, `bullet`) -- use `title`/`subtitle` for context.
`LastValueLabel` and `Trendline` only apply to their native chart types
(`multi_line`/`area` and scatter respectively).

For bar-chart annotation compatibility (single-series vs stacked vs
horizontal vs grouped), see §6.2.

### 8.5 Layers

Stackable overlays applied AFTER the base chart. Use `annotations=[...]`
for VLine/HLine/Band/Arrow; `layers=[...]` only for a regression line,
threshold rule, or secondary point cloud.

```python
layers = [
    {'type': 'regression', 'x': 'x_var', 'y': 'y_var', 'method': 'linear'},
    {'type': 'rule', 'y': 2.0, 'color': '#FF0000', 'stroke_dash': [4, 4]},
    {'type': 'point', 'x': 'x_var', 'y': 'y_var', 'data': highlight_df, 'size': 200},
]
```

---

## 9. Dual-axis charts

### 9.1 When to use dual axis

When two series belong on the same chart but live in very different scales — equity index vs ISM, 2s10s curve vs WTI, mortgage rates vs starts. The reader's eye lands on co-movement; the two axis labels make scale separation explicit.

Always declare dual-axis with explicit long format. `y: [list]` (the auto-melt shortcut) is incompatible with `dual_axis_series` — long format gives the engine the per-row series labels it routes off.

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

**Engine y-scale flatness gate.** The engine REJECTS multi-series single-y-axis `multi_line` / `timeseries` charts where any series would compress below 10% of the visible y-axis span (would read as a flat horizontal rail). Canonical triggers: gold + WTI on one axis ($2000 vs $70 → WTI ~2% of span), FCI components clustered at disparate levels (e.g. 30 / 60 / 10 with small per-series variation), equity index + 2Y yield. When `make_chart()` returns `success=False` with `error_message` starting `Y-AXIS SCALE MISMATCH`, three reshape options — pick by series count and intent:

| Fix | Best when |
|---|---|
| **2-panel composite** (`make_2pack_horizontal` / `_vertical`) | 2 series with disparate magnitudes; each panel gets its own y-axis. Canonical fix for gold + WTI. |
| **Dual-axis** — route the smallest-scale series to a right axis via `mapping['dual_axis_series']=['<name>']` + `mapping['y_title_right']='...'` | 2-3 series where the argument is co-movement of differently-scaled shapes |
| **Normalize** — z-score, rebase-to-100, or pct-change every series before plotting | 3+ series; loses absolute level but preserves co-movement on one comparable scale |

The error message names the smallest-scale series and provides the exact `dual_axis_series=[...]` payload to drop in.

### 9.2 Series-name discipline

`dual_axis_series` is a list of series names that exactly match values in
the `color` column. The cleanest pattern is to define LEFT/RIGHT
constants and use them throughout — the constants double as the canonical
column-rename targets and the `y_title` / `y_title_right` source of truth,
keeping the four places these names appear (DataFrame values,
`dual_axis_series`, left title, right title) in lockstep.

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

Practical hygiene: rename DataFrame columns BEFORE melting (so the
post-melt `series` column carries the human-readable names), `.str.strip()`
any series column read from CSV (trailing whitespace silently disqualifies
the right-axis row), and re-check `df['series'].value_counts()` after any
`dropna()` so a sparse series isn't entirely filtered out before the
chart sees it.

### 9.3 Inverted right axis

`invert_right_axis: True` flips the right y-axis (higher values at the
bottom). This is the standard rates pattern where "up = bullish" on both
axes — equities up + yields down both read as risk-on. Vega-Lite uses
reversed domains natively, so no value negation is needed; axis labels
and `HLine` placement work correctly without manual sign flipping.

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': ['UST 10Y'],
    'invert_right_axis': True,
    'y_title': 'S&P 500', 'y_title_right': 'UST 10Y (%)',
}
```

### 9.4 Annotations against the right axis

`HLine`, `Segment`, `PointHighlight`, `Callout`, `Arrow`, `Band` (horizontal
form), and `PointLabel` accept an `axis` parameter (`'left'` / `'right'`,
default `'left'`). On a dual-axis chart, `axis='right'` interprets the
annotation's y values in right-axis units. `VLine` is axis-agnostic
(spans both vertically) — its label position auto-anchors to the left
range. `LastValueLabel` uses `include_right_axis=True` to opt right-axis
series into labelling.

```python
annotations = [
    HLine(y=4.25, axis='left', label='Fed funds upper bound', color='#666666'),
    HLine(y=3.50, axis='right', label='Q1 ISM trough', color='#f58518'),
    Segment(x1=T('2022-01'), x2=T('2022-12'), y1=50, y2=50,
            axis='right', label='ISM expansion threshold', color='#999999'),
    PointHighlight(x=T('2023-06'), y=48.5, axis='right',
                   color='#C00000', size=120),
    Arrow(x1=T('2023-01'), y1=46, x2=T('2023-06'), y2=48.5,
          axis='right', label='ISM rebound'),
    Band(y1=48, y2=52, axis='right', label='Neutral zone',
         color='#CCCCCC', opacity=0.3),
]
```

Annotation y values that fall outside the chosen side's domain are
silently dropped (the same out-of-range protection that applies to
single-axis charts) — pass values in the units of the side you're
targeting.

`Trendline` does not currently apply on dual-axis `multi_line` — for a
trendline-on-dual-axis story, build a single-axis chart per series and
combine via `make_2pack_vertical()`.

### 9.5 When to switch off dual axis

Dual-axis is the right shape when you want the reader's eye on co-movement.
For other intents:

| Intent | Better shape |
|---|---|
| Compare magnitudes side-by-side (not co-movement) | `make_2pack_vertical()` — two stacked panels with their own axes |
| Show many series on one canvas (3+) where dual-axis would still leave scale problems | z-score normalize all series, plot on a single axis with `multi_line` |
| Highlight regime changes per series independently | one `multi_line` per series in a composite, with per-panel annotations |

The principle: dual-axis is the densest expression when co-movement is
the point. When the comparison is "do these magnitudes agree", a stacked
composite is clearer.

---

## 10. Composite layouts

### 10.1 When to compose

Composites are almost always better than individual charts for related
data. If charts share an x-axis, y-axis concept, or comparison dimension
(US vs EU inflation, level + decomposition, 4 regional PMIs), they belong
in a composite. Use individual charts only for unrelated topics.

| Series count | Approach |
|---|---|
| 2-4 | Single `multi_line` (ideal) |
| 5-6 | `make_2pack_horizontal()`, 2-3 lines each |
| 7-8 | `make_4pack_grid()`, 2 lines each |
| 9+ | Aggregate / group series, or use `heatmap` |

### 10.2 ChartSpec & layout functions

```python
spec = ChartSpec(df=df, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'},
    title='Title', subtitle='Subtitle',
    annotations=[...], layers=[...])
```

Per-panel axis titles (`y_title`, `y_title_right`, `x_title`) live
INSIDE each `ChartSpec.mapping`, never as top-level `ChartSpec(...)`
kwargs (raises TypeError). Composite-level `title=` / `subtitle=`
describe the COMPOSITE; see §7.1.

| Function | Layout | Positional Args |
|----------|--------|-----------------|
| `make_2pack_horizontal(c1, c2, ...)` | Side-by-side | 2 ChartSpecs |
| `make_2pack_vertical(top, bottom, ...)` | Stacked | 2 ChartSpecs |
| `make_3pack_triangle(top, bl, br, ...)` | 1 top + 2 bottom | 3 ChartSpecs |
| `make_4pack_grid(tl, tr, bl, br, ...)` | 2x2 | 4 ChartSpecs |
| `make_6pack_grid(r1l, r1r, r2l, r2r, r3l, r3r, ...)` | 3x2 | 6 ChartSpecs (also accepts `specs=[c1..c6]`) |

All accept keyword args (`title`, `subtitle`, `dimension_preset`, `save_as`,
`spacing`, `filename_prefix`, `filename_suffix`) and return a
`CompositeResult` with `.png_path`, `.download_url`, `.editor_html_path`,
`.editor_download_url`, `.success`, `.error_message`, `.chart_errors`.

### 10.3 Composite rules

ChartSpec args are positional, metadata keyword-only (never `top=spec_a`).
`save_as` works on all chart functions (`{session_path}/{save_as}`,
overwrites, no timestamp). QC the composite PNG, not sub-specs:
`check_charts_quality([composite_result])`. QC "completely empty" usually
means date still in index, y column all-NaN, or DataFrame empty after
filtering. Color / x / y scales resolve independently per sub-chart (each
panel keeps its palette and axis range); up to N-1 sub-charts can fail and
survivors still render (failures land in `result.chart_errors`).

### 10.4 Common patterns

| Situation | Layout |
|---|---|
| US vs EU inflation comparison | `make_2pack_horizontal` (same y-concept, different region) |
| Level + decomposition (rates path + 2s10s spread) | `make_2pack_vertical` (related metrics, vertically associated) |
| 4 regional PMIs | `make_4pack_grid` (2x2; each panel a region) |
| Headline + 2 supporting | `make_3pack_triangle` (top wide; two narrower beneath) |
| Sector dashboard (6 panels) | `make_6pack_grid` (3x2) |

---

## 11. Prism Chart Center

### 11.1 What it provides

Every successful `make_chart()` / composite produces TWO artifacts in the
session folder: a static PNG and a self-contained interactive editor HTML
(the "Chart Center"), both on the same `ChartResult`.

- ~140 editable knobs across Dimensions, Title, Typography, Axes, Legend, Colors, Interactivity, and per-mark sections (Line / Bar / Scatter / Area / Arc / Heatmap / Box / Bullet / Waterfall). Editable title, subtitle, axis labels, legend title.
- 5 theme presets (`gs_clean`, `bridgewater`, `minimal`, `dark`, `print`); 14 color palettes -- categorical (`gs_primary`, `bridgewater`, `mono_blue`, `mono_grey`, `vivid`, `tableau`, `okabe_ito`), sequential (`viridis`, `blues`, `reds`, `greens`), diverging (`gs_diverging`, `redblue`, `spectral`).
- 12 dimension presets: 7 PRISM canonical sizes plus `report`, `dashboard`, `widescreen`, `twopack`, `fourpack`, `custom`.
- Spec sheets: named JSON bundles of styling preferences scoped to user (and optionally chart type), persisted in browser localStorage, importable / exportable as JSON.
- Export: PNG (1x / 2x / 4x), SVG, Vega-Lite JSON, Altair Python. Tabs: Chart, Data (sortable / filterable + summary stats), Code, Metadata.
- Interactivity: tooltips, crosshair, brush zoom (x / y / both), legend click toggle, per-series color overrides. Runs entirely client-side via CDN (`vega@5`, `vega-lite@5`, `vega-embed@6`); no server, no auth.

### 11.2 Styling delegation strategy (CRITICAL)

Prism should NOT iterate on chart styling. For ANY visual / aesthetic
request -- line thickness, colors, fonts, legend position, dimensions,
palette, padding, gridlines, "make it bigger" / "make the lines thicker"
-- hand the user the Chart Center link, do not regenerate. Re-run
`make_chart()` ONLY when the request changes the **data** (series / time
range / metric / filter), the **structure** (chart type, mapping,
annotations, composite layout), or the **narrative** (title, subtitle).

### 11.3 Delivering links to the end user (MANDATORY)

After EVERY successful chart, the LLM must surface BOTH links: the PNG
(renders inline) AND the Chart Center URL (for user customization).
Markdown only -- no HTML, no styling. (1) print both URLs from the script
so they reach the LLM context; (2) emit them in the narrative reply with
the actual URL strings. Composites work identically -- `CompositeResult`
carries the same `download_url` / `editor_download_url`.

```python
result = make_chart(...)
if result.success:
    print(f"PNG: {result.download_url}")
    print(f"Chart Center: {result.editor_download_url}")
```

```markdown
![Chart](<result.download_url>)

[Open in Prism Chart Center](<result.editor_download_url>) -- customize
colors, fonts, dimensions, palette, and styling. Export as PNG / SVG /
Vega-Lite JSON. Save preferences as a spec sheet.
```

The Chart Center URL is presigned (1 hour default); the underlying
`editor_html_path` is a stable S3 path inside the session folder --
re-presign via `s3_manager` if the original URL expires.

### 11.4 Session folder structure

```
sessions/{timestamp}_{slug}/
    {timestamp}_{chart_name}_{chart_type}.png
    charts/{timestamp}_{chart_name}_{chart_type}_editor.html
```

`save_as='charts/foo.png'` lands the editor companion at
`charts/foo_editor.html` (same dir, same base, no timestamp prefix).

### 11.5 Non-fatal generation

If Chart Center generation fails (vega CDN unreachable, spec hash collision,
template error), the PNG still delivers; `editor_download_url` and
`editor_html_path` are `None` and `result.warnings` carries the cause --
deliver the PNG and note Chart Center was unavailable, never silently omit.

### 11.6 Known limitations

| Feature | Status | Workaround |
|---------|--------|------------|
| Inverted right axis | Supported | `invert_right_axis: True` |
| HLine on right axis | Supported | `HLine(y=val, axis='right')` |
| Segment on right axis | Supported | `Segment(..., axis='right')` |
| `Trendline` on dual-axis multi_line | Not supported | Single-axis chart, or `make_2pack_vertical()` |
| >2 y-axes | Not supported | Composite layouts |
| Candlestick | Not supported | Plotly (`px`) -- no GS styling |
| Sankey / Treemap | Not supported | Plotly (`px`) -- no GS styling |
| Boxplot outlier markers | Not supported | Basic boxplot (Tukey 1.5*IQR whiskers) |

---

## 12. Dimensions

| Preset | Size | Best For |
|--------|------|----------|
| `wide` | 700x350 | Time series (default) |
| `square` | 450x450 | Scatter, heatmaps |
| `tall` | 400x550 | Vertical bars, rankings |
| `compact` | 400x300 | Dashboard components |
| `presentation` | 900x500 | Slides |
| `thumbnail` | 300x200 | Previews |

Typography auto-scales for `thumbnail` and `compact` presets.

---

## 13. Chart time horizon guidelines

### Default lookback

| Frequency | Default | Horizon Class | Use Case |
|-----------|---------|---------------|----------|
| Quarterly / Monthly | 10 years | Medium | Cyclical patterns, regime comparisons -- default |
| Weekly | 5 years | -- | Trend + cycle (also YoY series, to show cycle) |
| Daily | 2-3 years | Short | Recent acceleration, event reactions -- regime without noise |
| Intraday | 5 trading days | Very Short | Event reaction window, data releases |

For structural shifts ("not seen since X"), use Long (20-50y) full history
regardless of frequency.

### Override rules

- "Highest since 2008" -> chart MUST include 2008. Pre-pandemic -> start >= 2015. Percentile claims require a full percentile window.
- Don't show 1-2y of monthly data (hides cycle); don't show 30+y of daily (noise); don't use different ranges for charts meant to be compared.

---

## 14. Failure transparency

Never silently substitute a different layout or rationalize a substitution.
If a requested chart shape isn't feasible, tell the user and offer
alternatives. Max 2 retries per chart concept; after 2 failures, deliver
the best version with a note or ask the user about alternatives.
