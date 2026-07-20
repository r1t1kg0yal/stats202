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

Use these only when the high-level builder cannot represent the intended product. Widget `title` and `subtitle` belong beside `spec`, never inside it. Standard chart widths are 4 or 6 in a 12-column layout. A single decision-critical full-width chart may set `hero: true` and `w: 12`; it must occupy its own row.

## Chart-type catalog (31)

The closed chart-type enum is:

`line`, `multi_line`, `bar`, `bar_horizontal`, `scatter`, `scatter_multi`, `scatter_studio`, `area`, `heatmap`, `geo_map`, `correlation_matrix`, `pie`, `donut`, `boxplot`, `histogram`, `bullet`, `sankey`, `treemap`, `sunburst`, `graph`, `candlestick`, `radar`, `gauge`, `calendar_heatmap`, `funnel`, `parallel_coords`, `tree`, `waterfall`, `slope`, `fan_cone`, `marimekko`

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
| `geo_map` | `region`, numeric `value`, and `map` asset name |
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

### Geographic maps

`geo_map` never fetches remote map data. Embed the exact GeoJSON asset in the manifest so the compiled dashboard remains self-contained:

```python
"map_assets": {
    "countries": {
        "geojson": country_feature_collection,
        "name_property": "name",
        "aliases": {"United States of America": "United States"},
    },
},
# chart mapping
{"region": "country", "value": "growth_pct", "map": "countries"}
```

| Asset key | Contract |
|---|---|
| `geojson` | Required non-empty GeoJSON `FeatureCollection`; features are `Polygon`/`MultiPolygon` |
| `name_property` | Optional feature-property key, default `"name"`; use `"$id"` for feature ids |
| `aliases` | Optional exact `{dataset_value: canonical_geojson_value}` mapping |

Aliases belong only at `map_assets.<map>.aliases`, never in chart `mapping`.
GeoJSON feature keys must be unique. After aliases, every non-null dataset
region must match a feature key and appear in exactly one dataset row; unknown
keys or multiple rows resolving to one canonical region block compilation.
Aggregate duplicates upstream with an explicitly chosen statistic. `roam` is
an optional boolean mapping key (default `false`) that enables pan/zoom;
`selected_mode` controls ECharts region selection and defaults to `false`.
Optional `value_min`, `value_max`, `series_name`, and
`visual_map_orient`/`visual_map_left`/`visual_map_bottom` configure the scale
and legend. Fuzzy geographic matching and CDN fallbacks are intentionally
absent.

## Pre-render data integrity

Every mapped time series is profiled after compute/transform
materialization and again in the default filter state. Compilation blocks
positive/negative infinity, invalid log domains, backward time ordering,
conflicting duplicate timestamps, and empty effective x/y pairs. Null/NaN
observations are missing values rather than infinities: isolated or bounded
internal/edge runs remain warning evidence unless an explicit missingness
expectation is breached. Warnings also surface irregular gaps/frequency,
stale tails, scale-dominating observations, abrupt breaks, and constant
series.

Automatic time inference requires an explicit four-digit year in at least
80% of non-null string labels. Bare month names and two-digit month/year
labels remain categorical, so pandas-version differences cannot silently
turn a category axis into a time axis. Normalize genuinely temporal labels
upstream to unambiguous full-year values and declare `quality.time_field`.

Persist optional expectations in `manifest_template.json` at
`datasets.<name>.quality`; the example below is the value of
`datasets.rates`:

```python
"rates": {
    "source": rates,
    "quality": {
        "time_field": "date",
        "expected_frequency": "B",
        "max_internal_gap": "5D",
        "max_staleness": "3D",
        "duplicate_policy": "error",
        "severity": "error",
        "fields": {
            "us_10y": {
                "domain": "positive",
                "min": 0,
                "max": 25,
                "max_missing_fraction": 0.02,
                "max_internal_na_run": 1,
                "outlier": {
                    "method": "mad",
                    "threshold": 8,
                    "max_scale_expansion": 4,
                },
                "max_step_robust_z": 10,
            },
        },
    },
}
```

Durations accept pandas-style strings or positive seconds. A field
expectation inherits `quality.severity`; a field-level `severity` overrides
it, and the default is `error` when neither is supplied. The canonical
outlier shape is exactly `{"method": "mad", "threshold": 8,
"max_scale_expansion": 4}`; aliases such as `robust_z` are invalid. With no
explicit outlier block, conservative automatic profiling uses those 8/4
thresholds and reports scale-dominating points as warnings. Omitted
`max_internal_gap` uses five times the observed median interval as a warning
threshold; omitted `expected_frequency` and `max_staleness` make no explicit
contract assertion. `duplicate_policy` defaults to `error` for conflicting
values and still warns on exact duplicate timestamps.

Set `severity: "warning"` only when a breach is known to remain renderable
and analytically usable. Warning-only findings do not block
`compile_dashboard(strict=True)`; they remain in
`DashboardResult.quality_findings` and `inspect_dashboard(FOLDER)["findings"]`.
Each structured record exposes `severity`, `code`, `path`, `widget_id`,
`dataset`, `series`, `field`, `observed`, `expected`, `examples`,
`visual_effect`, and `fix_hint`. Never clip, sort, impute, delete, or
winsorize silently. Repair a demonstrated source/transform defect; when a
flagged observation may be real, surface the evidence and ask.
For publication, `review.panel(id)` is the authoritative panel decision and
evidence surface; inspection findings are the owner-localization/diagnostic
index. Correlate shared codes, but do not report the same finding twice.

### Garbage-gate chart states

