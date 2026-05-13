# Filters + linking (sync, brush)

Spoke fetched on demand from the dashboards hub. Covers all 10 filter types, cascading filters, in-chart `dataZoom`, click-to-filter wiring, compound rule filters, and chart-to-chart links (sync + brush).

---

## 1. Filter shape

```json
{"id": "region", "type": "multiSelect", "default": ["US", "EU"],
  "options": ["US", "EU", "JP", "UK"],
  "targets": ["*"], "field": "region", "label": "Region"}
```

`options` can also be `{value, label}` dicts when visible text differs from underlying value.

### 1.1 Types and fields

**Ten filter types:**

| Type | UI | Applies to |
|------|-----|-----------|
| `dateRange` | select 1M/3M/6M/YTD/1Y/2Y/5Y/All | Charts (view-mode default): sets initial `dataZoom` window. Tables/KPIs/stat_grids: row-filters `rows[field]`. `mode: "filter"` row-filters charts too |
| `select` | `<select>` | `rows[field] == value` |
| `multiSelect` | `<select multiple>` | `rows[field] in [values]` |
| `radio` | radio button group | same as `select`, different UI |
| `numberRange` | text `min,max` | `min <= rows[field] <= max` |
| `slider` | range input + value | `rows[field] op value` (op defaults `>=`) |
| `number` | number input | `rows[field] op value` (op defaults `>=`) |
| `text` | text input | `rows[field] op value` (op defaults `contains`) |
| `toggle` | checkbox | `rows[field]` truthy when checked |
| `rule` | enable-chip + popup tree | nested AND/OR/NOT row-evaluator, see §5 |

**`dateRange` semantics on charts.** Time-series charts ship with their own `dataZoom` (§3). A `dateRange` filter is a global "initial lookback" knob, not a data filter — changing the dropdown moves every targeted chart's visible window via `dispatchAction({type:'dataZoom'})` and leaves the underlying dataset untouched. Tables / KPIs / stat_grids targeted by the same filter still see real row-filtering. Pass `"mode": "filter"` to force row-filter on charts (e.g. histograms / aggregates that must recompute over the window).

**Fields:**

| Field | Purpose |
|-------|---------|
| `id` / `type` (req) | Unique id; one of the 10 types above |
| `default` / `label` | Initial value; display label |
| `field` | Dataset column to filter against |
| `op` | `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith` |
| `transform` | `abs` / `neg` applied to cell before compare (e.g. `\|z\|` filters) |
| `options` | Required for select/multiSelect/radio. List of primitives OR `{value, label}` dicts |
| `min` / `max` / `step` | Required for slider; optional for number |
| `placeholder` / `all_value` | Placeholder text; "no filter" sentinel (`"All"`, `"Any"`) |
| `targets` | List of widget ids to refresh. `"*"` = all data-bound. Wildcards: `"prefix_*"`, `"*_suffix"` |
| `description` (aliases `help`, `info`) / `popup` | Help text + info icon; `{title, body}` markdown popup for click |
| `scope` | `"global"` (top filter bar) or `"tab:<id>"` (inline). Auto-inferred from targets |

**Filter placement is auto-scoped.** Filters targeting multiple tabs or `"*"` go in the global bar; filters whose targets all resolve to a single tab go in a tab-inline bar. Override with explicit `scope`.

**Which chart types reshape on filter change.** Auto-wire happens for `line` / `multi_line` / `bar` / `area` with simple wide-form mapping (no `color` long-form, no `stack`, no `trendline`). Tables, KPIs, stat_grids, and chart types with computed series data (histograms, bullets, candlesticks, heatmaps, scatter-with-trendline, radar, gauge, sankey, treemap, sunburst, funnel, parallel_coords, tree, graph, boxplot) keep their baseline data.

---

## 2. Cascading filters (`depends_on` + `options_from`)

A filter declares `depends_on: <upstream_filter_id>` + `options_from: {dataset, key, where?}`. When the upstream changes, the dependent rebuilds options from the named dataset, optionally filtered by `where` substituting upstream values via `${filter_id}`.

```python
"filters": [
    {"id": "region", "type": "select", "label": "Region", "default": "NA",
      "options": ["NA", "EU", "AP"], "field": "region", "targets": ["country_view"]},
    {"id": "country", "type": "select", "label": "Country",
      "depends_on": "region",
      "options_from": {"dataset": "universe", "key": "country",
                         "where": "region == ${region}"},
      "options": ["US"], "field": "country", "targets": ["country_view"]},
    {"id": "ticker", "type": "select", "label": "Ticker",
      "depends_on": "country",
      "options_from": {"dataset": "universe", "key": "ticker",
                         "where": "country == ${country}"},
      "options": [""], "field": "ticker", "targets": ["country_view"]}]
```

Supported `where` ops: `==`, `!=`, `>`, `>=`, `<`, `<=`. Dependent filter's existing value is preserved when valid in the new option set; otherwise falls back to first new option (or empty for `multiSelect`). Cascades chain: when region changes, both country and ticker rebuild in dependency order.

---

## 3. Per-chart zoom (in-chart `dataZoom`)

Every chart with `time` x-axis ships with two `dataZoom` controls injected at compile time (independent of any `dateRange` filter): `type: "inside"` (mouse wheel / pinch zoom + click-and-drag pan) and `type: "slider"` (draggable slider beneath the grid). Full dataset embedded; slider clips visible window. `grid.bottom` auto-bumps. Builders that already declared their own `dataZoom` (e.g. candlestick) are left alone.

The injected zoom is **per-chart and local by default** — dragging the slider on one chart does not move sibling charts. To propagate drags across charts, author a `Link` with `sync: ["dataZoom"]` (§6); a `dateRange` global filter dropdown also moves every targeted chart. Slider tick label format is auto-selected from the data span (no author knob).

