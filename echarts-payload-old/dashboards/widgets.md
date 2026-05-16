# Widgets (KPI, table, pivot, stat_grid, image, markdown, divider)

Spoke fetched on demand from the dashboards hub. Covers every non-chart, non-tool widget kind. For chart specs (`widget: chart`), fetch `charts.md`. For the tool widget (`widget: tool`), fetch `widget_tool.md`.

---

## 1. Catalog + presentation knobs

| Widget | Required | Purpose |
|--------|----------|---------|
| `chart` | `id`, one of `spec` / `ref` / `option` | ECharts canvas tile (see `charts.md`) |
| `kpi` | `id`, `label` | Big-number tile + delta + sparkline |
| `table` | `id`, `ref` or `dataset_ref` | Rich table with sort / search / format / popup |
| `pivot` | `id`, `dataset_ref`, `row_dim_columns`, `col_dim_columns`, `value_columns` | Crosstab with row/col/value/agg dropdowns (§6) |
| `stat_grid` | `id`, `stats[]` | Dense grid of label/value stats |
| `image` | `id`, `src` or `url` | Embed static image or logo |
| `markdown` | `id`, `content` (or `body`) | Freeform markdown. Optional `kind` ∈ {insight, thesis, watch, risk, context, fact} renders as a tinted semantic card with coloured left-edge stripe (§8) |
| `divider` | `id` | Horizontal rule, forces row break |
| `tool` | `id`, `tool_def` | Interactive form -> compute -> output (see `widget_tool.md`) |

`widget: "note"` is a back-compat alias for `widget: "markdown"` with an implicit `kind: "insight"`; both go through the same renderer (§8).

Common optional fields: `w` (1-12 grid span), `h_px` (chart only; default 280), `title`, `show_when` (§10).

**Widget presentation knobs** (every tile type):

| Field | Purpose |
|-------|---------|
| `title` / `subtitle` | Card header at widget level (never in `spec`). Italic secondary line. PNG export bakes title in |
| `footer` (alias `footnote`) | Small text below tile body, dashed-border separator. Source attribution |
| `info` / `popup` | Short help (info icon: hover tooltip + click modal). `popup: {title, body}` markdown overrides modal content |
| `badge` / `badge_color` | Short pill (1-6 chars) next to title; color ∈ `"gs-navy"` (default) / `"sky"` / `"pos"` / `"neg"` / `"muted"` |
| `emphasis` / `pinned` | Thicker navy border + shadow (KPIs: sky-blue top border) / sticky to viewport top |
| `action_buttons` | List of toolbar buttons: `{label, icon?, href?, onclick?, primary?, title?}` |
| `click_emit_filter` (chart) | Data-point clicks → filter changes (see `filters.md`) |
| `click_popup` (chart) | Data-point clicks → per-row detail popup. Same grammar as table `row_click` (§3) |

```json
{"widget": "chart", "id": "price_chart", "w": 6, "h_px": 440,
  "title": "ACME daily OHLC (1Y)", "badge": "LIVE", "badge_color": "pos",
  "info": "Daily OHLC. Drag the brush at the bottom to zoom.",
  "footer": "Source: GS Market Data. Updated at market close.",
  "action_buttons": [{"label": "Open in portal", "href": "https://example.com/acme"}],
  "spec": {"chart_type": "candlestick", "dataset": "ohlc",
            "mapping": {"x": "date", "open": "open", "close": "close",
                        "low": "low", "high": "high"}}}
```

Chart widgets are never full-width — pair with a volume chart, RSI panel, or stat strip on the right half of the row. The hub's layouts section has the chart-width rule.

---

## 2. KPI

**Source path syntax.** `source` (and `delta_source`) use `<dataset>.<aggregator>.<column>`. `sparkline_source` drops the aggregator: `<dataset>.<column>`. Aggregators: `latest` / `first` / `sum` / `mean` / `min` / `max` / `count` / `prev`.

For time-series datasets:
- `rates.latest.us_10y` — last numeric value
- `rates.prev.us_10y` — second-to-last (drives delta vs prev)

