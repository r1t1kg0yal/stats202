# Diagnose, heal, and revert

- **Context ID:** `echarts.diagnose`
- **Owns:** `diagnose.inspect`, `diagnose.triage`, `diagnose.heal`, `diagnose.revert`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** None for read-only inspection; fetch the evidence-identified repair owner before mutation.

Start every inherited-dashboard investigation with the public read-only inspector. Do not begin with manual S3 listings, handwritten layout walks, direct telemetry parsing, or a guessed repair. For ordinary “what does this look like?” layout sync on a healthy edit path, use `describe_dashboard` from the hub instead of this spoke.

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
| `scripts.pull_data` / `scripts.build` | Canonical path, presence, byte count, SHA-256 guard, syntax status, registered function inventory, resolved producer outputs, and unresolved output sites |
| `versioning` | Current/previous definition version, working/current recipe hashes, clean/dirty state, and five recent product summaries |
| `review` | Availability/source, `BLOCK`/`REVIEW_REQUIRED`/`CLEAR`, definition/quality/review signatures, acknowledgment match/path, and flagged panel drill-down pointers |
| `metadata` | Identity, cadence, methodology, sources, and authored state |
| `tabs` | Canonical ordered `{id, label, index}` list |
| `datasets` | Name-keyed records with persisted CSV path/presence, columns, dtypes, `[rows, columns]` shape, data origin, producer classification/pipelines/transform, and widget/filter consumers |
| `widgets.ordered` / `widgets.by_id` | Stable id, kind, tab id/index, row/index, dataset refs, chart type, mapping/source summaries, `click_emit_filter`, and `show_when` |
| `filters.ordered` / `filters.by_id` | Id, type, index, targets, reached datasets, field, dependency/options source, scope, default, and summary |
| `links` | Ordered `{index, group, members, sync, brush}` records |
| `persisted_path_index` | Canonical `by_relative_path` and `by_basename` maps for resource correlation |
| `counts` | Tabs, rows, widgets by kind, filters, datasets, pipelines, CSVs, telemetry |
| `graph.pipelines` | `PULLS` names, function names, helper-aware CSV stems, and per-pipeline unresolved output sites |
| `graph.csvs` | Persisted CSV stems and producer links |
| `graph.transforms` | Dataset keys materialized by `TRANSFORMS` |
| `graph.producer_analysis` | Pull/transform output sites the registered call-graph analyzer cannot resolve |
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

`popup_config_blank`, `popup_detail_invalid`, `popup_section_invalid`, `popup_section_kind_unsupported`, `popup_section_dataset_missing`, `popup_section_filter_field_missing`, `popup_section_row_key_missing`, `popup_section_keys_no_overlap`

Every popup finding has a top-level `fix_hint`. Join-related `context` carries stable `detail_dataset`, `row_key`, `filter_field`, `available_columns`, and `overlap` fields when applicable, plus the same `fix_hint`. Popup chart legend/link behavior is supported through a stable section `id` and manifest `links[]`. Repair only the named source/detail binding or use the supported alternative in the hint.

### Interaction and geographic findings

`filter_chart_rebuild_unsupported` identifies every targeted chart that cannot be faithfully rebuilt under browser filtering; retarget or reshape it rather than accepting a static chart. `geo_map_asset_missing`, `geo_map_region_unknown`, and `geo_map_region_duplicate` are always blocking. Their context names the map, region field, representative unknown/duplicate keys, available map keys, and exact alias/aggregation repair.

### Producer-attachment findings

`pull_producer_output_unresolved` and
`transform_producer_output_unresolved` mean a registered producer reaches an
output whose fixed key is hidden behind runtime computation.
`dataset_<key>_producer_unresolved` means the engine therefore cannot prove
whether that consumer is attached. This is distinct from
`dataset_<key>_silent_stale`, which means the complete registered graph is
resolvable and definitely contains no producer.

For an unresolved site, inspect `scripts.*.unresolved_outputs`,
`graph.pipelines[].unresolved_outputs`, and `graph.producer_analysis`. Preserve
one coherent pull when outputs share source/cadence/failure semantics. Expose
each fixed stem/key at the standard call, local writer/materializer-helper
call, literal assignment/update, or finite literal loop. Do not split the pull,
invent per-output network calls, or add no-op transform assignments. Only a
definite silent-stale/unattached finding justifies adding a missing producer.

### Data-quality findings

