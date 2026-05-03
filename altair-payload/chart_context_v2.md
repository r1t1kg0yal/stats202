# Altair Charts v2 (`Chart` + `render_grid`)

- **Module:** `chart_context_v2`
- **Audience:** PRISM (all interfaces, all workflows), developers
- **Tier:** 2 (on-demand)
- **Scope:** All static-PNG chart authoring in PRISM (chat / email /
  report flows). Composite layouts ship in this same module.
  Interactive HTML dashboards use the separate `dashboards` module
  (echarts).

`Chart` is the single builder for both standalone and composite use;
`render_grid` lays multiple `Chart` objects out into one of six
geometric layouts. Quality control, S3 cleanup, and download-URL
printing are absorbed into the render path -- you build the chart,
the engine handles the plumbing.

`Chart`, `render_grid`, the annotation classes, and `profile_df` are
auto-injected into `execute_analysis_script()`. Raw matplotlib is
blocked. Do NOT import chart functions.

---

## Catalog index

| Primitive | Names | Where |
|---|---|---|
| Chart types (12) | `multi_line`, `scatter`, `scatter_multi`, `bar`, `bar_horizontal`, `heatmap`, `histogram`, `boxplot`, `area`, `donut`, `bullet`, `waterfall` | §5 |
| Encoding kwargs | flat kwargs on `Chart(...)` | §2 |
| Annotation classes (11) | `VLine`, `HLine`, `Segment`, `Band`, `Arrow`, `PointLabel`, `PointHighlight`, `Callout`, `LastValueLabel`, `Trendline`, `PlotText` | §6 |
| Layouts (6) | `'auto'`, `'1x2'`, `'2x1'`, `'2x2'`, `'3x2'`, `'triangle'` | §4 |
| Skin (1, only published) | `gs_clean` | §2 |
| Intent values (3) | `'explore'`, `'publish'`, `'monitor'` | §2 |
| Layer types (3) | `regression`, `rule`, `point` | §6.5 |

Canvas size is auto-picked by the engine per chart type and per
composite layout. PRISM does not pick or pass a `dimensions` value.

---

## 1. Auto-injected namespace

| Name | Purpose |
|---|---|
| `Chart` | Build a single chart |
| `render_grid` | Compose 2-6 `Chart` objects into one grid layout |
| `render_all` | Render N independent `Chart` objects (NOT a grid) |
| `profile_df` | Analyse a DataFrame pre-charting |
| `ChartResult` / `CompositeResult` / `DataProfile` | Return types |
| `VLine`, `HLine`, `Segment`, `Band`, `Arrow` | Line / region annotations |
| `PointLabel`, `PointHighlight`, `Callout` | Point / text annotations |
| `LastValueLabel`, `Trendline`, `PlotText` | Series-aware / in-plot text |

---

## 2. The `Chart` class

```python
chart = Chart(
    df, type='multi_line',
    x='date', y='value', color='series',
    y_title='Yield (%)',
    title='Inflation Has Peaked',
    subtitle='Core CPI decelerating 6 months',
    annotations=[VLine(x='2022-03'), HLine(y=2.0)],
)
result = chart.render(save_as='charts/cpi.png')
```

### Encoding kwargs

| Kwarg | Type | Where it applies |
|---|---|---|
| `x`, `y`, `color` | str | All chart types (column names) |
| `value` | str | `heatmap` (cell color column; not `'color'`) |
| `theta` | str | `donut` (magnitude column) |
| `x_title`, `y_title`, `y_title_right` | str | Display labels (max 16 chars) |
| `x_sort`, `y_sort` | list | Explicit ordinal sort order |
| `x_type` | `'ordinal'` | Force ordinal on a datetime column |
| `dual_axis_series` | list[str] | Series names that route to the right y-axis |
| `invert_right_axis` | bool | Flip right axis (rates pattern) |
| `stack` | bool | Bar with color: `True` stacked (default), `False` grouped |
| `trendline` / `trendlines` | bool | `scatter` overall / `scatter_multi` per-group |
| `strokeDash` | str | `multi_line` per-series dash (column name) |
| `strokeDashScale`, `strokeDashLegend` | dict / bool | Explicit dash scale / show dash legend |
| `x_low`, `x_high`, `color_by`, `label` | str | `bullet`: range bounds, severity, label column |
| `type_col` | str | `waterfall`: column naming bar type (`total` / `positive` / `negative`) |
| `color_scheme` | str | `heatmap` palette (`'blues'`, `'viridis'`, ...) |

