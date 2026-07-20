# Composer-on-dashboard stack: current-view snapshot contract

_as of 2026-07-20; baseline source: PRISM working-tree diff review
`sessions/20260719_221610_goyalri_dashboard_website_diff_review/`
(`git diff HEAD` in both `prism-main` and `prism-core`); staging
producer source/tests:
`echarts-payload/{rendering.py,dashboard_user_input.py}` and
`dev/tests.py::TestWidgetSnapshotProducer`; required `prism-main`
consumer specified below but not claimed as implemented_

This is the staging-side SSOT for how Prism Composer mounts onto
compiled dashboard documents, how it binds to ECharts `rendering.py`,
and how bounded, current-view `dashboard_component` artifacts enter
fire-off / inline chat. It preserves the verified 2026-07-19 as-landed
baseline, then defines the exact implementation contract that replaces
that baseline's six-kind, canonical-only component body.

This workspace cannot inspect the current live `prism-main` checkout.
The 2026-07-19 working-tree review is the verified baseline, not proof
that the required changes below exist. A fresh implementation session
must re-open every named live file and its tests before editing, preserve
unrelated post-review work, and map this contract onto the live call
graph without fabricating line numbers.

Companion docs:

```text
projects/echarts/README.md                          short boundary + stage bar
projects/echarts/dev/notes.md                       open leftovers
projects/echarts/dev/handoffs/2026-07-18_dashboard_component_composer_drag.md
projects/echarts/dev/handoffs/2026-07-18_prism_main_component_drag_explainer.md
prism/dashboards-portal.md §11                      portal-side mirror
```

---

## Stage bar

```text
Stage 0              █████  seams verified
Stage 1              █████  Composer mount on served user dashboards
Stage 2a baseline    █████  widgets + prism:dashboard:ready
Stage 2b baseline    █████  six-kind drag + canonical component body
Stage 2b producer    █████  all-12 bounded view snapshots, locally tested
Stage 2b prism-main  ░░░░░  transport, validation, merge, grips pending
Stage 3              ░░░░░  typed-operation visual builder (excluded)
```

The six-kind Stage 2b baseline landed in the PRISM working tree reviewed
2026-07-19. The neutral producer has since landed locally:
`rendering.py` exports all 12 `WIDGET_SNAPSHOTTERS` through synchronous
`window.DASHBOARD.getWidgetSnapshot(widgetId)`,
`dashboard_user_input.py` retains the authority metadata it consumes,
and `TestWidgetSnapshotProducer` pins the executable behavior. The
required `prism-main` transport/validation/merge/grip edits remain a
target contract because this workspace still cannot inspect or claim
their live implementation. Promote the landed payload into a reconciled
`prism-core` checkout before enabling that PRISM leaf or claiming
installed-byte parity.

---

## Required Stage 2b implementation contract

### Product boundary

Exactly these 12 top-level widget kinds are draggable, in this stable
order:

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

`layout.tabs[*].rows[*][*]` and `layout.rows[*][*]` contain top-level
widgets and are eligible. Tabs themselves, filters, layout groups,
popups, popup detail sections, chart series, stat cells, tool inputs,
tool outputs, table rows, and every other nested leaf are not drag
sources. A top-level widget snapshot may contain the current state of
its nested content; that does not make the nested content independently
draggable.

The boundary is deliberately asymmetric:

```text
┌──────────────────────────────────────────────────────────────────┐
│ ECharts payload: neutral producer                                │
│                                                                  │
│ window.DASHBOARD.getWidgetSnapshot(widgetId)                     │
│   -> current rendered view + current interaction state           │
│   -> bounded JSON, schema version 1                              │
│   -> no Composer names, routes, MIME types, cards, or policy     │
└───────────────────────────────┬──────────────────────────────────┘
                                │ synchronous call at dragstart
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ prism-main leaf: transport + authority                           │
│                                                                  │
│ owner-only drag -> Composer card -> fire-off/chat POST           │
│ authenticated canonical widget resolve -> validate -> merge      │
│ prompt contains server-owned definition + bounded current view   │
└──────────────────────────────────────────────────────────────────┘
```

There is no screenshot capture, snapshot endpoint, independent
snapshot S3 object, snapshot database, or canonical-only fallback.
Snapshots travel inline with the existing Composer artifact through
drag state, tabs, local session persistence, fire-off/chat POST, and the
existing run-history record.

### Dependency and enablement order

The implementation order is load-bearing:

```text
1. Keep landed neutral producer + tests green in canonical payload
                         ↓
2. Reconcile prism-main's prism-core checkout to its recorded gitlink
                         ↓
3. Promote the required ECharts payload files into reconciled prism-core
                         ↓
4. Prove byte parity between canonical payload and installed files
                         ↓
5. Implement + test prism-main validation, merge, transport, and grips
                         ↓
6. Enable the all-12 PRISM drag leaf and run owned/shared smoke
```

Do not expand `dashboard_composer.js::ALLOWED_KINDS` before the installed
dashboard document exposes the snapshot API and the installed
`dashboards.echart_dashboard` exports
`read_dashboard_user_input`. Do not patch installed `prism-core` files
as independent sources: edit the canonical
`projects/echarts/echarts-payload/` copies, promote them, reconcile the
checkout, and verify byte identity.

---

## Neutral ECharts snapshot producer

### Landed public call

`rendering.py` now exposes this synchronous function:

```javascript
window.DASHBOARD.getWidgetSnapshot(widgetId)
```

The call:

1. accepts one non-empty top-level widget id;
2. resolves it only through `TOP_LEVEL_WIDGET_META`, so nested leaves
   cannot be addressed;
3. dispatches through `WIDGET_SNAPSHOTTERS`, whose keys exactly equal
   the 12 engine widget kinds;
4. captures state at call time, after current filters, controls,
   sorting, search, pivots, tool compute, and user-input load state;
5. JSON-normalizes Date values, converts `undefined` and non-finite
   numbers to null, rejects functions/symbols/bigints/cycles, and
   bounds strings/collections/partitions;
6. throws on an unknown top-level id, unsupported kind, unavailable
   required runtime cache, depth above 40, cycle, unsupported runtime
   value, or unstable/oversized final accounting.

It is synchronous because `DataTransfer.setData(...)` must occur inside
the browser's `dragstart` event. `dashboard_composer.js` calls it on
`dragstart`, not when handles are bound and not on `mousedown`, so the
`view_snapshot` transported by Composer is the view the owner actually
dragged.

### Landed version-1 envelope

The return value has exactly these ten keys; missing or unknown envelope
keys are invalid:

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

The returned envelope contains the stabilized UTF-8 byte length of
`JSON.stringify(envelope)`; 601 is the measured length of this exact
example. The landed tests assert the same fixed-point invariant.

| Field | Exact contract |
|---|---|
| `snapshot_schema_version` | Integer `1`; booleans are not integers |
| `widget_id` | Non-empty string equal to `TOP_LEVEL_WIDGET_META` id |
| `widget_kind` | One of the 12 exact lowercase literals |
| `captured_at` | `new Date().toISOString()` |
| `resolved_view` | Kind-specific current semantic output below |
| `view_state` | Common visibility/filter state overlaid with kind-specific state |
| `source_refs` | Encounter-order neutral `{kind, ref, ...}` records below |
| `truncation.truncated` | True iff any omitted counter is non-zero |
| `truncation.limits` | Exact five landed names/values shown above |
| `truncation.omitted` | Exact seven landed counters shown above |
| `truncation.result_bytes` | Stabilized browser UTF-8 bytes of `JSON.stringify(envelope)` |
| `coverage` | Exactly `full`, `partial`, or `metadata_only`; any truncation forces `partial` |
| `coverage_notes` | De-duplicated ordered plain-string notes |

The landed finalizer budgets the JSON-safe partitions before assembling
the envelope:

```text
resolved_view    156 KiB
view_state        48 KiB
source_refs        8 KiB
coverage_notes     8 KiB
complete envelope 256 KiB hard maximum
```

Omission accounting is exact for the producer's operation:

- `rows`: table/data-grid rows beyond 500;
- `points`: chart/tree/link or KPI sparkline points beyond 2,000;
- `cells`: pivot cells or tool semantic leaves beyond 2,000;
- `strings` / `string_bytes`: strings shortened at 32 KiB and exact
  omitted UTF-8 bytes;
- `values` / `value_bytes`: semantic values omitted by partition byte
  budgeting, plus non-finite numbers normalized to null.

String truncation keeps the longest Unicode-code-point prefix whose
UTF-8 encoding is at most 32,768 bytes. It does not append an ellipsis.
Collections preserve source order. The producer emits generic notes for
collection, string, and value truncation; exact counts remain in the
ledger.

