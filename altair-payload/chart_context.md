# Altair Charts & Tables (`make_chart`, `make_table`)

- **Module:** `chart_context`
- **Audience:** PRISM (all interfaces, all workflows), developers
- **Tier:** 2 (on-demand)
- **Scope:** All static-PNG chart + table authoring (chat / email / report). Composites here. Interactive HTML dashboards: `dashboards` (echarts).

`make_chart()`, `make_table()`, composite / annotation / profile helpers auto-injected. Raw matplotlib blocked. Do NOT import. `s3_manager` / `session_path` / `user_id` auto-inject at call time -- never pass them.

> **Tables default to PNG via `make_table()`** -- structured-data answers ship as static PNGs across all interfaces (chat / email / report / any artifact). Switch to markdown (`|...|...|` pipes, `print(df)` / `df.to_string()`, aligned text-blocks) only when the user asks for one or expresses a preference. Full surface: §13 (no spoke fetch).

---

## Catalog index

| Primitive | Names | Where |
|---|---|---|
| Chart types (11) | `multi_line`, `scatter`, `scatter_multi`, `bar`, `bar_horizontal`, `heatmap`, `histogram`, `boxplot`, `area`, `donut`, `waterfall` | §6 |
| Mapping keys | `x`, `y`, `color`, `value`, `theta`, `y_title`, `y_title_right`, `x_title`, `x_sort`, `y_sort`, `x_type`, `dual_axis_series`, `invert_right_axis`, `dual_axis_config`, `legend`, `trendline`, `trendlines`, `stack`, `strokeDash`, `strokeDashScale`, `strokeDashLegend`, `bins`, `maxbins`, `bin_extent`, `extent`, `scale_type`, `orientation`, `color_sort` (alias `legend_sort`), `value_sort`, `type`, `facet_order` | §7 |
| Annotation classes (11) | `VLine`, `HLine`, `Segment`, `Band`, `Arrow`, `PointLabel`, `PointHighlight`, `Callout`, `LastValueLabel`, `Trendline`, `PlotText` | §8 |
| Composite functions (5) | `make_2pack_horizontal`, `make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid` | §10 |
| Grid mode | `mapping['facet']`, `facet_cols`, `same_scale`, `share_x` / `share_y` / `share_color` | spoke `chart_context_grids.md` |
| Chart colour / opacity | `mapping['color_scheme']`, `color_map`, `opacity`, `opacity_map` | spoke `chart_context_colors.md` -- **MUST fetch** |
| Static tables | `make_table` + `TableResult`; `df=` or `rows=`; 3 color modes (`'rwg'` / `'bw'` / `'rag'`); `heatmap_groups` (col/row/group scope); `header_levels`; `row_groups`; `row_indent`; `total_rows` / `subtotal_rows`; `sparkline_columns`; `minibar_columns`; `signed_columns` | §13 |
| Skin | `gs_clean` | §1 |
| Intent | `'explore'`, `'publish'`, `'monitor'` | §1 |
| Layer types | `regression`, `rule`, `point` | §8.5 |

---

## Spokes (mid-session fetch)

Mid-session reads use `list_ai_repo` with `mode="full"` -- pass ONLY `file_paths` and `mode`. `get_context()` is one-shot per user message.

| Spoke | Trigger | Tool call |
|---|---|---|
| `chart_context_grids.md` | 8-30 entities sharing one shape (G20 GDP, sector PMIs, FX cross-rates, country curves); scatter phase-space with temporal/numeric `color` | `list_ai_repo(file_paths=["context/modules/static/chart_context_grids.md"], mode="full")` |
| `chart_context_colors.md` | **MANDATORY** before any chart palette / per-series colour / hex / emphasis / fade / highlight / opacity ask on `make_chart` -- including trivial ones ("US red", "slot 2 fainter") | `list_ai_repo(file_paths=["context/modules/static/chart_context_colors.md"], mode="full")` |

Skip both for "make me a chart" with no colour / opacity / facet language -- defaults are on-brand. `make_table()` colour (`column_color_modes`, `cell_colors`, `heatmap_groups`) is **§13, NOT the colours spoke.**

---

## Tables vs Charts

| Question shape | Reach for |
|---|---|
| Time series, distribution, scatter, ranking, regime, co-movement, lead-lag | `make_chart` (§1-12) |
| 8-30 entities sharing one shape | `make_chart` grid mode (grids spoke) |
| Structured rows × columns where a chart can't visualise cleanly: watchlists, term structures, P&L attribution, factor tilts, sector tapes, calendars, snapshot dashboards, theme trackers, trade-idea lists | `make_table` (§13) |
| Single KPI tile | echarts dashboards (not altair) |

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

