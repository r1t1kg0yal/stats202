# Altair Charts & Tables (`make_chart`, `make_table`)

- **Module:** `chart_context`
- **Audience:** PRISM (all interfaces, all workflows), developers
- **Tier:** 2 (on-demand)
- **Scope:** All static-PNG chart + table authoring (chat / email / report). Composites here. Interactive HTML dashboards: `dashboards` (echarts).

`make_chart()`, `make_table()`, `build_charts()`, every annotation class (`VLine`, `HLine`, `Band`, `Callout`, `Segment`, `Arrow`, `PointLabel`, `PointHighlight`, `LastValueLabel`, `Trendline`, `PlotText`), `ChartSpec`, composite + `profile_df` helpers are AUTO-INJECTED into the sandbox namespace -- call them bare. Do NOT `import` any of them (no `from chart_context import ...`, no `from prism_charts import ...`): there is no such module and the import RAISES `ModuleNotFoundError` before any chart renders. Raw matplotlib blocked. `s3_manager` / `session_path` / `user_id` auto-inject at call time -- never pass them.

## Hard limits (anticipate these BEFORE authoring -- the engine raises, it never truncates)

The engine enforces these caps up-front and **raises** rather than silently clipping. Shortening strings in the DataFrame / kwargs is always the fix. When several independent gates fail, the engine raises ONCE with a numbered `N independent problems -- fix ALL, then re-run:` list -- fix every numbered item before re-running, never just the first.

**Caps are ceilings, not targets -- author every label well UNDER its cap, aiming roughly half.** The best label is the shortest string that still reads: prefer `'IT'` over `'Info Tech'` over `'Information Technology'`. A label that merely clears the cap is too long.

| Limit | Cap | Trips | Fix |
|---|---|---|---|
| Lines per `multi_line` / `area` panel | **6** (aim ≤4) | 7+ series on one canvas; LVL labels collide | 5-6 render but crowd → prefer composite (§10) or keep to 4; 7+ same-shape entities: facet (grids spoke); else split / aggregate (§3.1) |
| Axis title (`y_title` / `x_title` / `y_title_right`) | **24 chars** (aim ≤16) | long descriptive axis labels | abbreviate before `make_chart` |
| LVL end-of-line series name (`multi_line` / `area`) | **25 chars** (aim ≤12) | long melt column values auto-become LVL labels | rename in DataFrame before melting |
| Heatmap row + column labels | **15 chars** (aim ≤8) | correlation matrix ticker names, long categories | abbreviate row/col strings |
| Heatmap ROW COUNT (square corr / wide-universe) | rows must fit canvas height | 50×50 corr on one PNG | aggregate, facet, or split tables |
| Composite subtitle line-wrap | wraps to a cap that scales DOWN with composite width | long subtitles on wide 2-packs | shorten subtitle text |
| Bar category labels | **15 chars** (aim ≤8) | long x categories on vertical bars | abbreviate `x` column |
| Composite pack ceiling vs facet floor | packs take **2-6** cells; facet needs **7+** panels | 7 G7 lines on one panel, 8-panel ranking | `make_*pack_*` for ≤6 panels, facet 7-36 (grids spoke) |

When a cap is hit the error names the offending strings and suggests an abbreviation. See §4 for authoring rules that mirror these caps.

> **Tables default to PNG via `make_table()`** -- structured-data answers ship as static PNGs across all interfaces (chat / email / report / any artifact). Switch to markdown (`|...|...|` pipes, `print(df)` / `df.to_string()`, aligned text-blocks) only when the user asks for one or expresses a preference. Full surface: §13 (no spoke fetch).

---

## Catalog index

| Primitive | Names | Where |
|---|---|---|
| Chart types (11) | `multi_line`, `scatter`, `scatter_multi`, `bar`, `bar_horizontal`, `heatmap`, `histogram`, `boxplot`, `area`, `donut`, `waterfall` | §6 |
| Mapping keys (30+) | full table with types + defaults in §7.3 | §7.3 |
| Annotation classes (11) | names + params in §8.3 (usage example §8.1) | §8 |
| Composite functions (5) | `make_2pack_horizontal`, `make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid` | §10 |
| Grid mode | `mapping['facet']`, `facet_cols`, `same_scale`, `share_x` / `share_y` / `share_color` | spoke `chart_context_grids.md` |
| Chart colour / opacity | `mapping['color_scheme']`, `color_map`, `opacity`, `opacity_map` | spoke `chart_context_colors.md` -- **MUST fetch** |
| Static tables | `make_table` + `TableResult`; `df=` / `rows=`; 3 color modes (`'rwg'` / `'bw'` / `'rag'`); heatmap groups, multi-level headers, row groups / indent, totals / subtotals, sparklines, mini-bars, signed columns | §13 |
| Skin | `gs_clean` | §1 |
| Intent | `'explore'`, `'publish'`, `'monitor'` | §1 |
| Layer types | `regression`, `rule`, `point` | §8.4 |

---

## Spokes (mid-session fetch)

Mid-session reads use `list_ai_repo` with `mode="full"` -- pass ONLY `file_paths` and `mode`. `get_context()` is one-shot per user message.

| Spoke | Trigger | Tool call |
|---|---|---|
| `chart_context_grids.md` | 7-36 entities sharing one shape (G20 GDP, sector PMIs, FX cross-rates, country curves); scatter phase-space with temporal/numeric `color` | `list_ai_repo(file_paths=["context/modules/static/chart_context_grids.md"], mode="full")` |
| `chart_context_colors.md` | **MANDATORY** before any chart palette / per-series colour / hex / emphasis / fade / highlight / opacity ask on `make_chart`, incl. trivial ones ("US red", "slot 2 fainter") | `list_ai_repo(file_paths=["context/modules/static/chart_context_colors.md"], mode="full")` |

Skip both for "make me a chart" with no colour / opacity / facet language -- defaults are on-brand. `make_table()` colour (`column_color_modes`, `cell_colors`, `heatmap_groups`) is **§13, NOT the colours spoke.**

---

## Tables vs Charts

| Question shape | Reach for |
|---|---|
| Time series, distribution, scatter, ranking, regime, co-movement, lead-lag | `make_chart` (§1-12) |
| 7-36 entities sharing one shape | `make_chart` grid mode (grids spoke) |
| Structured rows × columns a chart can't visualise cleanly: watchlists, term structures, P&L attribution, factor tilts, FX cross-rates, sector tapes, calendars, snapshot dashboards, theme trackers, trade-idea lists | `make_table` (§13) |
| Single KPI tile | echarts dashboards (not altair) |

**Two distinct APIs, two distinct kwarg sets.** `make_chart` (§1-12) and `make_table` (§13) share NO kwargs. The §13 table-only kwargs (`column_formats`, `column_color_modes`, `rag_thresholds`, ...) are rejected by `make_chart` with a `TypeError` naming the kwarg.

---

## 1. `make_chart()` signature & `ChartResult`

```python
result = make_chart(
    df=df, chart_type='multi_line', mapping={...},
    title='Title',                # required for production
    subtitle='Subtitle',          # optional; NEVER for source attribution
    skin='gs_clean', intent='explore',
    annotations=[...], layers=[...],
    caption='note...',            # below-chart italic note
    side_left='...', side_right='...',   # str or {'text': ..., 'italic': True, ...}
    save_as='charts/name.png',    # overwrites, no timestamp
    auto_beautify=True,
    x_title=None, y_title=None, y_title_right=None,   # top-level == mapping[...] (§7.1)
    x_label=None, y_label=None,   # legacy aliases for x_title / y_title
    filename_prefix=None, filename_suffix=None,
)
```

Canvas size engine-decided per `chart_type`. `interactive=True` (default) auto-emits an interactive HTML companion alongside the PNG. `skin`: only `gs_clean` ships -- never pass anything else. `intent`: `'explore'` (default) / `'publish'` (fixed 700x400, no interactive params) / `'monitor'` (fixed 500x300 dashboard tile) -- leave default unless the artifact is a report or a tile.

**Auto-injected names:** `make_chart`, `make_table`, `build_charts` (§2a), `profile_df` (§5), `ChartResult` / `ChartSpec` / `TableResult` / `CompositeResult`, `check_charts_quality` (§2), all composites (§10), all 11 annotation classes (§8).

**`ChartResult` is a dataclass -- dot notation only; `result['png_path']` raises `TypeError`.**

| Attribute | Description |
|---|---|
| `png_path` / `download_url` | PNG S3 path / presigned URL |
| `editor_html_path` / `editor_download_url` / `editor_chart_id` | Interactive HTML companion -- surface alongside PNG |
| `vegalite_json` | Final Vega-Lite spec |
| `chart_type` / `skin` | Echoed |
| `success` / `error_message` | `True` on any returned result; failures **raise** (see Failure contract) |
| `warnings` | Fail-soft annotations (auto-melt, dropped annotations) -- caller may surface |
| `audit_trail` | Informational engine decisions (auto-recovered dual-axis, downsampling) -- chart is fine; do NOT surface as failures |

`CompositeResult` (from `make_Npack_*`) adds `layout`, `n_charts`, `chart_errors`; editor fields same as single charts. Per-cell failure details are folded into the raised `ValidationError` message (a returned `CompositeResult` has `success=True` and empty `chart_errors`).