### Landed neutral source references

Every browser reference begins with exactly `kind` and `ref`; some kinds
carry the landed metadata shown:

```json
{"kind": "dataset", "ref": "rates"}
{"kind": "value_source", "ref": "rates.latest.us_10y"}
{"kind": "tool", "ref": "scenario_calculator"}
{"kind": "user_input", "ref": "knowledge_drop", "mode": "files"}
{"kind": "user_input_file", "ref": "file-id", "file_id": "file-id", "filename": "source.pdf"}
{"kind": "image", "ref": "https://example.test/image.png"}
{"kind": "link", "ref": "https://example.test/source"}
```

References are de-duplicated by exact `JSON.stringify(record)` while
preserving first encounter order; they are not lexicographically
sorted. Chart/table/pivot/stat/KPI refs come from the top-level widget,
tool refs carry the tool name/title, and user-input file refs carry only
the browser-visible file id/name. A `data:` image source is omitted with
partial coverage rather than transported as bytes. No producer ref
contains a download URL, object key, or file bytes.

The authenticated server treats all browser refs as evidence. It
rebuilds canonical dataset/value/image/tool refs and, for `user_input`,
replaces file-id refs with authorized object-key refs returned from the
trusted read helper.

### Recursive forbidden-key and JSON checks

The producer's generic JSON normalizer intentionally preserves arbitrary
object keys in chart/table/tool domain data. The `prism-main` validator
must therefore be path-aware rather than applying one global business-
key blacklist.

```python
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
```

Prototype-pollution keys are rejected recursively everywhere. The
canonical/transport keys are rejected only in the envelope,
`truncation`, `view_state`, source-ref records, and the structural
control objects of each `resolved_view`. They are not rejected merely
because a table column is named `object_key`, a chart datum has a
domain field named `manifest`, or a tool result uses one of those names.
Those row/cell/result objects are values. Their contents still receive
prototype-key, JSON type, finite-number, depth-40, string-byte, and
overall-byte validation.

Data-bearing zones are chart `series[].data`/`links`/mark data, KPI
values/delta/sparkline points, table `columns`/`rows`, pivot cell
row/column/value fields, stat values, tool `outputs`/`inputs`, and
user-input metadata values. Everywhere else is a structural/control
zone with exact allowed keys.

---

## Per-kind version-1 schema and merge

This section mirrors the landed `WIDGET_SNAPSHOTTERS`; it does not
invent a normalized schema the producer does not emit. Required fields
are the unconditional object-literal fields below. Fields described as
optional are emitted only when the corresponding live ECharts/runtime
property exists. Data-bearing values remain generic JSON after the
landed safety/budget pass.

Every finalized `view_state` starts with these common fields:

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

`filters` contains current values for manifest filters whose empty
targets or target patterns apply to the widget. Kind-specific
`view_state` fields below overlay this common object. Tabs, groups, and
filters are still not independently draggable.

The common merge rule is:

```text
authenticated dashboard identity
        + current manifest_template.json widget
        + validated browser view_snapshot
        = prompt component body
```

The server never overlays browser keys onto the canonical widget
definition. It preserves validated current-view evidence, recomputes
source refs from canonical authority, and resolves `user_input` content
separately from server persistence.

### `chart`

Landed `resolved_view`:

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

Every series always has `name`, `type`, `data`. `stack`,
`coordinate_system`, `links`, `mark_lines`, and `mark_areas` are
optional and appear only when the live option contains them. Visual
style keys are stripped from object-form data. Tree children remain
nested and count recursively; links share the 2,000-point budget.

Kind-specific `view_state`:

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

`option_source` is `live` or `materialized`. A materialized unmounted
chart adds a coverage note but remains `full` unless actual truncation
occurs. The server rebuilds canonical dataset refs and never treats the
captured option-derived view as the widget definition.

### `kpi`

Landed `resolved_view` is the current `KPI_RESOLVED` record plus
sparkline data:

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

`delta` may be null; otherwise it has the five fields shown.
Sparkline points use the 2,000-point cap and increment
`truncation.omitted.points`.

Kind-specific `view_state` fields are `compare_period`,
`sparkline_visible`, `delta_visible`, and `decimals`. The server
rebuilds canonical `value_source` refs from `source`, `delta_source`,
and `sparkline_source`.

### `table` and `data_grid`

Both use the same current-view schema and retain their distinct
`widget_kind`.

Landed `resolved_view`:

```json
{
  "status": "ready",
  "columns": ["Name", "Value"],
  "rows": [["Alpha"]],
  "row_count": 1,
  "total_row_count": 1
}
```

`columns`/`rows` come from `_exportTableRowsForXlsx`, so they already
reflect current filtering, search, sort, hidden columns, and display
labels. `row_count` is retained rows; `total_row_count` is the
pre-truncation count. At most 500 rows are retained and
`truncation.omitted.rows == total_row_count - row_count`.

Kind-specific `view_state`:

```text
search, sort_column_index, sort_direction, hidden_column_indexes,
density, freeze_first_column, decimals, virtualized
```

Sort and hidden-column identifiers are the landed numeric indexes, not
field names. The server rebuilds the canonical dataset ref. Row/cell
objects and column-name strings remain domain values for path-aware
forbidden-key validation.

### `pivot`

Landed `resolved_view`:

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

`status` is the current resolved status (`ready`, `empty`, or
`missing_columns`). Cells are emitted in data-row-major order, followed
when configured by row totals, column totals, and grand total.
`total_kind` is null, `row`, `column`, or `grand`. The first 2,000 cells
are retained and the remainder increments `omitted.cells`.

Kind-specific `view_state` is the landed pivot state object with keys
`row`, `col`, `val`, and `agg`. The server rebuilds the canonical
dataset ref.

### `stat_grid`

Landed `resolved_view`:

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

Every stat has exactly `id`, `label`, `value`, `formatted_value`,
`sub`, `trend`. There are no kind-specific `view_state` fields beyond
the common state. Runtime values win; the server rebuilds canonical
`value_source` refs from `stats[*].source`.

### `tool`

Landed `resolved_view`:

```json
{
  "status": "ready",
  "outputs": {"result": 8.0},
  "total_cell_count": 2
}
```

`outputs` is the tool's actual JSON-safe compute result; the producer
does not rewrite it into an invented row schema. `status` is `pending`,
`ready`, or `error`.

Kind-specific `view_state`:

```json
{
  "inputs": {"x": 4},
  "computed_at": "2026-07-20T17:52:31.123Z",
  "error": null
}
```

Outputs consume the shared 2,000-cell/semantic-leaf budget before
inputs. `total_cell_count` counts both unbounded source structures.
`TOOL_STATE` caches output only after successful render. On a later
compute failure, `error` and `computed_at` update but the prior
successfully rendered `outputs` remain; an error snapshot can therefore
carry the still-visible prior output and an explicit error note. The
server owns the canonical tool definition and compute source.

### `user_input`

The browser is metadata evidence only. Landed `resolved_view`:

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

No text body or checklist item text is emitted. Files contain only the
eight landed metadata fields shown; browser-only `download_url`, S3
keys/object keys, and bytes are excluded.

The producer reads the trusted helper's canonical `detected_mime`
field directly. The executable file-metadata fixture uses that same
name and asserts that no `content_type` alias survives. The server
still treats all browser metadata as evidence and uses the helper-
verified value when rebuilding authorized file references.

Kind-specific `view_state`:

```text
phase, source, revision_id, parent_revision_id, content_sha256,
updated_at, updated_by, can_write, dirty
```

Coverage is `metadata_only` unless envelope truncation forces
`partial`. Browser refs are exactly
`{kind:"user_input", ref:widget_id, mode}` and, per file,
`{kind:"user_input_file", ref:file_id, file_id, filename}`.

On submit, the server calls `read_dashboard_user_input(...)`; trusted
server text/checklist/file content wins. Captured revision/hash/source
remain comparison evidence. Authorized file refs are rebuilt with the
verified object key and metadata; browser file refs are never promoted
to object-key authority.

### `markdown`

Landed `resolved_view`:

```json
{
  "status": "ready",
  "title": null,
  "note_kind": null,
  "text": "Visible rendered text"
}
```

`text` is `textContent` from `.markdown-body`, not markdown source or
HTML. There are no kind-specific state fields. Plain markdown without a
semantic kind uses an injected owner-only drag grip because it has no
natural header. The canonical definition remains server-owned.

### `note`

`note` uses the same `_snapshotMarkdown` producer:

```json
{
  "status": "ready",
  "title": "Optional title",
  "note_kind": "insight",
  "text": "Visible rendered text"
}
```

There are no kind-specific state fields. Legacy `note` uses the
renderer/producer's implicit `note_kind: "insight"`. `.note-head` is
the natural drag surface.

### `image`

Landed `resolved_view` contains only visible text semantics:

```json
{
  "title": "Reference image",
  "alt": "Description"
}
```

There are no kind-specific state fields. The source and surrounding
link live in `{kind:"image"|"link", ref}` records, not
`resolved_view`. Embedded `data:` bytes are omitted with partial
coverage. A titled image uses `.tile-header`; an untitled image receives
an injected owner-only drag grip.

### `divider`

Landed `resolved_view` is exactly:

```json
{"marker": "divider"}
```

There are no kind-specific state fields. A divider always receives an
injected owner-only drag grip.

---

## Drag and artifact wire contracts

### Natural handles and injected grips

On an owned served dashboard, `dashboard_composer.js` binds natural
headers:

```text
.tile-header   chart, table, data_grid, pivot, stat_grid, tool,
               user_input, titled image
.kpi-header    kpi
.note-head     note and semantic markdown
```

This covers the natural chart/KPI/table/tool/user-input/note/image
chrome while retaining the existing pivot/stat-grid/data-grid headers.
Header buttons, links, form controls, info icons, sort controls, and
anything matching `INTERACTIVE_SELECTOR` remain non-drag initiators.

For plain headerless markdown, untitled image, and divider,
`dashboard_composer.js` appends exactly one
`.prism-composer-drag-grip` inside the `[data-tile-id]` wrapper after
both ready latches fire. The grip is `draggable="true"`, contains visible
text `Drag to Composer`, and carries the same drag handler as a natural
header. It is injected only after
`PRISM_VIEWER === PRISM_DASHBOARD_OWNER`; non-owners receive neither
handles nor grips. The injector stylesheet in `dashboard_composer.py`
positions the grip without changing payload/stored HTML. Rebinding is
idempotent and removes no dashboard DOM.

### `application/x-prism-artifact`

The plan-mandated drag MIME JSON has exactly these ten top-level fields:

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

No unknown top-level keys are permitted for a `dashboard_component`.
`path` and `label` are display hints only. Identity comes from
authenticated Kerberos, `dashboard_id`, current canonical manifest,
artifact `id`/`widget_kind`, and
`view_snapshot.widget_id`/`widget_kind`.

`snapshot_schema_version` is duplicated at transport level so a receiver
can reject an unsupported payload before descending into
`view_snapshot`; both values must be integer `1`.
`snapshot_bytes` is computed in the browser as:

```javascript
new TextEncoder().encode(JSON.stringify(viewSnapshot)).length
```

It is advisory for card display and early preflight. The server decodes
`view_snapshot`, recomputes its own canonical UTF-8 JSON bytes, and
enforces 262,144 against that recomputed value. In the landed browser,
`snapshot_bytes` and producer `truncation.result_bytes` should match
because both measure `JSON.stringify(view_snapshot)`. The server does
not require either browser number to equal its Python canonical byte
count, and an inaccurate advisory number neither bypasses nor fails
authoritative size validation.

Label prefixes are synchronized across
`dashboard_composer.js`, `composer.js`, and
`composer_artifacts.py::_KIND_PREFIX`:

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

Title selection is, in order: widget `title`, widget `label`,
`tool_def.name`, image `alt`, widget id. The display label is
`"<prefix>: <selected title>"`. The server recalculates it.

### Persisted Composer and POST artifact

On drop, `composer.js` normalizes only `path` to `art_path`, deletes
`path`, deep-clones `view_snapshot`, and persists this exact shape:

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

`ViewSnapshotV1` is the exact ten-key producer envelope above. The
drag/internal/POST forms therefore differ only in `path` versus
`art_path`; the three snapshot transport names and values are unchanged.

This exact object is preserved through:

```text
drop card
  -> active tab state
  -> per-tab localStorage/session restoration
  -> tab switch/close/re-open
  -> fire-off POST artifacts[]
  -> inline-chat POST artifacts[]
  -> existing fire_offs question/run history
  -> replayed run
```

Every allowlist/copy/serialization layer must include all ten fields and
must not flatten or stringify `view_snapshot`. A local persistence quota
failure is visible as `snapshot_persistence_failed` and blocks sending;
there is no memory-only send fallback.

Within one tab, identity is `(dashboard_id, id)`. Dragging that same
widget again atomically replaces the existing card's complete ten-field
artifact with the newer capture; it does not keep the old view snapshot or
create two copies. An older in-flight artifact-info response may update
only the replacement card's label/preview and can never restore the old
view snapshot/hash.

The full fire-off and chat request bodies retain their live outer
schema; the `artifacts` member contains the exact normalized object
above. Both POST paths require inline `snapshot_schema_version`,
`snapshot_bytes`, and `view_snapshot`. A replay that re-runs an old
history item uses the stored captured view snapshot and revalidates it
against the current canonical template. `mode="view"` only displays the
stored response and performs no resolution.

No independent snapshot endpoint/store is introduced. Keeping the
inline object in the existing Composer tab and run record is part of
the existing artifact lifecycle, not a snapshot service.

The locked 1,048,576-byte turn aggregate is the sum of the server's
recomputed canonical bytes for validated `view_snapshot` objects only.
Canonical definitions, labels, paths, and other artifact fields do not
consume that aggregate. Any separate existing prompt/request body guard
is additional infrastructure policy and must not be described or
implemented as this snapshot aggregate.

### Artifact-info GET remains small

`resolveArtifactInfo` sends the six scalar identity/display fields as
query parameters and deliberately omits all three snapshot transport
fields:

```text
type, id, art_path, dashboard_id, widget_kind, template_sha256

omitted:
snapshot_schema_version, snapshot_bytes, view_snapshot
```

For `dashboard_component`, the response remains exactly:

```json
{"label": "Chart: Current canonical title", "preview": "small canonical preview"}
```

It contains no canonical widget body or `view_snapshot`.
Merging the response into a card may update `label`/`preview` only; it
must preserve the original three snapshot transport fields and captured
`template_sha256`.
The GET never upgrades the captured hash to the current hash.

---

## Server authority, validation, and merged prompt body

### Authority split

| Concern | Browser producer | Authenticated server |
|---|---|---|
| Dashboard owner/path | Display evidence | Derives `users/{kerberos}/dashboards/{dashboard_id}` |
| Widget id/kind | Captured identity | Requires artifact = `view_snapshot` = canonical |
| Canonical definition | Never authoritative | Reads current `manifest_template.json` |
| Current chart/table/tool view | Authoritative capture after validation | Preserves, bounds, and labels it as captured |
| Static markdown/note/image/divider content | Evidence only | Rebuilds from canonical widget |
| `user_input` content/files | Evidence only | Resolves through `read_dashboard_user_input` |
| Source refs | Evidence only | Rebuilds; authorizes file refs |
| Template hash | Captured served hash | Computes current hash and classifies current/stale |
| `snapshot_bytes` | Advisory `JSON.stringify` byte count | Recomputes canonical `view_snapshot` bytes |
| 262,144 / 1,048,576 limits | Early check | Enforces per-view and aggregate over validated `view_snapshot` bytes |

The server must never merge client keys into `canonical_definition`.
The merge is an explicit constructor, not recursive `dict.update`.

### Exact merged `content_summary`

`read_artifact_content(..., purpose="submit")` serializes this exact
object into `content_summary`:

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

No owner path, screenshot, HTML, or binary bytes are included.
`canonical_definition` is the complete current top-level widget dict,
not a browser copy. `view_snapshot` is the validated landed envelope.
`server_resolution` is null except for `user_input`, where it contains
the authoritative persisted/seed content and rebuilt authorized refs.

The 262,144-byte component check applies to the server-recomputed
canonical UTF-8 bytes of `view_snapshot`. The 1,048,576-byte turn check
sums only those validated view-snapshot byte counts. Neither
`canonical_definition`, `server_resolution`, nor the surrounding prompt
body consumes the locked snapshot aggregate. Any separate existing
prompt-body guard remains additional policy.

`composer_prompt.py::build_composer_prompt` pretty-prints this object
under the existing inlined dashboard-component framing. Email fire-off
and `_build_chat_prompt` use the same builder. Files-mode
`user_input_file` refs remain metadata/references in JSON; neither path
downloads or inlines their bytes.

### `composer_dashboard_snapshot.py` public surface

Create:

```text
web/backend_django/news/composer_dashboard_snapshot.py
```