For categorical / summary datasets, source paths still work but the aggregator collapses N rows to one — rarely what you want. Either pivot to a single-row "latest" snapshot, or skip `source` and pass `value` directly:

```python
{"widget": "kpi", "id": "kpi_aapl", "label": "AAPL NTM EPS", "value": 8.98, "w": 3}
```

| Key | Purpose |
|-----|---------|
| `value` / `source` | Direct override; or dotted `<dataset>.<agg>.<column>` |
| `sub` | Subtext under the value |
| `delta` / `delta_source` / `delta_pct` | Direct delta or dotted source (delta = current − prev); `delta_pct` auto-computed from `delta_source` if absent |
| `delta_label` / `delta_decimals` | Label after delta / precision (default 2; clamped to global cap) |
| `prefix` / `suffix` / `decimals` | Prepended / appended (`$`, `%`, `bp`); precision (default 2 for <1000, else 0; clamped) |
| `sparkline_source` | Dotted: `<dataset>.<column>` for inline sparkline (no aggregator) |
| `format` | `"auto"` (default; `2820` → `2,820`), `"compact"` (K/M/B/T), `"comma"`, `"percent"`, `"raw"` |
| `sense_check` | Bool, default `True`. Compile prints every resolved KPI value and fires a `kpi_value_sense_check` warning when `|value| > 20` so the headline number gets a second look. Set `False` only after confirming the number AND the concept are correct (S&P 4500, VIX 25, probability=68%). Hub §0 Rule 1 has the full discipline. |

```json
{"widget": "kpi", "id": "k10y", "label": "10Y", "w": 3,
  "source": "rates.latest.us_10y", "suffix": "%",
  "delta_source": "rates.prev.us_10y", "delta_label": "vs prev",
  "sparkline_source": "rates.us_10y"}
```

---

## 3. Table

Pass `dataset_ref` and the table renders every column by default. For production dashboards, declare `columns[]` for per-column labels, formatters, tooltips, conditional formatting, color scales, plus search / sort / row-click popups.

```json
{"widget": "table", "id": "rv_table", "w": 12, "dataset_ref": "rv",
  "title": "RV screen (click a row for detail)",
  "searchable": true, "sortable": true,
  "max_rows": 50, "row_height": "compact",
  "empty_message": "No metrics match the current filters.",
  "columns": [
    {"field": "metric", "label": "Metric", "align": "left"},
    {"field": "current", "label": "Current", "format": "number:2", "align": "right"},
    {"field": "z", "label": "Z", "format": "signed:2", "align": "right",
      "color_scale": {"min": -2, "max": 2, "palette": "gs_diverging"}},
    {"field": "pct", "label": "Pctile", "format": "percent:0", "align": "right",
      "conditional": [
        {"op": ">=", "value": 0.85, "background": "#c53030", "color": "#fff", "bold": true},
        {"op": "<=", "value": 0.15, "background": "#2b6cb0", "color": "#fff", "bold": true}]}],
  "row_click": {"title_field": "metric",
                "popup_fields": ["metric", "current", "z", "pct", "note"]}}
```

**Per-column fields:**

| Key | Purpose |
|-----|---------|
| `field` (req) / `label` | Column name in dataset; header label (defaults to field) |
| `format` | `text` / `number[:d]` / `integer` / `percent[:d]` / `currency[:d]` / `bps[:d]` / `signed[:d]` / `delta[:d]` / `date` / `datetime` / `link`. The `:d` suffix is clamped to the global cap |
| `align` / `sortable` / `tooltip` | `left` / `center` / `right` (auto-right for numeric); defaults to table-level; hover text |
| `conditional` | First-match-wins rules: `{op, value, background?, color?, bold?}` (op from filter ops set) |
| `color_scale` | Continuous heatmap: `{min, max, palette}` (`gs_diverging` / `gs_blues`) |
| `in_cell` | `"bar"` (proportional bar inside cell, anchored at zero when col crosses zero) or `"sparkline"` (inline 80×16 SVG, requires `from_dataset` + `row_key` + `filter_field`; optional `value`, `show_text: false`) |

