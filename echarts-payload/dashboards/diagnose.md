# Diagnose, heal, and revert

- **Context ID:** `echarts.diagnose`
- **Owns:** `diagnose.inspect`, `diagnose.triage`, `diagnose.heal`, `diagnose.revert`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** None for read-only inspection; fetch the evidence-identified repair owner before mutation.

Start every inherited-dashboard investigation with the public read-only inspector. Do not begin with manual S3 listings, handwritten layout walks, direct telemetry parsing, or a guessed repair.

## Structured inspection

```python
from dashboards import inspect_dashboard

FOLDER = "users/{kerberos}/dashboards/{dashboard_id}"
state = inspect_dashboard(FOLDER, telemetry_limit=50)
```

The deterministic result contains:

| Field | Evidence |
|---|---|
| `files` | Required presence/missing/extras plus optional `refresh_status.json`, `console_log.jsonl`, registry, and user-manifest entries with explicit `present` booleans |
| `manifest_template_sha256` / `template_sha256` / `compiled_manifest_sha256` | Concurrency token, read-only equal pre/post snapshot, and compiled-manifest hash |
| `metadata` | Identity, cadence, methodology, sources, and authored state |
| `tabs` | Canonical ordered `{id, label, index}` list |
| `datasets` | Name-keyed records with persisted CSV path/presence, columns, dtypes, `[rows, columns]` shape, data origin, producer classification/pipelines/transform, and widget/filter consumers |
| `widgets.ordered` / `widgets.by_id` | Stable id, kind, tab id/index, row/index, dataset refs, chart type, mapping/source summaries, `click_emit_filter`, and `show_when` |
| `filters.ordered` / `filters.by_id` | Id, type, index, targets, reached datasets, field, dependency/options source, scope, default, and summary |
| `links` | Ordered `{index, group, members, sync, brush}` records |
| `persisted_path_index` | Canonical `by_relative_path` and `by_basename` maps for resource correlation |
| `counts` | Tabs, rows, widgets by kind, filters, datasets, pipelines, CSVs, telemetry |
| `graph.pipelines` | `PULLS` names, function names, and statically inferred CSV stems |
| `graph.csvs` | Persisted CSV stems and producer links |
| `graph.transforms` | Dataset keys materialized by `TRANSFORMS` |
| `graph.datasets` | CSV/transform producers and consuming widgets/filters |
| `graph.widgets` | Stable ids, kinds, datasets, tab, row, and index |
| `graph.filters` | Filter ids, kinds, targets, and dataset reach |
| `graph.edges` | Pipeline → CSV → dataset → widget/filter relationships |
| `refresh_status` | Last refresh status, errors, timestamps, log path, and failure count when present |
| `registry` | Path/presence, matching entries, `match_count`, canonical entry, duplicates, `created_at`, refresh frequency/alignment, and manifest-pointer state |
| `attachment_gaps` | Compile-to-refresh attachment violations with repair text |
| `telemetry_contract` / `telemetry` | Category definitions plus normalized recent events preserving `kind`, `message`, `url`, `source`, raw event, and persisted-path matches |
| `findings` | Sorted `{severity, code, path, message, fix_hint, context?}` records |

Optional status or telemetry absence is not itself an error. Required-file absence is a structured finding.

### Popup findings

Explicit `row_click` and `click_popup` failures appear in `findings` with stable codes:

`popup_config_blank`, `popup_detail_invalid`, `popup_section_invalid`, `popup_section_kind_unsupported`, `popup_legend_sync_unsupported`, `popup_section_dataset_missing`, `popup_section_filter_field_missing`, `popup_section_row_key_missing`, `popup_section_keys_no_overlap`

Every popup finding has a top-level `fix_hint`. Join-related `context` carries stable `detail_dataset`, `row_key`, `filter_field`, `available_columns`, and `overlap` fields when applicable, plus the same `fix_hint`. Repair only the named source/detail binding or use the supported alternative in the hint.

`update_widget.patch` is shallow. After inspection identifies the widget, read its complete current object from the decoded template, copy the whole popup subtree, change one leaf, and patch that subtree:

```python
popup = copy.deepcopy(current_widget["row_click"])
popup["detail"]["sections"][0]["filter_field"] = "cusip"
apply_manifest_operations(
    FOLDER,
    [{"op": "update_widget",
      "selector": {"id": "bond_table"},
      "patch": {"row_click": popup}}],
    expected_sha256=state["manifest_template_sha256"],
)
```

Use the same pattern with `click_popup`; never patch only `detail` or `sections` and thereby discard sibling popup fields.

### Telemetry categories

Classification uses only persisted `kind`, `message`, `url`, and `source`:

| Category | Triage |
|---|---|
| `dashboard_runtime` | Script/runtime exception, rejection, or dashboard console error; correlate to the affected primitive |
| `resource` | Resource load failure or `resource_404`; normalize the event URL and compare `persisted_path_index.by_relative_path` first, then `by_basename`, before selecting the pipeline/path owner |
| `csp` | Content Security Policy violation or blocked-resource message; separate authored external resource use from environment policy |
| `extension_or_viewer` | Browser extension, PDF/viewer, or injected client-surface event; do not mutate the dashboard without corroborating evidence |
| `unknown` | Unclassified event; use refresh, graph, registry, and reproduction evidence |

ECharts is inlined, so ordinary chart display does not depend on a CDN.
Excel export and whole-dashboard PNG are optional exceptions: XLSX loads
eagerly and html2canvas loads on first PNG action from jsDelivr. If charts
render but one of those actions fails with a resource/CSP event, classify
the incident as environment/network evidence before mutating the dashboard.

## Triage order

1. **Identity and required files.** Confirm canonical folder identity and address every `files.missing` finding before mutation.
2. **Structured findings.** Work error findings before warnings. Use each `path` to localize and each `fix_hint` as the corrective contract.
3. **Refresh attachment.** Resolve every `attachment_gaps` item; a compiling but unattached dashboard is not healthy.
4. **Refresh evidence.** Read `refresh_status.status`, `errors`, and `log_path`. Do not restart-loop a failing dashboard.
5. **Browser evidence.** Classify recent telemetry by `kind`, timestamp, viewer, message, source, and URL.
6. **Dependency graph.** Trace affected widget/filter backward through dataset and CSV to a pull or transform.
7. **Registry.** Require exactly one matching entry and aligned cadence.
8. **Choose the repair owner.** Fetch only the context file that owns the identified surface, then mutate.

## Evidence matrix

| Evidence | Likely owner | Action |
|---|---|---|
| Missing canonical file | Build/pipeline intent | Restore from a known source; if intent is unknowable, escalate |
| Invalid template or manifest diagnostic | `template_crud.md` plus affected primitive | Apply typed operations using the current SHA |
| Popup detail dataset/field/key-overlap finding | `widgets.md` and `template_crud.md` | Correct the source/target binding named by the diagnostic |
| CSV missing or stem not produced | `pipelines.md` | Repair the pull output path/name or transform |
| Dataset has no pull/transform producer | `pipelines.md` | Attach a real producer; do not preserve a silently aging CSV |
| Refresh failed before browser errors | `pipelines.md` | Follow refresh error/log evidence, repair script/data, refresh |
| Refresh succeeded plus ECharts/browser error | Primitive owner plus `template_crud.md` | Repair the authored spec |
| `resource_404` for dashboard data | `pipelines.md` | Repair the persisted path/stem and refresh |
| Registry count invalid | Registry owner | Diagnose the canonical entry and report the exact registry merge/create action; no dashboard-template API removes duplicate registry rows |
| Registry/template cadence mismatch | Kernel public API | Call `synchronize_refresh_frequency` |
| Telemetry absent | No conclusion | Use other evidence; absence is not proof of health |
| Browser-extension/CSP noise isolated to one viewer | External environment | State the product-level limitation only after evidence rules out dashboard defects |
| Charts render but XLSX or whole-dashboard PNG reports a jsDelivr resource/CSP failure | Optional CDN environment | Do not repair the manifest; verify browser reachability or policy |