| Receipt state | Decision |
|---|---|
| Literal date formatter such as `x_date_format="MMM YY"` | `BLOCK`: ECharts repeats the literal at every tick. Use `"auto"` or an explicit JavaScript function string. |
| Gauge with non-finite/inverted bounds or a value outside its declared range | `BLOCK`: correct the units/value or set finite `min < max`; these defects cannot be acknowledged. |
| Sparse, gappy, stale, flat, spiky, or isolated spike/reversal line evidence | `REVIEW_REQUIRED`: inspect missing runs, gap/frequency evidence, scale-dominating points, reversal neighborhoods, and abrupt breaks in `review.panel(id)`; preserve ambiguous source values. |
| Categorical bar/waterfall marks with only zeros | `REVIEW_REQUIRED` with `data_state="ALL_ZERO"`: verify upstream values/units and make genuine zero explicit. |
| Categorical bar/waterfall marks with missing values | `REVIEW_REQUIRED` with `data_state="PARTIAL"`: distinguish genuine absence from pull/join failure; never coerce missing to zero. |

These decisions describe the Python compiler's default-filter state. Browser interactions and tool calculations need their separate runtime checks.

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

`dual_axis_series` must name concrete emitted series, not source columns. When scalar `y` is split by both `color` and `strokeDash` with `strokeDashLegend: true`, emitted names are `<color> — <strokeDash>` (em dash). ASCII ` -- ` is accepted and normalized. A mismatch fails with the concrete emitted-series list in `fix:`. Example: `dual_axis_series: ["change — actual", "change — estimate"]`.

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
| `series_labels` | Exact display names `{raw: "EUR/USD"}`; case-insensitive key match; always wins |
| `humanize` | Legend casing: `true`/`"title"` (default), `false`/`"preserve"`, or `"upper"`. Default title mode keeps ISO FX codes UPPER (`eur_3m`→`EUR 3M`, `eurusd`→`EURUSD`) |
| `x_date_format` | `"auto"` or an explicit JavaScript function string; token literals such as `"MMM YY"` block |
| `y_min`, `y_max`, `x_min`, `x_max` | Fixed ranges |
| `y_format`, `x_format` | `percent`, `bp`, `usd`, `compact`, or JS formatter |
| `grid_padding` | `{top, right, bottom, left}` |
| `show_grid`, `show_axis_line`, `show_axis_ticks` | Axis chrome |
| `spec.series_colors` | Exact series/raw-column name to validated `{light, dark}` colors |
| `tooltip` | Trigger, precision, formatter, visibility |
| `palette`, `theme` | Per-spec visual override |
| `stat_strip` | Toggle eligible time-series stat strip |
| `chart_zoom` | `true` (default), `false`, or `{inside, slider}` booleans |

Numeric display precision is capped at five decimals. Use units in axis titles and provenance; do not rely on hover context alone.

Time-axis charts inject both inside and slider data zoom when `spec.chart_zoom` is omitted or `true`. Set `spec.chart_zoom: {"inside": true, "slider": false}` for inside-only zoom or `false` to disable both. A link with `sync: ["dataZoom"]` synchronizes zoom windows that already exist; it does not enable zoom.

The resolved theme owns chart, popup, pivot/table scale, PNG, and print colors.
Series slots are assigned from stable series names, not row order;
deterministic collision resolution keeps unique names on distinct colors until
palette capacity is exhausted, including after filtering and theme toggles.
Use `gs_colorblind` for categorical accessibility or
`gs_diverging_accessible` for a diverging scale. A custom palette uses
`spec.colors = {"light": [...], "dark": [...], "role": "data_mark"}`;
equal-length arrays define corresponding light/dark slots. When exact names
must own exact colors, bypass slot assignment:

```python
"series_colors": {
    "Nominal": {"light": "#002F6C", "dark": "#74C0E3"},
    "Real": {"light": "#8A1538", "dark": "#FF8A80"},
}
```

Keys match emitted series names or raw wide-form columns. Every free-form mark
must pass contrast for its mode. Dark-mode PNG exports retain the dark
background; PDF/print intentionally switches to the light print contract,
mounts charts from every tab, opens collapsed layout groups, and prints every
filtered `data_grid` row up to `max_rows`.

Filters faithfully rebuild wide and grouped line/bar/area/scatter, stacked bar/area, pie/donut, heatmap, `geo_map`, `scatter_studio`, and `correlation_matrix`. A `dateRange` in default `mode: "view"` may also target supported data-zoom time-series charts such as candlesticks without rebuilding their series. A filter targeting any other chart shape is an explicit `filter_chart_rebuild_unsupported` error; never ship a static chart beside changing KPIs or tables.

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

For every rich chart/table section, `row_key` is a column on the clicked chart's dataset, `filter_field` is a column on the detail dataset, and representative values must overlap. Give a popup chart a stable `id` when filters or `links[].members` target it. Popup charts mount through the same controller as inline charts, so theme, legend, smoothing, zoom, click, brush, filter, and link behavior are shared. Missing datasets/columns, non-overlapping keys, and empty explicit popup objects are blocking diagnostics. Use `click_popup: false` for deliberate opt-out.

## Chart judgment

- Choose chart type from the analytical question and data shape.
- Keep no more than four overlaid line series.
- Use stable persisted column names; display labels belong in mapping.
- Verify units, frequency, as-of alignment, and provenance.
- Keep chart ids stable through targeted edits.
- Treat popup join keys as data contracts, not presentation hints.
- Use a persisted transform when a computation exceeds the [manifest computed-column grammar](#manifest-computed-columns).
