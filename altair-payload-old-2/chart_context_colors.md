# Altair Colours (`mapping['color_scheme']` / `mapping['color_map']`)

Spoke fetched on demand from `chart_context.md`. Covers per-chart palette and colour customisation across every chart type. Default behaviour (no kwarg passed) renders in the GS_PRIMARY brand palette — fetch this spoke ONLY when the user explicitly asks to change colours.

---

## 1. When to fetch this spoke

| User says | Reach for |
|---|---|
| "Use a colourblind-friendly palette" / "make it accessible" | `color_scheme='colorblind'` |
| "Make the US line red, EU blue, JP green" | `color_map={'US': '#DC143C', 'EU': '#1F77B4', 'JP': '#2CA02C'}` |
| "Highlight the US line in red, fade the rest" | `color_map={'US': '#DC143C'}` (others fall back to default palette) |
| "Make this chart [single hex]" | `color_map=['#DC143C']` (single-series) |
| "Use a navy-only / mono palette" | `color_scheme='mono_navy'` or `'mono_grey'` |
| "Use bold / vivid colours" | `color_scheme='bold'` |
| "Match Bloomberg / FT muted style" | `color_scheme='business'` |
| Heatmap: "flip to red-blue diverging" | `color_scheme='redblue'` (heatmap only) |
| Heatmap: "use a sequential green ramp" | `color_scheme='greens'` (heatmap only) |

Skip this spoke (use defaults) for any "make me a chart" request that does NOT mention colours, palette, hex, or theme. Default colours are already on-brand.

---

## 2. The two kwargs

Both live INSIDE `mapping={}`. Engine routes them per chart type.

| Kwarg | Type | Use |
|---|---|---|
| `color_scheme` | str | Named palette (categorical OR heatmap; engine validates context) |
| `color_map` | list[hex] / dict[cat: hex] | Explicit per-category colours; categorical only |

Both can be passed simultaneously. Resolution priority:

```
1. color_map dict {category: hex}      # specific categories pinned;
                                       # missing categories fall back to
                                       # the default palette (or
                                       # color_scheme palette if also set)
2. color_map list[hex]                 # range only, applied in legend order
3. color_scheme=<categorical name>     # named palette as range
4. (default)                           # GS_PRIMARY brand palette
```

---

## 3. Categorical palettes (multi_line, scatter_multi, bar+color, area+color, donut)

Seven PRISM-facing names. Engine rejects any other categorical name with a list of valid options.

| Name | Slot 0..N | Use case |
|---|---|---|
| `gs_primary` (default) | navy / light blue / mid blue / grey / red / cobalt / olive / purple / orange / teal | Production charts; brand-consistent |
| `colorblind` | orange / sky / green / yellow / dark blue / red / pink / black | Colourblind-safe (Okabe-Ito 8) |
| `bold` | electric blue / orange / red / green / purple / amber / teal | High-contrast presentations |
| `pastel` | soft sky / peach / mint / cream / lavender / pink | Light, low-saturation aesthetic; print / decks |
| `mono_navy` | five shades of navy from dark to light | Same-metric-different-tenor; sequential intent without hue change |
| `mono_grey` | five greys from black to light | Reference / comparison panel where colour shouldn't pull the eye |
| `business` | muted Tableau-10 set | FT / Bloomberg report aesthetic |

```python
make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value', 'color': 'series',
        'color_scheme': 'colorblind',
    },
    title='G7 GDP (colourblind-safe)',
)
```

Series count exceeds palette length → engine cycles through the palette. The 12-cardinality cap (§6.1 / hub) still applies.

---

## 4. Explicit `color_map`

### 4.1 Dict form — pin specific categories

```python
make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value', 'color': 'country',
        'color_map': {'US': '#DC143C', 'EU': '#1F77B4', 'JP': '#2CA02C'},
    },
    title='G3 GDP, hand-picked colours',
)
```

Categories not present in the dict fall back to `gs_primary` (or the palette named in `color_scheme` when both are set). Use the dict form for highlight-one patterns:

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'country',
    'color_map': {'US': '#DC143C'},   # US red; others on default palette
}
```

### 4.2 List form — colours in legend order

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'color_map': ['#003359', '#94C7DD', '#A6A6A6'],   # series #1 navy, #2 light blue, #3 grey
}
```

Engine cycles through the list; pass at least as many entries as distinct categories.

### 4.3 Single-series colour

```python
make_chart(
    df=df, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value',
        'color_map': ['#DC143C'],   # one hex for the one line
    },
    title='Just one red line',
)
```