`registry.manifest_pointer` is read-only evidence with `state`, `registry_path_matches`, `update_required`, `owner`, and `fix_hint`. The pointer does not carry refresh cadence. When update is required, report or invoke the owning `core.user_manifest.UserManifestManager.update_dashboard_pointer` workflow if that owner is available; do not invent a dashboard-client mutation method. Template/registry cadence remains owned by `synchronize_refresh_frequency`.

## Heal loop

A heal preserves product intent while making persisted state satisfy the current public contract.

```text
inspect
  → classify every finding and attachment gap
  → fetch the evidence-identified owner
  → apply the smallest durable repair
  → strict build or clean refresh
  → inspect again
  → stop only when required files, attachment, registry, refresh,
    and relevant browser evidence are clean
```

Manifest heals use `apply_manifest_operations` with `expected_sha256=state["manifest_template_sha256"]`. Pipeline heals edit the persisted input script, run the affected pull, build, then execute the clean refresh path. Cadence heals use `synchronize_refresh_frequency`.

For a typed manifest transaction, success proves the commit path when `result.pre_sha256` equals the inspected token, `result.post_sha256` equals the final inspection hash, and `result.rollback_sha256 == result.pre_sha256`. `inspect_dashboard` supplies template and compiled-manifest SHA values; it does not supply pull/build script SHA values. Hash retained script bytes directly before editing, for example `hashlib.sha256(old_pull_bytes).hexdigest()`. A failed transaction proves restoration only when the final template SHA and snapshotted template, registry, compiled manifest, and HTML bytes all equal their pre-transaction values, while restored scripts match the hashes computed from retained bytes.

Do not:

- replace an inherited manifest root;
- edit generated `manifest.json`, CSVs, or HTML as the durable fix;
- ignore a `fix_hint` and invent traversal mechanics;
- ask the user to choose between implementation strategies;
- declare success from a passing schema validation while refresh evidence is red;
- remove a primitive simply because its current binding is broken.

## Escalation judgment

Heal silently when intent is preserved:

- field/key rename with one current equivalent;
- missing metadata inferable from the canonical folder and surviving content;
- registry shape or cadence alignment;
- stale primitive name with an unambiguous current equivalent;
- broken relationship whose intended endpoint is uniquely visible in the dependency graph;
- malformed path or output stem with one canonical correction.

Escalate in product language when no safe interpretation exists:

- required source data no longer exists and substitutions change meaning;
- a retired primitive has multiple materially different replacements;
- a missing canonical input cannot be reconstructed from a real prior artifact or surviving state;
- conflicting user-visible intents remain after inspecting current and retained state;
- the issue is external to the dashboard and requires the user's environment or access to change.

The user sees the product choice, not the implementation mechanics.

## Revert

A revert restores a known prior product state; it is never a best-guess reconstruction.

Preferred sources:

1. Exact prior bytes retained in the active conversation for the changed input.
2. A known-good `history/<UTC>/` snapshot when `keep_history` is enabled.
3. A user-supplied known-good artifact or precise prior-state description.

Procedure:

1. Inspect current state and capture its template SHA.
2. Identify the exact rollback source and affected persisted inputs.
3. For manifest-only rollback, express the prior state as typed operations against the current template. Use the captured SHA.
4. For pull/build script rollback, restore exact known bytes; do not reconstruct from memory.
5. Run the affected pulls, strict build, and clean refresh.
6. Inspect again and require clean canonical files, attachment, registry, and refresh evidence.
7. If the restored prior state violates a current contract, heal it while preserving the restored product intent.

If no known prior state exists, ask for the product state the user wants. Do not claim a revert.

## Completion evidence

A diagnosis is complete when the cause and owner are identified. A repair is complete only when:

- no required canonical file is missing;
- error findings relevant to the incident are gone;
- `attachment_gaps` is empty;
- registry match count is one and cadence is aligned;
- a clean refresh reports success;
- the dependency graph confirms the repaired producer/consumer path;
- new telemetry does not reproduce the incident, when browser evidence was part of the report.

User-facing completion is concise product language: acknowledge, state the fixed/live outcome, and give the portal URL when useful.