**Failure contract.** `make_chart`, `make_table`, and the `make_*pack_*` composites **raise** `ValidationError` on failure -- it bubbles out and PRISM surfaces it; do **not** `try/except` to swallow it. A *returned* result therefore always has `success=True` (no `if not r.success` guard needed). **Independent validation failures aggregate into ONE raise** -- a numbered `N independent problems` list -- so fix every numbered item, then re-run once. **Composites raise if *any* sub-chart fails** -- one empty / broken panel raises the whole call (no partial render); each failing panel reports its complete finding list. Build every panel from validated, non-empty data before composing. Never `try/except` around chart calls: for 2+ charts use `build_charts()` (§2a), which aggregates per-chart failures engine-side; for a single eager chart, let it bubble.

---

## 2. Quality gate (MANDATORY)

This is non-negotiable: **every** chart and composite you render -- in every flow (chat, email, report, interactive companion, one-off, ad-hoc exploration) -- must pass through `check_charts_quality()` before you surface it; there is no situation in which a rendered chart skips the gate. Tables (`make_table`, §13) are the sole exception: they are deterministic and must NOT be sent to `check_charts_quality()`.

Every chart through `check_charts_quality()`. Fail-open if Gemini unavailable (treats the chart as passing so a QC outage never suppresses good charts); fail-closed on a missing/stale `png_path` (flagged, not rubber-stamped). Pass composites as single PNGs. Accepts `ChartResult`/`CompositeResult` objects, bare S3 `png_path` strings, or `{'png_path': ...}` dicts -- pass artifact paths directly when a multi-step pipeline no longer holds the result objects. Returns a list of plain dicts -- read verdicts with key access (`qc['passed']`, `qc['reason']`, `qc['png_path']`, `qc['description']`), never attribute access. Branch on `qc['passed']`, NOT on `verdict`. On a GOOD verdict `qc['description']` carries Gemini's viewer's-eye narration. On QC fail: `s3_manager.delete()` the PNG using `qc['png_path']` (returned on every verdict); fix or remove the call. (Build failures already raised upstream per §1, so every `r` here has rendered.)

```python
qc_results = check_charts_quality([r1, r2])
for qc in qc_results:
    if not qc['passed']:
        s3_manager.delete(qc['png_path'])
```

**Using the description (GOOD verdicts).** Numbers are ground truth for values in your script / DataFrame. The description is ground truth for what the chart *looks like* -- use it to sanity-check legend overlap, label clipping, colour emphasis, annotation placement, and empty-panel artefacts before surfacing. On BAD verdicts `qc['description']` is `""`; rely on `qc['reason']` for the fix. "Could not generate" is acceptable; showing a failed chart is not.

---

## 2a. Batch building -- `build_charts()` (MANDATORY for 2+ charts)

A bare sequence of `make_chart` calls stops at the **first** `ValidationError` -- every later chart is never attempted and its failure is invisible. Building 2+ chart calls in one script? Wrap each call as a `(name, thunk)` pair and pass them all to `build_charts()` (auto-injected): every chart is attempted, survivors render and save normally, and ALL failures aggregate into one raise naming each failed chart with its complete finding list. Names label the aggregate error (short snake_case); each thunk is a zero-arg callable invoking exactly one `make_chart` / `make_*pack_*` call with all kwargs wired (a composite counts as ONE call; define its `ChartSpec`s before the list and close over them). A single chart call never goes through `build_charts` -- call it directly.

```python
built = build_charts([
    ("us_cpi", lambda: make_chart(
        df=us_cpi, chart_type='multi_line',
        mapping={'x': 'date', 'y': 'value', 'color': 'series'},
        title='US CPI YoY', save_as='charts/us_cpi.png',
    )),
    ("spread", lambda: make_2pack_horizontal(
        spec_lhs, spec_rhs,
        title='US vs EU inflation', save_as='charts/spread.png',
    )),
])   # -> [(name, result), ...] survivors only

qc_results = check_charts_quality([r for _, r in built])
for qc in qc_results:
    if not qc['passed']:
        s3_manager.delete(qc['png_path'])
```

On failure the raise reads:

```
2 of 3 chart(s) failed to build:
  [seven_sectors]  2 independent problems -- fix ALL, then re-run:
    1. multi_line has 7 series ... over the 6-line cap ...
    2. Y-axis label '...' is 35 characters (max 24) ...
  [corr_matrix]  Heatmap row labels ... exceed ...
(survivor 'us_cpi' rendered)
```

The survivor parenthetical is NOT a ship signal: on a raise, surface nothing -- fix **every** named failure, re-run the whole batch (survivors re-render too; `save_as` overwrites), then QC the full `built` list. Do not cherry-pick one chart and re-run hoping the others were fine. **Anti-pattern:** `for spec in specs: make_chart(...)` with no `build_charts` -- first failure aborts silently for the rest. **Anti-pattern:** wrapping chart calls in your own `try/except` -- let single charts bubble per §1; let `build_charts` do the batching.

---

## 3. Design defaults

### 3.1 Default to composite when more than one story

2 panels is the default composite shape for an argument. 1 reads as anecdote; 4+ as dashboard.

| Shape | Layout | Use case |
|---|---|---|
| **2 panels (default)** | `make_2pack_horizontal` / `_vertical` | Compare/contrast: US vs EU, level + change, scatter + supporting series, before/after |
| 1 headline + 2 supporting | `make_3pack_triangle` | One main + two angles |
| 4 panels | `make_4pack_grid` | Regional/sector/scenario grid where grid IS the point |
| 6-panel dashboard | `make_6pack_grid` | True dashboards; not for arguments |
| 7-36 entities sharing one shape | grid mode (`mapping['facet']`) | Mag-7 / sectors / G20 / FX -- fetch grids spoke |
| 9+ series on one canvas | aggregate/group, or `heatmap` | Too many for any panel composite |

### 3.2 Annotations make charts argue

Default-include the annotation that makes the point legible at-a-glance. Skip for clean reference plots / exploratory work.

| Intent | Reach for |
|---|---|
| Threshold (Fed 2%, recession 0%, PMI 50) | `HLine` -- drop or minimise label; title carries directional claim (§8.2) |
| Regime / shaded period | `Band` |
| Point at latest / max / min / event | `Callout` |
| Event date | `VLine` |
| Forecast / regime-change segment | `Segment` |
| Best-fit on scatter | `Trendline` (or `mapping['trendline']=True`) |
| Below-plot note | `PlotText` |

### 3.3 Default to relationship charts in freeform analysis

When user hands chart-type pick ("analysis", "what's interesting"), lean toward shapes that DEMONSTRATE A RELATIONSHIP.

| Shape | Use case | Build |
|---|---|---|
| Scatter (+ trendline) | Direct X-Y: shape, strength, outliers | `'scatter'` + `mapping['trendline']=True`. Per-group: `'scatter_multi'` + `color=...` + `mapping['trendlines']=True` |
| Phase orbit | Distribution vs activity loop through time | `'scatter'` + `mapping['connect']=True` + temporal/numeric `color` (or `order`) — §6.1 |
| Squeeze / diffusion gauge | Single series vs a regime line (0, 50, …) | `'multi_line'` + `mapping['zero_fill']=True` + `zero_fill_baseline` — §6.1 |
| Dual-axis multi_line in change space | Co-movement over time. Both transformed to SAME change measure (YoY %, MoM %, log-diff) BEFORE charting | `'multi_line'` + `mapping['dual_axis_series']=[...]` (§9) |
| Lead-lag | Does X anticipate Y? | scatter `Y_t` vs `X_{t-N}`, or time-shift predictor `+N` → dual-axis + `VLine` "Today" — builds in §9.6 |

**Anti-pattern:** single-series `multi_line` on "is anything happening?" -- narrates, doesn't argue.

Engine rejects scatters with < 10 distinct (x, y) coords in the visible region (anecdote; error suggests bar / multi_line / table or a wider data window). For correlation across disparate magnitudes (gold + WTI) or levels (FCI components 30/60/10), the engine auto-recovers single-y-axis `multi_line` to dual-axis (§9.1) -- declare `dual_axis_series` yourself only when units differ but magnitudes overlap.

---

## 4. Authoring rules

