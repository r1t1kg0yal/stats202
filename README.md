# staging/

PRISM-bound outputs + cross-project meta. Everything in this folder is
either (a) an ephemeral drag-and-drop copy of a project's payload on
its way into PRISM, (b) the living projects roster below, (c) a
PRISM-facing context-extraction prompt, or (d) a scratch capture space.

```
┌─────────────────────────────────────────────────────────────────────┐
│ THREE-SUBTREE REPO MODEL (since 2026-05-02 restructure)             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   projects/    ACTIVE MULTI-SESSION DEV                             │
│                projects/<name>/<name>-payload/  is CANONICAL        │
│                projects/<name>/dev/             is HOW WORK HAPPENS │
│                                                                     │
│   staging/     PRISM-BOUND OUTPUTS                                  │
│                staging/<name>-payload/          is EPHEMERAL COPY   │
│                staging/prompts/                 is PRISM PROMPTS    │
│                staging/README.md                is THIS FILE        │
│                                                                     │
│   GS/          LIBRARIES PRISM CONSUMES (non-active)                │
│                skills, models, scrapers, pipelines, ontologies,     │
│                knowledge, tools, products                           │
│                                                                     │
│   prism/       HOW PRISM WORKS (orientation SSOT)                   │
│                curated docs Cursor reads before editing projects/   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The counterpart to `staging/` is `prism/` — the curated PRISM-side SSOT
that Cursor reads whenever it edits anything under `projects/` or `GS/`
that has to interoperate with PRISM. Where `prism/` describes how PRISM
works, `staging/README.md` below describes what is being built for
PRISM right now.

---

## Staging projects (the living cheat sheet)

```
┌─────────────────────────────────────────────────────────────────────┐
│ STATUS AT A GLANCE                                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  altair       ████████████████████  mature (drag-and-drop ready)    │
│  echarts      ████████████████████  mature + 3 hardening sweeps     │
│                                       same day (10 always-blocking  │
│                                       codes total — 5 from chart    │
│                                       sweep + 2 from tool-widget    │
│                                       python-leak sweep + 3 from    │
│                                       empty-visual sweep; 65 stress │
│                                       fixtures across V01-V08;      │
│                                       canonical reference JSON +    │
│                                       Tool 4 subprocess contract +  │
│                                       no-static-values rule + new   │
│                                       script-preservation rule      │
│                                       (§2.5.5) + path-decision      │
│                                       table (§6.0) + derivation     │
│                                       playbook (recipes.md §7))     │
│  apis         ████████████████████  rule codified (S8 batch ready)  │
│  whitepapers  █████████████░░░░░░░  workshop PLAN LOCKED + intake   │
│                                       verified + frontmatter on all │
│                                       5 inherited docs              │
│  frontend     ████████████████░░░░  MVP + FULL REFACTOR + UI UPLIFT │
│                                       (URL grammar unified, white   │
│                                       papers from filesystem,       │
│                                       design tokens realized, plus  │
│                                       the 2026-05-03 frontmatter-   │
│                                       driven doc system: registry   │
│                                       pipeline in views.py,         │
│                                       enriched doc_page chrome,     │
│                                       topic-chip listings, home     │
│                                       featured block; awaiting      │
│                                       PRISM-verbatim payload sync)  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Project | Maturity | Repo path (canonical) | Payload source | PRISM destination | Rule | prism/ refs | Active endeavor / spec |
|---------|----------|-----------------------|----------------|-------------------|------|-------------|------------------------|
| altair | mature | `projects/altair/` | `projects/altair/altair-payload/` | `mcp/utils/chart_functions.py` + `context/modules/static/chart_context.md` (single-file L2 module) | `.cursor/rules/viz-platforms.mdc` | `code-sandbox.md`, `mcp-utils.md`, `vision-qc.md`, `mcp-tools.md` §3+§5 | `projects/altair/dev/specs/composites.md` (next feature build) |
| echarts | mature | `projects/echarts/` | `projects/echarts/echarts-payload/` | `ai_development/dashboards/*.py` + `context/modules/static/tools/dashboards.md` (hub) + `dashboards/*.md` (spokes) | `.cursor/rules/viz-platforms.mdc` | `dashboard-refresh.md`, `dashboards-portal.md` | — |
| apis | 2/24 rebuilt + rule codified, Session 8 batch ready | `projects/apis/` | `projects/apis/apis-payload/clients/*.py` + `apis-payload/modules/*.md` | `mcp/clients/*_client.py` + `context/modules/static/{data_guides,instruments,tools}/*.md` | `.cursor/rules/api-clients.mdc` | `gs-proxy.md`, `api-clients.md`, `data-functions.md` §0 | `projects/apis/dev/endeavors/apis_endeavor.md` (8-session plan) |
| frontend | MVP RUNNING + FULL REFACTOR + UI UPLIFT IN FLIGHT | `projects/frontend/` | `projects/frontend/frontend-payload/ai_development/` | `ai_development/mysite/` + `ai_development/mysite/news/static/css/{tokens,fonts,base}.css` + settings.py PATCH (STATICFILES_DIRS) + URL-grammar unification (10 legacy URLs 301 to canonical) + filesystem reads from `ai_development/context/white_papers/` (was S3 `secondary/technical_docs/`) + frontmatter-driven `_doc_registry()` pipeline in views.py + enriched `doc_page.html` chrome (TOC, breadcrumbs, related, prev/next) + topic-chip listings + home featured-resources block | — | `dashboards-portal.md`, `architecture.md` §10 | `projects/frontend/dev/specs/ui_uplift.md` (per-surface UI uplift plan; locked 2026-05-03); `projects/frontend/dev/specs/design_system.md` (token + component SSOT); `staging/prompts/open/2026-05-02_frontend_full_context.md` (PRISM-verbatim sync prompt) |
| whitepapers | intake VERIFIED + workshop PLAN LOCKED + frontmatter on all 5 inherited docs | `projects/whitepapers/` | `projects/whitepapers/whitepapers-payload/*.md` | `ai_development/context/white_papers/{whitepaper_data_integrations,whitepaper_user_personalization,whitepaper_world_state_and_reasoning,faq,email_usage_guide}.md` (filenames change to canonical slugs once workshop pass renames per `dev/specs/whitepaper_workshop.md` §8) | — | sourced from `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md` (OCR) + `2026-05-02_whitepapers_s3_verify_reply.md` (S3 verbatim verify). Plan: `projects/whitepapers/dev/specs/whitepaper_workshop.md`. | All 5 inherited docs now have YAML frontmatter (slug + title + format + topic + audience + last_updated + reading_time + summary + related + sequence + featured). Body workshop pass: collapse to 6-doc target set (3 whitepapers + 3 guides; "What is Prism" + "Getting started" are NEW). Spread across whitepapers turns 2-4 (workshop_spec §7). Dual-surface lock DEFERRED — workshop customer-facing first, L2 alignment is follow-up. |