`findings` also includes every `data_quality_*` and `timeseries_*`
diagnostic, including warnings. Stable evidence fields are `dataset`,
`series`, `field`, `observed`, `expected`, `examples`, `visual_effect`,
and `fix_hint`. Errors block strict compilation. Warnings identify
suspicious but potentially genuine missing runs, gaps, stale tails,
scale-dominating observations, abrupt breaks, irregular cadence, or
degenerate series.

After strict build or clean refresh, enumerate the complete quality subset
before handoff:

```python
state = inspect_dashboard(FOLDER)
quality_findings = [
    finding for finding in state["findings"]
    if finding["code"].startswith(("data_quality_", "timeseries_"))
]
```

Report every warning with its evidence and `visual_effect`; do not replace
that exhaustive list with a generic “data quality warning” summary.

Trace a quality finding backward through `graph.datasets` to its transform,
CSV, and pull. Repair only a demonstrated producer, join, unit, or mapping
defect. Never make a chart pass by silently sorting, filling, clipping,
winsorizing, or deleting observations. If the evidence does not establish
that the value is wrong, preserve it, explain the visual risk, and ask
whether the product should keep the full scale or use an explicit
alternative view.

### Dashboard review evidence

Inspection summarizes the currently persisted candidate at `state["review"]`. When a publish is authorized, get the complete current receipt and inspect every flagged panel before mutation:

```python
review = review_dashboard(FOLDER)
print(review.to_text())
for panel in review.panels:
    if panel.status != "CLEAR":
        print(review.panel(panel.panel_id).to_text())
```

The receipt is Python compile/default-state semantics only. It always indexes every panel and includes flagged detail by default; `review.panel(id)` is the authoritative drill-down. `state["review"]["pending_findings"]` and top-level `state["findings"]` are read-only triage indexes, not a second publish loop: use them to locate owners, then enumerate each non-`CLEAR` panel exactly once from the fresh `DashboardReview`. `BLOCK` is deterministic and unacknowledgeable. For a first build or changed review signature, prefer `publish_dashboard(FOLDER, rationale=..., expected_current_version_id=...)` after inspecting flagged panels (or the equivalent `acknowledge_dashboard_review` + `build_dashboard`); the rationale must name the reviewed panel ids (or complete `CLEAR` index), accepted finding/baseline, receipt evidence, and analytical reason. When `state["review"]["acknowledgment_match"]` and `publish_ready` are both true, follow that state's `fix_hint` — skip redundant acknowledgment and continue the refresh. Browser-only tool `compute_js` remains `runtime_unverified` because Python never executes it.

`update_widget.patch` deep-merges nested dicts (lists replace; `None` clears). After inspection identifies the widget, patch only the leaf dict path — sibling popup fields are preserved:

```python
apply_manifest_operations(
    state,
    [{"op": "update_widget",
      "selector": {"id": "bond_table"},
      "patch": {
          "row_click": {
              "detail": {"title": "Bond detail"},
          },
      }}],
)
```

When changing one element inside a list (for example `detail.sections`), replace that list with the full intended value while still deep-merging the surrounding dict. Use the same pattern with `click_popup`.

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
4. **Refresh evidence.** Read `refresh_status.status`, `errors`, and `log_path`. `review_required` retains live output bytes and is not a failure cooldown; inspect and acknowledge rather than restart-looping.
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
| Data-quality error | `pipelines.md` plus the consuming primitive | Repair the named producer/transform/contract defect; strict compilation remains blocked |
| Data-quality warning with ambiguous observation | Product judgment | Preserve the data, surface the structured evidence, and ask before changing scale treatment or data |
| Review status `BLOCK` | Owning primitive or pipeline | Repair the deterministic finding and obtain a new receipt; acknowledgment is forbidden |
| Review status `REVIEW_REQUIRED` or unacknowledged `CLEAR` | Dashboard Garbage Gate | Drill into every flagged panel, acknowledge the exact signature with rationale, then run the guarded build |
| Refresh status `review_required` | Dashboard Garbage Gate | Live manifest/dashboard and registry/user pointers remain unchanged; acknowledge the current review and retry without failure cooldown |
| CSV missing or stem not produced | `pipelines.md` | Repair the pull output path/name or transform |
| Producer output unresolved through a helper/dynamic key | `pipelines.md` | Preserve the coherent producer; make its fixed output names statically visible at literal helper call sites or finite literal loops |
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
  → review receipt and flagged panels
  → acknowledge exact non-BLOCK signature with rationale
  → guarded build or clean refresh
  → inspect again
  → stop only when required files, attachment, registry, refresh,
    and relevant browser evidence are clean