**Table-level fields:** `searchable`, `sortable`, `downloadable` (XLSX button; default `true`), `row_height` (`compact` / default), `max_rows` (default 100), `empty_message`.

**Row-level highlighting** (`row_highlight`): list of rules evaluated per row; first match wins. `{field, op, value, class}` where `op` ∈ `==, !=, >, >=, <, <=, contains, startsWith, endsWith` and `class` ∈ `"pos"` / `"neg"` / `"warn"` / `"info"` / `"muted"`. Row gets tinted background + left-edge accent.

### `row_click` and chart `click_popup` — same grammar

Two modes: simple (key/value table) or rich drill-down (mini-dashboard inside the modal).

*Simple:*

```json
"row_click": {"title_field": "ticker", "popup_fields": ["ticker", "sector", "last", "d1_pct"]}
```

*Rich drill-down* — modal widens to 880px when `detail.wide: True`:

```json
"row_click": {
  "title_field": "issuer",
  "subtitle_template": "CUSIP {cusip} - {coupon_pct:number:2}% coupon - matures {maturity}",
  "detail": {"wide": true, "sections": [
    {"type": "stats", "fields": [
      {"field": "price", "label": "Price", "format": "number:2"},
      {"field": "ytm_pct", "label": "YTM", "format": "number:2", "suffix": "%"}]},
    {"type": "markdown", "template": "**{issuer}** - rated `{rating}`."},
    {"type": "chart", "title": "Price history (180 biz days)",
      "chart_type": "line", "dataset": "bond_hist",
      "row_key": "cusip", "filter_field": "cusip",
      "mapping": {"x": "date", "y": "price"}, "height": 220},
    {"type": "table", "title": "Recent events", "dataset": "bond_events",
      "row_key": "issuer", "filter_field": "issuer", "max_rows": 6,
      "columns": [{"field": "date"}, {"field": "event"}]}]}}
```

**Section types inside `detail.sections`:**

| Type | Purpose |
|------|---------|
| `stats` | Dense KPI-style row. `fields[]`: string OR `{field, label, format, prefix, suffix, sub, signed_color}` |
| `markdown` | Paragraph with `{field}` / `{field:format}` template substitution. Full markdown grammar (§9) |
| `chart` | Embedded mini-chart. `chart_type` ∈ `line` / `bar` / `area`; dataset + `filter_field` / `row_key` to scope. Supports `mapping.y` (col or list), `annotations`, numeric `height` |
| `table` | Sub-table from filtered manifest dataset. `max_rows` caps length |
| `kv` / `kv_table` | Key/value table for subset of `row` fields |

Template substitution `{field:format}` matches column formats (`number:N`, `signed:N`, `percent:N`, `currency:N`, `bps:N`, `delta:N`, `date`). Unknown fields pass through.

**Chart `click_popup`** uses identical grammar. Click any point in scatter / line / bar / area / candlestick / bullet / pie / donut / funnel / treemap / sunburst / heatmap / calendar_heatmap → corresponding row opens in the same modal grammar.

**Row resolution** (chart click → dataset row):

| Chart type | params → row |
|------------|--------------|
| line / multi_line / area / bar / bar_horizontal / scatter / scatter_multi / candlestick / bullet | `rows[dataIndex]` of (filter-stripped) dataset; with `mapping.color`, filter by `color_col == params.seriesName` first |
| pie / donut / funnel / treemap / sunburst | match `mapping.category` / `mapping.name` cell `== params.name` |
| heatmap / calendar_heatmap | reconstruct unique x/y categories and match pair / match `mapping.date` cell `== params.value[0]` |
| histogram / radar / gauge / sankey / graph / tree / parallel_coords / boxplot | not row-resolvable; click is a no-op |

**Popup chart capabilities (subset of inline).** The chart inside a `detail.sections[type=chart]` (or chart `click_popup`) renders in a modal canvas with fewer interactive controls than an inline chart. Today's allow-list:

| Feature | Inline | Popup |
|---|---|---|
| `chart_type` ∈ `line` / `bar` / `area` / `multi_line` | yes | yes |
| Other chart types | yes | no |
| `mapping.y` (single col or list) | yes | yes |
| `annotations` (hline / vline / band / arrow / point) | yes | yes |
| Series legend with click-to-toggle visibility | yes | no |
| MA overlay via `initial_state.smoothing` | yes | no |
| `chart_zoom` slider / inside | yes | no |
| `click_emit_filter` / nested `click_popup` | yes | no |
| Brush / sync linkage via `links[]` | yes | no |

When the user asks for interactive controls inside the popup (series toggle, MA overlay, brush, dataZoom) and the engine cannot render them, surface the limitation upfront. Two clean fallbacks: (a) inline the charts in a row instead of nesting in a popup, (b) ship a simpler popup with static series and route the interactive view to a sibling inline chart. Do not author a popup spec with a feature outside the allow-list and report success.

**Filter scoping for popup charts.** A popup chart's dataset MUST contain a column named `filter_field` whose values match the parent row's `row_key` cell. If the dataset has only `(date, val)` columns and the popup tries `filter_field: metric`, the popup renders empty. Verify at build time before authoring the manifest: load the dataset, run `df[df[filter_field] == row_key].head()`, and require `len(rows) > 0`. Empty popup charts silently shipped to the user is the canonical row_click failure mode — catch it pre-author.

---

## 4. Provenance

Every line / bar / point / row / cell carries the upstream identifier plus source system. The compiler does NOT introspect `df.attrs`; PRISM cleans upstream metadata into the canonical shape and passes it explicitly. Vendor-agnostic — the renderer treats `system` as opaque, so adding a new data source is one PRISM-side adapter (~10 lines), no echarts code change.

**The contract:** attach `field_provenance` (and optionally `row_provenance_field` + `row_provenance` for mixed-vendor columns) alongside `source`.

```python
manifest["datasets"]["rates"] = {
    "source": df_rates,
    "field_provenance": {
        "UST10Y": {"system": "market_data", "symbol": "IR_USD_Treasury_10Y_Rate",
                    "tsdb_symbol": "ustsy10y", "display_name": "US 10Y Treasury Rate",
                    "units": "percent", "source_label": "GS Market Data"},
        "JCXFE":  {"system": "haver", "symbol": "JCXFE@USECON",
                    "haver_code": "JCXFE@USECON", "units": "percent",
                    "source_label": "Haver Economics"},
        "us_2s10s": {"system": "computed", "recipe": "UST10Y - UST2Y",
                      "computed_from": ["UST10Y", "UST2Y"], "units": "bp"}}}
```

**Per-column keys** (`system` and `symbol` always populate; rest optional, all free-form strings):

| Key | Purpose |
|-----|---------|
| `system` | Source slug: `haver`, `market_data`, `plottool`, `fred`, `bloomberg`, `refinitiv`, `factset`, `csv`, `computed`, `manual`, or any string PRISM picks for a new vendor. Renderer treats as opaque |
| `symbol` | Universal primary identifier — pass the exact upstream string (`GDP@USECON`, `IR_USD_Treasury_10Y_Rate`, `DGS10`, `USGG10YR Index`, `AAPL-US.GAAP.EPS_DILUTED`) |
| `display_name` / `units` / `source_label` | Human-readable footer label; `percent` / `bp` / etc.; vendor attribution |
| `recipe` / `computed_from` | For `system: "computed"`: free-form formula + list of source columns referenced |
| `as_of` | ISO timestamp of latest tick at column level |
| `<vendor_alt>` | System-specific alternate id: `haver_code`, `tsdb_symbol`, `fred_series`, `bloomberg_ticker`, `refinitiv_ric`, `factset_id` |

**Mixed-vendor columns** (one column, different upstream per row) override per row via `row_provenance_field` + `row_provenance`:

```python
{"source": df_screener,
 "field_provenance": {"last": {"system": "market_data", "source_label": "GS Market Data"}},
 "row_provenance_field": "ticker",
 "row_provenance": {
    "AAPL": {"last": {"system": "market_data", "symbol": "EQ_US_AAPL_Last"}},
    "TSLA": {"last": {"system": "bloomberg", "symbol": "TSLA US Equity"}}}}
```

**Where it surfaces:** auto-default popup when `field_provenance` is set but no `click_popup` / `row_click` declared (minimal modal + Sources footer); Sources footer auto-appended to every explicit popup (suppress per popup with `show_provenance: false`); inline source line under `detail.sections[type=stats]` via `show_source: true`. Opt-out per widget: `click_popup: false` / `row_click: false`.

PRISM rule: every dataset backing a chart or table carries `field_provenance`.

---

## 5. stat_grid

Dense grid of label / value stats — for when a row of KPIs would take too much vertical space.

```json
{"widget": "stat_grid", "id": "summary", "w": 12, "title": "Risk summary",
  "stats": [
    {"id": "s1", "label": "Beta to SPX", "value": "0.82", "sub": "60D", "trend": 0.04,
      "info": "OLS beta of book P&L vs S&P 500 TR, trailing 60 biz days."},
    {"id": "s2", "label": "Duration", "value": "4.8y", "sub": "DV01 $280k"},
    {"id": "s3", "label": "Gross leverage", "value": "2.3x", "sub": "vs 3.0x cap", "trend": 0.1},
    {"id": "s4", "label": "HY OAS", "value": "285 bp", "sub": "z = -1.1", "trend": -0.05}]}
```

| Field | Purpose |
|-------|---------|
| `id` / `label` / `sub` | Optional DOM id; title line (small caps, dim); secondary caption |
| `value` / `source` | Pre-formatted (no number formatting applied) OR dotted `<dataset>.<agg>.<column>` |
| `info` (alias `description`) / `popup` | Hover tooltip + click modal; `{title, body}` markdown popup |
| `trend` | Optional numeric delta. Positive = green up, negative = red down |
| `sense_check` | Bool, default `True`. Per-stat. Same semantics as KPI's `sense_check` — compile prints every resolved stat value and fires `stat_grid_value_sense_check` when `|value| > 20`. Set per-stat (not per-widget) to acknowledge legitimately-large items (HY OAS 285bp, VaR $18m) one at a time. |

---

## 6. Pivot

Long-form dataset → interactive crosstab. Viewer picks row dim, col dim, value column, aggregator from author-supplied whitelists.

```python
{"widget": "pivot", "id": "perf_pivot", "w": 12,
  "title": "Sector × window perf", "subtitle": "Drag the dropdowns to repivot.",
  "dataset_ref": "perf_long",
  "row_dim_columns": ["sector", "country", "ticker"],
  "col_dim_columns": ["window"],
  "value_columns":   ["ret", "ret_pct"],
  "agg_options":     ["mean", "median", "sum", "min", "max", "count"],
  "row_default": "sector", "col_default": "window",
  "value_default": "ret", "agg_default": "mean",
  "decimals": 2, "color_scale": "diverging", "show_totals": True}
```

| Key | Required | Purpose |
|-----|----------|---------|
| `dataset_ref` | yes | Long-form dataset (one row per `(row_cat, col_cat, value)`) |
| `row_dim_columns` / `col_dim_columns` / `value_columns` | yes | Whitelists |
| `agg_options` | no | Default `["mean", "sum", "median", "min", "max", "count"]` |
| `row_default` / `col_default` / `value_default` / `agg_default` / `decimals` | no | Initial selections; cell precision (default 2; clamped) |
| `color_scale` / `show_totals` | no | `"sequential"` / `"diverging"` / `"auto"` (diverging when crosses 0) / `false`; row/col totals (recomputed, not summed; default `True`) |

Filters targeting `dataset_ref` flow through naturally. User's last selections survive URL state encoding (`#p.<id>.r=...&p.<id>.c=...`).

---

## 7. image / markdown / divider