Always-applied rule: `.cursor/rules/prism.mdc` (the repo orientation).
Orthogonal rule: `.cursor/rules/skill-discipline.mdc` (applies to every
skill/context file under `context/modules/static/`).

---

## Payload flow

```
                   ┌──────────────────────────────┐
   CANONICAL       │ projects/<name>/<name>-      │
   (source of      │   payload/                   │
    truth)         │                              │
                   │ edited here. demos, tests,   │
                   │ stub mirror, feedback, and   │
                   │ notes live alongside at      │
                   │ projects/<name>/{dev,        │
                   │                  ai_develop- │
                   │                  ment}/      │
                   └───────────────┬──────────────┘
                                   │
                                   │ user copies by hand
                                   │ when ready to promote
                                   ▼
                   ┌──────────────────────────────┐
   EPHEMERAL       │ staging/<name>-payload/      │
   (drag-and-drop  │                              │
    scratch zone)  │ may be stale between         │
                   │ promotions. NEVER edited     │
                   │ directly — always a copy of  │
                   │ projects/<name>/<name>-      │
                   │   payload/.                  │
                   └───────────────┬──────────────┘
                                   │
                                   │ user drags into PRISM
                                   │ (copy-paste into PRISM source)
                                   ▼
                   ┌──────────────────────────────┐
   PRISM           │ ai_development/... in the    │
                   │ PRISM repo. Downstream-read- │
                   │ only. Never edited there.    │
                   └──────────────────────────────┘
```

This flow applies uniformly to altair, echarts, apis. For frontend the
flow materialises when the first payload lands.

---

## test_prompts/ convention (cross-project)

Every project's payload folder carries a `test_prompts/` subfolder.
Apis (D7 / D13 in `projects/apis/dev/endeavors/apis_endeavor.md`)
established the shape; altair / echarts adopted it on 2026-05-02.
Whitepapers is deferred (portal-served documents, not chat-loaded
context — `test_prompts/` is reconsidered after the workshop pass).
Frontend is N/A (no payload yet).

```
projects/<name>/<name>-payload/test_prompts/
├── <unit_1>_test.md     ← one file per natural unit:
├── <unit_2>_test.md       per-topic (altair), per-spoke (echarts),
└── ...                    per-source (apis)
```

| Aspect | Rule |
|---|---|
| Files per project | One per natural unit (topic / spoke / source). 5-7 files per project today. |
| Prompts per file | 7 canonical prompts that mix broad regression coverage AND specific recent-implementation tests for that unit. |
| Format | Pure prompt bodies separated by `---` horizontal rules. No headers, no frontmatter, no annotations. |
| Per-prompt convention | Each body is 1-3 sentences ending with "Let me know if frictions." |
| Drag-and-drop status | STAGING-ONLY. Carve-out from the byte-identical-payload invariant: `test_prompts/` does NOT ship to PRISM. The user drops `clients/` + `modules/` (apis), or the payload `.py` / `.md` files (altair / echarts) — NEVER `test_prompts/`. |
| Two purposes | (1) **Per-iteration verification** — Cursor surfaces the 1-2 most discriminating prompts to the user as the success-criterion loop after promoting a unit to PRISM. (2) **Regression sweep** — re-paste any subset after a payload update to verify nothing regressed. |
| Loop shape | User pastes prompt body into PRISM → PRISM responds → no frictions = unit is done; frictions = user pastes the reply back, Cursor iterates payload + prompt, loop. The same `<unit>_test.md` is reusable across iterations. |

Per-project unit count and file inventory:

| Project | Units | Files in `test_prompts/` |
|---|---|---|
| apis | per-source | 2 today (`treasury_test.md`, `treasury_direct_test.md`); grows as more clients are rebuilt (target ~20) |
| altair | per-topic | 6 (`chart_types`, `mapping`, `annotations`, `dual_axis`, `composites`, `chart_center`) — topic split is independent of the single-file `chart_context.md` skill |
| echarts | per-spoke | 6 (`charts`, `widgets`, `widget_tool`, `filters`, `recipes`, `pipelines`) — 6/6 bodies seeded as of 2026-05-02. `widget_tool_test.md` (4 manifest-preservation regression + 3 canonical-example cribs); `widgets_test.md` (3 popup-parity regression + 4 row_click drill-down / KPI / stat_grid / pivot); `recipes_test.md` (2 data-pipeline coupling + 2 revert + 3 long-form/dual-axis/RV/computed-columns); `charts_test.md` (broad coverage of the 30-type catalog + corner cases: correlation_matrix, scatter_studio, multi-axis, computed columns, heatmap palette); `filters_test.md` (10 types + 11 ops + cascading + dataZoom sync + click_emit + compound rule + scope + show_when); `pipelines_test.md` (catalog the pipeline graph + 3 reuse-ladder paths + active-pipeline integrity + re-author end-to-end + session folder health check) |
| whitepapers | — (deferred) | 0 |
| frontend | — (no payload) | 0 |

This convention is intentionally **not codified as a `.cursor/rules/`
file yet** — same wait-for-pattern-to-prove-itself discipline applied
to apis (no `api-clients.mdc` until Session 7) and whitepapers. After
at least one full feedback loop on a non-apis project, the cross-
project shape can be promoted to a rule if drift warrants it.

---

## Per-project details

### altair — static PNG chart engine

