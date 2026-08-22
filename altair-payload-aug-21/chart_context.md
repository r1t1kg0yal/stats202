# Altair Charts & Tables — v1 router and core

- **Audience:** the chart agent
- **Scope:** Static PNG charts, multi-panel composites, and PNG tables. Live dashboards are not yours.

The v1 surface is canonical. `make_chart`, `make_table`, `build_charts`,
`profile_df`, `ChartSpec`, all five `make_*pack_*` helpers, result classes,
and all annotation classes are injected into the sandbox. Call them bare:
**never import them**. `s3_manager`, `session_path`, and `user_id` are supplied
by the sandbox; never pass them. There is no matplotlib here: `plt` is not in
your namespace and importing it yourself produces a confusing failure, not a
chart. Every visual on this surface comes from the functions below.

## 1. Where things are

Everything you need is already here. This document continues past the `---`
separators below into six further documents, all of them present in full. There
is nothing to retrieve and no tool to retrieve it with.

| Topic | Trigger | Document |
|---|---|---|
| Annotations | Threshold, event line, regime band, callout, highlight, trendline, narrative text, or any `annotations=[...]` / `layers=[...]` | `chart_context_annotations.md` |
| Dual axis | Two metrics or units on one timeline; `dual_axis_*`, `y_title_right`, inverted RHS, lead-lag time shift, or a y-scale mismatch error | `chart_context_dual_axis.md` |
| Composites and batch | Two or more chart calls, any `ChartSpec` / `make_*pack_*`, or several independent charts in one script | `chart_context_composites.md` |
| Tables | Any structured rows × columns output or any `make_table()` call | `chart_context_tables.md` |
| Grids | `mapping['facet']` or 7–36 same-shape entities | `chart_context_grids.md` |
| Colours | Any chart palette, per-series colour, hex, fade, highlight, opacity, `color_scheme`, `color_map`, or `opacity_map` request | `chart_context_colors.md` |

A basic single chart using default colours and no annotations needs none of
them. Table colouring is in **tables**, not colours.

## 2. Pick the artifact and shape

**Structured rows × columns always render through `make_table()`.** Do not emit
Markdown pipe tables, `print(df)`, `df.to_string()`, or aligned text blocks.
See `chart_context_tables.md`.

| Analytical shape | Reach for |
|---|---|
| Time path, datetime `x` | `timeseries` |
| Curve or profile across tenors, strikes, or buckets | `multi_line` |
| X–Y relationship | `scatter`; grouped relationships → `scatter_multi` |
| Categorical comparison | `bar` / `bar_horizontal` |
| Matrix | `heatmap` |
| Distribution | `histogram` / `boxplot` |
| Additive time-series components, all same-sign | `area` |
| Additive components that change sign over time | `contribution` |
| A single period's decomposition, no time axis | `bar`, one bar per component; `waterfall` when the point is the bridge to a total |
| Forecast fan, confidence interval, or range around a path | `band` |
| Part-to-whole | `donut` |
| Current value inside a range | `bullet` |
| Additive bridge between two points in time | `waterfall` |
| Two to six related stories | composite helper; see `chart_context_composites.md` |
| Seven to 36 same-shape entities | facet grid; see `chart_context_grids.md` |
| Structured watchlist, tape, calendar, snapshot, or trade list | `make_table`; see `chart_context_tables.md` |

For freeform analysis, prefer a relationship-bearing shape over a descriptive
single line: scatter with trendline, lead-lag, phase orbit, normalized
co-movement, or a level-plus-change composite. Use a single chart when there is
one story; two panels are the default for compare/contrast.

Reach for a composite whenever the answer is an argument rather than a single
observation, and give each panel a job the others do not do: setup then payoff,
level then change, driver then outcome, cross-section then history, or claim
then falsification test. Panels that restate the same series in the same shape,
or that bundle unrelated charts onto one canvas, waste the layout—cut back to
one chart, or replace the redundant panel with the view that answers the
question the first panel raises.

## 3. Plot-ready data contract

The engine handles structural mechanics, not economic meaning:

