# staging/

> ## Staleness notice for the prism/ pointer below — added 2026-05-15
>
> The references to `prism/` in this README (the three-subtree diagram
> below, the "counterpart to staging/" paragraph, and the per-project
> `prism/ refs` column) describe a state that is **no longer current**.
> As of 2026-05-15, `prism/` is no longer maintained as the source of
> truth for how PRISM works (see `prism/README.md` for the full
> notice). The only PRISM-bound SSOTs still actively maintained in
> this repo are `projects/altair/` and `projects/echarts/`; everything
> else under `projects/` (`apis/`, `bloomberg/`, `frontend/`,
> `gs_reference/`, `macro/`, `whitepapers/`) is not load-bearing for
> ongoing PRISM work. The body below is preserved as-is until a
> future cleanup pass refreshes the roster.
>
> ---

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
│  altair       ████████████████████  mature + MARKDOWN-TABLE BAN +    │
│                                       TABLES SPOKE FOLDED INTO HUB    │
│                                       (2026-05-16): make_table() is   │
│                                       the only path PRISM emits a     │
│                                       table — no markdown tables, no  │
│                                       df.to_string(), no aligned      │
│                                       code-blocks, across every       │
│                                       interface. chart_context_       │
│                                       tables.md was folded into       │
│                                       chart_context.md as §13 so      │
│                                       PRISM never pays a spoke-fetch  │
│                                       tax for a table; chart_context. │
│                                       md is now 1050 lines / ~65 KB   │
│                                       (hub + 2 surviving spokes:      │
│                                       grids + colors). The full       │
│                                       make_table surface (3 color     │
│                                       modes, heatmap_groups,          │
│                                       sparkline + mini-bar cells,     │
│                                       header_levels, row_groups,      │
│                                       row_indent, total/subtotal,     │
│                                       number formatting hints,        │
│                                       worked examples) is inline.     │
│                                       Test surface: dev/tests.py      │
│                                       (30 API-only tests, ~6s) +      │
│                                       dev/gallery.py (22-card first   │
│                                       gallery) + dev/fail_gallery.py  │
│                                       (LVL+endpoint anno overlap      │
│                                       repro).                         │
│  echarts      ████████████████████  mature + TIME / LIVE-REFRESH   │
│                                       UPLIFT LANDED (2026-05-12);   │
│                                       COMPILE ⇔ REFRESH-ATTACH      │
│                                       INVARIANT + HEAL DOCTRINE     │
│                                       LANDED (2026-05-12):          │
│                                       NEW echart_dashboard.         │
│                                       _audit_refresh_attachment +   │
│                                       RefreshAttachmentError;       │
│                                       wired into build_dashboard    │
│                                       end (strict=False; Tool-2     │
│                                       carve-out) + refresh_         │
│                                       dashboard start (strict=True; │
│                                       fail-fast); catches the 15    │
│                                       canonical drift patterns      │
│                                       (registry orphan, refresh_    │
│                                       frequency mismatch, silent-   │
│                                       stale dataset, unparseable    │
│                                       script, missing metadata,     │
│                                       ...) via static-parse helpers │
│                                       (_infer_pull_stems_from_      │
│                                       source / _infer_transform_    │
│                                       keys_from_source); dashboards │
│                                       .md skill gained §H Heal      │
│                                       recipe (~95 lines); 31 new    │
│                                       unit tests pass; gallery at   │
│                                       dev/_gallery_refresh_         │
│                                       attachment_audit.py renders   │
│                                       compliant baseline + 7 drift  │
│                                       scenarios. Pre-this-edit:     │
│                                       new dashboards_time.py        │
│                                       canonical helpers (parse_iso  │
│                                       / format_iso / freq_delta /   │
│                                       is_stale / format_pill);      │
│                                       build_dashboard stamps        │
│                                       metadata.time.* four-times    │
│                                       schema + server-bakes         │
│                                       pill_text (no JS date math);  │
│                                       chrome JS pollLiveData loop   │
│                                       swaps datasets in-place every │
│                                       60s (ETag-gated); 2x          │
│                                       location.reload() in refresh  │
│                                       button replaced with in-place │
│                                       swap; stat_grid HYBRID        │
│                                       client-render; resolve_chart_ │
│                                       specs public alias; new dev/  │
│                                       live_refresh_harness.py       │
│                                       mimics views.py endpoints for │
│                                       local validation; PRISM-side  │
│                                       prompt paste-ready at         │
│                                       staging/prompts/open/         │
│                                       2026-05-11_views_py_time_     │
│                                       refresh_uplift.md; deferred   │
│                                       follow-up: pull-helper        │
│                                       sidecar pull_completed_at     │
│                                       stamping (own prompt)         │
│  apis         ████████████████████  5 PRISM-shape (treasury,         │
│                                       treasury_direct, bis, + Canada: │
│                                       statcan + bank_of_canada,       │
│                                       both universe-first 2026-05-30) │
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
│  gs_reference ████████████████████  LIVE 2026-05-14 — self-        │
│                                       contained Django mock of      │
│                                       goldmansachs.com visual       │
│                                       design language (8 pages:    │
│                                       home / what_we_do / insights │
│                                       list+article+podcast /       │
│                                       careers+life / our-firm/     │
│                                       purpose) + authoritative     │
│                                       gs_design_dna.md (~1,000     │
│                                       lines: --gs-uitk-* tokens,   │
│                                       60+ type roles per           │
│                                       breakpoint, 15 component     │
│                                       primitives, 7 page           │
│                                       archetypes, PRISM-runtime    │
│                                       substitution recipe for      │
│                                       absent GS Serif TTF) + 16    │
│                                       playwright screenshots       │
│                                       (8 prism + 8 live runtime).  │
│                                       Live extract from gs.com     │
│                                       inline <style> (1,150 vars,  │
│                                       26 @font-face). Reference    │
│                                       asset, not a payload —       │
│                                       PRISM consumes the spec      │
│                                       inline; mock is for visual   │
│                                       verification. Surfaced       │
│                                       freshness signal to          │
│                                       projects/frontend/dev/specs/ │
│                                       design_system.md (GS Serif   │
│                                       IS the live signature        │
│                                       headline face — PRISM's TTF  │
│                                       drop simply lacks it; the    │
│                                       frontend spec's 2026-05-02   │
│                                       framing reassigning display  │
│                                       to GS Cond Black needs an    │
│                                       additive correction).        │
│  bloomberg    ███░░░░░░░░░░░░░░░░░  hub-and-spoke; flat payload    │
│                                       (`bloomberg_excel.md` + eight  │
│                                       `bbg_*.md`); PRISM target      │
│                                       `context/modules/static/bloomberg/` │
│                                       · awaits first round-trip      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Project | Maturity | Repo path (canonical) | Payload source | PRISM destination | Rule | prism/ refs | Active endeavor / spec |
|---------|----------|-----------------------|----------------|-------------------|------|-------------|------------------------|
| altair | mature + markdown-table ban + tables spoke folded into hub (2026-05-16); prism-main import migration landed (2026-07-04) + stub mirror aligned (2026-07-07) | `projects/altair/` | `projects/altair/altair-payload/` | `prism-core/prism_mcp/utils/{chart_functions,chart_functions_studio}.py` + `prism-core/context/modules/static/tools/chart_context.md` (hub, ~69 KB; tables = §13) + `prism-core/context/modules/static/tools/charts/{chart_context_grids,chart_context_colors}.md` (2 surviving spokes) | `.cursor/rules/viz-platforms.mdc` | `code-sandbox.md` (§5.3 freshness stamp bumped 2026-05-13), `mcp-utils.md`, `vision-qc.md`, `mcp-tools.md` §3+§5 | `projects/altair/dev/specs/composites.md` (next feature build); `staging/prompts/open/2026-05-12_make_table_namespace_injection.md` (PRISM-side `make_table` namespace wiring); `projects/altair/dev/feedback/2026-05-13_make_table_hardening.md` (4-fix sync from PRISM-side use: png_path-on-success regression + truncation-aware QC + cell_colors col-name normalization + no-auto-truncation invariant) |
| echarts | mature + time/live-refresh uplift landed (2026-05-12); per-dashboard cadence + daemon mode + tz-mix engine absorption landed (2026-05-12 follow-up); compile ⇔ refresh-attach invariant + heal doctrine landed (2026-05-12); S3 subprocess-log migration + structured cron/runner logs + `_audit_dashboard_layout` helper landed (2026-05-12); awaits PRISM-side handoff | `projects/echarts/` | `projects/echarts/echarts-payload/` (engine + runner files + `dashboards_time.py` canonical time helpers; `parse_freq` accepts "60s"/"5m"/"1h"/"1d"/"1w" + legacy enum; `refresh_dashboards.py --interval N` daemon mode; `echart_dashboard._audit_refresh_attachment` + `RefreshAttachmentError` wired into `build_dashboard` end + `refresh_dashboard` start; `__init__.py` exports `_audit_dashboard_layout` (canonical 5-path audit, scan-version with `*, s3_manager=None` kwarg + AWS-shape tolerance); `refresh_dashboards._spawn_runner` streams subprocess stdout/stderr to `subprocess_logs/YYYY/MM/DD/...` S3 keys via `S3LogStreamer` daemon thread with `PRISM_SUBPROCESS_S3_FOLDER_KEY` env propagation, no `/tmp/` fallback; `refresh_runner.main()` calls `register_completion_marker()` so `completion.json` distinguishes still-running / clean-exit / error-exit / parent-died; runner prints rewritten as PHASE BLOCKS (3 phases × indented per-event lines with timing), cron prints rewritten as HIERARCHICAL (banner per walk + `kerberos/id  freq=  last=  -> SPAWN/SKIP/COOLDOWN` summary lines + indented sub-events for spawn / done)) | `prism-core/dashboards/*.py` (engine + runner + `dashboards_time`; `refresh_dashboards.py` goes to `jobs/hourly/` in the prism-main parent tree) + `prism-core/prism_mcp/utils/{s3_log_streamer,subprocess_completion}.py` (PRISM-side modules the runner files import) + `prism-core/context/modules/static/tools/dashboards.md` (preflight pointer) + `prism-core/context/modules/static/tools/dashboards_hub.md` (full authoring hub) + `tools/dashboards/*.md` (7 spokes incl. template_crud.md). **CAUTION 2026-07-07: staging payload imports still say `ai_development.*` while prod's installed copies were migrated to `core.*`/`dashboards.*`/`prism_mcp.utils.*` — housekeeping pass required before the next promotion; see `projects/echarts/dev/notes.md` "Still open".** | `.cursor/rules/viz-platforms.mdc` | `dashboard-refresh.md`, `dashboards-portal.md` | `staging/prompts/open/2026-05-11_views_py_time_refresh_uplift.md` (the PRISM-side half: NEW dashboard_data_api endpoint + template_hash injection + refresh_status_api auto-heal rewrite + views.py datetime-parse audit). Follow-ups: `staging/prompts/open/2026-05-12_refresh_dashboards_daemon_install.md` (decouple `refresh_dashboards` from the entrypoint.py multi-task generator sequence — invoke `--interval 30` as its own continuously-running worker so sub-5-min `refresh_frequency` dashboards actually refresh at their authored cadence rather than being bottlenecked by the slowest job in the multi-task cycle); `staging/prompts/open/2026-05-12_pull_helpers_sidecar.md` (pull_completed_at stamping — observability-only); `staging/prompts/open/2026-05-12_pull_market_data_tz_normalization.md` (uniform tz convention across pull_market_data modes — source-side hygiene). The S3 subprocess-log migration assumes PRISM-side `S3LogPathBuilder.build()` returns a 3-tuple `(folder_key, log_key, metadata_key)`; staging-side stub + payload call site both unpack 3-tuple, so the prior `_ck` 4th slot (unused dead code in PRISM per 2026-05-12 inspection) needs PRISM-side cleanup at promotion. The refresh-attachment audit + heal doctrine are pure additive (no signature changes; existing consumers get the audit + invariant for free) — no PRISM-side handoff prompt needed beyond the 3-tuple coordination above. |
| apis | 9 PRISM-shape clients (treasury / treasury_direct / bis migrated; statcan / bank_of_canada / wid / ai_buildout / ilo / imf net-new), rule codified, Session 8 in flight + net-new sources through 2026-06-14 (imf) | `projects/apis/` | `projects/apis/apis-payload/clients/*.py` + `apis-payload/modules/*.md` | `core/mcp/clients/*_client.py` (prism-main parent tree; transport at `core/mcp/gs_app_proxy_negotiate.py` — verified 2026-07-07) + `prism-core/context/modules/static/{data_guides,instruments,tools}/*.md` (guide paths not yet re-verified post-reorg) | `.cursor/rules/api-clients.mdc` | `gs-proxy.md`, `api-clients.md`, `data-functions.md` §0 | `projects/apis/dev/endeavors/apis_endeavor.md` (8-session plan) |
| frontend | MVP RUNNING + FULL REFACTOR + UI UPLIFT IN FLIGHT | `projects/frontend/` | `projects/frontend/frontend-payload/ai_development/` | `ai_development/mysite/` + `ai_development/mysite/news/static/css/{tokens,fonts,base}.css` + settings.py PATCH (STATICFILES_DIRS) + URL-grammar unification (10 legacy URLs 301 to canonical) + filesystem reads from `ai_development/context/white_papers/` (was S3 `secondary/technical_docs/`) + frontmatter-driven `_doc_registry()` pipeline in views.py + enriched `doc_page.html` chrome (TOC, breadcrumbs, related, prev/next) + topic-chip listings + home featured-resources block | — | `dashboards-portal.md`, `architecture.md` §10 | `projects/frontend/dev/specs/ui_uplift.md` (per-surface UI uplift plan; locked 2026-05-03); `projects/frontend/dev/specs/design_system.md` (token + component SSOT); `staging/prompts/open/2026-05-02_frontend_full_context.md` (PRISM-verbatim sync prompt) |
| whitepapers | intake VERIFIED + workshop PLAN LOCKED + frontmatter on all 5 inherited docs | `projects/whitepapers/` | `projects/whitepapers/whitepapers-payload/*.md` | `ai_development/context/white_papers/{whitepaper_data_integrations,whitepaper_user_personalization,whitepaper_world_state_and_reasoning,faq,email_usage_guide}.md` (filenames change to canonical slugs once workshop pass renames per `dev/specs/whitepaper_workshop.md` §8) | — | sourced from `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md` (OCR) + `2026-05-02_whitepapers_s3_verify_reply.md` (S3 verbatim verify). Plan: `projects/whitepapers/dev/specs/whitepaper_workshop.md`. | All 5 inherited docs now have YAML frontmatter (slug + title + format + topic + audience + last_updated + reading_time + summary + related + sequence + featured). Body workshop pass: collapse to 6-doc target set (3 whitepapers + 3 guides; "What is Prism" + "Getting started" are NEW). Spread across whitepapers turns 2-4 (workshop_spec §7). Dual-surface lock DEFERRED — workshop customer-facing first, L2 alignment is follow-up. |
| bloomberg | hub-and-spoke landed 2026-05-16; flat `bloomberg-payload/` mirrors PRISM `context/modules/static/bloomberg/`; awaits PRISM round-trip | `projects/bloomberg/` | `projects/bloomberg/bloomberg-payload/` — hub `bloomberg_excel.md` + eight sibling `bbg_*.md` files | `ai_development/context/modules/static/bloomberg/` (same nine files byte-identical); registry hub `static/bloomberg/bloomberg_excel.md`; spokes fetched via `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_<spoke>.md"], mode="full")` per hub §10 | — | — | `projects/bloomberg/README.md` — SSOT for mapping, triggers, and registry example. Workshop pass + RBR deferred until first PRISM round-trip surfaces frictions. |