- **Building 2+ charts in one script? Drive them through `build_charts()` (§2a)** instead of a bare sequence -- one run surfaces every failure, not just the first.
- **Up to 6 lines per `multi_line` / `area` panel (hard cap; engine raises at 7+) — but aim ≤4.** 4 or fewer reads cleanest; 5-6 still render but crowd and the LVL end-of-line labels start to collide, so prefer a composite (§10) or keep to 4. For 7+ same-shape entities: small-multiples facet (grids spoke); heterogeneous 7-8 series: 4-pack split (§10); 9+ series: aggregate or heatmap (§3.1). Composite cells each aim ≤4.
- **Axis titles: aim ≤16 (hard cap 24).** `y_title`, `x_title`, and `y_title_right` — abbreviate long descriptive labels before `make_chart`.
- **LVL end-of-line series names: aim ≤12 (hard cap 25).** Long melt column values auto-become LVL labels on `multi_line` / `area` — rename in the DataFrame before melting (§6.1).
- **Heatmap row + column labels: aim ≤8 (hard cap 15).** Correlation-matrix tickers and long categories — abbreviate row/col strings in the DataFrame (§6.3).
- **Bar category labels: aim ≤8 (hard cap 15).** Long x categories on vertical bars — abbreviate the `x` column before `make_chart` (§6.2).
- **Composite pack ceiling vs facet floor.** `make_*pack_*` helpers take **2-6** cells; facet (grids spoke) needs **7+** panels. Seven G7 lines on one panel or an 8-panel ranking: use packs for ≤6 panels, facet for 7-36 (grids spoke).
- **Labels: shortest string that still reads — caps are ceilings, aim roughly half.** Prefer `'IT'` over `'Info Tech'` over `'Information Technology'`.
- **X column must be `'date'` for time series, as a column.** `df.rename(columns={'datetime': 'date'}).reset_index()`.
- **Multi-line long format: rename FIRST, then melt** -- or use auto-melt (no `color` key, pass `y=[list]`).
- **No source attribution in title/subtitle.** Title argues; sources in PRISM metadata. Good: `title='Inflation Has Peaked'`, `subtitle='Core CPI decelerating 6 months'`. Bad: `title='US CPI Data'`, `subtitle='Source: Haver'`.
- **Clean before charting.** `pd.to_numeric(errors='coerce')` + `dropna(subset=['date', 'value'])`. Max 10 color cats; facet panel floor/cap (7 / 36) in the grids spoke. >5,000 rows auto-downsample to ~2,000 (warning).
- **Never plot `np.zeros()` placeholder.** Skip the panel or add text annotation.
- **Title/subtitle: 2-line cap, auto-wrap.** Engine reports exact char limit on rejection; explicit `\n` honored (counts toward cap). Wrapped titles grow the header band vertically only — font-size-aware pre-wrap keeps lines inside the plot width (never Vega-Lite ``title.limit``, which ellipsis-truncates).
- **Never truncate axis / legend / LVL labels.** Vega-Lite ``labelLimit`` ellipsis is forbidden -- overlong nominal labels raise typed errors (`BarCategoryLabelTooLongError`, `HeatmapColumnLabelTooLongError`, `HeatmapRowLabelTooLongError`, `LegendLabelTooLongError`, `LvlSeriesNameTooLongError`). Shorten strings in the DataFrame; the engine will not silently clip.

---

## 5. `profile_df`: pre-charting analysis

Verify columns, dtypes, missingness, cardinality, date coverage. Returns `DataProfile` dataclass: `columns`, `dtypes`, `shape`, `temporal_columns`, `numeric_columns`, `categorical_columns`, `cardinality`, `missing_pct`, `date_range`, `numeric_stats`. `.to_dict()` to serialise.

```python
profile = profile_df(df)
profile.shape           # (rows, cols)
profile.cardinality     # {'series': 4, 'date': 252, ...}
profile.date_range      # {'date': {'min': '...', 'max': '...'}}
```

---

## 6. Chart types

### 6.1 Type catalog

| Type | Use case | Required mapping |
|---|---|---|
| `multi_line` | Time series, curve evolution | `x`, `y`, `color` (opt) |
| `scatter` | X-Y relationships | `x`, `y` |
| `scatter_multi` | Grouped scatter + trendlines | `x`, `y`, `color` |
| `bar` | Category comparisons only -- NEVER time series (stacked/grouped via `stack`) | `x` (cat), `y`, `color` (opt) |
| `bar_horizontal` | Horizontal category comparisons -- NEVER time series | `x`, `y` (cat) |
| `heatmap` | Matrices | `x`, `y`, `value` (NOT `'color'`) |
| `histogram` | Distributions | `x` |
| `boxplot` | Distribution comparison | `x` (cat), `y` — engine renders x labels at -45° |
| `area` | Stacked time series | `x`, `y`, `color` |
| `donut` | Part-to-whole | `theta`, `color` |
| `waterfall` | Additive decomposition | `x` (cat), `y`, `type` (opt) |

`timeseries` is an alias for `multi_line`. `multi_line` auto-detects non-datetime x → ordinal mode; tenor values (`1M`, `2Y`, `10Y`) auto-sort by maturity.

**Intraday x-axis (minute / hour bars).** Pass ``datetime64[ns]`` (strings / epoch / tz-aware also normalized); do NOT pre-format to strings or set ``x_type='ordinal'``. Default clock US/Eastern (ET) — override via ``mapping['x_timezone']``. The engine picks date-vs-``HH:MM`` ticks by span.

**Phase orbit (`scatter` + `connect`).** Goodwin-style phase portraits: plot (x, y) with `mapping['connect']=True` for a time-ordered path instead of isolated dots. Needs `mapping['order']` or a temporal/numeric `mapping['color']` for sequence. Set ramp endpoints via `mapping['color_range']=['#start', '#end']` (early→late, HSV rainbow through the longer hue arc), or `color_scheme='turbo'` etc. — see `chart_context_colors.md` §6. Incompatible with `trendline=True`.

**Baseline fill gauge (`multi_line` + `zero_fill`).** Single-series line shaded above/below a horizontal baseline — squeeze gauge at 0, ISM diffusion at 50, etc. Set `mapping['zero_fill']=True` and `mapping['zero_fill_baseline']=50` (default `0`). Optional `zero_fill_positive` / `zero_fill_negative` hex overrides. Single-series only; incompatible with `color`, dual-axis, `strokeDash`, log scale.

**End-of-line labels (LVL), not colour legend, on `multi_line` / `timeseries`.** Series name paints at the line's right end (FT/Bloomberg), in the line's own colour — `color_map` / `color_scheme` overrides flow through to the labels automatically. Auto-injected on every single panel **and every pack-composite cell**. **Series names aim ≤12 (cap §Hard limits)** -- longer raises `LvlSeriesNameTooLongError`; rename in DataFrame (`'United States Equities Index 500'` → `'S&P 500'`). Customise via explicit `LastValueLabel(dx=..., font_size=..., font_weight=...)` (wins). **Dual-axis (`dual_axis_series`): no LVL** -- end-of-line text collides with the right y-axis, so the colour legend renders instead (§9.4). Facet grids (`mapping['facet']`) strip LVL -- see grids spoke.

**Colour-legend series names** apply only when the legend is visible (dual-axis, or explicit `mapping['legend']=True`): must fit the cell-width budget or the engine raises `LegendLabelTooLongError`. On dual-axis with 3+ lines the engine auto-appends ` (LHS)` / ` (RHS)` to disambiguate axis binding; disable via `mapping['dual_axis_legend_tags']=False`. Pack composites with LVL show no colour legend.

**Seasonal-jaggedness gate (`multi_line` / `timeseries` / `line` / `area`).** A weekly/monthly/quarterly series with a strong, regular every-period swing (e.g. raw quarterly revenue with a holiday-quarter spike) is REJECTED with `SEASONAL JAGGEDNESS`. Checked per series, incl. composite cells. Fix: seasonally adjust, plot YoY % change, or take a trailing rolling mean/sum over one full period (e.g. 4-quarter rolling sum). A low-frequency series (quarterly SEP dots, an annual projection) step-filled onto a denser grid manufactures the same flat-then-jump sawtooth — keep it at native cadence (concat in long format; the sparse line draws between its observation dates) or plot it as `scatter` point markers on the shared timeline, not forward-filled onto the dense grid (this is the §6.5 carve-out).

**Series-oscillation gate (`multi_line` / `timeseries` / `line` / `area`).** When two horizons or series are interleaved at every x-date without `mapping['color']` (canonical: MSFT panel in a Mag-7 EPS facet grid), REJECTED with `SERIES OSCILLATION` — distinct from seasonal jaggedness (reverses on nearly every step with large vertical jumps). Fix: add `mapping['color']`, filter to one horizon per x, use `mapping['facet']`, or split with `dual_axis_series`.

**Stacked-area alignment gate (`area` + `color`).** When series report on different calendars so layers don't share x-values → REJECTED with `SERIES MISALIGNMENT` (the stack shatters into white gaps). Fix: resample every series onto a common period grid (e.g. quarter-end, forward-filled) before stacking.

**Empty-body / coverage gate (`multi_line` / `timeseries` / `area`).** A line/area interpolates across NaNs, so a series >90% missing (per `color` group; per melted column for wide input; whole `y` for single-series) is REJECTED with `EMPTY CHART BODY` — it clears the ≥2-valid-points check but draws nothing. Usual cause: a filter/join whose category spelling doesn't match the source (e.g. `isin(['Treasury Inflation-Protected Securities'])` when the API spells it otherwise) leaves a dense date grid that's almost all holes. Fix: verify the filter matches rows; `df = df.dropna(subset=['value'])` so surviving points draw a line; or `chart_type='scatter'` if only a few discrete observations exist per series.

### 6.2 Bar family

**Bars are categorical-only.** `bar` / `bar_horizontal` require a categorical (string / ordinal) `x` -- NEVER a datetime / temporal axis. There is no bar-chart time series: continuous time series route to `multi_line` / `area` (additive decomposition → `waterfall`), including signed flow / issuance / surprise / net-position tapes that might otherwise read as thin bars over time. Discrete periods (quarters, months) belong on bars ONLY as string labels (`"Q1 2025"`, `"Jan"`), which makes them categorical -- never pass the raw datetime.

`stack=True` (default with color) for parts-of-whole; `stack=False` for grouped side-by-side. Don't sign-key colour (`'Positive'`/`'Negative'`) -- bar position vs zero conveys sign.

**One unit per value axis.** A bar's length IS its value, so categories carrying different units on one shared axis (`'HY chg (bp)'` ≈58, `'SPX (%)'` ≈-2.5, `'VIX (pts)'` ≈3.1) let a large-unit bar dwarf an economically larger small-unit one — the engine **raises** when it detects 2+ unit families. Split into one panel per unit (`make_3pack_triangle` / `make_2pack_*`) or normalize every category to a common unit (z-score / rebase-to-100 / %-change) before charting. (Bars always anchor at zero and zero-valued bars draw a baseline tick — no author action.)

```python
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product'}                  # stacked
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product', 'stack': False}  # grouped
```

