> IMPLEMENTATION DIRECTIVE: Open the live `prism-main` checkout and its checked-out
> `prism-core` submodule first. Inspect every production file and test named below,
> map this contract onto the live call graph, preserve unrelated work, implement the
> complete all-12 widget snapshot consumer, run the unit, integration, Playwright,
> owned/shared, and byte-parity gates, then update this handoff with the exact landed
> symbols and runnable test commands. Do not stop after analysis or planning.

# PRISM all-widget dashboard snapshot implementation handoff

## Current status and non-negotiable scope

Status as of 2026-07-20:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ ECharts neutral producer                                                │
│   █████  implemented and fully qualified locally                        │
│                                                                          │
│ prism-main all-12 consumer                                              │
│   ░░░░░  not implemented or verified by this workspace                  │
│                                                                          │
│ Installed prism-core byte parity                                        │
│   ░░░░░  not established; reconcile and measure before claiming it       │
│                                                                          │
│ Stage 3 typed-operation visual builder                                  │
│   ░░░░░  explicitly excluded                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

The last reviewed `prism-main` working-tree baseline had owner-only,
six-kind component drag, canonical component resolution, inlined prompt
bodies, Composer tabs/history/chat, and the dashboard-ready seam. That
review is not proof of the current live checkout. Re-open all live files
before editing and use their current symbols and call graph.

The build in this handoff is read-only component context:

```text
owner drags a top-level rendered widget
    → ECharts captures its bounded semantic current view at dragstart
    → Composer persists the immutable capture with the attachment card
    → fire-off or inline chat POST carries the capture inline
    → authenticated server resolves the current canonical widget
    → server validates identity, schema, bounds, and source authority
    → prompt contains canonical definition + captured current view
```

It is not dashboard editing. It adds no manifest mutation, layout mutation,
browser-side dashboard write, screenshot pipeline, HTML attachment, binary
file attachment, independent snapshot store, or snapshot endpoint.

### Exact draggable top-level kinds

The closed enum, in stable producer order, is:

```python
(
    "chart",
    "kpi",
    "table",
    "data_grid",
    "pivot",
    "stat_grid",
    "tool",
    "user_input",
    "markdown",
    "note",
    "image",
    "divider",
)
```

Only widgets directly under either of these layout locations are eligible:

```text
layout.rows[*][*]
layout.tabs[*].rows[*][*]
```

The following are excluded as independent drag sources:

```text
tabs
filters
layout groups and group children
popups and popup detail sections
chart series
table rows
stat cells
tool inputs and outputs
user-input files
every other nested leaf
```

A top-level snapshot may contain the visible/current state of nested content.
That does not make the nested content separately draggable.

### Stage 3 exclusions

Do not expose, call, or bridge these through Composer:

```text
describe_dashboard
apply_manifest_operations
review_dashboard
acknowledge_dashboard_review
publish_dashboard
launch_clean_refresh
```

Tile rearrangement, direct manifest writes, and a Django mutation bridge are
separate work and would need to preserve template SHA, version, review,
acknowledgment, publish, and clean-refresh semantics.

## Architecture and ownership boundary

```text
┌─────────────────────────────────────────────────────────────────────┐
│ prism-core/dashboards/rendering.py                                  │
│                                                                     │
│ TOP_LEVEL_WIDGET_META                                               │
│ WIDGET_SNAPSHOTTERS (all 12)                                        │
│ window.DASHBOARD.widgets                                            │
│ window.DASHBOARD.getWidgetSnapshot(widgetId)                        │
│ prism:dashboard:ready                                                │
│                                                                     │
│ Neutral producer only: no Composer MIME, routes, cards, or policy.   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ synchronous capture during dragstart
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ web/prism_site/js/dashboard_composer.js                             │
│                                                                     │
│ owner gate → natural handles / served-only grips                    │
│ capture → basic preflight → application/x-prism-artifact            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTML5 DataTransfer
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ web/prism_site/js/composer.js                                       │
│                                                                     │
│ card → tabs → local session → POST → history → replay               │
│ immutable snapshot transport; visible errors; no downgrade          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ artifact-info GET / submit POST
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ prism-main Django                                                   │
│                                                                     │
│ composer_artifacts.py         canonical resolve + purpose split      │
│ composer_dashboard_snapshot.py validation + deterministic merge      │
│ composer_views.py             POST preflight + aggregate gate        │
│ composer_prompt.py            shared inlined prompt framing          │
└─────────────────────────────────────────────────────────────────────┘
```

The ECharts payload produces bounded current-view evidence. `prism-main`
owns transport, authorization, canonical resolution, prompt framing,
Composer state, and errors. No Composer literal belongs in the ECharts
payload.

## Dependency, promotion, and enablement order

This order is load-bearing:

```text
1. Keep the canonical ECharts producer and producer tests green
                         ↓
2. Inspect prism-main and reconcile prism-core to the commit/gitlink
   recorded by prism-main
                         ↓
3. Promote the required canonical payload files into that reconciled
   prism-core checkout
                         ↓
4. Prove byte-for-byte parity between canonical payload and installed files
                         ↓
5. Implement and test prism-main validation, merge, transport, state, and grips
                         ↓
6. Enable the all-12 drag allowlist and run owned/shared browser smoke
```

Do not expand the live `dashboard_composer.js::ALLOWED_KINDS` before the
installed dashboard document exposes `getWidgetSnapshot` and the installed
`dashboards.echart_dashboard` exports `read_dashboard_user_input`.

### Canonical producer files

The authoritative producer files are:

```text
projects/echarts/echarts-payload/rendering.py
projects/echarts/echarts-payload/dashboard_user_input.py
projects/echarts/echarts-payload/echart_dashboard.py
projects/echarts/dev/tests.py
```

Promotion destinations:

```text
projects/echarts/echarts-payload/rendering.py
    → prism-core/dashboards/rendering.py

projects/echarts/echarts-payload/dashboard_user_input.py
    → prism-core/dashboards/dashboard_user_input.py

projects/echarts/echarts-payload/echart_dashboard.py
    → prism-core/dashboards/echart_dashboard.py
```

`rendering.py` and `dashboard_user_input.py` contain the landed producer
work. `echart_dashboard.py` did not require producer-specific behavior, but
its accepted `read_dashboard_user_input` export and call shape are part of
the consumer contract. Promote it if the reconciled live checkout lacks
that accepted helper. Never patch an installed payload file as an independent
source; change the canonical payload, qualify it, promote it, and re-check
bytes.

No installed-byte parity claim is valid until the `prism-core` checkout is
reconciled and the relevant source/destination files compare byte-identically.

## Live-first production file matrix

Inspect the current bodies, imports, tests, staged index, and working-tree
diff before changing anything.

### MODIFY

```text
web/prism_site/js/dashboard_composer.js
web/prism_site/js/composer.js
web/backend_django/news/composer_artifacts.py
web/backend_django/news/composer_prompt.py
web/backend_django/news/composer_views.py
web/backend_django/news/dashboard_composer.py
```

### CREATE

```text
web/backend_django/news/composer_dashboard_snapshot.py
```

### ADD OR UPDATE TESTS

```text
web/backend_django/news/tests/test_composer_dashboard_snapshot.py
web/backend_django/news/tests/test_composer_artifacts.py
web/backend_django/news/tests/test_composer_views.py
web/backend_django/news/tests/test_dashboard_composer.py
the live JavaScript/Playwright test surface covering dashboard Composer
```

Use the live test layout if filenames differ, but retain every assertion
listed in this handoff.

### VERIFY ONLY unless the live call graph proves a required change

```text
web/backend_django/news/views.py
web/backend_django/news/urls.py
web/backend_django/news/composer_email.py
web/prism_site/css/composer.css
web/prism_site/run.py
```

No `urls.py` change and no snapshot route are expected. The contract does
not require a generic `views.py` edit: `composer_views.py` is the required
POST path. Verify that:

- `views.py` already injects Composer on the served user-dashboard route
  and provides the canonical template hash;
- `urls.py` already exposes the existing Composer routes;
- `composer_email.py` remains a thin wrapper over the shared prompt builder;
- shared `composer.css` still provides the existing Composer error/card UI;
- `run.py` carries the intended `enable_inline_chat` product flag.