```

Manifest heals pass the complete inspection state to
`apply_manifest_operations(state, operations)`. Pipeline heals use
`apply_persisted_script_operations(state, "pull_data"|"build", operations)`,
run any affected pull for current-cycle schema verification, then call
`launch_clean_refresh(FOLDER)`. Cadence heals use
`synchronize_refresh_frequency` with the inspected guards.

For either typed transaction, success proves the commit path when
`result.pre_sha256` equals the matching inspected token,
`result.post_sha256` equals the final inspection hash, and
`result.rollback_sha256 == result.pre_sha256`. A failed transaction must
leave the snapshotted canonical bytes equal to their pre-transaction
values.

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

A revert restores one engine-recorded dashboard definition and recompiles it with current persisted data. It does not restore historical CSV values.

```python
from dashboards import (
    acknowledge_dashboard_review,
    list_dashboard_versions,
    restore_dashboard_version,
    review_dashboard,
)

versions = list_dashboard_versions(
    FOLDER,
    limit=20,
    timezone_name="America/New_York",  # user's IANA timezone
)
# Apply the resolution rules below, then copy one exact returned entry.
target = SELECTED_VERSION_ENTRY
review = review_dashboard(FOLDER, version_id=target["version_id"])
print(review.to_text())
for panel in review.panels:
    if panel.status != "CLEAR":
        print(review.panel(panel.panel_id).to_text())
if review.status == "BLOCK":
    raise ValueError("repair or choose another saved definition")
acknowledge_dashboard_review(
    FOLDER,
    expected_review_signature=review.review_signature,
    rationale=(
        "Reviewed the selected saved definition with current persisted data; "
        "accepted <specific panel findings and evidence>."
    ),
    version_id=target["version_id"],
)
result = restore_dashboard_version(
    FOLDER,
    version_id=target["version_id"],
    expected_current_version_id=versions["current_version_id"],
)
```

The list result has top-level `current_version_id`, `previous_version_id`, and `timezone`. Each version entry contains exact `version_id`, `created_at_utc`, `display_time`, `local_date`, `timezone`, `summary`, `is_current`, and `is_previous`. Summary contains `title`, `tab_names`, `widget_count`, `filter_count`, `pull_script_changed`, and `build_script_changed`. The version id is an opaque engine token: copy it exactly from the selected entry and never show it to the user.

Resolve the target in product language:

1. “Go back to what we had” or “undo that restore” selects `previous_version_id`.
2. “Version from yesterday” passes the user’s IANA timezone and selects the sole entry whose `local_date` equals the user’s yesterday. If the timezone is unavailable, ask for it. If several versions match, show their `display_time`, titles, tab names, and widget counts and ask which one.
3. “The old version” restores directly only when exactly one earlier version exists; otherwise show all materially different candidates up to the three most recent. Material difference means any change in title, tab names, widget count, or script-change markers.
4. “The newer one again” selects `previous_version_id` only after confirming its timestamp is newer than current; otherwise show newer timestamped candidates.
5. Pass only the exact selected `version_id`; never invent or partially reconstruct a version.

Re-run `list_dashboard_versions` immediately before every restore, including a second restore in the same turn, so the expected-current guard is fresh. Review and acknowledge that exact saved `version_id` against current data before each restore; a missing acknowledgment raises `DashboardReviewRequired` before any live bytes change. A stale expected-current error means re-list and re-resolve; never retry with a guessed id.

If the selected definition fails current compilation or attachment validation, `DashboardVersionRestoreError` carries `code="saved_definition_incompatible"`, `version_id`, `current_version_id`, `cause_type`, and `fix_hint`; the live dashboard remains unchanged. Surface the product-level incompatibility, restate that restores use current data, and ask whether to choose another version or repair that saved definition. After success say: “Restored the dashboard definition from <local time>. It is using the latest available data.”

## Completion evidence

A diagnosis is complete when the cause and owner are identified. A repair is complete only when:

- no required canonical file is missing;
- error findings relevant to the incident are gone;
- every remaining quality warning has been surfaced and not silently
  transformed away;
- the current review is non-`BLOCK`, its flagged panels were inspected, and its exact signature is acknowledged before publish;
- `attachment_gaps` is empty;
- registry match count is one and cadence is aligned;
- a clean refresh reports success;
- the dependency graph confirms the repaired producer/consumer path;
- new telemetry does not reproduce the incident, when browser evidence was part of the report.

User-facing completion is concise product language: acknowledge, state the fixed/live outcome, optionally paraphrase `describe_dashboard(FOLDER)["text"]` for layout sync, and give the portal URL when useful.
