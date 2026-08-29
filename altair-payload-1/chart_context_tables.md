# Altair static tables (`make_table`)

This document governs every `make_table()` call. Structured rows × columns
ship as PNG tables across PRISM interfaces. Do not emit Markdown pipe tables,
`print(df)`, `df.to_string()`, or aligned text blocks.

Table colour kwargs are documented here; they are unrelated to the chart
colours document.

## 1. Data source and minimal calls

Pass exactly one source:

| Source | Argument |
|---|---|
| Pulled, loaded, or computed data | `df=<DataFrame>` |
| Curated rows | `rows=[{...}, ...]` |
| Curated tuples/lists | `rows=[(...), ...], columns=[...]` |

```python
# DataFrame
result = make_table(
    df=macro,
    title="Macro Snapshot",
    source="Haver",
    column_formats={"GDP YoY (%)": "pct_signed", "CPI YoY (%)": "pct"},
    signed_columns=["GDP YoY (%)"],
    column_color_modes={"GDP YoY (%)": "rwg", "CPI YoY (%)": "bw"},
    save_as="tables/macro_snapshot.png",
)

# Curated rows
RAG = {"High": "#2EB857", "Medium": "#FFC107", "Low": "#DC3545"}
themes = [
    {"Theme": "Soft Landing", "Owner": "Macro", "Conviction": "High"},
    {"Theme": "China Property", "Owner": "EM", "Conviction": "Medium"},
]
result = make_table(
    rows=themes,
    title="Theme Tracker",
    cell_colors={
        (i, "Conviction"): RAG[row["Conviction"]]
        for i, row in enumerate(themes)
    },
)
```

## 2. Public kwargs

`make_table` has no `mapping` dictionary and no side panels. Every table
option below is a top-level `make_table(...)` kwarg. Chart mapping, chart
colour, `side_left`, `side_right`, `annotations`, and `layers` do not apply
and raise if passed.

| Kwarg | Purpose |
|---|---|
| `df` | DataFrame source; mutually exclusive with `rows` |
| `rows` | List of dicts, tuples, or lists |
| `columns` | Headers for tuple/list rows; order override for dict rows |
| `title`, `subtitle` | Top labels. `title` is the finding; a figure id (`R15a`, `Exhibit 3`) is `subtitle`. Never splice an id into `title` |
| `caption` | Italic note below the table |
| `source` | Attribution; fills an unset caption as `Source: ...` |
| `theme_overrides` | Override individual house-palette colours, e.g. `{'row_band_color': '#FFF4E5'}`; an unknown key raises listing all of them |
| `column_formats` | `{column: format_hint}` |
| `column_aligns` | `{column: 'left'|'center'|'right'}` |
| `header_levels` | Multi-level column headers |
| `row_groups` | `[(label, row_count), ...]` section bands |
| `row_indent` | Per-row first-column indentation |
| `row_bands` | Alternating rows; default `True` |
| `row_colors` | `{row_index: hex}` background |
| `column_color_modes` | `{column: 'rwg'|'bw'|'rag'}` |
| `heatmap_groups` | Shared scales across several numeric columns |
| `rag_thresholds` | Thresholds for numeric `rag` columns |
| `highlight_columns` | Whole-column light-blue tint |
| `cell_colors` | `{(row, column): hex}` cell background override |
| `cell_text_colors` | `{(row, column): hex}` cell text override |
| `sparkline_columns` | `{display_column: [series_per_row]}` |
| `minibar_columns` | `{display_column: numeric_source_column}` |
| `signed_columns` | Positive/negative text colour |
| `total_rows`, `subtotal_rows` | Style rows already present in the data |
| `column_widths` | `{column: pixels}` pin, or `{column: 'auto'}` to fit the content and never wrap |
| `value_overrides` | `{(row, column): text}` replaces one cell's text, bypassing formatting |
| `row_height_scale` | Row air; 0.5–3.0, default 1.0 |
| `show_index` | Include DataFrame index; default `False` |
| `target_html_width` | Intended display width for font normalization; default 720, use 600 for narrower email |
| `save_as` | Stable PNG path |

A figure-label instruction does not change this surface. `side_left` /
`side_right` exist only on `make_chart` and `make_*pack_*`. Do not recover
from that refusal by writing `title="R16a | Twenty Widest Bonds..."` or
`title="R15a ;"` — keep `title` as the finding and put the id in `subtitle`.

If a DataFrame index carries a semantic identifier such as country or ticker,
either `reset_index()` so it becomes a named column (preferred) or set
`show_index=True`; the default intentionally omits the index.

Canvas dimensions are content-driven. Text columns wrap, every row is kept,
and the table is never truncated. To reach the width that keeps body text at
6pt on a portrait page the engine spends four levers in order — wrap text
columns to their floors, reflow multi-word headers onto a second line, give
back the cosmetic per-column padding, then grow the body font (a wider canvas
at a bigger font prints larger, because padding does not scale) — and raises
only when all four are exhausted. The budget is about 140 characters across
one row: the widest cell of each column, summed, less roughly 2.5 per column
for padding.

