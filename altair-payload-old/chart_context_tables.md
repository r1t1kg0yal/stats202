# Altair Tables (`make_table`)

**Canonical for every table PRISM authors.** Across chat / email /
report / any artifact PRISM produces for the user, all tables MUST be
PNG artifacts from `make_table()`. **Markdown tables are forbidden
anywhere in PRISM output.** Report-pipeline workflow specifics
(`worker_N_findings.md`, `report.md`) live in
`report_worker_instructions.md` and `report_writer_instructions.md`.

Spoke fetched on demand from `chart_context.md`. Covers `make_table()` —
the static-PNG table renderer. Same brand palette and Liberation Sans
font stack as `make_chart`. **The canvas is engine-decided**: PNG
width fits the data (text columns wrap automatically when they would
otherwise be too wide; cap is soft) and height grows to fit every row.
PRISM never picks a dimension or canvas; nothing is ever truncated.

Reach for a table when the answer is structured rows × columns and a
chart can't visualise the relationship cleanly: watchlists, term
structures, P&L attribution, factor tilts, FX cross-rates, sector
tapes, calendars, snapshot dashboards.

**Two data-source paths.** Tables routinely mix data-pulled content
(macro / market / position pulls) with hand-curated content (themes,
trade ideas, calendar entries). Both are first-class — pick the one
that matches the source:

| Source | Pass to `make_table` |
|---|---|
| Real data (Haver / market / CSV / scraper / computed positions) | `df=<DataFrame>` |
| Hardcoded / hand-curated values | `rows=[{...}, {...}]` (or `rows=[(...), ...]` + `columns=[...]`) |

`df=` and `rows=` are mutually exclusive — the engine errors if you
pass both.

---

## 1. When to use `make_table` vs `make_chart`

| Situation | Reach for |
|---|---|
| Levels + changes across a curve / cross-section (5-15 rows × 4-8 cols) | `make_table` |
| Watchlist / tape with sparkline-per-row | `make_table` (sparkline cells) |
| Attribution / decomposition with parent-child rows | `make_table` (indent + total/subtotal) |
| Time series, distribution, scatter, ranking, dual-axis | `make_chart` (hub) |
| Many series sharing one shape (8-30 entities) | `make_chart` grid mode (`chart_context_grids.md`) |
| Single number / KPI tile | not in altair — use echarts dashboards |

---

## 2. Minimal call

### 2.1 Data-pulled (`df=`)

```python
result = make_table(
    df=df,                     # DataFrame from pull_*_data() / CSV / scraper
    title='Macro Snapshot',
    subtitle='G15 · Q1 2026',
    column_formats={'GDP YoY (%)': 'pct_signed', 'CPI YoY (%)': 'pct'},
    signed_columns=['GDP YoY (%)'],
    column_color_modes={'GDP YoY (%)': 'rwg', 'CPI YoY (%)': 'bw'},
    save_as='tables/macro_snapshot.png',
)
```

### 2.2 Hardcoded (`rows=`)

For hand-curated content (themes, trade ideas, calendar entries,
narrative tables) where there's no source dataset to pull. Pass
`rows=` as a list of dicts (column names from the dict keys) OR a list
of tuples/lists with `columns=[...]` naming the headers:

```python
# list-of-dicts form — column names from keys
# Categorical RAG (string buckets like 'High'/'Medium'/'Low') uses
# cell_colors directly; column_color_modes='rag' is for numeric
# columns + rag_thresholds (see §3 + §6).
RAG_HEX = {'High': '#1A8754', 'Medium': '#FFC107', 'Low': '#DC3545'}
themes = [
    {'Theme': 'Soft Landing',    'Owner': 'Macro',    'Conviction': 'High'},
    {'Theme': 'China Property',  'Owner': 'EM',       'Conviction': 'Medium'},
    {'Theme': 'European Energy', 'Owner': 'Equities', 'Conviction': 'High'},
]
result = make_table(
    rows=themes,
    title='Theme Tracker',
    cell_colors={(r, 'Conviction'): RAG_HEX[t['Conviction']]
                 for r, t in enumerate(themes)},
    save_as='tables/themes.png',
)

# list-of-tuples form — explicit columns=
result = make_table(
    rows=[
        ('USTs',   'Long 5Y',         'High',   'Macro'),
        ('DXY',    'Lower',           'Medium', 'FX'),
        ('Energy', 'Tactical long',   'Medium', 'Equities'),
    ],
    columns=['Asset', 'View', 'Conviction', 'Owner'],
    title='Trade Ideas',
)
```