Combine with `color_scheme` to set the fallback for missing dict keys:

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'country',
    'color_map': {'US': '#DC143C'},
    'color_scheme': 'colorblind',     # missing categories from Okabe-Ito
}
```

---

## 5. Heatmap palettes (`color_scheme` only)

`mapping['color_map']` is REJECTED on heatmap — the cells encode magnitude, not category identity. Use `color_scheme` to pick a Vega-Lite ramp.

| Kind | Names |
|---|---|
| Sequential single-hue | `blues`, `greens`, `reds`, `oranges`, `purples`, `greys` |
| Sequential multi-hue | `viridis`, `plasma`, `magma`, `cividis`, `turbo`, `inferno`, `rainbow` |
| Diverging | `redblue`, `spectral`, `browngreen`, `redyellowblue`, `redyellowgreen`, `blueorange` |

```python
make_chart(
    df=correlation_df, chart_type='heatmap',
    mapping={
        'x': 'a', 'y': 'b', 'value': 'corr',
        'color_scheme': 'redblue',     # diverging-at-zero
    },
)
```

Engine picks `blues` (sequential) by default. Override to `redblue` / `spectral` for diverging-at-zero data; pick `viridis` / `magma` for perceptually-uniform sequential.

---

## 6. Scatter phase-space gradient

Triggered by a temporal or numeric `mapping['color']` column on `scatter` / `scatter_multi` (see grids spoke §5). Engine picks `viridis` by default; override via `color_scheme`:

| Name | When |
|---|---|
| `viridis` (default) | Perceptually uniform; safe choice |
| `plasma` / `magma` / `inferno` | Same shape, hotter palette |
| `turbo` / `rainbow` | More-saturated rainbow; avoid for serious analysis |
| `cividis` | Colourblind-safe sequential |

```python
mapping = {
    'x': 'cpi', 'y': 'gdp', 'color': 'quarter',   # temporal -> gradient
    'color_scheme': 'plasma',
}
```

`color_map` does not apply (the color encoding is continuous).

---

## 7. Validation

Engine validates at the boundary, returns `ChartResult(success=False, error_message=...)`:

| Mistake | Engine message |
|---|---|
| Unknown palette name | `"... not a recognised palette. Categorical palettes: [bold, business, colorblind, gs_primary, mono_grey, mono_navy]. Heatmap / gradient palettes: blues, greens, ..."` |
| Categorical palette on heatmap | `"... is a categorical palette but chart_type='heatmap' needs a gradient ramp ..."` |
| Gradient ramp on categorical chart | `"... is a heatmap / gradient ramp but chart_type='multi_line' needs a categorical palette ..."` |
| `color_map` on heatmap | `"mapping['color_map'] is for categorical color encodings ..."` |
| Non-hex value in `color_map` | `"... must be a hex string like '#1A2B3C'."` |

The error message names the right alternative; PRISM should switch and re-render.

---

## 8. Anti-patterns

| Anti-pattern | Why |
|---|---|
| Cracking the skin to set every colour by hand | Brand consistency lives at the skin layer; `color_map` exists for one-off pinning, not bulk overrides. Use `color_scheme` for the look you want. |
| `color_scheme='rainbow'` on a categorical chart | `rainbow` is a HEATMAP / gradient ramp — categorical only accepts the names in §3. For "vivid rainbow" categorical use `bold`, or `color_map=[...]` with explicit hexes. Engine validation catches this. |
| `color_scheme='blue'` (singular) | Not a valid name. Sequential is `blues` (plural). Engine error names the alternatives. |
| `color_map` with rgb tuples or named CSS colours | Hex strings only (`'#DC143C'`); `'red'` / `(220, 20, 60)` rejected. |
| Per-series `strokeDash` AND `color_map` together | Engine renders both; eye gets overloaded. Pick one encoding per dimension. |
| `color_scheme='colorblind'` AND `color_map` with non-colourblind hex | Defeats the accessibility goal. Either trust `colorblind`, or hand-pick from the Okabe-Ito set yourself. |
| Heatmap `color_scheme='spectral'` on sequential data (single-sided range) | Diverging palettes assume a meaningful zero / centre; on 0-100 unsigned data they waste half the range. Use `viridis` / `blues` instead. |

---

## 9. Composite charts

Each `ChartSpec` carries its own `mapping`. Pass `color_scheme` / `color_map` per panel:

```python
spec_us = ChartSpec(
    df=df_us, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'series',
             'color_scheme': 'gs_primary'},
    title='United States',
)
spec_eu = ChartSpec(
    df=df_eu, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'series',
             'color_scheme': 'colorblind'},     # different palette per panel
    title='Eurozone',
)
make_2pack_horizontal(spec_us, spec_eu, title='Inflation by region')
```

For grid mode (`mapping['facet']`), the same `color_scheme` / `color_map` applies across every panel — set once on the single `make_chart` call.

---

## 10. Output

Returns a `ChartResult` (or `CompositeResult`) — same shape as the hub. No additional fields; the colour resolution lands in `vegalite_json` as the actual `scale.range` / `scale.domain` values rendered.