**Category labels aim ≤8 (cap §Hard limits)** on every bar chart (`bar` / `bar_horizontal` / grouped / stacked / single / composite — same cap). Longer raises `BarCategoryLabelTooLongError`; shorten in the DataFrame to the shortest readable form (`'Information Technology'` → `'IT'`, `'Manufacturing PMI Composite'` → `'Mfg PMI'`).

Grouped clamps facet width to cell budget; below ~3px per bar (~60+ cats compact, ~200+ standalone) engine raises `GROUPED BAR CELL-BUDGET ERROR` -- switch to `stack=True`, reduce categories, or render standalone. `bar_horizontal` same on height.

| Bar mode | Annotation support |
|---|---|
| Single-series | `HLine`, `VLine`, `Band`, `Arrow`, `PointLabel` |
| Stacked | `HLine` clamped against stacked totals |
| `bar_horizontal` | `HLine` → vertical threshold |
| Grouped (`stack=False`) | Annotations DO NOT render -- use title/subtitle or `stack=True` |

### 6.3 Heatmap

**Data shape:** pass long (`x`/`y`/`value` columns), wide (an id column + one value column per category, e.g. `[ticker, 2016…2023]` or `[date, AAPL, MSFT…]`), or a matrix indexed by the row category — the engine auto-reshapes to long; never melt/pivot by hand. Always name `x`, `y`, `value` as the *intended* fields; for wide/matrix input the field name not present as a column labels the melted axis (or values), and `value` may be omitted (defaults to `value`). Ambiguous shapes (≥2 id-like / non-numeric columns, or a matrix with a default RangeIndex) raise `ValidationError` naming the exact reshape.

```python
mapping = {'x': 'year', 'y': 'ticker', 'value': 'op_margin'}   # wide df=[ticker, 2016…2023] (y is the id col)
mapping = {'x': 'date', 'y': 'ticker', 'value': 'ret'}         # wide df=[date, AAPL, MSFT…]  (x is the id col)
mapping = {'x': 'factor', 'y': 'factor', 'value': 'corr'}      # matrix: index + cols = factors (correlation)
```

`value` column renders as cell colour. Two recipes by dtype:

| `value` dtype | Color scale | Cap |
|---|---|---|
| numeric | quantitative; sequential, OR diverging-at-zero when min<0<max | warned >500 cells |
| categorical / string | nominal sequential ramp indexed by sort order; cell label is the bin | ≤10 distinct bins (rejected above) |

For categorical recipe (continuous binned to labels), bin via `pd.cut()` / `np.digitize()`. Override sort via `mapping['value_sort']=[...]`.

**Column labels (x-axis):** aim ≤8 (cap §Hard limits). Overlong values raise `HeatmapColumnLabelTooLongError`; shorten in the DataFrame. The engine sets angle and thins dense ticks (calendar-aware) — do not pass `labelAngle` / tick counts.

**Temporal x columns:** pass raw timestamps, ``.dt.year`` / ``groupby`` integers, quarter tokens, pandas Period, or epoch ms — the engine materialises readable period labels (``Q2 25``, ``2024``, ``Oct 24``, sub-daily ``05-27 09:30``); do not set ``x_type='ordinal'`` to block it. Full month names (``January 2024``) are rejected — use abbreviated ``%b %y`` (``Jan 24``). Mixed temporal + categorical x, or epoch-ms blended with quarter/year strings, raises ``ValidationError``.

**Row labels (y-axis):** always horizontal, never truncated. Aim ≤8 (cap §Hard limits); overlong values raise `HeatmapRowLabelTooLongError` — shorten in the DataFrame.

```python
df['prob_bucket'] = pd.cut(df['Probability'], bins=10,
    labels=[f'{i*10}-{(i+1)*10}%' for i in range(10)])
mapping = {'x': 'meeting_date', 'y': 'fed_funds_rate', 'value': 'prob_bucket'}
```

### 6.4 Waterfall

Additive decomposition (CPI/GDP, P&L, FCI impulse): bars float, each starts where previous ended. `type` optional -- absent means first/last rows are totals, intermediates signed by value. Colour: positive green (`#2EB857`), negative red (`#DC143C`), totals skin primary. Engine warns if intermediates don't sum to `(last - first)` within 15%.

```python
df = pd.DataFrame({
    'component': ['Start', 'Energy', 'Food', 'Core Goods', 'Core Services', 'End'],
    'contribution': [3.0, -0.4, -0.2, 0.1, 0.6, 3.1],
    'type': ['total', 'negative', 'negative', 'positive', 'positive', 'total'],
})
mapping = {'x': 'component', 'y': 'contribution', 'type': 'type', 'y_title': 'CPI YoY (%)'}
```

### 6.5 Haver frequency hygiene

Haver stores many monthly/quarterly at business-daily granularity (same value ~22 days). Symptom: stair-step lines. Resample to native frequency BEFORE charting. Merging mixed-frequency creates NaN gaps -- resample to lowest common frequency before `concat` / `merge`. Carve-out: do NOT *upsample* a sparse low-frequency projection (SEP dots, annual targets) onto a denser grid to align it with a daily series -- that manufactures the §6.1 step-sawtooth. Concat at native cadences in long format (dense series draws continuously, sparse draws between its dates), or split into a 2-pack.

| Series type | Resample | Example |
|---|---|---|
| Point-in-time / stock | `.last()` | Housing starts, unemployment rate |
| Flow / cumulative | `.mean()` or `.sum()` | Initial claims (mean), retail sales (sum) |
| Rate / percentage | `.last()` or `.mean()` | CPI YoY, mortgage rate |

---

## 7. Mapping reference

### 7.1 Axis-title kwargs

`x_title` / `y_title` / `y_title_right` accepted both INSIDE `mapping={}` and as TOP-LEVEL kwargs on `make_chart()` / `ChartSpec(...)`; engine routes top-level into `mapping`, `mapping[...]` wins on conflict. `x_label` / `y_label` are legacy aliases for the top-level form. Composite `title=` / `subtitle=` describe the COMPOSITE; set per-panel axis titles on each `ChartSpec`.

### 7.2 Basic patterns

```python
mapping = {'x': 'date', 'y': 'value', 'y_title': 'GDP Growth (%)'}                      # basic
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}                                # multi-series (long)
mapping = {'x': 'date', 'y': ['col_a', 'col_b']}                                        # auto-melt (wide)
mapping = {'x': 'tenor', 'y': 'yield_pct', 'color': 'curve_date'}                       # profile/curve
mapping = {'x': 'x_var', 'y': 'y_var', 'color': 'group', 'trendlines': True}            # scatter + trendlines
mapping = {'x': 'util', 'y': 'labor_share', 'color': 'date', 'connect': True}          # phase orbit (§6.1)
mapping = {'x': 'date', 'y': 'ism_mfg', 'zero_fill': True, 'zero_fill_baseline': 50}    # baseline gauge (§6.1)
mapping = {'x': 'date', 'y': 'value', 'color': 'series',                                # dual axis (§9)
           'dual_axis_series': ['Right Axis Series'],
           'y_title': 'Left Label', 'y_title_right': 'Right Label'}
```

### 7.3 All mapping keys

| Key | Type | Description |
|---|---|---|
| `x` | str | X-axis column |
| `y` | str / list | Y-axis column(s); list triggers auto-melt |
| `color` | str | Grouping column for multi-series |
| `y_title` / `y_title_right` / `x_title` | str | Axis labels (≤24 chars hard, aim ≤16); right Y dual-axis only |
| `x_sort` / `y_sort` | list | Explicit ordinal sort (x) / heatmap y-sort |
| `x_type` | str | Force `'ordinal'` on non-temporal categoricals (yield-curve tenors); NOT for intraday datetime |
| `x_timezone` | str | Intraday display clock override (default ET / `America/New_York`). Aliases: `UTC`, `LON`, `US/Eastern` |
| `dual_axis_series` / `dual_axis_bind` | list / dict | Right-axis series names, **or** per-series bind dict (`{'Series A': 'left', 'Series B': 'right'}`; aliases `lhs`/`rhs`). Pass one mechanism, not both. Unlisted series default left. |
| `dual_axis_legend_tags` | bool | Append ` (LHS)` / ` (RHS)` to colour-legend entries. Default `True` when 3+ series; `False` on 2-series dual-axis. |
| `invert_right_axis` | bool | Flip right axis (higher = bottom) |
| `dual_axis_config` | dict | Pin dual-axis y domains: `{'y_domain_left': [lo, hi], 'y_domain_right': [lo, hi]}` |
| `legend` | bool | Show/hide (auto by default) |
| `trendline` / `trendlines` | bool | Overall (scatter) / per-group (scatter_multi) |
| `connect` | bool | `scatter`: time-ordered path through (x, y); needs `order` or temporal/numeric `color` |
| `order` | str | Path sequence column for `connect` (optional when `color` is temporal/numeric) |
| `zero_fill` | bool | Single-series line: shade above/below baseline |
| `zero_fill_baseline` | float | Baseline for `zero_fill` (default `0`; e.g. `50` for ISM) |
| `zero_fill_positive` / `zero_fill_negative` | str | Hex overrides for above-/below-baseline fill |
| `stack` | bool | Bar+color: `True` stacked (default), `False` grouped |
| `strokeDash` / `strokeDashScale` / `strokeDashLegend` | str/dict/bool | Line-style col / `{domain, range}` / show legend (default `False`) |
| `value` / `theta` | str | Heatmap cell value / donut magnitude |
| `type` | str | Waterfall bar type (`total`/`positive`/`negative`) |
| `bins` / `maxbins` | int | Histogram bin count (aliases) |
| `bin_extent` | list | Histogram bin range `[lo, hi]` |
| `extent` | float | Boxplot whisker IQR multiplier (default `1.5`) |
| `scale_type` | str | `'linear'` / `'log'` override on auto log-scale detection |
| `orientation` | str | `'vertical'` opt-out from `bar` auto-flip on long category labels |
| `color_sort` (alias `legend_sort`) | list | Explicit category order in legend |
| `value_sort` | list | Heatmap value-driven sort |
| `facet_order` | list | Explicit panel-id order in grid mode |