Canvas size engine-decided per `chart_type`. `interactive=True` (default) auto-emits an interactive HTML companion alongside the PNG.

**Auto-injected names:** `make_chart`, `make_table`, `profile_df` (§5), `ChartResult` / `ChartSpec` / `TableResult` / `CompositeResult`, `check_charts_quality` (§2), all composites (§10), all 11 annotation classes (§8).

**`ChartResult` is a dataclass -- dot notation only; `result['png_path']` raises `TypeError`.**

| Attribute | Description |
|---|---|
| `png_path` / `download_url` | PNG S3 path / presigned URL |
| `editor_html_path` / `editor_download_url` / `editor_chart_id` | Interactive HTML companion -- surface alongside PNG |
| `vegalite_json` | Final Vega-Lite spec |
| `chart_type` / `skin` | Echoed |
| `success` / `error_message` | `success` is `True` on any returned result; failures **raise** instead (see Failure contract) |
| `warnings` | Fail-soft annotations (auto-melt, dropped annotations) -- caller may surface |
| `audit_trail` | Informational engine decisions (auto-recovered dual-axis, downsampling) -- chart is fine; do NOT surface as failures |

`CompositeResult` (from `make_Npack_*`) adds `layout`, `n_charts`, `chart_errors` (per-sub-chart `df_shape` / `error_type` / `error_message`); editor fields same as single charts.

**Failure contract.** `make_chart`, `make_table`, and the `make_*pack_*` composites **raise** `ValidationError` on failure -- the error bubbles out of your script and PRISM surfaces it to the user. Do **not** wrap these calls in `try/except` to swallow it. A *returned* result therefore always has `success=True`; no `if not r.success` guard is needed. **Composites raise if *any* sub-chart fails** -- one empty / broken panel raises the whole `make_*pack_*` call (it does not return a partial render). Build every panel from validated, non-empty data before composing.

---

## 2. Quality gate (MANDATORY)

Every chart through `check_charts_quality()`. Fail-open if Gemini unavailable. Pass composites as single PNGs. On QC fail: `s3_manager.delete()` the PNG; fix or remove the call. (Build failures already raised upstream, so every `r` here has rendered.)

```python
qc_results = check_charts_quality([r1, r2])
for r, qc in zip([r1, r2], qc_results):
    if not qc['passed']:
        s3_manager.delete(r.png_path)
```

"Could not generate" is acceptable; showing a failed chart is not.

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
| 7-30 entities sharing one shape | grid mode (`mapping['facet']`) | Mag-7 / sectors / G20 / FX -- fetch grids spoke |
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
| Lead-lag | Does X anticipate Y? | Scatter form: `merged['x_lag'] = x.shift(N)` + `'scatter'` + `mapping['trendline']=True`. Time-shift form: shift predictor `+N` months → dual-axis + `VLine` "Today" (§9.6) |

**Anti-pattern:** single-series `multi_line` on "is anything happening?" -- narrates, doesn't argue.

Engine rejects scatters with < 10 distinct (x, y) coords in visible region (reads as anecdote; error directs you to find a different representation — bar, multi_line, table, or a wider data window). For correlation with disparate magnitudes (gold + WTI) or disparate levels (FCI components 30/60/10), single-y-axis `multi_line` is REJECTED -- pick 2-pack or dual-axis (§9.1).

---

## 4. Authoring rules

