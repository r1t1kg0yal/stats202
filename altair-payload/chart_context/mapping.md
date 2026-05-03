# Mapping reference

Spoke fetched on demand from the chart_context hub. Covers the `mapping={...}` argument to `make_chart()` — the axis-title kwarg discipline, the basic patterns (long, wide, profile/curve, scatter+trendlines, dual-axis), the full key reference, and per-series line styling via `strokeDash`.

For per-chart-type required keys + caveats fetch `chart_types.md`. For dual-axis depth (right-axis title pairing, inverted right axis, name matching) fetch `dual_axis.md`. For composite layouts (n-pack helpers) fetch `composites.md`.

---

## 1. Axis-title keys live INSIDE `mapping={}`

`y_title`, `y_title_right`, `x_title` are NEVER top-level kwargs on
`make_chart()` or `ChartSpec(...)` -- passing them outside `mapping={}`
raises `TypeError: __init__() got an unexpected keyword argument
'y_title'`. Composites are the same shape: `make_2pack_horizontal`,
`make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`,
`make_6pack_grid` accept composite-level `title=` / `subtitle=`, but
per-panel axis titles live inside each panel's `ChartSpec.mapping`.

```python
make_chart(df=df, chart_type='multi_line',
           mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'})

ChartSpec(df=df, chart_type='multi_line',
          mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'})

# WRONG -- raises TypeError on `y_title=`:
ChartSpec(df=df, chart_type='multi_line', y_title='Yield (%)',
          mapping={'x': 'date', 'y': 'value'})

# Composite -- composite-level title=, per-panel y_title in spec.mapping:
make_2pack_horizontal(
    spec_left, spec_right,
    title='Composite title', subtitle='Composite subtitle',
)
```

---

## 2. Basic patterns

```python
# Basic
mapping = {'x': 'date', 'y': 'value', 'y_title': 'GDP Growth (%)'}
# Multi-series (long format)
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}
# Auto-melt (wide format)
mapping = {'x': 'date', 'y': ['col_a', 'col_b']}
# Profile/curve (ordinal x auto-detected)
mapping = {'x': 'tenor', 'y': 'yield_pct', 'color': 'curve_date'}
# Scatter with trendlines
mapping = {'x': 'x_var', 'y': 'y_var', 'color': 'group', 'trendlines': True}
# Dual axis (see dual_axis.md for depth)
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': ['Right Axis Series'],
    'y_title': 'Left Label', 'y_title_right': 'Right Label',
}
```

---

## 3. All mapping keys

| Key | Type | Description |
|-----|------|-------------|
| `x` | str | X-axis column |
| `y` | str / list | Y-axis column(s); list triggers auto-melt |
| `color` | str | Grouping column for multi-series |
| `y_title` / `y_title_right` / `x_title` | str | Y-axis label (max 20 chars) / right y-axis label (dual only) / x-axis label |
| `x_sort` / `y_sort` | list | Explicit ordinal sort order (x) / heatmap y-axis sort order |
| `x_type` | str | Force `'ordinal'` on datetime columns |
| `dual_axis_series` / `invert_right_axis` | list / bool | Series names for right y-axis / flip right y-axis (higher = bottom; standard rates pattern) |
| `trendline` / `trendlines` | bool | Overall trendline (scatter) / per-group trendlines (scatter_multi) |
| `stack` | bool | Bar with color: `True` (default) = stacked, `False` = grouped |
| `strokeDash` / `strokeDashScale` / `strokeDashLegend` | str / dict / bool | Column for per-series line style / explicit `{domain: [...], range: [...]}` / show legend (default `False`) |
| `value` / `theta` | str | Value column (heatmap) / magnitude column (donut) |
| `x_low` / `x_high` / `color_by` / `label` | str | Bullet only: range bounds / severity column / label column |
| `type` | str | Bar-type column (waterfall: `total` / `positive` / `negative`) |

---

## 4. strokeDash: per-series line styles

For `multi_line` only (single y-axis); not supported on dual-axis or
profile/curve charts. Uses Altair 4.1+ `alt.StrokeDash()`. Use when lines
share the same color but differ in style (actuals vs estimates) -- keep
`color` for the entity, `strokeDash` for the type, do NOT combine them
into one series name.

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'company',
    'strokeDash': 'type',                    # 'Actual' vs 'Estimate'
    'strokeDashScale': {                     # Optional explicit scale
        'domain': ['Actual', 'Forecast'], 'range': [[1, 0], [8, 3]],
    },
    'y_title': 'Capex ($B)',
}
```

Auto-scale: 2 categories -> solid `[1,0]` + dashed `[6,4]`; 3 -> adds
dotted `[2,2]`; 4+ -> Altair auto-assigns. Legend suppressed by default
(color identifies series); set `strokeDashLegend: True` to show it.
