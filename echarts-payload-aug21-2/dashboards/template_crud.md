# Manifest operations

- **Context ID:** `echarts.manifest_ops`
- **Owns:** `manifest.schema`, `manifest.selector`, `manifest.transaction`, `manifest.concurrency`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#manifest-skeleton) and the affected primitive owner.

This file is the sole owner of edits to an existing `manifest_template.json`. Use the public operation API; do not write row-traversal code or replace the root.

## Manifest operations

```python
from dashboards import (
    DashboardReviewRequired,
    describe_dashboard,
    apply_manifest_operations,
    publish_dashboard,
    review_dashboard,
    launch_clean_refresh,
)

before = describe_dashboard(FOLDER)
print(before["text"])  # product floorplan — sync with the user

try:
    result = apply_manifest_operations(
        before,
        operations=[...],
        recompile=True,
    )
except DashboardReviewRequired:
    review = review_dashboard(FOLDER)
    print(review.to_text())
    for panel in review.panels:
        if panel.status != "CLEAR":
            print(review.panel(panel.panel_id).to_text())
    published = publish_dashboard(
        FOLDER,
        rationale=(
            "Reviewed <panel ids or CLEAR index>; accepted "
            "<finding or CLEAR baseline> because <evidence>."
        ),
        expected_current_version_id=before["versioning"]["current_version_id"],
    )

launch_clean_refresh(FOLDER)
after = describe_dashboard(FOLDER)
print(after["text"])
```

Passing a `describe_dashboard` or `inspect_dashboard` state into
`apply_manifest_operations` supplies `manifest_template_sha256` and
`versioning.current_version_id` automatically. Do not hand-copy those
guards unless you are targeting the folder string alone.

Operations execute in list order against one working copy, so later operations see earlier results. The engine stamps canonical `metadata.kerberos` and `metadata.dashboard_id`, validates persistence metadata, writes the template, synchronizes refresh cadence when changed, and optionally calls `build_dashboard`. A successful changed build automatically records the template plus both persisted scripts as one immutable definition version; `recompile=False` remains dirty until a later successful build.

When the pre-edit review is already publish-ready and the edit does not change the review signature, `recompile=True` builds inside the transaction — no separate publish call is required. When `recompile=True` raises `DashboardReviewRequired`, the candidate template is kept; complete the publish path with a substantive rationale.

On direct success, `result["manifest_template"]` is the exact post-edit
data-free definition and `result["compiled_manifest"]` is its populated
manifest when `recompile=True`. On the review-required branch,
`published["manifest"]` is the populated post-publish manifest. Use these
structured returns to verify the target and unchanged siblings; the final
`describe_dashboard` verifies the persisted hash and visible floorplan.

## Patch merge semantics

`update_widget`, `update_filter`, `update_tab`, `update_dataset`, and
`patch_metadata` deep-merge nested **dicts**. **Lists** and scalars
**replace**. Explicit JSON/`None` **clears** that key.

Leaf dict edits do not require copying sibling subtrees:

```python
{
    "op": "update_widget",
    "selector": {"id": "bond_table"},
    "patch": {
        "row_click": {
            "detail": {
                "title": "Bond detail",
            },
        },
    },
}
```