`df=` and `rows=` are mutually exclusive. `make_table` is
auto-injected — do NOT import. `s3_manager`, `session_path`,
`user_id` are auto-injected at call time; never pass them.

### 2.3 Full kwarg reference

| Kwarg | Type | Purpose |
|---|---|---|
| `df` | DataFrame | Data-pulled tables — pass exactly one of `df` or `rows` |
| `rows` | list[dict] / list[tuple] | Hardcoded tables — pass exactly one of `df` or `rows` |
| `columns` | list[str] | Header names for `rows=`-as-tuples form; reorders for `rows=`-as-dicts form |
| `title` / `subtitle` | str | Top labels (left-aligned, FT/Bloomberg style) |
| `caption` | str | Italic note BELOW the table (auto-wraps) |
| `column_formats` | dict | `{col: hint}` — see §8 number formatting hints |
| `column_aligns` | dict | `{col: 'left'\|'center'\|'right'}` override (engine default: numeric → right, text → left) |
| `header_levels` | list | Multi-level column headers — see §5.1 |
| `row_groups` | list | `[(label, n_rows), ...]` navy band sub-headers — see §5.2 |
| `row_indent` | list | Per-row indent levels (first column only) — see §5.3 |
| `row_bands` | bool | Default True; alt-row stripe |
| `row_colors` | dict | `{row_idx: hex}` per-row tint — see §6 |
| `column_color_modes` | dict | `{col: 'rwg'\|'bw'\|'rag'}` per-column color — see §3 |
| `heatmap_groups` | list | Multi-column shared scale — see §4 |
| `rag_thresholds` | dict | `{col: (red_max, amber_max)}` for `'rag'` mode |
| `highlight_columns` | list | Tint full column light blue — see §6 |
| `cell_colors` | dict | `{(row, col): hex}` per-cell background — wins over everything. `col` accepts name (preferred) or integer index. |
| `cell_text_colors` | dict | `{(row, col): hex}` per-cell text override. Same key shape as `cell_colors`. |
| `sparkline_columns` | dict | `{col: [list_per_row]}` — see §7.1 |
| `minibar_columns` | dict | `{display_col: source_col}` — see §7.2 |
| `signed_columns` | list | Auto green-positive / red-negative TEXT colour |
| `total_rows` | list | Row indices to render in inverted navy + bold |
| `subtotal_rows` | list | Row indices to render bold + subtle band |
| `show_index` | bool | Include the DataFrame index as the leftmost column |

### `TableResult` (dataclass, NOT dict)

| Attribute | Type | Description |
|---|---|---|
| `success` | bool | True on render success |
| `png_path` / `download_url` | str | PNG S3 path / presigned URL |
| `error_message` | str-None | Failure reason |
| `warnings` | list | Non-fatal annotations (e.g. dropped `cell_colors` keys with unknown column names) |
| `n_rows` / `n_cols` | int | Shape after `show_index` adjustment |
| `truncated_rows` | int | Always 0 — `make_table` never truncates rows |
| `canvas_size` | tuple | (width, height) the engine actually emitted |

Access via dot notation only. Always check `r.success` before reading
`r.png_path` / `r.download_url`.

---

## 3. Color modes — three strings, no degrees of freedom

| Mode | Use case | Palette (engine-controlled) |
|---|---|---|
| `'rwg'` | Diverging at zero — signed columns where positive = good and negative = bad (P&L, returns, surprises vs forecast) | red(neg) ↔ white(0) ↔ green(pos) |
| `'bw'` | Sequential — values >= 0 where higher = "more" (CPI %, vol, AUM, market cap, headcount) | white → navy |
| `'rag'` | Discrete bucketing by author thresholds (Unemp red < 4 < amber < 6 < green) | red / amber / green |