- **Max 4 lines per `multi_line` / `area` -- engine-enforced (raises).** 5+ overplot and end-of-line labels collide; the engine rejects with a message routing to a breakup. For >4, don't crowd one panel -- split into a composite (§10), small-multiples facet (grids spoke), or normalize/aggregate to the most important ≤4. Counted per panel, so composite cells must each stay ≤4.
- **`y_title` plain English; aim ≤16 chars (hard cap 24).** Same cap on `x_title` / `y_title_right`. Series names on `multi_line` / `timeseries` capped 25 (§6.1) -- rename in DataFrame before melting.
- **X column must be `'date'` for time series, as a column.** `df.rename(columns={'datetime': 'date'}).reset_index()`.
- **Multi-line long format: rename FIRST, then melt** -- or use auto-melt (no `color` key, pass `y=[list]`).
- **No source attribution in title/subtitle.** Title argues; sources in PRISM metadata. Good: `title='Inflation Has Peaked'`, `subtitle='Core CPI decelerating 6 months'`. Bad: `title='US CPI Data'`, `subtitle='Source: Haver'`.
- **Clean before charting.** `pd.to_numeric(errors='coerce')` + `dropna(subset=['date', 'value'])`. Max 12 color cats, 16 facet cats. >5,000 rows auto-downsample to ~2,000 (warning).
- **Never plot `np.zeros()` placeholder.** Skip the panel or add text annotation.
- **Title/subtitle: 2-line cap, auto-wrap.** Engine reports exact char limit on rejection; explicit `\n` honored (counts toward cap). Wrapped titles grow the header band vertically only — font-size-aware pre-wrap keeps lines inside the plot width (never Vega-Lite ``title.limit``, which ellipsis-truncates).
- **Never truncate axis / legend / LVL labels.** Vega-Lite ``labelLimit`` ellipsis is forbidden -- overlong nominal labels raise typed errors (`BarCategoryLabelTooLongError`, `HeatmapRowLabelTooLongError`, `LegendLabelTooLongError`, `LvlSeriesNameTooLongError`). Shorten strings in the DataFrame; the engine will not silently clip.

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

**Intraday x-axis (minute / hour bars).** Pass ``datetime64[ns]`` (or strings / epoch / tz-aware -- the engine normalizes). **Default clock: US/Eastern (ET).** X labels: **multi-day** → date at midnight only (``May 28``), otherwise ``HH:MM``; **single-session** (one calendar day) → date on the leftmost tick only (``May 27``), otherwise ``HH:MM``. Override display clock with ``mapping['x_timezone']``. Do NOT pre-format to strings or set ``x_type='ordinal'``.

**Phase orbit (`scatter` + `connect`).** Goodwin-style phase portraits: plot (x, y) with `mapping['connect']=True` to draw a time-ordered path instead of isolated dots. Requires `mapping['order']` or a temporal/numeric `mapping['color']` for sequence. Set ramp endpoints with `mapping['color_range']=['#start', '#end']` (early→late, HSV rainbow through the longer hue arc), or use `color_scheme='turbo'` etc. — see `chart_context_colors.md` §6. Incompatible with `trendline=True`.

**Baseline fill gauge (`multi_line` + `zero_fill`).** Single-series line with shaded band above/below a horizontal baseline — squeeze gauge at 0, ISM diffusion at 50, etc. Set `mapping['zero_fill']=True` and `mapping['zero_fill_baseline']=50` (default `0`). Optional `zero_fill_positive` / `zero_fill_negative` hex overrides. Single-series only; incompatible with `color`, dual-axis, `strokeDash`, log scale.

**End-of-line labels (LVL), not colour legend, on `multi_line` / `timeseries`.** Series name paints at line's right end in own colour (FT/Bloomberg). Auto-injected on every single panel **and every pack-composite cell** (`make_2pack_*`, `make_3pack_*`, `make_4pack_grid`, `make_6pack_grid`). **Series names ≤25 chars** -- longer raises `LvlSeriesNameTooLongError`; rename in DataFrame (`'United States Equities Index 500'` → `'S&P 500'`). Customise via explicit `LastValueLabel(dx=..., font_size=..., font_weight=...)` -- your annotation wins. **Dual-axis (`dual_axis_series`): no LVL** -- end-of-line text collides with the right y-axis; colour legend renders instead (§9.4). Facet grids (`mapping['facet']`) strip LVL -- see grids spoke.

**Colour-legend series names** apply only when the legend is visible (dual-axis, or explicit `mapping['legend']=True`): must fit the cell-width budget or the engine raises `LegendLabelTooLongError`. Pack composites with LVL do not show a colour legend.

**Seasonal-jaggedness gate (`multi_line` / `timeseries` / `line` / `area`).** A weekly / monthly / quarterly series with a strong, regular every-period swing (e.g. raw quarterly revenue with a holiday-quarter spike) is REJECTED with `SEASONAL JAGGEDNESS` — it renders as an unreadable sawtooth. Checked per series, including single-panel composite cells. Fix: seasonally adjust, plot YoY % change, or take a trailing rolling mean / rolling sum over one full period (e.g. a 4-quarter rolling sum for quarterly revenue) before charting.

**Stacked-area alignment gate (`area` + `color`).** When series report on different calendars so the layers don't share x-values, the stack shatters into white triangular gaps and the engine REJECTS with `SERIES MISALIGNMENT`. Fix: resample every series onto a common period grid (e.g. quarter-end, forward-filled to the last reported value) before stacking.

### 6.2 Bar family

