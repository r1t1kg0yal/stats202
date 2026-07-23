# Altair chart colours and opacity

Fetch this spoke before any chart palette, per-series colour, hex, emphasis,
fade, transparency, `color_scheme`, `color_map`, `color_range`, `opacity`, or
`opacity_map` request. Skip it when the user did not ask for colour control;
the default `gs_primary` palette is production-ready.

This spoke is for `make_chart`. Table backgrounds and heatmap-style table
cells belong to `chart_context_tables.md`.

## 1. Five mapping kwargs

All colour controls live inside `mapping={}`:

| Key | Shape | Use |
|---|---|---|
| `color_scheme` | string | Named categorical palette or quantitative ramp |
| `color_map` | list or `{category/slot: colour}` | Explicit categorical colours |
| `opacity` | number from 0 to 1 | Uniform mark transparency |
| `opacity_map` | list or `{category/slot: opacity}` | Per-category transparency |
| `color_range` | `[start_colour, end_colour]` | Continuous scatter/phase gradient |

Top-level forms such as `make_chart(color_map=...)` raise. Common CSS colour
names are normalized by the engine, but hex is preferred for precision;
unknown names raise with the accepted alternatives.

## 2. Intent recipes

| Ask | Mapping addition |
|---|---|
| Colourblind-safe | `color_scheme='colorblind'` |
| Muted business palette | `color_scheme='business'` |
| Bold palette | `color_scheme='bold'` |
| Monochrome | `color_scheme='mono_navy'` or `'mono_grey'` |
| Pin named series | `color_map={'US': '#DC143C', 'EU': '#1F77B4'}` |
| Change second legend slot | `color_map={2: '#DC143C'}` |
| One colour for a single series | `color_map=['#DC143C']` |
| Highlight one series and fade peers | named `color_map` plus `opacity_map` for every highlighted/faded category |
| Uniform 50% alpha | `opacity=0.5` |
| Fade the second category | `opacity_map={2: 0.25}` |
| Diverging heatmap | `color_scheme='redblue'` |
| Sequential heatmap | `color_scheme='viridis'` or `'blues'` |

```python
mapping = {
    "x": "date", "y": "value", "color": "region",
    "color_map": {"US": "#DC143C"},
    "opacity_map": {"US": 1.0, "EU": 0.25, "APAC": 0.25},
}
```

Setting only `color_map={'US': ...}` changes US colour but does **not** fade
the other series.

## 3. Named categorical palettes

| Name | Use |
|---|---|
| `gs_primary` | Default GS brand palette |
| `colorblind` | Okabe–Ito colourblind-safe set |
| `bold` | High-contrast presentation |
| `pastel` | Low-saturation print/deck |
| `mono_navy` | Sequential same-metric categories |
| `mono_grey` | Neutral comparison |
| `business` | Muted FT/Bloomberg-style set |

Categorical colour has a hard 10-category cap. Filter or aggregate before
plotting; do not rely on palette cycling.

## 4. Explicit `color_map` and `opacity_map`

Dictionary keys may be:

- exact category strings; or
- positive integers representing **1-indexed rendered legend slots**.

Named keys win when a named and positional key address the same slot. Slot
order follows `color_sort` when supplied, otherwise data insertion order.
Out-of-range slots raise.

```python
# Named, positional, and mixed forms
{"color_map": {"US": "#DC143C", "EU": "#1F77B4"}}
{"color_map": {2: "#DC143C", 4: "#A6A6A6"}}
{"color_map": {"US": "#DC143C", 3: "#A6A6A6"}}

# A named scheme supplies fallback colours for unpinned categories
{"color": "country", "color_scheme": "colorblind",
 "color_map": {"US": "#DC143C"}}
```

Unpinned categories use `color_scheme` when present, otherwise `gs_primary`.
A list is a complete positional range; use a dictionary for partial overrides.

`opacity_map` uses the same key shapes. Unpinned categories retain the scalar
`opacity` when supplied, otherwise the engine's density/mark default.
Per-category opacity needs a categorical `color` field. `bar_horizontal` is
supported. Continuous gradient scatters use scalar `opacity`, not
`opacity_map`.

For single-series charts, `color_map=['#hex']` sets the mark colour. For
categorical pinning, supply `mapping['color']`; prefer `scatter_multi` for a
grouped scatter.

## 5. Heatmaps

Heatmaps encode magnitude, so `color_map` and `opacity_map` are rejected.
Use `color_scheme`:

| Family | Names |
|---|---|
| Sequential single hue | `blues`, `greens`, `reds`, `oranges`, `purples`, `greys` |
| Sequential multi hue | `viridis`, `plasma`, `magma`, `cividis`, `turbo`, `inferno`, `rainbow` |
| Diverging | `redblue`, `spectral`, `browngreen`, `redyellowblue`, `redyellowgreen`, `blueorange` |

Use a diverging scheme only when zero or a meaningful centre divides the
metric. Unsigned 0–100 data should use a sequential ramp. Uniform cell alpha
may use `opacity`.

## 6. Continuous scatter and phase gradients

When scatter `color` is temporal or numeric, it becomes a continuous ramp and
does not count against the 10-category cap. For an ordered path:

```python
mapping = {
    "x": "utilization",
    "y": "labor_share",
    "color": "date",
    "connect": True,
    "color_range": ["#DC143C", "#003359"],
}
```

`color_range` defines early and late endpoints and wins over `color_scheme`.
With neither override, the engine uses its red-to-blue HSV time ramp. A named
continuous scheme such as `viridis`, `cividis`, `turbo`, or `magma` is also
valid on the same temporal/numeric `color` encoding. Author either
`color_range` or `color_scheme`, not both; `color_map` does not apply to a
continuous encoding.

## 7. Chart-specific restrictions

- Heatmap rejects `color_map` / `opacity_map`.
- `bullet` and `waterfall` reject dictionary `color_map`; their semantic
  colours are engine-owned. A one-entry list may set the primary mark.
- `rainbow` is a quantitative ramp, not a categorical palette; use `bold` for
  vivid categories.
- Do not hand-author ticker colour registries when the user did not request
  colours. Omit all colour kwargs and preserve the default palette.
- Avoid encoding one category with both colour and line style unless the user
  explicitly needs both.
- A colourblind request should use `colorblind` without arbitrary non-safe hex
  overrides.

Colour and opacity validation joins the chart's other independent findings in
one `ValidationError`: invalid scheme, unknown colour, opacity outside 0–1,
wrong chart family, or illegal slot. Fix every numbered item and re-run.
