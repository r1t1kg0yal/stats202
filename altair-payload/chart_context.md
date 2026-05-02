# Chart Creation Reference

`make_chart()` and the composite/annotation/profile helpers are auto-injected
into `execute_analysis_script()`. Raw matplotlib is blocked. Do NOT import
chart functions.

## Auto-Injected Namespace

| Function / Class | Purpose |
|------------------|---------|
| `make_chart()` | Build a single chart |
| `profile_df()` | Analyze a DataFrame pre-charting |
| `ChartResult` | Return type of `make_chart()` |
| `ChartSpec` | Spec for composite sub-charts |
| `check_charts_quality()` | MANDATORY post-chart QC gate |
| `make_2pack_horizontal()`, `make_2pack_vertical()` | 2-chart composites |
| `make_3pack_triangle()` | 3-chart composite (1 top, 2 bottom) |
| `make_4pack_grid()` | 2x2 composite |
| `make_6pack_grid()` | 3x2 composite |
| `VLine`, `HLine`, `Segment`, `Band`, `Arrow` | Line/region annotations |
| `PointLabel`, `PointHighlight`, `Callout` | Point/text annotations |
| `LastValueLabel`, `Trendline` | Series-aware annotations |

`s3_manager`, `session_path`, and `user_id` are auto-injected at call time --
never pass them explicitly.

## `make_chart()` Signature

```python
result = make_chart(
    df=df,                       # Plot-ready DataFrame
    chart_type='multi_line',     # See Chart Types
    mapping={...},               # Column mappings
    title='Title',               # Required for production charts
    subtitle='Subtitle',         # Optional (NEVER for source attribution)
    skin='gs_clean',             # Only published skin
    intent='explore',            # 'explore' | 'publish' | 'monitor'
    dimensions='wide',           # See Dimensions
    annotations=[...],           # Optional
    layers=[...],                # Optional overlays (regression / rule / point)
    save_as='charts/name.png',   # Optional fixed path (overwrites, no timestamp)
    auto_beautify=True,          # Date format, label angle, y-domain (default True)
    x_label=None, y_label=None,  # Convenience aliases for mapping['x_title' / 'y_title']
    filename_prefix=None,        # Optional slug prefix
    filename_suffix=None,        # Optional slug suffix
)
```

`SESSION_PATH` and `s3_manager` are wired by the sandbox. `output_dir` is
local-mode only. `interactive=True` is reserved.

## `ChartResult` (Dataclass, NOT Dict)

Access via dot notation only (`result.png_path`). `result['png_path']` raises
`TypeError`.

| Attribute | Type | Description |
|-----------|------|-------------|
| `png_path` | str | S3 path to PNG |
| `download_url` | str | Presigned PNG URL |
| `editor_html_path` | str | S3 path to Chart Center HTML |
| `editor_download_url` | str | Presigned Chart Center HTML URL |
| `editor_chart_id` | str | Chart Center chart ID (sha1 of spec) |
| `vegalite_json` | dict | Final Vega-Lite spec |
| `chart_type` | str | Echoed chart type |
| `skin` | str | Echoed skin |
| `success` | bool | Render succeeded? |
| `error_message` | str / None | Error details |
| `warnings` | list | Non-fatal warnings (auto-melt, downsample, beautify failures, ...) |

`CompositeResult` (returned by all `make_Npack_*` helpers) carries the same
PNG/editor fields plus `layout`, `n_charts`, and `chart_errors` (per-sub-chart
failures with `df_shape`, `error_type`, `error_message`).

## Quality Gate (MANDATORY)

Every chart must pass through `check_charts_quality()`. Fail-open: if Gemini
is unavailable, all charts auto-pass. Pass composite results as single PNGs.

```python
r1 = make_chart(df=df1, chart_type='multi_line', mapping={...}, title='Chart 1')
r2 = make_chart(df=df2, chart_type='bar',        mapping={...}, title='Chart 2')

qc_results = check_charts_quality([r1, r2])
for r, qc in zip([r1, r2], qc_results):
    if not qc['passed']:
        print(f"FAIL: {r.png_path} -- {qc['reason']}")
        s3_manager.delete(r.png_path)
        if r.editor_html_path:
            s3_manager.delete(r.editor_html_path)
    else:
        print(f"PASS: {r.png_path}")
        if r.success:
            print(f" PNG: {r.download_url}")
            print(f" Chart Center: {r.editor_download_url}")
```

