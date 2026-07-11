# ECharts dashboard router

- **Context ID:** `echarts.router`
- **Owns:** `route.surface`, `route.intent`, `route.fetch`, `route.message`
- **Fetch when:** Always loaded when dashboard intent is present.
- **Depends on:** None.

ECharts is the only sanctioned path for persistent PRISM dashboards. PRISM authors Python plus a JSON manifest and calls the public `dashboards` APIs. Do not hand-roll HTML/CSS/JS, use another dashboard framework, or use Altair composites as dashboards.

## User-message contract

Dashboard construction is invisible plumbing. Unless the user explicitly asks for implementation detail:

- Say what is live, fixed, or blocked in product language.
- Never expose file names, manifests, datasets, widgets, pipelines, runners, validation codes, registry mechanics, or architectural options.
- Pick implementation paths yourself. Ask only product questions whose answer changes what the user sees.
- Do not promise work after the response. Complete the build or edit before replying.
- A failure response is at most: product-level acknowledgement, present/past-tense action, and one product-level question if no defensible choice exists.

Success handoff uses exactly:

`http://reports.prism-ai.url.gs.com:8501/users/{kerberos}/dashboards/{dashboard_id}/`

Use `http`, port `8501`, the author's kerberos, the folder-leaf dashboard id, and the trailing slash. Never hand off an S3 HTML path.

## Tool 1 prerequisites

Before authoring a first build:

1. Use the canonical folder `users/{kerberos}/dashboards/{dashboard_id}`.
2. Every persisted data script defines that literal as `SESSION_PATH` and imports every helper it calls.
3. Every pull writes to `f"{SESSION_PATH}/data"`; `name=` becomes the CSV stem and must match the manifest dataset key byte-for-byte.
4. Persist `scripts/pull_data.py`, define a module-level `PULLS` mapping, run each entry with `run_pull(folder, name)`, and verify the persisted CSV columns and rows.
5. Use real data. Never invent identifiers, visible numbers, or successful results.

Pull primitives:

| Function | Required naming result |
|---|---|
| `pull_haver_data(..., name="cpi")` | `data/cpi.csv` |
| `pull_plottool_data(..., labels=[...], name="rates")` | `data/rates.csv` |
| `pull_fred_data(..., name="labor")` | `data/labor.csv` |
| `pull_market_data(..., name="rates", mode="eod")` | `data/rates_eod.csv` |
| `save_artifact(..., name="screen")` | `data/screen.csv` or JSON according to payload type |

## Route before fetching

Classify the request, then issue the smallest applicable `list_ai_repo(file_paths=[...], mode="full")` call. Pass only `file_paths` and `mode`. Never call `get_context()` again during the same user turn.

**Initial** means the first context fetch after the user prompt. **Adaptive** means a later fetch at a newly reached phase boundary. Fetch for the current phase only; context needed by a later phase is not an initial requirement unless that later phase is already explicit in the prompt.

| Intent at the current phase | First fetch for that phase |
|---|---|
| First build | `dashboards_hub.md`, `dashboards/build.md`, then only primitive spokes required by the requested artifact |
| Manifest/layout/widget/filter edit | `dashboards_hub.md`, `dashboards/template_crud.md`, plus the affected primitive spoke |
| Pure pull source/column/parameter edit with no derived dataset or `TRANSFORMS` change | `dashboards_hub.md`, `dashboards/pipelines.md` only |
| Derived dataset or `TRANSFORMS` operation: rolling/window, lag, normalization, join/pivot/reshape, or any other derived shape | `dashboards_hub.md`, `dashboards/pipelines.md`, `dashboards/recipes.md` |
| Read-only diagnosis | `dashboards/diagnose.md` only |
| Revert or heal reached during an active turn | `dashboards/diagnose.md` first; fetch repair context only after inspection identifies its owner |
| Chart authoring | `dashboards/charts.md` |
| KPI/table/pivot/stat/image/markdown/divider | `dashboards/widgets.md` |
| `widget: tool` with stat, table, or stat_grid outputs and no sibling/dashboard chart | `dashboards/widget_tool.md`, `dashboards/widgets.md` |
| `widget: tool` with a sibling/dashboard chart or chart/series output requiring chart specs | `dashboards/widget_tool.md`, `dashboards/widgets.md`, `dashboards/charts.md` |
| Filters, zoom, click-to-filter, sync, brush | `dashboards/filters.md` |
| Chart-choice archetype without a pipeline operation | `dashboards/recipes.md` |

Every tool build requires the widgets companion: it owns the stat, table, and stat_grid presentation contracts. Add charts only for the charted-tool row above.

### Adaptive phase rules

