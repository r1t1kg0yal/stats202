# Altair Grid (small-multiples / facet)

Spoke fetched on demand from `chart_context.md`. Covers `make_chart()` in grid mode -- `mapping['facet']='<col>'` lays out N panels in NxM grid for cross-sectional comparison (G20 GDP per country, sector PMIs, country FX returns). For single canvas, n-pack composites, annotations, dual-axis -- the hub is enough.

---

## 1. When to use a grid

| Situation | Reach for |
|---|---|
| 7-30 entities sharing one shape (Mag-7, 11 GICS sectors, G20 GDP, 16 FX pairs) | grid mode (this spoke) |
| 2-6 panels making a single ARGUMENT (US vs EU, level + change) | `make_2pack_*` / `make_4pack_grid` / `make_6pack_grid` (hub §10) |
| One canvas with one comparison | single `make_chart()` + `mapping['color']` |
| 30+ entities or matrix-of-values | `chart_type='heatmap'` |

Grid is for cross-sectional dashboards, not arguments. A 2-pack reads tighter for ONE comparison.

---

## 2. Minimal call

```python
result = make_chart(
    df=g20_long,                  # long-form, one row per (country, date)
    chart_type='multi_line',      # or 'scatter' / 'bar' / 'area' / 'histogram'
    mapping={'x': 'date', 'y': 'gdp_growth', 'facet': 'country'},
    facet_cols=4,                 # rows derived: ceil(n_panels / cols)
    title='G20 Real GDP Growth (YoY %)',
)
```

Grid mode triggered ONLY by `mapping['facet']`. Without it, normal single-canvas mode.

### Kwargs

| Kwarg | Default | Notes |
|---|---|---|
| `mapping['facet']` | required | Column whose unique values become panel ids |
| `facet_cols` | near-square `ceil(sqrt(n))` | Rows derived; trailing cells blank if not divisible |
| `same_scale` | `False` | Smart-routes per chart_type (§4); preferred over individual `share_*` |
| `share_x` / `share_y` / `share_color` | `False` | Lower-level locks; reach for these only when `same_scale` is too coarse |
| `mapping['facet_order']` | first-appearance in df | Optional explicit list of panel ids |
| `edge_only_ticks` / `edge_only_axis_titles` | `False` | Opt-in; suppress tick labels/titles on inner panels |

### Limits

- `n_panels > 36` → hard reject (aggregate to group level or use `chart_type='heatmap'`)
- `n_panels >= 25` → render + warning ("consider aggregating")
- `n_panels < 7` → hard reject (use `make_2pack_*` / `make_4pack_grid` / `make_6pack_grid`; composites top out at 6)

---

## 3. Compatible chart_types

Allowed: `multi_line`, `timeseries`, `scatter`, `scatter_multi`, `bar`, `bar_horizontal`, `area`, `histogram`.

Rejected: `heatmap`, `donut`, `boxplot`, `waterfall` -- single-canvas by design; grid mode raises `ValidationError` pointing at the right alternative.

---

## 4. Synchronisation: `same_scale=True`

| chart_type | `same_scale=True` effect |
|---|---|
| `multi_line` / `timeseries` / `area` / `bar` / `bar_horizontal` | `share_y=True` |
| `scatter` / `scatter_multi` | `share_x=True` AND `share_y=True` |
| `histogram` | `share_x=True` always in facet mode (count axis stays per-panel); `same_scale=True` is a no-op extra |

Set `same_scale=True` for direct cross-panel comparison (G20 GDP in same y-range; (CPI, GDP) scatters on single 8x8 grid). Default `False` keeps per-panel scales -- better when each panel's own range matters more than cross-panel level comparison (except histogram x, which is always shared in facet mode).

`share_color=True` is separate -- locks categorical color domain across panels + renders a SINGLE shared legend below the grid (gradient color uses the gradient bar, §5).

---

## 5. Scatter phase-space gradient

For `scatter` / `scatter_multi`: when `mapping['color']` references a TEMPORAL or NUMERIC column, engine auto-switches to sequential palette. Use for phase-space plots where each dot's colour encodes its position in time/sequence -- dots paint a trail through (x, y). Add `mapping['connect']=True` to link points into a gradient path (Goodwin orbit); `order` defaults to `color` when temporal/numeric.

```python
make_chart(df=df,                            # cols: country, quarter, cpi, gdp
    chart_type='scatter',
    mapping={'x': 'cpi', 'y': 'gdp', 'facet': 'country',
             'color': 'quarter'},     # temporal → sequential gradient
    facet_cols=4, same_scale=True,
    title='Inflation vs Growth: time-coloured phase plot')
```

12-color cardinality cap BYPASSED for gradient (continuous palette). SINGLE composite-level gradient legend bar renders below grid; per-panel gradient legends stripped.

---

## 6. Engine defaults

PRISM passes none of these. Panels are square (squareness > canvas-fill). Y-axis title strip stripped on line/multi_line/bar/area/histogram (composite title carries metric); KEPT on scatter/scatter_multi (x and y are different variables). Per-panel legends always stripped; `share_color=True` rebuilds a single composite legend. Typography uses the `facet_grid` preset (24pt axis labels, 3 tick budget) on every panel regardless of pixel size. `LastValueLabel` is never rendered in facet grids or composites -- the engine silently strips any LVL PRISM passes. Bar value labels are suppressed in facet panels. If ANY panel fails validation the entire grid is rejected -- the error names the offending panel id(s) and cause (same fail-fast contract as `make_*pack_*` composites).

---

## 7. Output

Returns `ChartResult` (same dataclass as single-canvas) with `chart_type='<base>_facet'` (e.g. `multi_line_facet`, `scatter_facet`). Pass through `check_charts_quality()` like any other chart.