### Other kwargs

| Kwarg | Type | Default | Notes |
|---|---|---|---|
| `title` / `subtitle` | str | None | Title required for production; never use subtitle for source attribution |
| `annotations` | list | None | See §6 |
| `layers` | list[dict] | None | Regression / rule / point overlays; see §6.5 |
| `caption` / `side_left` / `side_right` | str or dict | None | Text panels |
| `skin` | str | `'gs_clean'` | Only published skin |
| `intent` | str | `'explore'` | `'explore'` / `'publish'` / `'monitor'` |
| `auto_beautify` | bool | True | Date format, label angle, y-domain |

### Methods

| Method | Returns | Purpose |
|---|---|---|
| `chart.render(save_as=None, *, run_qc=True, verbose=True)` | `ChartResult` | Build + QC + URL printing |
| `chart.preview()` | `dict` (Vega-Lite spec) | Inspect spec without writing PNG |
| `chart.annotate(*anns)` | `self` | Append annotations in place |
| `chart.layer(*layer_dicts)` | `self` | Append overlay layers in place |
| `chart.with_data(df)` | new `Chart` | Copy with data replaced (templates; see §13) |
| `chart.with_title(title, subtitle=None)` | new `Chart` | Copy with title replaced |

### `ChartResult` (dataclass, NOT dict)

Access via dot notation only (`result.png_path`, never `result['png_path']`).

| Attribute | Description |
|---|---|
| `png_path` / `download_url` | PNG S3 path / presigned URL |
| `editor_html_path` / `editor_download_url` | Chart Center HTML / presigned URL |
| `vegalite_json` | Final Vega-Lite spec dict |
| `success` / `error_message` | Render+QC succeeded? + error details |
| `warnings` | Non-fatal (auto-melt, downsample, ...) |

`CompositeResult` (returned by `render_grid`) adds `layout`,
`n_charts`, and `chart_errors` (per-panel build failures).

---

## 3. Render contract

`Chart.render()` and `render_grid()` automatically run Gemini-vision
QC over the rendered PNG, delete failed charts from S3 (so the
session folder never accumulates rejects), and print PNG + Chart
Center URLs to stdout. PRISM does NOT write `check_charts_quality()`,
`s3_manager.delete()`, or URL prints.

Opt-out flags (rare): `run_qc=False`, `cleanup_on_qc_fail=False`,
`verbose=False`.

### Delivering URLs to the user (mandatory)

The engine prints URLs for the LLM context; PRISM still weaves them
into the narrative reply as markdown links so they render in the
chat / email surface:

```markdown
![Chart](<result.download_url>)

[Open in Prism Chart Center](<result.editor_download_url>) -- customize
colors, fonts, dimensions, palette. Export as PNG / SVG / Vega-Lite
JSON.
```

If `result.success=False`, do NOT include the chart in the reply; say
"could not deliver" with the reason.

---

## 4. Composites: `render_grid`

```python
result = render_grid(
    [c1, c2, c3, c4],
    layout='2x2',                # 'auto' | '1x2' | '2x1' | '2x2' | '3x2' | 'triangle'
    title='Inflation Has Peaked',
    subtitle='...',
    caption='...',
    narrative_left='...', narrative_right='...',
    save_as='charts/cpi_grid.png',
)
```

### Layouts

| Layout | Charts | Use case |
|---|---|---|
| `'1x2'` | 2 side-by-side | US vs EU comparison |
| `'2x1'` | 2 stacked | Level + decomposition |
| `'2x2'` | 4 in 2x2 | Regional 4-panel |
| `'triangle'` | 3 (1 top, 2 bottom) | Headline + 2 supporting |
| `'3x2'` | 6 in 3x2 | Sector / macro dashboard |
| `'auto'` | 2, 3, 4, or 6 | Layout inferred from `len(charts)` |

For 5 or 7+ charts, `'2x2'` / `'3x2'` with one purposeful blank
panel, OR rethink the composition.

### Composite rules

- Default to a composite when there's more than one related story
  (US vs EU, level vs change, regional grid). Single charts only for
  unrelated topics.
- Per-panel titles live on each `Chart`; `render_grid(title=...)`
  describes the whole pack.
- Per-panel scales / palettes resolve independently.
- Up to N-1 sub-charts can fail; survivors still render. Failures
  land in `result.chart_errors`.

### Series count guideline