When changing one element inside a list (for example `tool_def.inputs`
or `detail.sections`), replace that list with the full intended value;
sibling dict keys under the same parent still deep-merge and are preserved.

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
    before,
    [{
        "op": "patch_dashboard",
        "patch": {
            "title": "TIPS Relative Value Monitor",
            "description": "Cross-sectional TIPS valuation and carry.",
            "theme": "gs_clean",
            "palette": "gs_diverging",
        },
    }],
    recompile=True,
)
```

The approved keys are `title`, `description`, `theme`, and `palette`; values are strings, and title/theme/palette are non-empty. Unknown root keys are rejected. Dashboard summary is not a top-level field: patch `metadata.summary` with `patch_metadata`. Root title changes must use `patch_dashboard`, never `patch_metadata` or a root replacement.

Safe title rename flow: `describe_dashboard` → apply one `patch_dashboard` with state-supplied guards and `recompile=True` → publish when required → clean refresh → `describe_dashboard` again and confirm the new title while `id`, folder, tabs, widgets, filters, links, registry `created_at`, and cadence remain unchanged.

## Selectors and destinations

Widget, tab, and filter mutations select exactly one stable id:

```python
{"selector": {"id": "curve"}}
```

The selector object must contain only `id`, and the id must match exactly once. Read valid ids from `describe_dashboard` (`layout_text` / `text`) or `inspect_dashboard`:

| Surface | Describe / inspect source |
|---|---|
| Widgets | `layout_text` tokens, or `widgets.by_id` / `widgets.ordered` |
| Tabs | `tabs`, or tab headers in `layout_text` |
| Filters | `filters_text`, or `filters.by_id` / `filters.ordered` |
| Datasets | `counts.datasets` plus consumer tokens in `layout_text`, or `datasets` |

Destinations place a widget:

| Destination | Meaning |
|---|---|
| `{"row": N}` | Append to row `N` of a grid layout |
| `{"row": N, "index": I}` | Insert at index `I` in that row |
| `{"tab_id": "...", "row": N}` | Append inside the named tab |
| `{"tab_id": "...", "row": N, "index": I}` | Insert inside the named tab |

`tab_id` is required for tabbed layouts and forbidden for grid layouts. Missing rows are created as empty lists through the requested index. Negative indexes and out-of-range insert indexes are rejected.

## Widget operations

`add_widget.widget` is a complete widget with a unique stable id. `update_widget.patch` is a non-empty deep-merge field patch (lists replace). If an update renames the widget id, the engine updates filter targets and link members. `move_widget` preserves the widget and its relationships.

`remove_widget` deletes the widget and cleans dependent filter targets, link membership, and `show_when` clauses that named it. Empty rows left behind are removed.

For `user_input`, manifest operations change only the widget definition. Preserve its stable `id` and `mode` after first save; persisted text, checklist state, and uploaded files are separate and must not appear in a manifest patch.

## Tab operations

Tab layouts only. `add_tab.tab` must include `id`, `label`, and `rows` (use `[]` for an empty tab). `update_tab` may change metadata such as `label`; it cannot replace `rows` wholesale — use widget operations. `remove_tab` removes the tab and cleans relationships for every widget it contained. `move_tab.index` is the final zero-based position.

## Filter operations

`add_filter` requires a unique id. `update_filter` deep-merges dict fields (lists replace); id renames update downstream `depends_on` and widget `show_when` references. `remove_filter` removes dependent `depends_on` links and strips its `show_when` clauses. `move_filter.index` is the final zero-based position.

## Dataset operations

Dataset `name` is the exact slot/CSV stem. `add_dataset` rejects an existing name; `update_dataset` requires an existing object slot and deep-merges the patch.

`remove_dataset` is cascading and irreversible inside the transaction:

1. delete the dataset slot;
2. remove every widget that references it;
3. remove filters whose `options_from.dataset` equals that name;
4. clean filter targets, links, and `show_when` clauses for the removed widgets and filters.

Prefer removing a single widget when only one surface should disappear. Require explicit user intent before a cascade that changes multiple visible panels.

## Metadata and cadence

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

Metadata patches deep-merge nested dicts (`summary.title` can change without rewriting `summary.body`). List-valued keys such as `tags` replace. Do not set `kerberos` or `dashboard_id` to values that conflict with the folder; the engine stamps canonical identity. A `refresh_frequency` patch also updates the matching registry entry in the same transaction. The registry must already contain exactly one matching dashboard.

Use `patch_metadata` for authored `methodology`, `tags`, `summary`, `sources`, and other metadata fields. For cadence-only edits, call `synchronize_refresh_frequency` directly.

## Transaction, rollback, and concurrency

Before mutation the engine:

1. requires a canonical folder and all five required files;
2. snapshots template, registry, compiled manifest, and HTML;
3. hashes the template bytes;
4. rejects a mismatched `expected_sha256` (inferred from describe/inspect state when passed);
5. deep-copies the decoded template.

It then applies operations in order, stamps identity, validates, writes, synchronizes cadence if needed, and recompiles when requested.

Any write, cadence, validation, or recompile failure restores all snapshotted keys to their prior existence and bytes — except `DashboardReviewRequired`, which keeps the candidate definition for the publish path. The raised error states whether rollback completed or names rollback failures. Treat a rolled-back list as uncommitted; describe/inspect again before retrying.

On success, the serialized result includes `pre_sha256`, `post_sha256`,
`rollback_sha256`, `manifest_template`, and `compiled_manifest`
(`compiled_manifest` is `None` when `recompile=False`). `rollback_sha256`
equals the exact pre-transaction template hash retained for restoration.
Verify `pre_sha256` matches the pre-edit state's template SHA,
`post_sha256 == describe_dashboard(FOLDER)["manifest_template_sha256"]`,
and `rollback_sha256 == pre_sha256`. Verify exact field-level postconditions
against `manifest_template` / `compiled_manifest`; after a review hold, use
`publish_dashboard(... )["manifest"]`.

Never suppress the concurrency guard by reusing stale state. On mismatch: describe/inspect again, rebase the operations, retry with the fresh state.

## Recompile choice

`recompile=True` is the default and the standard for user-visible manifest edits. It rebuilds against current persisted data and rolls back on compile failure (other than the review gate).

`recompile=False` commits a validated template-only transaction. Use it only inside a larger atomic flow that will provide required data and compile before the user sees a result. It does not prove mappings resolve against data.

After the final operation batch, run the clean refresh path and `describe_dashboard` again.

## Concise patterns

### Change one series color

Deep-merge the named color without copying the rest of the chart:

```python
{
    "op": "update_widget",
    "selector": {"id": "curve"},
    "patch": {
        "spec": {
            "series_colors": {
                "us_10y": {"light": "#002F6C", "dark": "#74C0E3"},
            },
        },
    },
}
```

The key must match an emitted series name or raw wide-form column. Supply both
theme colors; sibling mappings and named colors are preserved. Capture the
pre-edit map from
`before["widgets"]["by_id"]["curve"]["series_colors"]`, then verify the target
colors, complete mapping, and every pre-existing named-color entry against the
returned `manifest_template` and populated manifest (or the published manifest
after a review hold).

### Add one line from an existing dataset

`mapping.y` is a list, so replace it with the complete intended list:

```python
current_y = list(
    before["widgets"]["by_id"]["curve"]["mapping_summary"]["y"]
)
updated_y = [*current_y, "us_30y"]

