# Altair Charts & Tables — v1 router and core

- **Module:** `chart_context`
- **Audience:** PRISM in chat, email, report, and analysis workflows
- **Tier:** 2 (registered context module)
- **Scope:** Static PNG charts, multi-panel composites, and PNG tables. Interactive dashboards use `dashboards`.

The v1 surface is canonical. `make_chart`, `make_table`, `build_charts`,
`profile_df`, `ChartSpec`, all five `make_*pack_*` helpers, result classes,
and all annotation classes are injected into the sandbox. Call them bare:
**never import them**. `s3_manager`, `session_path`, and `user_id` are supplied
by the sandbox; never pass them. Raw matplotlib is blocked.

## 1. Route before authoring

Classify the request, then fetch every applicable spoke in one
`list_ai_repo(file_paths=[...], mode="full")` call. Pass only `file_paths`
and `mode`; `get_context()` is one-shot and cannot fetch a sibling mid-turn.

| Spoke | Mandatory trigger | Short path |
|---|---|---|
| Annotations | Threshold, event line, regime band, callout, highlight, trendline, narrative text, or any `annotations=[...]` / `layers=[...]` | `charts/chart_context_annotations.md` |
| Dual axis | Two metrics or units on one timeline; `dual_axis_*`, `y_title_right`, inverted RHS, lead-lag time shift, or a y-scale mismatch error | `charts/chart_context_dual_axis.md` |
| Composites and batch | Two or more chart calls, any `ChartSpec` / `make_*pack_*`, or several independent charts in one script | `charts/chart_context_composites.md` |
| Tables | Any structured rows × columns output or any `make_table()` call | `charts/chart_context_tables.md` |
| Grids | `mapping['facet']` or 7–36 same-shape entities | `charts/chart_context_grids.md` |
| Colours | Any chart palette, per-series colour, hex, fade, highlight, opacity, `color_scheme`, `color_map`, or `opacity_map` request | `charts/chart_context_colors.md` |

Example:

```python
list_ai_repo(
    file_paths=[
        "charts/chart_context_composites.md",
        "charts/chart_context_dual_axis.md",
    ],
    mode="full",
)
```

No spoke is needed for a basic single chart using default colours and no
annotations. Table colouring belongs to the **tables** spoke, not colours.

## 2. Pick the artifact and shape

**Structured rows × columns always render through `make_table()`.** Do not emit
Markdown pipe tables, `print(df)`, `df.to_string()`, or aligned text blocks.
Fetch the tables spoke before the call.

| Analytical shape | Reach for |
|---|---|
| Time path or curve | `multi_line` / `timeseries` |
| X–Y relationship | `scatter`; grouped relationships → `scatter_multi` |
| Categorical comparison | `bar` / `bar_horizontal` |
| Matrix | `heatmap` |
| Distribution | `histogram` / `boxplot` |
| Additive time-series components | `area` |
| Part-to-whole | `donut` |
| Current value inside a range | `bullet` |
| Additive bridge or attribution | `waterfall` |
| Two to six related stories | composite helper; fetch composites |
| Seven to 36 same-shape entities | facet grid; fetch grids |
| Structured watchlist, tape, calendar, snapshot, or trade list | `make_table`; fetch tables |

For freeform analysis, prefer a relationship-bearing shape over a descriptive
single line: scatter with trendline, lead-lag, phase orbit, normalized
co-movement, or a level-plus-change composite. Use a single chart when there is
one story; two panels are the default for compare/contrast.

## 3. Plot-ready data contract

The engine handles structural mechanics, not economic meaning:

1. Resolve units before plotting. Never guess whether `0.042` means 4.2%,
   0.042%, or 4.2 bp.
2. Choose the duplicate/revision policy explicitly. Keep one observation per
   intended `(x, series)` unless the chosen distribution chart needs raw rows.
3. Quantitative mapping fields must be numeric. Parse commas, currency,
   percentages, and blanks only after choosing the intended unit.
4. Normalize category identifiers used for joins and exact series binding
   (`strip`, case, aliases) before charting.
5. A single value axis must carry one unit family. Normalize, split into
   panels, or declare a dual axis when units differ.
6. Check that filters leave rows and valid mapped values. Empty frames raise.
   Do not delete outliers or fill missing values merely to make a chart pass.
   Decide whether they are errors, genuine observations, or missing coverage.
7. Keep sparse projections at native dates; do not forward-fill them onto a
   denser series and manufacture a step pattern.

The engine already promotes an unambiguous named/date index to `mapping['x']`,
parses date-like and timezone-aware x values for line charts, sanitizes
Vega-unsafe column names, auto-melts wide line data, reshapes unambiguous
wide/matrix heatmaps, sorts tenors, and downsamples very large time series.
Still name the intended x field in `mapping`; if that column is absent and an
unambiguous index supplies it, the engine promotes the index. Do not
`reset_index()` solely for the renderer.

