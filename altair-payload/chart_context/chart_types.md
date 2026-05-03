# Chart types

Spoke fetched on demand from the chart_context hub. Covers every chart type `make_chart()` supports — required mapping keys, per-type cosmetic guidance, the bar-chart family (stacked vs grouped, annotation compatibility, datetime x-axes), and the data-shape concerns (Haver business-daily storage, mixed-frequency merges) that cross-cut every time-series type.

For dual-axis time series (`dual_axis_series` mechanics, inverted right axis, HLine on right) fetch `dual_axis.md`. For mapping-key reference and `strokeDash` styling fetch `mapping.md`. For composite layouts (n-pack helpers) fetch `composites.md`.

---

## 1. Type catalog

| Type | Use Case | Required Mapping |
|------|----------|------------------|
| `multi_line` | Time series, curve evolution | `x`, `y`, `color` (opt) |
| `scatter` | X-Y relationships | `x`, `y` |
| `scatter_multi` | Grouped scatter + trendlines | `x`, `y`, `color` |
| `bar` | Category comparisons (stacked/grouped via `stack`) | `x` (cat), `y`, `color` (opt) |
| `bar_horizontal` | Horizontal bars | `x`, `y` (cat) |
| `heatmap` | Matrices | `x`, `y`, `value` (NOT `'color'`) |
| `histogram` | Distributions | `x` |
| `boxplot` | Distribution comparison | `x` (cat), `y` |
| `area` | Stacked time series | `x`, `y`, `color` |
| `donut` | Part-to-whole | `theta`, `color` |
| `bullet` | Range dot / percentile position | `y` (cat), `x` (val), `x_low`, `x_high` |
| `waterfall` | Additive decomposition / attribution | `x` (cat), `y`, `type` (opt) |

`timeseries` is accepted as an alias path inside the `multi_line` builder.

For `multi_line`, `multi_line` auto-detects non-datetime x-axis -> ordinal mode. Tenor-like values (`1M`, `2Y`, `10Y`) auto-sort by maturity, so curve-evolution charts (yields by tenor across snapshot dates) just work.

---

## 2. Bar chart family

### Stacked vs grouped

`stack=True` (default with color, sums components into a total) vs
`stack=False` (side-by-side). Applies to `bar` and `bar_horizontal`.

| Data Relationship | `stack` | Example |
|-------------------|---------|---------|
| Parts of a whole / additive decomposition | `True` | Revenue by product, GDP decomposition |
| Independent comparisons / benchmarking | `False` | OLS vs LASSO coefficients, actual vs forecast |

```python
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product'}                  # stacked (default)
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product', 'stack': False}  # grouped
```

Grouped mode uses Altair 4.x column faceting internally. The engine
clamps facet width to the cell budget so a grouped bar inside an
n-pack composite stays inside its 2x2 / 3x2 cell. If per-bar pixel
width would drop below ~3 px (~60+ x-categories in a compact 4_grid
cell, ~200+ in a wide standalone cell), the engine raises a
`GROUPED BAR CELL-BUDGET ERROR` -- switch to `stack=True`, reduce
x-categories, or render the chart standalone (larger budget) instead
of inside a composite. `bar_horizontal` enforces the same on the
height axis.

### No redundant positive/negative color coding

Do NOT add a color column encoding sign (`'Positive'`/`'Negative'`) -- the
bar's position relative to zero already conveys sign. Color should encode
a conceptual dimension (sector, region, model type).

### Annotation compatibility

| Bar Mode | Annotation Support |
|----------|--------------------|
| Single-series | `HLine`, `VLine`, `Band`, `Arrow`, `PointLabel` work |
| Stacked (default w/ color) | `HLine` works; clamped against stacked totals |
| `bar_horizontal` | `HLine` renders as a vertical threshold |
| Grouped (`stack=False`) | Annotations DO NOT render (Altair faceting + layering incompatibility) |