If a live dependency is absent, document the call-graph evidence before
changing a verify-only file. Do not create a snapshot GET/POST route.

## Neutral ECharts producer contract

### Public browser API

The installed compiled dashboard must expose:

```javascript
window.DASHBOARD.getWidgetSnapshot(widgetId)
```

This call is synchronous because `DataTransfer.setData(...)` must run inside
the browser's `dragstart` event. The function:

1. accepts one non-empty top-level widget id;
2. resolves only through `TOP_LEVEL_WIDGET_META`;
3. dispatches through `WIDGET_SNAPSHOTTERS`, whose keys exactly equal the
   12 widget kinds;
4. captures state at call time, after current filters, controls, sorting,
   search, pivot state, tool compute, and user-input loading;
5. JSON-normalizes dates, converts `undefined` and non-finite numbers to
   `null`, and rejects functions, symbols, bigints, and cycles;
6. bounds strings, collections, semantic partitions, and the final envelope;
7. throws for unknown top-level ids, unsupported kinds, unavailable required
   runtime caches, depth above 40, cycles, unsupported runtime values, or
   unstable/oversized final byte accounting.

The dashboard also exposes:

```javascript
window.DASHBOARD.widgets
```

and emits `prism:dashboard:ready` once after tool and user-input
initialization. Existing `window.DASHBOARD` fields must not be removed.

### Exact version-1 envelope

The producer returns exactly these ten top-level keys. Missing or unknown
envelope keys are invalid:

```json
{
  "snapshot_schema_version": 1,
  "widget_id": "divider",
  "widget_kind": "divider",
  "captured_at": "2026-07-20T17:52:31.123Z",
  "resolved_view": {"marker": "divider"},
  "view_state": {
    "rendered": true,
    "visible": true,
    "tab_id": null,
    "tab_active": true,
    "group_id": null,
    "group_open": null,
    "filters": {}
  },
  "source_refs": [],
  "truncation": {
    "truncated": false,
    "limits": {
      "component_bytes": 262144,
      "string_bytes": 32768,
      "table_rows": 500,
      "chart_points": 2000,
      "pivot_tool_cells": 2000
    },
    "omitted": {
      "rows": 0,
      "points": 0,
      "cells": 0,
      "strings": 0,
      "string_bytes": 0,
      "values": 0,
      "value_bytes": 0
    },
    "result_bytes": 601
  },
  "coverage": "full",
  "coverage_notes": []
}
```

Envelope semantics:

| Field | Exact contract |
|---|---|
| `snapshot_schema_version` | Integer `1`; booleans are not integers |
| `widget_id` | Non-empty top-level widget id |
| `widget_kind` | One exact lowercase 12-kind literal |
| `captured_at` | Browser `new Date().toISOString()` value |
| `resolved_view` | Kind-specific semantic current output |
| `view_state` | Common rendered/visibility/filter state plus kind state |
| `source_refs` | Encounter-ordered neutral reference records |
| `truncation.truncated` | True iff any omitted counter is non-zero |
| `truncation.limits` | Exact five names and values above |
| `truncation.omitted` | Exact seven names above; non-negative integers |
| `truncation.result_bytes` | Stabilized UTF-8 bytes of `JSON.stringify(envelope)` |
| `coverage` | Exactly `full`, `partial`, or `metadata_only` |
| `coverage_notes` | De-duplicated, encounter-ordered plain strings |

Any truncation forces `coverage: "partial"`. `metadata_only` is the
non-truncated `user_input` coverage because the browser intentionally omits
authoritative content.

The finalizer budgets the normalized partitions before assembly:

```text
resolved_view     156 KiB
view_state         48 KiB
source_refs         8 KiB
coverage_notes      8 KiB
complete envelope 256 KiB hard maximum
```

Omission fields mean:

```text
rows          table/data-grid rows omitted beyond 500
points        chart/tree/link or KPI sparkline points omitted beyond 2,000
cells         pivot cells or tool semantic leaves omitted beyond 2,000
strings       strings shortened at the 32 KiB retained-string limit
string_bytes  exact omitted UTF-8 string bytes
values        semantic values omitted by partition budgeting, plus
              non-finite values normalized to null
value_bytes   exact omitted value bytes from partition budgeting
```

String truncation keeps the longest Unicode-code-point prefix whose UTF-8
encoding is at most 32,768 bytes. It appends no ellipsis. Collections keep
source order. Generic coverage notes identify collection, string, and value
truncation; exact counts live in the omission ledger.

`truncation.result_bytes` is a fixed point: it is the byte length of the
complete serialized envelope containing that same result. The example's
measured value is 601.

### Neutral source-reference shapes

Every browser source reference begins with exactly `kind` and `ref`.
Supported landed shapes are:

```json
{"kind": "dataset", "ref": "rates"}
{"kind": "value_source", "ref": "rates.latest.us_10y"}
{"kind": "tool", "ref": "scenario_calculator"}
{"kind": "user_input", "ref": "knowledge_drop", "mode": "files"}
{"kind": "user_input_file", "ref": "file-id", "file_id": "file-id", "filename": "source.pdf"}
{"kind": "image", "ref": "https://example.test/image.png"}
{"kind": "link", "ref": "https://example.test/source"}
```

References are de-duplicated by exact `JSON.stringify(record)` while keeping
first encounter order. They are not sorted. Chart/table/pivot/stat/KPI refs
come from the top-level widget; tool refs carry the tool name/title; browser
user-input file refs carry only file id and filename.

A `data:` image is not transported. It produces partial coverage. No browser
reference may contain an object key, download URL, or bytes. The server treats
all producer refs as evidence and rebuilds canonical refs; user-input file
refs are replaced with authorized server refs.

### JSON and forbidden-key boundary

Reject these recursively everywhere:

```python
RECURSIVE_PROTOTYPE_KEYS = frozenset({
    "__proto__",
    "prototype",
    "constructor",
})
```

These authority/transport names are forbidden in control objects:

```python
FORBIDDEN_CONTROL_KEYS = frozenset({
    "canonical_definition",
    "definition",
    "manifest",
    "tool_def",
    "object_key",
    "download_url",
    "bytes",
    "file_bytes",
    "blob",
    "screenshot",
    "screenshot_data",
    "image_data",
    "data_url",
})
```

Apply the second set only to the envelope, truncation object, view state,
source-ref records, and structural control objects in `resolved_view`.
Do not globally blacklist valid domain fields. A table column named
`object_key`, chart datum field named `manifest`, or tool result field named
`definition` remains valid data. Such values still receive prototype-key,
JSON-type, finite-number, depth-40, string, and total-byte validation.

Data-bearing zones are:

```text
chart series[].data / links / mark data
KPI value / delta / sparkline points
table and data-grid columns / rows
pivot cell row / column / value fields
stat values
tool outputs / inputs
user-input metadata values
```

Everything else is a structural/control zone with exact allowed keys.

## Exact per-kind producer schemas and semantics

Every finalized `view_state` starts with:

```json
{
  "rendered": true,
  "visible": true,
  "tab_id": null,
  "tab_active": true,
  "group_id": null,
  "group_open": null,
  "filters": {}
}
```

`filters` contains current manifest-filter values whose empty targets or
target patterns apply to the widget. Kind-specific fields overlay this object.

The common server merge rule is:

```text
authenticated dashboard identity
    + current top-level widget from manifest_template.json
    + validated browser view_snapshot
    = prompt component body
```

The browser snapshot never becomes the canonical widget definition.

### `chart`

`resolved_view`:

```json
{
  "status": "ready",
  "title": "UST yields",
  "chart_type": "multi_line",
  "series": [
    {
      "name": "US 10Y",
      "type": "line",
      "data": [["2026-07-20", 4.25]],
      "stack": "total",
      "coordinate_system": "cartesian2d",
      "links": [],
      "mark_lines": [],
      "mark_areas": []
    }
  ],
  "total_point_count": 1
}
```

Each series always has `name`, `type`, and `data`. `stack`,
`coordinate_system`, `links`, `mark_lines`, and `mark_areas` are optional
and appear only when present in the live option. Object-form data is stripped
of visual-style keys. Tree children stay nested and count recursively.
Links share the 2,000-point budget.

Kind state:

```json
{
  "option_source": "live",
  "controls": {},
  "data_zoom": [
    {"start": null, "end": null, "start_value": null, "end_value": null}
  ],
  "legend_selected": {}
}
```