**Bars are categorical-only.** `bar` / `bar_horizontal` require a categorical (string / ordinal) `x` -- NEVER a datetime / temporal axis. There is no bar-chart time series: continuous time series route to `multi_line` / `area` (additive decomposition → `waterfall`), including signed flow / issuance / surprise / net-position tapes that might otherwise read as thin bars over time. Discrete periods (quarters, months) belong on bars ONLY as string labels (`"Q1 2025"`, `"Jan"`), which makes them categorical -- never pass the raw datetime.

`stack=True` (default with color) for parts-of-whole; `stack=False` for grouped side-by-side. Don't sign-key colour (`'Positive'`/`'Negative'`) -- bar position vs zero conveys sign.

```python
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product'}                  # stacked
mapping = {'x': 'Region', 'y': 'Revenue', 'color': 'Product', 'stack': False}  # grouped
```

**Category labels ≤15 chars** on every bar chart (`bar`, `bar_horizontal`, grouped, stacked, single, composite -- same cap regardless of orientation or context). Longer raises `BarCategoryLabelTooLongError`; shorten in the DataFrame (`'Information Technology'` → `'Info Tech'` / `'IT'`, `'Manufacturing PMI Composite'` → `'Mfg PMI'`). The engine names the offending labels and suggests abbreviations in the error message.

Grouped clamps facet width to cell budget; below ~3px per bar (~60+ cats compact, ~200+ standalone) engine raises `GROUPED BAR CELL-BUDGET ERROR` -- switch to `stack=True`, reduce categories, or render standalone. `bar_horizontal` same on height.

| Bar mode | Annotation support |
|---|---|
| Single-series | `HLine`, `VLine`, `Band`, `Arrow`, `PointLabel` |
| Stacked | `HLine` clamped against stacked totals |
| `bar_horizontal` | `HLine` → vertical threshold |
| Grouped (`stack=False`) | Annotations DO NOT render -- use title/subtitle or `stack=True` |

### 6.3 Heatmap

**Data shape:** pass long (`x`/`y`/`value` columns), wide (an id column + one value column per category, e.g. `[ticker, 2016…2023]` or `[date, AAPL, MSFT…]`), or a matrix indexed by the row category — the engine auto-reshapes to long; never melt/pivot by hand. Always name `x`, `y`, `value` as the *intended* fields; for wide/matrix input the field name not present as a column labels the melted axis (or values), and `value` may be omitted (defaults to `value`). Ambiguous shapes (≥2 id-like / non-numeric columns, or a matrix with a default RangeIndex) raise a `ValidationError` naming the exact reshape.

```python
mapping = {'x': 'year', 'y': 'ticker', 'value': 'op_margin'}   # wide df=[ticker, 2016…2023] (y is the id col)
mapping = {'x': 'date', 'y': 'ticker', 'value': 'ret'}         # wide df=[date, AAPL, MSFT…]  (x is the id col)
mapping = {'x': 'factor', 'y': 'factor', 'value': 'corr'}      # matrix: index + cols = factors (correlation)
```

`value` column renders as cell colour. Two recipes by dtype:

| `value` dtype | Color scale | Cap |
|---|---|---|
| numeric | quantitative; sequential, OR diverging-at-zero when min<0<max | warned >500 cells |
| categorical / string | nominal sequential ramp indexed by sort order; cell label is the bin | ≤12 distinct bins (rejected above) |

For categorical recipe (continuous binned to labels), bin via `pd.cut()` / `np.digitize()`. Override sort via `mapping['value_sort']=[...]`.

**Column labels (x-axis):** engine picks horizontal or -45° and thins tick labels when the x grid is dense (intraday heatmaps use ~half the tick frequency of profile-line charts). Do not pass `labelAngle` / tick counts — shorten category strings or reduce x cardinality in the DataFrame if labels still crowd.

**Temporal x columns (epoch ms, datetime64, ``2024-Q1`` strings, pandas Period):** the engine auto-materialises readable period labels (``Q2 25``, ``2024``, ``Oct 24``) before the nominal encode — pass raw timestamps or quarter tokens; do not pre-format to strings and do not set ``x_type='ordinal'`` to block coercion. True categoricals (region codes, probability buckets, ``T000`` session tags) are left untouched. Mixed temporal + categorical x raises ``ValidationError``.

**Row labels (y-axis):** always horizontal (`labelAngle=0`); never rotated to -45; never ellipsis-truncated. Hard cap **15 chars** (same discipline as bar category labels). Row labels are validated on every heatmap -- overlong values raise `HeatmapRowLabelTooLongError`; shorten in the DataFrame.

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

