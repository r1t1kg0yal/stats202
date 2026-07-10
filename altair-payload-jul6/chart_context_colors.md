# Altair Colours (`mapping['color_scheme']` / `color_map` / `opacity` / `opacity_map`)

Spoke fetched on demand from `chart_context.md`. **MANDATORY before any `mapping` colour/opacity kwarg** when the user asks to change palette, hex, fade, highlight, transparency. Default (no kwarg) renders in GS_PRIMARY brand palette; skip this spoke only when no colour/opacity ask is in play.

---

## 1. When to fetch

| User says | Reach for |
|---|---|
| "Colourblind-friendly" / "make it accessible" | `color_scheme='colorblind'` |
| "US red, EU blue, JP green" | `color_map={'US': '#DC143C', 'EU': '#1F77B4', 'JP': '#2CA02C'}` (named) |
| "Highlight US, fade rest" | `color_map={'US': '#DC143C'}` (others → default palette) |
| "Fade EU cluster, keep US opaque" | `opacity_map={'EU': 0.25}` on `scatter_multi` |
| "Cluster 2 faint" / "slot 3 at 30%" | `opacity_map={2: 0.3}` (1-indexed) |
| "All dots at 50% opacity" | `opacity=0.5` |
| "Make colour 2 red" / "second colour" / "slot 3 green" | `color_map={2: '#DC143C'}` (1-indexed) |
| "Slot 2 red AND slot 4 grey" | `color_map={2: '#DC143C', 4: '#A6A6A6'}` |
| "Pin US red AND slot 3 grey" | `color_map={'US': '#DC143C', 3: '#A6A6A6'}` (mixed name + slot) |
| "Single hex on whole chart" | `color_map=['#DC143C']` (single-series) |
| "Navy-only / mono palette" | `color_scheme='mono_navy'` or `'mono_grey'` |
| "Bold / vivid colours" | `color_scheme='bold'` |
| "Bloomberg / FT muted" | `color_scheme='business'` |
| Heatmap: "red-blue diverging" | `color_scheme='redblue'` (heatmap only) |
| Heatmap: "sequential green ramp" | `color_scheme='greens'` (heatmap only) |

Skip for "make me a chart" with no colour / palette / hex / theme mention.

---

## 2. The kwargs

All live INSIDE `mapping={}`. Engine routes by chart type.

| Kwarg | Type | Use |
|---|---|---|
| `color_scheme` | str | Named palette (categorical OR heatmap; engine validates context) |
| `color_map` | list[hex] / dict[cat: hex] / dict[int: hex] | Explicit per-category colours; categorical only |
| `opacity` | float 0.0-1.0 | Uniform mark alpha (overrides skin default) |
| `opacity_map` | list[float] / dict[cat: float] / dict[int: float] | Per-series alpha on categorical charts (`multi_line`, `area`, `bar`, `boxplot`, `donut`, `histogram`, `scatter`, `scatter_multi`); same key shapes as `color_map` |

**Top-level kwargs rejected.** `make_chart(color_map={...})` / `make_chart(color_overrides={...})` raise `TypeError` -- must live in `mapping`. `chart_type='scatter'` + `mapping['color_map']` without `mapping['color']` ignores the map (no category to colour); use `'scatter_multi'` + `mapping={'color': 'cat_col', 'color_map': {...}}`.

Both `color_map` + `color_scheme` can be passed simultaneously. Resolution:

```
1. color_map dict {category: hex}      specific categories pinned; missing → default palette
                                       (or color_scheme palette if set)
2. color_map list[hex]                 range only, applied in legend order
3. color_scheme=<categorical name>     named palette as range
4. (default)                           GS_PRIMARY brand palette
```

---

## 3. Categorical palettes (multi_line, scatter_multi, bar+color, area+color, donut)

Seven PRISM-facing names. Engine rejects any other categorical name with the valid list.

| Name | Slots 0..N | Use case |
|---|---|---|
| `gs_primary` (default) | navy / light blue / mid blue / grey / red / cobalt / olive / purple / orange / teal | Production; brand-consistent |
| `colorblind` | orange / sky / green / yellow / dark blue / red / pink / black | Okabe-Ito 8 -- colourblind-safe |
| `bold` | electric blue / orange / red / green / purple / amber / teal | High-contrast presentations |
| `pastel` | soft sky / peach / mint / cream / lavender / pink | Low-saturation; print/decks |
| `mono_navy` | five navy shades dark→light | Same-metric-different-tenor; sequential without hue change |
| `mono_grey` | five greys black→light | Reference/comparison where colour shouldn't pull eye |
| `business` | muted Tableau-10 set | FT/Bloomberg report aesthetic |

