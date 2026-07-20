# Altair dual-axis and lead-lag charts

Fetch this spoke for two metrics or unit families on one timeline, any
`dual_axis_*` / `y_title_right` / inverted-RHS request, a y-scale mismatch
error, or a time-shifted lead-lag chart. Dual axis is supported on
`multi_line` / `timeseries`.

## 1. Choose dual axis deliberately

Use a dual axis when co-movement is the analytical point and the series have
different units or materially different scales. Otherwise prefer:

| Goal | Better shape |
|---|---|
| Compare each series' own path | Two-panel composite |
| Compare co-movement across many series | Normalize to z-score, percent change, or rebased 100 |
| Compare 7–36 same-shape entities independently | Facet grid |

Different units require explicit dual-axis intent even when their numerical
ranges happen to overlap. The engine can detect magnitude mismatch; it cannot
infer economic units.

**Every dual-axis chart requires a short semantic `y_title_right` naming the
right metric and unit.** Empty values and placeholders such as `Right Axis`,
`RHS`, and `Value` raise. The left title should also name metric and unit.

## 2. Two binding forms

Long format is canonical:

```python
LEFT = "S&P 500"
RIGHT = "UST 10Y"

df_long = pd.concat([
    equities.rename(columns={"spx": "value"}).assign(series=LEFT),
    yields.rename(columns={"yield_pct": "value"}).assign(series=RIGHT),
], ignore_index=True)

result = make_chart(
    df=df_long,
    chart_type="multi_line",
    mapping={
        "x": "date", "y": "value", "color": "series",
        "dual_axis_series": [RIGHT],
        "y_title": "S&P 500 Index",
        "y_title_right": "UST 10Y (%)",
    },
    title="Equities Rose as Yields Fell",
)
```

`dual_axis_series=[...]` lists the right-axis category values exactly; all
unlisted series use the left. Wide `y=[...]` input is also accepted, and the
right-axis names refer to the original wide column names.

For three or more lines, prefer an explicit binding:

```python
mapping = {
    "x": "date", "y": "value", "color": "series",
    "dual_axis_bind": {
        "Total Debt ($T)": "left",
        "Public Held ($T)": "left",
        "Intragov (%)": "right",
    },
    "y_title": "USD Trillions",
    "y_title_right": "% of Total",
}
```

`dual_axis_bind` values accept `left` / `right` and `lhs` / `rhs`. Do not pass
both binding forms. An all-left or all-right binding raises because it is not a
dual-axis chart. Normalize exact series identifiers before calling; a trailing
space is a different category.

## 3. Scale gates and automatic recovery

On an undeclared multi-series single axis, the engine checks for a series that
would appear nearly flat and for severe level disparity. When a semantic
`y_title_right` is already present, a standalone chart may recover to two axes
and records the decision in `result.audit_trail`. Without that title, it raises
and asks for explicit binding and both axis titles.

Automatic recovery is not available inside a `ChartSpec` composite cell.
Declare the binding and `y_title_right` on that `ChartSpec`.

For three or more lines, the engine makes a best-effort split and may put a
within-axis compression warning in `result.warnings`. If each shape matters,
split or normalize instead of accepting a crowded dual axis.

Optional explicit domains:

```python
mapping["dual_axis_config"] = {
    "y_domain_left": [3500, 6000],
    "y_domain_right": [2.5, 5.5],
}
```

Use explicit domains only when the analytical frame requires fixed bounds.

## 4. Inverted right axis and legends

`invert_right_axis=True` flips the RHS so larger values plot lower. This is
useful when the visual direction should align, such as equities up versus
yields down. Do not negate the data.

```python
mapping["invert_right_axis"] = True
```

Dual-axis charts use a colour legend, not end-of-line labels.
`LastValueLabel` is removed with a warning. With three or more series the
engine normally appends ` (LHS)` / ` (RHS)` to legend entries; set
`dual_axis_legend_tags=False` only when the axis association is already
unambiguous.

`strokeDash` is unsupported on dual-axis charts and is ignored with a warning.
If line style is essential, split into single-axis panels.

## 5. Right-axis annotations

`HLine`, `Segment`, `PointHighlight`, `Callout`, `Arrow`, horizontal `Band`,
and `PointLabel` accept `axis='right'`. Pass their y values in right-axis
units. `VLine` is axis-agnostic.

```python
annotations = [
    HLine(y=4500, axis="left", label="Index threshold"),
    HLine(y=4.25, axis="right", label="Yield threshold"),
    Band(y1=3.5, y2=4.0, axis="right", label="Yield regime", opacity=0.2),
    PointHighlight(x=pd.Timestamp("2024-10-01"), y=3.62,
                   axis="right", size=120),
]
```

Out-of-domain annotations are removed and reported in `result.warnings`.
`Trendline` is removed on dual-axis charts. For per-series trends or end
labels, build single-axis charts and compose them.

## 6. Lead-lag

| Question | Build |
|---|---|
| Does `X` at lag N explain `Y` now? | Scatter `Y_t` versus `X_{t-N}` with `trendline=True` |
| What does `X` imply for `Y` over the next N months? | Shift predictor dates forward N months, then dual axis |
| Show strength and time path together | Horizontal 2-pack: lagged scatter + shifted timeline |

```python
predictor_shift = predictor.copy()
predictor_shift["date"] = (
    predictor_shift["date"] + pd.DateOffset(months=6)
)

lead_df = pd.concat([
    outcome.rename(columns={"spx_yoy": "value"})
           .assign(series="SPX YoY (%)"),
    predictor_shift.rename(columns={"ism": "value"})
                   .assign(series="ISM (lead 6m)"),
], ignore_index=True)

today = outcome["date"].max()
future_end = predictor_shift["date"].max()

make_chart(
    df=lead_df,
    chart_type="multi_line",
    mapping={
        "x": "date", "y": "value", "color": "series",
        "dual_axis_series": ["ISM (lead 6m)"],
        "y_title": "SPX YoY (%)",
        "y_title_right": "ISM (lead 6m)",
    },
    title="ISM Leads SPX by Six Months",
    annotations=[
        VLine(x=today, label="Today", style="dashed"),
        Band(x1=today, x2=future_end, label="Implied", opacity=0.18),
    ],
)
```

Compute any implied target before charting; the engine does not derive a
forecast. Use a `VLine` and optional future `Band` rather than trying to switch
one dual-axis series from solid to dashed. If the shifted series extends the
frame so far that historical co-movement becomes unreadable, use the
scatter-plus-timeline composite instead.