## Failed Chart Cleanup (MANDATORY)

Leave no trace of failing charts. Session folders must only contain QC-passed
charts. Failed PNGs mislead downstream consumers (report writers, dashboards,
session reloads). Delete failed PNGs AND their `editor_html_path` companion
via `s3_manager.delete()`. Fix or remove the offending `make_chart()` call.
Never expose a QC-failed chart to the user. It is acceptable to say Prism
could not generate a chart; it is never acceptable to show a failed one.

## Chart Types

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

`timeseries` is accepted as an alias path inside the multi_line builder.

## Mapping Structure & Keys

### Basic Patterns

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

# Dual axis
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': ['Right Axis Series'],
    'y_title': 'Left Label', 'y_title_right': 'Right Label',
}
```

### All Mapping Keys

| Key | Type | Description |
|-----|------|-------------|
| `x` | str | X-axis column |
| `y` | str / list | Y-axis column(s); list triggers auto-melt |
| `color` | str | Grouping column for multi-series |
| `y_title` | str | Y-axis label override (max 20 chars) |
| `y_title_right` | str | Right y-axis label (dual axis only) |
| `x_title` | str | X-axis label override |
| `x_sort` | list | Explicit ordinal sort order |
| `x_type` | str | Force `'ordinal'` on datetime columns |
| `y_sort` | list | Explicit y-axis sort order (heatmap) |
| `dual_axis_series` | list | Series names for right y-axis |
| `invert_right_axis` | bool | Flip right y-axis (higher = bottom); standard rates pattern |
| `trendline` | bool | Overall trendline (scatter) |
| `trendlines` | bool | Per-group trendlines (scatter_multi) |
| `stack` | bool | Bar with color: `True` (default) = stacked, `False` = grouped |
| `strokeDash` | str | Column for per-series line style |
| `strokeDashScale` | dict | Explicit `{domain: [...], range: [...]}` for dash patterns |
| `strokeDashLegend` | bool | Show strokeDash legend (default `False`) |
| `value` | str | Value column (heatmap only) |
| `theta` | str | Magnitude column (donut only) |
| `x_low` / `x_high` | str | Range bounds (bullet only) |
| `color_by` | str | Severity column (bullet only) |
| `label` | str | Label column (bullet only) |
| `type` | str | Bar-type column (waterfall only: `total` / `positive` / `negative`) |

### strokeDash: Per-Series Line Styles

For `multi_line` only (single y-axis path). Not supported on dual-axis or
profile/curve charts. Uses Altair 4.1+ `alt.StrokeDash()`.

Use when lines share the same color but differ in style (e.g., actuals vs
estimates). Keep `color` for the entity and `strokeDash` for the type -- do
NOT combine them into one series name.

```python
result = make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value',
        'color': 'company',
        'strokeDash': 'type',  # 'Actual' vs 'Estimate'
        'y_title': 'Capex ($B)',
    },
    title='Big Tech Capex: Actuals and Estimates',
    subtitle='Solid = actuals, dashed = consensus estimates',
)
```

Auto-scale: 2 categories -> solid `[1,0]` + dashed `[6,4]`; 3 -> adds dotted
`[2,2]`; 4+ -> Altair auto-assigns. Explicit scale (optional):

```python
strokeDashScale = {'domain': ['Actual', 'Forecast'], 'range': [[1, 0], [8, 3]]}
```

Legend suppressed by default (color already identifies series). Set
`strokeDashLegend: True` to show it.

## Critical Rules

### 0. Max Lines Per Chart (Soft Guideline)

<= 4 lines per `multi_line` chart. 5+ lines cause clutter.

| Series Count | Approach |
|--------------|----------|
| 2-4 | Single `multi_line` (ideal) |
| 5-6 | `make_2pack_horizontal()`, 2-3 lines each |
| 7-8 | `make_4pack_grid()`, 2 lines each |
| 9+ | Aggregate/group series, or use heatmap |

### 1. Y-Axis Labels: Plain English, Max 16 Chars

Always set `y_title` if the column name is coded or exceeds 16 chars.

| Wrong | Correct |
|-------|---------|
| `JXCHF@USECON` | `Core CPI (YoY %)` |
| `Population (Millions)` (21 chars) | `Pop. (Millions)` |

### 2. Date Column Requirements (Top Cause of Empty Charts)

- X column must be named `'date'` for time series: `df = df.rename(columns={'datetime': 'date'})`
- Date must be a column, not just the index: `df = df.reset_index()`

### 3. Multi-Line with Color Requires Long Format

```python
df_long = df.melt(id_vars=['date'], var_name='series', value_name='value')
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}
```

OR auto-melt shortcut (no `color` key):

```python
mapping = {'x': 'date', 'y': ['col_a', 'col_b']}
```

### 4. Rename Columns BEFORE melt()

`reset_index()` uses the original index name. Rename immediately after reset,
before any melt.

```python
df = df.reset_index()
df.columns = ['date', 'Series A', 'Series B']  # Rename FIRST
df_long = df.melt(id_vars='date', var_name='series', value_name='value')
```

### 5. No Source Attribution in Title/Subtitle

Title/subtitle should make the argument. Source tracking lives in Prism's
metadata.

| Good | Bad |
|------|-----|
| `title='Inflation Has Peaked'` | `title='US CPI Data'` |
| `subtitle='Core CPI decelerating 6 months'` | `subtitle='Source: Haver'` |

### 6. Data Cleaning Before Charting

```python
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
assert len(df) > 0, "DataFrame is empty"
```

Max 12 color categories, 16 facet categories. Time series above 5,000 rows
are auto-downsampled to ~2,000 (warning emitted in `result.warnings`).

### 7. Never Plot Placeholder/Zero-Fill Data

If data is unavailable, skip the panel (use a smaller composite) or add a
text annotation. Never use `np.zeros()` as fallback; it produces misleading
flat lines at 0.

### 8. Stacked vs Grouped Bars

If summing values within a group is meaningful -> stacked (`stack=True`,
default). If summing is nonsensical -> grouped (`stack=False`). Applies to
both `bar` and `bar_horizontal`.

| Data Relationship | `stack` | Example |
|-------------------|---------|---------|
| Parts of a whole / additive decomposition | `True` | Revenue by product, GDP decomposition, asset allocation |
| Independent comparisons / benchmarking | `False` | OLS vs LASSO coefficients, actual vs forecast |

### 9. No Redundant Positive/Negative Color Coding

Do NOT add a color column encoding sign (`'Positive'`/`'Negative'`). The
bar's position relative to zero already conveys sign. Color should encode a
conceptual dimension (sector, region, model type).

## Haver Frequency & Mixed-Frequency DataFrames

### Business-Daily Storage Problem

Haver stores many monthly/quarterly series at business-daily granularity (same
value repeated ~22 days, then jumps). Symptom: stair-step lines. Fix: resample
to true frequency before charting.

```python
starts = starts.resample('M').last()   # Monthly
gdp = gdp.resample('Q').last()         # Quarterly
```

### Combining Different Frequencies

Merging series of different frequencies creates NaN gaps. Resample everything
to the lowest common frequency before charting.

```python
claims_monthly = claims.resample('M').mean()  # Weekly -> Monthly
df = pd.concat([claims_monthly, nfp_monthly], axis=1).dropna()
```

| Series Type | Resample Method | Example |
|-------------|-----------------|---------|
| Point-in-time / stock | `.last()` | Housing starts, unemployment rate |
| Flow / cumulative | `.mean()` or `.sum()` | Initial claims (mean), retail sales (sum) |
| Rate / percentage | `.last()` or `.mean()` | CPI YoY, mortgage rate |

Rules:

- Never chart a DataFrame with mixed-frequency NaN gaps.
- Always resample to common frequency before `concat` / `merge`.
- Comment the resampling method for auditability.
- For Haver data, resample business-daily to true native frequency as the first step.

## Bar Charts: Stacked vs Grouped (Details)

Default with color is stacked. Set `mapping['stack'] = False` for grouped
(side-by-side). Grouped mode uses Altair 4.x column faceting internally.

### Stacked

```python
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product'}
```

### Grouped

```python
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product', 'stack': False}
```

### Bar Chart Annotation Compatibility

| Bar Mode | Annotation Support |
|----------|--------------------|
| Single-series bar | `HLine`, `VLine`, `Band`, `Arrow`, `PointLabel` work |
| Stacked bar (default w/ color) | `HLine` works; clamped against stacked totals |
| Horizontal bar (`bar_horizontal`) | `HLine` renders as a vertical threshold |
| Grouped bar (`stack=False`) | Annotations DO NOT render (Altair faceting + layering incompatibility) |

For grouped bars, convey thresholds via title/subtitle or narrative text
instead, or switch to `stack=True` if a stacked view is acceptable.

For stacked bars, an `HLine` encodes against the stacked TOTAL (not individual
components) -- use this when the threshold applies to the total (e.g.
"regional target = $100B"), not when it applies to a single component.

### Bar Charts with Datetime X-Axes

Prefer `multi_line` or `area` for time-series data. If you must use `bar` +
datetime x, the engine handles temporal encoding automatically. For
period-based bars, convert dates to string labels (e.g., `"Q1 2025"`) to use
nominal encoding instead.

## Dual Axis

Use when series have very different scales. CRITICAL: `y: [list]` is
INCOMPATIBLE with `dual_axis_series` -- always use explicit long format.

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

### Inverted Right Axis

`invert_right_axis: True` flips the right y-axis (higher values at bottom).
Standard rates pattern where "up = bullish" on both axes. Vega-Lite uses
reversed domains natively -- no value negation needed; axis labels and
`HLine` placement work correctly.

### HLine on Right Axis

```python
annotations = [
    HLine(y=0, axis='left', label='Flat Curve', color='#666666'),
    HLine(y=3.50, axis='right', label='3.50%', color='#f58518'),
]
```

`axis` defaults to `'left'`. When `'right'`, `HLine` encodes against the
right y-axis field/domain. `Segment` and `PointHighlight` also support
`axis='right'`.

### Series Name Matching (CRITICAL #1 Dual-Axis Failure)

`dual_axis_series` must exactly match values in the color column. Mismatches
cause `ValueError` (one axis gets 0 rows).

| Common Cause | Fix |
|--------------|-----|
| Name differs between DataFrame and mapping | Use a constant variable for the series name |
| Trailing whitespace | `.str.strip()` on color column |
| `dropna()` removed all rows for one series | Inspect `df['series'].value_counts()` before charting |
| Melt used original column names | Rename columns BEFORE melting |

Mandatory diagnostic before every dual-axis call:

```python
print(f"Series in data: {df_long['series'].unique().tolist()}")
print(f"dual_axis_series: {[RIGHT_SERIES]}")
assert RIGHT_SERIES in df_long['series'].values, f"Mismatch! {RIGHT_SERIES} not found"
```

Best practice -- use constants:

```python
LEFT_SERIES = '2s10s Curve (bp)'
RIGHT_SERIES = 'WTI Crude ($/bbl)'
curve_df['series'] = LEFT_SERIES
oil_df['series'] = RIGHT_SERIES
df_long = pd.concat([curve_df, oil_df], ignore_index=True)
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': [RIGHT_SERIES],
    'y_title': '2s10s (bp)', 'y_title_right': 'WTI ($/bbl)',
}
```

### Dual-Axis Fallback

If dual-axis fails after 2 attempts, use `make_2pack_vertical()` or z-score
normalization. Max 2 retries per chart concept.

## Dimensions

| Preset | Size | Best For |
|--------|------|----------|
| `wide` | 700x350 | Time series (default) |
| `square` | 450x450 | Scatter, heatmaps |
| `tall` | 400x550 | Vertical bars, rankings |
| `compact` | 400x300 | Dashboard components |
| `presentation` | 900x500 | Slides |
| `thumbnail` | 300x200 | Previews |
| `teams` | 420x210 | Required for Teams medium |

When request is from Teams, always use `dimensions='teams'` (or
`dimension_preset='teams'` for composites). Typography auto-scales for
`teams`, `thumbnail`, and `compact` presets.

## Composite Charts

### When to Use (Decision Guide)

Composites are almost always better than individual charts for related data.
If charts share an x-axis, y-axis concept, or comparison dimension, they
belong in a composite.

| Situation | Winner |
|-----------|--------|
| US vs EU inflation comparison | Composite (`make_2pack_horizontal`) |
| Level + decomposition | Composite (`make_2pack_vertical`) |
| 4 regional PMIs | Composite (`make_4pack_grid`) |
| Unrelated topics | Individual charts |

### ChartSpec & Layout Functions

```python
spec = ChartSpec(df=df, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value'}, title='Title',
    subtitle='Subtitle', annotations=[...], layers=[...])
