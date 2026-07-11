# Chart specifications

- **Context ID:** `echarts.charts`
- **Owns:** `chart.catalog`, `chart.mapping`, `chart.annotation`, `chart.popup`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#manifest-skeleton), [recipes.md](recipes.md#data-archetypes) for analytical choice, and [template_crud.md](template_crud.md#widget-operations) for edits.

## Chart widget

Prefer high-level `spec`:

```python
{
    "widget": "chart",
    "id": "curve",
    "w": 6,
    "h_px": 400,
    "title": "UST curve",
    "subtitle": "Current yield",
    "spec": {
        "chart_type": "multi_line",
        "dataset": "rates",
        "mapping": {
            "x": "date",
            "y": ["us_2y", "us_10y"],
            "y_title": "Yield (%)",
        },
    },
}
```

Alternatives:

- `ref`: relative path to a pre-emitted ECharts option;
- `option`: inline raw ECharts option.

Use these only when the high-level builder cannot represent the intended product. Widget `title` and `subtitle` belong beside `spec`, never inside it. Chart widths are 4 or 6 in a 12-column layout.

## Chart-type catalog (30)

The closed chart-type enum is:

`line`, `multi_line`, `bar`, `bar_horizontal`, `scatter`, `scatter_multi`, `scatter_studio`, `area`, `heatmap`, `correlation_matrix`, `pie`, `donut`, `boxplot`, `histogram`, `bullet`, `sankey`, `treemap`, `sunburst`, `graph`, `candlestick`, `radar`, `gauge`, `calendar_heatmap`, `funnel`, `parallel_coords`, `tree`, `waterfall`, `slope`, `fan_cone`, `marimekko`