The single-chart builder (`make_chart`) and the composite family
(`make_2pack_*`, `make_3pack_*`, `make_4pack_grid`, `make_6pack_grid`).
Produces static PNGs (and an interactive HTML companion) for chat,
email, and report flows.

| Aspect | Value |
|---|---|
| Drag-and-drop status | READY. 15/15 demos pass. PRISM-runtime introspection confirmed every helper signature + the verbatim 14-entry namespace literal + sole-consumer property (`mcp/tools/script_exec_tools.py`). A live PRISM session is the only remaining verification step. |
| Canonical payload | `projects/altair/altair-payload/chart_functions.py`, `chart_functions_studio.py`, `chart_context.md` (single-file L2 module) |
| Stub mirror | `projects/altair/ai_development/mcp/utils/*.py` — mirrors the 5 helpers `chart_functions.py` imports |
| Pinned interpreter | `projects/altair/.venv/` (regenerate after the 2026-05-02 restructure — shebangs point at old `GS/viz/altair/.venv/` paths) |
| Demo gallery | `projects/altair/dev/demos/01..25_*.py` (one file per demo; `run_all.py --all`) |
| Skill shape | Single-file L2 module. `chart_context.md` carries the full surface (~900 lines / ~43 KB) — namespace + QC + design defaults + authoring rules + chart types + mapping + annotations + dual-axis + composites + Chart Center + dimensions + horizons + failure transparency. `TestChartContextCoverage` in `dev/tests.py` pins skill/engine drift (every chart type / annotation class / composite function in the engine appears in the skill). Hub-and-spoke split landed 2026-05-02 and was reverted same-week in favor of single-file ergonomics. |
| QC workflow | `workflows/altair_qc.md` — adversarial vision + validation hardening |
| Notes file | `projects/altair/dev/notes.md` |
| Tests | `projects/altair/dev/tests.py` (`python tests.py` interactive; `python tests.py unit -v` headless). Currently houses `TestChartContextCoverage` (skill/engine drift gate) + `TestGroupedBarCellBudget` (cell-budget regression). |
| Test prompts | `altair-payload/test_prompts/{chart_types,mapping,annotations,dual_axis,composites,chart_center}_test.md` — one per topic area, 7 prompts each. Per the cross-project convention. STAGING-ONLY (does NOT ship). The 6-topic split is regression-coverage scaffolding, independent of the single-file skill. |
| Active feature work | `projects/altair/dev/specs/composites.md` — 4-batch plan for layered composites, forecast styling, new annotation classes (`BarValueLabels`, `BarHighlight`, `Connector`, `SeriesLabel`), two-level x-axis |
| Feedback queue + external signals (UPDATED 2026-05-03) | 3 distinct incidents + 1 cross-project signal in `projects/altair/dev/feedback/` and `dev/notes.md` §External-signals / §Cross-project-signals. **FEEDBACK (3):** (a) `2026-04-26-2333-stress-test-results.md` — engine stress harness; (b) `2026-05-02_4pack_blowout.md` — grouped-bar 4-pack cell-budget blowout (RESOLVED — facet-width math now subtracts spacing overhead; 3px readability gate raises `GROUPED BAR CELL-BUDGET ERROR`; `TestGroupedBarCellBudget` pins); (c) `2026-05-02_chartspec_y_title_kwarg.md` — `ChartSpec(y_title=...)` hallucinated kwarg (skill rule lives in `chart_context.md` §7.1 + §10.2; optional engine convenience kwarg remains open). **PRISM DIAGNOSTIC (1):** `scans/prism/2026-05-02_bimodal_stir_report_diagnostic.md` issue 2 — heatmap >12 color cardinality silent-fail (skill rule lives in `chart_context.md` §6.3; optional `_validate_chart_inputs` binning-named error remains open). **CROSS-PROJECT SIGNAL (1, NEW 2026-05-02):** GS Sans font registration for matplotlib — `projects/frontend/dev/notes.md` §A has the plan; sequenced AFTER frontend staging fonts mirror lands. Engine edit adds `_register_gs_fonts()` at `chart_functions.py` import time (matplotlib sandbox workaround — PRISM hard-blocks matplotlib imports at the sandbox surface) and flips `GS_CLEAN` `"font.family"` from `"Liberation Sans, Arial, sans-serif"` to `"GS Sans, Helvetica Neue, Arial, sans-serif"`. Details in `projects/altair/dev/notes.md` "Cross-project signals". |

### echarts — interactive HTML dashboard compiler

The `compile_dashboard` pipeline + a hub-and-spoke skill. Emits
self-contained HTML dashboards with the echarts JS inlined; no external
dependencies at render time.