`option_source` is `live` or `materialized`. An unmounted materialized chart
adds a coverage note but remains `full` unless data is actually truncated.
The server rebuilds canonical dataset refs and never treats the option-derived
view as a widget definition.

### `kpi`

`resolved_view`:

```json
{
  "status": "ready",
  "label": "Latest 10Y",
  "value": 4.25,
  "formatted_value": "4.25",
  "delta": {
    "value": 0.03,
    "percent": 0.71,
    "label": "vs 1m",
    "formatted": "▲ 0.03 (+0.7%) vs 1m",
    "direction": "pos"
  },
  "sub": null,
  "sparkline_visible": true,
  "sparkline": {
    "columns": ["date", "value"],
    "points": [["2026-07-20", 4.25]],
    "total_point_count": 1
  }
}
```

`delta` is either null or exactly the five-field object shown.
Sparkline points use the 2,000-point cap and increment `omitted.points`.
Kind-state fields are:

```text
compare_period
sparkline_visible
delta_visible
decimals
```

The server rebuilds canonical `value_source` refs from `source`,
`delta_source`, and `sparkline_source`.

### `table` and `data_grid`

Both kinds use the same schema while retaining distinct `widget_kind` values.

```json
{
  "status": "ready",
  "columns": ["Name", "Value"],
  "rows": [["Alpha"]],
  "row_count": 1,
  "total_row_count": 1
}
```

`columns` and `rows` come from the existing table XLSX-export current-view
path, so they reflect search, filtering, sorting, hidden columns, and display
labels. `row_count` is retained rows; `total_row_count` is pre-truncation
rows. At most 500 rows survive, and:

```text
omitted.rows = total_row_count - row_count
```

Kind-state fields:

```text
search
sort_column_index
sort_direction
hidden_column_indexes
density
freeze_first_column
decimals
virtualized
```

Sort and hidden-column identities are numeric indexes, not field names.
The server rebuilds the canonical dataset ref.

### `pivot`

```json
{
  "status": "ready",
  "row_dimension": "region",
  "column_dimension": "bucket",
  "value_column": "amount",
  "aggregation": "mean",
  "cells": [
    {"row": "EMEA", "column": "A", "value": 10, "total_kind": null}
  ],
  "total_cell_count": 1,
  "input_row_count": 20
}
```

`status` is `ready`, `empty`, or `missing_columns`. Cells are data-row-major,
then optional row totals, column totals, and grand total. `total_kind` is
null, `row`, `column`, or `grand`. Keep the first 2,000 cells and add the rest
to `omitted.cells`.

Kind state is the landed pivot object with:

```text
row
col
val
agg
```

The server rebuilds the canonical dataset ref.

### `stat_grid`

```json
{
  "status": "ready",
  "title": "Rates",
  "stats": [
    {
      "id": "ten_year",
      "label": "10Y",
      "value": 4.25,
      "formatted_value": "4.25",
      "trend": 0.03,
      "sub": ""
    }
  ]
}
```

Each stat has exactly `id`, `label`, `value`, `formatted_value`, `sub`, and
`trend`. Runtime values win. There is no kind state beyond the common state.
The server rebuilds canonical `value_source` refs from `stats[*].source`.

### `tool`

```json
{
  "status": "ready",
  "outputs": {"result": 8.0},
  "total_cell_count": 2
}
```

`status` is `pending`, `ready`, or `error`. `outputs` is the tool's actual
JSON-safe compute result; do not invent a row schema.

Kind state:

```json
{
  "inputs": {"x": 4},
  "computed_at": "2026-07-20T17:52:31.123Z",
  "error": null
}
```

Outputs consume the shared 2,000 semantic-leaf budget before inputs.
`total_cell_count` counts the unbounded source structures for both.
`TOOL_STATE` caches output only after successful render. If a later compute
fails, `error` and `computed_at` update while the latest successfully rendered
output remains visible and may appear in the error snapshot with an explicit
coverage note. The server owns the canonical tool definition and compute
source.

### `user_input`

The browser is metadata evidence only:

```json
{
  "status": "ready",
  "title": "Knowledge files",
  "mode": "files",
  "content_metadata": {
    "file_count": 1,
    "files": [
      {
        "file_id": "file-id",
        "original_filename": "Weekend Reading.pdf",
        "normalized_filename": "Weekend Reading.pdf",
        "size_bytes": 184239,
        "detected_mime": "application/pdf",
        "content_sha256": "64hex",
        "uploaded_at": "2026-07-20T03:30:00.000000Z",
        "uploaded_by": "owner"
      }
    ]
  }
}
```

Mode-specific `content_metadata` is exactly one of:

```json
{"text_bytes": 123}
{"item_count": 8, "checked_count": 3}
{"files": [], "file_count": 0}
```

No text body or checklist item text is emitted. File metadata has only the
eight fields shown. It excludes `download_url`, S3/object keys, and bytes.
The exact MIME field is `detected_mime`; do not accept a browser
`content_type` alias.

Kind-state fields:

```text
phase
source
revision_id
parent_revision_id
content_sha256
updated_at
updated_by
can_write
dirty
```

Coverage is `metadata_only` unless truncation forces `partial`. Browser refs
are exactly:

```json
{"kind": "user_input", "ref": "knowledge_drop", "mode": "files"}
{"kind": "user_input_file", "ref": "file-id", "file_id": "file-id", "filename": "source.pdf"}
```

On submit, trusted server content from `read_dashboard_user_input` wins.
Captured revision/hash/source remain comparison evidence.

### `markdown`

```json
{
  "status": "ready",
  "title": null,
  "note_kind": null,
  "text": "Visible rendered text"
}
```

`text` is `.markdown-body.textContent`, not markdown source and not HTML.
There is no kind state beyond the common state. Headerless plain markdown
uses a served-only owner grip. Its canonical definition remains server-owned.

### `note`

`note` uses the same markdown snapshotter:

```json
{
  "status": "ready",
  "title": "Optional title",
  "note_kind": "insight",
  "text": "Visible rendered text"
}
```

There is no additional kind state. Legacy `note` uses the producer's implicit
`note_kind: "insight"`. `.note-head` is its natural drag surface.

### `image`

Only visible text semantics are in `resolved_view`:

```json
{
  "title": "Reference image",
  "alt": "Description"
}
```

There is no additional kind state. Source and surrounding link are separate
`image` and `link` source refs. Embedded `data:` bytes are omitted and force
partial coverage. A titled image uses `.tile-header`; an untitled image gets
a served-only owner grip.

### `divider`

`resolved_view` is exactly:

```json
{"marker": "divider"}
```

There is no additional kind state. A divider always gets a served-only owner
grip.

## Browser drag behavior

### Startup and owner gate

Keep the two-latch, no-polling startup:

```text
composerReady   ← window.ComposerManager exists
dashboardReady  ← prism:dashboard:ready or window.DASHBOARD already exists
bind exactly once when both are true
```

Before binding any source or injecting any grip:

```javascript
window.PRISM_VIEWER === window.PRISM_DASHBOARD_OWNER
```

Both sides must be present and equal. A shared/non-owner dashboard may still
mount Composer under the existing product flag, but it gets no draggable
natural header and no injected grip.

### Natural handles and served-only grips

Natural handles:

```text
.tile-header   chart, table, data_grid, pivot, stat_grid, tool,
               user_input, titled image
.kpi-header    kpi
.note-head     note and semantic markdown
```

For plain headerless markdown, untitled image, and divider, append exactly
one `.prism-composer-drag-grip` to the `[data-tile-id]` wrapper only after
both ready latches and owner authorization. The grip:

```text
draggable="true"
visible text: Drag to Composer
same drag handler as a natural handle
```

Position it with response-injected CSS in `dashboard_composer.py`. Do not
write it into stored `dashboard.html` or the ECharts payload. Rebinding is
idempotent and removes no dashboard DOM.

Never use a canvas, table body, whole tile body, filter, control drawer, or
popup as a drag handle. Preserve the current `INTERACTIVE_SELECTOR`; a drag
starting on a button, link, form control, info icon, sorting control, or other
interactive descendant must be ignored.

### Capture timing and visible errors

