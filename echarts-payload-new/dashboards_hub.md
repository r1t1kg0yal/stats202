# ECharts dashboard kernel

- **Context ID:** `echarts.kernel`
- **Owns:** `kernel.contract`, `kernel.manifest`, `kernel.api`, `kernel.layout`, `kernel.registry`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards.md](dashboards.md#route-before-fetching).

This is the compact cross-cutting contract. It does not own first-build steps, mutation recipes, diagnosis, data pipelines, or primitive catalogs; use the [owner index](#owner-index).

## Contract

1. **Real, refreshable data.** Every visible number derives from a persisted pull or transform. KPI/stat literals and invented identifiers are forbidden.
2. **Template contains no live data.** `manifest_template.json` keeps dataset slots; `manifest.json` is populated output.
3. **Canonical order.** Pulls produce files, transforms derive datasets, the template is populated, strict compilation writes outputs, registry metadata is aligned, then a clean subprocess refresh verifies the persisted artifact.
4. **Canonical folder.** Persistent dashboards live only at `users/{kerberos}/dashboards/{dashboard_id}`.
5. **Flat CSV routing.** Every pull writes to `{folder}/data`; only CSV files become datasets, and each dataset key matches the complete emitted stem byte-for-byte.
6. **Portal handoff.** Surface only `http://reports.prism-ai.url.gs.com:8501/users/{kerberos}/dashboards/{dashboard_id}/`.
7. **Atomic work.** Do not return between steps of a build or edit. Once a response is sent, no autonomous work continues.
8. **Preserve inherited intent.** Inspect before mutation. Use typed operations for manifests and evidence-based edits for scripts. Root replacement is forbidden.
9. **Engine diagnostics are instructions.** Follow each structured `fix_hint`, retry, and expose only product-level residue to the user.

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
| `palette` | `gs_primary`, `gs_blues`, or `gs_diverging` |
| `metadata.kerberos` | Folder owner; engine stamps it during typed mutation |
| `metadata.dashboard_id` | Folder leaf; engine stamps it during typed mutation |
| `metadata.methodology` | Required non-empty markdown |
| `metadata.sources` | Human-readable source systems |
| `metadata.summary` | String or `{title, body}` banner |
| `metadata.refresh_frequency` | Duration string, positive integer seconds, or `hourly` / `daily` / `weekly` / `manual` |
| `metadata.live_refresh_seconds` | Browser polling cadence; `0` disables, effective floor 15 |
| `metadata.time.data_domain_freq` | `daily`, `weekly`, `monthly`, `quarterly`, or `annual`; set only to correct inference |
| `datasets` | Named slots populated from CSVs/transforms |
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
    refresh_dashboard,
    audit_dashboard_layout,
    inspect_dashboard,
    list_dashboard_versions,
    restore_dashboard_version,
    apply_manifest_operations,
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
)
```

| API | Contract |
|---|---|
| `run_pull(folder, pull_name)` | Execute one named `PULLS` entry and persist its side effects |
| `build_dashboard(folder, expected_current_version_id=None)` | Load template and CSVs, run `TRANSFORMS`, strict-compile, write outputs, and record a changed recipe; pass the inspected current version id for a changed existing recipe, while unchanged refreshes and the first baseline need none |
| `refresh_dashboard(folder)` | Run all pulls, then `build_dashboard`; there is no universal per-pull refresh timeout |
| `audit_dashboard_layout(folder)` | Require the five canonical paths; return `True` |
| `inspect_dashboard(folder, telemetry_limit=50)` | Read-only structured folder, definition-version, graph, refresh, registry, telemetry, and finding report |
| `list_dashboard_versions(folder, limit=20, timezone_name="UTC")` | Return recent immutable definition versions with UTC/local timestamps, local calendar date, product summaries, and current/previous markers; pass the user’s IANA timezone for relative-date requests |
| `restore_dashboard_version(folder, version_id, expected_current_version_id=...)` | Restore one exact listed definition, compile it with current persisted data, and preserve every other version |
| `apply_manifest_operations(folder, operations, recompile=True, expected_sha256=None, expected_current_version_id=None)` | Ordered typed template transaction with template-hash and current-version guards, dependent-reference cleanup, optional compile/version, and rollback |
| `synchronize_refresh_frequency(folder, value, expected_sha256=None, expected_current_version_id=None)` | Atomically align template metadata and the matching registry entry; existing versioned dashboards require the inspected current version id; `sync_refresh_frequency` is the alias |
| `validate_manifest(manifest)` | Structural validation only |
| `compile_dashboard(manifest, strict=True, ...)` | Compile an in-memory manifest; always check `result.success` |
| `manifest_template(manifest)` | Strip live data while retaining dataset slots |
| `populate_template(template, datasets)` | Bind current datasets into a template |
| `load_manifest(path)` / `save_manifest(manifest, path)` | Read or persist a manifest through the canonical S3 manager |
| `chart_data_diagnostics(manifest)` | Post-population lint for empty or unusable chart data |

`build_dashboard` is the standard persistent compile path. `strict=False` is limited to in-session diagnostic discovery; always-blocking diagnostics still raise.
`make_echart`, `EChartResult`, and `echart_studio` are internal lowering
substrate, not public PRISM authoring APIs.

### Persisted-script execution namespaces

In-process `run_pull` / `build_dashboard` inject `s3_manager`, the supported
pull helpers, `save_artifact`, `pull_nyfed_data`, `pd`, and `np`. Clean
refresh discovery injects only `s3_manager`, the supported pull helpers, and
`save_artifact`. Persisted `pull_data.py` and `build.py` must explicitly
import every name they use; treat an in-process success that depends on
injection as a defect until namespace parity is fixed.

## Layouts

```python
# Grid
{"kind": "grid", "cols": 12, "rows": [[widget, widget], [widget]]}

# Tabs
{"kind": "tabs", "cols": 12, "tabs": [
    {"id": "overview", "label": "Overview",
     "description": "Headline view", "rows": [[widget, widget]]},
]}
```

- Each row is a list of widget objects.
- Row widths sum to at most `cols`.
- Chart widgets are exactly two-up (`w=6`) or three-up (`w=4`) on a 12-column layout. Omitted chart width defaults to the legal two-up width.
- Non-chart widgets may span any legal width.
- Use tabs when the information has distinct jobs; use a grid for one coherent scan path.
- Stable tab and widget ids are selectors, state keys, and relationship targets. Do not rename them casually.

## Header actions

`header_actions[]` adds custom actions to the left of always-on Methodology, Refresh, Share, Download, theme, and freshness controls.

| Key | Rule |
|---|---|
| `label` | Required |
| `href` / `onclick` | Exactly one action path |
| `target` | `_blank` default or `_self` |
| `id` | Optional unique DOM id |
| `primary` / `icon` / `title` | Styling and tooltip |

Reserved ids: `refresh-btn`, `share-btn`, `download-btn`, `download-menu`, `methodology-btn`, `theme-toggle`, `export-all`, `export-dashboard`, `export-excel`, `data-as-of`, `data-as-of-val`, `header-actions`.

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
| Guessing a fix before inspection | Start with `inspect_dashboard` |
| Reusing a popup join without key overlap | Fix source/target binding before compile |

## Owner index

This kernel is loaded on demand after the router; it is not a separate
context-registry entry.

| Authority | File |
|---|---|
| First-build transaction | [build.md](dashboards/build.md#four-tool-transaction) |
| Inspect, triage, heal, revert | [diagnose.md](dashboards/diagnose.md#structured-inspection) |
| Manifest operations | [template_crud.md](dashboards/template_crud.md#manifest-operations) |
| Pull/build script edits | [pipelines.md](dashboards/pipelines.md#pipeline-reuse-decision) |
| Archetypes and transforms | [recipes.md](dashboards/recipes.md#data-archetypes) |
| Chart primitives | [charts.md](dashboards/charts.md#chart-type-catalog-30) |
| Non-tool widgets and popups | [widgets.md](dashboards/widgets.md#widget-kinds) |
| Tool widgets | [widget_tool.md](dashboards/widget_tool.md#tool-definition) |
| Filters and links | [filters.md](dashboards/filters.md#filter-catalog) |