Use `profile_df(df)` when schema or coverage is uncertain. Its `DataProfile`
exposes `.shape`, `.dtypes`, `.cardinality`, `.missing_pct`, and `.date_range`.

## 4. `make_chart()` and results

```python
result = make_chart(
    df=df,
    chart_type="multi_line",
    mapping={"x": "date", "y": "value", "color": "series"},
    title="Inflation Is Converging",
    subtitle="Core measures have slowed across regions",
    source="BLS via Haver",
    annotations=[...],
    layers=[...],
    caption=None,
    side_left=None,
    side_right=None,
    intent="explore",
    save_as="charts/inflation.png",
)
```

`title` should state the finding. `subtitle` adds context, never attribution.
`source="Haver"` renders `Source: Haver` below the chart; an explicit
`caption` wins. Never invent a source. `skin="gs_clean"` is the only published
skin. `intent` is `explore` (default), `publish` (700×400), or `monitor`
(500×300). Canvas dimensions are otherwise engine-selected.

Top-level `x_title`, `y_title`, and `y_title_right` are aliases for the same
keys inside `mapping`; a non-empty mapping value wins. `x_label` / `y_label`
are legacy aliases. Leave `interactive`, `auto_beautify`, dimensions, and
runtime-injected kwargs at their defaults unless an external artifact
constraint explicitly requires otherwise.

Results are dataclasses; use dot notation.

| Result field | Use |
|---|---|
| `png_path`, `download_url` | Stored PNG and user-facing URL |
| `vegalite_json` | Final chart specification |
| `warnings` | Non-fatal data or annotation findings; inspect and surface when material |
| `audit_trail` | Informational engine routing; do not present as a failure |
| `success`, `error_message` | Returned results are successful; public failures raise |

`make_chart`, `make_table`, and composites raise `ValidationError` on failure.
Independent defects aggregate into one numbered message. Fix **every** item,
then re-run; never swallow chart errors with `try/except`.

### Quality control

Foreground PRISM execution automatically runs the post-script chart-quality
sweep over rendered chart/composite PNGs. Do **not** call
`check_charts_quality()` manually in ordinary scripts. Tables are excluded.
The callable is foreground-only; background sandboxes do not inject it. Use it
directly only when a foreground multi-step workflow explicitly needs an
in-script gate over prior `ChartResult`, PNG-path, or `{"png_path": ...}`
values.

## 5. Hard readability gates

The engine raises rather than truncating. These are ceilings, not targets.

| Gate | Current hard limit | Authoring action |
|---|---:|---|
| Lines per `multi_line` / `timeseries` / `area` panel | 6 | Aim for ≤4; split, facet, or aggregate |
| Value-axis title (`y_title`, `y_title_right`; `x_title` on horizontal bars) | 28 characters | Aim for concise metric + unit |
| Auto end-label series name | 32 characters | Rename categories before charting |
| Bar category label | 22 characters | Abbreviate in the DataFrame |
| Heatmap row or column label | 20 characters | Abbreviate in the DataFrame |
| Scatter relationship | At least 8 distinct visible `(x, y)` coordinates | Widen window or use line/bar/table |
| Categorical colour / donut slices | 10 categories | Filter or aggregate to `Other` |
| Composite / facet count | Packs 2–6; facets 7–36 | Fetch the matching spoke |
| `PlotText.text` | 10 words (aim ≤8) | Use caption/side text for longer prose |

Long labels are named in the error with an actionable repair. Never pre-truncate
with ellipses.

## 6. Chart types and core mapping

### 6.1 Type catalog

| `chart_type` | Required mapping | Core rule |
|---|---|---|
| `multi_line` / `timeseries` | `x`, `y`; optional `color` | Datetime series or ordinal profiles; `timeseries` follows the same line path |
| `scatter` | `x`, `y` | At least 8 distinct visible coordinates |
| `scatter_multi` | `x`, `y`, `color` | Grouped scatter; `trendlines=True` fits per group |
| `bar` | categorical `x`, numeric `y` | Categorical only, never raw datetime |
| `bar_horizontal` | numeric `x`, categorical `y` | Prefer for longer category labels |
| `heatmap` | `x`, `y`, `value` | Cell magnitude is `value`, not `color` |
| `histogram` | `x` | Distribution of one numeric field |
| `boxplot` | categorical `x`, numeric `y` | Compare distributions |
| `area` | `x`, `y`; optional `color` | Stacked series require common x coverage and non-negative values |
| `donut` | `theta`, `color` | Part-to-whole; at most 10 slices |
| `bullet` | `y`, `x`, `x_low`, `x_high` | Current value within a range |
| `waterfall` | categorical `x`, numeric `y`; optional `type` | Additive bridge |

