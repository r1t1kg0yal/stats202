# Manifest operations

- **Context ID:** `echarts.manifest_ops`
- **Owns:** `manifest.schema`, `manifest.selector`, `manifest.transaction`, `manifest.concurrency`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#manifest-skeleton) and the affected primitive owner.

This file is the sole owner of edits to an existing `manifest_template.json`. Use the public operation API; do not write row-traversal code or replace the root.

## Manifest operations

```python
from dashboards import apply_manifest_operations, inspect_dashboard

state = inspect_dashboard(FOLDER)
result = apply_manifest_operations(
    FOLDER,
    operations=[...],
    expected_sha256=state["manifest_template_sha256"],
    recompile=True,
)
```

Operations execute in list order against one working copy, so later operations see earlier results. The engine stamps canonical `metadata.kerberos` and `metadata.dashboard_id`, validates persistence metadata, writes the template, synchronizes refresh cadence when changed, and optionally calls `build_dashboard`.

## Operation schemas

Unknown keys and missing required keys are rejected.

| `op` | Required fields | Optional fields |
|---|---|---|
| `add_widget` | `widget`, `destination` | none |
| `update_widget` | `selector`, `patch` | none |
| `remove_widget` | `selector` | none |
| `move_widget` | `selector`, `destination` | none |
| `add_tab` | `tab` | `index` |
| `update_tab` | `selector`, `patch` | none |
| `remove_tab` | `selector` | none |
| `move_tab` | `selector`, `index` | none |
| `add_filter` | `filter` | `index` |
| `update_filter` | `selector`, `patch` | none |
| `remove_filter` | `selector` | none |
| `move_filter` | `selector`, `index` | none |
| `add_dataset` | `name`, `dataset` | none |
| `update_dataset` | `name`, `patch` | none |
| `remove_dataset` | `name` | none |
| `patch_dashboard` | `patch` | none |
| `patch_metadata` | `patch` | none |

Generic `replace`, `replace_root`, `replace_manifest`, `set_manifest`, and `write_manifest` operations are forbidden.

## Dashboard operations

`patch_dashboard` is the only typed path for approved root presentation fields:

```python
result = apply_manifest_operations(
    FOLDER,
    [{
        "op": "patch_dashboard",
        "patch": {
            "title": "TIPS Relative Value Monitor",
            "description": "Cross-sectional TIPS valuation and carry.",
            "theme": "gs_clean",
            "palette": "gs_diverging",
        },
    }],
    expected_sha256=state["manifest_template_sha256"],
)
```

The approved keys are `title`, `description`, `theme`, and `palette`; values are strings, and title/theme/palette are non-empty. Unknown root keys are rejected. Dashboard summary is not a top-level field: patch `metadata.summary` with `patch_metadata`. Root title changes must use `patch_dashboard`, never `patch_metadata` or a root replacement.

Safe title rename flow: inspect → capture `manifest_template_sha256` and current title → apply one `patch_dashboard` operation with that expected SHA and `recompile=True` → require the result hashes to agree with inspection → run clean refresh → inspect and confirm the new title while `id`, folder, tabs, widgets, filters, links, registry `created_at`, and cadence remain unchanged.

## Selectors and destinations

Widget, tab, and filter mutations select exactly one stable id:

```python
{"selector": {"id": "curve"}}
```

The selector object must contain only `id`, and the id must match exactly once. Read valid ids from `inspect_dashboard`:

- widgets: `state["graph"]["widgets"]`;
- filters: `state["graph"]["filters"]`;
- tabs: widget `tab_id` values plus the current template when tab metadata is needed.

Widget destinations:

```python
# Grid layout
{"row": 1}                  # append to row 1
{"row": 1, "index": 0}     # insert at position 0

# Tabs layout
{"tab_id": "overview", "row": 1}
{"tab_id": "overview", "row": 1, "index": 0}
```

`row` is a non-negative integer. It may select an existing row or equal `len(rows)` to append one new row; it may not skip row indices. `index` defaults to row end and must be within `0..len(row)`. `tab_id` is required for tabs and forbidden for grids.

## Widget operations

