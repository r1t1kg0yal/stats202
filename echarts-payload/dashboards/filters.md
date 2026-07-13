# Filters and linked interaction

- **Context ID:** `echarts.filters`
- **Owns:** `filter.catalog`, `filter.rule`, `filter.cascade`, `filter.link`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#manifest-skeleton) and [template_crud.md](template_crud.md#filter-operations) for edits.

## Filter catalog

The closed filter enum is:

`dateRange`, `select`, `multiSelect`, `numberRange`, `toggle`, `slider`, `radio`, `text`, `number`, `rule`

| Type | Core fields | Use |
|---|---|---|
| `dateRange` | `field`, `default`, optional `mode` | Time window |
| `select` | `field`, `options`, `default` | One categorical value |
| `multiSelect` | `field`, `options`, `default` list | Multiple categorical values |
| `numberRange` | `field`, `[low, high]` default | Numeric interval |
| `toggle` | `field`, boolean default, optional `op` | Boolean state |
| `slider` | `field`, `min`, `max`, `step`, `default`, optional `op` | Bounded numeric threshold |
| `radio` | `field`, `options`, `default` | Compact categorical choice |
| `text` | `field`, string default, optional `op` | Text match |
| `number` | `field`, numeric default, optional `op` | Numeric threshold |
| `rule` | nested `rule` tree | Compound screen |

Every filter needs a unique `id`, valid `type`, and `targets` list. `field` is always one bare persisted column such as `"region"`, never a qualified string such as `"fundamentals.region"`; dataset ownership is resolved from `targets`. Targets are data-bound widget ids or patterns such as `"*"`, and the field must exist in every targeted widget dataset.

The closed operator enum is:

`==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`, `in`, `not_in`

## Date range

```python
{
    "id": "lookback",
    "type": "dateRange",
    "label": "Initial range",
    "default": "5Y",
    "field": "date",
    "targets": ["curve", "spread", "events"],
}
```

Default `mode: "view"` sets the initial chart data-zoom window while charts retain full history; the same filter deliberately row-filters targeted tables, data grids, KPIs, pivots, and stat grids. Set `mode: "filter"` only when targeted chart rows themselves must also be discarded.

The fixed visible preset surface is `1M`, `3M`, `6M`, `YTD`, `1Y`, `2Y`, `5Y`, `All`; it has no authored `options` key. Canonical defaults use those tokens with complete history authored as `MAX`; supplied aliases `All` and `all` normalize to `MAX`, while the control displays and selects `All`. Under default `mode: "view"`, `MAX`/`All` includes every row on targeted tables, data grids, KPIs, pivots, and stat grids while chart targets retain full history with a full-range data-zoom window. Date fields across targets must parse as compatible dates.

## Select, multi-select, and radio

```python
{
    "id": "region",
    "type": "select",
    "label": "Region",
    "default": "",
    "all_value": "",
    "options": [
        {"value": "", "label": "All"},
        {"value": "US", "label": "United States"},
        {"value": "EU", "label": "Europe"},
    ],
    "field": "region",
    "targets": ["country_chart", "country_table"],
}
```

Options are primitives or `{value, label}` dictionaries. Defaults use option values, not labels. Use:

- `select` for one value in a larger domain;
- `radio` for a small set that benefits from simultaneous visibility;
- `multiSelect` when comparison across selected categories is the point.

`select`/`radio` may use an empty `all_value` for no categorical
restriction. `multiSelect` uses the same `field`, `options`, `label`, and
`targets` schema, but its `default` is a list of option values:

```python
{"id": "region", "type": "multiSelect", "field": "region",
 "options": ["US", "EU", "JP", "UK"],
 "default": ["US", "EU", "JP", "UK"],
 "targets": ["regional_performance", "regional_snapshot"]}
```

Selected values are OR-included; an empty selection returns zero rows. To
open unfiltered, select every option rather than authoring `all_value`.

## Numeric and text controls

```python
{
    "id": "min_z",
    "type": "slider",
    "label": "|z| ≥",
    "default": 0,
    "min": 0,
    "max": 3,
    "step": 0.1,
    "field": "zscore",
    "op": ">=",
    "transform": "abs",
    "targets": ["rv_table"],
}
```

