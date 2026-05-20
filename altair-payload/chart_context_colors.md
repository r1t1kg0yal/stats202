# Altair Colours (`mapping['color_scheme']` / `mapping['color_map']`)

Spoke fetched on demand from `chart_context.md`. Covers per-chart palette, colour, and opacity customisation. **PRISM MUST fetch this file (via `list_ai_repo`, see hub Spokes index) before authoring any `mapping['color_scheme']`, `color_map`, `opacity`, or `opacity_map` when the user asks to change colours, palette, hex, fade, highlight, or transparency on a chart.** Default behaviour (no kwarg passed) renders in the GS_PRIMARY brand palette — skip this spoke only when the user did not ask for any colour/opacity change.

---

## 1. When to fetch this spoke

| User says | Reach for |
|---|---|
| "Use a colourblind-friendly palette" / "make it accessible" | `color_scheme='colorblind'` |
| "Make the US line red, EU blue, JP green" | `color_map={'US': '#DC143C', 'EU': '#1F77B4', 'JP': '#2CA02C'}` (named) |
| "Highlight the US line in red, fade the rest" | `color_map={'US': '#DC143C'}` (named; others fall back to default palette) |
| "Fade the EU cluster, keep US opaque" | `opacity_map={'EU': 0.25}` on `scatter_multi` (others keep the engine density default) |
| "Make cluster 2 faint" / "slot 3 at 30% opacity" | `opacity_map={2: 0.3}` (1-indexed legend slot) |
| "All dots at 50% opacity" | `opacity=0.5` in mapping (uniform override) |
| "Make colour 2 red" / "Change the second colour" / "Slot 3 should be green" | `color_map={2: '#DC143C'}` (1-indexed legend slot; others default) |
| "Make slot 2 red AND slot 4 grey" | `color_map={2: '#DC143C', 4: '#A6A6A6'}` (multi-slot positional) |
| "Pin US red AND make slot 3 grey" | `color_map={'US': '#DC143C', 3: '#A6A6A6'}` (mixed name + slot) |
| "Make this chart [single hex]" | `color_map=['#DC143C']` (single-series) |
| "Use a navy-only / mono palette" | `color_scheme='mono_navy'` or `'mono_grey'` |
| "Use bold / vivid colours" | `color_scheme='bold'` |
| "Match Bloomberg / FT muted style" | `color_scheme='business'` |
| Heatmap: "flip to red-blue diverging" | `color_scheme='redblue'` (heatmap only) |
| Heatmap: "use a sequential green ramp" | `color_scheme='greens'` (heatmap only) |

Skip this spoke (use defaults) for any "make me a chart" request that does NOT mention colours, palette, hex, or theme. Default colours are already on-brand.

---

## 2. The colour + opacity kwargs

All live INSIDE `mapping={}`. Engine routes them per chart type.

| Kwarg | Type | Use |
|---|---|---|
| `color_scheme` | str | Named palette (categorical OR heatmap; engine validates context) |
| `color_map` | list[hex] / dict[cat: hex] | Explicit per-category colours; categorical only |
| `opacity` | float `0.0`–`1.0` | Uniform mark alpha (overrides skin default on any chart type that supports it) |
| `opacity_map` | list[float] / dict[cat: float] | Per-series alpha on categorical charts (`multi_line`, `area`, `bar`, `boxplot`, `donut`, `histogram`, `scatter`, `scatter_multi`); same named / 1-indexed slot keys as `color_map` |

**Anti-patterns:**

| Wrong shape | Why it fails | Right shape |
|---|---|---|
| `make_chart(... color_overrides={...})` — top-level kwarg | No such kwarg; engine raises `TypeError` | `mapping={'color_map': {...}}` |
| `make_chart(... color_map={...})` — top-level kwarg | Same | `mapping={'color_map': {...}}` |
| `chart_type='scatter'` + `mapping['color_map']` (no `mapping['color']`) | Engine has no category field to colour by; renders single-colour and ignores `color_map` | `chart_type='scatter_multi'` + `mapping={'color': 'category_col', 'color_map': {...}}` |

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

### 4.1 Dict form — pin specific colours (named OR positional, mix freely)

`color_map` accepts two key types in the same dict:

- **String keys** = category names. Match `df[color_field]` values exactly. Use when the user names the series ("make EU red").
- **Integer keys** = 1-indexed legend slot positions. Match what the user sees in the rendered legend. Use when the user references the colour by position ("make colour 2 red").

Categories not pinned by either form fall back to `gs_primary` (or the palette named in `color_scheme` when both are set). Named-key wins over integer-key when both apply to the same slot. Integer slots match legend display order (per `mapping['color_sort']` if set, else data insertion order); out-of-range integers raise a validation error naming the legal range.

| User said | Use |
|---|---|
| "Make EU red, JP blue" | `color_map={'EU': '#DC143C', 'JP': '#1F77B4'}` |
| "Highlight US in red, fade the rest" | `color_map={'US': '#DC143C'}` |
| "Make colour 2 red" / "Change the second colour" | `color_map={2: '#DC143C'}` |
| "Slot 2 red AND slot 4 grey" | `color_map={2: '#DC143C', 4: '#A6A6A6'}` |
| "Pin US red AND make slot 3 grey" | `color_map={'US': '#DC143C', 3: '#A6A6A6'}` |

