# Composite layouts

Spoke fetched on demand from the chart_context hub. Covers `ChartSpec` (the per-sub-chart spec object) and the n-pack composite helpers (`make_2pack_horizontal`, `make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid`) that PRISM reaches for whenever charts share an x-axis, y-axis concept, or comparison dimension.

For per-chart-type rules in the sub-charts fetch `chart_types.md`. For the post-render Chart Center editor that ships with every composite fetch `chart_center.md`.

---

## 1. When to compose

Composites are almost always better than individual charts for related
data. If charts share an x-axis, y-axis concept, or comparison dimension
(US vs EU inflation, level + decomposition, 4 regional PMIs), they belong
in a composite. Use individual charts only for unrelated topics.

| Series count | Approach |
|---|---|
| 2-4 | Single `multi_line` (ideal) |
| 5-6 | `make_2pack_horizontal()`, 2-3 lines each |
| 7-8 | `make_4pack_grid()`, 2 lines each |
| 9+ | Aggregate / group series, or use `heatmap` |

---

## 2. ChartSpec & layout functions

```python
spec = ChartSpec(df=df, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'},
    title='Title', subtitle='Subtitle',
    annotations=[...], layers=[...])
```

Per-panel axis titles (`y_title`, `y_title_right`, `x_title`) live
INSIDE each `ChartSpec.mapping`, never as top-level `ChartSpec(...)`
kwargs (raises TypeError). Composite-level `title=` / `subtitle=`
describe the COMPOSITE; see `mapping.md` §1.

| Function | Layout | Positional Args |
|----------|--------|-----------------|
| `make_2pack_horizontal(c1, c2, ...)` | Side-by-side | 2 ChartSpecs |
| `make_2pack_vertical(top, bottom, ...)` | Stacked | 2 ChartSpecs |
| `make_3pack_triangle(top, bl, br, ...)` | 1 top + 2 bottom | 3 ChartSpecs |
| `make_4pack_grid(tl, tr, bl, br, ...)` | 2x2 | 4 ChartSpecs |
| `make_6pack_grid(r1l, r1r, r2l, r2r, r3l, r3r, ...)` | 3x2 | 6 ChartSpecs (also accepts `specs=[c1..c6]`) |

All accept keyword args (`title`, `subtitle`, `dimension_preset`, `save_as`,
`spacing`, `filename_prefix`, `filename_suffix`) and return a
`CompositeResult` with `.png_path`, `.download_url`, `.editor_html_path`,
`.editor_download_url`, `.success`, `.error_message`, `.chart_errors`.

---

## 3. Composite rules

ChartSpec args are positional, metadata keyword-only (never `top=spec_a`).
`save_as` works on all chart functions (`{session_path}/{save_as}`,
overwrites, no timestamp). QC the composite PNG, not sub-specs:
`check_charts_quality([composite_result])`. QC "completely empty" usually
means date still in index, y column all-NaN, or DataFrame empty after
filtering. Color / x / y scales resolve independently per sub-chart (each
panel keeps its palette and axis range); up to N-1 sub-charts can fail and
survivors still render (failures land in `result.chart_errors`).

---

## 4. Common patterns

| Situation | Layout |
|---|---|
| US vs EU inflation comparison | `make_2pack_horizontal` (same y-concept, different region) |
| Level + decomposition (rates path + 2s10s spread) | `make_2pack_vertical` (related metrics, vertically associated) |
| 4 regional PMIs | `make_4pack_grid` (2x2; each panel a region) |
| Headline + 2 supporting | `make_3pack_triangle` (top wide; two narrower beneath) |
| Sector dashboard (6 panels) | `make_6pack_grid` (3x2) |