Call `getWidgetSnapshot(widgetId)` on every `dragstart`, immediately before
`DataTransfer.setData`. Do not capture when handles bind, on `mousedown`, or
when the card renders. This ensures the capture contains the state the owner
actually dragged.

Capture is required. Abort without creating a card and report through:

```javascript
ComposerManager.reportArtifactError({code, message})
```

Browser codes:

```text
snapshot_api_unavailable
snapshot_capture_failed
snapshot_persistence_failed
```

Console-only reporting is insufficient. Reuse the existing visible Composer
error surface. There is no canonical-only downgrade.

## Drag, persisted, and POST wire schemas

### `application/x-prism-artifact`

The drag JSON has exactly these ten top-level fields:

```json
{
  "type": "dashboard_component",
  "id": "divider",
  "path": "users/owner/dashboards/dashboard-id",
  "label": "Divider: divider",
  "dashboard_id": "dashboard-id",
  "widget_kind": "divider",
  "template_sha256": "64 lowercase hexadecimal characters",
  "snapshot_schema_version": 1,
  "snapshot_bytes": 601,
  "view_snapshot": {
    "snapshot_schema_version": 1,
    "widget_id": "divider",
    "widget_kind": "divider",
    "captured_at": "2026-07-20T17:52:31.123Z",
    "resolved_view": {"marker": "divider"},
    "view_state": {
      "rendered": true,
      "visible": true,
      "tab_id": null,
      "tab_active": true,
      "group_id": null,
      "group_open": null,
      "filters": {}
    },
    "source_refs": [],
    "truncation": {
      "truncated": false,
      "limits": {
        "component_bytes": 262144,
        "string_bytes": 32768,
        "table_rows": 500,
        "chart_points": 2000,
        "pivot_tool_cells": 2000
      },
      "omitted": {
        "rows": 0,
        "points": 0,
        "cells": 0,
        "strings": 0,
        "string_bytes": 0,
        "values": 0,
        "value_bytes": 0
      },
      "result_bytes": 601
    },
    "coverage": "full",
    "coverage_notes": []
  }
}
```

No unknown top-level key is permitted. `path` and `label` are display hints,
not authority. The transport-level schema version allows early rejection
before descending into the snapshot; it and the envelope version must both be
integer `1`.

Compute browser advisory bytes as:

```javascript
new TextEncoder().encode(JSON.stringify(viewSnapshot)).length
```

The server recomputes canonical Python JSON bytes and does not require its
count to equal advisory `snapshot_bytes` or producer `result_bytes`.
An inaccurate non-negative advisory number neither bypasses nor independently
fails authoritative server size validation.

### Kind labels

Synchronize this exact map in `dashboard_composer.js`, `composer.js`, and
`composer_artifacts.py`:

```python
{
    "chart": "Chart",
    "kpi": "KPI",
    "table": "Table",
    "data_grid": "Data grid",
    "pivot": "Pivot",
    "stat_grid": "Stat grid",
    "tool": "Tool",
    "user_input": "User input",
    "markdown": "Markdown",
    "note": "Note",
    "image": "Image",
    "divider": "Divider",
}
```

Title selection order is:

```text
widget.title
→ widget.label
→ tool_def.name
→ image.alt
→ widget id
```

The label is `"<prefix>: <selected title>"`. The server recalculates it.

### Persisted and POST artifact

On drop, normalize only `path` to `art_path`, delete `path`, and deep-clone
`view_snapshot`:

```typescript
type PersistedDashboardComponent = {
  type: "dashboard_component";
  id: string;
  art_path: string;
  label: string;
  dashboard_id: string;
  widget_kind: "chart" | "kpi" | "table" | "data_grid" | "pivot"
    | "stat_grid" | "tool" | "user_input" | "markdown" | "note"
    | "image" | "divider";
  template_sha256: string;
  snapshot_schema_version: 1;
  snapshot_bytes: number;
  view_snapshot: ViewSnapshotV1;
};
```

The drag, internal, and POST forms differ only by `path` versus `art_path`.
The three snapshot transport fields remain top-level and unchanged:

```text
snapshot_schema_version
snapshot_bytes
view_snapshot
```

Preserve the exact object through:

```text
optimistic drop card
    → active tab
    → per-tab local session persistence
    → tab switch / close / reopen / migration
    → full session restore
    → fire-off POST artifacts[]
    → inline-chat POST artifacts[]
    → question-grouped fire_offs runs[]
    → history view
    → run replay
```

Do not flatten or stringify `view_snapshot`. Every allowlist, copy, clone,
serializer, parser, and history layer must include all ten persisted fields.

Within one tab, component identity is `(dashboard_id, id)`. Dragging the same
widget again atomically replaces the complete prior artifact with the latest
ten-field capture. An older in-flight artifact-info response may update only
the replacement card's `label` and `preview`; it cannot restore the previous
snapshot or template hash.

### Browser and server preflight

Limits:

```text
per view_snapshot: 262,144 bytes
per Composer turn: 1,048,576 bytes
```

Browser code uses advisory serialized bytes for early card/turn UX. A capture
or local persistence quota failure is visible and blocks send. There is no
memory-only send path.

The server:

1. validates every dashboard-component snapshot;
2. recomputes canonical bytes for each validated `view_snapshot`;
3. sums those recomputed counts only;
4. rejects a total above 1,048,576;
5. completes all this before prompt construction, email dispatch, agent
   launch, SSE response creation, or success-history persistence.

Canonical definitions, labels, paths, user-input server resolution, and
other artifact fields do not consume this locked snapshot aggregate. Any
separate request/prompt-body guard is additional policy and must not be
presented as snapshot truncation.

## `composer_dashboard_snapshot.py` contract

Create:

```text
web/backend_django/news/composer_dashboard_snapshot.py
```

It is deterministic and side-effect free. It performs no ACL, S3, Django,
email, agent, or history operation.

### Exact constants and error mapping

```python
SNAPSHOT_SCHEMA_VERSION = 1
COMPONENT_SCHEMA_VERSION = 1
ALLOWED_WIDGET_KINDS = frozenset((
    "chart",
    "kpi",
    "table",
    "data_grid",
    "pivot",
    "stat_grid",
    "tool",
    "user_input",
    "markdown",
    "note",
    "image",
    "divider",
))
MAX_VIEW_SNAPSHOT_BYTES = 262_144
MAX_TURN_VIEW_SNAPSHOT_BYTES = 1_048_576
MAX_STRING_BYTES = 32_768
MAX_JSON_DEPTH = 40
LANDED_LIMITS = MappingProxyType({
    "component_bytes": 262_144,
    "string_bytes": 32_768,
    "table_rows": 500,
    "chart_points": 2_000,
    "pivot_tool_cells": 2_000,
})
RECURSIVE_PROTOTYPE_KEYS = frozenset({
    "__proto__",
    "prototype",
    "constructor",
})
FORBIDDEN_CONTROL_KEYS = frozenset({
    "canonical_definition",
    "definition",
    "manifest",
    "tool_def",
    "object_key",
    "download_url",
    "bytes",
    "file_bytes",
    "blob",
    "screenshot",
    "screenshot_data",
    "image_data",
    "data_url",
})
ERROR_HTTP_STATUS = MappingProxyType({
    "snapshot_missing": 400,
    "snapshot_schema_unsupported": 400,
    "snapshot_malformed": 400,
    "snapshot_forbidden_key": 400,
    "snapshot_depth_exceeded": 400,
    "snapshot_string_oversized": 400,
    "snapshot_truncation_invalid": 400,
    "snapshot_identity_mismatch": 400,
    "dashboard_widget_not_found": 400,
    "dashboard_widget_kind_not_allowed": 400,
    "snapshot_component_oversized": 400,
    "snapshot_turn_oversized": 400,
    "dashboard_widget_ambiguous": 500,
    "user_input_resolution_failed": 500,
    "user_input_source_ref_unauthorized": 500,
})
```

### Exact exception and public signatures