### 6.2 Canonical mapping patterns

```python
# Long multi-series
{"x": "date", "y": "value", "color": "series", "y_title": "CPI YoY (%)"}

# Wide line input; engine melts the y columns
{"x": "date", "y": ["headline", "core"]}

# Relationship
{"x": "financial_conditions", "y": "growth", "trendline": True}

# Heatmap: long, wide, or an indexed matrix
{"x": "tenor", "y": "country", "value": "yield_pct"}

# Range-dot / percentile screen: use chart_type="bullet"
{"y": "metric", "x": "current", "x_low": "low", "x_high": "high",
 "color_by": "zscore", "label": "display_value"}
```

| Mapping key | Meaning |
|---|---|
| `x`, `y`, `color` | Primary fields; `y` may be a list for line/area auto-melt |
| `x_title`, `y_title`, `y_title_right` | Semantic axis title, including unit |
| `x_sort`, `y_sort`, `color_sort` / `legend_sort`, `value_sort` | Explicit display order |
| `x_type` | Force ordinal for genuine categories such as tenors; not for datetime |
| `x_timezone` | Intraday display clock; default `America/New_York` |
| `legend` | Explicit legend override; normally leave automatic |
| `trendline`, `trendlines` | Overall scatter fit / per-group fits |
| `connect`, `order` | Ordered scatter path; incompatible with trendline |
| `zero_fill`, `zero_fill_baseline` | Single-line above/below-baseline fill |
| `stack` | `bar`/`area` with colour: stacked by default; `False` groups/layers |
| `strokeDash`, `strokeDashScale`, `strokeDashLegend` | Single-axis line-style encoding |
| `value`, `theta`, `type` | Heatmap value, donut magnitude, waterfall type |
| `bins` / `maxbins`, `bin_extent` | Histogram bins and range |
| `extent` | Boxplot whisker IQR multiplier; default 1.5 |
| `scale_type` | `linear` / `log` for line/timeseries/scatter only |
| `orientation` | `bar`: force `vertical` instead of automatic horizontal routing |
| `x_low`, `x_high`, `color_by`, `label` | Bullet range, marker colour metric, optional label |
| `dual_axis_series`, `dual_axis_bind`, `invert_right_axis`, `dual_axis_config` | Fetch dual-axis spoke |
| `facet`, `facet_order`; `facet_cols`, `same_scale`, `share_*` top-level | Fetch grids spoke |
| `color_scheme`, `color_range`, `color_map`, `opacity`, `opacity_map` | Fetch colours spoke |

### 6.3 Type-specific decisions

- `multi_line` / `timeseries` auto-add end-of-line labels on a single axis.
  Dual-axis and facet charts use legends/headers instead. Seasonal
  jaggedness, alternating-series oscillation, extreme missing coverage, and
  incompatible y-scales raise with the required reshape.
- Intraday line x values should stay datetime-like. Do not pre-format clock
  strings or force ordinal; set `x_timezone` only when ET is wrong.
- `scatter` + `connect=True` creates an ordered phase path and needs `order`
  or temporal/numeric `color`. Fetch colours when overriding its gradient.
- `bar` / `bar_horizontal` are categorical comparisons. Mixed value units on
  one bar axis raise. Grouped bars (`stack=False`) do not render annotations.
- `heatmap` accepts tidy long data, an unambiguous wide frame, or a meaningful
  indexed matrix. Numeric values use a quantitative scale; categorical bins
  may have at most 10 ordered labels via `value_sort`.
- `area` stacks by default when `color` is present. Misaligned calendars or
  negative stacked values raise; align the series, use `stack=False`, switch
  to `multi_line`, or use `waterfall` as the error directs.
- `bullet.color_by` interprets 0–100-like values as percentile distance from
  50 and other numeric values as z-score magnitude. Omit `color_by` for one
  marker colour.
- `waterfall.type` may contain `total`, `positive`, and `negative`; when
  omitted, first/last are totals and intermediate signs follow `y`.

## 7. Titles, horizons, and failure recovery

Use the shortest label that remains unambiguous. Put units in axis titles,
not series names. `source=` owns attribution. Use `caption` / `side_left` /
`side_right` for prose that does not belong inside the plot.

| Frequency | Default window |
|---|---|
| Monthly / quarterly | About 10 years |
| Weekly | About 5 years |
| Daily | About 2–3 years |
| Intraday | About 5 trading days |

Expand the window to support the claim: “since 2008” must include 2008;
percentiles need the full calculation window; compared charts use the same
window.

For two or more chart calls, fetch the composites spoke and use
`build_charts()` rather than a bare loop. A failed batch or composite surfaces
all named defects; fix all of them and rebuild the complete set. Never silently
substitute a different layout—if the requested shape is analytically invalid,
explain the constraint and offer the engine-directed alternatives.