```json
{"widget": "image", "id": "logo", "w": 3,
  "src": "https://.../gs_logo.png", "alt": "Goldman Sachs", "link": "https://..."}

{"widget": "markdown", "id": "md", "w": 12,
  "content": "### Method\nSynthetic UST panel. **Brush** the curve to cross-filter."}

{"widget": "divider", "id": "sep"}
```

The `markdown` widget renders as transparent prose by default. Set `kind` to one of `insight` / `thesis` / `watch` / `risk` / `context` / `fact` to render as a tinted semantic card with a coloured left-edge stripe instead — see §8.

---

## 8. Markdown with `kind` (semantic callout)

Set `kind` on a markdown widget when a paragraph is load-bearing — the thesis, the risk, the watch level. The widget body stays markdown; the renderer adds a tinted card with a coloured left-edge stripe and a kind-label header so the reader can scan for "this is the thesis" / "this is a risk" without reading prose.

Required: `id`, `content` (markdown — `body` also accepted as a legacy alias). Optional: `kind` ∈ `insight` / `thesis` / `watch` / `risk` / `context` / `fact`, `title`, `icon` (1-2 char glyph), `w` (default 12), `footer`, `popup`, `info`.

| Kind | Visual | Use for |
|------|--------|---------|
| `insight` | sky stripe + sky tint | Observation / "the lightbulb" |
| `thesis` | navy stripe + navy tint | Load-bearing claim of the dashboard |
| `watch` | amber stripe + amber tint | Levels / events to monitor |
| `risk` | red stripe + red tint | Downside / pain trades |
| `context` | grey stripe + grey tint | Background / setup info |
| `fact` | green stripe + green tint | Established / point-in-time facts |

```json
{"widget": "markdown", "id": "n_thesis", "w": 6,
  "kind": "thesis", "title": "Bull-steepener resumes",
  "content": "The curve is **bull-steepening** for the third session in a row.\n\n"
              "1. 2Y -6bp on the day, -18bp on the week\n2. 10Y -3bp on the day, -9bp on the week\n"
              "3. Spread widening primarily front-led, consistent with a *priced-in cut* trade"}
```

Pairing a `thesis` and `watch` markdown card in a 6/6 row at the top is high-leverage: load-bearing claim + "what would change my mind" criteria, before any chart loads.

`widget: "note"` is a back-compat alias accepted by the validator; persisted manifests written under the legacy two-widget contract still render. New manifests should emit `widget: "markdown"` with an explicit `kind`. Both routes go through the same renderer.

---

## 9. Markdown grammar (shared)

Same grammar applies to: `widget: markdown` (with or without `kind`), `metadata.summary`, `metadata.methodology`, `popup: {body}` on any tile / filter / stat, per-row `markdown` sections (§3). Tab `subtitle` / `description` is plain text, not markdown.