| Count | Approach |
|---|---|
| 2-4 | Single `multi_line` (ideal) |
| 5-6 | `render_grid([..], layout='1x2')`, 2-3 lines each |
| 7-8 | `render_grid([..], layout='2x2')`, 2 lines each |
| 9+ | Aggregate / group, or `heatmap` |

---

## 5. Chart types

### 5.1 Type catalog

| Type | Use case | Required encoding |
|---|---|---|
| `multi_line` | Time series, curve evolution | `x`, `y`, `color` (opt) |
| `scatter` | X-Y relationships | `x`, `y` |
| `scatter_multi` | Grouped scatter + trendlines | `x`, `y`, `color` |
| `bar` | Category comparisons (stacked / grouped via `stack`) | `x` (cat), `y`, `color` (opt) |
| `bar_horizontal` | Horizontal bars | `x`, `y` (cat) |
| `heatmap` | Matrices | `x`, `y`, `value` (NOT `color`) |
| `histogram` | Distributions | `x` |
| `boxplot` | Distribution comparison | `x` (cat), `y` |
| `area` | Stacked time series | `x`, `y`, `color` |
| `donut` | Part-to-whole | `theta`, `color` |
| `bullet` | Range dot / percentile | `y` (cat), `x`, `x_low`, `x_high` |
| `waterfall` | Additive decomposition | `x` (cat), `y`, `type_col` (opt) |

`multi_line` auto-detects non-datetime x-axis -> ordinal mode. Tenor
values (`1M`, `2Y`, `10Y`) auto-sort by maturity.

### 5.2 Bar family

`stack=True` (default with color) sums components into a stacked
total. `stack=False` produces grouped bars. Use stacked for
parts-of-a-whole / additive decomposition; grouped for independent
comparisons / benchmarking. Don't add a sign-keyed color column to
bars -- position relative to zero already conveys sign.

Annotation compatibility: single-series and stacked bars accept
`HLine`, `VLine`, `Band`, `Arrow`, `PointLabel`. Grouped bars
(`stack=False`) do NOT render annotations -- convey thresholds via
title / subtitle, or switch to `stack=True`.

### 5.3 Heatmap

Continuous values must be binned to <=12 categories before charting:

```python
df['prob_bucket'] = pd.cut(
    df['Probability'], bins=10,
    labels=[f'{i*10}-{(i+1)*10}%' for i in range(10)],
)
Chart(df, type='heatmap',
      x='meeting_date', y='fed_funds_rate',
      value='prob_bucket', color_scheme='blues')
```

Matrix-shape DataFrames (correlation / distance matrices) auto-melt
internally when `x` and `y` are `'columns'` / `'index'`.

### 5.4 Bullet

Current values within historical ranges; marker color encodes
severity via z-score or percentile.

```python
Chart(df, type='bullet',
      y='variable', x='current_value',
      x_low='range_low', x_high='range_high',
      color_by='z_score', label='percentile')
```

### 5.5 Waterfall

Additive decomposition (CPI / GDP, P&L, FCI impulse). `type_col` is
optional -- if absent, first / last rows are totals, intermediates
signed by value. Engine warns if intermediates do not sum to
`(last - first)` within 15%.

```python
Chart(df, type='waterfall',
      x='component', y='contribution', type_col='type',
      y_title='CPI YoY (%)')
```

### 5.6 Haver frequency hygiene

Haver stores many monthly / quarterly series at business-daily
granularity (same value repeated ~22 days). Symptom: stair-step
lines. Fix: resample to native frequency BEFORE charting.

| Series type | Resample | Example |
|---|---|---|
| Point-in-time / stock | `.last()` | Housing starts, unemployment |
| Flow / cumulative | `.mean()` or `.sum()` | Initial claims, retail sales |
| Rate / percentage | `.last()` or `.mean()` | CPI YoY, mortgage rate |

Merging mixed-frequency series creates NaN gaps -- resample
everything to the lowest common frequency before `concat` / `merge`.

---

## 6. Annotations & layers

### 6.1 The "is this annotation worth it?" filter

Annotations must be EXTREMELY useful and core to the chart's
argument -- otherwise omit. Default to zero annotations; add one
only when it actively sharpens the narrative. Test: "would a PM
learn anything new from this annotation?" If no, omit.

```python
T = pd.Timestamp
annotations = [
    HLine(y=2.0, label='Target', color='#00AA00'),
    VLine(x=T('2022-03'), label='Hike start'),
    Band(x1=T('2020-03'), x2=T('2020-06'), label='Recession', opacity=0.3),
    Callout(x=T('2022-06'), y=9.1, label='Peak 9.1%'),
    LastValueLabel(show_value=True),
]
```