```python
class DashboardSnapshotError(ValueError):
    code: str
    http_status: int
    details: Dict[str, Any]

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None: ...

def canonical_view_snapshot_bytes(
    view_snapshot: Mapping[str, Any],
) -> bytes: ...

def validate_view_snapshot(
    view_snapshot: Any,
    *,
    transport_snapshot_schema_version: Any,
    advisory_snapshot_bytes: Any,
    expected_widget_id: str,
    expected_widget_kind: str,
) -> Tuple[Dict[str, Any], int]: ...

def merge_widget_snapshot(
    *,
    dashboard_id: str,
    canonical_widget: Mapping[str, Any],
    validated_view_snapshot: Mapping[str, Any],
    captured_template_sha256: str,
    current_template_sha256: str,
    user_input_state: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]: ...

def validate_turn_view_snapshot_size(
    validated_view_snapshots: Sequence[Tuple[Mapping[str, Any], int]],
) -> int: ...
```

Canonical server bytes are:

```python
json.dumps(
    view_snapshot,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
```

`canonical_view_snapshot_bytes` raises
`DashboardSnapshotError("snapshot_malformed", ...)` if representation fails.
It does not reproduce browser insertion order.

`validate_view_snapshot` must:

1. require the three snapshot transport fields at the caller;
2. require a non-negative integer advisory `snapshot_bytes`;
3. require transport and envelope schema versions to equal integer `1`;
4. require the exact ten-key envelope;
5. apply path-aware exact schema, JSON, finite-number, depth-40, string,
   prototype-key, and control-key validation;
6. validate artifact-expected id/kind before per-kind parsing;
7. validate all 12 kind-specific structures without rejecting arbitrary
   valid domain-field names;
8. validate source refs and reject browser object-key/download/byte authority;
9. validate exact limits, omission names/counts, `truncated`, `result_bytes`,
   coverage enum, and coverage consistency;
10. recompute canonical bytes and reject a count above 262,144;
11. return `(deep_normalized_copy, recomputed_byte_count)`.

`result_bytes` must be a non-negative integer no greater than 262,144. It is
producer accounting, not the server's byte oracle. Do not require it or
advisory `snapshot_bytes` to equal the canonical Python count.

`merge_widget_snapshot` requires canonical `id` and `widget` to agree with
the validated snapshot, applies the explicit authority rules, rebuilds source
refs, classifies template status, and returns the merged component object.
`user_input_state` is required only for `user_input` and forbidden for other
kinds. This function performs no S3/ACL lookup.

`validate_turn_view_snapshot_size` sums only supplied recomputed counts and
returns the total. On overflow it raises `snapshot_turn_oversized` with exact
total, maximum, and component count.

### Error catalog

`DashboardSnapshotError` maps to:

```json
{
  "ok": false,
  "error": {
    "code": "snapshot_missing",
    "message": "A dashboard component requires snapshot_schema_version, snapshot_bytes, and view_snapshot.",
    "details": {}
  }
}
```

| Code | HTTP | Meaning |
|---|---:|---|
| `snapshot_missing` | 400 | One or more snapshot transport fields absent |
| `snapshot_schema_unsupported` | 400 | Transport or envelope version is not 1 |
| `snapshot_malformed` | 400 | Wrong type, structural field, count, ref, timestamp, hash, or JSON value |
| `snapshot_forbidden_key` | 400 | Prototype key anywhere or forbidden control authority/byte key |
| `snapshot_depth_exceeded` | 400 | Container depth exceeds 40 |
| `snapshot_string_oversized` | 400 | Retained string exceeds 32,768 UTF-8 bytes |
| `snapshot_truncation_invalid` | 400 | Exact limits/omissions, `truncated`, result bytes, or coverage invalid |
| `snapshot_identity_mismatch` | 400 | Artifact, snapshot, canonical, mode, owner, or dashboard identity disagrees |
| `dashboard_widget_not_found` | 400 | Current canonical top-level widget absent |
| `dashboard_widget_kind_not_allowed` | 400 | Canonical or snapshot kind outside the exact 12 |
| `snapshot_component_oversized` | 400 | Canonical snapshot bytes exceed 262,144 |
| `snapshot_turn_oversized` | 400 | Validated turn snapshot bytes exceed 1,048,576 |
| `dashboard_widget_ambiguous` | 500 | Duplicate matching canonical top-level ids |
| `user_input_resolution_failed` | 500 | Trusted persisted state corrupt/incomplete or helper fails |
| `user_input_source_ref_unauthorized` | 500 | Trusted file ref escapes canonical active-file path |

All missing, malformed, oversized, and identity-related snapshot failures are
HTTP 400 in both fire-off and chat. Snapshot validation does not use 409,
413, or 422. Existing surrounding errors remain distinct:

| Code | HTTP | Meaning |
|---|---:|---|
| `authentication_required` | 401 | No authenticated Kerberos |
| `dashboard_forbidden` | 403 | ACL denial or non-owner component submit |
| `dashboard_not_found` | 404 | Authorized dashboard lookup fails |
| `canonical_template_unavailable` | 503 | Current template cannot be read |

## Server authority and canonical resolution

### Authority split

| Concern | Browser | Authenticated server |
|---|---|---|
| Owner/path | Display evidence | Derives `users/{kerberos}/dashboards/{dashboard_id}` |
| Widget id/kind | Captured identity | Requires artifact = snapshot = canonical |
| Canonical definition | Never authoritative | Reads current `manifest_template.json` |
| Current chart/table/tool view | Capture after validation | Preserves as bounded captured evidence |
| Static markdown/note/image/divider | Evidence only | Canonical widget remains authority |
| User-input content/files | Evidence only | Resolves with trusted read helper |
| Source refs | Evidence only | Rebuilds and authorizes |
| Template hash | Served-page capture | Computes current hash and marks current/stale |
| Snapshot bytes | Advisory browser count | Recomputes canonical bytes |
| Per-component/turn limits | Early UX | Authoritative enforcement |

Never overlay browser keys onto `canonical_definition`. Build the merged
object explicitly; do not use a recursive `dict.update`.

### Identity checks

All of these must agree:

```text
authenticated kerberos
    → canonical folder owner

artifact.dashboard_id
    → server-derived folder dashboard id

artifact.id
    = view_snapshot.widget_id
    = canonical_widget.id

artifact.widget_kind
    = view_snapshot.widget_kind
    = canonical_widget.widget

artifact.snapshot_schema_version
    = view_snapshot.snapshot_schema_version
    = integer 1
```

`art_path` is parsed only to reject an explicit cross-user or
cross-dashboard claim. It never chooses S3 data.

Resolve the canonical widget only from:

```text
layout.rows[*][*]
layout.tabs[*].rows[*][*]
```

Require exactly one match. Missing and nested-only matches are
`dashboard_widget_not_found`; duplicate top-level ids are
`dashboard_widget_ambiguous`.

### Canonical template hash and staleness

Compute the hash from the same template bytes used for widget resolution:

```python
stripped = (raw or b"").rstrip(b"\x00")
canonical = json.dumps(
    json.loads(stripped.decode("utf-8")),
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
sha256 = hashlib.sha256(canonical).hexdigest()
```

Cross-check the existing view-side helper so the served-page hash and
artifact resolver cannot drift. A generic `views.py` change is not required
when the live helper already has this behavior.

Stale behavior:

```text
captured hash = current hash
    → template.status = "current"

captured hash != current hash
and same top-level id/kind still exists
    → template.status = "stale"
    → current canonical definition wins
    → captured view remains evidence labeled by captured_at
    → preserve both hashes
    → submit continues

captured hash != current hash
and widget is missing or only in excluded nesting
    → dashboard_widget_not_found

captured hash != current hash
and widget kind changed
    → snapshot_identity_mismatch
```

Hash staleness alone is not a reject gate. Artifact-info must never replace
the captured hash with a current hash.

### Exact merged `content_summary`

`read_artifact_content(..., purpose="submit")` serializes an object with this
exact top-level shape:

```json
{
  "component_schema_version": 1,
  "artifact_type": "dashboard_component",
  "dashboard_id": "dashboard-id",
  "widget_id": "divider",
  "widget_kind": "divider",
  "template": {
    "captured_sha256": "64hex",
    "current_sha256": "64hex",
    "status": "current"
  },
  "canonical_definition": {
    "widget": "divider",
    "id": "divider",
    "w": 12
  },
  "view_snapshot": {
    "snapshot_schema_version": 1,
    "widget_id": "divider",
    "widget_kind": "divider",
    "captured_at": "2026-07-20T17:52:31.123Z",
    "resolved_view": {"marker": "divider"},
    "view_state": {
      "rendered": true,
      "visible": true,
      "tab_id": null,
      "tab_active": true,
      "group_id": null,
      "group_open": null,
      "filters": {}
    },
    "source_refs": [],
    "truncation": {
      "truncated": false,
      "limits": {
        "component_bytes": 262144,
        "string_bytes": 32768,
        "table_rows": 500,
        "chart_points": 2000,
        "pivot_tool_cells": 2000
      },
      "omitted": {
        "rows": 0,
        "points": 0,
        "cells": 0,
        "strings": 0,
        "string_bytes": 0,
        "values": 0,
        "value_bytes": 0
      },
      "result_bytes": 601
    },
    "coverage": "full",
    "coverage_notes": []
  },
  "server_resolution": null
}
```

`canonical_definition` is the complete current top-level widget dictionary,
not a client copy. `view_snapshot` is the complete validated producer
envelope. `server_resolution` is null except for `user_input`.

Do not include owner path, screenshot, HTML, download URL, or binary bytes.

### Per-kind server merge semantics

- `chart`: preserve the validated current option semantics and state; rebuild
  canonical dataset refs from the widget definition.
- `kpi`: preserve current value/delta/sparkline evidence; rebuild canonical
  `value_source` refs from source, delta source, and sparkline source.
- `table` and `data_grid`: preserve current filtered/sorted/hidden-column
  export; rebuild the canonical dataset ref.
- `pivot`: preserve current dimensions, aggregation, and bounded cells;
  rebuild the canonical dataset ref.
- `stat_grid`: preserve runtime values; rebuild canonical refs from each
  stat source.
- `tool`: preserve current inputs, latest rendered outputs, compute time, and
  error state; canonical tool definition and compute source remain server
  owned.
- `user_input`: preserve browser metadata capture unchanged, but resolve
  current authoritative content and file refs server-side as specified below.
- `markdown`, `note`, `image`, `divider`: keep the validated snapshot as
  captured-view evidence; static definition/content authority remains the
  current canonical widget.

In every kind, rebuild source refs explicitly and never accept a client
canonical definition or authority ref.

## Persisted `user_input` authority

### Ownership and persistence model

A `user_input` widget has one mode:

```text
text
checklist
files
```

Its manifest definition is separate from viewer-authored state:

```text
users/{owner}/dashboards/{dashboard_id}/
├── manifest_template.json
└── user_input/widgets/{widget_id}/
    ├── current.json
    ├── revisions/{revision_id}.json
    ├── files/{file_id}/blob
    ├── files/{file_id}/metadata.json
    └── tombstones/{file_id}/{revision_id}.json
```

The browser may display and edit state through the authenticated Django
user-input API, but it never supplies an S3 prefix, object key, revision key,
or download key. The component-snapshot consumer does not reimplement the
persistence repository.

### Trusted helper

Import:

```python
from dashboards.echart_dashboard import read_dashboard_user_input
```

Accepted public signature:

```python
read_dashboard_user_input(
    folder: str,
    widget_id: Optional[str] = None,
    *,
    s3_manager: Any = None,
    include_deleted: bool = False,
) -> Dict[str, Any]
```

For Composer, call exactly:

```python
read_dashboard_user_input(
    server_derived_folder,
    widget_id,
    s3_manager=s3_manager,
    include_deleted=False,
)
```

The helper validates a canonical `users/{owner}/dashboards/{dashboard_id}`
folder, follows `current.json` and its immutable revision, verifies hashes and
identity, returns active files with stable `object_key`, returns `{}` for an
absent requested widget/root, raises on corruption, never mutates S3, and
never reads Cabinet.

### Resolution algorithm

For a canonical `user_input`:

1. require canonical mode to equal `view_snapshot.resolved_view.mode`;
2. call the trusted helper with the authenticated server-derived folder;
3. for persisted state, require helper widget id, mode, revision identity,
   and verified content hash;
4. if the helper returns `{}`, synthesize the canonical seed in memory,
   without writing it, with null revision/hash and
   `revision_status: "seed"`;
5. compare captured `view_state.revision_id` and `content_sha256` to trusted
   current values;
6. equal persisted pairs produce `revision_status: "current"`;
7. unequal well-formed pairs produce `revision_status: "stale"` and retain
   both captured and trusted pairs;
8. malformed half-pairs produce `snapshot_malformed`;
9. mode or identity disagreement produces `snapshot_identity_mismatch`;
10. preserve the validated browser envelope unchanged as capture evidence;
11. place trusted current text/checklist/file content in
    `server_resolution.content`;
12. rebuild authorized `server_resolution.source_refs`.

Current trusted server state always wins. A stale revision/hash is explicit
comparison evidence, not a reason to use browser content. A corrupt pointer,
revision, or file state fails loudly and is not converted to seed.

### Exact `server_resolution`

```json
{
  "kind": "user_input",
  "mode": "files",
  "revision_status": "current",
  "captured_revision_id": "captured-revision",
  "captured_content_sha256": "captured-hash",
  "revision_id": "current-revision",
  "parent_revision_id": "parent-revision",
  "content_sha256": "current-hash",
  "updated_at": "2026-07-20T03:30:00.000000Z",
  "updated_by": "owner",
  "content": {"files": []},
  "source_refs": []
}
```

Seed revision fields may be null. Trusted user-input content is outside the
262,144/1,048,576 browser snapshot limits but may be subject to a separate
existing prompt-body guard. Do not call that guard snapshot truncation and do
not fall back to browser metadata.

Files in `server_resolution.content` retain verified metadata but omit
`object_key`. The authorized key appears only as the source-ref `ref`.

### Authorized file-object checks

Each helper-returned key must equal:

```text
users/{authenticated_owner}/dashboards/{dashboard_id}/
user_input/widgets/{widget_id}/files/{file_id}/blob
```

The metadata file id, hash, size, and detected MIME must agree with the trusted
helper result. Authorization comes from the already-authorized dashboard and
the active-file resolution. A client cannot supply or broaden a file ref.

Server file refs:

```json
{
  "kind": "user_input_file",
  "ref": "users/owner/dashboards/id/user_input/widgets/w/files/f/blob",
  "file_id": "f",
  "filename": "source.pdf",
  "size_bytes": 42,
  "sha256": "64hex",
  "detected_mime": "application/pdf"
}
```

The helper may read immutable bytes to verify integrity, but no binary value
enters the Composer artifact, prompt, tab state, session, history, or replay.
Neither email nor chat downloads or embeds the file.

## Artifact preview, submit, prompts, and history

### `composer_artifacts.py` purpose split

Use:

```python
read_artifact_content(artifact, kerberos, *, purpose="submit")
```

`purpose` is exactly `preview` or `submit`.

`purpose="preview"`:

- resolves canonical label and a small canonical preview only;
- does not require, accept, return, query, or store
  `snapshot_schema_version`, `snapshot_bytes`, or `view_snapshot`;
- returns only the existing artifact-info shape:

```json
{"label": "Chart: Current canonical title", "preview": "small canonical preview"}
```

`purpose="submit"`:

- requires the exact normalized ten-field persisted artifact;
- derives the owner folder from authenticated Kerberos;
- rejects cross-user/cross-dashboard hints;
- reads the current template;
- resolves exactly one top-level widget;
- validates the snapshot and authoritative bytes;
- resolves trusted user-input state when applicable;
- performs the explicit kind-aware merge;
- returns merged JSON serialized in `content_summary`.

All other artifact types must remain behaviorally unchanged.

### Artifact-info query behavior

`resolveArtifactInfo` sends only:

```text
type
id
art_path
dashboard_id
widget_kind
template_sha256
```

It omits:

```text
snapshot_schema_version
snapshot_bytes
view_snapshot
```

The response may update only card `label` and `preview`. It cannot replace
the snapshot transport fields or captured template hash. Artifact-info is a
canonical preview GET, never a snapshot upload.

### Prompt framing

Keep:

```python
_INLINE_BODY_TYPES = ("skill", "preference", "dashboard_component")
_REFERENCE_ONLY_TYPES = ("cabinet",)
_NON_ATTACHED_TYPES = _INLINE_BODY_TYPES + _REFERENCE_ONLY_TYPES
```

`dashboard_component` remains an inlined body type. It is not reference-only.