A refusal therefore means the content itself is too wide, and it names which
columns are paying and whether each one's floor comes from its header or its
values — shorten the header only where the error says "set by header". Reach
for `column_widths` / `row_height_scale` only to satisfy a stated layout
request; the engine's own sizing is the default. For "wide enough not to
wrap" pass `'auto'` rather than guessing a pixel count — the width depends on
font metrics you cannot measure.

**A square label-by-label numeric matrix is not a table.** A correlation
matrix pivoted into columns hits this ceiling at around 18 columns and reads
badly long before that. Render it with
`make_chart(chart_type='heatmap')` on the long-form frame instead: that path
sizes its own canvas from the matrix and has no page-width ceiling.

Every column-keyed kwarg above warns rather than fails when a name matches no
column, so a mistyped column silently styles nothing. Check `result.warnings`.

## 3. `TableResult`

Use dot notation:

| Field | Meaning |
|---|---|
| `png_path`, `download_url` | Stored PNG and user-facing URL |
| `n_rows`, `n_cols` | Rendered shape |
| `canvas_size` | Emitted `(width, height)` |
| `warnings` | Non-fatal dropped keys, unknown column names or format hints, automatic font adjustments |
| `truncated_rows` | Always 0 |
| `interactive`, `editor_url` | Whether an editor was emitted, and its internal link; never surface the URL |
| `success`, `error_message` | Returned results are successful; failures raise |

Inspect and surface material `result.warnings`.

### Editor companion

Session runs emit a self-contained HTML editor beside the PNG by default, in
which the user can restyle, reformat, resize, restructure and retype the
table directly and copy back a runnable `make_table(...)` call. Leave
`interactive` alone. Never surface `editor_url` — the user opens the editor
by clicking the table in place, so when they ask to adjust it themselves say
"you can edit the table by clicking on it". The editor is a per-table
companion, not a dashboard — a request for live filtering, refresh, or
cross-widget interaction is a `dashboards` task.

Studio-generated code round-trips exactly and carries both halves of the
edit — the kwargs and the data. Keep the whole block; dropping any kwarg it
carries (`theme_overrides`, `column_widths`, `value_overrides`,
`row_height_scale`) silently undoes the styling.

The data half arrives one of two ways and the code says which. Where every
edit was a rule, it emits the original frame followed by the pandas that
reproduces them — a drop, a sort, a filter, a rename, a `df.insert` for a
computed column — so replacing the literal with a fresh pull re-applies all
of it. Where an edit typed a value or placed a row by hand, it emits the
edited frame instead and states the reason in a comment above it; that one
cannot be refreshed without redoing the edit.

`value_overrides`, `row_colors`, `row_indent`, `total_rows`, and
`subtotal_rows` address rows by position either way, so pointing a studio
call at refreshed data moves them onto whatever now sits at that index, with
no error. Re-sort the new data the same way, or drop the row-indexed kwargs
and say so.

## 4. Colour semantics

Three PRISM-facing column modes:

| Mode | Meaning | Use |
|---|---|---|
| `rwg` | Red negative ↔ white zero ↔ green positive | Returns, P&L, surprises |
| `bw` | White → navy as magnitude rises | Unsigned levels such as volatility or AUM |
| `rag` | Discrete red / amber / green by explicit thresholds | Risk and status metrics |

`rag` is numeric and requires `rag_thresholds`:

```python
column_color_modes={
    "GDP YoY (%)": "rwg",
    "CPI YoY (%)": "bw",
    "Unemployment (%)": "rag",
    "Inflation (%)": "rag",
}
rag_thresholds={
    "Unemployment (%)": {"amber_above": 5.0, "red_above": 7.0},
    "Inflation (%)": {"amber_above": 2.0, "red_above": 4.0},
}
```

| Threshold form | Direction |
|---|---|
| `(red_max, amber_max)` | Lower is bad: below first red, below second amber, else green |
| `{'red_below': X, 'amber_below': Y}` | Explicit lower-is-bad |
| `{'amber_above': X, 'red_above': Y}` | Higher-is-bad |

String buckets such as `High` / `Medium` / `Low` use `cell_colors`, not
`column_color_modes='rag'`.

`rag` means traffic-light status against risk bands. A plain "highlight the
cells above X" is not that: build `cell_colors` from a comprehension over the
data, the same way string buckets do.

```python
cell_colors={
    (i, "Policy Rate (%)"): "#FFF4CC"
    for i, v in enumerate(df["Policy Rate (%)"]) if v > 4.0
}
```

### Shared heatmap scales

```python
heatmap_groups=[
    {
        "columns": ["1M", "3M", "6M"],
        "scope": "row",
        "mode": "diverging",
    },
]
```