For grouped bars, convey thresholds via title/subtitle, or switch to
`stack=True` if acceptable. For stacked bars, `HLine` encodes the stacked
TOTAL (use when the threshold applies to the total -- e.g. "regional
target = $100B" -- not a single component).

### Datetime x-axes

Prefer `multi_line` or `area` for time-series. If using `bar` + datetime
x, the engine handles temporal encoding automatically; for period-based
bars, convert dates to string labels (e.g., `"Q1 2025"`) for nominal
encoding.

---

## 3. Heatmap

`value` column is rendered as cell color. `MAX_COLOR_CARDINALITY=12`
applies -- continuous numeric values MUST be binned to <=12 categories
BEFORE `make_chart()`, else `check_charts_quality` rejects and the
chart is dropped. Bin via `pd.cut()` (equal-width) or `np.digitize()`
(custom edges); set `mapping['color_scheme']` to a sequential scheme
(`'blues'`, `'viridis'`, etc.) keyed to the binned values.

```python
df['prob_bucket'] = pd.cut(
    df['Probability'], bins=10,
    labels=[f'{i*10}-{(i+1)*10}%' for i in range(10)],
)
mapping = {
    'x': 'meeting_date', 'y': 'fed_funds_rate', 'value': 'prob_bucket',
    'color_scheme': 'blues',
}
```

---

## 4. Bullet chart

Current values within historical ranges. Marker color encodes severity via
z-score or percentile.

```python
df = pd.DataFrame({
    'variable': ['2s10s', '5s30s', '10Y Spd'],
    'current_value': [38, -5, -33], 'range_low': [-20, -10, -45], 'range_high': [45, 60, -20],
    'z_score': [1.2, -1.5, 0.1], 'percentile': [85, 12, 45],
})
mapping = {
    'y': 'variable', 'x': 'current_value',
    'x_low': 'range_low', 'x_high': 'range_high',
    'color_by': 'z_score', 'label': 'percentile',
}
```

---

## 5. Waterfall chart

Additive decomposition / attribution -- bars float, each starts where the
previous ended. Use for CPI / GDP decomposition, P&L attribution, FCI
impulse, any additive breakdown. `type` is optional (if absent, first/last
rows are totals, intermediates signed by value). Color: positive = green
(`#2EB857`), negative = red (`#DC143C`), totals = skin primary. The engine
warns if intermediates do not sum to `(last - first)` within 15%.

```python
df = pd.DataFrame({
    'component': ['Start', 'Energy', 'Food', 'Core Goods', 'Core Services', 'End'],
    'contribution': [3.0, -0.4, -0.2, 0.1, 0.6, 3.1],
    'type': ['total', 'negative', 'negative', 'positive', 'positive', 'total'],
})
mapping = {'x': 'component', 'y': 'contribution', 'type': 'type', 'y_title': 'CPI YoY (%)'}
```

---

## 6. Haver frequency & mixed-frequency DataFrames

Haver stores many monthly/quarterly series at business-daily granularity
(same value repeated ~22 days, then jumps). Symptom: stair-step lines.
Fix: resample business-daily to true native frequency as the first step.
Merging series of different frequencies creates NaN gaps -- resample
everything to the lowest common frequency before `concat` / `merge`.
Comment the resampling method for auditability; never chart a DataFrame
with mixed-frequency NaN gaps.

```python
starts = starts.resample('M').last()             # Monthly
gdp = gdp.resample('Q').last()                   # Quarterly
claims_monthly = claims.resample('M').mean()     # Weekly -> Monthly
df = pd.concat([claims_monthly, nfp_monthly], axis=1).dropna()
```

| Series Type | Resample Method | Example |
|-------------|-----------------|---------|
| Point-in-time / stock | `.last()` | Housing starts, unemployment rate |
| Flow / cumulative | `.mean()` or `.sum()` | Initial claims (mean), retail sales (sum) |
| Rate / percentage | `.last()` or `.mean()` | CPI YoY, mortgage rate |
