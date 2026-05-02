# Annotations & layers

Spoke fetched on demand from the chart_context hub. Covers every annotation class (parameter reference + chart-type compatibility), the discipline for when to add an annotation at all (anti-patterns + the principle), and the related `layers=[...]` overlay surface for regression / rule / point overlays.

For dual-axis-specific annotation behaviour (`HLine` / `Segment` / `PointHighlight` with `axis='right'`) fetch `dual_axis.md`.

---

## 1. The "is this annotation worth it?" filter

Annotations must be EXTREMELY useful, interesting, and core to the argument
the chart is making -- otherwise omit. Default to zero annotations and only
add one when it actively sharpens the narrative. The bar is high: every
annotation must reveal something the line/bar geometry alone cannot. Avoid
`PointLabel` (clutters), generic threshold lines, and text stating the obvious.

```python
T = pd.Timestamp
annotations = [
    HLine(y=2.0, label='Target', color='#00AA00'),
    VLine(x=T('2022-03'), label='Hike start', color='#003359'),
    Segment(x1=T('2015-01'), x2=T('2019-12'), y1=2.0, y2=2.0, label='2015-2019 avg'),
    Band(x1=T('2020-03'), x2=T('2020-06'), label='Recession', color='#CCCCCC', opacity=0.3),
    Arrow(x1=T('2020-04'), y1=5, x2=T('2021-03'), y2=8, label='Recovery', color='#0066CC'),
    PointHighlight(x=T('2022-06'), y=9.1, color='#C00000', size=120),
    Callout(x=T('2022-06'), y=9.1, label='Peak 9.1%', background='halo'),
    LastValueLabel(show_value=True),
]
```

---

## 2. Anti-patterns

Do NOT annotate visually obvious or universally known facts. Skip anything
the chart already conveys via geometry, axis labels, or basic reader
literacy. Test: "would a portfolio manager learn anything new from this
annotation?" If no, omit.

| Anti-Pattern | Why It's Trivial | Do Instead |
|---|---|---|
| `HLine(y=0, label='Zero'/'Flat'/'Break-even')` on a spread chart | The y-axis already shows zero | Omit; call out zero-crossings in narrative if they matter |
| `HLine(y=2.0, label='Fed 2% Target')` on inflation chart | Every macro reader knows the 2% target | Use the title: "Core PCE Still 80bp Above Target" |
| `HLine(y=last_value)` to label the latest reading | `LastValueLabel` already does this | Use `LastValueLabel(show_value=True)` |
| `VLine` at the latest data point labeled "Today" / "Now" | The chart's right edge IS today | Omit |
| `PointLabel` / `Callout` describing slope ("rising", "falling", "flat") | The line's slope conveys this | Omit; use the title to make the directional claim |
| `Band` covering the entire visible range, labeled "Sample period" | The whole chart IS the sample | Omit |
| Threshold lines at round numbers (`HLine(y=50)`, `HLine(y=100)`) chosen for visual reference | Round numbers carry no information unless they are policy / regime / target levels | Omit unless the threshold itself is the story |
| Multiple annotations crowding < 6 months of x-axis | Visual clutter beats narrative clarity | Pick the single most important; demote the rest to subtitle |

**Principle:** Annotate regime changes, policy shifts, hard event dates,
structural breaks, and threshold crossings that change interpretation.
Never decorate; never restate what the geometry already says. If you
cannot finish the sentence "this annotation shows the reader [X], which
they would not otherwise see", omit it.

---

## 3. Annotation parameter reference