```

| Function | Layout | Positional Args |
|----------|--------|-----------------|
| `make_2pack_horizontal(c1, c2, ...)` | Side-by-side | 2 ChartSpecs |
| `make_2pack_vertical(top, bottom, ...)` | Stacked | 2 ChartSpecs |
| `make_3pack_triangle(top, bl, br, ...)` | 1 top + 2 bottom | 3 ChartSpecs |
| `make_4pack_grid(tl, tr, bl, br, ...)` | 2x2 | 4 ChartSpecs |
| `make_6pack_grid(r1l, r1r, r2l, r2r, r3l, r3r, ...)` | 3x2 | 6 ChartSpecs |

All accept keyword args: `title`, `subtitle`, `dimension_preset`,
`save_as`, `spacing`, `filename_prefix`, `filename_suffix`. Returns
`CompositeResult` with `.png_path`, `.download_url`, `.editor_html_path`,
`.editor_download_url`, `.success`, `.error_message`, `.chart_errors`.

`make_6pack_grid` also accepts `specs=[c1, c2, c3, c4, c5, c6]` (list-style
calling convention).

### Composite Rules

ChartSpec args are positional; metadata is keyword-only. Never use
`top=spec_a`.

`save_as` works on all chart functions (both `make_chart()` and all
composites). Saves at `{session_path}/{save_as}`, overwrites existing, no
timestamp prefix.

QC the composite PNG, not individual sub-specs:
`check_charts_quality([composite_result])`.

If QC fails with "completely empty": date is likely still in index (not a
column), y column is all-NaN, or DataFrame is empty after filtering.

Composites resolve color, x, and y scales independently per sub-chart, so
each panel keeps its own palette and axis range. Up to N-1 sub-charts can
fail and the composite still renders with the survivors (failures are
collected in `result.chart_errors`).

## Annotations

Use sparingly -- only for high-value context (recessions, policy changes,
meaningful thresholds).

```python
annotations = [
    HLine(y=2.0, label='Target', color='#00AA00'),
    VLine(x=pd.Timestamp('2022-03'), label='Hike start', color='#003359'),
    Segment(x1=pd.Timestamp('2015-01'), x2=pd.Timestamp('2019-12'),
        y1=2.0, y2=2.0, label='2015-2019 avg', color='#666666'),
    Band(x1=pd.Timestamp('2020-03'), x2=pd.Timestamp('2020-06'),
        label='Recession', color='#CCCCCC', opacity=0.3),
    Arrow(x1=pd.Timestamp('2020-04'), y1=5, x2=pd.Timestamp('2021-03'), y2=8,
        label='Recovery', color='#0066CC'),
    PointHighlight(x=pd.Timestamp('2022-06'), y=9.1, color='#C00000', size=120),
    Callout(x=pd.Timestamp('2022-06'), y=9.1, label='Peak 9.1%',
        background='halo'),
    LastValueLabel(show_value=True),
]
```

Avoid: `PointLabel` (clutters), generic threshold lines, text stating the
obvious.

### Annotation Parameter Reference

| Annotation | Key Parameters & Notes |
|------------|------------------------|
| `VLine` | `x`, `label`, `color` (default `"#666666"`), `style` (`'solid'`/`'dashed'`/`'dotted'`), `stroke_dash`, `stroke_width`, `label_color`. Vertical rule spanning the full y-axis. Auto-staggers labels when multiple VLines cluster together. |
| `HLine` | `y`, `axis` (`'left'`/`'right'`), `label`, `color`, `style`, `stroke_dash`, `stroke_width`, `label_color`. Spans the FULL x-axis. `axis` only for dual-axis (default `'left'`). Default `stroke_dash` is `[4,4]`. |
| `Segment` | `x1`, `x2`, `y1`, `y2`, `label`, `color`, `style`, `stroke_dash`, `stroke_width`, `axis` (`'left'`/`'right'`), `label_position` (`'start'`/`'middle'`/`'end'`), `label_offset_x`, `label_offset_y`, `label_color`. Finite line segment (NOT full-axis). Common patterns: horizontal segment (`y1==y2`) for windowed average, vertical segment (`x1==x2`) for finite event mark, diagonal for ad-hoc connector. Aliases: `x_start`/`x_end`, `y_start`/`y_end`. |
| `Band` | `x1`/`x2` (vertical) OR `y1`/`y2` (horizontal), `label`, `color`, `opacity` (default `0.3`), `label_color`. Aliases: `x_start`/`x_end`, `y_start`/`y_end`, `start_x`/`end_x`. |
| `Arrow` | `x1`/`y1` (start), `x2`/`y2` (end), `label`, `color`, `stroke_width`, `stroke_dash`, `head_size`, `head_type` (`'triangle'`/`'none'`), `label_position` (`'start'`/`'middle'`/`'end'`), `label_color`. Aliases: `x_start`/`x_end`, `y_start`/`y_end`. |
| `PointLabel` | `x`, `y`, `label`, `dx`, `dy` (pixel offsets), `font_size`, `align`, `label_color`. Plain floating text. Use sparingly. |
| `PointHighlight` | `x`, `y`, `label`, `color` (default `"#C00000"`), `size` (default `100`), `opacity`, `shape` (`'circle'`/`'square'`/`'diamond'`/`'triangle'`/`'cross'`/`'stroke'`), `filled`, `stroke_color`, `stroke_width`, `axis` (`'left'`/`'right'`), `label_color`. Filled marker at a specific point. Often combined with `Callout` or `PointLabel` for a "labeled marker" effect. |
| `Callout` | `x`, `y`, `label`, `background` (`'halo'`/`'box'`/`'none'`), `background_color` (default `'#FFFFFF'`), `halo_width`, `box_padding_x`/`box_padding_y`, `box_opacity`, `box_corner_radius`, `color`, `dx`, `dy`, `font_size`, `font_weight`, `align`, `axis` (`'left'`/`'right'`), `label_color`. Text annotation with halo (text-stroke trick) or box background. Solves the "PointLabel fights gridlines" readability problem. Default `'halo'` is best for most charts. |
| `LastValueLabel` | `show_value` (default `False`), `value_format` (default `"{:.2f}"`), `show_dot` (default `True`), `dot_size`, `dot_color`, `dx`, `font_size`, `font_weight`, `include_right_axis` (default `False`), `label_color`. Direct end-of-line labels for `multi_line` charts (FT/Bloomberg style; replaces the legend). Auto-derives labels from the color column. `label` is ignored on multi-series charts; for single-series it overrides the y-field name. |
| `Trendline` | `method` (`'linear'`/`'exp'`/`'log'`/`'pow'`/`'poly'`/`'quad'`), `label`, `color`, `stroke_width`, `stroke_dash`, `label_color`. Regression overlay on scatter charts. |
| `PlotText` | `text`, `position` (default `'auto'`; or any of 9 corner / edge anchors), `padding_x`, `padding_y`, `font_size`, `color`, `italic`, `align`, `max_width_pct`. In-plot narrative anchored to a corner. `position='auto'` picks the corner that collides least with the data (scores TL / TR / BL / BR by how far the data extends into each); bar / waterfall disqualify bottom corners. Use `'auto'` unless a specific corner is required. |

No `dash`, `line_style`, `linestyle`, or `line_type` parameter exists. Use
`style=` or `stroke_dash=`. All classes inherit `label` and `label_color`
from base `Annotation`.

### Annotation Anti-Patterns

Do NOT annotate things that are visually obvious or universally known to the
audience.

| Anti-Pattern | Do Instead |
|--------------|------------|
| `HLine(y=0, label='Zero')` on a spread chart | Omit; call out zero-crossing in narrative |
| `HLine(y=2.0, label='Fed 2% Target')` on inflation chart | Use title: "Core PCE Still 80bp Above Target" |

**Principle:** Annotate regime changes, policy shifts, event dates, structural
breaks -- not self-evident facts.

### Annotation Chart-Type Compatibility

Rule-style annotations (`HLine`, `VLine`, `Band`, `Callout`, `PointLabel`,
`PointHighlight`) are silently dropped on chart types without Cartesian
axes (`donut`, `pie`, `bullet`). Use `title` / `subtitle` for context on
those charts. `LastValueLabel` and `Trendline` only apply to their native
chart types (`multi_line` / `area` and scatter respectively).

## Layers

```python
layers = [
    {'type': 'regression', 'x': 'x_var', 'y': 'y_var', 'method': 'linear'},
    {'type': 'rule', 'y': 2.0, 'color': '#FF0000', 'stroke_dash': [4, 4]},
    {'type': 'point', 'x': 'x_var', 'y': 'y_var', 'data': highlight_df, 'size': 200},
]
```

Layers are stackable overlays applied AFTER the base chart is built. Use
`annotations=[...]` for VLine/HLine/Band/Arrow-style additions; reach for
`layers=[...]` only when you need a regression line, threshold rule, or a
secondary point cloud.

## Bullet Chart

Shows current values within historical ranges. Marker color encodes severity
via z-score or percentile.

```python
df = pd.DataFrame({
    'variable': ['2s10s', '5s30s', '10Y Spd'],
    'current_value': [38, -5, -33],
    'range_low': [-20, -10, -45],
    'range_high': [45, 60, -20],
    'z_score': [1.2, -1.5, 0.1],
    'percentile': [85, 12, 45],
})