1. Resolve units before plotting. Never guess whether `0.042` means 4.2%,
   0.042%, or 4.2 bp.
2. Counts are integers everywhere they are written, including a markdown table
   typed straight into a reply: 171 observations, 2,350 rows. Decimals belong
   to measured quantities -- levels, yields, ratios -- where 4.00 carries the
   precision it shows.
3. Choose the duplicate/revision policy explicitly. Keep one observation per
   intended `(x, series)` unless the chosen distribution chart needs raw rows.
4. Quantitative mapping fields must be numeric. Parse commas, currency,
   percentages, and blanks only after choosing the intended unit.
5. Normalize category identifiers used for joins and exact series binding
   (`strip`, case, aliases) before charting.
6. A single value axis must carry one unit family. Normalize, split into
   panels, or declare a dual axis when units differ.
7. Check that filters leave rows and valid mapped values. Empty frames raise.
   Do not delete outliers or fill missing values merely to make a chart pass.
   Decide whether they are errors, genuine observations, or missing coverage.
8. Keep sparse projections at native dates; do not forward-fill them onto a
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
`caption` wins. Never invent a source. `intent` is `explore` (default),
`publish` (700×400), or `monitor` (500×300). Canvas dimensions are otherwise
engine-selected.

Axis titles live only in `mapping`: `mapping['x_title']`,
`mapping['y_title']`, `mapping['y_title_right']`. There is no top-level
axis-title kwarg. Leave `interactive`, `auto_beautify`, `dimension_preset`, and
runtime-injected kwargs at their defaults unless an external artifact
constraint explicitly requires otherwise.

A session run also registers the artifact with an interactive editor the user
opens by clicking the artifact in place. Never mint or surface an editor link;
say "you can edit the chart by clicking on it" (or the table). The editor
changes what the chart shows as well as how it looks — window a date or
numeric axis, sort a categorical one, transform a series, add or drop lines,
draw an annotation. Build what was asked for regardless; what the editor
absorbs is the open-ended follow-on, so "let me try a few cuts of this" is an
editor answer rather than repeated re-runs. It is still a per-artifact
companion, not a dashboard: live filtering, scheduled refresh, or
cross-widget interaction is a `dashboards` task.

Studio-generated code carries the edit as a pandas preamble above the call —
the transform, the lifted column, the dropped series. Keep the whole block;
point `df` at a fresh pull and the edits re-apply. Anything the call cannot
express is named in comments at its foot.

### Kwarg placement contract

Choose the surface first, then its kwargs. Do not flatten or move keys between
surfaces:

| Surface | What belongs there | Common wrong placement |
|---|---|---|
| `make_chart(...)` | `df`, `chart_type`, `mapping`; title/source/caption; `annotations`, `layers`; facet layout controls; save path | Colour, opacity, axis-title, dual-axis, and chart-encoding keys do **not** belong at top level |
| `mapping={...}` | Data fields, axis titles, and chart-specific encoding/configuration listed in §6 or a topic document | `title`, `source`, `annotations`, `layers`, `facet_cols`, `same_scale`, and save kwargs do **not** belong in `mapping` |
| `VLine(...)`, `Band(...)`, etc. | Only that annotation constructor's coordinates and style parameters | Annotation coordinates/style do not belong in `mapping` or at `make_chart` top level |
| `layers=[{...}]` | Only the strict layer dictionaries in `chart_context_annotations.md` | Do not pass annotation objects or arbitrary Vega-Lite dictionaries |
| `ChartSpec(...)` | Per-panel `df`, `chart_type`, `mapping`, text, annotations, and layers | `dimension_preset`, spacing, filename, and save path belong on `make_*pack_*` |
| `make_table(...)` | Table kwargs from `chart_context_tables.md`; there is no `mapping` | Chart colour or chart mapping kwargs do not apply |

Unknown `mapping` keys, unexpected top-level `make_chart` kwargs, malformed
layer dictionaries, and engine-only keys raise `ValidationError` with a
placement or spelling hint. `dual_axis_config` is engine-managed; never pass
it.