```python
# Named: pin specific countries
make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value', 'color': 'country',
        'color_map': {'US': '#DC143C', 'EU': '#1F77B4', 'JP': '#2CA02C'},
    },
    title='G3 GDP, hand-picked colours',
)

# Positional: user said "make colour 2 red" — pin slot 2 only,
# everything else stays on the default GS palette
make_chart(
    df=df_long, chart_type='scatter_multi',
    mapping={
        'x': 'beta', 'y': 'return_pct', 'color': 'sector',
        'color_map': {2: '#DC143C'},
    },
    title='Factor returns by sector (2nd colour highlighted)',
)
```

Combine with `color_scheme` to set the fallback for unpinned slots:

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'country',
    'color_map': {'US': '#DC143C'},
    'color_scheme': 'colorblind',     # missing categories from Okabe-Ito
}
```

### 4.2 Per-series opacity (`opacity_map` / `opacity`)

On any chart with categorical `mapping['color']` (or `category` on donut), use `opacity_map` with the **same key shapes as `color_map`** to set different transparencies per series / cluster / slice:

- **Categorical scatters** also auto-scale default point opacity with point count when `opacity_map` is omitted (density curve). Other chart types use the skin mark default unless `opacity` / `opacity_map` overrides it.

When the user wants **different transparencies per cluster**, use `opacity_map` with the **same key shapes as `color_map`**:

- **String keys** = category names (`'EU': 0.25`)
- **Integer keys** = 1-indexed legend slots (`2: 0.3` = second cluster in the legend)
- Unpinned clusters keep the engine density default unless `opacity` is also set — then that scalar is the fallback for unpinned slots

`opacity` alone sets one alpha for **every** point (single-colour or multi-colour). Combine `color_map` + `opacity_map` to highlight one cluster in colour while fading the rest.

```python
# Highlight US in brand red; fade every other sector to 25% alpha
make_chart(
    df=df, chart_type='scatter_multi',
    mapping={
        'x': 'beta', 'y': 'return_pct', 'color': 'sector',
        'color_map': {'US': '#DC143C'},
        'opacity_map': {'US': 0.95, 'EU': 0.2, 'APAC': 0.2},
    },
    title='Factor returns — US highlighted',
)

# User said "make the second cluster faint" (legend order, not name)
make_chart(
    df=df, chart_type='scatter_multi',
    mapping={
        'x': 'x', 'y': 'y', 'color': 'group',
        'opacity_map': {2: 0.15},
    },
    title='Second cluster de-emphasised',
)
```

Gradient scatters (temporal / numeric `color` column) accept `opacity` only, not `opacity_map` — there is no discrete series to target.

```python
# Fade every series except US on a multi-line
make_chart(
    df=df_long, chart_type='multi_line',
    mapping={
        'x': 'date', 'y': 'value', 'color': 'country',
        'opacity_map': {'US': 1.0, 'EU': 0.25, 'JP': 0.25},
    },
    title='G3 CPI — US emphasized',
)
```

### 4.3 List form — full positional colour override

```python
mapping = {
    'x': 'date', 'y': 'value', 'color': 'series',
    'color_map': ['#003359', '#94C7DD', '#A6A6A6'],   # series #1 navy, #2 light blue, #3 grey
}
```

Engine cycles through the list when there are more categories than entries. Use the dict form (§4.1) for partial overrides; reach for the list form only when the user wants to specify every slot themselves.

### 4.4 Single-series colour

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
| `opacity_map` on heatmap | `"mapping['opacity_map'] is for categorical scatter clusters ..."` |
| Non-hex value in `color_map` | `"... must be a hex string like '#1A2B3C'."` |
| Opacity outside 0–1 | `"mapping['opacity'] must be between 0.0 and 1.0; got ..."` |
| `opacity_map` int key out of range | Same slot-range message shape as `color_map` |
| `color_map` int key < 1 | `"... integer keys are 1-indexed legend slot positions; got 0 (must be >= 1; slot 1 is the first colour, slot 2 the second, ...)."` |
| `color_map` int key out of range (e.g. `{5: ...}` on 3-cat chart) | `"... integer slot 5 is out of range; the chart's 'sector' column has 3 categories (legal slots: 1..3). Use the named-key form ({'<category>': '#hex'}) or pick a slot in range."` |

The error message names the right alternative; PRISM should switch and re-render.

---

## 8. Anti-patterns

| Anti-pattern | Why |
|---|---|
| Cracking the skin to set every colour by hand | Brand consistency lives at the skin layer; `color_map` exists for one-off pinning, not bulk overrides. Use `color_scheme` for the look you want. |
| `color_scheme='rainbow'` on a categorical chart | `rainbow` is a HEATMAP / gradient ramp — categorical only accepts the names in §3. For "vivid rainbow" categorical use `bold`, or `color_map=[...]` with explicit hexes. Engine validation catches this. |
| `color_scheme='blue'` (singular) | Not a valid name. Sequential is `blues` (plural). Engine error names the alternatives. |
| `color_map` with rgb tuples or named CSS colours | Hex strings only (`'#DC143C'`); `'red'` / `(220, 20, 60)` rejected. |
| List form to "just change one colour" (`color_map=['#003359', '#DC143C']`) | List is a FULL override; with N>2 categories Vega-Lite cycles back to slot 1's colour for slots 3+. To change just one slot, use the dict form with an integer key: `color_map={2: '#DC143C'}`. To change a named series, use the dict form with a string key: `color_map={'EU': '#DC143C'}`. |
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