| Aspect | Value |
|---|---|
| Drag-and-drop status | VERIFIED end-to-end (local tests + demos). 14/14 production demos build cleanly under the 2026-05-03 hardening regime; 618/620 unit tests pass (the 2 baseline `TestMultiAxis` failures are pre-existing per `dev/notes.md`). |
| Canonical payload | `projects/echarts/echarts-payload/` — `__init__.py`, `config.py`, `echart_*.py`, `rendering.py`, `dashboards.md` (hub) + `dashboards/*.md` (6 spokes) + `dashboards/canonical_showcase.json` (templated `build_showcase` reference manifest, ~111 KB; landed 2026-05-03). The `*.json` glob is part of the drag-and-drop contract per `.cursor/rules/viz-platforms.mdc`. |
| Static-asset mirror | `projects/echarts/ai_development/mysite/news/static/js/echarts.js` (no Python stub mirror needed — stdlib + pandas only) |
| Playwright sweep | `projects/echarts/dev/inspect_dashboard.py` |
| Skill shape | Hub-and-spoke since 2026-05-01. `dashboards.md` is the L2 hub; per-primitive depth in `dashboards/{charts,widgets,widget_tool,filters,recipes,pipelines}.md`. The 6th spoke (`pipelines.md`) landed 2026-05-02 alongside the hub-level "2-script nucleus" framing. The hub gained a top-of-file "dashboard folder = workspace" framing + Rule 9 + Tool 4 (subprocess refresh as final action) on 2026-05-03; build flow promoted from 3-tool to 4-tool. `TestSpokeDriftPrevention` pins the hub/spoke/engine triple; `TestCanonicalShowcaseDrift` pins `canonical_showcase.json` to `build_showcase`. |
| Validation gates (always-blocking; 2026-05-03 hardening sweeps) | 10 ALWAYS_BLOCKING_ERROR_CODES landed across three sweeps the same day. **Chart sweep (2026-05-03 morning):** (a) `chart_too_many_series` — line / multi_line / area capped at 4 y-series (wide-form via validator; long-form via CDD); (b) `kpi_static_value_forbidden` + (c) `stat_grid_static_value_forbidden` — every visible number must source from a refreshable dataset (Rule 1 extension); plus the engine error-message contract was rewritten so `r.error_message` carries the FULL diagnostic body on any validate-failure return. **Tool-widget sweep (2026-05-03 evening, against the Fed Scenario Tool python-leak incident):** (d) `tool_compute_python_literal_in_js` — Python literals (`None` / `True` / `nan` / `Timestamp(...)` / `Decimal(...)` / etc.) leaked into a `widget: tool`'s compute_js source produce a runtime `compute error: <token> is not defined` and a blank right panel; the `_scan_compute_js_for_python_literals` static scanner blocks at validate time; (e) `tool_compute_missing_output_key` — declared output ids that don't appear as `<id>:` keys in the compute return literal silently render the right panel as empty; the `_check_compute_returns_all_outputs` heuristic (regex-based after JS string/comment stripping) blocks at validate time. **Empty-visual sweep (2026-05-03 evening):** (f) `table_dataset_empty` PROMOTED from severity="warning" to error + added to ALWAYS_BLOCKING (was papering over a header-only table render); (g) `pivot_dataset_empty` NEW — pivot widget on 0-row dataset renders empty grid (no row dims / col dims / value cells); (h) `pivot_column_missing` NEW — pivot's row_dim_columns / col_dim_columns / value_columns reference a column not in the materialised dataset. Empty-data for KPI / stat_grid already covered indirectly via `kpi_source_no_numeric_values` / `stat_grid_source_unresolvable`; chart via `chart_dataset_empty`; V08 fills the table + pivot legs. All 14 demos refactored to source-drive every KPI / stat_grid item (7 new synthetic stat datasets across showcase + 6 production demos). |
| Stress harness coverage | `dev/qc_runner.py` runs 8 deterministic test sets (V01-V08) totalling 65 fixtures, all comprehensive: V01 missing-required (12) / V02 comprehensive-error-delivery (4) / V03 line-cap (8) / V04 messy-data (8) / V05 edit-regression (6) / V06 pipeline-graph integrity (5) / V07 tool-widget compute_js leak class (15: 10 python-leak + 3 missing-output + 2 false-positive guards) / V08 empty-visual hardening (7: 4 block + 1 cross-stream + 2 must-NOT-block guards). The previous V07 reservation (refresh-runner namespace gap) is PRISM-side-only and skipped — tracked in `dev/notes.md` "Still open". |
| Notes file | `projects/echarts/dev/notes.md` |
| QC workflow | `workflows/dashboard_qc.md` — adversarial manifest synth + vision grading |
| Test prompts | `echarts-payload/test_prompts/{charts,widgets,widget_tool,filters,recipes,pipelines}_test.md` — one per spoke, 7 prompts each. Per the cross-project convention. STAGING-ONLY (does NOT ship). 6/6 seeded as of 2026-05-02: `widget_tool_test.md` (manifest-preservation regression + canonical-example cribs); `widgets_test.md` (popup-parity regression + row_click drill-down + thesis/watch/risk markdown + KPI/stat_grid + pivot); `recipes_test.md` (data-pipeline coupling + revert + long-form/dual-axis/RV/computed); `charts_test.md` (30-type catalog coverage + correlation_matrix, scatter_studio, multi-axis, computed columns, heatmap palette); `filters_test.md` (10 types × 11 ops, cascading, dataZoom sync, click_emit, compound rule, scope, show_when); `pipelines_test.md` (catalog the pipeline graph + reuse-ladder paths + active-pipeline integrity + re-author end-to-end + session folder health check). The full set verifies the manifest-preservation + popup-parity + data-pipeline-coupling + revert + parameterised-input fixes plus the new 2-script nucleus + pipeline-aware framing landed across `dashboards.md` §0 + §6.0 + `dashboards/{pipelines,recipes,widgets,widget_tool}.md` on 2026-05-02. |
| Feedback queue (UPDATED 2026-05-03) | 7 distinct dashboard incidents in `projects/echarts/dev/feedback/` covering 5 dashboards across 12 days: Fed Scenario Tool (manifest loss on rebuild + tool-widget python-leak), Fed Taylor Rule (parameterised inputs), NFP InstantRead × 3 (tab-3 birth-death + popup MA toggle bug; sector-wage chart redesign + revert; tab-1 row_click popup + AHE MoM/YoY mismatch), TIPS RV (3-iteration manifest validation series). All five cross-cutting patterns now ADDRESSED via skill-side + engine-side fold-ins: **MANIFEST-PRESERVATION** (`dashboards.md` §2.5.4 + `dashboards/recipes.md` §3 + `dashboards/widget_tool.md` §1; READ → MERGE → WRITE with surgical mutation helpers); **POPUP-PARITY** (`dashboards/widgets.md` §3 capability-allow-list + filter-scoping rule); **DATA-PIPELINE COUPLING** (`dashboards/recipes.md` §4 propose-and-confirm decision table + refresh-runner namespace audit); **REVERT WORKFLOW** (`dashboards/recipes.md` §5 chat-description / history / archive recovery paths); **PARAMETERISED-INPUT** (`dashboards/widget_tool.md` §3.2 scalars-plus-series pattern + §2 crib clarification); **SCRIPT-PRESERVATION** (NEW 2026-05-03; `dashboards.md` §2.5.5 + §6.0 path-decision + §6.2 pull discipline + `dashboards/recipes.md` §6 surgical script edit + `dashboards/recipes.md` §7 derivation playbook + `dashboards/widget_tool.md` §1 compute_js-lives-in-template guard); plus engine-side `tool_compute_python_literal_in_js` + `tool_compute_missing_output_key` blocking codes (V07 stress). All six fold-ins have round-trip regression coverage in the corresponding `test_prompts/*_test.md` files (5/6 seeded; widget_tool_test.md gets the new compute_js scenarios next). Per-incident → spoke routing in `projects/echarts/README.md` "Feedback queue (active absorption)". |
| Engine-companion roadmap (still open as of 2026-05-03) | The 2026-05-03 hardening sweep landed the easier wins (validation gates + canonical reference + verbose `error_message` + Tool 4 contract + V03-V06 stress sets). Five engine companions remain in `projects/echarts/dev/notes.md` "Still open": (a) **manifest-template strict-mode** (`replace_existing=True` guard refusing to overwrite when widget-count drops > 30%) — would gate the rebuild-from-scratch wipe footgun and let V05 add the corresponding stateful stress fixture; (b) **first-class revert primitive** (`load_dashboard_revision()` sandbox helper); (c) **refresh-runner namespace expansion** — closes the V07 gap (`save_artifact` + alt-data clients not in `_build_exec_namespace`); (d) **`_audit_pipeline_integrity()` companion** — stateful column-set diff vs pre-edit; would extend V06 with that subset; (e) **popup canvas full-feature parity** with inline charts (PRISM ticket TKT-20260430-110307-c9f93b); (f) **`raw` chart_type catalog/validator drift** + surfacing `dataset_dti_no_date_column` through compile_dashboard. None are blocking; each would tighten the existing surface. |