It exports exactly:

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

`canonical_view_snapshot_bytes` uses:

```python
json.dumps(
    view_snapshot,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
).encode("utf-8")
```

It does not attempt to reproduce browser key order. It
raises `DashboardSnapshotError("snapshot_malformed", ...)` for a value
that cannot be represented.

`validate_view_snapshot`:

1. requires transport `snapshot_schema_version`, non-negative integer
   advisory `snapshot_bytes`, and the exact landed envelope;
2. requires transport/envelope schema versions to both equal 1;
3. applies path-aware schema, JSON, finite-number, depth-40, string,
   prototype-key, and control-key checks;
4. validates artifact-expected id/kind before per-kind parsing;
5. validates landed per-kind structural fields while preserving domain
   row/cell/result object names;
6. validates `{kind, ref, ...}` source records and forbids browser
   object-key/download/byte authority;
7. validates exact limit names/values, omitted keys, `truncated`,
   `result_bytes`, and `full|partial|metadata_only`;
8. recomputes canonical server bytes and rejects above
   `MAX_VIEW_SNAPSHOT_BYTES`;
9. returns `(deep_normalized_copy, recomputed_byte_count)` without
   requiring equality to advisory `snapshot_bytes` or browser
   `result_bytes`.

For step 7, `result_bytes` must be a non-negative integer no greater
than the landed component limit; it is producer accounting, not the
server's canonical byte oracle.

`merge_widget_snapshot` requires canonical `id` and `widget` to equal
the validated view snapshot, applies the authority rules above, rebuilds
source refs, classifies template status, and returns the exact merged
component object. `user_input_state` is required only for
`widget_kind == "user_input"` and forbidden otherwise. It does not
perform S3 or ACL calls.

`validate_turn_view_snapshot_size` sums only the recomputed byte counts
of validated `view_snapshot` objects and raises
`snapshot_turn_oversized` with exact total, maximum, and component
count. Canonical definitions and merged prompt bodies are excluded. The
views call it after all dashboard-component artifacts validate and
before prompt construction, email dispatch, agent launch, SSE response
creation, or history success persistence.

### Identity validation

For every submit, all of these must agree:

```text
authenticated kerberos
  -> canonical folder owner
artifact.dashboard_id
  -> server-derived folder dashboard id
artifact.id
  == artifact.view_snapshot.widget_id
  == canonical widget.id
artifact.widget_kind
  == artifact.view_snapshot.widget_kind
  == canonical widget.widget
artifact.snapshot_schema_version
  == artifact.view_snapshot.snapshot_schema_version
  == 1
```

`art_path` is parsed only to reject an explicit cross-user or
cross-dashboard claim; it is never used to choose S3 data. A missing,
duplicate, or nested-only canonical match is an error. Resolution walks
only `layout.rows[*][*]` and `layout.tabs[*].rows[*][*]`; it does not
descend groups, popups, tool definitions, or other nested leaves.

### User-input server resolution

For a canonical `user_input`:

```python
read_dashboard_user_input(
    server_derived_folder,
    widget_id,
    s3_manager=s3_manager,
    include_deleted=False,
)
```

is the only persisted-state reader. The flow is exact:

1. verify canonical widget mode equals
   `view_snapshot.resolved_view.mode`;
2. call the helper with the authenticated, server-derived folder;
3. if it returns persisted state, require returned widget id/mode,
   revision identity, and verified content hash;
4. if it returns `{}`, synthesize the canonical seed without writing
   it, with revision/hash null and `revision_status: "seed"`;
5. compare `view_snapshot.view_state` revision/hash to server
   revision/hash;
6. equal persisted pairs produce `current`; unequal well-formed pairs
   produce `stale` and preserve both pairs;
7. malformed half-pairs fail `snapshot_malformed`; mode/identity
   disagreement fails `snapshot_identity_mismatch`;
8. preserve the validated browser envelope unchanged as capture
   evidence;
9. put trusted current text/checklist/file content in
   `server_resolution.content`;
10. rebuild authorized `server_resolution.source_refs`.

For `user_input`, merged `server_resolution` is exactly:

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

Null is allowed for seed revision fields. Trusted content is not counted
in the 262,144/1,048,576 client snapshot limits; it remains subject to
any separate existing prompt-body guard. The implementation must not
mislabel such a guard as snapshot truncation or silently fall back to
browser metadata. Files in `server_resolution.content` retain verified
metadata but omit `object_key`; the authorized object key appears only
as `ref` in `server_resolution.source_refs`.

Every file `object_key` must equal:

```text
users/{authenticated_owner}/dashboards/{dashboard_id}/
user_input/widgets/{widget_id}/files/{file_id}/blob
```

and its metadata id/hash/size/MIME must match the helper result.
Authorization is inherited from the already-authorized dashboard and
active-file resolution; a client can never supply or broaden a file
reference. Server refs use the landed neutral names but replace `ref`
with the verified object key:

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

The helper may read immutable bytes to verify integrity, but no binary
value enters the artifact, prompt, session, or history.

A stale revision/hash is comparison evidence, not a fallback and not a
reason to use browser content: current trusted server state wins and
the mismatch is explicit. Corrupt pointer/revision/file state from the
helper fails loudly; it is not converted to seed.

### Stale template behavior

`template_sha256` is the hash of the template used to serve the dragged
page. The server computes the canonical current hash using the existing
NUL-strip, parse, sorted-key compact-JSON algorithm.

```text
captured == current
    -> template.status = "current"

captured != current AND same top-level widget id + kind still exists
    -> template.status = "stale"
    -> current canonical definition remains authoritative
    -> captured current view remains labeled by captured_at
    -> preserve both hashes in the template object
    -> submit continues

captured != current AND widget missing / moved only into excluded nesting
    -> dashboard_widget_not_found

captured != current AND widget kind changed
    -> snapshot_identity_mismatch
```

Hash staleness alone is not a reject gate. This preserves the verified
baseline's TOCTOU decision while making the mixed-time merge explicit.
Artifact-info GET must not overwrite the captured hash.

### Error response and status catalog

Fire-off and chat preflight failures return, before email/agent/SSE
startup:

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

`DashboardSnapshotError` supplies this body and status. The exact
catalog is:

| Code | HTTP | Meaning |
|---|---:|---|
| `snapshot_missing` | 400 | Any of the three snapshot transport fields is absent |
| `snapshot_schema_unsupported` | 400 | Transport or envelope schema version is not 1 |
| `snapshot_malformed` | 400 | Wrong type, unknown/missing structural field, invalid `snapshot_bytes`, ref, count, timestamp, hash, or JSON value |
| `snapshot_forbidden_key` | 400 | Prototype key anywhere or forbidden authority/byte key in a control object |
| `snapshot_depth_exceeded` | 400 | Container depth exceeds 40 |
| `snapshot_string_oversized` | 400 | Retained string exceeds 32,768 UTF-8 bytes |
| `snapshot_truncation_invalid` | 400 | Landed limits/omitted keys, `truncated`, `result_bytes`, or coverage enum is invalid |
| `snapshot_identity_mismatch` | 400 | Artifact, transport, view snapshot, canonical widget, mode, owner, or dashboard identity disagrees |
| `dashboard_widget_not_found` | 400 | Current canonical top-level widget no longer exists |
| `dashboard_widget_ambiguous` | 500 | Canonical manifest contains duplicate matching top-level ids |
| `dashboard_widget_kind_not_allowed` | 400 | Canonical or view-snapshot kind is outside the exact 12 |
| `snapshot_component_oversized` | 400 | Recomputed canonical `view_snapshot` exceeds 262,144 bytes |
| `snapshot_turn_oversized` | 400 | Sum of recomputed validated `view_snapshot` bytes exceeds 1,048,576 |
| `user_input_resolution_failed` | 500 | Trusted persisted state is corrupt/incomplete or helper raises |
| `user_input_source_ref_unauthorized` | 500 | Helper-returned file ref escapes canonical active-file path |

All missing, invalid, oversized, or identity-related snapshot failures
are HTTP 400 for both fire-off and chat. No snapshot validation path
uses 409, 413, or 422. Authentication, ACL, canonical availability, and
server-integrity failures retain their distinct statuses below.

Existing authentication/ACL handling remains:

| Code | HTTP | Meaning |
|---|---:|---|
| `authentication_required` | 401 | No authenticated Kerberos |
| `dashboard_forbidden` | 403 | Viewer lacks dashboard access or non-owner attempts drag submit |
| `dashboard_not_found` | 404 | Authorized lookup cannot find dashboard |
| `canonical_template_unavailable` | 503 | Current template cannot be read; no canonical fallback |