| `scope` | Scale |
|---|---|
| `column` (default) | Each column independently |
| `row` | Across the selected columns within each row |
| `group` | One scale across every selected cell |

`mode` is `sequential` for unsigned magnitudes or `diverging` for
red-negative/green-positive. `heatmap_groups` wins over `column_color_modes`
for covered columns.

For signed returns, `rwg` colours each column on its own scale and is the
default choice. Switch to a row- or group-scope `diverging` heatmap only when
the comparison the user wants runs *across* the selected columns rather than
down them. Do not add `signed_columns` on top of either: the background
already carries the sign.

Per-cell background priority, highest first:

`cell_colors` → `total_rows` → `subtotal_rows` → `heatmap_groups` →
`column_color_modes` → `row_colors` → `highlight_columns` → group bands →
alternating row bands.

`signed_columns` changes text colour only and can be combined with a cell
background mode.

## 5. Headers, groups, and totals

```python
header_levels=[
    [("", 1), ("Yields (%)", 4), ("Changes (bp)", 2)],
]
row_groups=[("Americas", 3), ("EMEA", 4), ("Asia-Pacific", 5)]
row_indent=[1, 1, 0, 1, 1, 0, 0, 0, 0]
subtotal_rows=[2, 5]
total_rows=[8]
```

- Header spans on each level must sum to the number of columns.
- Row-group counts must sum to the number of rows.
- `total_rows` and `subtotal_rows` style existing rows; they do not calculate
  totals.
- Use at most two indentation levels; deeper structures should become groups.
- A long narrative column beside many numeric columns is the common width
  failure. Move the prose to `caption`, a group label, or a separate artifact.

## 6. Sparklines and mini-bars

```python
sparkline_columns={
    "Trend (60d)": [
        [101.2, 102.4, 99.8, 105.0],
        [98.0, 97.6, 100.2, 102.1],
    ],
}

minibar_columns={"Market cap": "Market Cap ($B)"}
```

Each sparkline row may have a different length and scales independently.
The sparkline key must name an existing display column; its cell values are
ignored. Series lists align to final row order. Use `[]` for a blank sparkline;
a shorter outer list leaves trailing rows blank. Mini-bars scale against the
source column across rows; the display column may also be the source column.

## 7. Number formats

Format hints format numeric values; they do not parse source text. Convert
currency and percentage strings such as `"$1.2M"` or `"4.2%"` to the intended
numeric unit before `make_table`.

| Hint | Output |
|---|---|
| `pct`, `pct_signed` | `12.3%`, `+1.5%` |
| `pct2`, `pct2_signed` | `12.34%`, `+1.50%` |
| `bp`, `bp_signed` | `42bp`, `+42bp` |
| `currency` | Magnitude-aware dollars |
| `ratio` | `2.45x` |
| `int` | `12,345` |

Omitted hints use magnitude-aware defaults.

Datetime columns are formatted automatically; name a hint only to override the
choice. A raw strftime string is also accepted.

| Hint | Output |
|---|---|
| `date_dmy`, `date_dmy_yy` | `05 Apr`, `05 Apr 26` |
| `date_mon_yy`, `date_mon_yyyy` | `Apr 26`, `Apr 2026` |
| `date_year`, `date_qtr` | `2026`, `Q2 26` |
| `date_iso`, `date_slash` | `2026-04-05`, `05/04/26` |
| `date_time` | `14:30` |

An unrecognised hint warns, names the closest match, and falls back to the
default format rather than raising — so a typo produces plausible but
unrequested output unless `result.warnings` is read.

## 8. Common shapes

| Shape | Useful kwargs |
|---|---|
| Macro snapshot | `row_groups`, `column_formats`, `rwg` / `bw` / numeric `rag` |
| Sovereign curves | `header_levels`, row-scope `heatmap_groups`, signed change columns |
| P&L attribution | `row_indent`, `subtotal_rows`, `total_rows`, `rwg` |
| Watchlist | Sparklines, mini-bars, signed return columns |
| Correlation matrix | Group-scope diverging `heatmap_groups` |
| Economic calendar | `rows`, categorical `cell_colors`, centered importance |
| Theme tracker | `rows`, categorical conviction `cell_colors` |

## 9. Failure contract

`make_table` raises one aggregated `ValidationError` naming every independent
defect it can evaluate. Common repairs are:

- pass exactly one of `df` or `rows`;
- provide `columns` for tuple/list rows;
- do not pass `side_left` / `side_right` / `annotations` / `layers`; a figure id belongs in `subtitle`;
- make header spans and row-group counts match the data;
- keep color-mode values to `rwg`, `bw`, or `rag`;
- put numeric RAG boundaries in `rag_thresholds` for every `rag` column;
- pass `heatmap_groups` as a list of dictionaries;
- keep `theme_overrides` keys to theme keys;
- keep `row_height_scale` within 0.5–3.0;
- transpose, split, aggregate, or shorten an over-wide table.

Fix every numbered finding, then re-run. Never catch and suppress the error.