`build_composer_prompt(user_message, artifact_contents)` remains the single
prompt builder for email and inline chat. Preserve this order:

```text
### Request
user message

### Attached Artifacts
reference lines

inlined typed bodies
    → for dashboard_component, pretty-printed merged content_summary
```

The dashboard-component framing must make these distinctions explicit:

```text
canonical_definition  current server-owned widget definition
view_snapshot         bounded current view captured at captured_at
source references     rebuilt server-authorized references
truncation            producer coverage and exact omission accounting
template.status       whether captured and current template hashes differ
server_resolution     trusted user_input content/reference resolution, or null
```

Do not add screenshot language. Do not fetch or inline user-input file bytes.
`composer_email.compose_email_body` should remain a thin wrapper over the
same builder. `_build_chat_prompt` must use that builder as well.

### Fire-off/chat preflight

`composer_views.py` is the required POST integration point:

```text
parse and normalize request
    → resolve every artifact with purpose="submit"
    → validate each dashboard-component snapshot
    → validate aggregate canonical snapshot bytes
    → only then construct prompt / dispatch email or agent / open SSE
    → only then persist successful history
```

Artifact-info calls with `purpose="preview"`. Fire-off, inline chat, and
run-replay submission call with `purpose="submit"`.

Convert `DashboardSnapshotError` to its exact JSON and HTTP status.
Inline-chat validation must complete before creating a streaming response.
There is no fallback, separate store, or endpoint.

### Inline history, SSE, and replay preservation

Preserve existing question-grouped history:

```text
question row
└── runs[]
    ├── mode="email"
    └── mode="inline"
```

Every completed inline turn persists as `mode="inline"` with thinking,
answer, and error transcript under the question. The normalized ten-field
artifacts, including all three snapshot transport fields, must survive in the
run record.

SSE classification remains:

```python
if chunk_type == "response":
    # emit final
else:
    # emit non-suppressed thinking
```

Tool-call events remain excluded from thinking-only streams.

Replay behavior:

- `mode="view"` displays stored output and performs no artifact resolution;
- a run replay reuses the stored captured snapshot and validates it against
  the current canonical template;
- `question_id` is retained so a rerun appends under the same question;
- replay must not recapture the browser or silently upgrade the snapshot;
- tab switch, panel resize, session restore, and history rendering must not
  strip any snapshot field.

## File-by-file implementation requirements

### `web/prism_site/js/dashboard_composer.js`

- Expand `ALLOWED_KINDS` to exactly the 12 top-level kinds.
- Keep the owner gate, two ready latches, bind-once behavior,
  `INTERACTIVE_SELECTOR`, and copy effect.
- Use the exact natural handles and inject grips only for headerless plain
  markdown, untitled image, and divider.
- Capture synchronously on each `dragstart`.
- Compute advisory bytes with `TextEncoder`.
- Perform basic envelope/id/kind/version/size preflight before `setData`.
- Emit the exact ten-field MIME object.
- Report visible errors and abort on any required-capture failure.
- Do not mutate `WIDGET_META`, manifest state, or stored HTML.

### `web/prism_site/js/composer.js`

- Preserve `DND_MODE` and `dashboard_components` behavior: drop enabled,
  uploads disabled, generic source scan disabled, only
  `dashboard_component` accepted.
- Add `reportArtifactError({code, message})` through the existing visible
  error surface.
- Accept only the exact dashboard-component wire fields.
- Rename only `path` to `art_path`.
- Deep-clone and preserve the view snapshot plus two scalar transport fields.
- Synchronize the complete kind-prefix map.
- Keep snapshot fields out of artifact-info query parameters.
- Limit artifact-info merge to `label` and `preview`.
- Preserve all ten fields through card, tab, local state, restore, POST,
  history, and replay.
- Apply advisory component and turn preflight.
- Block send on capture or persistence failure; never downgrade.

### `web/backend_django/news/composer_dashboard_snapshot.py`

- Implement the constants, public surface, exact schemas, path-aware
  recursive validation, byte accounting, merge rules, and errors in this
  handoff.
- Keep it deterministic and side-effect free.

### `web/backend_django/news/composer_artifacts.py`

- Expand allowed kinds and kind prefixes to all 12.
- Add the exact `purpose` split.
- Derive owner/dashboard authority server-side.
- Read the current canonical template and resolve one top-level widget.
- Hash the same bytes used for resolution with the canonical algorithm.
- Import and call `read_dashboard_user_input`; do not duplicate its
  pointer/revision/file verification.
- Never trust client path, label, canonical definition, source refs,
  user-input content, or file refs.
- Return merged submit JSON in `content_summary`.
- Keep other artifact types unchanged.

### `web/backend_django/news/composer_prompt.py`

- Keep `dashboard_component` in `_INLINE_BODY_TYPES`.
- Pretty-print the exact merged component object for both email and chat.
- Preserve unrelated inline/reference policy.
- Add no file-byte fetch or screenshot language.

### `web/backend_django/news/composer_views.py`

- Use `purpose="preview"` for artifact-info.
- Use `purpose="submit"` for fire-off, chat, and run replay.
- Ensure both POST bodies receive all three snapshot transport fields.
- Resolve all artifacts and enforce aggregate bytes before side effects.
- Map `DashboardSnapshotError` to exact JSON/status.
- Validate chat before opening SSE.
- Preserve artifacts in question-grouped email/inline history and replay.
- Create no snapshot API or persistence object.

### `web/backend_django/news/dashboard_composer.py`

- Preserve `inject_dashboard_composer(html, enable_inline_chat=False)`.
- Preserve shared Composer CSS/JavaScript and
  `PRISM_COMPOSER_DND_MODE = "dashboard_components"`.
- Add only the serve-time grip-positioning CSS needed by
  `.prism-composer-drag-grip`.
- Keep injection response-only and idempotent.
- Do not modify stored HTML, manifest, or ECharts payload.
- Keep Observatory/developer routes excluded.

## Tests and qualification

### Verified ECharts evidence

The canonical producer was qualified locally on 2026-07-20:

```text
17 focused producer/ready tests passed
1,071 complete unit tests passed
11 diagnostic stress scenarios passed
72 adversarial validation fixtures passed
browser/runtime sweeps passed
persisted-input sweeps passed
all aesthetic fixtures passed
```

The focused suite includes a compiled dashboard containing all 12 kinds,
opened in Chromium, with `getWidgetSnapshot()` invoked for every top-level
widget. It verifies exact identity, exact ten-key envelopes, fixed-point
`result_bytes`, and the 256 KiB cap.

Do not reinterpret this as installed-byte parity or as evidence that the live
`prism-main` consumer exists.

### Exact available commands

From `prism-main` root:

```bash
python -m pytest web/backend_django/news/tests/test_composer_dashboard_snapshot.py -q
python -m pytest web/backend_django/news/tests/test_composer_artifacts.py -q
python -m pytest web/backend_django/news/tests/test_composer_views.py -q
python -m pytest web/backend_django/news/tests/test_dashboard_composer.py -q
python -m pytest web/backend_django/news/tests -q
```

Canonical ECharts focused gate:

```bash
cd projects/echarts
../../.venv/bin/python dev/tests.py unit TestWidgetSnapshotProducer TestDashboardComponentReadyHook -v
```

Canonical ECharts full qualification gate:

```bash
cd projects/echarts
../../.venv/bin/python dev/qualification.py --all
```

If the live PRISM checkout has different test module names or a different
browser runner, update this handoff with the actual runnable command after
mapping tests into that live structure. Do not weaken assertions to fit a
runner.

### Snapshot module and Django unit/integration requirements

Cover:

1. exact constants, public signatures, and error/status map;
2. exact three transport fields and exact ten-key envelope;
3. schema versions rejecting booleans and non-1 integers;
4. exact limit and omission names/values;
5. exact coverage enum and truncation consistency;
6. canonical recomputed bytes and 262,144-byte limit;
7. aggregate recomputed bytes and 1,048,576-byte limit;
8. advisory browser-byte mismatch accepted while authoritative oversize fails;
9. depth 40 accepted and depth 41 rejected at the correct boundary;
10. 32,768 UTF-8 string bytes accepted and 32,769 rejected;
11. prototype keys rejected recursively;
12. authority/control keys rejected only in control zones;
13. valid table/chart/tool domain fields named like transport words accepted;
14. each of the 12 per-kind schemas and merge rules;
15. every artifact/snapshot/canonical id, kind, dashboard, owner, mode, and
    schema mismatch;