Browser-only errors are visible in the Composer panel and do not create
cards:

```text
snapshot_api_unavailable
snapshot_capture_failed
snapshot_persistence_failed
```

`dashboard_composer.js` reports these through one explicit
`ComposerManager.reportArtifactError({code, message})` method added to
`composer.js`. Console-only reporting is insufficient.

---

## Exact file-by-file implementation

### ECharts canonical payload and promotion

`projects/echarts/echarts-payload/rendering.py`

- The neutral constants/helpers, all 12 `WIDGET_SNAPSHOTTERS`,
  partition budgets, omission ledger, and synchronous
  `getWidgetSnapshot(widgetId)` are landed.
- The implementation uses `TOP_LEVEL_WIDGET_META`, `currentDatasets`,
  `filterState`, `CHARTS`,
  `chartControlState`, `TABLE_STATE`, `KPI_STATE`, `PIVOT_STATE`,
  `TOOL_STATE`, `USER_INPUT_STATE`, and the resolved KPI/pivot/stat
  caches rather than scraping semantic data from HTML.
- Tool inputs/latest successfully rendered outputs/error/computed time
  are retained in `TOOL_STATE`.
- `window.DASHBOARD.getWidgetSnapshot` is exported without removing
  existing fields; `prism:dashboard:ready` remains after tool and
  user-input initialization.
- Composer literals remain forbidden:
  `application/x-prism-artifact`, `/api/composer/`,
  `dashboard_component`, and PRISM drag-grip classes do not belong in
  the payload.

`projects/echarts/echarts-payload/dashboard_user_input.py`

- Server `parent_revision_id`, `content_sha256`, `source`, and
  `updated_by` are now retained beside `revisionId` in
  `USER_INPUT_STATE[wid]`.
- No object key or file bytes are exposed; the producer reads only
  authority state and bounded display metadata.
- The authenticated API and persistence ownership are unchanged.

`projects/echarts/echarts-payload/echart_dashboard.py`

- No producer-specific behavior was added here.
- Its accepted `read_dashboard_user_input` export and exact call shape
  remain the server consumer contract.

`projects/echarts/dev/tests.py`

- `TestWidgetSnapshotProducer` is landed and pins the executable
  producer contract summarized below.
- `TestDashboardComponentReadyHook` continues to pin the neutral
  integration seam.

Promote the landed `rendering.py` and `dashboard_user_input.py`
byte-identically to `prism-core/dashboards/` only after reconciling the
`prism-core` checkout with the commit recorded by `prism-main`. The same
promotion preflight must verify that canonical `echart_dashboard.py`
is installed byte-identically; promote it from the payload if the
re-opened checkout lacks the accepted read helper.

### Required `prism-main` files

These are the complete required production files for this build:

```text
web/prism_site/js/dashboard_composer.js
web/prism_site/js/composer.js
web/backend_django/news/composer_artifacts.py
web/backend_django/news/composer_prompt.py
web/backend_django/news/composer_views.py
web/backend_django/news/dashboard_composer.py
web/backend_django/news/composer_dashboard_snapshot.py   (create)
web/backend_django/news/tests/...                         (add/update)
```

Re-open their live bodies before applying this list.

#### `web/prism_site/js/dashboard_composer.js`

- Expand `ALLOWED_KINDS` to the exact 12 and no containers/nested
  leaves.
- Preserve the owner gate, two-latch startup, `INTERACTIVE_SELECTOR`,
  copy effect, and bind-once behavior.
- Resolve the natural handles listed above and inject grips only for
  headerless markdown, untitled image, and divider.
- Capture `view_snapshot` synchronously on every `dragstart`.
- Compute advisory `snapshot_bytes` with `TextEncoder` over
  `JSON.stringify(view_snapshot)`.
- Validate basic envelope/id/kind and advisory bytes before `setData`;
  report a visible error and abort on capture failure.
- Emit the exact MIME object with top-level
  `snapshot_schema_version`, `snapshot_bytes`, and `view_snapshot`.
- Do not mutate `WIDGET_META`, manifest state, or stored dashboard HTML.

#### `web/prism_site/js/composer.js`

- Preserve `DND_MODE` / `DND_COMPONENTS`; dashboard mode still disables
  uploads and generic source scanning.
- Add `reportArtifactError({code, message})` using the existing visible
  Composer error surface.
- Accept only exact dashboard-component wire fields, rename `path` to
  `art_path`, and preserve a deep `view_snapshot` object plus the two
  scalar snapshot transport fields.
- Update all kind-prefix/title normalization to the 12-kind map.
- Make `resolveArtifactInfo` query scalar fields only and merge its
  response without replacing any snapshot transport field/hash.
- Preserve the ten persisted fields through active state, per-tab
  storage, tab migration, session restore, card rerender, send, and
  history/replay.
- Use advisory bytes for early component/turn UX only; server
  recomputation remains authoritative. A persistence/capture failure
  blocks send; do not downgrade to canonical-only.

#### `web/backend_django/news/composer_dashboard_snapshot.py`

- Implement the exact public surface, schemas, merge rules, limits,
  recursive validation, errors, and canonical byte accounting above.
- Keep it deterministic and side-effect free; ACL/S3 lookup remains in
  the caller.

#### `web/backend_django/news/composer_artifacts.py`

- Expand `_ALLOWED_KINDS` and `_KIND_PREFIX` to the exact 12.
- Change `read_artifact_content` to:

  ```python
  read_artifact_content(artifact, kerberos, *, purpose="submit")
  ```

  where `purpose` is exactly `preview` or `submit`.
- `purpose="preview"` resolves only canonical label/preview and never
  requires, accepts, returns, or stores the three snapshot transport
  fields.
- `purpose="submit"` requires the exact normalized artifact, derives
  the owner folder, reads current canonical template, resolves exactly
  one top-level widget, validates `view_snapshot`, recomputes/enforces
  its bytes, resolves `user_input` when applicable, merges, and returns
  the merged JSON as `content_summary`.
- Hash the same template bytes used for widget resolution with the
  already-landed NUL-strip/parse/sorted-key compact-JSON algorithm;
  tests must cross-check the existing view helper so the two call paths
  cannot drift. This contract does not require a `views.py` edit.
- Import the trusted helper from
  `dashboards.echart_dashboard import read_dashboard_user_input`; do not
  duplicate its pointer/revision/file verification in `prism-main`.
- Never trust `art_path`, label, kind, canonical definition, source refs,
  user-input content, or file refs from the client.
- Keep all other artifact types behaviorally unchanged.

#### `web/backend_django/news/composer_prompt.py`

- Keep `dashboard_component` in `_INLINE_BODY_TYPES`.
- Frame the exact merged component JSON from `content_summary` for both
  email and chat.
- Do not fetch user-input file bytes or create screenshot language.
- Preserve `_REFERENCE_ONLY_TYPES` and unrelated artifact behavior.

#### `web/backend_django/news/composer_views.py`

- Pass `purpose="preview"` from artifact-info and `purpose="submit"` from
  fire-off/chat/replay submit paths.
- Ensure both POST paths receive inline `snapshot_schema_version`,
  `snapshot_bytes`, and `view_snapshot`; query GET receives none.
- Resolve every artifact before starting email, agent, SSE, or success
  history persistence; run aggregate validation across recomputed
  validated `view_snapshot` bytes only.
- Convert `DashboardSnapshotError` to the exact JSON/status response.
  Chat validation must happen before a streaming response is opened.
- Preserve normalized artifact fields in existing question-grouped
  `runs[]` history for email and inline modes. View replay reads stored
  output; run replay reuses the stored three-field snapshot transport.
- Do not create a snapshot API or separate persistence object.

#### `web/backend_django/news/dashboard_composer.py`

- Preserve `inject_dashboard_composer(html, enable_inline_chat=False)`,
  shared Composer assets, and
  `PRISM_COMPOSER_DND_MODE = "dashboard_components"`.
- Add serve-time CSS needed by `.prism-composer-drag-grip` to the
  existing injected style block.
- Keep the injection response-only and idempotent; stored
  `dashboard.html`, manifest, and ECharts payload stay unchanged.
- Observatory/developer routes remain excluded.

---

## Required tests

### ECharts producer tests

`projects/echarts/dev/tests.py::TestWidgetSnapshotProducer` is landed.
Its compile/static/Node-execution tests pin:

1. dispatcher equality with all 12 `VALID_WIDGETS`;
2. exported `getWidgetSnapshot` and top-level-only lookup;
3. exact ten-key envelope, 32-KiB strings, 256-KiB fixed-point
   `result_bytes`, and `full|partial|metadata_only`;