**Colour kwargs live in the spoke:** `color_scheme`, `color_range`, `color_map`, `opacity`, `opacity_map` -- fetch `chart_context_colors.md` first; do not add from memory.

### 7.4 strokeDash: per-series line styles

`multi_line` only (single y-axis; NOT dual-axis or profile/curve). Use when lines share colour but differ in style (actuals vs estimates). Auto-scale: 2 cats → solid + dashed; 3 → adds dotted; 4+ Altair auto. Legend suppressed by default; `strokeDashLegend: True` to show.

```python
mapping = {'x': 'date', 'y': 'value', 'color': 'company',
           'strokeDash': 'type',                    # 'Actual' vs 'Estimate'
           'strokeDashScale': {'domain': ['Actual', 'Forecast'], 'range': [[1, 0], [8, 3]]},
           'y_title': 'Capex ($B)'}
```

---

## 8. Annotations & layers

### 8.1 "Is this annotation worth it?"

Default to zero. Add only when it sharpens narrative. Test: "would a PM learn anything new?" If no, omit. Avoid `PointLabel` (clutters), generic threshold lines, text stating the obvious.

```python
T = pd.Timestamp
annotations = [
    HLine(y=2.0),                                                # threshold; no label (§8.2)
    VLine(x=T('2022-03'), label='Hike start'),
    Segment(x1=T('2015-01'), x2=T('2019-12'), y1=2.0, y2=2.0, label='2015-2019 avg'),
    Band(x1=T('2020-03'), x2=T('2020-06'), label='Recession', opacity=0.3),
    Arrow(x1=T('2020-04'), y1=5, x2=T('2021-03'), y2=8, label='Recovery'),
    PointHighlight(x=T('2022-06'), y=9.1, size=120),
    Callout(x=T('2022-06'), y=9.1, label='Peak 9.1%', background='halo'),
    LastValueLabel(dx=10, font_weight='bold'),  # customise default LVL; bare LastValueLabel() is redundant
]
```

### 8.2 Anti-patterns

| Anti-pattern | Why |
|---|---|
| `Segment(...)` "y=x / 45-deg / identity" on scatter | Macro/rates axes are different units; engine drops silently. Use `Trendline` |
| Any annotation outside the visible plot domain (`Band` edge above data; `Segment`/`Arrow` endpoint off-data; `PointLabel`/`PointHighlight`/`Callout` off-data coord) | Shared scale expands to include the coord, stretching the frame; engine drops silently. Keep coords inside data; put narrative thresholds in title/subtitle. For "highlight above X": `Band(y1=X, y2=df['value'].max())`. `HLine` drops if y outside but doesn't stretch |
| `HLine(y=2.0, label='Fed 2% Target')` -- redundant label on known threshold | Drop the label (or shrink to `'2%'`); title carries directional claim |
| `VLine` at right edge labelled "Today"/"Now" | Right edge IS today |
| `PointLabel`/`Callout` describing slope ("rising"/"falling") | Geometry conveys. Title for directional claim |
| `Band` covering entire visible range labelled "Sample period" | Whole chart IS the sample |
| Round-number `HLine` without regime/target meaning (`HLine(y=100)` on price chart) | Fed 2%, PMI 50, recession 0% ARE regime lines and welcome |
| Multiple annotations crowding < 6 months of x-axis | Pick most important; demote rest to subtitle |

**Principle:** annotate regime changes, policy shifts, event dates, structural breaks, threshold crossings. Never decorate.

### 8.3 Annotation parameters

All inherit `label`, `label_color`, `color`, `axis` (where applicable). Use `style=` or `stroke_dash=` for dash patterns -- no `dash` / `line_style` exists.

| Annotation | Key params |
|---|---|
| `VLine` | `x`, `style` (`'solid'`/`'dashed'`/`'dotted'`), `stroke_dash`, `stroke_width`. Full y-axis; auto-staggers clustered labels. Default `"#666666"` |
| `HLine` | `y`, `axis` (`'left'`/`'right'`, default `'left'`; right only on dual), `style`, `stroke_dash`, `stroke_width`. Default `stroke_dash=[4,4]` |
| `Segment` | `x1`/`x2`, `y1`/`y2`, `style`, `stroke_dash`, `stroke_width`, `label_position` (`'start'`/`'middle'`/`'end'`), `label_offset_x`/`_y`. Finite line. `y1==y2` windowed avg; `x1==x2` finite event; diagonal connector |
| `Band` | `x1`/`x2` (vertical) OR `y1`/`y2` (horizontal), `opacity` (default `0.3`), `axis` (horizontal only) |
| `Arrow` | `x1`/`y1`, `x2`/`y2`, `stroke_width`, `stroke_dash`, `head_size`, `head_type` (`'triangle'`/`'none'`), `label_position` |
| `PointLabel` | `x`, `y`, `dx`/`dy` (pixel offsets), `font_size`, `align`. Use sparingly |
| `PointHighlight` | `x`, `y`, `size` (default `100`), `opacity`, `shape` (`'circle'`/`'square'`/`'diamond'`/`'triangle'`/`'cross'`/`'stroke'`), `filled`, `stroke_color`, `stroke_width`. Default `"#C00000"` |
| `Callout` | `x`, `y`, `background` (`'halo'`/`'box'`/`'none'`, default `'halo'`), `background_color`, `halo_width`, `box_padding_x`/`_y`, `box_opacity`, `box_corner_radius`, `dx`/`dy`, `font_size`, `font_weight`, `align`. `dx` 0-60; `abs(dx)>80` risks off-canvas |
| `LastValueLabel` | `dx`, `font_size` (default 16), `font_weight`. Auto-injected (§6.1); pass an explicit instance to customise; auto-derives names from color column. Text-only, no endpoint dot. Name cap (≤25 chars, `LvlSeriesNameTooLongError`) + dual-axis stripping: §6.1 |
| `Trendline` | `method` (`'linear'`/`'exp'`/`'log'`/`'pow'`/`'poly'`/`'quad'`), `stroke_width`, `stroke_dash`. Scatter only |
| `PlotText` | `text` (**≤8 words**, hard cap 10), `position` (`'auto'` / `'left'` / `'right'` / `'bottom'`; auto routes right → bottom → left), `font_size`, `italic`, `color`, `align`, `width_pct`. For longer prose pass `make_chart(caption=...)` / `side_left=...` / `side_right=...` (explicit wins). Inside-plot anchor values rejected (`ValidationError`) |

### 8.4 Compatibility & layers

Rule-style annotations (`HLine`, `VLine`, `Band`, `Callout`, `PointLabel`, `PointHighlight`) silently dropped on non-Cartesian charts (`donut`, `pie`) -- use `title`/`subtitle`. `LastValueLabel` only on `multi_line`/`area`; `Trendline` only on scatter. Bar compatibility: §6.2.

`annotations=[...]` for VLine/HLine/Band/Arrow; `layers=[...]` only for regression / threshold rule / secondary point cloud.

```python
layers = [
    {'type': 'regression', 'x': 'x_var', 'y': 'y_var', 'method': 'linear'},
    {'type': 'rule', 'y': 2.0, 'color': '#FF0000', 'stroke_dash': [4, 4]},
    {'type': 'point', 'x': 'x_var', 'y': 'y_var', 'data': highlight_df, 'size': 200},
]
```

---

## 9. Dual-axis charts

### 9.1 When to use + engine y-scale gate

Two series belong together at very different scales (equity vs ISM, 2s10s vs WTI, mortgage rates vs starts). Always declare with explicit long format -- `y: [list]` auto-melt is INCOMPATIBLE with `dual_axis_series`.

```python
df_long = df.melt(id_vars=['date'], var_name='series', value_name='value')
result = make_chart(df=df_long, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'series',
             'dual_axis_series': ['ISM Manufacturing'],
             'y_title': 'S&P 500', 'y_title_right': 'ISM Index'},
    title='Equities Track Manufacturing')
```

Two y-scale gates fire on multi-series single-y-axis `multi_line` / `timeseries`:

| Failure | Trigger | Error prefix | Example |
|---|---|---|---|
| **Flatness** | single series's data span < 10% of visible y | `Y-AXIS SCALE MISMATCH` | gold ($2000) + WTI ($70); equity + 2Y yield |
| **Level disparity** | every series varies, but gap between two means > 3x the largest individual span | `Y-AXIS LEVEL DISPARITY` | corp saving (~2.5%) vs investment (~9.9%) of GDP |

**Magnitude-driven splits auto-recover, fully engine-side** -- never pre-split a chart whose problem is *magnitude*. When a gate fires the engine routes to two axes, tags the legend `(LHS)`/`(RHS)`, and logs `AUTO-RECOVERED` on `result.audit_trail` (the chart is fine, §1); 3+ tiers split at the largest gap and add a `DUAL-AXIS WITHIN-AXIS COMPRESSION` warning naming any series that may still flatten. Override via `dual_axis_series=` / `dual_axis_bind=`, or switch to `make_2pack_*` / `facet` if each series's SHAPE matters more than co-movement. **Auto-recovery is standalone-only**: inside `make_*pack_*` cells the gates raise instead -- declare `dual_axis_series` on the `ChartSpec` when a cell pairs disparate magnitudes.