| Rule | Trigger and timing | Fetch |
|---|---|---|
| `adaptive.inspect` | A build or edit reaches inspection, destructive dependency analysis, or post-edit verification. Fetch at that decision point, immediately before `inspect_dashboard`; never include this file in the initial build/edit fetch. | `dashboards/diagnose.md` |
| `phase.manifest_after_build` | A first build crosses into typed manifest operations. Before the first `apply_manifest_operations` call, ensure this context is loaded. It may join the initial fetch only when the prompt already states that same-turn second phase; otherwise fetch when the phase becomes known. | `dashboards_hub.md`, `dashboards/template_crud.md`, plus every affected primitive spoke |
| `phase.revert` | Reversion from retained template, transaction, or script bytes is reached during an active turn. Diagnosis owns inspection and exact rollback. Fetch a repair owner only when evidence shows retained bytes are insufficient or another persisted surface must be repaired; verification may refetch diagnosis alone. | `dashboards/diagnose.md` |
| `evidence.repair_owner` | After `inspect_dashboard`, classify a required repair through the exhaustive evidence map below and fetch its one matching branch. Selecting diagnosis now plus the mandated unique branch later is route-complete deterministic deferred routing, not router ambiguity. | Exactly one evidence-map branch; never guess multiple owners or fetch all |

### Evidence-deferred repair map

| Inspection evidence | Unique repair fetch |
|---|---|
| Manifest, layout, widget, filter, link, or metadata defect | `dashboards_hub.md`, `dashboards/template_crud.md`, plus the evidence-identified primitive |
| Pull source, `build.py`, CSV, or attachment defect with no derived-shape change | `dashboards_hub.md`, `dashboards/pipelines.md` |
| Transform or derived-shape defect: rolling/window, lag, normalization, join/pivot/reshape | `dashboards_hub.md`, `dashboards/pipelines.md`, `dashboards/recipes.md` |
| First-build transaction or registration defect | `dashboards_hub.md`, `dashboards/build.md` |

Read-only diagnosis is the only request that includes diagnosis in its initial fetch:

```python
list_ai_repo(file_paths=["dashboards/diagnose.md"], mode="full")
```

For build/edit work, fetch `dashboards/diagnose.md` separately when `adaptive.inspect` fires. Call `inspect_dashboard(folder)` before choosing a destructive change or repair and after mutation for verification. Its findings, graph, refresh evidence, registry state, and telemetry identify the owner. A later `list_ai_repo` call is allowed when that evidence identifies the repair surface; fetch only the hub if mutation needs cross-cutting contracts, the owner spoke, and any primitive reference needed to author the fix.

## Adaptive bundles

These are measured context bundles, not mandatory bulk loads:

| Bundle | Exact fetch |
|---|---|
| Typical create | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/build.md", "dashboards/charts.md", "dashboards/widgets.md"], mode="full")` |
| Filtered create | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/build.md", "dashboards/charts.md", "dashboards/widgets.md", "dashboards/filters.md"], mode="full")` |
| Tool create | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/build.md", "dashboards/widget_tool.md", "dashboards/widgets.md"], mode="full")` |
| Charted tool create | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/build.md", "dashboards/widget_tool.md", "dashboards/widgets.md", "dashboards/charts.md"], mode="full")` |
| Typical manifest edit | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/template_crud.md", "dashboards/charts.md"], mode="full")` |
| Pure pull edit | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/pipelines.md"], mode="full")` |
| Derived transform edit | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/pipelines.md", "dashboards/recipes.md"], mode="full")` |
| Typical diagnosis | `list_ai_repo(file_paths=["dashboards/diagnose.md"], mode="full")` |
| Explicit tool build then typed edit | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/build.md", "dashboards/template_crud.md", "dashboards/widget_tool.md", "dashboards/widgets.md"], mode="full")` |
| Explicit charted tool build then typed edit | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/build.md", "dashboards/template_crud.md", "dashboards/widget_tool.md", "dashboards/widgets.md", "dashboards/charts.md"], mode="full")` |

## File map

The router is the only fetch menu. The production context inventory is:

| File | Authority |
|---|---|
| `dashboards_hub.md` | Cross-cutting manifest, public API, layout, registry, and anti-pattern kernel |
| `dashboards/build.md` | First-build Tools 1-4 |
| `dashboards/diagnose.md` | Inspect, triage, heal, and revert |
| `dashboards/template_crud.md` | Typed manifest operations |
| `dashboards/pipelines.md` | Persisted pull/build script edits and data-flow integrity |
| `dashboards/recipes.md` | Data archetypes and transform patterns |
| `dashboards/charts.md` | Chart catalog, mappings, annotations, computed columns |
| `dashboards/widgets.md` | Non-tool widget catalog, popups, provenance, markdown |
| `dashboards/widget_tool.md` | Form-driven compute widgets |
| `dashboards/filters.md` | Filter catalog, linking, zoom, sync, brush |

## Atomic completion

- First build means all four tools in [build.md](dashboards/build.md#four-tool-transaction) complete in one turn.
- An edit means inspection, the owner API, recompile, clean refresh verification, and portal handoff complete before responding.
- A missing product decision may block. Mechanical uncertainty does not: follow structured engine fix hints.
- Never report success from `validate_manifest` alone. The persisted dashboard must pass the final refresh path and report `refresh_status.status == "success"`.