```python
make_chart(df=df_long, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'series', 'color_scheme': 'colorblind'},
    title='G7 GDP (colourblind-safe)')
```

Series count > palette length → engine cycles. 10-cardinality cap still applies.

---

## 4. Explicit `color_map`

### 4.1 Dict form -- named OR positional (mix freely)

- **String keys** = category names (match `df[color_field]` exactly). User names the series ("make EU red").
- **Integer keys** = 1-indexed legend slot positions (what user sees in rendered legend). User names by position ("make colour 2 red").

Unpinned categories fall back to `gs_primary` (or `color_scheme` palette if both set). Named key wins over integer key on same slot. Integer slots match legend display order (per `mapping['color_sort']` if set, else data insertion). Out-of-range integers → validation error naming the legal range.

| User said | Use |
|---|---|
| "Make EU red, JP blue" | `color_map={'EU': '#DC143C', 'JP': '#1F77B4'}` |
| "Highlight US, fade rest" | `color_map={'US': '#DC143C'}` |
| "Make colour 2 red" / "second colour" | `color_map={2: '#DC143C'}` |
| "Slot 2 red AND slot 4 grey" | `color_map={2: '#DC143C', 4: '#A6A6A6'}` |
| "Pin US red AND slot 3 grey" | `color_map={'US': '#DC143C', 3: '#A6A6A6'}` |

```python
# Named: pin specific countries
make_chart(df=df_long, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'country',
             'color_map': {'US': '#DC143C', 'EU': '#1F77B4', 'JP': '#2CA02C'}})

# Positional: "make colour 2 red"
make_chart(df=df_long, chart_type='scatter_multi',
    mapping={'x': 'beta', 'y': 'return_pct', 'color': 'sector',
             'color_map': {2: '#DC143C'}})

# Combine with color_scheme: fallback for unpinned
mapping = {'x': 'date', 'y': 'value', 'color': 'country',
           'color_map': {'US': '#DC143C'},
           'color_scheme': 'colorblind'}     # missing → Okabe-Ito
```

### 4.2 Per-series opacity (`opacity_map` / `opacity`)

`opacity` alone sets one alpha for every mark. `opacity_map` uses same key shapes as `color_map` (string = category name; int = 1-indexed legend slot). Unpinned slots keep engine density default unless `opacity` also set -- then that scalar is the fallback.

Categorical scatters auto-scale default point opacity with point count when `opacity_map` is omitted (density curve). Gradient scatters (temporal/numeric `color`) accept `opacity` only -- no discrete series to target.

```python
# Highlight US in brand red; fade other sectors to 25% alpha
make_chart(df=df, chart_type='scatter_multi',
    mapping={'x': 'beta', 'y': 'return_pct', 'color': 'sector',
             'color_map': {'US': '#DC143C'},
             'opacity_map': {'US': 0.95, 'EU': 0.2, 'APAC': 0.2}})

# "Make the second cluster faint" (positional)
mapping = {'x': 'x', 'y': 'y', 'color': 'group', 'opacity_map': {2: 0.15}}

# Fade every series except US on multi-line
mapping = {'x': 'date', 'y': 'value', 'color': 'country',
           'opacity_map': {'US': 1.0, 'EU': 0.25, 'JP': 0.25}}
```

### 4.3 List form -- full positional override

```python
mapping = {'x': 'date', 'y': 'value', 'color': 'series',
           'color_map': ['#003359', '#94C7DD', '#A6A6A6']}   # #1 navy, #2 light blue, #3 grey
```

Engine cycles when more categories than entries. Use dict form for partial overrides; list form only when user wants every slot.

### 4.4 Single-series colour

```python
mapping = {'x': 'date', 'y': 'value', 'color_map': ['#DC143C']}   # one hex for the one line
```

---

## 5. Heatmap palettes (`color_scheme` only)

`mapping['color_map']` REJECTED on heatmap -- cells encode magnitude, not category. Use `color_scheme`:

| Kind | Names |
|---|---|
| Sequential single-hue | `blues`, `greens`, `reds`, `oranges`, `purples`, `greys` |
| Sequential multi-hue | `viridis`, `plasma`, `magma`, `cividis`, `turbo`, `inferno`, `rainbow` |
| Diverging | `redblue`, `spectral`, `browngreen`, `redyellowblue`, `redyellowgreen`, `blueorange` |

Default `blues` (sequential). Override to `redblue`/`spectral` for diverging-at-zero; `viridis`/`magma` for perceptually-uniform sequential.

```python
mapping = {'x': 'a', 'y': 'b', 'value': 'corr', 'color_scheme': 'redblue'}
```

---

## 6. Scatter phase-space gradient