Haver stores many monthly/quarterly at business-daily granularity (same value ~22 days). Symptom: stair-step lines. Resample to native frequency BEFORE charting. Merging mixed-frequency creates NaN gaps -- resample to lowest common frequency before `concat` / `merge`.

| Series type | Resample | Example |
|---|---|---|
| Point-in-time / stock | `.last()` | Housing starts, unemployment rate |
| Flow / cumulative | `.mean()` or `.sum()` | Initial claims (mean), retail sales (sum) |
| Rate / percentage | `.last()` or `.mean()` | CPI YoY, mortgage rate |

---

## 7. Mapping reference

### 7.1 Axis-title kwargs

`x_title` / `y_title` / `y_title_right` accepted both INSIDE `mapping={}` and as TOP-LEVEL kwargs on `make_chart()` / `ChartSpec(...)`. Engine routes top-level into `mapping`; `mapping[...]` wins on conflict. `x_label` / `y_label` are legacy aliases for the top-level form. Composite-level `title=` / `subtitle=` describe the COMPOSITE; per-panel axis titles set on each `ChartSpec`.

### 7.2 Basic patterns

```python
mapping = {'x': 'date', 'y': 'value', 'y_title': 'GDP Growth (%)'}                      # basic
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}                                # multi-series (long)
mapping = {'x': 'date', 'y': ['col_a', 'col_b']}                                        # auto-melt (wide)
mapping = {'x': 'tenor', 'y': 'yield_pct', 'color': 'curve_date'}                       # profile/curve
mapping = {'x': 'x_var', 'y': 'y_var', 'color': 'group', 'trendlines': True}            # scatter + trendlines
mapping = {'x': 'util', 'y': 'labor_share', 'color': 'date', 'connect': True,
           'color_range': ['#DC143C', '#003359']}                                     # red → navy orbit
mapping = {'x': 'date', 'y': 'ulc_yoy', 'zero_fill': True}                              # squeeze gauge @ 0
mapping = {'x': 'date', 'y': 'ism_mfg', 'zero_fill': True, 'zero_fill_baseline': 50}    # ISM vs 50
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
| `dual_axis_series` / `invert_right_axis` | list / bool | Right-axis series / flip (higher = bottom) |
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
| Any annotation outside visible plot domain (`Band` edge above data; `Segment`/`Arrow` endpoint off-data; `PointLabel`/`PointHighlight`/`Callout` off-data coord) | Shared scale expands to include the coord, stretching frame. Engine drops silently. Keep coords inside data; for narrative thresholds outside use title/subtitle. For "highlight above X": `Band(y1=X, y2=df['value'].max())`. `HLine` drops if y outside but doesn't stretch |
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
| `LastValueLabel` | `dx`, `font_size` (default 16), `font_weight`. **Auto-injected** on every `multi_line` / `timeseries` single panel + pack-composite cell (§6.1); pass explicit instance to customise. Auto-derives names from color column. **Series names > 25 chars raise `LvlSeriesNameTooLongError`** -- rename in DataFrame. **Stripped on dual-axis** (collides with right y-axis). Text-only, no endpoint dot |
| `Trendline` | `method` (`'linear'`/`'exp'`/`'log'`/`'pow'`/`'poly'`/`'quad'`), `stroke_width`, `stroke_dash`. Scatter only |
| `PlotText` | `text` (**≤8 words**, hard cap 10), `position` (`'auto'` / `'left'` / `'right'` / `'bottom'`; auto routes right → bottom → left), `font_size`, `italic`, `color`, `align`, `width_pct`. For longer prose pass `make_chart(caption=...)` / `side_left=...` / `side_right=...` directly. Explicit `caption=` / `side_*=` wins. Inside-plot anchor values removed 2026-05-10 -- now `ValidationError` |

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

Engine REJECTS multi-series single-y-axis `multi_line` / `timeseries` when either fires:

| Failure | Trigger | Error prefix | Example |
|---|---|---|---|
| **Flatness** | single series's data span < 10% of visible y | `Y-AXIS SCALE MISMATCH` | gold ($2000) + WTI ($70); equity + 2Y yield |
| **Level disparity** | every series varies, but gap between two means > 3x the largest individual span | `Y-AXIS LEVEL DISPARITY` | corp saving (~2.5%) vs investment (~9.9%) of GDP |

**2-magnitude-cluster cases auto-recover** -- when the series split cleanly into two magnitude groups (the 2-series case, or e.g. two $-level series + one %-level series), the engine routes the smaller-magnitude group to the right axis, re-renders, and emits `AUTO-RECOVERED:` on `result.audit_trail` (NOT `warnings`; chart is fine). Override via explicit `dual_axis_series=` or switch to `make_2pack_*`.

**3+ irreconcilable magnitude tiers stay rejected** -- a dual axis only has two scales; editorial choice required:

| Fix | Best when |
|---|---|
| **2-panel composite** (`make_2pack_horizontal` / `_vertical`) | Each panel its own y-axis. Canonical for 2 series; for 3+ split into panels where each panel's content shares a scale |
| **Dual-axis** -- `mapping['dual_axis_series']=['<name>']` + `mapping['y_title_right']='...'` | 2-3 series, argument is co-movement of differently-scaled shapes |
| **Normalize** -- z-score, rebase-to-100, pct-change every series | 3+ series; loses absolute level but preserves co-movement |
| **Small-multiples / facet** -- `mapping['facet']='<color_col>'` (drop `color`) | 3+ series with own y-axis per panel; argument is SHAPE of each component. See grids spoke |

Error message names offending series + provides exact `dual_axis_series=[...]` / `facet=...` payload.

### 9.2 Series-name discipline

`dual_axis_series` lists names exactly matching `color` column values. Define LEFT/RIGHT constants -- keeps the 4 places these names appear (DataFrame, `dual_axis_series`, left title, right title) in lockstep.

```python
LEFT_SERIES, RIGHT_SERIES = '2s10s Curve (bp)', 'WTI Crude ($/bbl)'
curve_df['series'] = LEFT_SERIES
oil_df['series'] = RIGHT_SERIES
df_long = pd.concat([curve_df, oil_df], ignore_index=True)
mapping = {'x': 'date', 'y': 'value', 'color': 'series',
           'dual_axis_series': [RIGHT_SERIES],
           'y_title': '2s10s (bp)', 'y_title_right': 'WTI ($/bbl)'}
