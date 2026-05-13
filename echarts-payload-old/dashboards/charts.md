# Chart specs

Spoke fetched on demand from the dashboards hub. Covers every detail of `widget: chart` — variants, the 30-type catalog, mapping keys, cosmetic knobs, annotations, the two interactive sub-types (`scatter_studio`, `correlation_matrix`), and manifest-level computed columns.

For widget-level scaffolding (`title`, `footer`, `info`, `click_emit_filter`, `click_popup`), fetch `widgets.md`.

---

## 1. Chart variants

Every `widget: chart` declares one of three variants. Use the lowest ceremony that fits.

| Variant | Shape | When |
|---------|-------|------|
| `spec` | `{chart_type, dataset, mapping, [title, palette, ...]}` | **Preferred.** LLM-friendly. |
| `ref` | `"echarts/mychart.json"` (relative path) | Pre-emitted ECharts spec on disk |
| `option` | raw ECharts option dict | Hand-crafted; you own correctness (no validation) |

`spec.dataset` references `manifest.datasets.<name>`. At compile time the source rows are materialised into a pandas DataFrame and fed into the per-chart-type builder. `ref` paths resolve relative to `base_dir` arg → loaded manifest's parent → cwd.

---

## 2. Chart-type catalog (30)

| chart_type | Required mapping keys |
|------------|------------------------|
| `line` | `x`, `y`, optional `color`. Y-series cap 4 (§3.1) |
| `multi_line` | `x`, `y` (list) OR `x`, `y`, `color`. Y-series cap 4 (§3.1) |
| `bar` | `x` (category), `y`, optional `color`, `stack` (bool) |
| `bar_horizontal` | `x` (value), `y` (category), optional `color`, `stack` |
| `scatter` | `x`, `y`, optional `color`, `size`, `trendline` |
| `scatter_multi` | `x`, `y`, `color`, optional `trendlines` |
| `scatter_studio` | none required; author-supplied whitelists drive runtime picker (§5) |
| `area` | `x`, `y` (stacked area). Y-series cap 4 (§3.1) |
| `heatmap` | `x`, `y`, `value` |
| `correlation_matrix` | `columns` (≥2 numeric), optional `transform`, `method`, `order_by`, `window`, `window_options`, `transforms` (§6) |
| `histogram` | `x`, optional `bins` (int or list of edges), `density` |
| `bullet` | `y` (cat), `x` (cur), `x_low`, `x_high`, optional `color_by`, `label` |
| `pie` | `category`, `value` |
| `donut` | `category`, `value` |
| `boxplot` | `x` (cat), `y` |
| `sankey` | `source`, `target`, `value` |
| `treemap` | `path` (list) + `value` OR `name` + `parent` + `value` |
| `sunburst` | same as treemap |
| `graph` | `source`, `target`, `value`, `node_category` |
| `candlestick` | `x`, `open`, `close`, `low`, `high` |
| `radar` | `category`, `value`, optional `series` |
| `gauge` | `value`, optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`, optional `year` |
| `funnel` | `category`, `value` |
| `parallel_coords` | `dims` (list), optional `color` |
| `tree` | `name`, `parent` |
| `waterfall` | `x` (cat), `y` (signed delta), optional `is_total` (bool col flagging totals) |
| `slope` | `x` (snapshot col with exactly 2 distinct values), `y`, `color` (per-line cat) |
| `fan_cone` | `x`, `y` (central path), `bands` (list of `{lower, upper, label?, opacity?}`) |
| `marimekko` | `x` (col-axis cat), `y` (row-axis cat), `value`, optional `order_x`, `order_y` |
| `raw` | pass `option=...` directly (passthrough) |

Unknown `chart_type` raises `ValueError`. Datetime cols auto-resolve to `xAxis.type='time'`; numeric to `'value'`; everything else to `'category'`. Missing columns raise `ValueError` listing actual DataFrame columns — no silent fallback.

**Finance-flavoured shapes:**

| Type | What it draws | Example uses |
|------|---------------|--------------|
| `waterfall` | Incremental deltas (green +, red −), full-height bar when `is_total` | P&L bridges, attribution, factor decomp |
| `slope` | N categories at two snapshots joined by sloped lines + right-edge labels | "month-end vs latest", "before vs after" |
| `fan_cone` | Central path + N stacked confidence bands, opacity declines outside-in | FOMC dot-plot fans, scenario cones |
| `marimekko` | 2D categorical proportions: x-col widths = share of total; y-cats stack proportionally | Cap-weighted allocation by sector × size |

---

## 3. Mapping keys (XY chart types)

| Key | Purpose |
|-----|---------|
| `x`, `y` | Required. `y` can be a list (wide-form multi_line) |
| `color` | Grouping column (multi-series long form) |
| `y_title` / `x_title` / `y_title_right` | Plain-English axis titles. Right-axis title for dual-axis |
| `x_sort` | Explicit category order (list of values) |
| `x_type` | Force `'category'` / `'value'` / `'time'` on ambiguous columns |
| `invert_y` / `y_log` / `x_log` | Invert single-axis y; log scale on respective axis |
| `stack` (bar) | `True` (default) = stacked, `False` = grouped |
| `dual_axis_series` / `invert_right_axis` | Right-axis series list; flip right axis (rates "up = bullish") |
| `axes` | List of axis spec dicts for N-axis time series. Takes precedence over the legacy 2-axis API |
| `strokeDash` / `strokeDashScale` / `strokeDashLegend` | Column controlling per-series dash pattern; `{"domain": [...], "range": [[1,0], [8,3]]}` explicit mapping; legend cross-product |
| `trendline` / `trendlines` (scatter) | `True` adds overall / per-group OLS line |
| `size` (scatter) | Column driving marker size. Auto-scaled to a 6-28 px range using the column's robust 5th/95th percentile, so raw revenue / market-cap / volume columns work without pre-normalising. Override with `size_min` / `size_max` (pixels) and `size_lo` / `size_hi` (data-space pin) — see below. |
| `size_min` / `size_max` (scatter) | Pixel range for `size` mapping. Defaults: 6 / 28. |
| `size_lo` / `size_hi` (scatter) | Data-space pin for the `size` mapping. Defaults to the column's 5th/95th percentile. Use when a fixed reference scale matters (e.g. comparing across reruns where the dataset extent shifts). |
| `bins` / `density` (histogram) | Int or list of bin edges (default 20); `True` normalises counts to density |

### 3.1 Y-series cap (line / multi_line / area)

Hard cap: **4 y-series**. ≥5 raises `chart_too_many_series` and blocks the build (always-blocking; the cap is non-bypassable from `compile_dashboard`). Applies to wide-form (`y: [list]` of length N) and long-form (`y: scalar` + `color: column` with N distinct values) equally; `mapping.axes` is treated as wide-form via the union of every per-axis `series` list.

| Shape | Triggers |
|-------|----------|
| Wide-form list | `mapping.y` is a list with `len(y) > 4` |
| Long-form color | `mapping.y` is a scalar AND `mapping.color` resolves to a column with `> 4` distinct non-NaN values |
| Multi-axis | union of `mapping.axes[i].series` lists exceeds 4 |

Why: more than 4 overlaid lines crowd the legend onto multiple rows, push the GS palette past its discriminable categorical width, and stop any single series from being traceable across the canvas. The five-line spaghetti chart is dashboard noise, not signal.

Corrective actions in priority order:

| Action | When |
|--------|------|
| Drop to ≤4 series (filter dataset to top-N by some criterion — largest end-of-period magnitude, alphabetical first N, peer-group membership) | Default. Cheapest path; loses no fidelity if the dropped series are tail-of-distribution |
| Bucket the rest into a synthetic "Other" series | When the count of dropped series matters but their individual identity does not |
| Split into small multiples (one widget per category, paired into 2-up rows) | When every series is load-bearing and the data deserves dedicated canvases |
| Pivot framing: `Index=100` normalisation (5 series of normalised %-from-base read more cleanly than 5 raw levels), `correlation_matrix` (replaces a 5+ multi_line of asset returns), aggregate `stat_grid` (when the question is "where do these N values land today?" not "how have they evolved?") | When the question can be answered without the time-series axis |

**Chart-specific shapes:**

| Chart | Mapping keys |
|-------|--------------|
| `sankey` / `graph` | `source`, `target`, `value`; `graph` adds `node_category` |
| `treemap` / `sunburst` | `path` + `value`, OR `name` + `parent` + `value` |
| `candlestick` | `x`, `open`, `close`, `low`, `high` |
| `radar` | `category`, `value`, optional `series` |
| `gauge` | `value`, optional `min`, `max` |
| `calendar_heatmap` | `date`, `value`, optional `year` |
| `parallel_coords` | `dims` (list), optional `color` |
| `tree` | `name`, `parent` |

**Heatmap-style** (`heatmap`, `correlation_matrix`, `calendar_heatmap`) cell-label / color keys: `show_values`, `value_decimals` (auto, clamped to global cap §4), `value_formatter` (raw JS — suppresses auto-contrast + cap), `value_label_color` (`"auto"` / hex / `False`), `value_label_size` (default 11), `colors` / `color_palette`, `color_scale` (`sequential` / `diverging` / `auto`), `value_min` / `value_max` (pin visualMap range across reruns).

**Multi-axis time series (`mapping.axes`).** Line / multi_line / area accept arbitrary independent y-axes:

```json
"mapping": {
  "x": "date", "y": ["spx", "ust", "dxy", "wti"],
  "axes": [
    {"side": "left",  "title": "SPX",     "series": ["spx"], "format": "compact"},
    {"side": "right", "title": "UST 10Y", "series": ["ust"], "invert": true, "format": "percent"},
    {"side": "left",  "title": "DXY",     "series": ["dxy"]},
    {"side": "right", "title": "WTI",     "series": ["wti"], "format": "usd"}
  ]
}
```

Per-axis keys: `side` (`left`/`right`, req), `title`, `series`, `invert`, `log`, `min`/`max`, `format` (`percent`/`bp`/`usd`/`compact` or raw JS string), `offset` (auto-stacked at 0, 80, 160, …), `scale` (default `True`), `color` (auto-tints to series' palette color for single-series axes, Bloomberg-style). Mapping-level: `axis_offset_step` (default 80), `axis_color_coding` (default `True`). Annotations target an axis via `axis: <index>` (0..N-1).

When to use: 2 axes → prefer `dual_axis_series`; 3+ across asset classes → `axes`; 3+ same unit → one axis right; 3+ different units comparing patterns → consider Index=100 normalisation instead.

---

## 4. Cosmetic / layout knobs (every chart type)

| Key | Purpose |
|-----|---------|
| `legend_position` / `legend_show` | `"top"` (default), `"bottom"`, `"left"`, `"right"`, `"none"`; explicit `True`/`False` override |
| `series_labels` / `humanize` | `{raw_name: display_name}` overrides auto-humanise; `humanize: False` disables `us_10y` → `US 10Y` |
| `x_date_format` | `"auto"` for compact `MMM D`; raw JS string for custom |
| `show_slice_labels` (pie/donut) | Keep per-slice edge labels even with top/bottom legend |
| `y_min` / `y_max` / `x_min` / `x_max` | Force axis range |
| `y_format` / `x_format` | `"percent"` / `"bp"` / `"usd"` / `"compact"` (K/M/B) or raw JS |
| `y_title_gap` / `x_title_gap` / `y_title_right_gap` | Pixels between tick labels and axis title (auto-sized by default) |
| `category_label_max_px` | Max pixel width for category-axis tick labels (default 220); longer get ellipsis |
| `grid_padding` | `{top, right, bottom, left}` overriding plot-area margins |
| `show_grid` / `show_axis_line` / `show_axis_ticks` | `False` to suppress |
| `series_colors` | `{col_name: "#hex"}` overrides palette for specific series (raw or post-humanise name) |
| `tooltip` | `{"trigger": "axis"\|"item"\|"none", "decimals": 2, "formatter": "<JS fn>", "show": False}` |

The compiler truncates long category labels to `category_label_max_px`, sizes `nameGap` from real label widths, bumps `grid.left` / `grid.bottom` for rotated axis names, auto-rotates vertical-bar / boxplot x-labels when crowded, and bumps heatmap `grid.right` to 76px for visualMap clearance.

**Per-spec overrides.** `palette`, `theme`, `annotations` may live on `spec` to override manifest defaults. Required keys: `chart_type`, `dataset`, `mapping`. Titles / subtitles live at the widget level only — `spec.title` / `spec.subtitle` are rejected by the validator.

**Global decimal cap.** Numeric values rendered anywhere are hard-capped at 5 decimal places (`config.MAX_DASHBOARD_DECIMALS`); author-supplied precision options are clamped end-to-end. Author-supplied raw JS formatters (`value_formatter`, `tooltip.formatter`, `axisLabel.formatter`) are not inspected — if you pass raw JS, you own its precision.

---

## 5. Annotations

Five types in `annotations=[...]`:

```python
"annotations": [
    {"type": "hline", "y": 2.0, "label": "Fed target", "color": "#666", "style": "dashed"},
    {"type": "vline", "x": "2022-03-15", "label": "Liftoff"},
    {"type": "band",  "x1": "2020-03-01", "x2": "2020-06-01", "label": "COVID", "opacity": 0.3},
    {"type": "arrow", "x1": "2020-04-01", "y1": 5, "x2": "2021-03-01", "y2": 8, "label": "recovery"},
    {"type": "point", "x": "2023-06-15", "y": 4.4, "label": "peak"}]