Apply per column via `column_color_modes`:

```python
column_color_modes={
    'GDP YoY (%)': 'rwg',          # diverging at 0
    'CPI YoY (%)': 'bw',           # sequential, white → navy
    'Unemp (%)':   'rag',          # needs rag_thresholds
    'Inflation':   'rag',
}
rag_thresholds={
    'Unemp (%)':  (4.0, 6.0),                              # lower-is-bad: <4=red, 4-6=amber, >6=green
    'Inflation':  {'amber_above': 2.0, 'red_above': 4.0},  # higher-is-bad: <2=green, 2-4=amber, >4=red
}
```

| Threshold shape | Direction | Bucket boundaries |
|---|---|---|
| `(red_max, amber_max)` (legacy 2-tuple) | lower-is-bad | `< red_max` red, `< amber_max` amber, else green |
| `{'red_below': X, 'amber_below': Y}` | lower-is-bad (explicit) | same as above with named keys |
| `{'amber_above': X, 'red_above': Y}` | higher-is-bad (inflation, unemp, default rate) | `> red_above` red, `> amber_above` amber, else green |

Three modes are the entire surface. Anything else (palette tuning,
custom centers) falls under engine-controlled defaults — PRISM does
not pick.

---

## 4. Heatmap groups (multi-column shared scales)

When several columns belong to the same metric and should share one
heatmap scale (e.g. yield curve across countries, correlation matrix,
all-numeric block of a snapshot), use `heatmap_groups`:

```python
heatmap_groups=[
    {'columns': ['US', 'UK', 'EU', 'JPN'], 'scope': 'row',  'mode': 'sequential'},
    {'columns': ['Corr A', 'Corr B', 'Corr C'], 'scope': 'group', 'mode': 'diverging'},
]
```

Each group dict carries:

| Key | Type | Purpose |
|---|---|---|
| `columns` | list[str] | Column names included in the group |
| `scope` | str | `'column'` (default) / `'row'` / `'group'` — see table below |
| `mode` | str | `'sequential'` (→ bw palette) or `'diverging'` (→ rwg palette) |
| `palette` | str | Optional override; PRISM almost always omits this |

Scope semantics:

| Scope | Effect | Use case |
|---|---|---|
| `'column'` (default) | Each column scaled to its own min/max | "Within this country, where does this tenor sit?" |
| `'row'` | Each row scaled across the group's columns | "At this tenor, where does each country sit vs peers?" — yield-curve cross-country comparison |
| `'group'` | Single shared scale across every cell in the block | "Absolute level — JPN low everywhere, US high everywhere" — correlation matrix, true heatmap-of-numbers |

`heatmap_groups` wins over `column_color_modes` for any column it
covers.

---

## 5. Headers, rows, and hierarchy

### 5.1 Multi-level column headers

```python
header_levels=[
    [('', 1), ('Yields (%)', 4), ('Changes (bp)', 2)],   # super-header row
]
```

Each level is a list of `(label, span)` tuples. Spans must sum to
`len(df.columns)` per level. The bottom row is always the column-name
row (auto). Up to 3 levels read cleanly; deeper degrades.

### 5.2 Row-group navy bands

```python
row_groups=[('Americas', 3), ('EMEA', 4), ('Asia-Pac', 5)]
```

Inserts a navy mini-band labelled per group between row blocks.
Counts must sum to `len(df)`.

### 5.3 Indented hierarchical rows

```python
row_indent=[1, 1, 0, 1, 1, 0, 0, 0, 0]   # 0 = flush, 1 = one indent step (16 px)
```

Applied to the first column only. Pair with `subtotal_rows` /
`total_rows` for attribution layouts.

### 5.4 Total / subtotal rows (auto-styled)

```python
total_rows=[8],          # → inverted navy + bold + white text
subtotal_rows=[2, 5],    # → bold + subtle band
```