result = make_chart(
    df=df, chart_type='bullet',
    mapping={
        'y': 'variable', 'x': 'current_value',
        'x_low': 'range_low', 'x_high': 'range_high',
        'color_by': 'z_score', 'label': 'percentile',
    },
    title='Rates RV Screen',
)
```

## Waterfall Chart

Additive decomposition / attribution. Bars float -- each starts where the
previous one ended. Use for CPI decomposition, P&L attribution, GDP growth
decomposition, FCI impulse, any additive breakdown.

```python
df = pd.DataFrame({
    'component': ['Start', 'Energy', 'Food', 'Core Goods', 'Core Services', 'End'],
    'contribution': [3.0, -0.4, -0.2, 0.1, 0.6, 3.1],
    'type': ['total', 'negative', 'negative', 'positive', 'positive', 'total'],
})

result = make_chart(
    df=df, chart_type='waterfall',
    mapping={'x': 'component', 'y': 'contribution', 'type': 'type',
             'y_title': 'CPI YoY (%)'},
    title='CPI Decomposition: Q1 2026',
)
```

`type` is optional. If absent, the first and last rows are treated as totals
and intermediate rows are signed by value. Color: positive = green
(`#2EB857`), negative = red (`#DC143C`), totals = skin primary. The engine
warns if intermediate values do not sum to `(last - first)` within 15%.

