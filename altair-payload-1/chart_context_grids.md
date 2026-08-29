# Altair facet grids

This document covers `mapping['facet']` and 5–36 same-shape entities. A facet
grid is one `make_chart()` call whose facet-column values become panels.

## 1. Grid versus composite

| Need | Use |
|---|---|
| Two, three or four panels making one argument | `ChartSpec` pack; see `chart_context_composites.md` |
| Five to 36 entities with the same chart shape | Facet grid |
| Six panels as a tight argument | Either: `make_6pack_grid`, or a facet grid when the six need one shared scale |
| One scale shared across panels, at any count | Facet grid with `same_scale=True` — packs always scale each panel independently |
| More than 36 entities or matrix-like comparison | Aggregate or use heatmap/table |

The packs cover 2, 3, 4 and 6 cells; there is no five-cell pack, which is why
the facet floor is five rather than seven.

Facet grids are cross-sectional comparison sheets. Packs are tighter for one
compare/contrast argument.

## 2. Minimal call and kwargs

```python
result = make_chart(
    df=g20_long,
    chart_type="multi_line",
    mapping={
        "x": "date",
        "y": "gdp_growth",
        "facet": "country",
        "facet_order": ["US", "UK", "EU", "JP", "CA", "AU", "CN", "IN"],
    },
    facet_cols=4,
    same_scale=True,
    title="G20 Real GDP Growth",
)
```

Grid mode is triggered only by `mapping['facet']`. Only `facet` and
`facet_order` go inside `mapping`; `facet_cols`, `same_scale`, `share_color`,
and both `edge_only_*` controls are top-level `make_chart(...)` kwargs.

| Key | Default | Meaning |
|---|---|---|
| `mapping['facet']` | required | Panel-id column |
| `mapping['facet_order']` | first appearance | Explicit panel order |
| `mapping['y_title']` | none | Panels carry no y-axis title by default, so this is the only place to state a unit. Set it and the label appears on the leftmost panel of each row, not on every panel |
| `facet_cols` | near-square layout | Number of columns; rows are derived |
| `same_scale` | `False` | Lock the axis that matters for this chart type |
| `share_color` | `False` | Lock the colour domain; one shared legend |
| `edge_only_ticks` | `False` | Suppress y-tick labels on inner columns. X-tick labels always render on every panel |
| `edge_only_axis_titles` | `False` | Suppress repeated inner axis titles |

Every panel carries its own x-axis tick labels. There is no flag that hides
them -- `edge_only_ticks` only touches the y-axis.

Panel count below 7 or above 36 raises. Counts from 25 through 36 render with
an aggregation warning.

## 3. Compatible chart types

Allowed:

`multi_line`, `timeseries`, `scatter`, `scatter_multi`, `bar`,
`bar_horizontal`, `area`, `histogram`.

Rejected:

`heatmap`, `donut`, `boxplot`, `bullet`, `waterfall`, `contribution`, `band`.

For a long frame where each facet value is also the former series identifier,
set `facet` and drop `color` unless each panel genuinely contains a second
within-panel grouping.

## 4. Scale synchronization

`same_scale=True` locks whichever axis carries the comparison:

| Type | `same_scale=True` |
|---|---|
| Line, area, bar | Shared y scale |
| Scatter | Shared x and y scales |
| Histogram | x is already shared in facet mode; count y remains per panel |

Keep the default independent scales when each panel's shape matters more than
cross-panel level. Use `same_scale=True` when direct level/position comparison
is the point.

`share_color=True` is orthogonal — it locks the colour domain into one shared
legend and `same_scale` never sets it. For a temporal-colour phase grid whose
colours must compare across panels, pass both.

## 5. Time-coloured phase grids

For scatter grids, a temporal or numeric `color` becomes a continuous ramp.
Add `connect=True` for a time-ordered phase path:

```python
make_chart(
    df=phase_df,
    chart_type="scatter",
    mapping={
        "x": "inflation",
        "y": "growth",
        "facet": "country",
        "color": "quarter",
        "connect": True,
    },
    facet_cols=4,
    same_scale=True,
    share_color=True,
    title="Inflation–Growth Phase Paths",
)
```

The 10-category colour cap does not apply to a continuous ramp. See
`chart_context_colors.md` before setting `color_range`, `color_scheme`, or opacity.

## 6. Output and failures

Facet grids remove end-of-line labels; panel headers identify entities. A
panel header is a category name, so it takes the same 24-character cap as any
other one (`chart_context.md` §5.1) — the facet values do the work the
end-label names would have done, and the grid raises naming the offenders
rather than truncating them. Unsupported annotations and other non-fatal
adjustments appear in `result.warnings`.

If any panel fails validation, the complete grid raises and names every
offending panel with its findings. A successful call returns one `ChartResult`
whose `chart_type` is suffixed `_facet`.