### 6.2 Anti-patterns (DO NOT)

| Anti-pattern | Why trivial |
|---|---|
| `HLine(y=0)` on a spread chart | y-axis already shows zero |
| `HLine(y=2.0, label='Fed target')` on inflation | Every reader knows it; use the title |
| `HLine(y=last_value)` | `LastValueLabel` already does this |
| `VLine` at right edge labeled "Today" | The right edge IS today |
| `PointLabel` describing slope | Geometry conveys this |
| `Band` covering whole visible range | The whole chart IS the sample |
| Round-number threshold lines (`HLine(y=50)`) | No info unless it's a policy / regime level |
| Multiple annotations crowding < 6 months | Pick one; demote rest to subtitle |

### 6.3 Annotation parameters

| Class | Key parameters |
|---|---|
| `VLine` | `x`, `label`, `color`, `style`, `stroke_dash` |
| `HLine` | `y`, `axis` (`'left'` / `'right'`), `label`, `color`, `style` |
| `Segment` | `x1`/`x2`, `y1`/`y2`, `label`, `color`, `axis`, `label_position` |
| `Band` | `x1`/`x2` (vertical) OR `y1`/`y2` (horizontal), `label`, `opacity` |
| `Arrow` | `x1`/`y1`, `x2`/`y2`, `label`, `head_size`, `head_type` |
| `PointLabel` | `x`, `y`, `label`, `dx`, `dy` |
| `PointHighlight` | `x`, `y`, `color`, `size`, `shape`, `axis` |
| `Callout` | `x`, `y`, `label`, `background` (`'halo'` / `'box'` / `'none'`) |
| `LastValueLabel` | `show_value`, `value_format`, `include_right_axis` |
| `Trendline` | `method` (`'linear'` / `'exp'` / `'log'` / `'pow'` / `'poly'` / `'quad'`) |
| `PlotText` | `text`, `position` (`'auto'` or 9-corner anchor) |

All classes inherit `label` and `label_color` from base `Annotation`.
Use `style=` or `stroke_dash=` for dash patterns -- there is no
`dash` / `linestyle` parameter.

### 6.4 Chart-type compatibility

Rule-style annotations (`HLine`, `VLine`, `Band`, `Callout`,
`PointLabel`, `PointHighlight`) are silently dropped on non-Cartesian
chart types (`donut`, `pie`, `bullet`) -- use `title` / `subtitle`
instead. `LastValueLabel` only on `multi_line` / `area`; `Trendline`
only on scatter.

### 6.5 Layers

```python
layers = [
    {'type': 'regression', 'x': 'x_var', 'y': 'y_var', 'method': 'linear'},
    {'type': 'rule', 'y': 2.0, 'color': '#FF0000', 'stroke_dash': [4, 4]},
    {'type': 'point', 'x': 'x_var', 'y': 'y_var', 'data': highlight_df, 'size': 200},
]
```

Use `annotations=` for `VLine`/`HLine`/`Band`/`Arrow`; `layers=` only
for regression / rule / secondary-point overlays.

---

## 7. Authoring rules

- **Max 4 lines per `multi_line`.** For >4 series, use `render_grid`.
- **`y_title` plain English, max 16 chars.** Always set if column name
  is coded or exceeds 16 chars (`JXCHF@USECON` -> `Core CPI (YoY %)`).
- **X column must be named `'date'` for time series and be a column,
  not just the index.** `df = df.rename(columns={'datetime': 'date'}).reset_index()`.
- **Multi-line long-format pattern: rename FIRST, then melt.** Or use
  the auto-melt shortcut: `Chart(df, type='multi_line', x='date', y=['Series A', 'Series B'])`.
- **No source attribution in title / subtitle.** Title makes the
  argument; sources live in PRISM metadata.
- **Clean before charting.** `pd.to_numeric(errors='coerce')` then
  `dropna(subset=['date', 'value'])`. Max 12 color categories, 16
  facet categories. >5,000 rows auto-downsample to ~2,000 (warning
  in `result.warnings`).
- **Never plot `np.zeros()` placeholder.** If data is unavailable,
  skip the panel or add a text annotation.

---

## 8. Dual-axis charts

Use when two series belong on the same chart but have different
scales (equity index vs ISM, 2s10s vs WTI). The reader's eye lands
on co-movement; the two axis labels make scale separation explicit.

