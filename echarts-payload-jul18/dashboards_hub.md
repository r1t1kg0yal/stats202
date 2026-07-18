# ECharts dashboard kernel

- **Context ID:** `echarts.kernel`
- **Owns:** `kernel.contract`, `kernel.manifest`, `kernel.api`, `kernel.layout`, `kernel.registry`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards.md](dashboards.md#route-before-fetching).

This is the compact cross-cutting contract. It does not own first-build steps, mutation recipes, diagnosis, data pipelines, or primitive catalogs; use the [owner index](#owner-index).

## Contract

1. **Real, refreshable data.** Every visible number derives from a persisted pull or transform. KPI/stat literals and invented identifiers are forbidden.
2. **Template contains no live data.** `manifest_template.json` keeps dataset slots; `manifest.json` is populated output.
3. **Canonical order.** Pulls produce files, transforms derive datasets, the template is populated, the receipt and flagged panels are reviewed, the exact signature is acknowledged with rationale, the guarded build writes outputs, registry metadata is aligned, then a clean subprocess refresh verifies the persisted artifact.
4. **Canonical folder.** Persistent dashboards live only at `users/{kerberos}/dashboards/{dashboard_id}`.
5. **Flat CSV routing.** Every pull writes to `{folder}/data`; only CSV files become datasets, and each dataset key matches the complete emitted stem byte-for-byte.
6. **Portal handoff.** Surface only `http://reports.prism-ai.url.gs.com:8501/users/{kerberos}/dashboards/{dashboard_id}/`.
7. **Atomic work.** Do not return between steps of a build or edit. Once a response is sent, no autonomous work continues.
8. **Preserve inherited intent.** Describe before mutation on ordinary edits; inspect only for heal/triage. Use typed operations for manifests and evidence-based edits for scripts. Root replacement is forbidden.
9. **Engine diagnostics are instructions.** Follow each structured `fix_hint`, retry, and expose only product-level residue to the user.
10. **Layout sync.** On every inherited-dashboard edit, call `describe_dashboard` before and after mutation and paraphrase `text` in product language so the user and PRISM share the same floorplan. Never dump paths, SHAs, or graph internals.

## Canonical folder

```text
users/{kerberos}/dashboards/{dashboard_id}/
  manifest_template.json
  manifest.json
  dashboard.html
  scripts/
    pull_data.py
    build.py
  data/
    <dataset>.csv
    <dataset>_metadata.json
  refresh_status.json       optional runtime evidence
  console_log.jsonl         optional browser telemetry
  history/
    state.json              current + previous definition version
    versions/<UTC>__<hash>.json
  archive/<UTC>/            optional quarantine
```

The five required paths are `manifest_template.json`, `manifest.json`, `dashboard.html`, `scripts/pull_data.py`, and `scripts/build.py`. `audit_dashboard_layout(folder)` confirms presence and allows other legitimate files. Successful changed builds automatically version the template and both scripts under `history/`; CSVs and generated outputs are never versioned.

## Manifest skeleton

```python
manifest = {
    "schema_version": 1,
    "id": "rates_monitor",
    "title": "Rates monitor",
    "description": "Curve, spreads, and release context.",
    "theme": "gs_clean",
    "palette": "gs_primary",
    "metadata": {
        "kerberos": "goyalri",
        "dashboard_id": "rates_monitor",
        "methodology": "## Sources\n* GS Market Data\n## Construction\n* Daily close",
        "sources": ["GS Market Data"],
        "refresh_frequency": "1d",
        "tags": ["rates"],
    },
    "header_actions": [],
    "datasets": {"rates": {"source": [], "template": True}},
    "filters": [],
    "layout": {
        "kind": "tabs", "cols": 12,
        "tabs": [{"id": "overview", "label": "Overview", "rows": []}],
    },
    "links": [],
}
```

| Field | Decision contract |
|---|---|
| `id` | Stable folder leaf and registry id |
| `theme` | `gs_clean`; dark mode is viewer-controlled |
| `palette` | `gs_primary`, `gs_colorblind`, `gs_blues`, `gs_diverging`, or `gs_diverging_accessible` |
| `metadata.kerberos` | Folder owner; engine stamps it during typed mutation |
| `metadata.dashboard_id` | Folder leaf; engine stamps it during typed mutation |
| `metadata.methodology` | Required non-empty markdown |
| `metadata.sources` | Human-readable source systems |
| `metadata.summary` | String or `{title, body}` banner |
| `metadata.refresh_frequency` | Pull cadence (one authoring knob). Duration string, positive int seconds, or `hourly` / `daily` / `weekly` / `manual`. Pick from the cadence class table in [build.md](dashboards/build.md#cadence) |
| `metadata.live_refresh_seconds` | Browser `/api/dashboard/data/` poll. Omit — engine stamps from `refresh_frequency` (`manual`→0; else clamp 5–60s). Override only if needed; `0` disables; floor 5 when set |
| `metadata.presence_url` | Open-tab heartbeat POST URL; default `/api/dashboard/presence/` |
| `metadata.time.data_domain_freq` | `daily`, `weekly`, `monthly`, `quarterly`, or `annual`; set only to correct inference |
| `datasets` | Named slots populated from CSVs/transforms |
| `map_assets` | Self-contained, validated GeoJSON assets used by `geo_map`; never fetched remotely |
| `datasets.<name>.field_provenance` | Optional per-column lineage authored in the template and owned by [pipelines.md](dashboards/pipelines.md#field-provenance); never inferred from sidecars or `df.attrs` |
| `filters` / `links` | See [filters.md](dashboards/filters.md#filter-catalog) |
| `layout` | Grid or tabs; every row is a list of widgets |

The engine stamps data-domain, pull, build, and refresh-cycle timestamps. Do not author generated timestamps when the engine can derive them.

## Public engine APIs

Import public operations from `dashboards`:

```python
from dashboards import (
    run_pull,
    build_dashboard,
    build_dashboard_data_only,
    publish_dashboard,
    refresh_dashboard,
    light_refresh,
    review_dashboard,
    acknowledge_dashboard_review,
    audit_dashboard_layout,
    describe_dashboard,
    inspect_dashboard,
    list_dashboard_versions,
    restore_dashboard_version,
    apply_manifest_operations,
    apply_persisted_script_operations,
    launch_clean_refresh,
    record_open_presence,
    list_open_dashboards,
    synchronize_refresh_frequency,
    sync_refresh_frequency,
    compile_dashboard,
    validate_manifest,
    manifest_template,
    populate_template,
    df_to_source,
    load_manifest,
    save_manifest,
    chart_data_diagnostics,
    Manifest,
    DashboardResult,
    DashboardReview,
    DashboardReviewRequired,
)
```

| API | Contract |
|---|---|
| `run_pull(folder, pull_name)` | Execute one named `PULLS` entry and persist its side effects |
| `review_dashboard(folder, version_id=None)` | Compile current persisted data with the working recipe or one exact saved definition, without publishing, and return the gate's `DashboardReview` |
| `acknowledge_dashboard_review(folder, expected_review_signature=..., rationale=..., version_id=None)` | Recompute and immutably acknowledge one exact non-`BLOCK` working or saved-definition review; the rationale must explain why the candidate is acceptable |
| `publish_dashboard(folder, rationale=None, expected_current_version_id=None)` | Preferred publish path: review → refuse `BLOCK` → acknowledge exact signature when needed → `build_dashboard`. Omit `rationale` when already publish-ready; require a substantive rationale when a new ack is written |
| `build_dashboard(folder, expected_current_version_id=None)` | Recompute the review, require its exact acknowledgment, then write outputs and record a changed recipe; pass the current version id for a changed existing recipe, while unchanged refreshes and the first baseline need none |
| `build_dashboard_data_only(folder)` | Reload CSVs + transforms into live `manifest.json` datasets/time only; never compile or rewrite HTML |
| `refresh_dashboard(folder)` | Run all pulls, then `build_dashboard` (full / cold HTML); there is no universal per-pull refresh timeout |
| `light_refresh(folder)` | Run all pulls, then `build_dashboard_data_only` (Refresh button / open-tab path) |
| `launch_clean_refresh(folder, mode="full")` | Launch the isolated runner (`--mode full\|light`); own S3 logs/status/completion; return terminal `success` or `review_required`; raise on failure |
| `record_open_presence(folder, viewer)` / `list_open_dashboards()` | Open-tab heartbeat index (`secondary/dashboard_open_presence/index.json`, TTL 90s) |
| `audit_dashboard_layout(folder)` | Require the five canonical paths; return `True` |
| `describe_dashboard(folder, mode="layout")` | Compact product floorplan: `text` / `layout_text` / `filters_text`, counts, review publish-ready flags, plus concurrency guards (`manifest_template_sha256`, `versioning.current_version_id`) for typed edits. Prefer this for ordinary edit sync; it is not a screenshot |
| `inspect_dashboard(folder, telemetry_limit=50)` | Read-only structured folder, script hashes, definition-version, review/acknowledgment state, graph, refresh, registry, telemetry, and finding report. Use for heal/triage, not ordinary layout sync |
| `list_dashboard_versions(folder, limit=20, timezone_name="UTC")` | Return recent immutable definition versions with UTC/local timestamps, local calendar date, product summaries, and current/previous markers; pass the user’s IANA timezone for relative-date requests |
| `restore_dashboard_version(folder, version_id, expected_current_version_id=...)` | Restore one exact listed definition only after its current-data review is acknowledged; compile it with current persisted data and preserve every other version |
| `apply_manifest_operations(folder_or_state, operations, recompile=True, ...)` | Ordered typed template transaction; a describe/inspect state supplies both guards directly. Nested dict patches deep-merge; lists/scalars replace; `None` clears |
| `apply_persisted_script_operations(folder_or_state, script, operations, ...)` | Typed fragment transaction for `pull_data`/`build`: hash gate, syntax/pipeline check, atomic write, strict compile, exact rollback |
| `synchronize_refresh_frequency(folder, value, expected_sha256=None, expected_current_version_id=None)` | Atomically align template metadata and the matching registry entry; existing versioned dashboards require the inspected current version id; `sync_refresh_frequency` is the alias |
| `validate_manifest(manifest)` | Structural validation only |
| `compile_dashboard(manifest, strict=True, ...)` | Return `DashboardResult` with `.review` as a `DashboardReview`; strict mode raises when any error is present, while warnings remain on `.diagnostics`, `.quality_findings`, and the review |
| `manifest_template(manifest)` | Strip live data while retaining dataset slots |
| `populate_template(template, datasets)` | Bind current datasets into a template |
| `load_manifest(path)` / `save_manifest(manifest, path)` | Read or persist a manifest through the canonical S3 manager |
| `chart_data_diagnostics(manifest)` | Post-population lint for empty or unusable chart data |

`build_dashboard` is the standard persistent compile path. `DashboardReviewRequired` is raised before live manifest/HTML writes when the exact working or saved-definition signature lacks acknowledgment. `strict=False` is limited to in-session diagnostic discovery; always-blocking diagnostics still raise.
`make_echart`, `EChartResult`, and `echart_studio` are internal lowering
substrate, not public PRISM authoring APIs.

## Dashboard Garbage Gate

`compile_dashboard` returns `DashboardResult.review`, a `DashboardReview` over the Python compiler's populated, default-filter-state semantics. Its status is:

| Status | Publish decision |
|---|---|
| `BLOCK` | Deterministic defect; repair and review again. It cannot be acknowledged. |
| `REVIEW_REQUIRED` | Advisory or browser-runtime boundary; inspect the evidence and acknowledge only with an explicit rationale. |
| `CLEAR` | No flagged Python-visible panel semantics; the exact first-build or changed signature still requires acknowledgment. |

The versioned quality signature hashes the detector version plus sorted panel
status, data state, finding codes, and coarse materiality classes. Materiality
classes bucket row/effective-point counts, missing fractions, anomaly counts,
gap/scale/step ratios, time-span or claimed-window ratios, narrative lengths,
and tool matrix shapes as applicable; a tool's `compute_sha256` is exact.
Ordinary raw observations and extrema are excluded. Crossing one of those
classes, changing a finding code, or changing a panel state changes the quality
signature; moving values inside the same classes does not.

`review.to_text()` always emits one index line per panel and, within its bounded output, full detail for flagged panels by default. Inspect any omitted or flagged panel with `review.panel(panel_id)`; do not infer detail from the index line. This is a compile/default-state semantic receipt, not a screenshot or proof of arbitrary browser interactions. In particular, browser-only tool `compute_js` is never executed in Python: its panel has `coverage="runtime_unverified"` and requires acknowledgment of that boundary before build, followed by browser verification before delivery.

Persistent folder publication — preferred path:

```python
state = describe_dashboard(FOLDER)  # or inspect_dashboard for heal/triage
if state["review"]["publish_ready"]:
    published = publish_dashboard(FOLDER)  # rationale optional when publish-ready
else:
    review = review_dashboard(FOLDER)
    print(review.to_text())
    for panel in review.panels:
        if panel.status != "CLEAR":
            print(review.panel(panel.panel_id).to_text())
    published = publish_dashboard(
        FOLDER,
        rationale=(
            "Reviewed <panel ids or the complete CLEAR panel index>; "
            "accepted <finding or CLEAR baseline> because "
            "<specific receipt evidence and analytical reason>."
        ),
        expected_current_version_id=state["versioning"]["current_version_id"],
    )
```

`publish_dashboard` refuses `BLOCK`, binds a new rationale only when the signature still needs acknowledgment, and builds. Restores that need an explicit ack may still use `acknowledge_dashboard_review` + `restore_dashboard_version`. Omit `expected_current_version_id` only for the first baseline or an unchanged recipe; take it from a fresh `describe_dashboard` / `inspect_dashboard` when an existing recipe changed. First builds and every definition- or quality-signature change require a new exact acknowledgment. When `review.acknowledgment_match` and `review.publish_ready` are both true, call `publish_dashboard` without a new rationale.

Saved-definition restores use the same gate: call `review_dashboard(FOLDER, version_id=target_id)`, inspect its flagged panels, then pass the same `version_id` to `acknowledge_dashboard_review` before `restore_dashboard_version`. The review uses current persisted data; an older or materially changed saved definition therefore cannot bypass the publish boundary.

A refresh that reaches an unacknowledged review records lowercase `refresh_status.status="review_required"` while leaving the live `manifest.json` and `dashboard.html` bytes unchanged. This runner state is distinct from uppercase `DashboardReview.status="REVIEW_REQUIRED"`, the panel-quality decision that may cause the hold. The runner does not stamp registry refresh state or user-manifest pointers and does not treat the hold as a failure-cooldown outcome.

### Persisted-script execution namespaces

In-process `run_pull` / `build_dashboard` and clean refresh discovery use
the same namespace: `s3_manager`, the supported pull helpers,
`pull_nyfed_data`, `save_artifact`, `pd`, and `np`. Import other client
modules explicitly.

The refresh-attachment contract is registered-call-graph based. The engine
starts only from literal module-level `PULLS` / `TRANSFORMS`, follows local
helpers, and resolves fixed output names through assignments, helper
parameters, f-strings, dictionary/list/tuple loops, and
`datasets.update({...})`. One coherent pull may emit several terminal CSVs.
Runtime-dependent output names block with `producer_output_unresolved`; expose
the fixed key at a helper call or finite literal loop rather than splitting a
same-source pipeline or adding dummy transform assignments.

## Layouts

```python
# Grid
{"kind": "grid", "cols": 12, "rows": [[widget, widget], [widget]],
 "groups": [{"id": "regime", "title": "Regime",
             "start_row": 0, "end_row": 1}]}

# Tabs
{"kind": "tabs", "cols": 12, "tabs": [
    {"id": "overview", "label": "Overview",
     "description": "Headline view", "rows": [[widget, widget]],
     "groups": []},
]}
```

- Each row is a list of widget objects.
- Row widths sum to at most `cols`.
- Standard chart widgets are exactly two-up (`w=6`) or three-up (`w=4`) on a 12-column layout. Omitted chart width defaults to two-up. One decision-critical chart may set `hero: true, w: 12` and occupy its own row.
- Non-chart widgets may span any legal width.
- `data_grid` is full-width and virtualized. Named `groups` are non-overlapping inclusive row ranges with unique ids and required titles.
- Use tabs when the information has distinct jobs; use a grid for one coherent scan path.
- Stable tab and widget ids are selectors, state keys, and relationship targets. Do not rename them casually.

## Header actions

## Live refresh surfaces

| Surface | What PRISM / ops use | Effect |
|---|---|---|
| Browser `[Refresh]` | Chrome POSTs `mode=light` | Pulls + `manifest.json` datasets only now (bypasses due gate); open tab swaps via `/api/dashboard/data/` |
| Open-tab autorefresh | Tab heartbeats `/api/dashboard/presence/`; `entrypoint.py site` ticks `refresh_dashboards.py --open-interval 10` | Light-refreshes presence-fresh folders that are **due** per `refresh_frequency`; no full registry walk |
| Cold / scheduled | 15-minute one-shot `refresh_dashboards.main()` or `--interval N` | Full compile + `dashboard.html` for due dashboards |

Author **`metadata.refresh_frequency`** only. The engine stamps
`live_refresh_seconds` for the browser poll. Open-interval is a check
tick (recommend 10s), not “always pull while open”. Opt out of the site
daemon with `entrypoint.py site --no-open-refresh`.

`header_actions[]` adds custom actions to the left of always-on Methodology, Refresh, Share, Download, theme, and freshness controls.

| Key | Rule |
|---|---|
| `label` | Required |
| `href` / `onclick` | Exactly one action path |
| `target` | `_blank` default or `_self` |
| `id` | Optional unique DOM id |
| `primary` / `icon` / `title` | Styling and tooltip |

Reserved ids: `methodology-btn`, `refresh-btn`, `refresh-btn-label`, `refresh-err-btn`, `share-btn`, `share-btn-label`, `share-mode-users`, `share-mode-department`, `share-add-workspace`, `share-workspace-submenu`, `download-btn`, `download-btn-label`, `download-menu`, `export-all`, `export-dashboard`, `export-chart-data`, `export-print`, `export-excel`, `theme-toggle`, `now-pill`, `now-pill-val`, `refresh-pill`, `refresh-pill-val`, `header-actions`.

Every successful strict compile emits `export-chart-data` and `export-print`;
their presence is part of the compiler chrome contract, not a manifest option.
Runtime verification belongs in the browser gate: chart-data CSV must download
the bound source schema, and `beforeprint` must mount every tab and temporarily
open collapsed groups under the light print theme. A printed `data_grid`
contains its complete filtered/sorted result up to `max_rows`, not only the
currently virtualized screen page.

## Registry shape

The registry is `users/{kerberos}/dashboards/dashboards_registry.json`. The runner reads only `registry["dashboards"]`.

```python
{
    "dashboards": [{
        "id": "rates_monitor",
        "name": "Rates Monitor",
        "description": "Daily US rates monitor.",
        "created_at": "<preserve on update>",
        "last_refreshed": None,
        "last_refresh_status": None,
        "refresh_enabled": True,
        "refresh_frequency": "1d",
        "folder": "users/goyalri/dashboards/rates_monitor",
        "html_path": "users/goyalri/dashboards/rates_monitor/dashboard.html",
        "data_path": "users/goyalri/dashboards/rates_monitor/data",
        "tags": ["rates"],
    }],
    "last_updated": "<ISO timestamp>",
}
```

Exactly one entry matches the dashboard id. `refresh_frequency` must equal template metadata byte-for-byte; use `synchronize_refresh_frequency` for changes. Preserve `created_at`. Registration owns the registry write only. There is no authoring helper named `update_user_manifest`: the scheduled orchestrator calls `UserManifestManager.update_dashboard_pointer(kerberos)` after a successful registry walk, while an on-demand browser refresh does not update that pointer today.

Cadence examples: `"60s"`/`"5m"` for intraday, `"1h"` for frequently changing aggregates, `"1d"` for daily data, `"1w"` for slow data, `"manual"` for fixed exhibits. Pick cadence from the slowest load-bearing source and user need, not from convenience.

## Cross-cutting authoring judgment

- Choose a chart archetype that answers the question; do not maximize primitive variety.
- Every displayed field carries the dataset-entry lineage shape in [pipelines.md](dashboards/pipelines.md#field-provenance); computed fields state their recipe and upstream columns.
- Preserve source history deep enough for the requested horizon. Pull-time clipping cannot be recovered at render time.
- Keep line/area overlays to four series. Split, aggregate, or reframe when every fifth series is load-bearing.
- Use plain-English persisted columns. Labels applied only to an ephemeral DataFrame do not survive refresh.
- A destructive rebuild requires explicit product intent. Ordinary “add”, “change”, and “also show” asks are surgical edits.
- Intraday unavailability is a data-source condition to model explicitly in the product; do not fabricate values.

## Anti-patterns

| Anti-pattern | Required action |
|---|---|
| Hand-written dashboard HTML/JS | Use the manifest compiler |
| Root-replacing an inherited template | Use `apply_manifest_operations` |
| Editing `manifest.json`, CSV output, or HTML directly | Edit the owning persisted input |
| Static KPI/stat values | Pull or derive a dataset-backed value |
| Dataset key differs from CSV stem | Align pull `name=`, emitted file stem, and slot |
| Treating JSON, a metadata sidecar, or `df.attrs` as a dataset/provenance source | Persist a CSV dataset and author `field_provenance` in its template entry |
| Leaving NY Fed or client output in memory | Persist it with `save_artifact` or an explicit CSV write |
| Relying on injected helpers, `pd`/`np`, or client modules | Import every used name explicitly in the persisted script |
| Treating a retained CSV as current pull success | Require a successful current-cycle pull and verify the expected CSV is non-empty before build |
| Template and registry cadence differ | Use `synchronize_refresh_frequency` |
| Treating validation as delivery | Complete strict build and clean subprocess refresh |
| Reporting engine mechanics to the user | Rewrite in product language |
| Guessing a fix before describe/inspect | Start with `describe_dashboard` for ordinary edits; `inspect_dashboard` for heal/triage |
| Editing without layout sync | Call `describe_dashboard` before and after mutation; paraphrase `text` to the user |
| Reusing a popup join without key overlap | Fix source/target binding before compile |

## Owner index

This kernel is loaded on demand after the router; it is not a separate
context-registry entry.

| Authority | File |
|---|---|
| First-build transaction | [build.md](dashboards/build.md#four-tool-transaction) |
| Layout sync / ordinary edit floorplan | `describe_dashboard` in this kernel |
| Inspect, triage, heal, revert | [diagnose.md](dashboards/diagnose.md#structured-inspection) |
| Manifest operations | [template_crud.md](dashboards/template_crud.md#manifest-operations) |
| Pull/build script edits | [pipelines.md](dashboards/pipelines.md#pipeline-reuse-decision) |
| Archetypes and transforms | [recipes.md](dashboards/recipes.md#data-archetypes) |
| Chart primitives | [charts.md](dashboards/charts.md#chart-type-catalog-31) |
| Non-tool widgets and popups | [widgets.md](dashboards/widgets.md#widget-kinds) |
| Tool widgets | [widget_tool.md](dashboards/widget_tool.md#tool-definition) |
| Filters and links | [filters.md](dashboards/filters.md#filter-catalog) |
