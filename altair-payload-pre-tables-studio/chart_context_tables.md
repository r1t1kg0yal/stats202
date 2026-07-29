# Altair static tables (`make_table`)

Fetch this spoke before every `make_table()` call. Structured rows × columns
ship as PNG tables across PRISM interfaces. Do not emit Markdown pipe tables,
`print(df)`, `df.to_string()`, or aligned text blocks.

Table colour kwargs are documented here; they are unrelated to the chart
colours spoke.

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

`make_table` has no `mapping` dictionary. Every table option below is a
top-level `make_table(...)` kwarg; chart mapping and chart colour kwargs do
not apply.

| Kwarg | Purpose |
|---|---|
| `df` | DataFrame source; mutually exclusive with `rows` |
| `rows` | List of dicts, tuples, or lists |
| `columns` | Headers for tuple/list rows; order override for dict rows |
| `title`, `subtitle` | Top labels |
| `caption` | Italic note below the table |
| `source` | Attribution; fills an unset caption as `Source: ...` |
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
| `show_index` | Include DataFrame index; default `False` |
| `target_html_width` | Intended display width for font normalization; default 720, use 600 for narrower email |
| `save_as` | Stable PNG path |

If a DataFrame index carries a semantic identifier such as country or ticker,
either `reset_index()` so it becomes a named column (preferred) or set
`show_index=True`; the default intentionally omits the index.

Canvas dimensions are content-driven. Text columns wrap, every row is kept,
and the table is never truncated. A table too wide to remain legible on a
portrait page raises; transpose, split, aggregate, or shorten headers.

## 3. `TableResult`

Use dot notation:

| Field | Meaning |
|---|---|
| `png_path`, `download_url` | Stored PNG and user-facing URL |
| `n_rows`, `n_cols` | Rendered shape |
| `canvas_size` | Emitted `(width, height)` |
| `warnings` | Non-fatal dropped keys or automatic font adjustments |
| `truncated_rows` | Always 0 |
| `success`, `error_message` | Returned results are successful; failures raise |

Tables are deterministic and excluded from chart vision QC. Inspect and surface
material `result.warnings`.

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

### Shared heatmap scales

```python
heatmap_groups=[
    {
        "columns": ["US", "UK", "EU", "JPN"],
        "scope": "row",
        "mode": "sequential",
    },
]
```

| `scope` | Scale |
|---|---|
| `column` (default) | Each column independently |
| `row` | Across the selected columns within each row |
| `group` | One scale across every selected cell |

`mode` is `sequential` or `diverging`. `heatmap_groups` wins over
`column_color_modes` for covered columns.

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
- make header spans and row-group counts match the data;
- keep color-mode values to `rwg`, `bw`, or `rag`;
- put numeric RAG boundaries in `rag_thresholds` for every `rag` column;
- pass `heatmap_groups` as a list of dictionaries;
- transpose, split, aggregate, or shorten an over-wide table.

Fix every numbered finding, then re-run. Never catch and suppress the error.