```

Common keys: `label`, `color`, `style` (`'solid'|'dashed'|'dotted'`), `stroke_dash` (`[4,4]`), `stroke_width`, `label_color`, `label_position`, `opacity` (band), `head_size` / `head_type` (arrow), `font_size` (point). `band` accepts `y1`/`y2` (horizontal band) and aliases `x_start`/`x_end`, `y_start`/`y_end`. Dual-axis: `hline` accepts `"axis": "right"`. Charts without axes (pie / donut / sankey / treemap / sunburst / radar / gauge / funnel / parallel_coords / tree) silently ignore annotations.

Annotate regime changes, policy shifts, event dates, structural breaks. Don't annotate self-evident facts (zero line on a spread, target on every CPI chart).

---

## 6. `scatter_studio` — exploratory bivariate

Use when the analyst should pick X / Y / color / size / per-axis transform / regression interactively. Author whitelists columns; regression line, R², p-value, window slicer wired automatically.

| Mapping key | Purpose |
|-------------|---------|
| `x_columns` / `y_columns` / `color_columns` / `size_columns` | Whitelisted numeric / categorical columns. Default: every numeric col for X/Y, empty for color/size |
| `x_default` / `y_default` / `color_default` / `size_default` | Initial selections |
| `order_by` | Sort key for order-aware transforms. Default: first datetime-like col. Required if any order-aware transform is in `studio.transforms` |
| `label_column` | Row label in tooltip header / `click_popup` template. Default: `order_by` |
| `x_transform_default` / `y_transform_default` | Initial per-axis transforms (default `'raw'`) |

`spec.studio` block (sibling to `mapping`, all optional):

| Key | Default |
|-----|---------|
| `transforms` | `['raw', 'log', 'change', 'pct_change', 'yoy_pct', 'zscore', 'rolling_zscore_252', 'rank_pct']` |
| `regression` / `regression_default` | `['off', 'ols', 'ols_per_group']` / `'off'` |
| `windows` / `window_default` | `['all', '252d', '504d', '5y']` / `'all'` |
| `outliers` / `outlier_default` | `['off', 'iqr_3', 'z_4']` / `'off'` |
| `show_stats` | `True`. Stats strip below canvas: `n`, Pearson `r`, `R²`, slope `beta` (SE), intercept `alpha`, RMSE, p-value |

Per-axis transforms: `raw`, `log` (drops non-positive), `change`, `pct_change`, `yoy_change`, `yoy_pct`, `zscore`, `rolling_zscore_<N>`, `rank_pct`, `index100`. Order-aware (`change`, `pct_change`, `yoy_*`, `rolling_zscore_*`) require `order_by`.

Stats strip example: `n=247  r=0.68***  R²=0.46  beta=0.42 (SE 0.03)  alpha=1.18  RMSE=0.31  p=4.2e-9`. Stars: `***` p<0.001 / `**` p<0.01 / `*` p<0.05 / `·` p<0.10. With `regression: ols_per_group` the strip lists per-color stats below the overall row. Edge cases: `n<2` → unavailable; zero X-variance suppresses the line; `log` drops negatives; filter narrowing recomputes against the filtered subset.

---

## 7. `correlation_matrix` — N×N heatmap from a column list

"How do these N series co-move?" Builder applies a per-column transform, computes the correlation matrix, emits a diverging heatmap pinned to `[-1, 1]`. Mapping `transform`, `window`, and `method` are the INITIAL state of the runtime drawer, not pins — the viewer can re-correlate against any combination without a script reload.

| Mapping key | Purpose |
|-------------|---------|
| `columns` (req) | Numeric column names, length ≥ 2 |
| `method` | `'pearson'` (default) or `'spearman'` (rank correlation; robust to monotonic non-linearity) |
| `transform` | Initial per-column transform shown in the drawer (default `'raw'`; same names as scatter_studio) |
| `order_by` | Required when `transform` is order-aware OR when `window != 'all'`. Default: first datetime-like col |
| `window` | Initial rolling window shown in the drawer. One of `window_options` (default `'all'`) |
| `window_options` | Drawer's window menu. Default `['all', '21d', '63d', '126d', '252d', '504d', '1260d']`. Each entry must be `'all'` or `'<int>d'` |
| `transforms` | Curated list of transform names the drawer offers. Default: `['raw', 'log', 'change', 'pct_change', 'yoy_pct', 'zscore', 'rolling_zscore_252', 'rank_pct']`. `raw` is always prepended |
| `min_periods` | Min overlapping non-null pairs to report (default 5); below threshold renders blank |
| `show_values` / `value_decimals` | Print correlation in cell (default `True` / `2`; clamped to global cap) |
| `value_label_color` | `"auto"` (B/W contrast), hex, or `False` |
| `colors` / `color_palette` | Override palette (default `gs_diverging`) |

Use `correlation_matrix` for wide-form time-series panels (author gives columns; builder does math + visualMap). Use `heatmap` for pre-computed bivariate cells (cross-asset returns by month, hit-rate by quintile). Author passes an explicit `subtitle` to suppress the auto-stamped `Pearson · %Δ · 63-day rolling · as of <date>` line.

Budget: ~70 KB per chart for an 8-column 5y daily panel. Cap dataset frequency or column count if a dashboard needs many corr matrices.

---

## 8. Computed columns (manifest-level expressions)

A dataset entry can declare a `compute` block of named expressions evaluated against an existing source dataset. Use this instead of computing spreads / ratios / z-scores in `build.py`. The compiler runs an AST-level whitelist (no `eval`, no `__import__`, no attribute access), materialises each output column, and auto-stamps `field_provenance` with `system: "computed"`, the recipe string, and the upstream column list.

```python
"datasets": {
    "rates": df_rates,
    "spreads": {
        "from": "rates",
        "compute": {
            "us_2s10s_bp":  "(us_10y - us_2y) * 100",
            "us_5s30s_bp":  "(us_30y - us_5y) * 100",
            "us_10y_z_60":  "zscore(us_10y, 60)",
            "spread_pct":   "pct_change(us_10y - us_2y)",
        }
    }
}
```

Cross-dataset references via `<other_ds>.<col>`. Omit `from` to append computed columns to the same dataset's source.

**Allowed function whitelist** (any other name = validation error):

| Group | Functions |
|-------|-----------|
| Arithmetic | `+ - * / % ** //`, unary `+ -` |
| Numeric | `log`, `log10`, `log2`, `exp`, `sqrt`, `abs`, `sign`, `round` |
| Aggregate | `mean`, `std`, `min`, `max`, `sum` (broadcast scalar) |
| Series | `zscore(x, window?)`, `rolling_mean(x, n)`, `rolling_std(x, n)`, `pct_change(x, periods?)`, `diff(x, periods?)`, `shift(x, periods?)`, `clip(x, lo?, hi?)`, `index100(x)`, `rank_pct(x)` |

Column names referenced in expressions must start with letter or underscore (no digits, no spaces / dots / dashes). Inferred units: `* 100` on percent inputs → `bp`; `zscore(...)` → `z`; `pct_change(...)` / `yoy_pct(...)` / `index100(...)` → `percent`; otherwise inherit when every referenced column shares units.

The popup Sources footer on any chart point surfaces the recipe directly.