| `chart_type` | Required mapping |
|---|---|
| `line` | `x`, `y`; optional `color` |
| `multi_line` | `x`, `y` list, or scalar `y` + `color` |
| `bar` | category `x`, numeric `y`; optional `color`, `stack` |
| `bar_horizontal` | numeric `x`, category `y`; optional `color`, `stack` |
| `scatter` | `x`, `y`; optional `color`, `size`, `trendline` |
| `scatter_multi` | `x`, `y`; normally `color`; optional `trendlines` |
| `scatter_studio` | no required mapping; author whitelists viewer choices |
| `area` | `x`, `y`; optional `color` |
| `heatmap` | categorical `x`, categorical `y`, numeric `value` |
| `correlation_matrix` | numeric `columns` list |
| `pie` | `category`, `value` |
| `donut` | `category`, `value` |
| `boxplot` | category `x`, numeric `y` |
| `histogram` | `x`; optional `bins`, `density` |
| `bullet` | category `y`, current `x`, `x_low`, `x_high` |
| `sankey` | `source`, `target`, `value` |
| `treemap` | `path` + `value`, or `name` + `parent` + `value` |
| `sunburst` | `path` + `value`, or `name` + `parent` + `value` |
| `graph` | `source`, `target`; optional numeric `value`/`weight`, `node_category` |
| `candlestick` | `x`, `open`, `high`, `low`, `close` |
| `radar` | `category`, `value`; optional `series` |
| `gauge` | `value`; optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`; optional `year` |
| `funnel` | `category`, `value` |
| `parallel_coords` | numeric `dims` list; optional `color` |
| `tree` | `name`, `parent` |
| `waterfall` | category `x`, signed `y`; optional `is_total` |
| `slope` | two-snapshot `x`, numeric `y`, entity `color` |
| `fan_cone` | `x`, central `y`, non-empty `bands` list |
| `marimekko` | categorical `x`, categorical `y`, numeric `value` |

Unknown chart types, missing mapping keys/columns, and wrong numeric/categorical roles are diagnostics. Author from the actual persisted dataset schema.

## XY mappings

| Key | Purpose |
|---|---|
| `x`, `y` | Primary fields; `y` may be a wide-form list |
| `color` | Long-form grouping field |
| `x_title`, `y_title`, `y_title_right` | Plain-English units/axis labels |
| `x_sort` | Explicit category order |
| `x_type` | Force `category`, `value`, or `time` |
| `invert_y`, `invert_right_axis` | Reverse scale direction |
| `x_log`, `y_log` | Log scales |
| `stack` | Stacked/grouped bars or areas |
| `dual_axis_series` | Series assigned to right axis |
| `axes` | Explicit multi-axis definitions |
| `strokeDash`, `strokeDashScale`, `strokeDashLegend` | Semantic dash encoding |
| `trendline`, `trendlines` | Overall/grouped OLS |
| `size` | Scatter marker magnitude |
| `size_min`, `size_max` | Marker pixel range; defaults 6/28 |
| `size_lo`, `size_hi` | Fixed data-space marker scale |
| `bins`, `density` | Histogram configuration |

`strokeDash` names a persisted semantic-state column. Pair it with `strokeDashScale: {"domain": [...], "range": [[solid_on, solid_off], [dash_on, dash_off], ...]}` in matching order; `[1, 0]` is solid and `[8, 3]` is dashed. Set `strokeDashLegend: true` only when the dash-state legend adds information beyond the color legend.

`dual_axis_series` must name concrete emitted series, not source columns. When scalar `y` is split by both `color` and `strokeDash` with `strokeDashLegend: true`, each emitted name is exactly `<color value> — <strokeDash value>` using space, em dash, space. For example, `color="metric"` values `level`/`change` and `strokeDash="state"` values `actual`/`estimate` emit `level — actual`, `level — estimate`, `change — actual`, and `change — estimate`; assign the latter two to the right axis with `dual_axis_series: ["change — actual", "change — estimate"]`.

Line, `multi_line`, and `area` have a hard cap of four visible y-series in both wide and long form. If five or more series are all load-bearing, preserve every series in explicit small multiples: create separate chart widgets with at most four series each, use the same x field/range, and place them in 2-up or 3-up rows. Do not request one over-cap chart and do not silently drop series.

### Multi-axis

For two units use `dual_axis_series`. For a small number of independently scaled series:

```python
"mapping": {
    "x": "date",
    "y": ["spx", "ust_10y", "dxy", "wti"],
    "axes": [
        {"side": "left", "title": "SPX", "series": ["spx"],
         "format": "compact"},
        {"side": "right", "title": "UST 10Y", "series": ["ust_10y"],
         "format": "percent", "invert": True},
        {"side": "left", "title": "DXY", "series": ["dxy"]},
        {"side": "right", "title": "WTI", "series": ["wti"],
         "format": "usd"},
    ],
}
```

Axis fields include `side`, `title`, `series`, `invert`, `log`, `min`, `max`, `format`, `offset`, `scale`, and `color`. Prefer Index=100 or small multiples when independent axes make level comparison misleading.

## Presentation

Common mapping/spec controls:

| Key | Purpose |
|---|---|
| `legend_position`, `legend_show` | Legend placement/visibility |
| `series_labels`, `humanize` | Persisted-name display mapping |
| `x_date_format` | Date label formatting |
| `y_min`, `y_max`, `x_min`, `x_max` | Fixed ranges |
| `y_format`, `x_format` | `percent`, `bp`, `usd`, `compact`, or JS formatter |
| `grid_padding` | `{top, right, bottom, left}` |
| `show_grid`, `show_axis_line`, `show_axis_ticks` | Axis chrome |
| `series_colors` | Stable field-to-color mapping |
| `tooltip` | Trigger, precision, formatter, visibility |
| `palette`, `theme` | Per-spec visual override |
| `stat_strip` | Toggle eligible time-series stat strip |
| `chart_zoom` | `true` (default), `false`, or `{inside, slider}` booleans |

Numeric display precision is capped at five decimals. Use units in axis titles and provenance; do not rely on hover context alone.

Time-axis charts inject both inside and slider data zoom when `spec.chart_zoom` is omitted or `true`. Set `spec.chart_zoom: {"inside": true, "slider": false}` for inside-only zoom or `false` to disable both. A link with `sync: ["dataZoom"]` synchronizes zoom windows that already exist; it does not enable zoom.

Heatmap-style controls include:

`show_values`, `value_decimals`, `value_formatter`, `value_label_color`, `value_label_size`, `colors`, `color_palette`, `color_scale`, `value_min`, `value_max`

`colors` is an ordered list of at least two CSS colors and overrides `color_palette`. For a centered discrete-diverging 15-step heatmap, supply exactly 15 low→high stops with the neutral color at index 7, set `color_scale: "diverging"`, and pin symmetric `value_min = -M`, `value_max = M`, where `M = max(abs(requested lower bound), abs(requested upper bound))`. A canonical 15-step ramp is `["#67001F","#8A1538","#B2182B","#D6604D","#F4A582","#F7C6B6","#FDE0DD","#F7F7F7","#DDEBF7","#BDD7EE","#92C5DE","#67A9CF","#4393C3","#2166AC","#053061"]`.

Pin value range when refresh-to-refresh color comparability matters.

## Manifest computed columns

A computed dataset slot is self-contained under the chart route:

```python
"datasets": {
    "rates": {"source": []},
    "spreads": {
        "from": "rates",
        "compute": {
            "us_2s10s_bp": "(us_10y - us_2y) * 100",
            "us_10y_z_60": "zscore(us_10y, 60)",
        },
    },
}
```

`from` names one declared source dataset. `compute` maps new column names to expression strings; expressions run in declaration order, so a later expression may use an earlier computed column. Allowed syntax is numeric constants, column names, parentheses, unary `+`/`-`, arithmetic `+ - * / // % **`, and these functions:

| Function | Contract |
|---|---|
| `log`, `log10`, `log2`, `exp`, `sqrt`, `abs`, `sign`, `round` | Elementwise series transform |
| `mean`, `std`, `min`, `max`, `sum` | Full-column statistic repeated to row shape; sample standard deviation uses `ddof=1` |
| `zscore(x)` | Full-column `(x - mean) / std`, sample standard deviation |
| `zscore(x, n)` | Rolling `n`-row z-score with `min_periods=2`, sample standard deviation |
| `rolling_mean(x, n)` | Rolling mean with `min_periods=1` |
| `rolling_std(x, n)` | Rolling sample standard deviation with `min_periods=2` |
| `pct_change(x, n)`, `diff(x, n)`, `shift(x, n)` | `n`-row change/lag; `pct_change` returns percent points |
| `clip(x, lo, hi)`, `index100(x)`, `rank_pct(x)` | Bounds, first-valid=100 index, percentile rank in percent |

Attributes, subscripts, lambdas, comprehensions, and arbitrary function calls are rejected. Use a persisted `TRANSFORMS` function for joins, resampling, grouped/window logic, or multi-step validation. The compiler materializes `source` and computed `field_provenance`; chart mappings reference the emitted names.

## Annotations

The closed annotation-type enum is:

`hline`, `vline`, `band`, `arrow`, `point`

| Type | Required position |
|---|---|
| `hline` | `y` |
| `vline` | `x` |
| `band` | `x1` + `x2`, or `y1` + `y2` |
| `arrow` | `x1`, `y1`, `x2`, `y2` |
| `point` | `x`, `y` |

```python
"annotations": [
    {"type": "hline", "y": 2, "label": "Target",
     "color": "#666", "style": "dashed"},
    {"type": "vline", "x": "2022-03-15", "label": "Liftoff"},
    {"type": "band", "x1": "2020-03-01", "x2": "2020-06-01",
     "label": "Stress window", "opacity": 0.25},
    {"type": "point", "x": "2023-06-15", "y": 4.4, "label": "Peak"},
]
```