| Block | Syntax |
|-------|--------|
| Headings | `# H1` … `##### H5` (deeper clamped to h5) |
| Paragraph | Lines separated by blank line; lines within a para joined with single space |
| Unordered / ordered list | `-` or `*` (UL); `1.` / `2.` / … (OL; numbers don't have to be sequential) |
| Nested list | Indent by **2 spaces** per level. Mix `ul`/`ol` freely |
| Blockquote / code block | `> ...` (multi-line accumulates) / triple-backtick fenced (optional language tag) |
| Table | GFM: header row, separator `\| --- \| --- \|`, body rows. Alignment hints `:---` / `---:` / `:---:` |
| Horizontal rule | A line containing only `---`, `***`, or `___` |
| Inline | `**bold**` / `*italic*` / `~~strike~~` / `` `code` `` / `[label](url)` (opens in new tab) |

Anything that does not match is escaped as plain text — including raw HTML.

---

## 10. show_when, initial_state, stat strip

### `show_when` — conditional widget visibility

A widget can declare `show_when`; if it fails the widget is removed (compile-time data conditions) or hidden via CSS (runtime filter conditions).

- **Data condition** (compile-time) — `{"data": "<dotted_source> <op> <value>"}`. Source uses KPI dotted shape (`dataset.aggregator.column`); ops: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`. Widget removed from layout when condition fails.
- **Filter condition** (runtime) — `{"filter": "<filter_id>", "value": <v>}`, `{"filter": "<filter_id>", "in": [<v>, ...]}`, or `{"filter": "<filter_id>", "op": ">", "value": 25}`. JS toggles widget visibility on filter change.
- **Compound** — `{"all": [...]}` (AND), `{"any": [...]}` (OR). Mix data and filter clauses freely; compile-time pass evaluates only data sub-conditions.

```python
{"widget": "note", "id": "vol_warning", "kind": "risk",
  "body": "Vol regime elevated; tighten stops...",
  "show_when": {"data": "rates.latest.vix > 25"}}              # compile-time

{"widget": "chart", "id": "fed_path",
  "show_when": {"filter": "scope", "value": "domestic"}}        # runtime

{"widget": "pivot", "id": "global_pivot",
  "show_when": {"all": [{"data": "market.latest.vix < 30"},
                          {"filter": "scope", "in": ["us", "eu"]}]}}
```

### `initial_state` — seed the controls drawer

Every chart / table / KPI carries a controls drawer. `initial_state` seeds it so a chart opens in YoY % instead of raw levels (etc.) without an extra click. Mirrors drawer state shape; unknown keys are ignored.

```python
"spec": {"chart_type": "line", "dataset": "rates", "mapping": {"x": "date", "y": "us_10y"},
          "initial_state": {
              "transform": "yoy_pct", "smoothing": 5,
              "y_scale": "log", "y_range": "from_zero",
              "shape": {"lineStyleType": "dashed", "step": "middle",
                         "width": 2, "areaFill": True, "stack": "percent"},
              "series": {"us_10y": {"transform": "log", "visible": True}},
              "trendline": "linear", "color_scale": "diverging"}}

"spec": {"chart_type": "correlation_matrix", "dataset": "rates",
          "mapping": {"columns": ["us_2y", "us_5y", "us_10y", "us_30y"],
                       "transform": "raw", "order_by": "date"},
          "initial_state": {
              "corr_transform": "pct_change",
              "corr_window":    "63d",
              "corr_method":    "pearson"}}

{"widget": "table", "initial_state": {"search": "tech", "sort_by": "z", "sort_dir": "desc",
    "hidden_columns": ["legacy_col"], "density": "compact",
    "freeze_first_col": True, "decimals": 2}}

{"widget": "kpi", "initial_state": {"compare_period": "1m", "sparkline_visible": True,
    "delta_visible": True, "decimals": 1}}
```

### Auto stat strip (`Σ` button)

Every supported time-series chart (`line`, `multi_line`, `area`) gets a `Σ` button in its toolbar. The popup carries one row per visible series with current value, deltas at `1d` / `5d` / `1m` / `3m` / `YTD` / `1Y`, 1Y high-low range, 1Y percentile rank. Computed on-demand — always reflects current state including drawer transforms or filter state.

Format choice (bp / pct+abs / pp / arithmetic) follows `field_provenance.units`:

| units | delta format | example |
|-------|--------------|---------|
| `percent` / `pct` / `%` | bp arithmetic | `4.07%  Δ5d -6bp` |
| `bp` / `basis_points` | bp arithmetic | `-28bp  Δ5d +4bp` |
| `index` / `usd` / `eur` | pct + abs | `4,869  Δ5d +1.5% (+71)` |
| `z` / `zscore` / `sigma` | arithmetic | `1.8  Δ5d +0.6` |
| `pp` / `percentage_points` | pp arithmetic | `+18.4%  Δ5d +1.2pp` |
| (missing) | magnitude heuristic | falls back to pct |

Per-spec overrides: `"stat_strip": False` to suppress; or `"stat_strip": {"horizons": ["1d","5d","1m","YTD","1Y"], "delta_format": "bp", "show_range": True, "show_percentile": True}`. Σ button auto-suppressed for chart types where the strip doesn't apply.
