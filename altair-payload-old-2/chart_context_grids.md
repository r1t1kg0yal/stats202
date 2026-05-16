# Altair Grid (small-multiples / facet)

Spoke fetched on demand from `chart_context.md`. Covers `make_chart()`
in grid mode — `mapping['facet']='<col>'` lays out N panels in a
square NxM grid for cross-sectional comparison (G20 GDP per country,
sector PMIs, country FX returns, etc.). For chart authoring without
facet (single canvas, n-pack composites, annotations, dual-axis), the
hub at `chart_context.md` is enough.

---

## 1. When to use a grid

| Situation | Reach for |
|---|---|
| 8-30 entities sharing the same story shape (G20 GDP, 12 sectors, 16 FX pairs, 20 country curves) | grid mode (this spoke) |
| 2-4 panels making a single ARGUMENT (US vs EU, level + change) | `make_2pack_*` / `make_4pack_grid` (hub §10) |
| One canvas with one comparison | single `make_chart()` + `mapping['color']` |
| 30+ entities or matrix-of-values | `chart_type='heatmap'` |

The grid is for cross-sectional dashboards, not arguments. If the goal
is to make a point about ONE comparison, a 2-pack reads tighter.

---

## 2. Minimal call

```python
result = make_chart(
    df=g20_long,                  # long-form, one row per (country, date)
    chart_type='multi_line',      # or 'scatter' / 'bar' / 'area' / 'histogram'
    mapping={
        'x': 'date', 'y': 'gdp_growth',
        'facet': 'country',       # triggers grid mode
    },
    facet_cols=4,                 # rows derived: ceil(n_panels / cols)
    dimensions='page_grid',       # sizes panels for letter-portrait paper
    title='G20 Real GDP Growth (YoY %)',
)
```

Grid mode is triggered ONLY by `mapping['facet']`. Without it,
`make_chart` runs in normal single-canvas mode.

### Kwargs

| Kwarg | Default | Notes |
|---|---|---|
| `mapping['facet']` | (required) | Column whose unique values become panel ids |
| `facet_cols` | near-square `ceil(sqrt(n))` | Rows derived from cols; trailing cells blank if not divisible |
| `dimensions` | `'page_grid'` (default for facet) | Auto-sizes panels for US Letter portrait. `wide` / `square` / `compact` / etc still work but treat their (w, h) as per-panel BUDGET |
| `same_scale` | `False` | Smart-routes per chart_type (§4) — preferred over individual `share_*` |
| `share_x` / `share_y` / `share_color` | `False` | Lower-level locks; reach for these only when `same_scale` is too coarse |
| `mapping['facet_order']` | first-appearance in df | Optional explicit list of panel ids |
| `mapping['color_scheme']` | `'viridis'` | For gradient color: `'turbo'`, `'plasma'`, `'inferno'`, `'magma'`, `'cividis'`, `'rainbow'` |
| `edge_only_ticks` / `edge_only_axis_titles` | `False` | Opt-in; suppress tick labels / titles on inner panels (tight-paper mode) |

### Limits

| Limit | Behaviour |
|---|---|
| `n_panels > 36` | hard reject with actionable error (aggregate to group level or use `chart_type='heatmap'`) |
| `n_panels >= 25` | render + emit warning ("consider aggregating") |
| `n_panels < 2` | reject (use single canvas) |

---

## 3. Compatible chart_types

Allowed: `multi_line`, `timeseries`, `scatter`, `scatter_multi`, `bar`,
`bar_horizontal`, `area`, `histogram`.

Rejected: `heatmap`, `donut`, `boxplot`, `bullet`, `waterfall`. Each is
a single-canvas chart by design; grid mode raises `ValidationError`
pointing at the right alternative.

---

## 4. Synchronisation: `same_scale=True`

Smart-routes by `chart_type`:

| chart_type | `same_scale=True` effect |
|---|---|
| `multi_line` / `timeseries` / `area` / `bar` / `bar_horizontal` | `share_y=True` |
| `scatter` / `scatter_multi` | `share_x=True` AND `share_y=True` |
| `histogram` | `share_x=True` (count axis is per-panel) |

Set `same_scale=True` for direct cross-panel comparison (G20 GDP growth
in the same y-range; (CPI, GDP) scatters on a single 8x8 grid).
Default `same_scale=False` keeps per-panel scales — better when each
panel's own range matters more than cross-panel level comparison.

`share_color=True` is separate — it locks the categorical color domain
across panels and renders a SINGLE shared categorical legend below the
grid (gradient color uses the gradient bar instead, see §5).

---

## 5. Scatter phase-space gradient

For `scatter` / `scatter_multi`: when `mapping['color']` references a
TEMPORAL or NUMERIC column, the engine auto-switches to a sequential
palette. Use for phase-space plots where each dot's color encodes its
position in time or sequence — the dots paint a trail through (x, y).

```python
result = make_chart(
    df=df,                            # cols: country, quarter, cpi, gdp
    chart_type='scatter',
    mapping={
        'x': 'cpi', 'y': 'gdp',
        'facet': 'country',
        'color': 'quarter',           # temporal column -> viridis gradient
        'color_scheme': 'turbo',      # optional: more rainbow-y
    },
    facet_cols=4, dimensions='page_grid',
    same_scale=True,
    title='Inflation vs Growth: time-coloured phase plot',
)
```

The 12-color cardinality cap that fires for categorical color encodings
is BYPASSED for gradient color — 24 quarters can color 24 dots because
the palette is continuous.

A SINGLE composite-level gradient legend bar renders below the grid
showing the value range. Per-panel gradient legends are stripped.

---

## 6. What the engine does for you

PRISM does NOT pass any of these — listed so you don't reach for them.

| Behaviour | Detail |
|---|---|
| Square panels | `panel_w == panel_h`. Grids with fewer rows than cols leave canvas vertical space unused; readability of squares wins over canvas-fill efficiency |
| Y-axis title strip | Stripped on line / multi_line / bar / area / histogram (composite title carries the metric); KEPT on scatter / scatter_multi (x and y describe different variables) |
| Per-panel legend strip | Always. `share_color=True` rebuilds a single composite categorical legend; gradient color builds the composite gradient bar instead |
| Auto-typography | Tick labels 24pt, axis titles 22pt, panel titles 26pt; tickCount cap of 6 — sized for letter-portrait paper viewed at arm's length |
| Inter-panel spacing | 50px default |
| Empty-cell padding | Trailing cells render as invisible blanks when `n_panels < rows * cols` |
| Per-panel build resilience | Up to N-1 panels can fail and survivors still render; failures land in `result.warnings` |

There is no kwarg for `panel_width`, `panel_height`, `spacing`, or
typography in grid mode.

---

## 7. Output

Returns a `ChartResult` (same dataclass as single-canvas `make_chart()`)
with `chart_type='<base>_facet'` (e.g. `multi_line_facet`,
`scatter_facet`). `png_path`, `download_url`, `vegalite_json`,
`success`, `warnings` populate as usual. Pass through
`check_charts_quality()` like any other chart.