16. flat and tabbed top-level canonical resolution;
17. nested-only id rejection and duplicate-id ambiguity;
18. source refs rebuilt, de-duplicated, and encounter ordered;
19. browser object-key/download/byte refs rejected;
20. template current/stale status and both hashes;
21. stale same-kind submission succeeds;
22. stale missing or changed-kind submission fails;
23. captured hash survives artifact-info and state round trips;
24. user-input seed, current, stale revision, stale hash, and malformed
    half-pair behavior;
25. user-input helper exception/corrupt state behavior;
26. active files, metadata agreement, and exact authorized object-key path;
27. escaped/cross-widget/tombstoned file refs rejected;
28. no binary values in artifact, prompt, session, history, or replay;
29. artifact-info uses `purpose="preview"` and receives no snapshot fields;
30. artifact-info returns only label/preview and never a snapshot body;
31. fire-off and chat reject every missing/malformed/oversized/identity
    failure before side effects with exact HTTP 400 codes;
32. aggregate validation occurs before email, agent, SSE, or success history;
33. no canonical-only fallback, snapshot store, or endpoint;
34. all ten persisted artifact fields survive POST parsing and history;
35. run replay submits the stored snapshot; view replay does not resolve.

### JavaScript and Playwright requirements

Add or update browser tests that exercise the real served dashboard and
Composer scripts:

- two-latch startup in both script-load orders;
- bind-once behavior after duplicate ready notifications;
- strict owner gate;
- exact 12-kind allowlist;
- natural handle selection for every naturally headed kind;
- exactly one served grip for headerless markdown, untitled image, divider;
- no grips or draggable natural handles for non-owners;
- interactive descendants do not initiate drag;
- capture occurs at `dragstart`, after a visible state change;
- `getWidgetSnapshot` absence and thrown capture error are visible;
- exact MIME object, including top-level snapshot fields;
- advisory component and aggregate preflight;
- drop normalization from `path` to `art_path`;
- immutable deep snapshot through card replacement and tab state;
- local persistence failure blocks send visibly;
- stale artifact-info response cannot replace snapshot/hash;
- snapshot fields excluded from artifact-info URL;
- snapshot fields included in fire-off and chat bodies;
- session reload, history view, run replay, and view replay semantics;
- response-only injection leaves stored bytes unchanged.

### Owned dashboard smoke

```text
[ ] Natural drag works for chart
[ ] Natural drag works for kpi
[ ] Natural drag works for table
[ ] Natural drag works for data_grid
[ ] Natural drag works for pivot
[ ] Natural drag works for stat_grid
[ ] Natural drag works for tool
[ ] Natural drag works for user_input
[ ] Natural drag works for note
[ ] Natural drag works for titled image
[ ] Semantic markdown uses .note-head
[ ] Plain markdown gets exactly one grip
[ ] Untitled image gets exactly one grip
[ ] Divider gets exactly one grip
[ ] Chart controls changed before drag appear in the captured snapshot
[ ] Table sort/search/hidden columns changed before drag appear in capture
[ ] Pivot state changed before drag appears in capture
[ ] Tool inputs/latest output/error state appear in capture
[ ] User-input text/checklist resolves trusted current server revision
[ ] Files mode supplies verified metadata/refs and no bytes
[ ] Stale same-id/same-kind template submits with explicit stale status
[ ] Missing/malformed/oversized/mismatched snapshots fail visibly
[ ] Four near-cap snapshots pass when canonical total is within limit
[ ] Canonical total above 1,048,576 fails regardless of definition bytes
[ ] Tab switch and full reload preserve all snapshot transport fields
[ ] History view and run replay preserve the exact captured snapshot
```

### Shared/non-owner smoke

```text
[ ] Composer may render under the existing feature flag
[ ] No natural header is draggable
[ ] No injected grip exists
[ ] Existing dashboard controls still work
[ ] Forged dashboard_component POST fails owner/identity authorization
```

### Stored/browser artifact smoke

```text
[ ] S3 dashboard.html is byte-identical before and after serving
[ ] file:// dashboard has no Composer dependency or injected grip
[ ] Observatory/developer routes remain uninjected
[ ] No snapshot endpoint exists
[ ] No independent snapshot object or database record exists
```

### Promotion and byte-parity verification

Before enabling the all-12 leaf:

```text
[ ] prism-core checkout commit equals the gitlink recorded by prism-main
[ ] prism-core working tree status is understood
[ ] canonical rendering.py equals installed rendering.py byte-for-byte
[ ] canonical dashboard_user_input.py equals installed file byte-for-byte
[ ] canonical echart_dashboard.py equals installed file byte-for-byte
[ ] installed dashboard exposes window.DASHBOARD.getWidgetSnapshot
[ ] installed dashboard exports the accepted read_dashboard_user_input helper
[ ] focused ECharts producer tests still pass
[ ] prism-main Django and browser suites pass
```

Record the exact commits and byte comparison command/output in the landed
handoff update. Do not call semantic similarity byte parity.

## Commit and dirty-tree hygiene

Inspect both repositories and the submodule gitlink independently:

```bash
git status --short
git diff
git diff --cached
git submodule status
```

Do not reset or absorb unrelated work. In the previously reviewed tree, these
were local-development changes and must not be committed without explicit
intent:

```text
entrypoint.py
    SITE_DEFAULT_PORT 8501 → 8502

core/configs/access_control_lists.py
    THREAD_ACL adds goyalri
```

Confirm product intent before including:

```text
web/prism_site/run.py
    enable_inline_chat False → True
```

Unrelated dirty files previously observed:

```text
boj_client.py
chinadata_client.py
ai_buildout_client.py
prism_mcp/utils/skill_crud_functions.py
prism_mcp/utils/chart_functions.py
context/modules/static/developer/website_dev.md
```

The first three are API-client work. The skill CRUD id re-derive and Altair
`source=` changes are tangential. The blank `website_dev.md` and its registry
entry are separate follow-up. Do not include them merely because they share a
dirty tree.

If `dashboard_composer.py` or `dashboard_composer.js` appears as an empty
staged blob while real content exists in the working tree, inspect index
versus working tree and stage the actual intended content before committing.
Do not commit unless explicitly requested.

## Definition of done

```text
Producer and promotion
    [x] all-12 neutral snapshot producer implemented locally
    [x] exact bounded envelope and per-kind schemas tested locally
    [x] user-input authority metadata retained locally
    [x] 17 focused tests passed
    [x] full 1,071-unit / 11-stress / 72-validation qualification passed
    [ ] prism-core checkout reconciled to prism-main gitlink
    [ ] required payload files promoted byte-identically
    [ ] installed-byte parity proved

Browser consumer
    [ ] all 12 kinds enabled only after producer promotion
    [ ] owner-only natural handles and served-only grips implemented
    [ ] interactive descendants excluded
    [ ] required capture occurs at dragstart
    [ ] exact drag/persisted/POST schemas preserved
    [ ] component and aggregate preflight implemented
    [ ] visible capture/persistence errors implemented

Server consumer
    [ ] composer_dashboard_snapshot.py lands with exact public surface
    [ ] exact schema, bounds, errors, and all-kind merges pass
    [ ] authenticated canonical resolution and identity checks pass
    [ ] stale-template behavior passes
    [ ] source refs rebuilt from authority
    [ ] user-input trusted resolution and file-key authorization pass
    [ ] prompt contains canonical definition + bounded captured current view
    [ ] no binary bytes, fallback, snapshot store, or snapshot endpoint

Composer lifecycle
    [ ] artifact-info remains preview-only
    [ ] fire-off and chat preflight before side effects
    [ ] tabs/session/history/replay preserve immutable capture
    [ ] inline prompt/history/SSE behavior remains intact

Verification
    [ ] focused prism-main snapshot tests pass
    [ ] complete news test suite passes
    [ ] JavaScript/Playwright tests pass
    [ ] owned dashboard all-kind smoke passes
    [ ] shared/non-owner smoke passes
    [ ] stored dashboard bytes remain unchanged
    [ ] this handoff records landed symbols, commits, parity evidence,
        and exact runnable test commands
```