{
    "op": "update_widget",
    "selector": {"id": "curve"},
    "patch": {"spec": {"mapping": {"y": updated_y}}},
}
```

The dataset must already contain the new column and the final list may contain
at most four line series. If the column is absent, update and run its persisted
producer before this manifest operation. Never guess an inherited list: read it
from `before["widgets"]["by_id"][id]["mapping_summary"]["y"]`. Verify the
complete final list in the returned populated manifest (or the published
manifest after a review hold).

### Change user-input presentation only

Deep-merge presentation fields without replacing the widget or its saved state:

```python
{
    "op": "update_widget",
    "selector": {"id": "desk_notes"},
    "patch": {
        "title": "Monday handoff",
        "description": "Shared owner-authored notes for the desk.",
        "rows": 10,
    },
}
```

Keep `id` and `mode` unchanged. Saved content is read with `read_dashboard_user_input`, not copied into this patch.

### Add a widget and retarget a filter

```python
apply_manifest_operations(
    before,
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
    recompile=True,
)
```

### Change a tool default without touching compute code

Deep-merge into `tool_def` and replace only the `inputs` list (lists do not merge by index). Sibling `tool_def` keys such as `compute_js` and `outputs` are preserved:

```python
{
    "op": "update_widget",
    "selector": {"id": "scenario_tool"},
    "patch": {"tool_def": {"inputs": updated_inputs}},
}
```

Do not replace the entire widget or interpolate Python values into `compute_js`.

### Rename a widget safely

```python
apply_manifest_operations(
    before,
    [{
        "op": "update_widget",
        "selector": {"id": "curve_old"},
        "patch": {"id": "curve_current"},
    }],
    recompile=True,
)
```

The engine rewrites filter targets and link members.

## Destructive intent

Removing a tab, dataset, or relationship may delete multiple user-visible surfaces through dependency cleanup. Before applying:

- read the describe floorplan / inspect consumer graph;
- state the product impact internally;
- require explicit user intent when the visible result is ambiguous;
- prefer targeted widget/filter removal when only one surface should disappear.

Do not present engine implementation choices to the user.