Always declare with explicit long format -- the auto-melt shortcut
(`y=[list]`) is incompatible with `dual_axis_series`.

```python
LEFT, RIGHT = '2s10s Curve (bp)', 'WTI Crude ($/bbl)'
curve_df['series'] = LEFT
oil_df['series'] = RIGHT
df_long = pd.concat([curve_df, oil_df], ignore_index=True)

Chart(df_long, type='multi_line',
      x='date', y='value', color='series',
      dual_axis_series=[RIGHT],
      y_title='2s10s (bp)',
      y_title_right='WTI ($/bbl)',
      title='Curve vs Oil')
```

Discipline: define LEFT / RIGHT constants once, use them as the
DataFrame value AND the title source. Rename DataFrame columns BEFORE
melting; `.str.strip()` series read from CSV; re-check
`df['series'].value_counts()` after `.dropna()`.

`invert_right_axis=True` flips the right axis (higher = bottom).
Standard rates pattern where "up = bullish" on both axes.

`HLine`, `Segment`, `PointHighlight` accept `axis='right'` -- pass
values in right-axis units. `Trendline` does NOT apply on dual-axis;
for trendline-on-dual-axis stories, build single-axis charts and
combine via `render_grid([..], layout='2x1')`.

When NOT to use dual-axis:

| Intent | Better shape |
|---|---|
| Compare magnitudes side-by-side (not co-movement) | `render_grid([..], layout='2x1')` |
| 3+ series with scale problems | z-score normalize, single axis with `multi_line` |
| Per-series regime annotations | `multi_line` per series in `render_grid` |

---

## 9. `profile_df`: pre-charting analysis

```python
profile = profile_df(df)
print(profile.shape)              # (rows, cols)
print(profile.cardinality)        # {'series': 4, 'date': 252, ...}
print(profile.missing_pct)        # {'value': 0.0, 'series': 0.0}
print(profile.date_range)         # {'date': {'min': '...', 'max': '...'}}
print(profile.numeric_stats)      # {'value': {'mean':..., 'std':..., ...}}
```

Returns a `DataProfile` dataclass; `.to_dict()` to serialise.

---

## 10. Chart Center

Every successful render produces a Chart Center HTML editor on
`result.editor_download_url`: ~140 editable knobs (themes, palettes,
typography, dimensions, exports, interactivity), runs entirely
client-side via CDN.

**Styling delegation rule:** PRISM does NOT iterate on chart
styling. For any visual / aesthetic request -- line thickness,
colors, fonts, legend position, palette, "make it bigger" -- hand
the user the Chart Center link, do not regenerate. Re-render only
when the request changes the **data** (series, time range, filter),
the **structure** (chart type, encoding, annotations, layout), or
the **narrative** (title, subtitle).

---

## 11. Chart time horizon

| Frequency | Default | Use case |
|---|---|---|
| Quarterly / Monthly | 10 years | Cyclical patterns, regime comparisons |
| Weekly | 5 years | Trend + cycle |
| Daily | 2-3 years | Recent acceleration, event reactions |
| Intraday | 5 trading days | Event reaction window, data releases |

Override rules: "highest since 2008" -> chart MUST include 2008.
"Pre-pandemic" -> start >= 2015. Percentile claims require a full
percentile window. Don't show 1-2y of monthly data (hides cycle);
don't show 30+y of daily (noise); don't use different ranges for
charts meant to be compared. For structural shifts ("not seen since
X"), use Long (20-50y) regardless of frequency.

---

## 12. Failure transparency

Never silently substitute a different layout or rationalise it. If a
requested shape isn't feasible, tell the user and offer alternatives.
Max 2 retries per chart concept; after 2 failures, deliver the best
version with a note OR ask the user. Build / QC failure details land
in `result.error_message`, `result.warnings`, and (composites)
`result.chart_errors`.

---

## 13. Template pattern

Build a `Chart` once, swap the data per render. Annotations / titles
/ encoding kwargs all carry over via `with_data` / `with_title`.

```python
template = Chart(
    None, type='multi_line',
    x='date', y='value', color='series',
    y_title='Yield (%)',
    annotations=[LastValueLabel(show_value=True)],
)
for region, df in regions.items():
    template.with_data(df).with_title(f'{region} Yields').render(
        save_as=f'charts/{region.lower()}_yields.png',
    )
```

`with_data` / `with_title` return new `Chart` objects; the original
template is unchanged.