```python
operations = [
    {
        "op": "add_widget",
        "widget": {
            "widget": "chart",
            "id": "real_curve",
            "w": 6,
            "title": "Real yield",
            "spec": {
                "chart_type": "line",
                "dataset": "rates",
                "mapping": {"x": "date", "y": "real_10y"},
            },
        },
        "destination": {"tab_id": "overview", "row": 1},
    },
    {
        "op": "update_widget",
        "selector": {"id": "curve"},
        "patch": {"title": "Nominal curve"},
    },
    {
        "op": "move_widget",
        "selector": {"id": "real_curve"},
        "destination": {"tab_id": "overview", "row": 0, "index": 1},
    },
]
```

`add_widget.widget` is a complete widget with a unique stable id. `update_widget.patch` is a non-empty shallow field patch. If an update renames the widget id, the engine updates filter targets and link members. `move_widget` preserves the widget and its relationships.

`remove_widget` removes the widget, prunes empty rows, removes the id from filter targets and link members, drops relationships that become empty, and removes dependent filter/show conditions when their filter disappears.

## Tab operations

Tab operations require `layout.kind == "tabs"`.

```python
[
    {
        "op": "add_tab",
        "tab": {"id": "credit", "label": "Credit", "rows": []},
        "index": 1,
    },
    {
        "op": "update_tab",
        "selector": {"id": "credit"},
        "patch": {"label": "Credit risk", "description": "IG and HY"},
    },
    {
        "op": "move_tab",
        "selector": {"id": "credit"},
        "index": 0,
    },
]
```

`add_tab` requires a unique id; omitted `index` appends. `update_tab` may patch tab metadata but may not replace `rows`; use widget operations. `remove_tab` removes its widgets and cleans dependent filter/link references. Validation rejects a tabs layout left with no valid tabs.

## Filter operations

```python
[
    {
        "op": "add_filter",
        "filter": {
            "id": "region",
            "type": "multiSelect",
            "field": "region",
            "options": ["US", "EU", "JP"],
            "default": ["US", "EU"],
            "targets": ["curve", "table"],
        },
    },
    {
        "op": "update_filter",
        "selector": {"id": "region"},
        "patch": {"label": "Region"},
    },
]
```

`add_filter` requires a unique id. `update_filter` is a shallow patch; id renames update downstream `depends_on` and widget `show_when` references. `remove_filter` removes dependent `depends_on` links and strips its `show_when` clauses. `move_filter.index` is the final zero-based position.