Canonical names where a generic plotting prior suggests otherwise: `color`
(the categorical field), `x_title` / `y_title` (axis titles), `value` (heatmap
magnitude), `x_timezone` (display clock), `color_sort` (legend order).

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

## 5. Hard readability gates

The engine raises rather than truncating. These are ceilings, not targets.

| Gate | Current hard limit | Authoring action |
|---|---:|---|
| Lines per `multi_line` / `timeseries` / `area` panel | 6 | Aim for ≤4; split, facet, or aggregate |
| Value-axis title (`y_title`, `y_title_right`; `x_title` on horizontal bars) | 28 characters | Aim for concise metric + unit |
| Auto end-label series name | 32 characters | Rename categories before charting |
| Bar / `contribution` category label | 22 characters | Abbreviate in the DataFrame |
| Heatmap row or column label | 20 characters | Abbreviate in the DataFrame |
| Named categories vs canvas (`bar`, `bar_horizontal`, `heatmap` columns) | Every name must be labelled; the engine rotates and shrinks to fit, never hides one, and raises when it cannot. Date columns thin instead, including a `contribution` period axis that came from datetime | Aggregate or take the top-N, render standalone instead of in a composite cell, transpose a wide heatmap, or switch to `bar_horizontal` for long lists |
| Scatter relationship | At least 8 distinct visible `(x, y)` coordinates | Widen window or use line/bar/table |
| Series horizontal extent (`multi_line` / `timeseries` / `area` / `band`) | Every series needs ≥2 distinct `x` values and ≥10% of the x domain | Bind `x` to the axis the data varies along |
| Series vertical share (`color`-split `multi_line` / `timeseries`) | Every series needs ≥10% of the y span, and adjacent series means stay within 3× the widest single span | Pass `y_title_right` naming the secondary metric and unit: inert when one axis suffices, and when it does not the engine routes the magnitude clusters to a dual axis in one pass. Standalone charts only — inside a composite cell declare `dual_axis_series` as well. Otherwise 2-pack, rebase to 100, or facet |
| Categorical colour / donut slices | 10 categories | Filter or aggregate to `Other` |
| Composite super-title / super-subtitle | `3 x int(row_px / (font_px x 0.55))` characters, where `row_px = cols x chart_width + (cols - 1) x 20` for the chosen layout and `dimension_preset`, and `font_px` is 32 (title) / 22 (subtitle). Across the presets that runs 63 to 159 characters for the title, 93 to 231 for the subtitle | Write to the 63 / 93 floor and any preset takes it; name a wider preset and spend its full budget |
| `make_table` printed width | Body text prints at `body_font_size x 468 / canvas_px` and must clear 6pt, so the canvas stays under `78 x body_font_size` px, i.e. about 140 characters across one row (the widest cell of each column, summed), less ~2.5 per column for padding | Transpose, split by column group, drop or aggregate columns, shorten headers; the engine wraps text columns toward their floors to reach it |
| Composite / facet count | Packs 2–6; facets 7–36 | See the composites or grids document |
| `PlotText.text` | 10 words (aim ≤8) | Use caption/side text for longer prose |

Long labels are named in the error with an actionable repair. Never pre-truncate
with ellipses.

`x` is the axis the data varies along, which for a cross-section is the strike /
tenor / maturity / bucket, not the quote timestamp the pull happened to carry
alongside it. Put the as-of time in the title or subtitle. Never run
`pd.to_datetime()` on a measured quantity to make it "axis-like" — small numbers
become nanoseconds after 1970 and the axis renders as a clock.

## 6. Chart types and core mapping

### 6.1 Type catalog