### apis — external API client platform

17 PRISM-side clients (treasury, treasurydirect, fdic, bis, ofr,
sec_edgar, prediction_markets, …) plus 7 staging-only sources. Unified
plug-and-play layout — 20 clients + 20 guide markdowns built as of
2026-05-02.

| Aspect | Value |
|---|---|
| Status | 2/24 reference rebuilds done (treasury Bucket A + treasurydirect Bucket B); `.cursor/rules/api-clients.mdc` codified (422 lines). Both transport buckets exercised end-to-end. Stub mirror live; 10 demos pass live (2 Session 4 smoke + 4 Session 5 treasury + 4 Session 6 treasurydirect). Session 8 (batch migrations using the codified rule) is the next step; remaining 22 sources can be migrated self-serve from the rule. |
| Canonical payload | `projects/apis/apis-payload/{clients,modules,test_prompts}/` (three flat subfolders. clients/ + modules/ ship byte-identical to PRISM; test_prompts/ is staging-only per D7 carve-out — user sorts the `.md` modules into PRISM pillars on drop per D7) |
| Stub mirror | `projects/apis/ai_development/mcp/gs_app_proxy_negotiate.py` (live; vanilla `requests` fallthrough; satisfies all 3 `_USE_GS_PROXY` patterns transparently per L2) |
| Harness | `projects/apis/dev/_harness.py` (live; `setup_sys_path()` + `banner` / `report` / `run_or_menu` helpers) |
| Reference rebuilds shipped | treasury (Bucket A, Session 5) + treasurydirect (Bucket B, Session 6). Both 2026-05-02. 22 remaining. Pre-existing wrapper bug fixed during treasury rebuild: `get_avg_interest_rates` field-name mismatch (`security_type` → `security_desc:eq:Treasury <X>` translation). |
| Smoke + reference demos | 10 demos in `dev/demos/` — all pass live: 00_smoke_session_and_auth, 00_smoke_manual_https_request (Session 4 transport smoke), 01-04 treasury exercises (Session 5), 05-08 treasurydirect exercises (Session 6). |
| D13 test prompts | `apis-payload/test_prompts/<src>_test.md` — canonical home for the per-source PRISM round-trip prompts. STAGING-ONLY (carve-out from byte-identical invariant per D7); does NOT ship to PRISM. One file per migrated client; 7 prompts per file in pure-body / `---`-delimited format per D7 convention. Currently: `treasury_test.md`, `treasury_direct_test.md`. |
| Transport buckets | 3 (per L1 in `apis_endeavor.md`): A = standard requests proxy (6 clients), B = manual CONNECT (5), C = direct vanilla requests (6). Plus `newyorkfed` as a function-injection exception (L4). |
| Session-by-session plan | `projects/apis/dev/endeavors/apis_endeavor.md` (8 sessions; 1-7 complete) |
| Next session | Session 8 — first batch of migrations using the codified rule. Default order per D10 + priority hints: Bucket C wins first (cftc / congress / federal_register / usitc / ofac / openfigi — 6 zero-stub-dependency wins), then Bucket A fdic, then Bucket B bis + ofr. |
| Pre-payload archives | `projects/apis/dev/archive/_pre_payload/<src>/` (24 per-source folders; treasury's archived during Session 5; each future migration archives here) |
| Source inventory | `projects/apis/README.md` (24 sources + per-source migration table) |
| Rule | `.cursor/rules/api-clients.mdc` (422 lines, scoped to `projects/apis/**`) — codified in Session 7 from the Sessions 5+6 patterns. Sessions 8+ migrations are self-serve from this rule. |

### frontend — staging mockup of PRISM's Django UI

Faux frontend infrastructure (Kerberos URL structure, S3 mock, sharing
rules, link structure, whitepaper refactor, UI aesthetics) so UI work
can happen here with browser access and Cursor vision on rendered
snapshots. Follows the viz/apis two-sided contract idea, but the
destination side is Django / mysite / templates, not the MCP layer.

| Aspect | Value |
|---|---|
| Status | MVP RUNNING + FULL REFACTOR + UI UPLIFT IN FLIGHT (2026-05-03). Staging boots via `python dev/run_staging.py`. **URL grammar unified** under `/dashboards/[<category>|<author>]/<id>/`, `/whitepapers/<slug>/`, `/guides/<slug>/`; 10 legacy URLs 301 to canonical (back-compat preserved). **White papers read from filesystem**, not S3 — `frontend-payload/ai_development/context/white_papers/<name>.md` symlinks to canonical `projects/whitepapers/whitepapers-payload/`. **Full token migration** — 84 inline styles → 10 new component classes in base.css; templates carry zero non-dynamic inline styles (only the 4 dynamic data-driven ones remain). **Frontmatter-driven doc system** (2026-05-03): `_doc_registry()` in views.py + `markdown.toc`-built sidebar + breadcrumbs + topic chips + featured-on-home + topic-grouped listings; replaces hardcoded WHITEPAPER_MAP. **GS fonts** via `dev/setup_fonts.sh` one-line copy from user's PRISM repo (Option A locked). 15 API endpoints still return 501 with TODO pointing at the PRISM-verbatim sync prompt. |
| Scoping doc | `projects/frontend/dev/prompt.md` |
| UI uplift spec | `projects/frontend/dev/specs/ui_uplift.md` (per-surface implementation plan locked 2026-05-03 — frontmatter schema, doc_page chrome, listings, home featured block, nav/footer refresh, PRISM-handoff plan) |
| Design system | `projects/frontend/dev/specs/design_system.md` — v0 SSOT (~840 lines). Every color, font, type size, spacing unit, and component primitive resolved to a named CSS variable. DNA-inspired by goldmansachs.com 2024 rebrand language (`#092C61` "Sky Blue" navy, alpha-on-black text tiers, sharp corners `--radius-none`, tight letter-spacing with `1px` only on uppercase labels). **Realized in CSS** at `frontend-payload/ai_development/mysite/news/static/css/{tokens.css, fonts.css, base.css}` plus the 2026-05-03 frontmatter-driven doc-system block (.topic-chip*, .doc-card*, .doc-page__*, .featured-resources*). Spec remains the SSOT. |
| Payload skeleton | `projects/frontend/frontend-payload/ai_development/mysite/` — Django app: settings.py (PATCHED with STATICFILES_DIRS = `[('fonts', BASE_DIR / 'fonts')]` + STATIC_ROOT), urls.py, news/{views.py (~700 lines, ~30 view fns + frontmatter-driven `_doc_registry()` pipeline + `_render_doc_body()` toc helper), urls.py, context_processors.py, apps.py}, 16 templates (base, home, dashboards, profile, whitepapers, user_guides, doc_page (rewritten 2026-05-03 with TOC + breadcrumbs + related + prev/next), observation views, access_denied, _todo, ...), static/css/{tokens,fonts,base}.css, static/images/{prism,gs}_logo.png. Byte-identical-to-PRISM target. |
| Staging stub mirror | `projects/frontend/ai_development/{core,staging_*.py}` — s3_bucket_manager mock (file-backed against dev/fixtures/s3/), report_server.py Flask shim (port 5001), staging_settings.py (wraps payload settings to set ROOT_URLCONF), staging_urls.py (mounts /staging-s3/<path>), staging_views.py (file server with magic-bytes content-type detection). Staging-only; never ships. PEP 420 namespace package trick lets `ai_development.*` resolve from BOTH frontend-payload/ AND projects/frontend/ at runtime. |
| Fixtures | `projects/frontend/dev/fixtures/s3/` — file-backed mock S3: prism_users_list, 2 access groups, goyalri/gaursi user manifests + dashboard registries + dashboard.html files, observatory snapshot with 3 demo observations, observatory dashboards registry with 3 system dashboards + dashboard.html files, 4 whitepaper/FAQ markdowns, 3 logos (SVG-content-named-as-PNG). |
| Entrypoint | `projects/frontend/dev/run_staging.py` — interactive CLI (default) + argparse subcommands (`up`, `django-only`, `flask-only`, `check`, `info`). Boots Flask + Django, sets sys.path / env / Kerberos cookie, opens browser. |
| Notes file | `projects/frontend/dev/notes.md` — §A matplotlib font registration helper plan for altair (cross-project edit, sequenced after staging fonts mirror lands), §B quarantine-package audit (weasyprint / playwright / cairo* not installed — confirm "not vetted" vs "not installed"), §C echarts font inheritance (already-correct, just waiting), §D open items |
| Input scans | `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md`, `projects/frontend/dev/scans/2026-05-02_portal_views_urls_templates.md`, `projects/frontend/dev/scans/2026-05-02_fonts_and_python_font_stack_reply.md` |
| Input feedback | `projects/frontend/dev/feedback/2026-05-02_s3_logo_storage_paths.md` |
| venv | `projects/frontend/.venv/` — Python 3.11.15 (matches altair); `Django 5.2.13`, `Flask 3.1.3`, `requests 2.33.1`, `markdown 3.10.2`, `PyYAML 6.0.3` (added 2026-05-03 for frontmatter parsing), `playwright 1.59.0` (dev-only, for screenshot QC). Recreate via `/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv` + `pip install Django Flask requests markdown PyYAML`. |
| Vision QC output | `projects/frontend/dev/output/uplift_2026-05-03/*.png` — playwright screenshots of every priority surface (home, listings filtered + unfiltered, doc pages for all 5 inherited docs). Visual diary across iterations. |
| Open prompt loop | `staging/prompts/open/2026-05-02_frontend_full_context.md` (1,092 lines) — comprehensive PRISM-verbatim sync prompt. Frontmatter updated with current staging state. Reply backfills the 15 API endpoint bodies + load-bearing template diffs (profile.html PRISM is 1,157 lines; staging is best-guess) + real S3 caching architecture + verifies inline-CSS migration faithfulness. The 2026-05-02 fonts prompt is archived. |
| Next step | (a) Workshop pass on the 6-doc set per `projects/whitepapers/dev/specs/whitepaper_workshop.md` (whitepapers turns 2-4). (b) Generate the PRISM-side handoff prompt bundle per `projects/frontend/dev/specs/ui_uplift.md` §6 (covers views.py + 5 templates + CSS appends). (c) Send `2026-05-02_frontend_full_context.md` to PRISM; reply upgrades payload from "partial-scan-derived" to "PRISM-verbatim". (d) Manually copy 20 GS Sans TTFs from PRISM repo into `frontend-payload/ai_development/mysite/fonts/` (Option A locked 2026-05-02; gitignored). (e) Spin up `staging/prompts/open/YYYY-MM-DD_pdf_snapshot_audit.md` per dev/notes.md §B. (f) Cross-project altair `_register_gs_fonts()` helper edit per dev/notes.md §A, sequenced after step (d). |
| PRISM references for context | `prism/dashboards-portal.md` (Django identity, PAGE_ACCESS_RULES, share toggle), `prism/architecture.md` §10 (user system, kerberos resolution), `prism/dashboard-refresh.md` (refresh pipeline) |

### whitepapers — SSOT for portal-facing static documents

White papers (deep technical dives) and how-to guides (FAQs, usage
guides) that PRISM serves through its portal. Workshopped here, then
dropped into PRISM at `ai_development/context/white_papers/`. Today
this is 5 markdown files migrated off S3; the user has flagged the
inherited content as needing a full refactor and the broader system
may itself be overhauled.

Carved out from `projects/frontend/` on 2026-05-02 because content
and showcasing are different concerns with different cadences.
**Content** (this project) and **portal-side organizing/showcasing**
(`projects/frontend/`: URLs, listing pages, templates, nav, hero,
Kerberos visibility) evolve independently.

| Aspect | Value |
|---|---|
| Status | INTAKE VERIFIED + WORKSHOP PLAN LOCKED + FRONTMATTER LANDED (2026-05-03). All 5 payload files now carry YAML frontmatter (slug + title + format + topic + audience + last_updated + reading_time + summary + related + sequence + featured) so the frontend's frontmatter-driven `_doc_registry()` pipeline reads them. Workshop spec at `dev/specs/whitepaper_workshop.md` locks the 6-doc target set: 3 whitepapers (What is Prism / Using Prism / How Prism Works) + 3 guides (Getting started / Email usage / FAQ). Body workshop pass spread across whitepapers turns 2-4. Dual-surface lock DEFERRED — workshop customer-facing first; L2 alignment is a follow-up cleanup. |
| Canonical payload | `projects/whitepapers/whitepapers-payload/` — flat folder, 5 markdown files (each with YAML frontmatter at top per the schema in `projects/frontend/dev/specs/ui_uplift.md` §1). |
| Workshop spec | `projects/whitepapers/dev/specs/whitepaper_workshop.md` (per-doc workshop plans, frontmatter schema, source mapping for each new doc, voice principles, sequence). Locked 2026-05-03. |
| Files (3 white papers) | `whitepaper_data_integrations.md`, `whitepaper_user_personalization.md`, `whitepaper_world_state_and_reasoning.md` (all carry frontmatter; bodies workshopped in upcoming turns) |
| Files (2 how-to guides) | `faq.md`, `email_usage_guide.md` (both carry frontmatter) |
| PRISM destinations | `ai_development/context/white_papers/<name>.md` — byte-identical drag-and-drop. The directory ALREADY EXISTS in PRISM with stale 2026-05-02 versions of all 5 files (per §8 of the verify reply); promotion overwrites. NOT currently referenced by `views.py` (still points at S3); portal-side rewire is a `projects/frontend/` task. |
| Portal coupling | `WHITEPAPER_MAP`, `views.{whitepapers,user_guides,faq,email_guide,download_whitepaper}`, templates `news/{whitepapers,user_guides,doc_page}.html`, URLs `/whitepapers/`, `/user-guides/`, `/faq/`, `/guide/email/`, `/resources/<doc_name>/`. All live in `projects/frontend/`, not here. Drift-free per §3 of verify reply. |
| Source for content intake | `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md` (OCR scan; carries known artifacts — full-section duplication in User Personalization, title-drift on World State & FICC Reasoning vs portal's "World State & Reasoning") + `2026-05-02_whitepapers_s3_verify_reply.md` (verbatim S3 bodies in §2.1-§2.5; resolves the OCR duplication via §2.2 overwrite + the World State title-drift via portal-facing pick) |
| Source for portal wiring | `projects/frontend/dev/scans/2026-05-02_portal_views_urls_templates.md` (`WHITEPAPER_MAP`, view bodies, templates) — confirmed drift-free 2026-05-02 by the s3_verify_reply §3 |
| Dual-surface design | DEFERRED for the 2026-05-03 workshop pass per `dev/specs/whitepaper_workshop.md` §6. We write customer-facing only; L2 alignment becomes a follow-up cleanup once the customer-facing 6-doc set settles. PRISM-RECOMMENDED direction is **(a) Shared SSOT** (same `white_papers/<x>.md` doubles as customer doc + L2 self-knowledge module) per §7 of verify reply, but locking it now would tighten paragraph budget across audiences before the workshop pass has even drafted bodies. |
| Render path support | Standard Python `markdown` lib + `[tables, fenced_code, toc, nl2br]` extensions. Mermaid renders client-side via `news/base.html` (`mermaid.min.js`). NO LaTeX/MathJax, NO syntax highlighting, NO native chart embedding — `<details>` / `<summary>` survive (good for the OCR scan's `<details>` blocks). Per §5 of verify reply. |
| Workshopping flow | PULL (verbatim, complete) → INQUIRE (verify intake gaps via a dedicated `staging/prompts/open/YYYY-MM-DD_<topic>.md` PRISM round-trip) → WORKSHOP (refactor opinionated) → PROMOTE (staging-upstream from there). **Step 1 (PULL) is COMPLETE** as of 2026-05-02. Step 2 (INQUIRE) was the verify reply itself; remaining inquiry deltas to be raised inline as workshop unfolds. Steps 3-4 are the active surface. |
| Skill-discipline | Applies — every byte serves a portal-rendered page; noise compounds across visitors. Under Shared SSOT (if locked), discipline tightens further: Tier 1 always-on weighting applies. |
| Test prompts | DEFERRED. Whitepapers are portal-served customer documents, not chat-loaded context. The `test_prompts/` model (per-iteration PRISM round-trip) doesn't map cleanly until the workshop pass clarifies what "testing" means for portal docs (RAG-style? rendered-page check?). Re-evaluate after workshop. |
| Open prompt loop | `staging/prompts/archive/2026-05-02_whitepapers_s3_verify.md` (now-archived; reply pointer set to `projects/whitepapers/dev/scans/2026-05-02_whitepapers_s3_verify_reply.md`; `reply_folded_into:` carries 7 fold-in targets). |
| Next step | (a) WORKSHOP PASS over the 6-doc target set per `dev/specs/whitepaper_workshop.md` §2 + §7 (turn 2-4): 3 whitepapers + 3 guides; "What is Prism" + "Getting started" are NEW from scratch; "Using Prism" + "How Prism Works" + "Email usage" + "FAQ" workshop from inherited; (b) optional byte-overwrite of `whitepaper_user_personalization.md` from §2.2 of the verify reply BEFORE its workshop turn (or just cut the duplication during workshop — default); (c) PROMOTE 6 workshopped docs to `ai_development/context/white_papers/` (byte-overwrite the stale 2026-05-02 versions); (d) `projects/frontend/` already rewired `views.py` from S3 to codebase path AND wired the frontmatter pipeline — no further frontend work blocking the workshop. PRISM-side handoff prompts drafted in `projects/frontend/dev/specs/ui_uplift.md` §6. No `.cursor/rules/whitepapers.mdc` yet — same wait-for-pattern discipline as apis. |

---

## staging/ file index

| File / folder | Role |
|---|---|
| `README.md` | This file — the living projects roster |
| `altair-payload/` | Ephemeral drag-and-drop copy of `projects/altair/altair-payload/`. User refreshes before promoting to PRISM. |
| `echarts-payload/` | Ephemeral drag-and-drop copy of `projects/echarts/echarts-payload/`. Same semantics. |
| `frontend-payload/` | (FUTURE — not yet promoted) Will be the ephemeral drag-and-drop copy of `projects/frontend/frontend-payload/ai_development/`. Same semantics; lands when the first PRISM promotion happens after the `2026-05-02_frontend_full_context.md` reply lands. |
| `voice_memos.md` | Raw capture space — unstructured thoughts, undated. Content is promoted to a project-side design spec or endeavor file when it matures. Low-friction exception to the "staging has a narrow purpose" rule. |
| `prompts/` | PRISM-facing context-extraction prompts. |
| `prompts/open/` | Live prompts waiting to be sent, or sent but with reply not yet folded into `prism/`. One file per prompt, named `YYYY-MM-DD_<topic>.md` (unique topic slug per prompt — concurrent agents never collide on a shared slot). Frontmatter carries the session, send date, reply pointer, and fold-in plan. |
| `prompts/archive/` | Dated archive of past prompts (`YYYY-MM-DD_<topic>.md`) with frontmatter metadata. A prompt moves here (same filename, no rename) once the PRISM reply has been folded into `prism/` and the frontmatter is finalized with `status: USED` + `reply_folded_into:` pointers. |

No more `handoffs/`, `apis_endeavor.md`, `altair_composites_spec.md`,
or `archive/` in staging/ — those moved to their projects' `dev/`
subfolders or to `archive/` at repo root in the 2026-05-02 restructure.

---

## Related folders (for cross-orientation)

| Folder | What it is | When it's relevant |
|---|---|---|
| `projects/` | Canonical source of truth for all 5 active multi-session projects. Each `projects/<name>/` has payload + stub mirror + dev infrastructure. | Most non-trivial work touches one of these. |
| `prism/` | Curated PRISM-side SSOT (architecture, helpers, tool contracts) | Always, when editing anything that PRISM consumes. `prism/README.md` is the routing table. |
| `workflows/` | Timeless, pasteable workflow prompts (`altair_qc.md`, `dashboard_qc.md`, …) | When kicking off a named workflow-type session. Not session-specific. |
| `scans/` | Phone-scan SSOT — `inbox/` raw landing, `prism/` for filed PRISM-side scans, `archive/` for fully absorbed scans. Per-project scans land in `projects/<name>/dev/scans/` (context extraction) or `projects/<name>/dev/feedback/` (QC critique). Triage SOP at `.cursor/rules/scans.mdc`. **Agent does NOT read scan files without explicit user instruction.** | When the user explicitly asks you to triage, file, or read a scan. Pointers to scans elsewhere (recently-viewed, README, `prism/` line-range citations) are NOT invitations. |
| `papers/converted/` | Academic-PDF conversions (long-form book extracts, e.g. `comiskey/`, `marx/`, `economics_ai/`). NOT phone-scan landing — that moved to `scans/inbox/` on 2026-05-02. | When ingesting an academic PDF or referencing a converted-book subfolder. |
| `GS/` | Library material PRISM consumes (skills, models, scrapers, pipelines, ontologies, knowledge, tools, products). Minus the 5 projects which moved to `projects/`. | When adding a scraper, a skill module, a model, or anything else library-shaped. |
| `archive/` | Archived content (never delete — always move here). `archive/external_repos/` was relocated from `staging/archive/` in the 2026-05-02 restructure. | Clean up: relocate stale files here instead of deleting. |
| `.cursor/rules/` | Agent behavior rules (`prism.mdc` is always-applied) | Always — `prism.mdc` is the repo orientation rule |

---

## Freshness mandate

This cheat sheet is load-bearing for Cursor sessions: agents rely on it
to orient to the active staging surface. A stale roster is worse than
no roster. Update this file whenever any of the following happens:

| Event | What to update here |
|---|---|
| A project's maturity changes (scoping → scaffolded → payload built → mature) | The status-at-a-glance bar + the summary-table Maturity column + the per-project subsection |
| A new staging project starts (new folder under `projects/`) | A new row in the summary table + a new per-project subsection + a status bar entry |
| A project retires or merges into another | Move the section to an `archive/` reference (never delete), update the table row, update the status bar |
| A new endeavor file lands under `projects/<name>/dev/endeavors/` | Update the relevant project's "Active endeavor" cell |
| A new design spec lands under `projects/<name>/dev/specs/` | Update the relevant project's subsection with the spec pointer |
| A new rule lands that governs a project | Update the relevant project's Rule cell + the per-project subsection |
| A PRISM destination path changes (rare — PRISM-side restructure) | Update the PRISM destination cell + the per-project subsection + verify `prism/codebase-tree.md` matches |
| The staging/projects/GS/ three-subtree model itself changes | Update the top-of-file diagram + the per-project paths + `.cursor/rules/prism.mdc` "Repo-to-PRISM Mapping" section in lockstep |

A stale cheat sheet is a bug. Treat "cheat sheet drift detected" the
same way you'd treat "PRISM payload drift detected": stop, fix it, then
continue.