Rows in `total_rows` get the navy footer treatment automatically.
Rows in `subtotal_rows` get a subtle grey band + bold. Author the
totals into the DataFrame; engine handles the styling.

---

## 6. Per-row and per-cell control

| Kwarg | Purpose |
|---|---|
| `row_colors={r: hex}` | Per-row tint (flag outliers, sector-code rows). Loses to `heatmap_groups` / `column_color_modes` / `cell_colors` / `total_rows` / `subtotal_rows`; wins over `row_bands`. |
| `cell_colors={(r, c): hex}` | Per-cell background. Wins over EVERYTHING else. `c` is a column name (preferred) or integer index. |
| `cell_text_colors={(r, c): hex}` | Per-cell text colour. Same key shape as `cell_colors`. |
| `highlight_columns=[col, ...]` | Light-blue tint on entire column ("the answer" column). |
| `signed_columns=[col, ...]` | Auto green text for positive values, red for negative (text colour only — independent of cell background). |
| `row_bands=True` (default) | Subtle alt-row stripe. Set False for plain look. |

**Color resolution priority (top wins per cell):**

1. `cell_colors[(r, c)]`
2. `total_rows`
3. `subtotal_rows`
4. `heatmap_groups`
5. `column_color_modes`
6. `row_colors[r]`
7. `highlight_columns`
8. `row_groups` (handled separately as band rows between blocks)
9. `row_bands`

---

## 7. Special cells

### 7.1 Sparkline column

```python
sparkline_columns={'Trend (60d)': [
    [101.2, 102.4, 99.8, ..., 110.5],   # row 0 series
    [98.0,  97.6, 100.2, ..., 102.1],   # row 1 series
    ...
]}
```

The DataFrame value in the sparkline column is ignored; one list per
row of values renders as a tiny navy line + endpoint dot. The series
length per row can differ. Use for trailing-N-day price paths,
moving-average curves, period returns over time.

### 7.2 Mini-bar column (Bloomberg-style)

```python
minibar_columns={'MktBar': 'Mkt Cap ($B)'}
```

`{display_col: source_col}` — the display column becomes a horizontal
bar scaled to the source column's max across rows. Negative values
render right-aligned in red. Use for at-a-glance ranking by magnitude.

---

## 8. Number formatting hints

Pass via `column_formats` as `{col: hint}`:

| Hint | Format | Example |
|---|---|---|
| `'pct'` | `12.3%` | unsigned percent, 1dp |
| `'pct_signed'` | `+1.5%` | signed percent, 1dp |
| `'pct2'` / `'pct2_signed'` | `12.34%` | 2dp variants |
| `'bp'` / `'bp_signed'` | `42bp` / `+42bp` | basis points |
| `'currency'` | `$1.23B` / `$45.67M` / `$1,234.56` | magnitude-aware |
| `'ratio'` | `2.45x` | multiples |
| `'int'` | `12,345` | thousands-separated integer |
| (none) | magnitude-aware default | falls back to `,.1f` / `.2f` / `.3f` by abs value |

---

## 9. Authoring rules

- **Author totals into the DataFrame.** `total_rows=[8]` styles the
  row that EXISTS at index 8 — the engine doesn't compute the sum.
- **Header label spans must sum to `len(df.columns)`.** Engine rejects
  with the offending `level_idx` and span total.
- **Row group counts must sum to `len(df)`.** Same rejection pattern.
- **Color modes are 3 only — `'rwg'` / `'bw'` / `'rag'`.** Pick based
  on semantic, not aesthetic. Diverging-at-zero ≠ ramp-from-zero.
- **`signed_columns` colours TEXT, not the cell.** Combine with
  `column_color_modes={col: 'rwg'}` for both text + cell colour.
- **Sparkline series can differ in length per row.** Each row's
  min/max scales independently; faint baseline drawn to give the line
  context.
- **Mini-bar source can be the display column itself**
  (`minibar_columns={'X': 'X'}`) — then both number and bar render in
  the same cell.
- **Wide text columns wrap automatically.** The engine detects
  free-form text content (notes, themes, commentary) and wraps cells
  to multi-line; row heights grow to fit. PRISM doesn't opt in and
  doesn't set a wrap-line cap.