| `chart_type` | Required mapping | Core rule |
|---|---|---|
| `timeseries` | datetime `x`, `y`; optional `color` | `x` must be a datetime column; any other dtype raises. Convert with `pd.to_datetime()` first |
| `multi_line` | `x`, `y`; optional `color` | Datetime path, or an ordinal curve when `x` is categorical (tenors, strikes, buckets) |
| `scatter` | `x`, `y` | At least 8 distinct visible coordinates |
| `scatter_multi` | `x`, `y`, `color` | Grouped scatter; `trendlines=True` fits per group |
| `bar` | categorical `x`, numeric `y` | Categorical only, never raw datetime |
| `bar_horizontal` | numeric `x`, categorical `y` | Prefer for longer category labels |
| `heatmap` | `x`, `y`, `value` | Cell magnitude is `value`, not `color` |
| `histogram` | `x` | Distribution of one numeric field |
| `boxplot` | categorical `x`, numeric `y` | Compare distributions |
| `area` | `x`, `y`; optional `color` | Stacked series require common x coverage and non-negative values |
| `contribution` | `x`, numeric `y`, `color` | Signed stack per period plus an automatic net-total line; `color` is the component |
| `band` | `x`, `y`, `y_low`, `y_high` | One subject line plus its interval; `x` may be a date, a numeric offset, or an ordered category |
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

# Line style by a nominal grouping column; legend is opt-in
{"x": "date", "y": "value", "color": "pair",
 "strokeDash": "pair_tier", "strokeDashLegend": True}

# Heatmap: long, wide, or an indexed matrix
{"x": "tenor", "y": "country", "value": "yield_pct"}

# Range-dot / percentile screen: use chart_type="bullet"
{"y": "metric", "x": "current", "x_low": "low", "x_high": "high",
 "color_by": "zscore", "label": "display_value"}

# Contribution: one row per (period, component); net line is automatic
{"x": "date", "y": "contribution", "color": "component",
 "y_title": "Contribution (pp)"}

# Forecast fan: leave the interval columns NaN over history
{"x": "date", "y": "core_cpi",
 "y_low": ["p25", "p05"], "y_high": ["p75", "p95"]}

# Same fan when actuals and forecast arrive as separate columns
{"x": "date", "y": ["cpi_yoy", "fc_median"],
 "y_low": ["p25", "p05"], "y_high": ["p75", "p95"]}

# Envelope vs a reference path (event study, seasonal range)
{"x": "month", "y": "current_cycle", "y_ref": "prior_median",
 "y_low": "prior_min", "y_high": "prior_max"}
