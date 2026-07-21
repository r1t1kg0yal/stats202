# Widget catalog

- **Context ID:** `echarts.widgets`
- **Owns:** `widget.catalog`, `widget.kpi`, `widget.table`, `widget.narrative`, `widget.user_input`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#manifest-skeleton) and [template_crud.md](template_crud.md#widget-operations) for edits.

## Widget kinds

The closed widget enum is:

`chart`, `kpi`, `table`, `data_grid`, `pivot`, `stat_grid`, `tool`, `user_input`, `note`, `markdown`, `image`, `divider`

| Widget | Purpose |
|---|---|
| `chart` | ECharts visualization; see [charts.md](charts.md#chart-type-catalog-31) |
| `kpi` | One current dataset-bound value, optional delta and sparkline |
| `table` | Sortable/searchable records with formatting and row detail |
| `data_grid` | Full-width, virtualized large-screen records surface |
| `pivot` | Viewer-configurable multidimensional aggregation |
| `stat_grid` | Compact grid of dataset-bound statistics |
| `tool` | Interactive calculator; see [widget_tool.md](widget_tool.md#tool-definition) |
| `user_input` | Dashboard-shared text, checklist, or uploaded knowledge files |
| `markdown` | Plain Markdown narrative or semantic callout |
| `note` | Semantic callout alias |
| `image` | Image by `src` or `url` |
| `divider` | Full-width visual separator |

Every widget needs a stable unique `id` and integer width `w`. Non-chart widths may be 1–12; standard chart widths are 4 or 6, while `hero: true` permits one full-width chart. `data_grid` is always full-width. A row's widths must sum to at most 12.

## KPI

KPI and stat-grid values must be data-bound. The source grammar is:

`<dataset>.<aggregator>.<column>`

The closed aggregator enum is:

`latest`, `first`, `sum`, `mean`, `min`, `max`, `count`, `prev`

```python
{
    "widget": "kpi",
    "id": "us10y",
    "w": 3,
    "label": "US 10Y",
    "source": "rates.latest.us_10y",
    "delta_source": "rates.prev.us_10y",
    "delta_label": "vs prev",
    "delta_decimals": 2,
    "suffix": "%",
    "decimals": 2,
    "sparkline_source": "rates.us_10y",
}
```

| Field | Meaning |
|---|---|
| `source` | Required refreshable value |
| `label` | Required short identity |
| `sub` | Optional subtitle |
| `delta_source` | Optional previous-level comparison (`cur − prev`); same source grammar as `source` |
| `delta` / `delta_pct` | Optional authored change magnitude and relative percent (shown as-authored) |
| `delta_label`, `delta_decimals` | Delta presentation |
| `prefix`, `suffix`, `decimals` | Value presentation |
| `sparkline_source` | `<dataset>.<column>` full-series reference |

`value` and `delta` may appear after compilation as resolved values, but persisted templates keep the source wires. A hand-typed value without `source` is invalid. Compile receipts list every user-visible KPI string (headline and change pill); sense-check those before shipping.

## Stat grid

```python
{
    "widget": "stat_grid",
    "id": "risk_stats",
    "w": 6,
    "title": "Risk",
    "stats": [
        {
            "id": "vol",
            "label": "Realized vol",
            "source": "risk.latest.vol_20d",
            "suffix": "%",
            "decimals": 1,
        },
        {
            "id": "drawdown",
            "label": "Drawdown",
            "source": "risk.min.drawdown",
            "suffix": "%",
            "decimals": 1,
        },
    ],
}
```

Each stat requires `label` and `source`; use the KPI aggregator enum. Keep grids compact and conceptually coherent.

## Table

```python
{
    "widget": "table",
    "id": "country_grid",
    "w": 12,
    "title": "Country snapshot",
    "dataset_ref": "country_snapshot",
    "columns": [
        {"field": "country", "label": "Country", "format": "text"},
        {
            "field": "surprise_z",
            "label": "Surprise z",
            "format": "number:1",
            "align": "right",
            "conditional": [
                {"op": ">=", "value": 1, "color": "#19a974"},
                {"op": "<=", "value": -1, "color": "#ef5350"},
            ],
        },
        {
            "field": "yield_10y",
            "label": "10Y",
            "format": "number:2",
            "align": "right",
        },
    ],
    "max_rows": 20,
}
```

Tables require `dataset_ref` or `ref`. The closed column-format enum is:

`text`, `number`, `integer`, `percent`, `currency`, `bps`, `date`, `datetime`, `link`, `signed`, `delta`

Numeric precision uses `<format>:<decimals>`, such as `percent:1`.

Column fields include:

- `field`, `label`, `format`, `align`;
- `conditional`: ordered rule dicts using filter operators;
- `color_scale`: `{min, max, palette}`;
- `in_cell`: `bar`, `heat`, or `sparkline`;
- for sparkline cells: `from_dataset`/`dataset` and `row_key`.

Table controls may define searchable/sortable columns, frozen first column, and visible-column defaults. Pre-aggregate or narrow tables above 1,000 rows; 5,000 rows is blocking.

### Narrative-table review

A table with at most three rows and a cell of 160+ characters or 28+ words is flagged `table_narrative_wrap_risk` and makes its panel `REVIEW_REQUIRED`. The receipt's width evidence is the widget's declared `w` share of the 12-column dashboard grid together with its visible column count; it is an advisory wrap-risk estimate, not a pixel measurement. Inspect the risk-ranked rows through `review.panel(id)`. Keep a table when the cells remain genuinely comparable; otherwise use a note/markdown panel or a short summary with drill-down rather than acknowledging likely clipping blindly.

### Virtualized data grid

Use `data_grid` when a full-width analytical screen needs hundreds or thousands of rows without placing every row in the DOM:

```python
{
    "widget": "data_grid",
    "id": "security_grid",
    "w": 12,
    "h_px": 620,
    "title": "Security universe",
    "dataset_ref": "securities",
    "columns": security_columns,
    "page_size": 100,
    "max_rows": 5000,
    "searchable": True,
}
```

`data_grid` shares the table column, sorting, searching, filter, row-detail, CSV, and Excel contracts. Author `columns` as objects such as `{"field": "spread_bp", "label": "Spread", "format": "bps"}`; bare string columns are not accepted on an inline table or data grid. It is always virtualized: rows are sliced into `page_size` chunks and appended near the scroll boundary, while PDF/print expands the complete filtered/sorted result up to `max_rows`. `page_size` is 20–1,000, `h_px` is 240–1,200, and `max_rows` remains capped at 5,000. Do not raise data ceilings to compensate for an unbounded product query; slice or aggregate upstream first.

### Row details

Simple popup:

```python
{
    "row_click": {
        "title_field": "country",
        "subtitle_template": "{region}",
        "popup_fields": ["country", "region", "yield_10y", "surprise_z"],
    }
}
```

Rich popup:

```python
{
    "row_click": {
        "title_field": "country",
        "detail": {
            "sections": [
                {
                    "type": "chart",
                    "id": "country_history_popup",
                    "dataset": "country_history",
                    "row_key": "country",
                    "filter_field": "country",
                    "chart_type": "line",
                    "mapping": {
                        "x": "date",
                        "y": "yield_10y",
                        "zoom": True,
                    },
                },
                {
                    "type": "table",
                    "dataset": "country_events",
                    "row_key": "country",
                    "filter_field": "country",
                    "columns": [
                        {"field": "date", "label": "Date"},
                        {"field": "event", "label": "Event"},
                    ],
                },
            ]
        },
    }
}
```

The closed `detail.sections[].type` enum is:

`stats`, `markdown`, `chart`, `table`, `kv`, `kv_table`

| Section type | Authoring contract |
|---|---|
| `stats` | `fields` from the clicked source row, as strings or `{field, label?, format?, prefix?, suffix?, sub?}` |
| `markdown` | `template` or `content`; `{column}` tokens expand from the clicked row |
| `chart` | `dataset`, `row_key`, `filter_field`, `mapping`; optional stable `id`; optional `chart_type` (`line` default, `bar`, or `area`); optional `series_colors`; optional `mapping.zoom`, `mapping.smooth`, `mapping.color`, and `mapping.stack` |
| `table` | `dataset`, `row_key`, `filter_field`, optional column objects and `max_rows` |
| `kv` / `kv_table` | `fields` list from the clicked row; optional `title` |

`stat_grid` is not a popup section kind; express the same information with `type: "stats"`. If another rich shape is unsupported, preserve its analytical content as a supported `stats`/`markdown`/`chart`/`table`/`kv` section or as an inline dashboard widget. `row_click.title_field` is optional and defaults to the first displayed column; set it to another originating-dataset field when that field should identify the rich popup. Give a popup chart a stable `id` when a filter or manifest link targets it. Popup and inline charts use the same controller, including theme, legend, smoothing, zoom, click, brush, filtering, and `links[]` behavior.

For every rich chart/table section:

1. `dataset` names a declared detail dataset.
2. `row_key` exists on the full originating table dataset; it may remain off-grid and need not appear in `columns`.
3. `filter_field` exists on the detail dataset.
4. Representative `row_key` and `filter_field` values overlap after type normalization.

The join is clicked row `row_key` → detail `filter_field`. Missing datasets/columns, non-overlapping keys, and empty explicit popup objects are blocking diagnostics. A successful strict compile therefore proves representative overlap; `inspect_dashboard(FOLDER)["findings"]` must contain no `popup_section_keys_no_overlap` finding before delivery. Use `row_click: false` only for deliberate opt-out.

## Pivot

```python
{
    "widget": "pivot",
    "id": "cross_asset_pivot",
    "w": 12,
    "title": "Cross-asset pivot",
    "dataset_ref": "cross_asset",
    "row_dim_columns": ["asset_class", "security"],
    "col_dim_columns": ["period"],
    "value_columns": ["return_pct", "volatility"],
    "agg_options": ["mean", "sum", "median", "min", "max", "count"],
    "color_scale": "diverging",
    "show_totals": True,
}
```

`dataset_ref`, `row_dim_columns`, `col_dim_columns`, and `value_columns` are required. Dimension/value lists must be non-empty. `color_scale` is `sequential`, `diverging`, `auto`, or `{min?, max?, palette?, kind?}`; palette names are validated and must be sequential/diverging. The same resolved theme scale is used when the dictionary omits a palette. `show_totals` is boolean and controls the supported paired row-and-column totals. Independent `row_totals` or `column_totals` keys are invalid.

Use a pivot when the viewer needs to choose dimensions/aggregation. Use a table when the product has one intended comparison.

## Markdown and notes

Plain narrative:

```python
{
    "widget": "markdown",
    "id": "method",
    "w": 6,
    "content": "### Method\n\nSpread = 10Y minus 2Y.",
}
```

Semantic callout:

```python
{
    "widget": "markdown",
    "id": "thesis",
    "w": 6,
    "kind": "thesis",
    "title": "Base case",
    "content": "Front-end rates remain supported while inflation normalizes.",
}
```

The closed note-kind enum is:

`insight`, `thesis`, `watch`, `risk`, `context`, `fact`

`markdown` requires `content` or `body`. When `kind` is present it renders as a semantic card. `note` accepts the same body and note kinds; use `markdown` for authored manifests.

Values stated as facts must trace to refreshed data or identified sources. Use:

- `thesis` for the load-bearing view;
- `watch` for monitoring conditions;
- `risk` for invalidation/adverse scenarios;
- `fact` for sourced evidence;
- `insight` for interpretation;
- `context` for framing/methodology.

## Persisted user input

Use `user_input` when the dashboard needs shared manual state rather than authored narrative. The dashboard owner can write; every authorized dashboard viewer can read. Its stable widget `id` is the persistence identity, so preserve both `id` and `mode` after users begin saving.

```python
[
    {
        "widget": "user_input",
        "id": "desk_notes",
        "mode": "text",
        "w": 4,
        "title": "Desk notes",
        "placeholder": "Add the current handoff...",
        "rows": 8,
        "seed": {"text": ""},
    },
    {
        "widget": "user_input",
        "id": "close_checklist",
        "mode": "checklist",
        "w": 4,
        "title": "Close checklist",
        "seed": {
            "items": [
                {"id": "send-wrap", "text": "Send market wrap", "checked": False},
            ],
        },
    },
    {
        "widget": "user_input",
        "id": "research_files",
        "mode": "files",
        "w": 4,
        "title": "Research files",
        "seed": {"files": []},
    },
]
```

| Field | Contract |
|---|---|
| `mode` | Required: `text`, `checklist`, or `files` |
| `title` | Optional visible heading |
| `placeholder` | Text mode only; at most 500 characters |
| `rows` | Text mode only; integer 3–30, default 8 |
| text `seed` | Exactly `{"text": <string>}`; at most 250,000 UTF-8 bytes |
| checklist `seed` | Exactly `{"items": [...]}`; at most 500 unique stable items, each exactly `id`, non-empty `text`, and boolean `checked` |
| files `seed` | Omit or use exactly `{"files": []}`; file paths cannot be pre-seeded |

Seed content is the first-render default only. After the first successful save, persisted state wins across rebuilds and refreshes. Browser saves never modify the manifest, datasets, or compiled HTML. Uploaded files accept PDF, DOCX/XLSX/PPTX, Outlook MSG, UTF-8 text/Markdown/CSV/JSON, and common raster images up to 25 MB; active or content-mismatched files are rejected.

Read saved state for analysis through the public helper:

```python
from dashboards import read_dashboard_user_input

notes = read_dashboard_user_input(FOLDER, "desk_notes")
all_saved = read_dashboard_user_input(FOLDER)
file_history = read_dashboard_user_input(
    FOLDER, "research_files", include_deleted=True,
)
```

One widget id returns its persisted state or `{}` before the first save. Omitting `widget_id` returns a mapping of every widget that has persisted state. Files mode returns verified metadata and server-authoritative object keys; use those returned keys rather than constructing paths. `include_deleted=True` adds tombstoned file history.

Use guarded `update_widget` operations for presentation fields such as title, placeholder, rows, or seed before first save. Do not place saved text, checklist state, or uploaded-file keys in a manifest patch.

## Image and divider

```python
{
    "widget": "image",
    "id": "framework",
    "w": 6,
    "src": "https://example.com/framework.png",
    "title": "Framework",
}
```

Image requires `src` or `url`. Use only stable, authorized assets with useful context.

```python
{"widget": "divider", "id": "inflation_divider", "w": 12}
```

## Conditional visibility

Every widget may use `show_when`; the compile-time data forms, runtime filter form, operators, and composition rules are owned by [filters.md](filters.md#conditional-visibility).

## Widget judgment

- Stable ids are contracts for targeted edits, filters, links, popups, telemetry, and deep links.
- KPI/stat-grid numbers must remain refreshable and provenance-backed.
- A note should change interpretation, not repeat a nearby label.
- A table should expose only fields needed for comparison.
- Popup join keys must exist and overlap.
- Preserve sibling widgets and controls during targeted edits.