```

Hygiene: rename DataFrame columns BEFORE melting; `.str.strip()` series columns from CSV (trailing whitespace silently disqualifies the right-axis row); re-check `df['series'].value_counts()` after any `dropna()`.

### 9.3 Inverted right axis

`invert_right_axis: True` flips the right axis (higher = bottom). Standard rates pattern where "up = bullish" on both axes (equities up + yields down both = risk-on). No value negation needed.

```python
mapping = {'x': 'date', 'y': 'value', 'color': 'series',
           'dual_axis_series': ['UST 10Y'], 'invert_right_axis': True,
           'y_title': 'S&P 500', 'y_title_right': 'UST 10Y (%)'}
```

### 9.4 Annotations against the right axis

`HLine`, `Segment`, `PointHighlight`, `Callout`, `Arrow`, `Band` (horizontal), `PointLabel` accept `axis='right'` -- pass y-values in right-axis units. `VLine` is axis-agnostic. Out-of-domain values silently dropped. **`LastValueLabel` does not apply on dual-axis** -- engine strips it (non-fatal warning); end-of-line labels collide with the right y-axis, so the colour legend renders. `Trendline` also stripped on dual-axis. For end-of-line labels alongside two y-scales, build single-axis charts and combine via `make_2pack_vertical()`.

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

| Intent | Better shape |
|---|---|
| Compare magnitudes side-by-side (not co-movement) | `make_2pack_vertical()` |
| 3+ series with scale problems | z-score normalize, single axis `multi_line` |
| Per-series regime annotations | one `multi_line` per series in composite |

### 9.6 Lead-lag pattern

"Does X anticipate Y?" -- ISM PMI ahead of equity returns ~6m, jobless claims ahead of unemployment ~3m, HY spreads ahead of defaults ~12m. Shift predictor's date column forward by lead horizon → predictor's line extends past predicted series's last actual; past co-movement implies near-term direction.

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

`VLine` at "Today" canonical; `Band` over future zone optional. For implied-target callout: `Arrow` / `PointHighlight` / `Callout` with `implied_target` computed from predictor calibration before charting -- engine does not derive.

| Don't | Why |
|---|---|
| `strokeDash` on predicted series to switch solid→dashed on dual-axis | Silently dropped on dual-axis (§9.4); `VLine` + `Band` on LEFT axis cleaner |
| `layers=[{'type':'point', 'data': future_df, ...}]` for forecast dots on dual-axis | Custom-data points don't pin reliably; dots disappear. Use `Arrow` / `PointHighlight` / `Callout` |
| Single-axis `multi_line` on disparate scales without z-score | Engine y-scale gate rejects (§9.1) |
| Stacked `make_2pack_vertical` of predictor + predicted | Loses visual co-movement that's the whole point |

---

## 10. Composite layouts

Composites > individuals for related data (shared x-axis, y-concept, comparison dimension). Individuals only for unrelated topics. For 8-30 entities sharing the same shape, use grid mode (grids spoke) instead of `make_*pack_*`.

| Series count | Approach |
|---|---|
| 2-4 | Single `multi_line` (ideal) |
| 5-6 | `make_2pack_horizontal()`, 2-3 lines each |
| 7-8 | `make_4pack_grid()`, 2 lines each |
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

All accept `title`, `subtitle`, `caption`, `side_left`, `side_right`, `save_as`, `spacing`, `filename_prefix`, `filename_suffix`; return `CompositeResult` (`ChartResult` fields + `chart_errors`). `caption` / `side_*` flank the whole pack (same shape as `make_chart`); sub-chart text panels go on each `ChartSpec`.

**Composite-global kwargs** (`skin`, `dimensions`, `dimension_preset`, `save_as`, `spacing`, …) belong on the `make_*pack_*` call, **not** on `ChartSpec`. `make_chart(skin=...)` is valid; `ChartSpec(skin=...)` raises a typed `ValidationError` naming the bad kwarg and pointing at the pack helper.

**Rules:** ChartSpec args positional, metadata keyword-only (never `top=spec_a`). QC composite PNG, not sub-specs. "Completely empty" QC fail usually means date still in index, y column all-NaN, or empty DataFrame. Color/x/y scales resolve independently per sub-chart. **Any sub-chart failure raises `ValidationError`** (message names how many failed) -- every panel must build from valid, non-empty data. **`multi_line` series names ≤25 chars in every pack-composite cell** (same LVL cap as standalone; see §6.1). **`heatmap` row labels must fit horizontally in composite cells** -- long y-axis category strings raise `HeatmapRowLabelTooLongError`; shorten before `make_*pack_*()` (§6.3).

**Per-cell colour-legend label budget** (when a sub-chart uses categorical `mapping['color']` and the legend renders): char cap = `floor(0.25 * cell_width_px / 7)`. Composite cells are narrow -- budget before `LegendLabelTooLongError`:

| Pack | Typical cell width | Approx char cap |
|---|---|---|
| `make_3pack_triangle` | ~320px | ~11 |
| `make_4pack_grid` (compact) | 280px | ~10 |
| `make_6pack_grid` (compact) | 260px | ~9 |

Standalone `make_chart` at 600px allows ~21 chars. Shorten colour-category names in the DataFrame before building the composite; aim ≤6 chars in 4-pack / 6-pack cells.

| Situation | Layout |
|---|---|
| US vs EU inflation | `make_2pack_horizontal` (same y-concept, different region) |
| Level + decomposition (rates path + 2s10s) | `make_2pack_vertical` |
| 4 regional PMIs | `make_4pack_grid` |
| Headline + 2 supporting | `make_3pack_triangle` |
| Sector dashboard (6 panels) | `make_6pack_grid` |
| 7-30 entities (Mag-7, sectors, G20, FX) | grid mode via `mapping['facet']` -- fetch grids spoke |

---

## 11. Chart time horizon

| Frequency | Default | Class | Use case |
|---|---|---|---|
| Quarterly / Monthly | 10 years | Medium | Cyclical patterns, regime comparisons -- default |
| Weekly | 5 years | -- | Trend + cycle (also YoY series) |
| Daily | 2-3 years | Short | Recent acceleration, event reactions |
| Intraday | 5 trading days | Very Short | Event reaction window, data releases |

Overrides: "highest since 2008" → MUST include 2008. Pre-pandemic → start ≥ 2015. Percentile claims require a full percentile window. Don't show 1-2y of monthly (hides cycle); 30+y of daily (noise); different ranges for compared charts. Structural shifts ("not seen since X") → use Long (20-50y) regardless of frequency.

---

## 12. Failure transparency

Never silently substitute a layout. If a requested shape isn't feasible, tell the user and offer alternatives. Max 2 retries per chart concept; after 2 failures, deliver best version with a note or ask about alternatives.

---

## 13. Static tables (`make_table()`)

`make_table()` + `TableResult` auto-injected (§1). Same brand palette and Liberation Sans font stack as `make_chart`. **Canvas engine-decided**: PNG width fits data (text columns wrap automatically), height grows to fit every row. PRISM never picks a dimension; nothing is truncated. **One hard limit:** a table too wide to read on a portrait 8.5x11 page **raises** `ValidationError`, not shrunk into illegible micro-text -- reshape it instead of widening it (§13.10).

Reach for `make_table` when the answer is structured rows × columns and a chart can't visualise the relationship cleanly: watchlists, term structures, P&L attribution, factor tilts, FX cross-rates, sector tapes, calendars, snapshot dashboards.

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

# Hardcoded -- list-of-dicts (column names from keys).
# Categorical RAG ('High'/'Medium'/'Low') uses cell_colors directly;
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

### 13.3 `TableResult` (dataclass -- dot notation only; failures raise, so a returned result has rendered)

| Attribute | Description |
|---|---|
| `success` / `error_message` | `True` on returned results; failures raise (§2) |
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

Three modes are the entire surface -- PRISM does not pick palettes.

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
| `'column'` (default) | Each column scaled to its own min/max | "Within this country, where does this tenor sit?" |
| `'row'` | Each row scaled across the group's columns | "At this tenor, where does each country sit vs peers?" -- yield-curve cross-country |
| `'group'` | Single shared scale across every cell | "Absolute level -- JPN low everywhere, US high" -- correlation matrix |

`heatmap_groups` wins over `column_color_modes` for any covered column.

### 13.6 Headers, rows, hierarchy

```python
# Multi-level column headers -- spans must sum to len(df.columns) per level
header_levels=[[('', 1), ('Yields (%)', 4), ('Changes (bp)', 2)]]   # 3+ levels degrade