| Annotation | Key Parameters & Notes |
|------------|------------------------|
| `VLine` | `x`, `label`, `color` (default `"#666666"`), `style` (`'solid'`/`'dashed'`/`'dotted'`), `stroke_dash`, `stroke_width`, `label_color`. Vertical rule spanning the full y-axis. Auto-staggers labels when multiple VLines cluster together. |
| `HLine` | `y`, `axis` (`'left'`/`'right'`), `label`, `color`, `style`, `stroke_dash`, `stroke_width`, `label_color`. Spans the FULL x-axis. `axis` only for dual-axis (default `'left'`). Default `stroke_dash` is `[4,4]`. |
| `Segment` | `x1`, `x2`, `y1`, `y2`, `label`, `color`, `style`, `stroke_dash`, `stroke_width`, `axis` (`'left'`/`'right'`), `label_position` (`'start'`/`'middle'`/`'end'`), `label_offset_x`, `label_offset_y`, `label_color`. Finite line segment (NOT full-axis). Common patterns: horizontal segment (`y1==y2`) for windowed average, vertical segment (`x1==x2`) for finite event mark, diagonal for ad-hoc connector. Aliases: `x_start`/`x_end`, `y_start`/`y_end`. |
| `Band` | `x1`/`x2` (vertical) OR `y1`/`y2` (horizontal), `label`, `color`, `opacity` (default `0.3`), `label_color`. Aliases: `x_start`/`x_end`, `y_start`/`y_end`, `start_x`/`end_x`. |
| `Arrow` | `x1`/`y1` (start), `x2`/`y2` (end), `label`, `color`, `stroke_width`, `stroke_dash`, `head_size`, `head_type` (`'triangle'`/`'none'`), `label_position` (`'start'`/`'middle'`/`'end'`), `label_color`. Aliases: `x_start`/`x_end`, `y_start`/`y_end`. |
| `PointLabel` | `x`, `y`, `label`, `dx`, `dy` (pixel offsets), `font_size`, `align`, `label_color`. Plain floating text. Use sparingly. |
| `PointHighlight` | `x`, `y`, `label`, `color` (default `"#C00000"`), `size` (default `100`), `opacity`, `shape` (`'circle'`/`'square'`/`'diamond'`/`'triangle'`/`'cross'`/`'stroke'`), `filled`, `stroke_color`, `stroke_width`, `axis` (`'left'`/`'right'`), `label_color`. Filled marker at a specific point. Often combined with `Callout` or `PointLabel` for a "labeled marker" effect. |
| `Callout` | `x`, `y`, `label`, `background` (`'halo'`/`'box'`/`'none'`), `background_color` (default `'#FFFFFF'`), `halo_width`, `box_padding_x`/`box_padding_y`, `box_opacity`, `box_corner_radius`, `color`, `dx`, `dy`, `font_size`, `font_weight`, `align`, `axis` (`'left'`/`'right'`), `label_color`. Text annotation with halo (text-stroke trick) or box background. Solves the "PointLabel fights gridlines" readability problem. Default `'halo'` is best for most charts. |
| `LastValueLabel` | `show_value` (default `False`), `value_format` (default `None` -- auto-pick magnitude-aware decimals; or pass a Python format like `"{:+.2f}"`/`"{:.0%}"`), `show_dot` (default `True`), `dot_size`, `dot_color`, `dx`, `font_size`, `font_weight`, `include_right_axis` (default `False`), `label_color`. Direct end-of-line labels for `multi_line` charts (FT/Bloomberg style; replaces the legend). Auto-derives labels from the color column. `label` is ignored on multi-series charts; for single-series it overrides the y-field name. |
| `Trendline` | `method` (`'linear'`/`'exp'`/`'log'`/`'pow'`/`'poly'`/`'quad'`), `label`, `color`, `stroke_width`, `stroke_dash`, `label_color`. Regression overlay on scatter charts. |
| `PlotText` | `text`, `position` (default `'auto'`; or any of 9 corner / edge anchors), `padding_x`, `padding_y`, `font_size`, `color`, `italic`, `align`, `max_width_pct`. In-plot narrative anchored to a corner. `position='auto'` picks the corner that collides least with the data (scores TL / TR / BL / BR by how far the data extends into each); bar / waterfall disqualify bottom corners. Use `'auto'` unless a specific corner is required. |

No `dash` / `line_style` / `linestyle` / `line_type` parameter exists --
use `style=` or `stroke_dash=`. All classes inherit `label` and
`label_color` from base `Annotation`.

---

## 4. Chart-type compatibility

Rule-style annotations (`HLine`, `VLine`, `Band`, `Callout`, `PointLabel`,
`PointHighlight`) are silently dropped on chart types without Cartesian
axes (`donut`, `pie`, `bullet`) -- use `title`/`subtitle` for context.
`LastValueLabel` and `Trendline` only apply to their native chart types
(`multi_line`/`area` and scatter respectively).

For bar-chart annotation compatibility (single-series vs stacked vs
horizontal vs grouped), see `chart_types.md` §2.

---

## 5. Layers

Stackable overlays applied AFTER the base chart. Use `annotations=[...]`
for VLine/HLine/Band/Arrow; `layers=[...]` only for a regression line,
threshold rule, or secondary point cloud.

```python
layers = [
    {'type': 'regression', 'x': 'x_var', 'y': 'y_var', 'method': 'linear'},
    {'type': 'rule', 'y': 2.0, 'color': '#FF0000', 'stroke_dash': [4, 4]},
    {'type': 'point', 'x': 'x_var', 'y': 'y_var', 'data': highlight_df, 'size': 200},
]
```
