# Altair facet grids

Fetch this spoke for `mapping['facet']` or 7–36 same-shape entities. A facet
grid is one `make_chart()` call whose facet-column values become panels.

## 1. Grid versus composite

| Need | Use |
|---|---|
| Two to six panels making one argument | `ChartSpec` pack; fetch composites |
| Seven to 36 entities with the same chart shape | Facet grid |
| More than 36 entities or matrix-like comparison | Aggregate or use heatmap/table |

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

Grid mode is triggered only by `mapping['facet']`.
Only `facet` and `facet_order` go inside `mapping`; `facet_cols`,
`same_scale`, every `share_*`, and both `edge_only_*` controls are top-level
`make_chart(...)` kwargs.

| Key | Default | Meaning |
|---|---|---|
| `mapping['facet']` | required | Panel-id column |
| `mapping['facet_order']` | first appearance | Explicit panel order |
| `facet_cols` | near-square layout | Number of columns; rows are derived |
| `same_scale` | `False` | Recommended high-level scale lock |
| `share_x`, `share_y`, `share_color` | `False` | Lower-level locks |
| `edge_only_ticks`, `edge_only_axis_titles` | `False` | Suppress repeated inner labels |

Panel count below 7 or above 36 raises. Counts from 25 through 36 render with
an aggregation warning.

## 3. Compatible chart types

Allowed:

`multi_line`, `timeseries`, `scatter`, `scatter_multi`, `bar`,
`bar_horizontal`, `area`, `histogram`.

Rejected:

`heatmap`, `donut`, `boxplot`, `bullet`, `waterfall`.

For a long frame where each facet value is also the former series identifier,
set `facet` and drop `color` unless each panel genuinely contains a second
within-panel grouping.

## 4. Scale synchronization

| Type | `same_scale=True` |
|---|---|
| Line, area, bar | Shared y scale |
| Scatter | Shared x and y scales |
| Histogram | x is already shared in facet mode; count y remains per panel |

Keep the default independent scales when each panel's shape matters more than
cross-panel level. Use `same_scale=True` when direct level/position comparison
is the point.

`share_color=True` locks the colour domain and creates one shared legend. It is
separate from `same_scale`. For a temporal-colour phase grid whose time colours
must compare across panels, use both `same_scale=True` and `share_color=True`.

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

The 10-category colour cap does not apply to a continuous ramp. Fetch the
colours spoke before setting `color_range`, `color_scheme`, or opacity.

## 6. Output and failures

Facet grids remove end-of-line labels; panel headers identify entities.
Unsupported annotations and other non-fatal adjustments appear in
`result.warnings`.

If any panel fails validation, the complete grid raises and names every
offending panel with its findings. A successful call returns one `ChartResult`
whose `chart_type` is suffixed `_facet`. Foreground post-script QC evaluates
the single grid PNG automatically.