# Navy mini-band between row blocks -- counts must sum to len(df)
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

- **Author totals into the DataFrame.** `total_rows=[8]` styles existing row at index 8 -- engine doesn't compute.
- **Header label spans sum to `len(df.columns)`.** Engine rejects with offending `level_idx` and total.
- **Row group counts sum to `len(df)`.** Same.
- **Color modes are 3 only.** Pick by semantic, not aesthetic. Diverging-at-zero ≠ ramp-from-zero.
- **`signed_columns` colours TEXT, not the cell.** Combine with `column_color_modes={col: 'rwg'}` for both.
- **Sparkline series can differ in length per row.** Each row's min/max scales independently.
- **Wide text columns wrap automatically.** PRISM doesn't opt in.
- **Width has a hard legibility limit -- reshape, don't widen.** A table whose body text would print below ~6pt across a portrait 8.5x11 page's usable width is rejected (the error reports the canvas px width + printed pt). Column COUNT is not the trigger: numeric columns can't compress and headers set a non-compressible floor, so a few long-header numeric columns can fail where a dozen narrow ones pass. When the natural shape is too wide (e.g. a metric × 24-month grid, a 40-column matrix), build it narrow from the start by ONE of: (1) **transpose** -- if many columns and few rows, swap them (months-as-rows, not months-as-columns); (2) **split** by column group into several tables (one per year / region) rendered separately; (3) **aggregate** -- show latest + 3m + 12m change instead of every period, or top-N rows; (4) **shorten headers**. Prefer reshaping at authoring time over emitting a table that will be rejected.

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