4. filtered/sorted/hidden-column table export;
5. exact row/point/cell/string/value omission markers;
6. cached tool inputs/latest rendered outputs/error/computed time;
7. user-input pending/ready authority metadata, counts, file metadata,
   and absence of URL/object-key bytes;
8. 500-row, 2,000-point, and 2,000-cell executable caps;
9. image/link refs, embedded-data omission, and divider marker;
10. neutral boundary/no canonical copy and JavaScript syntax validity.

`TestDashboardComponentReadyHook` continues to pin the neutral ready
seam and absence of Composer literals.

The producer suite also compiles one dashboard containing all 12 kinds,
opens it in Chromium, invokes the complete exported
`getWidgetSnapshot()` path for every top-level widget, and verifies kind
and id identity, the exact envelope, fixed-point `result_bytes`, and the
256-KiB cap. Focused Node tests separately pin the detailed filtered-
view, omission, tool-cache, and asynchronous user-input semantics.

### `prism-main` unit/integration tests

Add focused tests for:

- exact constants/public signatures/error mapping;
- all three transport fields, exact landed envelope/limits/omitted
  names, schema version, depth, strings, canonical recomputed bytes, and
  aggregate bytes;
- advisory `snapshot_bytes` mismatch is accepted while authoritative
  recomputed oversize fails;
- prototype keys fail recursively while arbitrary table/chart/tool
  domain field names matching transport words remain valid;
- each of the 12 per-kind validators and merge rules;
- all artifact/view-snapshot/canonical identity mismatch combinations;
- flat and tabbed top-level resolution; nested-only and duplicate ids;
- artifact-info uses `purpose="preview"`, omits all three snapshot
  transport fields, and never returns a view snapshot;
- fire-off/chat return explicit HTTP 400 codes for every
  missing/malformed/oversized/identity snapshot failure before side
  effects and never fall back;
- source refs are rebuilt and client file/object refs rejected;
- user-input seed, current, stale revision, stale hash, corrupt state,
  active files, and escaped object-key cases using
  `read_dashboard_user_input`;
- current/stale template status, stale same-kind success, stale
  missing/kind-changed failure, and captured hash preservation;
- ten artifact fields survive tab serialization, session restore,
  POST parse, question-grouped history, and replay;
- injected grips appear once for owner headerless markdown, untitled
  image, divider; natural headers are used otherwise; shared viewers
  receive none;
- stored dashboard bytes remain unchanged by injection.

Concrete commands from the `prism-main` root:

```bash
python -m pytest web/backend_django/news/tests/test_composer_dashboard_snapshot.py -q
python -m pytest web/backend_django/news/tests/test_composer_artifacts.py -q
python -m pytest web/backend_django/news/tests/test_composer_views.py -q
python -m pytest web/backend_django/news/tests/test_dashboard_composer.py -q
python -m pytest web/backend_django/news/tests -q
```

Concrete staging producer command:

```bash
cd projects/echarts
../../.venv/bin/python dev/tests.py unit TestWidgetSnapshotProducer TestDashboardComponentReadyHook -v
```

Verified locally on 2026-07-20 with the repository virtual environment:
17 targeted tests passed, including the all-12 compiled-browser sweep.
The complete `dev/qualification.py --all` gate also passed: 1,071 unit
tests, 11 diagnostic stress scenarios, 72 adversarial validation
fixtures, all browser/runtime and persisted-input sweeps, and every
aesthetic fixture.

These commands must be adjusted only if the re-opened live checkout
uses different test module or runner names; do not weaken or omit the
listed assertions to fit a runner.

### Owned/shared browser smoke

Owned dashboard:

```text
[ ] Natural drag works for chart, kpi, table, data_grid, pivot,
    stat_grid, tool, user_input, note, titled image
[ ] Semantic markdown uses note head
[ ] Plain markdown, untitled image, divider each get one injected grip
[ ] Change chart controls / table sort-search / pivot / tool inputs,
    then drag; transported view_snapshot matches the visible current view
[ ] user_input text/checklist resolves current server revision
[ ] files mode shows metadata + authorized refs and no bytes
[ ] stale template with same id/kind submits with explicit stale status
[ ] missing/malformed/oversized snapshot blocks fire-off and chat visibly
[ ] four near-cap view snapshots pass; recomputed aggregate above
    1,048,576 fails regardless of canonical-definition bytes
[ ] tab switch, reload, history view, and run replay preserve all three
    snapshot transport fields
```

Shared/non-owner dashboard:

```text
[ ] Composer may render under the existing product flag
[ ] no natural header is draggable
[ ] no injected grip exists
[ ] forged dashboard_component POST is rejected by owner/identity gate
```

Stored artifact:

```text
[ ] S3 dashboard.html remains byte-identical before/after serving
[ ] file:// dashboard has no Composer dependency or injected grip
[ ] no snapshot endpoint/object exists
```

---

## Verified 2026-07-19 as-landed baseline

Everything from this heading through the baseline/open-items material
describes the reviewed 2026-07-19 working tree. It explains the seams
the required build extends. The local producer described above landed
after this baseline; none of this historical material asserts that the
required all-12 transport/consumer contract is present in live
`prism-main`.

### Baseline file inventory

#### Baseline parent-tree additions

| File | ~lines | Role |
|---|---:|---|
| `web/backend_django/news/dashboard_composer.py` | 126 | Leaf string-splice injector for compiled `dashboard.html` |
| `web/prism_site/js/dashboard_composer.js` | 205 | Owner-only component-drag boot (sources only) |
| `web/backend_django/news/composer_prompt.py` | 191 | SSOT prompt builder for email fire-off + inline SSE chat |

#### Baseline parent-tree edits

```text
web/backend_django/news/composer_views.py      +452; endpoints 5 -> 7 (+/chat/, +/delete/)
web/backend_django/news/composer_email.py      large net deletion; thin prompt wrapper + question-grouped history
web/backend_django/news/composer_artifacts.py  +123; dashboard_component branch; server-side path authority
web/backend_django/news/views.py              +50; injector call + canonical template hash
web/prism_site/js/composer.js                 +705; multi-tab, DND modes, resize, history, inline polish
web/prism_site/css/composer.css               large simplification + new chrome
web/prism_site/run.py                         enable_inline_chat False -> True  (local-dev risk)
entrypoint.py                                 SITE_DEFAULT_PORT 8501 -> 8502   (local-dev risk)
core/configs/access_control_lists.py          THREAD_ACL adds goyalri         (local-dev risk)
```

#### Baseline submodule edits

```text
dashboards/rendering.py                       +36; ready event, widgets export, brand-home
prism_mcp/utils/chart_functions.py            +47; source= kwarg on composites/grids
context/modules/static/tools/chart_context.md +15; documents source=
prism_mcp/utils/skill_crud_functions.py       +6; update_skill re-derives id from file_name
```

#### Baseline submodule deletion / emptying

```text
context/modules/static/developer/website_dev.md
    was 837 lines; now empty. Registry still references the module, so
    it renders blank. Follow-up: drop the registry entry or repopulate.
```

#### Baseline out-of-scope dirty files

```text
boj_client.py
chinadata_client.py
ai_buildout_client.py
```

---

### Baseline boundary with `rendering.py`

ECharts ownership ends at a neutral runtime contract. The payload must
never contain Composer MIME types, routes, cards, prompt text, or
artifact policy.

```text
┌──────────────────────────────────────────────────────────────┐
│ echarts-payload/rendering.py                                 │
│   stable [data-tile-id] wrappers                             │
│   .tile-header / .kpi-header                                 │
│   window.DASHBOARD.widgets = WIDGET_META                     │
│   prism:dashboard:ready after initTools()                    │
│   a.brand-home -> /profile/ on header mark                   │
│   NO composer literals                                       │
└──────────────────────────────┬───────────────────────────────┘
                               │ CustomEvent
                               ▼
┌──────────────────────────────────────────────────────────────┐
│ prism-main leaf                                              │
│   dashboard_composer.py  inject mount into served HTML       │
│   dashboard_composer.js  owner-only drag sources             │
│   composer.js            drop / card / tabs / chat / history │
│   composer_artifacts.py  resolve dashboard_component         │
│   composer_prompt.py     SSOT prompt text                    │
│   composer_views.py      /api/composer/*                     │
└──────────────────────────────────────────────────────────────┘
```

#### Baseline serve path (stored bytes stay Composer-free)