`chart_zoom` value:

| Form                                | Result                                                       |
|-------------------------------------|--------------------------------------------------------------|
| `true` / unset                      | Both inside + slider injected (default)                      |
| `false`                             | Nothing injected — sparkline mode                            |
| `{"slider": true, "inside": false}` | Slider only (chart inside-pan would steal page-scroll)       |
| `{"slider": false, "inside": true}` | Inside only (cramped tile, slider clutters)                  |
| `{"slider": false, "inside": false}`| Equivalent to `false`                                        |

`spec.chart_zoom` and `mapping.chart_zoom` both work; `spec.chart_zoom` wins when both are set.

```json
{"widget": "chart", "id": "tiny_sparkline", "w": 4,
  "spec": {"chart_type": "line", "dataset": "rates",
            "mapping": {"x": "date", "y": "us_2y"}, "chart_zoom": false}}

{"widget": "chart", "id": "intraday_compact", "w": 4,
  "spec": {"chart_type": "multi_line", "dataset": "rates_intraday",
            "mapping": {"x": "timestamp", "y": ["us_2y", "us_10y"]},
            "chart_zoom": {"slider": false}}}
```

---

## 4. `click_emit_filter`

Turn a data-point click on one chart into a filter change driving downstream widgets:

```json
"click_emit_filter": "sector_filter"

"click_emit_filter": {
    "filter_id": "sector_filter",
    "value_from": "name",     // "name" (default) | "value" | "seriesName"
    "toggle": true              // re-clicking same value clears (default true)
}
```

`filter_id` must reference a `select` or `radio` filter whose `targets` point at the widgets to re-render. Click-through navigation pattern: click sector slice on a donut → filter screener table to that sector.

---

## 5. Compound rule filters (`type: "rule"`)

Flat filters always AND together. When the screen needs OR or NOT — e.g. "investment-grade AND ((rich AND tight) OR (financial AND short-duration))" — declare a `rule` filter whose body is a nested all/any/not tree:

```json
{"id": "screen", "type": "rule", "label": "Compound screen",
  "summary": "rating + (rich-tight OR short-fin)",
  "targets": ["bond_table"],
  "rule": {
    "all": [
      {"field": "rating", "op": "in",
        "value": ["AAA", "AA", "A", "BBB"]},
      {"any": [
        {"all": [
          {"field": "ytm_pct",   "op": ">", "value": 4.5},
          {"field": "spread_bp", "op": "<", "value": 200}
        ]},
        {"all": [
          {"field": "sector",       "op": "in", "value": ["Financials", "Banks"]},
          {"field": "duration_yrs", "op": "<",  "value": 5.0}
        ]}
      ]}
    ]
  }}
```

The chip on the filter bar shows the rule's label + summary + an info icon that opens the full tree as a markdown popup. The checkbox toggles the rule on/off in one click; default is on.

**Grammar.** Each rule node is exactly one of:

| Shape | Meaning |
|-------|---------|
| `{"all": [<rule>, ...]}` | AND of children. At least one child required |
| `{"any": [<rule>, ...]}` | OR of children. At least one child required |
| `{"not": <rule>}` | NOT of single child |
| `{"field": ..., "op": ..., "value": ...}` | Leaf comparison against a row cell |

Mixing boolean keys with leaf keys in the same node is rejected. Multiple boolean keys in the same node is rejected. Nesting deeper than 12 levels is rejected (runaway-nesting guard).

**Leaf ops.** All `VALID_FILTER_OPS`: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`, plus the rule-specific `in` and `not_in` (value must be a non-empty list). Default op is `==`. Comparison semantics mirror the flat filter ops (numeric coercion, case-insensitive substring for `contains` etc.).

**Composition with flat filters.** A `rule` filter coexists with the 9 flat filter types — every targeted widget AND-intersects all applicable filters (rule + flats). Multiple rule filters on the same dashboard also AND together. Use a `rule` for the load-bearing screen logic; layer flat filters on top for live one-axis adjustments (sector multiSelect, search box, slider).

**Fields:**

| Field | Purpose |
|-------|---------|
| `id` / `type: "rule"` | Unique id; type literal |
| `rule` | Required. The all/any/not tree |
| `label` | Display text on the chip |
| `summary` | Short subtitle next to label (defaults to "<N> condition(s)") |
| `default` | `true` (default) renders the chip checked; `false` renders unchecked |
| `targets` | Widget ids the rule filters; same semantics as flat filters |
| `description` / `popup` | Optional alt-text and override popup body for the info icon |

The runtime walks the tree per row using a small JS evaluator. Performance is `O(rows × leaves)` — fine for the ~10k-row universes the dashboard system targets today.

---

## 6. Links (sync + brush)

```json
"links": [
    {"group": "sync", "members": ["curve", "spread"],
      "sync": ["axis", "tooltip", "dataZoom"]},
    {"group": "brush", "members": ["curve", "spread"],
      "brush": {"type": "rect", "xAxisIndex": 0}}
]
```

`sync` values: `axis`, `tooltip`, `legend`, `dataZoom`. At load, runtime sets `chart.group = group` and calls `echarts.connect(group)`.

`sync: ["dataZoom"]` is the **only** mechanism that mirrors a slider drag live across charts — without an explicit Link the in-chart zoom is always local (§3). Use it sparingly: it's the right call when a panel is comparing the same window across several series (curve / spread / vol on aligned dates) and the wrong call when each chart is independently navigable.

`brush.type`: `rect`, `polygon`, `lineX`, `lineY`. When user brushes on any member chart, runtime extracts `coordRange`, filters linked charts' datasets to brushed range on x axis, re-renders all linked charts. Clearing brush resets dataset.

`members` accepts widget ids or wildcards.