## profile_df: Pre-Charting DataFrame Analysis

Use before `make_chart()` to verify columns, dtypes, missingness, cardinality,
and date coverage. Returns a `DataProfile` (dataclass).

```python
profile = profile_df(df)
print(profile.shape)              # (rows, cols)
print(profile.temporal_columns)   # ['date']
print(profile.numeric_columns)    # ['value', 'pct_change']
print(profile.cardinality)        # {'series': 4, 'date': 252, ...}
print(profile.missing_pct)        # {'value': 0.0, 'series': 0.0}
print(profile.date_range)         # {'date': {'min': '...', 'max': '...'}}
print(profile.numeric_stats)      # {'value': {'mean':..., 'std':..., ...}}
```

`DataProfile` fields: `columns`, `dtypes`, `shape`, `temporal_columns`,
`numeric_columns`, `categorical_columns`, `cardinality`, `missing_pct`,
`date_range`, `numeric_stats`. Call `profile.to_dict()` to serialise.

## Chart Time Horizon Guidelines

### Default Lookback by Frequency

| Frequency | Default | Rationale |
|-----------|---------|-----------|
| Quarterly / Monthly | 10 years | Full business cycle |
| Weekly | 5 years | Trend + cycle |
| Daily | 2 years | Regime without noise |
| Intraday | 5 trading days | Event reaction window |

