# Widget catalog

- **Context ID:** `echarts.widgets`
- **Owns:** `widget.catalog`, `widget.kpi`, `widget.table`, `widget.narrative`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#manifest-skeleton) and [template_crud.md](template_crud.md#widget-operations) for edits.

## Widget kinds

The closed widget enum is:

`chart`, `kpi`, `table`, `pivot`, `stat_grid`, `tool`, `note`, `markdown`, `image`, `divider`

| Widget | Purpose |
|---|---|
| `chart` | ECharts visualization; see [charts.md](charts.md#chart-type-catalog-30) |
| `kpi` | One current dataset-bound value, optional delta and sparkline |
| `table` | Sortable/searchable records with formatting and row detail |
| `pivot` | Viewer-configurable multidimensional aggregation |
| `stat_grid` | Compact grid of dataset-bound statistics |
| `tool` | Interactive calculator; see [widget_tool.md](widget_tool.md#tool-definition) |
| `markdown` | Plain Markdown narrative or semantic callout |
| `note` | Semantic callout alias |
| `image` | Image by `src` or `url` |
| `divider` | Full-width visual separator |

Every widget needs a stable unique `id` and integer width `w`. Non-chart widths may be 1–12; chart widths are 4 or 6. A row's widths must sum to at most 12.

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
    "delta_source": "rates.latest.us_10y_change_bp",
    "delta_label": "1D",
    "delta_decimals": 0,
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
| `delta_source` | Optional refreshable comparison using the same source grammar |
| `delta_label`, `delta_decimals` | Delta presentation |
| `prefix`, `suffix`, `decimals` | Value presentation |
| `sparkline_source` | `<dataset>.<column>` full-series reference |

`value` and `delta` may appear after compilation as resolved values, but persisted templates keep the source wires. A hand-typed value without `source` is invalid.

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
                    "dataset": "country_history",
                    "row_key": "country",
                    "filter_field": "country",
                    "mapping": {"x": "date", "y": "yield_10y"},
                },
                {
                    "type": "table",
                    "dataset": "country_events",
                    "row_key": "country",
                    "filter_field": "country",
                    "columns": ["date", "event"],
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
| `stats` | `fields` list of strings or `{field, label?, format?, prefix?, suffix?, sub?}` |
| `markdown` | `template` or `content`; `{column}` tokens expand from the clicked row |
| `chart` | `dataset`, `row_key`, `filter_field`, `mapping`; optional `chart_type` (`line`, `bar`, or `area`) |
| `table` | `dataset`, `row_key`, `filter_field`, optional column objects and `max_rows` |
| `kv` / `kv_table` | `fields` list from the clicked row; optional `title` |

`stat_grid` is not a popup section kind; express the same information with `type: "stats"`. If another rich shape is unsupported, preserve its analytical content as a supported `stats`/`markdown`/`chart`/`table`/`kv` section or as an inline dashboard widget. Popup charts have independent legend state: do not author popup legend synchronization. When shared legend visibility is required, place both charts inline and connect their ids with `links[].sync: ["legend"]`.

For every rich chart/table section:

1. `dataset` names a declared detail dataset.
2. `row_key` exists on the originating table dataset.
3. `filter_field` exists on the detail dataset.
4. Representative `row_key` and `filter_field` values overlap after type normalization.

The join is clicked row `row_key` → detail `filter_field`. Missing datasets/columns, non-overlapping keys, and empty explicit popup objects are blocking diagnostics. Use `row_click: false` only for deliberate opt-out.

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

`dataset_ref`, `row_dim_columns`, `col_dim_columns`, and `value_columns` are required. Dimension/value lists must be non-empty. `color_scale` is `sequential`, `diverging`, `auto`, or `{min, max, palette}`. `show_totals` is boolean and controls the supported paired row-and-column totals. Independent `row_totals` or `column_totals` keys are invalid.

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