Use [filters.md](filters.md#filter-catalog) for filter schemas, links, sync modes, and brush types.

## Dataset operations

```python
[
    {
        "op": "add_dataset",
        "name": "real_rates",
        "dataset": {
            "source": [],
            "template": True,
            "schema": {"date": "datetime", "real_10y": "float"},
        },
    },
    {
        "op": "update_dataset",
        "name": "rates",
        "patch": {
            "schema": {
                "date": "datetime",
                "us_2y": "float",
                "us_10y": "float",
                "real_10y": "float",
            },
        },
    },
]
```

Dataset `name` is the exact slot/CSV stem. `add_dataset` rejects an existing name; `update_dataset` requires an existing object slot and applies a shallow patch.

Template dataset `source` is a header-only list, not a CSV path. If an inherited slot incorrectly stores a path string, use the persisted-path evidence to select the canonical stem and replace the unsupported source shape:

```python
apply_manifest_operations(
    FOLDER,
    [{
        "op": "update_dataset",
        "name": "rates",
        "patch": {
            "source": [["date", "us_10y_pct"]],
            "template": True,
        },
    }],
    expected_sha256=state["manifest_template_sha256"],
)
```

The next build populates that slot from `data/rates.csv`, derived from dataset name `rates`. Do not author `source_path`, `csv_path`, or a string `source`; if the canonical persisted stem itself is wrong, repair the owning pull/transform first.

`remove_dataset` is intentionally cascading: it removes the slot, every widget that references it, empty rows, affected filter targets/filters, `options_from` filters using it, dependent filter/show conditions, and empty links. Use only when destructive product intent is explicit and the inspection graph confirms every consumer should disappear.

Adding or changing a slot does not create data. Coordinate the matching producer through [pipelines.md](pipelines.md#pipeline-reuse-decision).

## Metadata operations

```python
[
    {
        "op": "patch_metadata",
        "patch": {
            "summary": {
                "title": "Today's read",
                "body": "Front-end rates led the move.",
            },
            "tags": ["rates", "macro"],
        },
    }
]
```

Metadata patches are shallow. Do not set `kerberos` or `dashboard_id` to values that conflict with the folder; the engine stamps canonical identity. A `refresh_frequency` patch also updates the matching registry entry in the same transaction. The registry must already contain exactly one matching dashboard.

Use `patch_metadata` for exact authored `methodology`, `tags`, `summary`, `sources`, and other metadata fields. Supply the complete replacement value for each patched key; a shallow patch does not merge inside `summary`.

For cadence-only edits, call `synchronize_refresh_frequency` directly.

## Transaction, rollback, and concurrency

Before mutation the engine:

1. requires a canonical folder and all five required files;
2. snapshots template, registry, compiled manifest, and HTML;
3. hashes the template bytes;
4. rejects a mismatched `expected_sha256`;
5. deep-copies the decoded template.

It then applies operations in order, stamps identity, validates, writes, synchronizes cadence if needed, and recompiles when requested.

Any write, cadence, validation, or recompile failure restores all snapshotted keys to their prior existence and bytes. The raised error states whether rollback completed or names rollback failures. Treat the whole operation list as uncommitted when it raises; inspect again before retrying.

On success, the serialized result includes `pre_sha256`, `post_sha256`, and `rollback_sha256`; `rollback_sha256` equals the exact pre-transaction template hash retained for restoration. Verify `pre_sha256 == expected_sha256`, `post_sha256 == inspect_dashboard(FOLDER)["manifest_template_sha256"]`, and `rollback_sha256 == pre_sha256`. For an expected failure, prove restoration by re-inspecting the template SHA and comparing the snapshotted template, registry, compiled manifest, and HTML bytes; a successful rollback leaves all four byte-identical to their pre-transaction state.

`expected_sha256` is the optimistic concurrency guard. Always pass the hash from the inspection that informed the edit. On mismatch:

1. inspect again;
2. compare the current graph/template intent to the planned operations;
3. rebase the operations;
4. retry with the current hash.

Never suppress the guard by reusing stale template bytes.

## Recompile choice

`recompile=True` is the default and the standard for user-visible manifest edits. It rebuilds against current persisted data and rolls back on compile failure.

`recompile=False` commits a validated template-only transaction. Use it only inside a larger atomic flow that will provide required data and compile before the user sees a result. It does not prove mappings resolve against data.

After the final operation batch, run the clean refresh path and inspect again.

## Concise patterns

### Add a widget and retarget a filter

```python
apply_manifest_operations(
    FOLDER,
    [
        {
            "op": "add_widget",
            "widget": NEW_CHART,
            "destination": {"tab_id": "overview", "row": 2},
        },
        {
            "op": "update_filter",
            "selector": {"id": "lookback"},
            "patch": {"targets": ["curve", NEW_CHART["id"]]},
        },
    ],
    expected_sha256=state["manifest_template_sha256"],
)
```

### Change a tool default without touching compute code

`update_widget.patch` is shallow, so read the current tool widget from the inspected/current template, copy its complete `tool_def`, change `inputs[].default`, and patch `{"tool_def": updated_tool_def}`. Do not replace the entire widget or interpolate Python values into `compute_js`.

### Rename a widget safely

```python
apply_manifest_operations(
    FOLDER,
    [{
        "op": "update_widget",
        "selector": {"id": "curve_old"},
        "patch": {"id": "curve_current"},
    }],
    expected_sha256=state["manifest_template_sha256"],
)
```

The engine rewrites filter targets and link members.

## Destructive intent

Removing a tab, dataset, or relationship may delete multiple user-visible surfaces through dependency cleanup. Before applying:

- inspect the consumer graph;
- state the product impact internally;
- require explicit user intent when the visible result is ambiguous;
- prefer targeted widget/filter removal when only one surface should disappear.

Do not present engine implementation choices to the user.