```text
compile_dashboard()
    -> S3 .../dashboard.html          (no Composer)
              |
              v
public_user_dashboard_detail
    -> _inject_prism_globals (before </head>)
    -> inject_dashboard_composer(html, enable_inline_chat=FEATURE_FLAGS["enable_inline_chat"])
              |
              v
         served response only

Observatory / developer detail routes: no injector.
Profile / Community detail aliases: 301 into the user route.
```

#### Baseline injector block (`dashboard_composer.py`)

`inject_dashboard_composer(html, enable_inline_chat=False)` splices
before the last `</body>`:

```text
1. scoped --gs-uitk-* tokens on #prism-composer-root  (_COMPOSER_TOKENS_STYLE)
2. /static/css/composer.css
3. <div id="prism-composer-root"></div>
4. window.PRISM_COMPOSER_INLINE_CHAT = <flag from caller>
5. window.PRISM_COMPOSER_DND_MODE = "dashboard_components"
6. deferred /static/js/composer.js
7. deferred /static/js/dashboard_composer.js
```

Design notes baked into the injector:

- SSOT of Composer appearance/behavior is still shared
  `/static/js/composer.js` + `/static/css/composer.css` (same files
  `base.html` loads). The injector adds no parallel UI.
- `_COMPOSER_TOKENS_STYLE` is a rendering shim: compiled dashboards lack
  `base.html` `:root`, so without the scoped tokens `composer.css`
  would fall back to its inline defaults.
- `enable_inline_chat` is passed from the view via
  `FEATURE_FLAGS["enable_inline_chat"]` — dashboard Composer follows the
  same site flag as Portal Composer (no longer hard-forced off).
- `PRISM_COMPOSER_DND_MODE = "dashboard_components"` restricts DND to
  that artifact type and disables file upload + generic Portal source
  scanning.

Legacy `PRISM_COMPOSER_DISABLE_DND === true` still maps to mode
`'disabled'` inside `composer.js::init()` for older callers.

#### Baseline ready hook (snapshot method absent)

```javascript
window.DASHBOARD = {
  // ...existing fields...
  widgets: WIDGET_META,
};

document.dispatchEvent(new CustomEvent('prism:dashboard:ready', {
  detail: { dashboard: window.DASHBOARD }
}));
```

Dispatched once after `initTools()`. Staging gates:
`TestDashboardComponentReadyHook`, gallery
`dev/_gallery_component_ready_hook.py`. Forbidden in `rendering.py`:
`application/x-prism-artifact`, `/api/composer/`, `dashboard_component`.

#### Baseline brand-home (submodule + staging)

Header GS/Prism mark is wrapped:

```html
<a class="brand-home" href="/profile/" ...>
```

Footer mark stays unlinked. Matching CSS lives beside the other chrome
rules in `rendering.py`. Gallery: `dev/_gallery_brand_home_link.py`.

---

### Baseline component drag (`dashboard_composer.js`)

The reviewed code is an owner-only, sources-only boot. Drop side stays
in generic `composer.js`.

#### Baseline two-latch startup (no polling)

```text
composerReady   <- window.ComposerManager present (composer.js executed)
dashboardReady  <- prism:dashboard:ready OR window.DASHBOARD already set
bind once when both latches are true
```

```javascript
function maybeBind() {
  if (_bound) return;
  if (!_composerReady || !_dashboardReady) return;
  _bound = true;
  bindComponentDrag(_dashboardObj);
}
```

#### Baseline eligibility replaced by the required build

The 2026-07-19 reviewed working tree allowed only six kinds:

```javascript
var ALLOWED_KINDS = {
  chart: 1, kpi: 1, table: 1, data_grid: 1, pivot: 1, stat_grid: 1
};
```

In that baseline, markdown, note, image, tool, divider, and the
subsequently added `user_input` surface had no handle. This is historical
evidence, not the target allowlist; the exact 12-kind contract and grip
rules above replace it.

#### Baseline owner gate

```javascript
var viewer = window.PRISM_VIEWER || null;
var owner = window.PRISM_DASHBOARD_OWNER || null;
if (!viewer || !owner || viewer !== owner) return;
```

Non-owner served dashboards may still show the Composer panel; handles
do not bind.

#### Baseline drag mechanics

| Rule | Detail |
|---|---|
| Affordance | Header only (`.tile-header` / `.kpi-header`); never canvas/body |
| Selection | `userSelect = 'none'`; mousedown on selectable text starts drag |
| Interactive skip | `dragstart` ignores `INTERACTIVE_SELECTOR` (buttons, sort, info popovers) |
| MIME | `application/x-prism-artifact`, `effectAllowed = "copy"` |

#### Baseline browser payload replaced by the snapshot wire schema

The reviewed payload stopped at canonical identity/display fields and
did not contain a current-view snapshot:

```javascript
var payload = {
  type: 'dashboard_component',
  id: wid,
  path: ownerPath,                 // display only; not authority
  label: label,                    // "<Kind>: <title>"
  dashboard_id: dashboardId,
  widget_kind: kind,
  template_sha256: templateHash    // advisory; server resolves live
};
```

Authority fields come from PRISM globals + `window.DASHBOARD`, not from
client-supplied cross-user paths. Label format `"<Kind>: <title>"` is
hand-synced across:

```text
dashboard_composer.js
composer.js
composer_artifacts.py   (_KIND_PREFIX map)
```

so optimistic cards do not flip when artifact-info returns.

The required MIME object is the ten-field object specified above.
Fire-off/chat must reject this historical seven-field shape rather than
falling back to canonical-only content.

---

### Baseline DND mode enum (`composer.js`)

```javascript
var DND_MODE = 'standard'; // 'standard' | 'disabled' | 'dashboard_components'
var DND_DISABLED = false;  // derived
var DND_COMPONENTS = false; // derived
```

Resolved in `init()` from `window.PRISM_COMPOSER_DND_MODE`. Legacy
`PRISM_COMPOSER_DISABLE_DND === true` maps to `'disabled'`.

| Mode | Drop target | File upload | Generic source scan | Allowed types |
|---|---|---|---|---|
| `standard` | on | on | on | Portal set |
| `disabled` | off | off | off | — |
| `dashboard_components` | on | off | off | `dashboard_component` only |

In `dashboard_components` mode the drop hint reads
"Drag a dashboard component header here..." and generic Portal
drag-source injection is skipped.

---

### Baseline prompt SSOT (`composer_prompt.py`)

Single builder for every Composer media path (email fire-off and inline
SSE chat):

```python
def build_composer_prompt(user_message, artifact_contents):
    # 1. user message first          (### Request)
    # 2. reference lines             (### Attached Artifacts)
    # 3. inlined bodies framed/type
    return "\n\n".join(parts)
```

Routing constants:

```python
_INLINE_BODY_TYPES = ('skill', 'preference', 'dashboard_component')
_REFERENCE_ONLY_TYPES = ('cabinet',)
_NON_ATTACHED_TYPES = _INLINE_BODY_TYPES + _REFERENCE_ONLY_TYPES
```

The baseline inlines `dashboard_component` (the canonical widget
specification JSON in `content_summary`) rather than a one-line pointer.
The required build keeps it inlined but replaces that body with the
exact server-owned-definition + bounded-current-view component object
above. `_NON_ATTACHED_TYPES` is imported by `composer_email.py` so
attach/reference/inline policy remains in one leaf.

Skill framing deliberately avoids "apply" language (users may be
editing). Legacy `APPLY THIS SKILL:` prefix is stripped at the resolver.

`composer_email.compose_email_body` is a thin wrapper:

```python
def compose_email_body(user_message, artifact_contents):
    from web.backend_django.news.composer_prompt import build_composer_prompt
    return build_composer_prompt(user_message, artifact_contents)
```

Chat path (`_build_chat_prompt`) uses the same builder, then appends a
consolidated `get_s3_files` batch for referenced non-skill paths.

---

### Baseline artifact resolver (`composer_artifacts.py`)

`read_artifact_content(artifact, kerberos)` gains a `dashboard_component`
branch:

1. Never trusts client `art_path` as authority.
2. Reconstructs `users/{kerberos}/dashboards/{dashboard_id}` from
   authenticated Kerberos.
3. Rejects any cross-user reference (`segs[1] != kerberos`).
4. Reads `manifest_template.json` (tabbed or flat layout).
5. Requires exactly one matching widget id; kind must be in
   `_ALLOWED_KINDS`.
6. Resolves the template **live** from `(dashboard_id + widget_id)`.
   Client-pinned `template_sha256` is not used as a reject gate —
   captured hashes are a TOCTOU trap against refresh-varying resolved
   data after a re-PUT.
7. Serializes the matched widget spec into inline JSON in
   `content_summary`.