`make_table` **raises** `ValidationError` on failure; the message carries the reason. Common triggers (error message names the fix):

- `header_levels[N] spans sum to X, expected Y` -- adjust spans to sum `len(df.columns)`
- `header_levels[N][i]=... is not a (label, span) tuple` -- use tuples (or `{'label': X, 'span': N}` dicts)
- `row_groups[N]=... is not a (label, count) tuple` -- use `[(label, n_rows), ...]`
- `row_groups counts sum to X, expected len(df)=Y` -- adjust counts
- `column_color_modes[col]=... looks like rag thresholds` -- split: `column_color_modes={col: 'rag'}` + `rag_thresholds={col: {...}}`
- `heatmap_groups=... was passed as a dict-keyed-by-mode` -- use list-of-dicts (§13.5)
- `too wide to render legibly on a portrait 8.5x11 page` -- reshape: transpose / split by column group / aggregate to fewer periods / shorten headers (§13.10)
- `DataFrame has no columns` -- filter upstream
- `Pass either df= (DataFrame) or rows= (list of dicts/tuples)` -- pass exactly one; `Pass either df= or rows=, not both` -- pick one
- `s3_manager.put failed: ...` -- check `session_path`; verify manager is alive

`result.warnings` carries non-fatal annotations -- e.g. `column_color_modes[col]='rag' set but no rag_thresholds[col] provided -- cells render uncoloured.` Surface them.
