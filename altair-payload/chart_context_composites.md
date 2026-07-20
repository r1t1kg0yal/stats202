# Altair composites and batch building

Fetch this spoke before any `ChartSpec`, `make_*pack_*`, or `build_charts` call,
and whenever one script builds two or more charts. Composite panels tell one
related story in one PNG; `build_charts` safely attempts several independent
chart/composite calls.

## 1. Pick the layout

| Need | Shape |
|---|---|
| Compare two series or views | `make_2pack_horizontal` |
| Level above change/decomposition | `make_2pack_vertical` |
| One headline plus two supporting views | `make_3pack_triangle` |
| Four coordinated regions/sectors/scenarios | `make_4pack_grid` |
| True six-panel monitoring sheet | `make_6pack_grid` |
| Seven to 36 same-shape entities | Facet grid, not a pack; fetch grids |

Two panels are the default for an analytical argument. Four or six should be
used only when the grid itself is meaningful.

For line count: aim for at most four lines per cell. Five or six can render but
are crowded; seven or more raises. Prefer grouping related series into cells,
faceting same-shape entities, normalizing, or aggregating.

## 2. `ChartSpec`

```python
left = ChartSpec(
    df=us_df,
    chart_type="multi_line",
    mapping={"x": "date", "y": "value", "color": "series",
             "y_title": "CPI YoY (%)"},
    title="United States",
    source="BLS via Haver",
)

right = ChartSpec(
    df=eu_df,
    chart_type="multi_line",
    mapping={"x": "date", "y": "value", "color": "series",
             "y_title": "HICP YoY (%)"},
    title="Euro Area",
    source="Eurostat",
)
```

Constructor shape:

```python
ChartSpec(
    df, chart_type, mapping, *,
    title=None, subtitle=None, annotations=None, layers=None,
    caption=None, source=None, side_left=None, side_right=None,
    x_title=None, y_title=None, y_title_right=None,
)
```

The first three arguments may be positional or keyword. Metadata is
keyword-only. `ChartSpec` accepts per-cell content only; `skin`, dimensions,
spacing, filenames, and save paths belong on the pack helper. Unknown kwargs
raise with the valid placement.

If a cell's date lives in a named datetime index, still set
`mapping['x']='date'`; the engine promotes the index when that column is
absent. Wide line cells may list their value columns in `mapping['y']`.

## 3. Pack helpers

```python
result = make_2pack_horizontal(
    left,
    right,
    title="Inflation Has Converged",
    subtitle="Core measures have slowed across both regions",
    source="BLS and Eurostat",
    save_as="charts/inflation_compare.png",
)
```

The chart slots are positional:

| Function | Positional `ChartSpec` arguments |
|---|---|
| `make_2pack_horizontal(c1, c2, ...)` | 2 side-by-side |
| `make_2pack_vertical(c1, c2, ...)` | 2 stacked |
| `make_3pack_triangle(top, bottom_left, bottom_right, ...)` | 3 |
| `make_4pack_grid(top_left, top_right, bottom_left, bottom_right, ...)` | 4 |
| `make_6pack_grid(c1, ..., c6, ...)` | 6; `specs=[c1, ..., c6]` is also valid |

Do not invent slot keywords such as `top=`, `left=`, or `chart_1=`.

All helpers accept composite-level `title`, `subtitle`, `caption`, `source`,
`side_left`, `side_right`, `skin`, `dimensions` / `dimension_preset`,
`spacing`, `save_as`, and filename prefix/suffix. Per-cell attribution and
text panels stay on each `ChartSpec`; pack-level `source` fills an unset
pack-level caption.

Each cell owns its mapping, colour scale, axes, and annotations. Apply chart
colour kwargs inside the cell's `mapping` after fetching the colours spoke.
Composite cells are narrower than standalone charts, so shorten category,
legend, and end-label names aggressively; the engine raises with the exact
offenders rather than truncating.

## 4. All-or-nothing failure contract

An empty or all-invalid DataFrame in any `make_chart` or `ChartSpec` raises;
check row count after filters. If any `ChartSpec` fails, the entire composite
raises `ValidationError`; no partial PNG is returned. The message names every
failing cell and all independent findings within each cell. Validate panel
data before composition and fix all reported findings together.

Automatic dual-axis scale recovery is standalone-only. If a composite cell
needs two axes, declare its binding and semantic `y_title_right` on that
`ChartSpec`.

The returned `CompositeResult` has the normal chart fields plus `layout`,
`n_charts`, and `chart_errors`. A returned result is successful; failures
raise. Foreground post-script QC evaluates the composite PNG once, not its
individual cells.

## 5. `build_charts()` for two or more chart calls

A bare sequence stops at the first exception, hiding every later defect.
`build_charts` attempts every zero-argument thunk and aggregates all failures:

```python
built = build_charts([
    ("us_cpi", lambda: make_chart(
        df=us_cpi,
        chart_type="multi_line",
        mapping={"x": "date", "y": "value", "y_title": "CPI YoY (%)"},
        title="US Inflation",
        save_as="charts/us_cpi.png",
    )),
    ("regional_compare", lambda: make_2pack_horizontal(
        left,
        right,
        title="US and Euro Area Inflation",
        save_as="charts/regional_compare.png",
    )),
])
```

Each entry is `(short_name, zero_arg_callable)`. A composite counts as one
thunk. Define its `ChartSpec`s before the list and close over them.

On complete success, the return value is `[(name, result), ...]` in input
order. If anything fails, `build_charts` raises after attempting the full list;
the message includes each failed name and mentions rendered survivors. The
survivor note is diagnostic, not permission to ship a partial set: fix every
failure and rebuild the whole batch. Stable `save_as` paths overwrite the
earlier survivor render.

Do not wrap individual chart calls in your own `try/except`, and do not use a
`for` loop that calls `make_chart` directly. A single chart should call
`make_chart` directly and let its error bubble.