```python
{
    "id": "valuation",
    "type": "numberRange",
    "label": "Forward P/E",
    "default": [10, 30],
    "field": "forward_pe",
    "targets": ["equity_table"],
}
```

```python
{
    "id": "issuer_search",
    "type": "text",
    "label": "Issuer contains",
    "default": "",
    "field": "issuer",
    "op": "contains",
    "targets": ["bond_table"],
}
```

`slider`, `number`, and `text` require `field`. `slider` also requires `min` and `max`. Use stable analytical bounds when comparisons across refreshes matter.

## Toggle

```python
{
    "id": "ig_only",
    "type": "toggle",
    "label": "IG only",
    "default": False,
    "field": "is_ig",
    "targets": ["bond_table"],
}
```

Use a boolean field when possible. If a toggle applies an operator/value policy to another field, make that policy explicit and verify both states.

## Compound rules

```python
{
    "id": "screen",
    "type": "rule",
    "label": "Compound screen",
    "summary": "rated AND (rich-tight OR short-fin)",
    "targets": ["bond_table"],
    "rule": {
        "all": [
            {"field": "rating", "op": "in",
             "value": ["AAA", "AA", "A", "BBB"]},
            {"any": [
                {"all": [
                    {"field": "ytm_pct", "op": ">", "value": 4.5},
                    {"field": "spread_bp", "op": "<", "value": 200},
                ]},
                {"all": [
                    {"field": "sector", "op": "in",
                     "value": ["Financials", "Banks"]},
                    {"field": "duration_yrs", "op": "<", "value": 5},
                ]},
                {"not": {
                    "field": "ticker",
                    "op": "startsWith",
                    "value": "Z",
                }},
            ]},
        ]
    },
}
```

Rule leaves are `{field, op, value}`. Compose with `all`, `any`, and `not`. `summary` is the only rule-level explanatory text and must be a string; it renders with the rule control automatically. Do not invent rule `chip`, `subtitle`, or popup keys.

## Cascading options

```python
[
    {
        "id": "region",
        "type": "select",
        "options": ["NA", "EU", "AP"],
        "default": "NA",
        "field": "region",
        "targets": ["country_table"],
    },
    {
        "id": "country",
        "type": "select",
        "options": ["US"],
        "depends_on": "region",
        "options_from": {
            "dataset": "country_universe",
            "key": "country",
            "where": "region == ${region}",
        },
        "field": "country",
        "targets": ["country_table"],
    },
]
```

`depends_on` names another declared filter. `options_from.dataset` and `.key` must exist after refresh. The placeholder in `where` uses the upstream filter id. Rebuilt options are deduplicated, then sorted numerically when every value is numeric and otherwise lexically with `String(a).localeCompare(String(b))`. Choose an initial child option valid for the parent's default.

When an upstream value changes, descendants rebuild breadth-first in filter declaration order. A single-select/radio child keeps its current value if still valid, otherwise resets to the first rebuilt option or `""` when none remain. A multi-select child keeps only selected values still present. Every deeper descendant then rebuilds from that updated state. Dependency cycles are invalid.

## Scope and targeting

`targets` is the execution contract; optional `scope` controls placement:

- `global`;
- `tab:<tab_id>`;
- inferred tab scope when every target is on one tab.

Before adding a filter:

1. resolve every target id;
2. prove each target dataset contains the field;
3. verify option/default values exist;
4. narrow targets when datasets are incompatible.

Independent filters that share a target compose with **AND**: a row must
satisfy every active filter. Values selected within one `multiSelect` compose
with OR as described above.

Filters can target `chart`, popup chart ids, `kpi`, `table`, `data_grid`, `pivot`, and `stat_grid`. Tools and narrative widgets are not filter-targetable. Chart targets are valid only when the browser can faithfully rebuild their emitted shape: wide/grouped line/bar/area/scatter, stacked bar/area, pie/donut, heatmap, `geo_map`, `scatter_studio`, and `correlation_matrix`. A default `dateRange` `mode: "view"` may additionally target supported time-series charts such as candlesticks because it changes the chart's data-zoom window without rebuilding series. Unsupported chart/filter combinations fail with `filter_chart_rebuild_unsupported`; narrow the targets or reshape the persisted data rather than leaving a static visual beside changing widgets.

