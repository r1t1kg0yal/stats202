# Altair annotations and layers

Fetch this spoke before any `annotations=[...]` or `layers=[...]` call, or when
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
| `Segment` | `x1`, `x2`, `y1`, `y2`, `axis`, `label_position='start'|'middle'|'end'`, offsets, line styling |
| `Band` | `x1`/`x2` for vertical or `y1`/`y2` for horizontal, `axis`, `color`, `opacity` (default 0.3) |
| `Arrow` | `x1`, `y1`, `x2`, `y2`, `axis`, `head_size`, `head_type='triangle'|'none'`, `label_position`, offsets; straight only (`curved=True` raises) |
| `PointLabel` | `x`, `y`, `label`, `axis`, `dx`, `dy`, `font_size`, `align`, `halo` |
| `PointHighlight` | `x`, `y`, `axis`, `color`, `size` (default 100), `opacity`, `shape`, `filled`, stroke controls |
| `Callout` | `x`, `y`, `axis`, `background='halo'|'box'|'none'`, box/halo controls, `dx`, `dy`, typography |
| `LastValueLabel` | `dx` (default 6), `font_size` (default 15), `font_weight` |
| `Trendline` | `method='linear'|'exp'|'log'|'pow'|'poly'|'quad'`, `color`, `stroke_width`, `stroke_dash` |
| `PlotText` | `text`, `position='auto'|'left'|'right'|'bottom'`, `font_size`, `color`, `italic`, `align`, `width_pct` |

`PointHighlight.shape` supports `circle`, `square`, `diamond`, `triangle`,
`triangle-up`, `triangle-down`, `cross`, and `stroke`. Callout x-offsets are
clamped to the available chart width; do not rely on extreme offsets.

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
| Horizontal bar | `HLine` becomes a vertical value threshold |
| Grouped bar (`stack=False`) | Annotations do not render; use title/subtitle or stack/split |
| `multi_line` / `timeseries` | Rules, bands, segments, arrows, point classes, and callouts are supported; engine auto-injects `LastValueLabel` on a single axis |
| Dual axis | Fetch dual-axis spoke; y-bearing annotations need the correct `axis` |
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
- Use one or two narrative annotations in a tight time window; move secondary
  details to subtitle or caption.

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