Author-friendly positional aliases include `value`, `at`, `x_value`, `y_value`, `x_start`, `x_end`, `y_start`, and `y_end`. Prefer canonical positions. Common styling fields are `label`, `color`, `style`, `stroke_dash`, `stroke_width`, `label_color`, `label_position`, `opacity`, and `font_size`.

Annotate events/regimes that change interpretation. Charts without Cartesian axes ignore annotations.

## Specialized charts

### Scatter studio

Use when the viewer should choose x, y, color, size, transforms, window, outlier policy, and regression.

Mapping keys:

- `x_columns`, `y_columns`, `color_columns`, `size_columns`;
- `x_default`, `y_default`, `color_default`, `size_default`;
- `order_by`, `label_column`;
- `x_transform_default`, `y_transform_default`.

Optional `studio`:

```python
"studio": {
    "transforms": [
        "raw", "log", "change", "pct_change", "yoy_pct",
        "zscore", "rolling_zscore_252", "rank_pct",
    ],
    "regression": ["off", "ols", "ols_per_group"],
    "regression_default": "off",
    "windows": ["all", "252d", "504d", "5y"],
    "window_default": "all",
    "outliers": ["off", "iqr_3", "z_4"],
    "outlier_default": "off",
    "show_stats": True,
}
```

Order-aware transforms require `order_by`. Filter changes recompute visual/stats state against the filtered rows.

### Correlation matrix

```python
{
    "chart_type": "correlation_matrix",
    "dataset": "returns",
    "mapping": {
        "columns": ["spx", "ust", "dxy", "wti", "gold"],
        "method": "pearson",
        "transform": "pct_change",
        "order_by": "date",
        "window": "252d",
        "window_options": ["all", "63d", "126d", "252d", "504d"],
        "min_periods": 20,
        "show_values": True,
        "value_decimals": 2,
    },
}
```

Use `correlation_matrix` for a wide panel the engine transforms/correlates; use `heatmap` for precomputed categorical cells. `method` is `pearson` or `spearman`.

### Finance shapes

```python
{"chart_type": "waterfall", "dataset": "pnl",
 "mapping": {"x": "factor", "y": "delta_mm", "is_total": "is_total"}}
```

```python
{"chart_type": "slope", "dataset": "snapshots",
 "mapping": {"x": "snapshot", "y": "spread_bp", "color": "issuer"}}
```

Slope `x` must contain exactly two distinct snapshots.

```python
{
    "chart_type": "fan_cone",
    "dataset": "forecast",
    "mapping": {
        "x": "date",
        "y": "median",
        "bands": [
            {"lower": "p10", "upper": "p90", "label": "10–90"},
            {"lower": "p25", "upper": "p75", "label": "25–75"},
        ],
    },
}
```

```python
{"chart_type": "marimekko", "dataset": "allocation",
 "mapping": {"x": "sector", "y": "size_bucket", "value": "market_value"}}
```

## Chart popup

Simple point detail:

```python
{
    "click_popup": {
        "title_field": "entity",
        "popup_fields": ["entity", "x", "y", "as_of"],
    }
}
```

Rich detail:

```python
{
    "click_popup": {
        "detail": {
            "sections": [{
                "type": "chart",
                "dataset": "entity_history",
                "row_key": "entity",
                "filter_field": "entity",
                "mapping": {"x": "date", "y": "value"},
            }]
        }
    }
}
```

For every rich chart/table section, `row_key` is a column on the clicked chart's dataset, `filter_field` is a column on the detail dataset, and representative values must overlap. Missing datasets/columns, non-overlapping keys, and empty explicit popup objects are blocking diagnostics. Use `click_popup: false` for deliberate opt-out.

## Chart judgment

- Choose chart type from the analytical question and data shape.
- Keep no more than four overlaid line series.
- Use stable persisted column names; display labels belong in mapping.
- Verify units, frequency, as-of alignment, and provenance.
- Keep chart ids stable through targeted edits.
- Treat popup join keys as data contracts, not presentation hints.
- Use a persisted transform when a computation exceeds the [manifest computed-column grammar](#manifest-computed-columns).