### Override Rules

- If referencing "highest since 2008", chart MUST include 2008.
- Pre-pandemic comparisons -> start >= 2015.

### Percentile Claims

- **Percentile claims** require a full percentile window.
- **YoY series**: 5 years to show cycle.

### Anti-Patterns

- Don't show only 1-2 years of monthly data (hides cycle).
- Don't show 30+ years of daily data (visual noise).
- Don't use different time ranges for charts meant to be compared.

### Horizon Selection

| Horizon | Use Case |
|---------|----------|
| Long (20-50y) | Structural shifts, "not seen since X" -- full history |
| Medium (10y) | Cyclical patterns, regime comparisons -- default |
| Short (2-3y) | Recent acceleration, event reactions -- recent |
| Very Short | Intraday, data release reactions -- days/weeks |

### Profile / Curve Evolution

`multi_line` auto-detects non-datetime x-axis -> ordinal mode. Tenor-like
values (`1M`, `2Y`, `10Y`) auto-sort by maturity.

## Failure Transparency (CRITICAL)

- Never silently substitute a different layout. If dual-axis fails, tell the
  user and offer alternatives.
- Max 2 retries per chart concept. After 2 failures, deliver best version
  with a note or ask user about alternatives.
- Never rationalize a substitution. Acknowledge the limitation honestly.