**Declare dual-axis intent yourself when units differ but magnitudes overlap** -- the gates key off magnitude, so they can't catch a `$T` series (10-40) plotted with a `%` series (20-38): same numbers, different units. That chart needs `dual_axis_series` / `dual_axis_bind` from you (the engine cannot infer units). Once declared, it auto-tags and warns on within-axis compression like the auto path.

| Reshape (when co-movement isn't the point) | Best when |
|---|---|
| **2-panel composite** (`make_2pack_horizontal` / `_vertical`) | Each panel its own y-axis. Canonical for 2 series; for 3+ split into panels where each panel's content shares a scale |
| **Normalize** -- z-score, rebase-to-100, pct-change every series | 3+ series; loses absolute level but preserves co-movement |
| **Small-multiples / facet** -- `mapping['facet']='<color_col>'` (drop `color`) | 3+ series with own y-axis per panel; argument is SHAPE of each component. See grids spoke |

### 9.2 Series-name discipline

`dual_axis_series` lists right-axis names exactly matching `color` values. For 3+ lines prefer `dual_axis_bind` (every series's axis explicit). Define LEFT/RIGHT constants to keep names in lockstep across DataFrame, binding, and axis titles.

```python
LEFT_SERIES, RIGHT_SERIES = '2s10s Curve (bp)', 'WTI Crude ($/bbl)'
curve_df['series'] = LEFT_SERIES
oil_df['series'] = RIGHT_SERIES
df_long = pd.concat([curve_df, oil_df], ignore_index=True)
mapping = {'x': 'date', 'y': 'value', 'color': 'series',
           'dual_axis_series': [RIGHT_SERIES],
           'y_title': '2s10s (bp)', 'y_title_right': 'WTI ($/bbl)'}

# 3+ lines: explicit per-series bind + auto LHS/RHS legend tags
mapping = {'x': 'date', 'y': 'value', 'color': 'series',
           'dual_axis_bind': {
               'Total Debt ($T)': 'left',
               'Public Held ($T)': 'left',
               'Intragov %': 'right',
           },
           'y_title': 'USD Trillions', 'y_title_right': '% of Total'}
```

Hygiene: rename DataFrame columns BEFORE melting; `.str.strip()` series columns from CSV (trailing whitespace silently disqualifies the right-axis row); re-check `df['series'].value_counts()` after any `dropna()`.

### 9.3 Inverted right axis

`invert_right_axis: True` flips the right axis (higher = bottom). Standard rates pattern: "up = bullish" on both axes (equities up + yields down = risk-on). No value negation needed.

```python
mapping = {'x': 'date', 'y': 'value', 'color': 'series',
           'dual_axis_series': ['UST 10Y'], 'invert_right_axis': True,
           'y_title': 'S&P 500', 'y_title_right': 'UST 10Y (%)'}
```

### 9.4 Annotations against the right axis

`HLine`, `Segment`, `PointHighlight`, `Callout`, `Arrow`, `Band` (horizontal), `PointLabel` accept `axis='right'` -- pass y-values in right-axis units. `VLine` is axis-agnostic. Out-of-domain values silently dropped. **`LastValueLabel` and `Trendline` are stripped on dual-axis** (non-fatal warning; end-of-line labels would collide with the right y-axis, so the colour legend renders). For end-of-line labels alongside two y-scales, build single-axis charts and combine via `make_2pack_vertical()`.

```python
annotations = [
    HLine(y=4.25, axis='left', label='Fed funds upper bound'),
    HLine(y=3.50, axis='right', label='Q1 ISM trough'),
    Segment(x1=T('2022-01'), x2=T('2022-12'), y1=50, y2=50, axis='right', label='ISM expansion'),
    PointHighlight(x=T('2023-06'), y=48.5, axis='right', size=120),
    Arrow(x1=T('2023-01'), y1=46, x2=T('2023-06'), y2=48.5, axis='right', label='ISM rebound'),
    Band(y1=48, y2=52, axis='right', label='Neutral zone', opacity=0.3),
]
```

### 9.5 When to switch off dual-axis

Per-series regime annotations → one `multi_line` per series in a composite. Magnitude / scale-problem reshapes (2-pack, z-score normalize, facet): §9.1.

### 9.6 Lead-lag pattern

"Does X anticipate Y?" -- ISM PMI leads equity returns ~6m, jobless claims lead unemployment ~3m, HY spreads lead defaults ~12m. Shift the predictor's date column forward by the lead horizon → its line extends past the predicted series's last actual; past co-movement implies near-term direction.

| Form | Question | Build |
|---|---|---|
| Time-shifted dual-axis | "What does X imply for Y over next N months?" | Shift predictor `+N` months → dual-axis + `VLine` at "Today" |
| Scatter `Y_t` vs `X_{t-N}` | "How tight is the lag-N relationship?" | `merged['x_lag'] = x.shift(N)` + `'scatter'` + `mapping['trendline']=True` |
| Combine | "Strength + path in one frame" | `make_2pack_horizontal(scatter_spec, time_shift_spec)` |

```python
predictor_shift = predictor.copy()
predictor_shift['date'] = predictor_shift['date'] + pd.DateOffset(months=6)
df_long = pd.concat([
    predicted.rename(columns={'spx_yoy_pct': 'value'}).assign(series='SPX YoY (%)'),
    predictor_shift.rename(columns={'ism': 'value'}).assign(series='ISM (lead 6m)'),
])
today, future_end = predicted['date'].max(), predictor_shift['date'].max()
make_chart(df=df_long, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'color': 'series',
             'dual_axis_series': ['ISM (lead 6m)'],
             'y_title': 'SPX YoY (%)', 'y_title_right': 'ISM (lead 6m)'},
    title='ISM Leads SPX by 6 Months',
    annotations=[VLine(x=today, label='Today', style='dashed'),
                 Band(x1=today, x2=future_end, label='Implied', opacity=0.18)])
```

`VLine` at "Today" canonical; `Band` over future zone optional. For an implied-target callout use `Arrow` / `PointHighlight` / `Callout` -- compute `implied_target` from predictor calibration before charting (engine does not derive it).

| Don't | Why |
|---|---|
| `strokeDash` on predicted series to switch solid→dashed on dual-axis | Silently dropped on dual-axis (§9.4); `VLine` + `Band` on LEFT axis cleaner |
| `layers=[{'type':'point', 'data': future_df, ...}]` for forecast dots on dual-axis | Custom-data points don't pin reliably; dots disappear. Use `Arrow` / `PointHighlight` / `Callout` |
| Stacked `make_2pack_vertical` of predictor + predicted | Loses visual co-movement that's the whole point |

---

## 10. Composite layouts

Composites > individuals for related data (shared x-axis, y-concept, comparison dimension). Individuals only for unrelated topics. **`make_*pack_*` helpers take 2-6 cells** (`make_2pack_*` through `make_6pack_grid`); **facet (grids spoke) is the floor at 7+ panels** — do not cram seven G7 lines onto one canvas or force an 8-panel ranking into a pack.

| Series count | Approach |
|---|---|
| ≤4 | Single `multi_line` (ideal) |
| 5-6 | Single panel still renders (hard cap 6) — prefer `make_2pack_horizontal()`, 2-3 lines each, for clarity |
| 7-8 | `make_4pack_grid()`, 2 lines each (single panel raises at 7+) |
| 9+ | Aggregate/group, or `heatmap` |

```python
spec = ChartSpec(df=df, chart_type='multi_line',
    mapping={'x': 'date', 'y': 'value', 'y_title': 'Yield (%)'},
    title='Title', subtitle='Subtitle',
    annotations=[...], layers=[...])
```

| Function | Layout | Args |
|---|---|---|
| `make_2pack_horizontal(c1, c2, ...)` | Side-by-side | 2 ChartSpecs |
| `make_2pack_vertical(top, bottom, ...)` | Stacked | 2 ChartSpecs |
| `make_3pack_triangle(top, bl, br, ...)` | 1 top + 2 bottom | 3 ChartSpecs |
| `make_4pack_grid(tl, tr, bl, br, ...)` | 2x2 | 4 ChartSpecs |
| `make_6pack_grid(...)` | 3x2 | 6 ChartSpecs (also `specs=[c1..c6]`) |

All accept `title`, `subtitle`, `caption`, `side_left`, `side_right`, `save_as`, `spacing`, `filename_prefix`, `filename_suffix`; return `CompositeResult` (`ChartResult` fields + `chart_errors`). `caption` / `side_*` flank the whole pack (like `make_chart`); per-sub-chart text panels go on each `ChartSpec`.

> **`build_charts` vs. composite-raise interaction.** `build_charts` (§2a) wraps WHOLE chart calls -- including a `make_*pack_*` composite call as a single thunk. When that thunk raises, the traceback is one composite-level `ValidationError` naming how many sub-charts failed, with each failing panel's complete finding list folded in. Build every `ChartSpec` from validated, non-empty data before composing; `build_charts` does not partial-render composites.

**Composite-global kwargs** (`skin`, `dimensions`, `dimension_preset`, `save_as`, `spacing`, …) go on the `make_*pack_*` call, **not** `ChartSpec` -- `ChartSpec(skin=...)` raises a typed `ValidationError` naming the bad kwarg and pointing at the pack helper (`make_chart(skin=...)` is valid).

**Rules:** ChartSpec args positional, metadata keyword-only (never `top=spec_a`). QC the composite PNG, not sub-specs. "Completely empty" QC fail usually means date still in index, y column all-NaN, or empty DataFrame. Color/x/y scales resolve independently per sub-chart. **Any sub-chart failure raises `ValidationError`** (message names how many failed) -- build every panel from valid, non-empty data. Per-cell label caps still apply in every pack cell -- cells are narrow, so aim even shorter than standalone (`LvlSeriesNameTooLongError`, §6.1; `HeatmapRowLabelTooLongError`, §6.3) -- shorten before `make_*pack_*()`.

**Per-cell colour-legend label budget** (when a sub-chart uses categorical `mapping['color']` and the legend renders): char cap = `floor(0.25 * cell_width_px / 7)`. Composite cells are narrow -- budget before `LegendLabelTooLongError`:

| Pack | Typical cell width | Approx char cap |
|---|---|---|
| `make_3pack_triangle` | ~320px | ~11 |
| `make_4pack_grid` (compact) | 280px | ~10 |
| `make_6pack_grid` (compact) | 260px | ~9 |

Standalone `make_chart` at 600px allows ~21 chars. Shorten colour-category names in the DataFrame before building the composite; aim ≤6 chars in 4-pack / 6-pack cells. (Scenario → layout: §3.1; level + decomposition stacks vertically.)

---

## 11. Chart time horizon

| Frequency | Default | Class | Use case |
|---|---|---|---|
| Quarterly / Monthly | 10 years | Medium | Cyclical patterns, regime comparisons -- default |
| Weekly | 5 years | -- | Trend + cycle (also YoY series) |
| Daily | 2-3 years | Short | Recent acceleration, event reactions |
| Intraday | 5 trading days | Very Short | Event reaction window, data releases |

Overrides: "highest since 2008" → MUST include 2008. Pre-pandemic → start ≥ 2015. Percentile claims need a full percentile window. Don't show 1-2y of monthly (hides cycle), 30+y of daily (noise), or different ranges for compared charts. Structural shifts ("not seen since X") → Long (20-50y) regardless of frequency.

---

## 12. Failure transparency

The retry budget is per *batch*, not per chart -- engine-enforced: `build_charts` (§2a) names every failed chart, each chart's error names every independent problem. One fix pass addresses all of them, then rebuild the whole batch.

Never silently substitute a layout. If a requested shape isn't feasible, tell the user and offer alternatives. Max 2 fix-passes per batch; after 2, deliver the best version with a note or ask about alternatives.

---

## 13. Static tables (`make_table()`)

`make_table()` + `TableResult` auto-injected (§1). Same brand palette + Liberation Sans font as `make_chart`. **Canvas engine-decided**: width fits data (text columns wrap), height grows to fit every row; PRISM never picks a dimension, nothing is truncated. **One hard limit:** a table too wide for a portrait 8.5x11 page **raises** `ValidationError` rather than shrinking to illegible micro-text -- reshape, don't widen (§13.10). When to reach for `make_table`: Tables vs Charts (top).

`df=` and `rows=` are mutually exclusive; engine errors if both:

| Source | Pass |
|---|---|
| Real data (Haver / market / CSV / scraper / computed positions) | `df=<DataFrame>` |
| Hardcoded / hand-curated values | `rows=[{...}, {...}]` (or `rows=[(...), ...]` + `columns=[...]`) |

### 13.1 Minimal calls

```python
# Data-pulled (df=)
result = make_table(df=df, title='Macro Snapshot', subtitle='G15 · Q1 2026',
    column_formats={'GDP YoY (%)': 'pct_signed', 'CPI YoY (%)': 'pct'},
    signed_columns=['GDP YoY (%)'],
    column_color_modes={'GDP YoY (%)': 'rwg', 'CPI YoY (%)': 'bw'},
    save_as='tables/macro_snapshot.png')

# Hardcoded -- list-of-dicts. Categorical RAG ('High'/'Medium'/'Low') via cell_colors;
# column_color_modes='rag' is for NUMERIC + rag_thresholds (§13.4).
RAG_HEX = {'High': '#1A8754', 'Medium': '#FFC107', 'Low': '#DC3545'}
themes = [{'Theme': 'Soft Landing', 'Owner': 'Macro', 'Conviction': 'High'},
          {'Theme': 'China Property', 'Owner': 'EM', 'Conviction': 'Medium'}]
result = make_table(rows=themes, title='Theme Tracker',
    cell_colors={(r, 'Conviction'): RAG_HEX[t['Conviction']]
                 for r, t in enumerate(themes)})

# Hardcoded -- list-of-tuples + explicit columns=
result = make_table(
    rows=[('USTs', 'Long 5Y', 'High', 'Macro'),
          ('DXY', 'Lower', 'Medium', 'FX')],
    columns=['Asset', 'View', 'Conviction', 'Owner'], title='Trade Ideas')
```

### 13.2 Full kwarg reference

| Kwarg | Type | Purpose |
|---|---|---|
| `df` | DataFrame | Data-pulled -- pass exactly one of `df` or `rows` |
| `rows` | list[dict] / list[tuple] | Hardcoded -- pass exactly one |
| `columns` | list[str] | Header names for `rows=`-as-tuples; reorders for dicts |
| `title` / `subtitle` | str | Top labels (left-aligned, FT/Bloomberg style) |
| `caption` | str | Italic note below table (auto-wraps) |
| `column_formats` | dict | `{col: hint}` -- §13.9 |
| `column_aligns` | dict | `{col: 'left'\|'center'\|'right'}` (default: numeric→right, text→left) |
| `header_levels` | list | Multi-level column headers -- §13.6 |
| `row_groups` | list | `[(label, n_rows), ...]` navy band sub-headers -- §13.6 |
| `row_indent` | list | Per-row indent (first column only) -- §13.6 |
| `row_bands` | bool | Default True; alt-row stripe |
| `row_colors` | dict | `{row_idx: hex}` per-row tint -- §13.7 |
| `column_color_modes` | dict | `{col: 'rwg'\|'bw'\|'rag'}` -- §13.4 |
| `heatmap_groups` | list | Multi-column shared scale -- §13.5 |
| `rag_thresholds` | dict | `{col: (red_max, amber_max)}` for `'rag'` -- §13.4 |
| `highlight_columns` | list | Tint full column light blue |
| `cell_colors` | dict | `{(row, col): hex}` per-cell bg -- wins over everything. `col` name (preferred) or int |
| `cell_text_colors` | dict | `{(row, col): hex}` per-cell text override |
| `sparkline_columns` | dict | `{col: [list_per_row]}` -- §13.8 |
| `minibar_columns` | dict | `{display_col: source_col}` -- §13.8 |
| `signed_columns` | list | Auto green-positive / red-negative TEXT colour |
| `total_rows` | list | Row indices → inverted navy + bold |
| `subtotal_rows` | list | Row indices → bold + subtle band |
| `show_index` | bool | Include DataFrame index as leftmost column |

### 13.3 `TableResult` (dataclass -- dot notation only; failures raise)

| Attribute | Description |
|---|---|
| `success` / `error_message` | `True` on returned results; failures raise (§1 failure contract) |
| `png_path` / `download_url` | PNG S3 path / presigned URL |
| `warnings` | non-fatal annotations (e.g. dropped `cell_colors` keys with unknown columns) |
| `n_rows` / `n_cols` | shape after `show_index` adjustment |
| `truncated_rows` | always 0 -- `make_table` never truncates |
| `canvas_size` | (width, height) emitted |

### 13.4 Color modes -- three strings, no degrees of freedom

| Mode | Use case | Palette |
|---|---|---|
| `'rwg'` | Diverging at zero -- signed columns where positive = good (P&L, returns, surprises) | red(neg) ↔ white(0) ↔ green(pos) |
| `'bw'` | Sequential -- values ≥ 0 where higher = "more" (CPI %, vol, AUM, market cap) | white → navy |
| `'rag'` | Discrete bucketing by author thresholds | red / amber / green |

```python
column_color_modes={'GDP YoY (%)': 'rwg', 'CPI YoY (%)': 'bw',
                    'Unemp (%)': 'rag', 'Inflation': 'rag'}
rag_thresholds={'Unemp (%)':  (4.0, 6.0),                              # lower-is-bad
                'Inflation':  {'amber_above': 2.0, 'red_above': 4.0}}  # higher-is-bad
```

| Threshold shape | Direction | Boundaries |
|---|---|---|
| `(red_max, amber_max)` (legacy 2-tuple) | lower-is-bad | `< red_max` red, `< amber_max` amber, else green |
| `{'red_below': X, 'amber_below': Y}` | lower-is-bad (explicit) | same with named keys |
| `{'amber_above': X, 'red_above': Y}` | higher-is-bad (inflation, unemp, default rate) | `> red_above` red, `> amber_above` amber, else green |

### 13.5 Heatmap groups (multi-column shared scales)

When columns belong to the same metric and should share one heatmap scale (yield curve across countries, correlation matrix, all-numeric snapshot block):

```python
heatmap_groups=[
    {'columns': ['US', 'UK', 'EU', 'JPN'], 'scope': 'row', 'mode': 'sequential'},
    {'columns': ['Corr A', 'Corr B', 'Corr C'], 'scope': 'group', 'mode': 'diverging'},
]
```

`columns` = column names. `mode` = `'sequential'` (→ bw palette) or `'diverging'` (→ rwg palette). `palette` optional override (almost always omit). `scope`:

| Scope | Effect | Use case |
|---|---|---|
| `'column'` (default) | Each column scaled to its own min/max | within-column ranking ("where does this tenor sit?") |
| `'row'` | Each row scaled across the group's columns | cross-entity at a fixed tenor -- yield-curve cross-country |
| `'group'` | Single shared scale across every cell | absolute level across all cells -- correlation matrix |

`heatmap_groups` wins over `column_color_modes` for any covered column.

### 13.6 Headers, rows, hierarchy

```python
# Multi-level headers -- spans sum to len(df.columns) per level
header_levels=[[('', 1), ('Yields (%)', 4), ('Changes (bp)', 2)]]   # 3+ levels degrade

# Navy band between row blocks -- counts sum to len(df)
row_groups=[('Americas', 3), ('EMEA', 4), ('Asia-Pac', 5)]

# Per-row indent (first column only); 2 levels read, 3+ degrade
row_indent=[1, 1, 0, 1, 1, 0, 0, 0, 0]   # 0 = flush, 1 = one step (16 px)

# Auto-styled totals/subtotals -- author the row INTO the DataFrame
total_rows=[8]          # → inverted navy + bold + white text
subtotal_rows=[2, 5]    # → bold + subtle band
```

### 13.7 Per-row / per-cell control

| Kwarg | Purpose |
|---|---|
| `row_colors={r: hex}` | Per-row tint. Loses to `heatmap_groups` / `column_color_modes` / `cell_colors` / `total_rows` / `subtotal_rows`; wins over `row_bands` |
| `cell_colors={(r, c): hex}` | Per-cell bg. Wins over EVERYTHING. `c` is column name (preferred) or int |
| `cell_text_colors={(r, c): hex}` | Per-cell text -- same key shape as `cell_colors` |
| `highlight_columns=[col, ...]` | Light-blue tint on entire column |
| `signed_columns=[col, ...]` | Auto green text positive, red negative (text only -- independent of cell bg) |
| `row_bands=True` (default) | Subtle alt-row stripe |

**Color resolution priority (top wins per cell):** `cell_colors` → `total_rows` → `subtotal_rows` → `heatmap_groups` → `column_color_modes` → `row_colors` → `highlight_columns` → `row_groups` (band rows) → `row_bands`.

### 13.8 Special cells

```python
# Sparkline -- DataFrame cell value ignored; one list per row → tiny navy line + endpoint dot
sparkline_columns={'Trend (60d)': [
    [101.2, 102.4, 99.8, ..., 110.5],   # row 0; lengths can differ per row
    [98.0,  97.6, 100.2, ..., 102.1],   # row 1; each row's min/max scales independently
]}

# Mini-bar (Bloomberg-style) -- display column = horizontal bar scaled to source's max across rows.
# Negative values right-aligned in red. Source CAN be display column itself (both number + bar in same cell).
minibar_columns={'MktBar': 'Mkt Cap ($B)'}
```

### 13.9 Number formatting hints

`column_formats` as `{col: hint}`:

| Hint | Format | Example |
|---|---|---|
| `'pct'` / `'pct_signed'` | `12.3%` / `+1.5%` | 1dp |
| `'pct2'` / `'pct2_signed'` | `12.34%` / `+1.50%` | 2dp |
| `'bp'` / `'bp_signed'` | `42bp` / `+42bp` | basis points |
| `'currency'` | `$1.23B` / `$45.67M` / `$1,234.56` | magnitude-aware |
| `'ratio'` | `2.45x` | multiples |
| `'int'` | `12,345` | thousands-separated integer |
| (none) | magnitude-aware default | `,.1f` / `.2f` / `.3f` by abs value |

### 13.10 Authoring rules

- **One long free-text column mixed with numeric columns is the most common width trip.** A single narrative column (thesis, note, description) beside many numeric metrics blows the legibility gate. Move the long-text column OUT of the grid: route it to `caption=`, wrap it into a row-group label, or drop it to a footnote.
- **Author totals into the DataFrame.** `total_rows=[8]` styles existing row at index 8 -- engine doesn't compute.
- **Header label spans sum to `len(df.columns)`.** Engine rejects with offending `level_idx` and total.
- **Row group counts sum to `len(df)`.** Same.
- **Color modes are 3 only.** Pick by semantic, not aesthetic. Diverging-at-zero ≠ ramp-from-zero.
- **`signed_columns` colours TEXT, not the cell.** Combine with `column_color_modes={col: 'rwg'}` for both.
- **Sparkline series can differ in length per row.** Each row's min/max scales independently.
- **Wide text columns wrap automatically.** PRISM doesn't opt in.
- **Width has a hard legibility limit -- reshape, don't widen.** A table whose body text would print below ~6pt across a portrait 8.5x11 page is rejected. Column COUNT isn't the trigger -- numeric columns can't compress and headers set a non-compressible floor, so a few long-header numeric columns fail where a dozen narrow ones pass. When the natural shape is too wide (metric × 24-month grid, 40-column matrix), build it narrow via ONE of: (1) **transpose**; (2) **split** by column group; (3) **aggregate** (latest + 3m + 12m change, or top-N rows); (4) **shorten headers**.

### 13.11 Anti-patterns

| Anti-pattern | Why |
|---|---|
| Markdown table / `print(df)` / `df.to_string()` / aligned text-block when the user hasn't asked for one | Default is PNG via `make_table()` (top-of-hub); switch only on explicit user preference |
| Colour mode beyond `'rwg'` / `'bw'` / `'rag'` | PRISM-facing surface is exactly those three |
| `make_table(df=df, color_mode='rwg')` -- top-level | Engine `TypeError`. Modes per-column: `column_color_modes={'col': 'rwg'}` |
| `column_color_modes={'col': {'amber_above': 5, 'red_above': 7}}` -- packing thresholds into mode value | `ValidationError`. Thresholds in `rag_thresholds={'col': {...}}`; mode value stays `'rag'` |
| `heatmap_groups={'sequential': ['col1']}` -- dict-keyed-by-mode | `ValidationError`. Canonical: list-of-dicts (§13.5) |
| `header_levels=[[{'label': 'Yields', 'span': 4}]]` -- list-of-dicts | Dicts accepted only when both `label` + `span` present; canonical is `[(label, span), ...]` |
| Computing totals in Python, passing as last row without `total_rows=[N]` | Loses inverted-navy footer that signals "this is the answer" |
| `row_indent=[0, 1, 2, 3, ...]` (deep multi-level) | 2 indent levels read; 3+ degrades. Refactor to row groups |
| Heatmap on a column where higher-is-just-different (Country code, Ticker, Sector) | Colour encodes magnitude or sign -- not nominal identity |
| Mixing `cell_colors` with `column_color_modes` on same cell | `cell_colors` always wins -- reserve for one-off highlights, not bulk |
| Emitting a very wide table (every month of a multi-year series, a 30+ column matrix) | Rejected as illegible on 8.5x11 -- transpose / split / aggregate / shorten headers (§13.10) |

### 13.12 Common shapes (worked examples)

`df=` for data-pulled, `rows=` for hardcoded.

| Shape | Source | Pattern |
|---|---|---|
| **Macro snapshot** | `df=` | `row_groups=[(region, n)]` + `column_color_modes={'GDP YoY': 'rwg', 'CPI': 'bw'}` + `rag_thresholds={'Unemp': {'amber_above': 5, 'red_above': 7}}` for any `'rag'` column |
| **Sovereign curve cross-country** | `df=` | `header_levels=[[('', 1), ('Yields (%)', N), ('Δ (bp)', M)]]` + `heatmap_groups=[{'columns': [yield_cols], 'scope': 'row', 'mode': 'sequential'}]` + `signed_columns=[Δ_cols]` |
| **P&L attribution** | `df=` | `row_indent=[...]` + `subtotal_rows=[...]` + `total_rows=[N-1]` + `column_color_modes={'PnL': 'rwg'}` |
| **Watchlist** | `df=` | `sparkline_columns={'Trend': [...]}` + `minibar_columns={'MktCap (bar)': 'Mkt Cap ($B)'}` + `column_color_modes={'YTD %': 'rwg'}` + `signed_columns=[period_pct_cols]` |
| **Correlation matrix** | `df=` | `heatmap_groups=[{'columns': [all numeric], 'scope': 'group', 'mode': 'diverging'}]` |
| **Econ calendar** | `rows=` | `cell_colors={(r, importance_col): RAG_hex}` + `column_aligns={'Importance': 'center'}` |
| **Theme tracker (categorical RAG)** | `rows=` | `cell_colors={(r, 'Conviction'): RAG_HEX[v]}` for string buckets ('High'/'Medium'/'Low'). Long `'Note'` columns wrap auto. `column_color_modes={'col': 'rag'}` only on NUMERIC columns + `rag_thresholds` |
| **Trade ideas / curated watchlist** | `rows=` | `rows=[(asset, view, conviction, owner)]` + `columns=[...]` |

### 13.13 Failure transparency

`make_table` **raises** `ValidationError` on failure and the message names the offending kwarg + the fix; the corrective shapes are the §13.11 anti-patterns and §13.10 rules (span/count sums, mode-vs-threshold split, list-of-dicts `heatmap_groups`, reshape-when-too-wide, exactly one of `df=`/`rows=`). `result.warnings` carries non-fatal annotations -- e.g. `column_color_modes[col]='rag' set but no rag_thresholds[col] provided -- cells render uncoloured.` Surface them.