8. Labels via hand-synced `_KIND_PREFIX` → `"<Kind>: <title>"`.

`artifact_info_api` collapses its ~100-line per-type switch into a
delegation to `read_artifact_content`, maps to `{label, preview}` for
the drag card, drops `@csrf_exempt` (plain GET), and passes through
`dashboard_component` fields so live widget resolution matches the
owner-scoped path.

---

### Baseline Composer views / SSE / history

#### Baseline fail-loud manifest read

`_get_manifest` no longer swallows S3/JSON errors. Missing path returns
`[]`; corrupt JSON raises.

#### Baseline inline chat persistence

`_persist_chat_record` writes completed inline turns into the
`fire_offs/` store with `mode='inline'` and a full transcript
(thinking, answer, error) so History can view/replay them.

#### Baseline SSE classification

Old `is_thinking_token()` misclassified answer tokens as thinking
(everything rendered in the thinking pane). New logic keys strictly on
`chunk_type`:

```python
if chunk_type == 'response':
    final_buffer.append(data)
    yield _sse_frame('final', {'text': data, 'accumulated': ''.join(final_buffer)})
elif data.strip() not in SUPPRESSED_MESSAGES:
    yield _sse_frame('thinking', {'text': data})
```

Tool-call events are dropped entirely during thinking-only streams.
UI receives a clear `final` frame.

#### Baseline replay

`replay_api` gains `mode='view'` (read-only stored response) and threads
`question_id` so a re-run appends under the same question instead of
superseding it.

#### Baseline dev email of exact prompt

Every `/chat/` call fail-soft fires the exact Prism prompt to
`DEV_NOTIFICATION_RECIPIENT` via `_email_prompt_to_dev`.

#### Baseline question-grouped history (`persist_fire_off_record`)

Manifest holds one row per **QUESTION**; each fire-off is a **RUN**
appended under it:

```text
question_id set           -> append run to that question
supersedes_id only        -> adopt superseded id as question_id (legacy)
neither                   -> open new question; id = this fire_off_id
```

Stamps `mode` (`'email'` default, `'inline'` for chat). Migrates legacy
flat rows into a `runs[]` schema. Preview helpers
`_strip_sentinels` / `_strip_artifact_prefix` keep History cards clean.

Browser History UI (`renderHistory`):

- question row with expand/collapse and `(N Plays)`
- runs newest-first; `[View]` (email runs greyed as "(Emailed)")
- question-level `Replay`; `deleteHistoryItem` deletes the whole group
- `viewRun` calls replay with `mode='view'`
- send/replay thread on `question_id`, not `supersedes`

---

### Baseline generic Composer UX batches (`composer.js` / CSS)

#### Multi-tab (Batch 4a)

Thin tab layer over singleton `state` (active tab). Per-tab blobs under
`STORAGE_KEY + ':' + id`; tab list + `activeTabId` under `TABS_KEY`.
Chrome-style strip via `renderTabStrip`; `switchTab` / `newTab` /
`closeTab` / `ensureTabs()` (migrates legacy single-tab state).

#### Panel resize (Batch 4b)

`.composer-panel__resize-handle` at top-left; bottom-right anchored so
growing expands toward top-left. Size persisted under `SIZE_KEY`,
re-applied by `applyPanelSize` after each render.

#### Inline chat polish (Batch 1)

- TO/CC rows hidden when `_inline` is hoisted
- thinking pane is a wrapping `<div>` (no tool chips / `tools[]`)
- newline-separated thinking chunks; `_collapseThinkingPane()` once
  answer rendering begins
- `chat-copy` copies raw markdown (Clipboard API + `execCommand` fallback)
- dropped-context recap of dragged cards for the turn
- one-shot `marked` re-render if the library was not ready at first paint

#### Baseline `dashboard_component` drop handling

Preserves `dashboard_id`, `template_sha256`, `widget_kind`; normalizes
labels to `"<Kind>: <title>"` at drop time; `resolveArtifactInfo`
forwards extra validation fields on the query string.

The required build additionally preserves top-level
`snapshot_schema_version`, `snapshot_bytes`, and `view_snapshot`
through every state/history layer and keeps all three out of the
artifact-info query.

#### CSS

Large net deletion of obsolete inline-chat / tool-chip styling; additive
rules for tab strip, resize handle, thinking `div`, chat-context recap,
and run rows.

---

### Baseline canonical template hash (`views.py`)

False "stale dashboard-component" triggers came from inconsistent S3
NUL padding and JSON key order. New helper:

```python
def _canonical_template_hash(raw):
    stripped = (raw or b'').rstrip(b'\x00')
    canonical = json.dumps(
        json.loads(stripped.decode('utf-8')),
        sort_keys=True, separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()
```

`_compute_template_hash` and `dashboard_data_api` route through it.
This is independent of the resolver's live `(dashboard_id + widget_id)`
lookup — the hash still feeds `PRISM_TEMPLATE_HASH` for the served page.

---

### Baseline adjacent submodule changes (not Composer UX)

#### `source=` on Altair chart helpers

First-class `source=` kwargs on `make_composite`, `make_2pack_*`,
`make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid`,
`render_grid`. `ChartSpec` / `Chart` gain a `source` field. Unset
caption → `Source: {source}`; explicit caption wins. `make_table` fills
source after `rows= -> df` resolution. Documented in `chart_context.md`.
Owner: `projects/altair/`, not this echarts stack — listed here only
because it rode the same submodule diff.

#### `update_skill` id re-derive

`skill_crud_functions.update_skill` re-derives `id` from the (possibly
renamed) `file_name` in the returned dict so
`get_skill_body(returned["id"])` cannot resolve a stale handle. Tangential
to Composer skill-attach.

#### Emptied `website_dev.md`

837-line developer guide wiped; registry entry still present → blank
module. Follow-up outside Composer Stage 2b.

---

### Baseline config toggles — commit hygiene

| File | Change | Treat as |
|---|---|---|
| `web/prism_site/run.py` | `enable_inline_chat: False -> True` | Likely intentional product flip; confirm before commit |
| `entrypoint.py` | port `8501 -> 8502` | Local dev-instance; do not commit |
| `core/configs/access_control_lists.py` | add `goyalri` to `THREAD_ACL_SYSTEM_KERBEROS` | Local privilege; do not commit |

The 2026-07-19 review also noted intermediate staging of new-client
files with empty staged blobs — inspect index vs working tree before any
commit that includes `dashboard_composer.*`.

---

### Baseline contract flips vs 2026-07-18 staging docs

These prior claims are superseded:

| Prior (2026-07-18) | As-landed baseline (2026-07-19 review) |
|---|---|
| Stage 2b open | Landed in PRISM working tree |
| `PRISM_COMPOSER_DISABLE_DND = true` on dashboards | `PRISM_COMPOSER_DND_MODE = "dashboard_components"` |
| Dashboard inline chat forced off | Flag passed from `FEATURE_FLAGS["enable_inline_chat"]` |
| `dashboard_component` is reference-only (one pointer line) | Inlined body type; full widget JSON in prompt |
| Client `template_sha256` must match or stale-error | Live resolve; client hash is not a reject gate |
| Label `"<dashboard> · <component>"` | `"<Kind>: <title>"` (3-file sync) |
| Prompt built inside `composer_email.py` | SSOT `composer_prompt.py`; email is thin wrapper |
| Flat fire-off history + supersede | Question-grouped versioned `runs[]` |
| Inline chat ephemeral (no history) | Persisted as `mode='inline'` runs |
| SSE uses `is_thinking_token()` + tool frames | `chunk_type == 'response'`; tools dropped |
| Coarse boolean DND only | Mode enum `standard` / `disabled` / `dashboard_components` |

---

## Open implementation and adjacent items

```text
[x] Implement and test neutral getWidgetSnapshot() in canonical payload
[x] Align producer file MIME input (`detected_mime`) and its Node fixture
[x] Add compiled-browser getWidgetSnapshot() sweep across all 12 kinds
[ ] Promote required ECharts payload files into reconciled prism-core
[ ] Prove canonical payload / installed-file byte parity
[ ] Implement composer_dashboard_snapshot.py and required prism-main edits
[ ] Run the exact unit/integration and owned/shared smoke gates above
[ ] Confirm enable_inline_chat product intent vs local-dev flag
[ ] Drop or repopulate emptied website_dev.md + registry entry
[ ] Stage 3 typed-operation builder (explicitly excluded)
[ ] Shared-dashboard component dragging remains excluded; owner-only stands
[ ] Whole-dashboard index.html vs dashboard.html attachment naming
    (pre-existing; separate from component path)
```