## Prism Chart Center

Every successful `make_chart()` (and every composite) produces TWO artifacts
in the session folder: a static PNG and a self-contained interactive editor
HTML (the "Chart Center"). Both come back on the same `ChartResult` object.

### What It Provides

- ~140 editable knobs grouped into Dimensions, Title, Typography, Axes,
  Legend, Colors, Interactivity, and per-mark sections (Line / Bar / Scatter
  / Area / Arc / Heatmap / Box / Bullet / Waterfall).
- Editable title, subtitle, axis labels, legend title.
- 5 theme presets: `gs_clean`, `bridgewater`, `minimal`, `dark`, `print`.
- 14 color palettes: categorical (`gs_primary`, `bridgewater`, `mono_blue`,
  `mono_grey`, `vivid`, `tableau`, `okabe_ito`), sequential (`viridis`,
  `blues`, `reds`, `greens`), diverging (`gs_diverging`, `redblue`,
  `spectral`).
- 12 dimension presets (the 7 PRISM canonical sizes plus `report`,
  `dashboard`, `widescreen`, `twopack`, `fourpack`, `custom`).
- Spec sheets: named, saveable JSON bundles of styling preferences scoped to
  user (and optionally chart type), persisted in browser localStorage and
  exportable / importable as JSON.
- Export: PNG (1x / 2x / 4x), SVG, Vega-Lite JSON, Altair Python.
- Tabs: Chart, Data (sortable / filterable + summary stats), Code,
  Metadata.