```

| Mapping key | Meaning |
|---|---|
| `x`, `y`, `color` | Primary fields; `y` may be a list for line/area auto-melt, or for `band` to join actuals and forecast into one path |
| `x_title`, `y_title`, `y_title_right` | Semantic axis title, including unit |
| `x_sort`, `y_sort`, `color_sort`, `value_sort` | Explicit display order; use `color_sort` as the canonical legend/category order |
| `x_type` | Force ordinal for genuine categories such as tenors; on a datetime column the engine materialises house-style date labels on evenly spaced bands |
| `x_timezone` | Intraday display clock; default `America/New_York` |
| `legend` | Explicit legend override; normally leave automatic |
| `trendline`, `trendlines` | Overall scatter fit / per-group fits |
| `size` | `scatter`: column name bound to the dot-size channel for a bubble scatter |
| `connect`, `order` | Ordered scatter path; incompatible with trendline |
| `zero_fill`, `zero_fill_baseline` | Single-line above/below-baseline fill |
| `stack` | `bar`/`area` with colour: stacked by default; `False` groups/layers |
| `strokeDash`, `strokeDashScale`, `strokeDashLegend` | Single-axis line-style encoding |
| `value`, `theta`, `type` | Heatmap value, donut magnitude, waterfall type |
| `y_low`, `y_high` | `band` interval bounds; equal-length lists give nested levels, paired by position (`y_low[0]` with `y_high[0]`) |
| `y_ref` | `band`: optional dashed reference path inside the interval |
| `net`, `net_label` | `contribution`: `True` sums the components (default), a column name uses a published total, `False` drops the line; `net_label` names it (default `Total`) |
| `color_sort` on `contribution` | Sets stack order as well as legend order — first entry sits nearest the zero line |
| `bins` / `maxbins`, `bin_extent` | Histogram bins and range |
| `extent` | Boxplot whisker IQR multiplier; default 1.5 |
| `scale_type` | `linear` / `log` for line/timeseries/scatter only |
| `orientation` | `bar`: force `vertical` instead of automatic horizontal routing |
| `x_low`, `x_high`, `color_by`, `label`, `marker_size` | Bullet range, marker colour metric, optional label, marker area (default 200) |
| `dual_axis_series`, `dual_axis_bind`, `invert_right_axis` | See `chart_context_dual_axis.md`; `dual_axis_config` is engine-managed |
| `facet`, `facet_order`; `facet_cols`, `same_scale`, `share_color` top-level | See `chart_context_grids.md` |
| `color_scheme`, `color_range`, `color_map`, `opacity`, `opacity_map` | See `chart_context_colors.md` |

### 6.3 Type-specific decisions

- `multi_line` / `timeseries` auto-add end-of-line labels on a single axis.
  Dual-axis and facet charts use legends/headers instead.
  Alternating-series oscillation, extreme missing coverage, and incompatible
  y-scales raise with the required reshape.
- Intraday line x values should stay datetime-like. Do not pre-format clock
  strings or force ordinal; set `x_timezone` only when ET is wrong.
- `scatter` + `connect=True` creates an ordered phase path and needs `order`
  or temporal/numeric `color`. See `chart_context_colors.md` to override its gradient.
- `bar` / `bar_horizontal` are categorical comparisons. Mixed value units on
  one bar axis raise. Grouped bars (`stack=False`) do not render annotations.
- `heatmap` accepts tidy long data, an unambiguous wide frame, or a meaningful
  indexed matrix. Numeric values use a quantitative scale; categorical bins
  may have at most 10 ordered labels via `value_sort`.
- `area` stacks by default when `color` is present, and only holds for
  same-sign components. Misaligned calendars or negative stacked values
  raise; align the series, use `stack=False`, switch to `multi_line`, or move
  to `contribution`, which is built for components that cross zero.
- `contribution` is the running counterpart to `waterfall`: a waterfall
  bridges one start to one end, a contribution chart repeats the
  decomposition every period. Pass tidy long data, one row per
  `(period, component)`. A datetime `x` is converted to house period labels
  automatically — do not pre-format it. Long windows thin the axis ticks to
  year (or coarser) labels the way a date column does; every bar still draws.
  The net line, the zero rule, and the
  per-period value labels are engine-supplied; `net` only needs naming when
  the published total differs from the sum of the components. A named `net`
  column sits on the components' own axis — repeat the period's total on
  every row of that period, and keep it in the same unit as `y`, since a
  level plotted over contributions warns and reads wrong.
- `band` carries one subject line. It is the right type whenever the frame
  already contains bounds — percentiles, min/max, standard-error legs. Do not
  plot the bounds as extra `multi_line` series; that is the shape `band`
  replaces. Bounds may be a single pair or equal-length lists for nested
  intervals, paired by position and drawn widest-first, so the levels grade
  themselves and their order in the list does not matter. Rows whose bounds
  are all NaN are read as history, which is what splits a forecast fan into a
  solid actual segment, a dashed projection, and a divider; an all-bounded
  frame is simply an envelope. Leave those bounds NaN — the sparse-column
  warning does not apply to them. When the actual path and the projection
  arrive as separate columns, pass both to `y` as a list, actuals first, and
  the engine joins them into one line; no pandas preamble. Add `y_ref` when the reader needs the band's
  own centre alongside the subject line — that is still one subject, not two
  series. Band levels are not labelled on the canvas, so name them in the
  subtitle ("shaded 50% and 90% intervals"). The forecast divider is drawn
  for you, so do not add a `VLine` at the handoff. For several banded
  series, use one panel each via a composite.
- Annotations work normally on both types and read against the axis the
  builder drew, so a threshold inside the ribbon or a rule at zero survives.
  On `contribution` an annotation's `x` may be the date you have; the engine
  translates it to the rendered period label.
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

For two or more chart calls, see `chart_context_composites.md` and use
`build_charts()` rather than a bare loop. A failed batch or composite surfaces
all named defects; fix all of them and rebuild the complete set. Never silently
substitute a different layout—if the requested shape is analytically invalid,
explain the constraint and offer the engine-directed alternatives.