For a long-form grouped chart, use the persisted grouping column as both the
categorical filter `field` and the chart grouping mapping (`color`, or
`category` for pie/donut). Wide-form series names are columns, not row values;
reshape wide data to long form before offering a series-selection filter.
Filtering a `data_grid` happens before virtualization. Any active user sort is
preserved and recomputed on the filtered rows, then the grid resets to the
first `page_size` rows of that filtered-then-sorted result.

## Linked charts

The closed sync-mode enum is:

`axis`, `tooltip`, `legend`, `dataZoom`

```python
{
    "group": "rates_sync",
    "members": ["curve", "spread", "vol"],
    "sync": ["axis", "tooltip", "dataZoom"],
}
```

| Mode | Effect |
|---|---|
| `axis` | Shared pointer/axis position |
| `tooltip` | Coordinated tooltips |
| `legend` | Shared series visibility state |
| `dataZoom` | Shared window across member charts that already have data zoom |

All members must be chart ids with compatible domains and semantics. The link does not enable data zoom; use the supported chart contract in [charts.md](charts.md#presentation).

The closed brush-type enum is:

`rect`, `polygon`, `lineX`, `lineY`

```python
{
    "group": "rates_brush",
    "members": ["curve", "spread"],
    "brush": {"type": "lineX", "xAxisIndex": 0},
}
```

Use `lineX` for time windows, `lineY` for value bands, `rect` for bounded x/y selection, and `polygon` for exploratory point selection.

## Click-to-filter

A chart widget emits one categorical value into an existing `select` or `radio` filter:

```python
{
    "widget": "chart",
    "id": "sector_weights",
    "click_emit_filter": {
        "filter_id": "sector",
        "value_from": "name",
        "toggle": True,
    },
    "spec": {
        "chart_type": "donut",
        "dataset": "sector_weights",
        "mapping": {"category": "sector", "value": "weight_pct"},
    },
}
```

`filter_id` must resolve to a declared `select` or `radio` filter. `value_from` is one of `name`, `value`, or `seriesName` and selects the corresponding ECharts click-event field. `toggle` must be boolean; when true, clicking the currently emitted value again clears the target filter to its `all_value` or empty state. The emitted value must be one of the target filter's option values. `multiSelect` is not a legal target.

## Conditional visibility

`show_when` has three distinct forms:

```python
# Compile-time row existence
{"data": "scenario_rows"}

# Compile-time scalar threshold
{"data": "risk.latest.vix", "op": ">", "value": 25}

# Runtime filter state
{"filter": "scope", "value": "global"}
```

The scalar data source is exactly `<dataset>.<aggregator>.<column>`, where the aggregator is `latest`, `first`, `sum`, `mean`, `min`, `max`, `count`, or `prev`. Its `op` is one of `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`, `in`, or `not_in`; `value` is required. The row-existence form names only a dataset and is true when it has at least one row. Data conditions resolve during compilation and may remove a widget; filter conditions remain for runtime evaluation. Compose clauses with `{"all": [...]}` or `{"any": [...]}`. Every dataset, column, aggregator, operator, and filter id must resolve.

## Filter operations

Add:

```python
{
    "op": "add_filter",
    "filter": {
        "id": "lookback",
        "type": "dateRange",
        "default": "5Y",
        "field": "date",
        "targets": ["curve"],
    },
}
```

Update:

```python
{
    "op": "update_filter",
    "selector": {"id": "lookback"},
    "patch": {"default": "10Y"},
}
```

Remove only with explicit destructive intent:

```python
{"op": "remove_filter", "selector": {"id": "lookback"}}
```

See [template_crud.md](template_crud.md#filter-operations) for transactional semantics.

## Interaction judgment

- A control must change a meaningful decision surface.
- Defaults must render a coherent initial view.
- Fields, targets, options, dependencies, and rule leaves must resolve after refresh.
- Link only charts whose axes/series represent comparable states.
- Preserve unrelated controls and links during targeted edits.