- Interactivity: tooltips, crosshair, brush zoom (x / y / both), legend
  click toggle, per-series color overrides.
- Runs entirely client-side via CDN (`vega@5`, `vega-lite@5`,
  `vega-embed@6`). No server, no auth.

### Styling Delegation Strategy (CRITICAL)

Prism should NOT iterate on chart styling. For ANY visual / aesthetic
request -- line thickness, colors, fonts, legend position, dimensions,
palette, padding, gridlines, etc. -- hand the user the Chart Center link.

Re-run `make_chart()` ONLY for:

- Different data (series / time range / metric / filter).
- Different structure (chart type, mapping, annotations, composite layout).
- Different narrative (title, subtitle).

If the user says "make it bigger" / "change the color" / "use a different
font" / "move the legend" / "make the lines thicker" -> point at Chart
Center, do not regenerate.

### Delivering Links to the End User (MANDATORY)

After EVERY successful chart, the LLM must surface BOTH links in its
response: the PNG (so the chart renders inline) AND the Chart Center URL
(so the user can customize it). Markdown only -- no HTML, no styling.

Step 1 -- print both URLs from the script so they reach the LLM context:

```python
result = make_chart(...)

if result.success:
    print(f"PNG: {result.download_url}")
    print(f"Chart Center: {result.editor_download_url}")
```

Step 2 -- emit them in the narrative reply. Substitute the actual URL
strings; the placeholders below are illustrative:

```markdown
![Chart](<result.download_url>)

[Open in Prism Chart Center](<result.editor_download_url>) -- customize
colors, fonts, dimensions, palette, and styling. Export as PNG / SVG /
Vega-Lite JSON. Save preferences as a spec sheet.
```

For composites (`make_2pack_horizontal`, `make_4pack_grid`, etc.) the
exact same pattern applies -- `CompositeResult` carries `download_url` and
`editor_download_url` with identical semantics:

```python
comp = make_2pack_horizontal(spec_a, spec_b, title='...')
if comp.success:
    print(f"PNG: {comp.download_url}")
    print(f"Chart Center: {comp.editor_download_url}")
```

The Chart Center URL is presigned (1 hour by default) and the underlying
`editor_html_path` is a stable S3 path inside the session folder, so the
user can re-open the same editor by re-presigning the path later via
`s3_manager` if the original URL expires.

### Session Folder Structure

```
sessions/{timestamp}_{slug}/
    {timestamp}_{chart_name}_{chart_type}.png
    charts/{timestamp}_{chart_name}_{chart_type}_editor.html
```

When `save_as='charts/foo.png'` is supplied, the editor companion lands at
`charts/foo_editor.html` -- same dir, same base, no timestamp prefix.

### Non-Fatal Generation

If Chart Center generation fails (vega CDN unreachable, spec hash collision,
template error), the PNG still delivers. `editor_download_url` and
`editor_html_path` will be `None` and `result.warnings` carries the cause.
Deliver the PNG and note Chart Center was unavailable rather than silently
omitting it.

### Known Limitations

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