PRISM destinations are expressed against the prism-main split checkout
(2026-07-07 layout: `prism-main/` root with `core/`, `jobs/`,
`prism_meta/`, `web/`, containing the `prism-core/` submodule with
`prism_mcp/`, `context/`, `dashboards/`; there is no `ai_development/`
tree any more — verbatim map in
`scans/prism/2026-07-07_prism_main_module_structure.md`). The frontend /
whitepapers / bloomberg rows still carry pre-reorg destination paths:
the scan could not locate `white_papers/` in the new checkout and did
not enumerate the Django/portal or bloomberg trees, so those
destinations need re-verification before their next promotion.

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
                   │ notes live alongside under   │
                   │ projects/<name>/ (dev/ plus  │
                   │ the per-platform stub trees) │
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
   PRISM           │ prism-main / prism-core      │
                   │ destinations (see roster).   │
                   │ Downstream-read-only. Never  │
                   │ edited there.                │
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
| apis | per-source | 9 today (`treasury`, `treasury_direct`, `bis`, `statcan`, `bank_of_canada`, `wid`, `ai_buildout`, `ilo`, `imf`); grows as more clients are rebuilt (target ~20) |
| altair | per-topic | 5 (`chart_types`, `mapping`, `annotations`, `dual_axis`, `composites`) — topic split is independent of the single-file `chart_context.md` skill. The 2026-05-10 Chart Center disable archived `chart_center_test.md` to `projects/altair/dev/archive/test_prompts/`; restore it alongside §11 + the studio call sites when re-enabling. |
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