---

## 10. Anti-patterns (do NOT)

| Anti-pattern | Why |
|---|---|
| Reaching for any colour mode beyond `'rwg'` / `'bw'` / `'rag'` | The PRISM-facing surface is exactly those three. Engine-internal palettes are not for PRISM. |
| Computing totals in Python and passing as last row WITHOUT `total_rows=[N]` | Loses the inverted-navy footer treatment that signals "this is the answer" |
| `row_indent=[0, 1, 2, 3, ...]` (deep multi-level) | 2 indent levels read; 3+ degrades. Refactor to row groups. |
| Heatmap on a column where higher-is-just-different (Country code, Ticker, Sector) | Colour should encode magnitude or sign — not nominal identity |
| Mixing `cell_colors` with `column_color_modes` on the same cell | `cell_colors` always wins — reserve for one-off highlights, not bulk colouring |

---

## 11. Common shapes (worked examples)

Source column tells PRISM which kwarg to use: `df=` for data-pulled,
`rows=` for hardcoded.

| Shape | Source | Pattern |
|---|---|---|
| **Macro snapshot** | `df=` (Haver / market pull) | `row_groups=[(region, n), ...]` + `column_color_modes={'GDP YoY': 'rwg', 'CPI': 'bw'}` |
| **Sovereign curve cross-country** | `df=` (treasury / market pull) | `header_levels=[[('', 1), ('Yields (%)', N), ('Δ (bp)', M)]]` + `heatmap_groups=[{'columns': [yield_cols], 'scope': 'row', 'mode': 'sequential'}]` + `signed_columns=[Δ_cols]` |
| **P&L attribution** | `df=` (computed from positions) | `row_indent=[...]` + `subtotal_rows=[...]` + `total_rows=[N-1]` + `column_color_modes={'PnL': 'rwg'}` |
| **Watchlist** | `df=` (real-time market pull) | `sparkline_columns={'Trend': [...]}` + `minibar_columns={'MktCap (bar)': 'Mkt Cap ($B)'}` + `column_color_modes={'YTD %': 'rwg'}` + `signed_columns=[period_pct_cols]` |
| **Correlation matrix** | `df=` (computed from returns) | `heatmap_groups=[{'columns': [all numeric], 'scope': 'group', 'mode': 'diverging'}]` |
| **Econ calendar** | `rows=` (hand-curated upcoming events) | `cell_colors={(r, importance_col): RAG_hex}` per importance level + `column_aligns={'Importance': 'center'}` |
| **Theme tracker (categorical RAG)** | `rows=` (PM-authored narrative) | `cell_colors={(r, 'Conviction'): RAG_HEX[v]}` for string buckets like `'High'/'Medium'/'Low'` (see §2.2). Long `'Note'` columns wrap automatically. Use `column_color_modes={'col': 'rag'}` only on NUMERIC columns paired with `rag_thresholds` |
| **Trade ideas / curated watchlist** | `rows=` (PM-authored) | `rows=[(asset, view, conviction, owner), ...]` + `columns=[...]` |

---

## 12. Failure transparency

`make_table` always returns a `TableResult`. On render failure
`success=False` and `error_message` carries the reason; `png_path`
and `download_url` are `None`. Common failure modes:

| Error message prefix | Cause | Fix |
|---|---|---|
| `header_levels[N] spans sum to X, expected Y` | Multi-level header row span mismatch | Adjust spans to sum to `len(df.columns)` |
| `row_groups counts sum to X, expected len(df)=Y` | Row group counts don't match dataframe | Adjust counts |
| `DataFrame has no columns` | Empty DataFrame | Filter upstream |
| `Pass either df= (DataFrame) or rows= (list of dicts/tuples)` | Neither data-source kwarg passed | Pass exactly one |
| `Pass either df= or rows=, not both` | Both data-source kwargs passed | Pick one |
| `s3_manager.put failed: ...` | Underlying S3 / FS write failed | Check `session_path`; verify the manager is alive |
