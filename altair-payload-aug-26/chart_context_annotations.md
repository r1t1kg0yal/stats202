# Altair annotations and layers

This document governs any `annotations=[...]` or `layers=[...]` call, and applies when
the request asks to mark an event, threshold, regime, point, trend, forecast
zone, or narrative takeaway. All classes are injected; call them bare.

## 1. Pick the smallest useful annotation

Default to none. Add an annotation only when it changes what the viewer learns.

| Intent | Primitive |
|---|---|
| Event date | `VLine` |
| Horizontal threshold or target | `HLine` |
| Shaded date or value regime | `Band` |
| Finite trend, average, or connector | `Segment` |
| Directional movement between two coordinates | `Arrow` |
| Text at one coordinate | `PointLabel` |
| Marker at one coordinate | `PointHighlight` |
| Legible labelled point | `Callout` |
| End-of-line identity | `LastValueLabel` |
| Best-fit relationship | `Trendline` |
| Short prose outside the plot | `PlotText` |

Use the title for the claim. Avoid labels that merely restate visible geometry
(`"rising"`, `"today"` at the right edge, `"sample period"` across the full
window). Known regime lines may be unlabelled or use a very short label.

```python
T = pd.Timestamp
annotations = [
    HLine(y=2.0),
    VLine(x=T("2022-03-01"), label="Hikes begin"),
    Band(x1=T("2020-03-01"), x2=T("2020-06-01"),
         label="Recession", opacity=0.25),
    PointHighlight(x=T("2022-06-01"), y=9.1, size=120),
    Callout(x=T("2022-06-01"), y=9.1, label="Peak 9.1%"),
]
```

## 2. Public parameter reference

Annotation coordinates and styles belong on the constructor, never inside
`mapping`. Most labelled classes inherit `label` and `label_color`;
`PlotText` uses `text` and `color`, while `LastValueLabel` derives its text
from the series. Use `stroke_dash=[...]` or a documented `style=` value; there
is no `dash=` or `line_style=`.

| Class | Decision-changing parameters |
|---|---|
| `VLine` | `x`, `label`, `color`, `stroke_width`, `stroke_dash`, `style='solid'|'dashed'|'dotted'` |
| `HLine` | `y`, `axis='left'|'right'`, `label`, `color`, `stroke_width`, `stroke_dash`, `style` |
| `Segment` | `x1`, `x2`, `y1`, `y2`, `axis`, `label_position='start'|'middle'|'end'`, line styling |
| `Band` | `x1`/`x2` for vertical or `y1`/`y2` for horizontal, `axis`, `color`, `opacity` (default 0.3) |
| `Arrow` | `x1`, `y1`, `x2`, `y2`, `axis`, `head_size`, `head_type='triangle'|'none'`, `label_position`; straight only (`curved=True` raises) |
| `PointLabel` | `x`, `y`, `label`, `axis`, `halo` |
| `PointHighlight` | `x`, `y`, `axis`, `color`, `size` (default 100), `opacity`, `shape`, `filled`, stroke controls |
| `Callout` | `x`, `y`, `axis`, `background='halo'|'box'|'none'`, box/halo controls |
| `LastValueLabel` | `font_size` (default 15), `font_weight` |
| `Trendline` | `method='linear'|'exp'|'log'|'pow'|'poly'|'quad'`, `color`, `stroke_width`, `stroke_dash` |
| `PlotText` | `text`, `position='auto'|'left'|'right'|'bottom'`, `font_size`, `color`, `italic`, `align`, `width_pct` |

`PointHighlight.shape` supports `circle`, `square`, `diamond`, `triangle`,
`triangle-up`, `triangle-down`, `cross`, and `stroke`.

### Label placement is engine-owned

Give every annotation its coordinates in DATA units and its text. Do not
compute where the text sits. The engine measures each label, projects it
against the axis it belongs to, and solves placement across all
annotations at once so none overlap and none leave the plot. It handles a
heavy load — a dozen-plus labels on one panel is expected, not abusive.

There is therefore no reason to pass a pixel offset, alignment, or label
font size, and no reason to hand-space annotations to avoid a clash you
cannot see. If space genuinely runs out the engine repositions, then
shrinks, then omits the least informative label and reports the omission
in `result.warnings`.

`PlotText.text` has a 10-word hard cap; aim for eight or fewer. It occupies an
outside panel, not the plot. Explicit `side_right`, `caption`, or `side_left`
wins its slot; `position='auto'` tries right, bottom, then left. Use the
top-level text kwargs for longer prose.

There are four distinct trend surfaces; choose one and do not combine them:

| Need | Surface |
|---|---|
| One default fit on `scatter` | `mapping['trendline']=True` |
| One fit per colour group on `scatter_multi` | `mapping['trendlines']=True` |
| One explicitly styled fit annotation | `annotations=[Trendline(...)]` on `scatter` |
| Lower-level regression overlay | `layers=[{'type': 'regression', 'x': ..., 'y': ...}]` |

## 3. Compatibility

| Shape | Contract |
|---|---|
| Scatter | `Trendline`, point classes, rules, bands, segments, arrows |
| Single-series bar | `HLine`, `VLine`, `Band`, `Arrow`, `PointLabel` |
| Stacked bar | `HLine` is clamped against stacked totals |
| Horizontal bar | `HLine` becomes a vertical value threshold. Point classes, callouts, arrows, and segments take a category NAME as `y`. `Band(y1=name, y2=name)` shades the whole inclusive row range |
| Heatmap | Same as horizontal bar: `y` is a row name. `Band(y1=..., y2=...)` shades whole rows; `HLine` renders its label at the named row without a rule |
| Grouped bar (`stack=False`) | Annotations do not render; use title/subtitle or stack/split |
| `multi_line` / `timeseries` | Rules, bands, segments, arrows, point classes, and callouts are supported; engine auto-injects `LastValueLabel` on a single axis |
| Dual axis | See `chart_context_dual_axis.md`; y-bearing annotations need the correct `axis` |
| `band` | Rules, bands, segments, arrows, and callouts read against the ribbon, not just the subject line; the forecast divider is already drawn, so skip a `VLine` at the handoff |
| `contribution` | `HLine` reads against stacked totals and zero is always in domain; a rule at zero is already drawn. Pass `VLine.x` as the date you have — the engine maps it to the rendered period label |
| Facet grid | `LastValueLabel` is removed; panel headers identify facets |
| Donut / bullet | Do not use plot annotations; rule-style classes are suppressed with a warning |

`LastValueLabel` is automatic on ordinary single-axis line charts. Pass an
explicit instance only to customise it. It is removed on dual-axis and facet
charts. When LVL already identifies the latest endpoint, the engine may
silently deduplicate a redundant endpoint `Callout`, `PointLabel`, or
`PointHighlight`.

`Trendline` is scatter-only and is removed from dual-axis line charts with a
warning. For per-group fits, prefer `chart_type='scatter_multi'` with
`mapping['trendlines']=True`.

`Trendline` and `LastValueLabel` are the two classes that need a continuous
axis and cannot be re-anchored onto a category one. Both are removed with a
reason in `result.warnings` when the axis they depend on is categorical —
`Trendline` on either axis (so also on a plain vertical bar), `LastValueLabel`
on y.

## 4. Coordinates and warnings

- A y-bearing annotation on a dual axis uses `axis='right'` and right-axis
  units. `VLine` is axis-agnostic.
- Keep point, line, arrow, and band coordinates inside the plotted data
  domains. The engine removes out-of-domain annotations to prevent whitespace
  and records the reason in `result.warnings`.
- A `Segment` identity line (`y=x`) on a macro/rates scatter is removed; use
  `Trendline` because the axes generally have different units.
- For “highlight values above X,” use
  `Band(y1=X, y2=df[value_col].max())`, not an unbounded band.
- Density is an editorial choice, not a technical limit. The engine will
  place a crowded set legibly, so choose the number of annotations by what
  the reader needs, not by fear of collisions.

Always inspect `result.warnings`. Unsupported or out-of-domain removals are
reported there; they are not build failures.

## 5. `layers=[...]`

Use structured annotation classes for narrative marks. `layers` is the
lower-level overlay surface for a regression, fixed rule, or secondary point
cloud:

```python
layers = [
    {"type": "regression", "x": "x_var", "y": "y_var", "method": "linear"},
    {"type": "rule", "y": 2.0, "color": "#DC143C",
     "stroke_dash": [4, 4]},
    {"type": "point", "x": "x_var", "y": "y_var",
     "data": highlight_df, "size": 180},
]
```

Layer dictionaries are strict:

| `type` | Required keys | Optional keys |
|---|---|---|
| `regression` | `x`, `y` field names | `method`, `color`, `stroke_width`, `stroke_dash` |
| `rule` | Exactly one of `x` or `y` | `color`, `stroke_dash` |
| `point` | `data=<DataFrame>`, `x`, `y` | `color`, `size` |

Unknown layer types, misspelled keys, missing required keys, and arbitrary
Vega-Lite dictionaries raise. Put narrative coordinates in annotation objects
instead of reproducing them as layers.

For a rule threshold, use the coordinate holding the thresholded variable:
`x=<threshold>` when that variable is `mapping['x']`, or `y=<threshold>` when
it is `mapping['y']`.

Do not combine multiple encodings merely for decoration. If an annotation or
layer is not essential to the analytical claim, omit it.