(PRISM destination paths in the sections below that still say
`ai_development/...` predate the 2026-07-07 prism-main reorg — see the
note under the roster table. Altair + echarts + apis are current;
frontend / whitepapers / bloomberg need re-verification before their
next promotion.)

### altair — static PNG chart engine

The single-chart builder (`make_chart`) and the composite family
(`make_2pack_*`, `make_3pack_*`, `make_4pack_grid`, `make_6pack_grid`).
Produces static PNGs (and an interactive HTML companion) for chat,
email, and report flows.

| Aspect | Value |
|---|---|
| Drag-and-drop status | IN PROD + byte-verified (2026-07-07 introspection: installed 27,456 lines vs staging 27,460; sole-consumer property holds at `prism-core/prism_mcp/tools/script_exec_tools.py`; injected namespace = chart builders wrapped in `validate_params(_wrap_chart_func(...))`, annotation classes bare, `check_charts_quality` foreground-only). 90/90 API-only tests in `dev/tests.py` pass. |
| Canonical payload | `projects/altair/altair-payload/chart_functions.py`, `chart_functions_studio.py`, `chart_context.md` (hub; static tables = §13 of the hub) + `chart_context_grids.md` + `chart_context_colors.md` (2 spokes: grid mode + palette customisation) |
| Stub mirror | `projects/altair/{prism_mcp,prism_meta,core,web}/` — stub packages mirroring prism-main's import surface (5 helpers under `prism_mcp/utils/`, `prism_meta.REPO_ROOT` anchor, `core.s3_bucket_manager`, fonts dir). Pre-prism-main trees archived at `dev/archive/2026-07-07_pre_prism_main_stubs/`. |
| Pinned interpreter | `projects/altair/.venv/` (regenerate after the 2026-05-02 restructure — shebangs point at old `GS/viz/altair/.venv/` paths) |
| Galleries | `projects/altair/dev/gallery.py` (22-card first gallery covering all 12 chart types + 3 composite shapes + 2 table data-source paths + dual-axis + a multi-annotation case) + `projects/altair/dev/fail_gallery.py` (control + 5 reproductions of the LVL + endpoint annotation overlap bug). Both run with no args -> render to `dev/output/<YYYY-MM-DD_HHMM>_<slug>/` and `webbrowser.open` the index.html. Per-edit mini-galleries follow the same timestamped-output convention per `.cursor/rules/viz-platforms.mdc`. |
| Skill shape | Hub + 2 spokes. `chart_context.md` (hub, ~1050 lines / ~65 KB after the 2026-05-16 tables fold-in) carries the always-needed surface — markdown-table prohibition (HARD RULE) + namespace + QC + design defaults + authoring rules + chart types + mapping + annotations + dual-axis + composites + dimensions + horizons + failure transparency + the full static-tables surface as §13 (`make_table()` + `TableResult` + `df=`/`rows=` + 3 color modes + `heatmap_groups` + `header_levels` + `row_groups` + `row_indent` + `total_rows` / `subtotal_rows` + `sparkline_columns` + `minibar_columns` + number formatting hints + worked examples). `chart_context_grids.md` (spoke, ~157 lines) carves off the grid / small-multiples topic. `chart_context_colors.md` (spoke) carves off palette customisation. Both surviving spokes fetched mid-session via `list_ai_repo(file_paths=["context/modules/static/<spoke>.md"], mode="full")`. The 2026-05-12 tables spoke was folded into the hub on 2026-05-16 when the markdown-table prohibition went hard — PRISM uses `make_table()` constantly so the surface has to be inline (no spoke-fetch tax). carve-outs followed the same pattern (genuine standalone topic + discipline-warranting affordances that wouldn't compress to a paragraph in the hub). Skill / engine drift is caught at PRISM round-trip rather than via a local introspection gate -- the staging test surface is API-only. |
| QC workflow | `workflows/altair_qc.md` — adversarial vision + validation hardening |
| Notes file | `projects/altair/dev/notes.md` |
| Tests | `projects/altair/dev/tests.py` (`python tests.py` interactive; `python tests.py unit -v` headless). Lightweight API-only suite -- 30 tests across `TestSingleChartAPI` (one per chart_type), `TestAnnotationsAPI` (one per annotation class), `TestCompositeAPI` (one per composite helper), `TestTableAPI` (the two `make_table` data-source paths + a `heatmap_groups` smoke). Every test calls the public entry point (`make_chart`, `make_table`, `make_*pack_*`) the same way PRISM does and asserts `result.success` + a basic invariant. No internal-function tests, no engine-introspection drift gates. |
| Test prompts | `altair-payload/test_prompts/{chart_types,mapping,annotations,dual_axis,composites}_test.md` — one per topic area, 7 prompts each. Per the cross-project convention. STAGING-ONLY (does NOT ship). The 5-topic split is regression-coverage scaffolding, independent of the single-file skill. `chart_center_test.md` was archived to `projects/altair/dev/archive/test_prompts/` alongside the 2026-05-10 Chart Center disable (§11 stripped from `chart_context.md`, studio call sites in `chart_functions.py` deactivated). Restore the file alongside re-adding §11 + the studio call sites when re-enabling. |
| Active feature work | `projects/altair/dev/specs/composites.md` — 4-batch plan for layered composites, forecast styling, new annotation classes (`BarValueLabels`, `BarHighlight`, `Connector`, `SeriesLabel`), two-level x-axis |
| Feedback queue + external signals | 3 historical incidents + 1 cross-project signal in `projects/altair/dev/feedback/` and `dev/notes.md` §External-signals / §Cross-project-signals. **FEEDBACK (3):** (a) `2026-04-26-2333-stress-test-results.md` — engine stress harness; (b) `2026-05-02_4pack_blowout.md` — grouped-bar 4-pack cell-budget blowout (RESOLVED — facet-width math now subtracts spacing overhead; 3px readability gate raises `GROUPED BAR CELL-BUDGET ERROR`); (c) `2026-05-02_chartspec_y_title_kwarg.md` — `ChartSpec(y_title=...)` hallucinated kwarg (skill rule lives in `chart_context.md` §7.1 + §10.2; optional engine convenience kwarg remains open). **PRISM DIAGNOSTIC (1):** `scans/prism/2026-05-02_bimodal_stir_report_diagnostic.md` issue 2 — heatmap >12 color cardinality silent-fail (skill rule lives in `chart_context.md` §6.3; optional `_validate_chart_inputs` binning-named error remains open). **CROSS-PROJECT SIGNAL (1):** GS Sans font registration for matplotlib — `projects/frontend/dev/notes.md` §A has the plan; sequenced AFTER frontend staging fonts mirror lands. Engine edit adds `_register_gs_fonts()` at `chart_functions.py` import time (matplotlib sandbox workaround — PRISM hard-blocks matplotlib imports at the sandbox surface) and flips `GS_CLEAN` `"font.family"` from `"Liberation Sans, Arial, sans-serif"` to `"GS Sans, Helvetica Neue, Arial, sans-serif"`. Details in `projects/altair/dev/notes.md` "Cross-project signals". **OPEN BUG (2026-05-14):** LVL + endpoint annotation overlap reproduced in `dev/fail_gallery.py` (control + 5 repros). PRISM-shaped `Callout` / `PointLabel` / `PointHighlight` placed at the line endpoint stacks visually next to the auto-injected `LastValueLabel`. No engine fix yet -- repro pixels are the bug report; engine should detect endpoint-clustered annotations and either suppress the auto-LVL or reposition. |

### echarts — interactive HTML dashboard compiler

The `compile_dashboard` pipeline + a hub-and-spoke skill. Emits
self-contained HTML dashboards with the echarts JS inlined; no external
dependencies at render time.

| Aspect | Value |
|---|---|
| Drag-and-drop status | v2 ARCHITECTURE LANDED (2026-05-04) — staging-side rewrite complete (engine helpers + runner files in payload + hub absorbed CRUD recipes + spokes trimmed); 619/621 unit tests pass + new `TestFolderEntryPoints` (8 tests on the v2 entry points) + `folder_workflow` demo proves the new entry points end-to-end against a mock S3. PRISM-side install gated on the 3 handoff prompts in `staging/prompts/open/`. |
| Canonical payload | `projects/echarts/echarts-payload/` — `__init__.py` (re-exports the new entry points + exports `_audit_dashboard_layout` canonical 5-path audit), `config.py`, `dashboards_time.py` (canonical time helpers — `parse_iso` / `format_iso` / `parse_freq` / `freq_delta` / `is_stale` / `format_pill`), `echart_dashboard.py` (engine + the new `run_pull` / `build_dashboard` / `refresh_dashboard` helpers), `echart_studio.py`, `rendering.py`, `refresh_runner.py` (single-dashboard CLI; calls `register_completion_marker` at top of `main()`; phase-blocks structured stdout), `refresh_dashboards.py` (cron / `--interval N` daemon; `_spawn_runner` streams subprocess output to `subprocess_logs/YYYY/MM/DD/...` S3 keys via `S3LogStreamer` daemon thread + `PRISM_SUBPROCESS_S3_FOLDER_KEY` env propagation; hierarchical-indent structured stdout), `dashboards.md` (preflight pointer, ~280 lines) + `dashboards_hub.md` (full authoring hub, ~94 KB) + `dashboards/*.md` (7 spokes incl. `template_crud.md` thinned) + `dashboards/canonical_showcase.json` (templated `build_showcase` reference manifest, ~111 KB). The `*.json` glob is part of the drag-and-drop contract per `.cursor/rules/viz-platforms.mdc`. |
| Stub mirrors | `projects/echarts/ai_development/mysite/news/static/js/echarts.js` (~1MB ECharts JS asset at the path the CURRENT staging payload resolves; prod migrated to `web/backend_django/news/static/js/` anchored at `prism_meta.REPO_ROOT` — mirror restructures with the prism-main housekeeping pass, see `projects/echarts/dev/notes.md`); `projects/echarts/ai_development/mcp/utils/{s3_log_streamer,subprocess_completion}.py` (Python stubs added 2026-05-12 mirroring PRISM's real `mcp/utils/*` modules; `S3LogPathBuilder.build()` returns 3-tuple of S3-shape keys, `S3LogStreamer` writes streamed bytes to `<sandbox>/_logs/<flat-key>.log` instead of S3, `register_completion_marker` no-ops when `PRISM_SUBPROCESS_S3_FOLDER_KEY` is unset — PRISM-parity API surface, filesystem-backed locally per the parity invariant in `viz-platforms.mdc`). The `core/{s3_bucket_manager,common,user_manifest}.py` filesystem-backed stubs from 2026-05-04 + the new `mcp/utils/` stubs together let `dashboard_runner.py` exercise the cron path end-to-end against the local sandbox. See `projects/echarts/ai_development/README.md` for the full layout. |
| Playwright sweep | `projects/echarts/dev/inspect_dashboard.py` |
| Skill shape | Preflight + hub-and-spoke since 2026-05-16 (preflight `dashboards.md` carved out of the hub as the lean L2 pointer; full authoring depth moved to `dashboards_hub.md`). Hub-and-spoke since 2026-05-01; v2 architecture landed 2026-05-04. `dashboards_hub.md` (the L2 authoring hub) absorbed the 6 canonical recipes (A-G: 3-surfaces cheat sheet + path decision; build new dashboard; CRUD on manifest_template; pipeline edits; refresh discipline; manifest exploration; revert) into CORE — the recipes are no longer spoke-fetched. Per-primitive depth still in `dashboards/{charts,widgets,widget_tool,filters,recipes,pipelines,template_crud}.md` (template_crud hollowed to ~50 lines pointing back at hub §C; recipes trimmed to archetypes + transforms patterns; pipelines trimmed to cataloging + reuse-ladder + integrity rules). §2.5 audit trimmed to 10 lines + §2.6 versioning deleted. `TestSpokeDriftPrevention` pins the hub/spoke/engine triple; `TestCanonicalShowcaseDrift` pins `canonical_showcase.json` to `build_showcase`; `TestFolderEntryPoints` pins the v2 entry-point contract. |
| Validation gates (always-blocking; 2026-05-03 hardening sweeps) | 10 ALWAYS_BLOCKING_ERROR_CODES landed across three sweeps the same day. **Chart sweep (2026-05-03 morning):** (a) `chart_too_many_series` — line / multi_line / area capped at 4 y-series (wide-form via validator; long-form via CDD); (b) `kpi_static_value_forbidden` + (c) `stat_grid_static_value_forbidden` — every visible number must source from a refreshable dataset (Rule 1 extension); plus the engine error-message contract was rewritten so `r.error_message` carries the FULL diagnostic body on any validate-failure return. **Tool-widget sweep (2026-05-03 evening, against the Fed Scenario Tool python-leak incident):** (d) `tool_compute_python_literal_in_js` — Python literals (`None` / `True` / `nan` / `Timestamp(...)` / `Decimal(...)` / etc.) leaked into a `widget: tool`'s compute_js source produce a runtime `compute error: <token> is not defined` and a blank right panel; the `_scan_compute_js_for_python_literals` static scanner blocks at validate time; (e) `tool_compute_missing_output_key` — declared output ids that don't appear as `<id>:` keys in the compute return literal silently render the right panel as empty; the `_check_compute_returns_all_outputs` heuristic (regex-based after JS string/comment stripping) blocks at validate time. **Empty-visual sweep (2026-05-03 evening):** (f) `table_dataset_empty` PROMOTED from severity="warning" to error + added to ALWAYS_BLOCKING (was papering over a header-only table render); (g) `pivot_dataset_empty` NEW — pivot widget on 0-row dataset renders empty grid (no row dims / col dims / value cells); (h) `pivot_column_missing` NEW — pivot's row_dim_columns / col_dim_columns / value_columns reference a column not in the materialised dataset. Empty-data for KPI / stat_grid already covered indirectly via `kpi_source_no_numeric_values` / `stat_grid_source_unresolvable`; chart via `chart_dataset_empty`; V08 fills the table + pivot legs. All 14 demos refactored to source-drive every KPI / stat_grid item (7 new synthetic stat datasets across showcase + 6 production demos). |
| Stress harness coverage | `dev/qc_runner.py` runs 8 deterministic test sets (V01-V08) totalling 65 fixtures, all comprehensive: V01 missing-required (12) / V02 comprehensive-error-delivery (4) / V03 line-cap (8) / V04 messy-data (8) / V05 edit-regression (6) / V06 pipeline-graph integrity (5) / V07 tool-widget compute_js leak class (15: 10 python-leak + 3 missing-output + 2 false-positive guards) / V08 empty-visual hardening (7: 4 block + 1 cross-stream + 2 must-NOT-block guards). The previous V07 reservation (refresh-runner namespace gap) is PRISM-side-only and skipped — tracked in `dev/notes.md` "Still open". |
| Notes file | `projects/echarts/dev/notes.md` |
| QC workflow | `workflows/dashboard_qc.md` — adversarial manifest synth + vision grading |
| Test prompts | `echarts-payload/test_prompts/{charts,widgets,widget_tool,filters,recipes,pipelines}_test.md` — one per spoke, 7 prompts each. Per the cross-project convention. STAGING-ONLY (does NOT ship). 6/6 seeded as of 2026-05-02: `widget_tool_test.md` (manifest-preservation regression + canonical-example cribs); `widgets_test.md` (popup-parity regression + row_click drill-down + thesis/watch/risk markdown + KPI/stat_grid + pivot); `recipes_test.md` (data-pipeline coupling + revert + long-form/dual-axis/RV/computed); `charts_test.md` (30-type catalog coverage + correlation_matrix, scatter_studio, multi-axis, computed columns, heatmap palette); `filters_test.md` (10 types × 11 ops, cascading, dataZoom sync, click_emit, compound rule, scope, show_when); `pipelines_test.md` (catalog the pipeline graph + reuse-ladder paths + active-pipeline integrity + re-author end-to-end + session folder health check). The full set verifies the manifest-preservation + popup-parity + data-pipeline-coupling + revert + parameterised-input fixes plus the new 2-script nucleus + pipeline-aware framing landed across `dashboards_hub.md` §0 + §6.0 + `dashboards/{pipelines,recipes,widgets,widget_tool}.md` on 2026-05-02. |
| Feedback queue (UPDATED 2026-05-03) | 7 distinct dashboard incidents in `projects/echarts/dev/feedback/` covering 5 dashboards across 12 days: Fed Scenario Tool (manifest loss on rebuild + tool-widget python-leak), Fed Taylor Rule (parameterised inputs), NFP InstantRead × 3 (tab-3 birth-death + popup MA toggle bug; sector-wage chart redesign + revert; tab-1 row_click popup + AHE MoM/YoY mismatch), TIPS RV (3-iteration manifest validation series). All five cross-cutting patterns now ADDRESSED via skill-side + engine-side fold-ins: **MANIFEST-PRESERVATION** (`dashboards_hub.md` §2.5.4 + `dashboards/recipes.md` §3 + `dashboards/widget_tool.md` §1; READ → MERGE → WRITE with surgical mutation helpers); **POPUP-PARITY** (`dashboards/widgets.md` §3 capability-allow-list + filter-scoping rule); **DATA-PIPELINE COUPLING** (`dashboards/recipes.md` §4 propose-and-confirm decision table + refresh-runner namespace audit); **REVERT WORKFLOW** (`dashboards/recipes.md` §5 chat-description / history / archive recovery paths); **PARAMETERISED-INPUT** (`dashboards/widget_tool.md` §3.2 scalars-plus-series pattern + §2 crib clarification); **SCRIPT-PRESERVATION** (NEW 2026-05-03; `dashboards_hub.md` §2.5.5 + §6.0 path-decision + §6.2 pull discipline + `dashboards/recipes.md` §6 surgical script edit + `dashboards/recipes.md` §7 derivation playbook + `dashboards/widget_tool.md` §1 compute_js-lives-in-template guard); plus engine-side `tool_compute_python_literal_in_js` + `tool_compute_missing_output_key` blocking codes (V07 stress). All six fold-ins have round-trip regression coverage in the corresponding `test_prompts/*_test.md` files (5/6 seeded; widget_tool_test.md gets the new compute_js scenarios next). Per-incident → spoke routing in `projects/echarts/README.md` "Feedback queue (active absorption)". |
| Engine-companion roadmap (still open as of 2026-05-04) | The 2026-05-04 v2 architecture redesign subsumed several of the previously-open companions: **(c) refresh-runner namespace expansion** is moot — the v2 model uses real Python imports in persisted scripts (no namespace to expand); the v2 `refresh_runner.py` + `refresh_dashboards.py` live in the payload now. **(b) first-class revert primitive** is replaced by Recipe 6 (hub §G) — re-edit from chat history or restore from `history/<UTC>/` snapshots; no `scripts/versions/` chain to manage. **(a) manifest-template strict-mode** is now load-bearing differently: the v2 build flow's hub §A.2 path-decision table routes "add a chart" to §C surgical CRUD (no rebuild-from-scratch wipe path possible). Three companions remain in `projects/echarts/dev/notes.md` "Still open": (d) **`_audit_pipeline_integrity()` companion** — stateful column-set diff vs pre-edit; would extend V06 with that subset; (e) **popup canvas full-feature parity** with inline charts (PRISM ticket TKT-20260430-110307-c9f93b); (f) **`raw` chart_type catalog/validator drift** + surfacing `dataset_dti_no_date_column` through compile_dashboard. None are blocking; each would tighten the existing surface. |
| v2 install status (NEW 2026-05-04, hardened 2026-05-05) | Staging-side rewrite COMPLETE + runner files plug-and-play hardened: engine helpers (`run_pull` / `build_dashboard` / `refresh_dashboard`) added to `echart_dashboard.py`; runner files (`refresh_runner.py` + `refresh_dashboards.py`) added to payload; hub absorbed CRUD recipes A-G; spokes trimmed; demos exercise the new entry points end-to-end (`folder_workflow` demo); `TestFolderEntryPoints` (8 tests) pass; V09 fixture set documents the contract in qc_runner. **2026-05-05 runner hardening pass** (verified by `dev/roleplay_prism_dashboards.py` scenarios 5+6 against an in-memory mock S3 with PRISM-side stubs for UserRegistry / UserManifestManager / s3_manager): `refresh_runner.py` gained a phase tracker that tags each `errors[]` dict with `script: scripts/pull_data.py::<pull_name>` (or `scripts/build.py` / `<registry>`); a heuristic exception classifier mapping to `data_pull_empty` / `network_error` / `data_schema_error` / `compile_failed` / `missing_artifact`; an optional `--log-path` arg surfacing the spawner's log file path verbatim into `refresh_status.json`; Z-suffix timestamps to match existing registry entries. `refresh_dashboards.py` gained per-spawn try/except (one bad spawn cannot crash the cron pass); registry-read try/except (corrupt `dashboards_registry.json` returns `[]` instead of crashing); a post-spawn `UserManifestManager.update_dashboard_pointer(kerberos)` step per successful-refresh user (matches `prism/dashboard-refresh.md` §7 contract); skip categorization (`disabled=N not_due=N` in summary). PRISM-side install awaits 3 round-trip prompts in `staging/prompts/open/`: `2026-05-04_dashboards_v2_engine_imports.md` (verify pull/save_artifact/alt-data signatures + s3_manager kwarg + canonical import paths), `2026-05-04_dashboards_v2_runner_relocate.md` (enumerate every call site that imports from `ai_development.jobs.refresh_runner`), and the consolidated `2026-05-04_dashboards_v2_handoff.md` (apply the diff: drop new payload into `ai_development/dashboards/`, delete old `jobs/` files, update Django views.py + entrypoint.py imports — note Popen now passes `--log-path` arg too — optionally drop dashboard-script namespace injection from `script_exec_tools.py`). |

### apis — external API client platform

17 PRISM-side clients (treasury, treasurydirect, fdic, bis, ofr,
sec_edgar, prediction_markets, …) plus 7 staging-only sources. Unified
plug-and-play layout — 20 clients + 20 guide markdowns built as of
2026-05-02.

| Aspect | Value |
|---|---|
| Status | 3/24 reference rebuilds done (treasury Bucket A + treasurydirect Bucket B + bis Bucket B universe-first). `.cursor/rules/api-clients.mdc` codified (422 lines). All three transport patterns + universe-first ontology pattern exercised end-to-end. Stub mirror live; 14 demos pass live (2 Session 4 smoke + 4 Session 5 treasury + 4 Session 6 treasurydirect + 4 Session 8 bis). Remaining 21 batch migrations queued. |
| Canonical payload | `projects/apis/apis-payload/{clients,modules,test_prompts}/` (three flat subfolders. clients/ + modules/ ship byte-identical to PRISM; test_prompts/ is staging-only per D7 carve-out — user sorts the `.md` modules into PRISM pillars on drop per D7) |
| Stub mirror | `projects/apis/ai_development/mcp/gs_app_proxy_negotiate.py` (live; vanilla `requests` fallthrough; satisfies all 3 `_USE_GS_PROXY` patterns transparently per L2) |
| Harness | `projects/apis/dev/_harness.py` (live; `setup_sys_path()` + `banner` / `report` / `run_or_menu` helpers) |
| Reference rebuilds shipped | treasury (Bucket A, Session 5, 2026-05-02) + treasurydirect (Bucket B, Session 6, 2026-05-02) + bis (Bucket B universe-first, Session 8 first migration, 2026-05-09). 21 remaining. Pre-existing wrapper bug fixed during treasury rebuild: `get_avg_interest_rates` field-name mismatch (`security_type` → `security_desc:eq:Treasury <X>` translation). BIS rebuild surfaced + absorbed structural BIS quirks: domestic-currency LBS breakdowns are unpublished (wrapper auto-derives L_CURR_TYPE per reporter-currency pair); CBS basis F uses L_POSITION=I while basis U uses L_POSITION=C (recipe_contagion handles); diacritic search (turkey↔Türkiye, uk↔United Kingdom, …); ~420 KB full-ontology embed (29 dataflows with per-flow time coverage 1913-01 onwards + series counts up to 608K, 108 codelists incl. 15 attribute-only, 7,280 codes with 630 long-form descriptions, 26 hierarchical codelists, per-flow attribute metadata, 138 SDMX concepts with descriptions) so PRISM has full universe access without disk I/O including hierarchical drill-down (`get_code_hierarchy`), attribute interpretation (`interpret_attribute`), concept lookup (`get_concept`), and frequency-filtered enumeration (`list_dataflows(frequency="M")`). |
| Smoke + reference demos | 15 demos in `dev/demos/` — all pass live: 00_smoke_session_and_auth, 00_smoke_manual_https_request (Session 4 transport smoke), 01-04 treasury (Session 5), 05-08 treasurydirect (Session 6), 09-13 bis (Session 8 first migration: discovery / availability / query / recipes / universe-walkthrough). 36 BIS checks across 5 demos all green. |
| D13 test prompts | `apis-payload/test_prompts/<src>_test.md` — canonical home for the per-source PRISM round-trip prompts. STAGING-ONLY (carve-out from byte-identical invariant per D7); does NOT ship to PRISM. One file per migrated client; 7 prompts per file in pure-body / `---`-delimited format per D7 convention. Currently: `treasury_test.md`, `treasury_direct_test.md`, `bis_test.md`, `statcan_test.md`, `bank_of_canada_test.md`. |
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

### bloomberg — Bloomberg Excel formula skill (BQL + DAPI)

A single PRISM-bound skill file teaching the Bloomberg formula
catalog so PRISM can author Excel workbooks (via `openpyxl`) that
evaluate against the live Bloomberg Professional Service when the
user opens them in Excel-with-Bloomberg-add-in. PRISM never
executes BQL or `blpapi` itself — it ships a workbook the user
evaluates locally. Bloomberg licensing is per-seat, not per-server,
which is why this design exists.

| Aspect | Value |
|---|---|
| Status | Hub-and-spoke since 2026-05-16. Nine markdown files in a flat payload folder; no dev/, no stub mirror. Awaits first PRISM round-trip. |
| Canonical payload | `projects/bloomberg/bloomberg-payload/` — `bloomberg_excel.md` (hub) + eight `bbg_*.md` spokes (siblings in one flat directory) |
| PRISM destination | `ai_development/context/modules/static/bloomberg/` — copy all nine files byte-identical; `context/registry.py` hub entry with `source`: `static/bloomberg/bloomberg_excel.md`; spokes loaded mid-session via `list_ai_repo` using paths under `context/modules/static/bloomberg/` (see hub §10) |
| Coverage | (1) **openpyxl gotchas** — `_xll.` prefix mandatory, `ArrayFormula` for multi-cell returns, double-quote escaping, cached-value semantics, refresh-on-open behaviour; (2) **DAPI** — BDP / BDH / BDS / BEQS / BCURVE / BSRCH with full argument signatures + override flag catalog (~25 flags incl. CURR / PER / DAYS / FILL / CSHADJ / DPDF / DIR / DTS) + relative date strings; (3) **BQL** — BQL / BQL.Query / BQL.Dates / BQL.Params / BQL.Expr + clause grammar (let/get/for/with/preferences) + universe builders (members / peers / holdings / bondsuniv / bonds / segments / curvemembers / screenresults / filter / translatesymbols) + aggregation/group + statistical/technical (zscore / corr / regr / sma / emavg / rsi / macd / boll_band / return_series / rank / pct_rank) + date helpers + with-clause execution params + field-level params (currency / fpt / fpr / fa_period_type / fa_period_offset / est_source / fa_act_est_data / dates / period); (4) **field mnemonic catalog** — curated ~200 mnemonics across equity prices / equity identifiers + descriptive / equity fundamentals (IS + BS + CF + ratios + estimates) / fixed income (yield + risk + spreads + issue + ratings) / FX / commodities / indices; (5) **security syntax** — full yellow-key catalog + identifier types (ticker / CUSIP / ISIN / SEDOL / FIGI) + special forms (CT10 / CL1 / month codes); (6) **decision table** — DAPI vs BQL by question shape; (7) **integration patterns** — 4 worked openpyxl examples (BDP grid, BDH ArrayFormula, INDX_MEMBERS + per-row BDP, BQL screen); (8) **anti-patterns** — 14-row table; (9) **cheat sheet** — formulas / yellow keys / BDH flags / BQL clauses / universe builders. |
| Drop-in mapping | `projects/bloomberg/README.md` documents it. Promote = copy all nine files into `context/modules/static/bloomberg/` + add registry entry for the hub. |
| Test prompts | DEFERRED. The first PRISM round-trip will surface frictions; only after that pass do we know what test prompts to canonicalise. Pattern parallel to whitepapers — write a context-extraction style prompt only if the round-trip surfaces an ambiguity worth re-confirming. |
| Stub mirror | None. No engine, no Python imports, nothing to stub. The skill is markdown-only. |
| Next step | (a) User reviews the skill content; (b) drop all payload files into PRISM at `ai_development/context/modules/static/bloomberg/` + registry entry pointing at `static/bloomberg/bloomberg_excel.md`; (c) end-usage round-trip — user prompts PRISM for a Bloomberg workbook; (d) frictions drive a workshop pass HERE; (e) iterate. RBR optional. No `.cursor/rules/bloomberg.mdc` yet — same wait-for-pattern discipline as whitepapers / apis. |
| PRISM references for context | None — `prism/` is no longer maintained per the staleness notice at top of this README. The skill is self-contained against PRISM's already-known openpyxl + sandbox surface. |

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
