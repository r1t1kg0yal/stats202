# Dual-axis charts

Spoke fetched on demand from the chart_context hub. Covers the dual-axis surface end to end — declaring the right axis, pairing left/right titles, inverting the right axis (the "up = bullish" rates pattern), placing annotations against the right axis, and the long-format discipline that keeps series-name routing clean.

For the broader mapping reference fetch `mapping.md`. For the underlying `multi_line` chart type fetch `chart_types.md`. For composite alternatives (when a single-canvas dual-axis isn't the right shape), fetch `composites.md`.

---

## 1. When to use dual axis

When two series belong on the same chart but live in very different scales — equity index vs ISM, 2s10s curve vs WTI, mortgage rates vs starts. The reader's eye lands on co-movement; the two axis labels make scale separation explicit.

Always declare dual-axis with explicit long format. `y: [list]` (the auto-melt shortcut) is incompatible with `dual_axis_series` — long format gives the engine the per-row series labels it routes off.

```python
df_long = df.melt(id_vars=['date'], var_name='series', value_name='value')

result = make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value', 'color': 'series',
        'dual_axis_series': ['ISM Manufacturing'],
        'y_title': 'S&P 500', 'y_title_right': 'ISM Index',
    },
    title='Equities Track Manufacturing',
)
```

---

## 2. Series-name discipline

`dual_axis_series` is a list of series names that exactly match values in
the `color` column. The cleanest pattern is to define LEFT/RIGHT
constants and use them throughout — the constants double as the canonical
column-rename targets and the `y_title` / `y_title_right` source of truth,
keeping the four places these names appear (DataFrame values,
`dual_axis_series`, left title, right title) in lockstep.

```python
LEFT_SERIES, RIGHT_SERIES = '2s10s Curve (bp)', 'WTI Crude ($/bbl)'
curve_df['series'] = LEFT_SERIES
oil_df['series'] = RIGHT_SERIES
df_long = pd.concat([curve_df, oil_df], ignore_index=True)
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': [RIGHT_SERIES],
    'y_title': '2s10s (bp)', 'y_title_right': 'WTI ($/bbl)',
}
```

Practical hygiene: rename DataFrame columns BEFORE melting (so the
post-melt `series` column carries the human-readable names), `.str.strip()`
any series column read from CSV (trailing whitespace silently disqualifies
the right-axis row), and re-check `df['series'].value_counts()` after any
`dropna()` so a sparse series isn't entirely filtered out before the
chart sees it.

---

## 3. Inverted right axis

`invert_right_axis: True` flips the right y-axis (higher values at the
bottom). This is the standard rates pattern where "up = bullish" on both
axes — equities up + yields down both read as risk-on. Vega-Lite uses
reversed domains natively, so no value negation is needed; axis labels
and `HLine` placement work correctly without manual sign flipping.

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'dual_axis_series': ['UST 10Y'],
    'invert_right_axis': True,
    'y_title': 'S&P 500', 'y_title_right': 'UST 10Y (%)',
}
```

---

## 4. Annotations against the right axis

`HLine`, `Segment`, and `PointHighlight` accept an `axis` parameter
(`'left'` / `'right'`, default `'left'`). On a dual-axis chart, `axis='right'`
encodes against the right y-axis field/domain — pass values in
right-axis units, not left.

```python
annotations = [
    HLine(y=4.25, axis='left', label='Fed funds upper bound', color='#666666'),
    HLine(y=3.50, axis='right', label='Q1 ISM trough', color='#f58518'),
    Segment(x1=T('2022-01'), x2=T('2022-12'), y1=50, y2=50,
            axis='right', label='ISM expansion threshold', color='#999999'),
    PointHighlight(x=T('2023-06'), y=48.5, axis='right',
                   color='#C00000', size=120),
]
```

`Trendline` does not currently apply on dual-axis `multi_line` — for a
trendline-on-dual-axis story, build a single-axis chart per series and
combine via `make_2pack_vertical()`.

---

## 5. When to switch off dual axis

Dual-axis is the right shape when you want the reader's eye on co-movement.
For other intents:

| Intent | Better shape |
|---|---|
| Compare magnitudes side-by-side (not co-movement) | `make_2pack_vertical()` — two stacked panels with their own axes |
| Show many series on one canvas (3+) where dual-axis would still leave scale problems | z-score normalize all series, plot on a single axis with `multi_line` |
| Highlight regime changes per series independently | one `multi_line` per series in a composite, with per-panel annotations |

The principle: dual-axis is the densest expression when co-movement is
the point. When the comparison is "do these magnitudes agree", a stacked
composite is clearer.