Triggered by temporal or numeric `mapping['color']` on `scatter`/`scatter_multi` (grids spoke §5). Two ways to set the ramp:

**Explicit endpoints (preferred for orbits):** `mapping['color_range']=[start_hex, end_hex]` — early time = first colour, late time = second. The engine builds a multi-stop HSV ramp along the **longer hue arc** on the colour wheel (e.g. red→blue passes orange, yellow, green — not a direct RGB blend through purple).

```python
mapping = {'x': 'util', 'y': 'labor_share', 'color': 'date', 'connect': True,
           'color_range': ['#DC143C', '#003359']}   # red → navy
mapping = {'x': 'cpi', 'y': 'gdp', 'color': 'quarter',
           'color_range': ['#E63946', '#6A0DAD']}     # red → purple
```

**Default (no kwargs):** when both `color_range` and `color_scheme` are omitted, the engine uses the same HSV rainbow sweep from `#DC143C` (red) to `#1E90FF` (blue). Multi-stop ramps encode normalized time position (`0→1`) as quantitative color so Vega-Lite uses every stop (temporal encoding only interpolates the first two).

**Named scheme (explicit override):** set `color_scheme` alone to select a Vega-Lite ramp instead of HSV endpoints:

| Name | When |
|---|---|
| `viridis` | Perceptually uniform; safe |
| `plasma` / `magma` / `inferno` | Same shape, hotter palette |
| `turbo` / `rainbow` | More-saturated rainbow |
| `cividis` | Colourblind-safe sequential |

`color_range` wins over `color_scheme` when both are set. Legend shows first/last time only. `color_map` doesn't apply (continuous encoding).

---

## 7. Validation errors

Engine **raises** `ValidationError` (hub §1 failure contract) with the right alternative named; independent colour + opacity problems aggregate into one raise:

- Unknown palette name -- lists valid categorical / heatmap names
- Categorical palette on heatmap / gradient ramp on categorical -- crosses dispatch
- `color_map` on heatmap / `opacity_map` on heatmap -- wrong kwarg for the chart
- Non-hex in `color_map` -- must be `'#1A2B3C'` form
- Opacity outside 0-1
- `color_map` / `opacity_map` int key out of range or < 1 (slot 1 is the first colour)

Fix every named problem, then re-render.

---

## 8. Anti-patterns

| Anti-pattern | Why |
|---|---|
| Cracking the skin to set every colour by hand | Brand consistency lives at skin layer; `color_map` for one-off pinning, not bulk. Use `color_scheme` |
| Per-ticker `color_map` (`TICKER_COLORS`, `{AAPL: '#...', NVDA: '#...'}`) on routine multi-line overlays | No ticker→hex registry exists; user did not ask for colours. Omit `color_map`/`color_scheme` — default `gs_primary` slots apply in data-first-seen order |
| `color_scheme='rainbow'` on categorical | `rainbow` is heatmap/gradient. Vivid categorical → `bold` or `color_map=[...]` with explicit hexes |
| `color_scheme='blue'` (singular) | Not valid. Sequential is `blues` (plural) |
| `color_map` with rgb tuples or named CSS | Hex strings only (`'#DC143C'`); `'red'` / `(220, 20, 60)` rejected |
| List form to change one colour (`['#003359', '#DC143C']`) | List is FULL override; with N>2 cats Vega-Lite cycles back to slot 1 for slots 3+. Use dict with int key: `{2: '#DC143C'}`; or string key: `{'EU': '#DC143C'}` |
| Per-series `strokeDash` AND `color_map` together | Eye overloads. Pick one encoding per dimension |
| `color_scheme='colorblind'` AND `color_map` with non-colourblind hex | Defeats accessibility. Trust `colorblind`, or hand-pick from Okabe-Ito |
| Heatmap `color_scheme='spectral'` on sequential data (0-100 unsigned) | Diverging palettes assume meaningful zero/centre; wastes half the range. Use `viridis`/`blues` |

---

## 9. Composite charts

Each `ChartSpec` carries its own `mapping`. Pass `color_scheme` / `color_map` per panel:

```python
spec_us = ChartSpec(df=df_us, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'series', 'color_scheme': 'gs_primary'},
    title='United States')
spec_eu = ChartSpec(df=df_eu, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'series', 'color_scheme': 'colorblind'},
    title='Eurozone')
make_2pack_horizontal(spec_us, spec_eu, title='Inflation by region')
```

For grid mode (`mapping['facet']`), same `color_scheme`/`color_map` applies across every panel -- set once on the single `make_chart` call.

Returns `ChartResult` / `CompositeResult` -- same shape as hub. Colour resolution lands in `vegalite_json` as `scale.range` / `scale.domain`.
