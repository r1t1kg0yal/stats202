# staging/

> ## Roster refresh in progress — 2026-08-09
>
> `prism/` is being restored as the PRISM-side source of truth (it was
> suspended from 2026-05-15 to 2026-08-09), so the `prism/ refs` column
> and the three-subtree diagram below are live pointers again — but
> check each cited file's `_as of` stamp, since the refresh lands file
> by file.
>
> **There is no submodule any more.** `prism-core` was vendored into
> `prism-main` as a plain subdirectory on 2026-08-07 (`287311b`, then
> `3ec2ace`). Every "gitlink vs checkout" parity blocker in the rows
> below is void — parity is now a direct one-repo measurement.
>
> **Altair is in sync**, confirmed by direct inspection 2026-08-09: the
> installed chart engine and chart context are identical to
> `projects/altair/altair-payload/`. The Ritik-authored commits touching
> those paths (`5ff6e3f`, `a1620b6`) are promotions landing in PRISM's
> history, which is what the normal staging→PRISM flow looks like from
> the PRISM side — not out-of-band edits. Echarts parity has not been
> re-verified since the vendoring and remains an open measurement.
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
│  altair       ████████████████████  mature engine + LEAN CONTEXT:    │
│                                       registered 306-line router/core │
│                                       + 6 intent-routed spokes        │
│                                       (annotations, dual axis,        │
│                                       composites/batch, tables,       │
│                                       grids, colours). The router     │
│                                       retains the hard PNG-table ban, │
│                                       exact public chart catalog,     │
│                                       current engine caps, automatic  │
│                                       foreground-QC contract, and     │
│                                       one-call spoke routing.         │
│                                       Engine Python is prod-verified; │
│                                       context rewrite awaits promote. │
│                                       Test surface: ~100 API-only     │
│                                       tests + targeted galleries.     │
│  echarts      ████████████████████  mature + GARBAGE GATE +         │
│                                       SPLIT ARCHITECTURE. Canonical  │
│                                       payload: 10 Python files +    │
│                                       registered router, kernel,    │
│                                       10 spokes; 8 prompt files stay │
│                                       staging-only. Local publish   │
│                                       requires panel receipts,      │
│                                       flagged drill-down, exact     │
│                                       rationale ack, guarded build. │
│                                       2026-07-21 LIVE: Composer is  │
│                                       response-only on canonical    │
│                                       user dashboards; drag         │
│                                       allowlists all 12 kinds but   │
│                                       still sends 7 scalar fields.  │
│                                       Note/semantic-markdown header │
│                                       lookup is mismatched and no   │
│                                       headerless grips exist.       │
│                                       getWidgetSnapshot exists but  │
│                                       is uncalled; no snapshot      │
│                                       validator/merger or prod      │
│                                       tests exist. Persisted input  │
│                                       GET/save/upload/download is   │
│                                       live; conditional writes use  │
│                                       raw boto3 and can degrade to  │
│                                       a non-atomic plain PUT. BYTE  │
│                                       PARITY OPEN: checked-out core │
│                                       bf4bcd12 is ahead of parent   │
│                                       gitlink 1e6d3955; all four    │
│                                       measured Composer/input files │
│                                       differ from candidate.        │
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
| altair | mature engine, now split per PRISM branch `macdist-refactor-chartRender`: the renderer lives in an import-closed `chart_render/` package (`core.py` + `house_style.py`, alongside PRISM-owned `units.py`) that pulls only stdlib + altair/numpy/pandas/PIL/vl_convert, so it ships in the secure-execution sandbox image; the old `utils/chart_functions.py` path is a 46-line trusted-side wrapper injecting presign / studio / table-studio / vision / error-mail / dimension-presets / chart-id / font-root through `register_trusted_extensions()`. Unregistered, those degrade to no-ops, so a sandbox render returns a bare S3 handle with no presigned URL and no studio companion. Consolidated 2026-08-08 from the `projects/altair2/` port scratch (now at `archive/2026-08-08_altair2_port_scratch/`), carrying the Aug 2-3 work forward: band + contribution chart types, the newer studios, and the lean registered router + 6 on-demand spokes. Verified: 182/184 tests (the 2 failures are the pre-existing skin/format-hint spoke-naming gates, unrelated to the split), AST closure clean, identical 44-entry `__all__` across core/package/wrapper, and byte-identical PNGs across 10 chart types between the trusted and bare-sandbox paths. Pre-split payload archived at `projects/altair/dev/archive/2026-08-08_pre_chart_render/`; what is installed in PRISM today is still the flat aug2 layout, so nothing in the payload is installed-byte-verified. | `projects/altair/` | `projects/altair/altair-payload/` (TWO destination dirs: `chart_render/` + `utils/`) | `prism-core/prism_mcp/chart_render/{__init__,core,house_style}.py` + `prism-core/prism_mcp/utils/{chart_functions,chart_functions_studio,chart_functions_studio_tables}.py` + `prism-core/context/modules/static/tools/chart_context.md` (registered router/core) + `prism-core/context/modules/static/tools/charts/chart_context_{annotations,dual_axis,composites,tables,grids,colors}.md` | `.cursor/rules/viz-platforms.mdc` | `code-sandbox.md`, `mcp-utils.md`, `vision-qc.md`, `mcp-tools.md` §3+§5 | Promote the split payload + context together and re-verify installed bytes; open question on whether the sandbox injects from `utils/chart_functions` or `chart_render` is out to PRISM at `staging/prompts/open/2026-08-08_sandbox_injection_source.md`; then constrained RBR |
| echarts | mature reliability-first compiler with Dashboard Garbage Gate, persisted input, refresh, and hub/spoke context; 2026-07-21 live Composer state is response-only mount + all-12 allowlist + seven-field canonical-only drag, with installed snapshot producer uncalled and validator/tests absent; persisted-input routes are live; installed-byte parity remains open because checked-out core is ahead of the parent gitlink and all four measured files differ | `projects/echarts/` | `projects/echarts/echarts-payload/` (10 Python files incl. `dashboard_share.py` + `dashboard_user_input.py` + 12 context files: registered router, on-demand kernel, 10 spokes; 8-file/63-prompt `test_prompts/` remains staging-only) | 9 canonical modules target `prism-core/dashboards/` + parent-tree `jobs/hourly/refresh_dashboards.py` + `prism-core/context/modules/static/tools/{dashboards,dashboards_hub}.md` + `tools/dashboards/*.md`; live extraction confirms `dashboard_share.py` and `dashboard_user_input.py` exist but did not rerun a complete payload inventory count; local runtime mirrors the split checkout through `core/`, `dashboards/`, `jobs/`, `prism_mcp/`, `prism_meta/`, and `web/` | `.cursor/rules/viz-platforms.mdc` | `codebase-tree.md` §0+§5, `code-sandbox.md` §2.4+§8, `mcp-tools.md` §5, `dashboard-refresh.md`, `dashboards-portal.md` | `projects/echarts/dev/specs/{composer_dashboard_stack,dashboard_user_input}.md`; live extraction archived at `staging/prompts/archive/2026-07-21_composer_s3_full_stack_refresh.md` |
| apis | 9 PRISM-shape clients (treasury / treasury_direct / bis migrated; statcan / bank_of_canada / wid / ai_buildout / ilo / imf net-new), rule codified, Session 8 in flight + net-new sources through 2026-06-14 (imf) | `projects/apis/` | `projects/apis/apis-payload/clients/*.py` + `apis-payload/modules/*.md` | `core/mcp/clients/*_client.py` (prism-main parent tree; transport at `core/mcp/gs_app_proxy_negotiate.py` — verified 2026-07-07) + `prism-core/context/modules/static/{data_guides,instruments,tools}/*.md` (guide paths not yet re-verified post-reorg) | `.cursor/rules/api-clients.mdc` | `gs-proxy.md`, `api-clients.md`, `data-functions.md` §0 | `projects/apis/dev/endeavors/apis_endeavor.md` (8-session plan) |
| frontend | MVP RUNNING + FULL REFACTOR + UI UPLIFT IN FLIGHT | `projects/frontend/` | `projects/frontend/frontend-payload/ai_development/` | `ai_development/mysite/` + `ai_development/mysite/news/static/css/{tokens,fonts,base}.css` + settings.py PATCH (STATICFILES_DIRS) + URL-grammar unification (10 legacy URLs 301 to canonical) + filesystem reads from `ai_development/context/white_papers/` (was S3 `secondary/technical_docs/`) + frontmatter-driven `_doc_registry()` pipeline in views.py + enriched `doc_page.html` chrome (TOC, breadcrumbs, related, prev/next) + topic-chip listings + home featured-resources block | — | `dashboards-portal.md`, `architecture.md` §10 | `projects/frontend/dev/specs/ui_uplift.md` (per-surface UI uplift plan; locked 2026-05-03); `projects/frontend/dev/specs/design_system.md` (token + component SSOT); `staging/prompts/open/2026-05-02_frontend_full_context.md` (PRISM-verbatim sync prompt) |
| whitepapers | intake VERIFIED + workshop PLAN LOCKED + frontmatter on all 5 inherited docs | `projects/whitepapers/` | `projects/whitepapers/whitepapers-payload/*.md` | `ai_development/context/white_papers/{whitepaper_data_integrations,whitepaper_user_personalization,whitepaper_world_state_and_reasoning,faq,email_usage_guide}.md` (filenames change to canonical slugs once workshop pass renames per `dev/specs/whitepaper_workshop.md` §8) | — | sourced from `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md` (OCR) + `2026-05-02_whitepapers_s3_verify_reply.md` (S3 verbatim verify). Plan: `projects/whitepapers/dev/specs/whitepaper_workshop.md`. | All 5 inherited docs now have YAML frontmatter (slug + title + format + topic + audience + last_updated + reading_time + summary + related + sequence + featured). Body workshop pass: collapse to 6-doc target set (3 whitepapers + 3 guides; "What is Prism" + "Getting started" are NEW). Spread across whitepapers turns 2-4 (workshop_spec §7). Dual-surface lock DEFERRED — workshop customer-facing first, L2 alignment is follow-up. |
| bloomberg | hub-and-spoke landed 2026-05-16; flat `bloomberg-payload/` mirrors PRISM `context/modules/static/bloomberg/`; awaits PRISM round-trip | `projects/bloomberg/` | `projects/bloomberg/bloomberg-payload/` — hub `bloomberg_excel.md` + eight sibling `bbg_*.md` files | `ai_development/context/modules/static/bloomberg/` (same nine files byte-identical); registry hub `static/bloomberg/bloomberg_excel.md`; spokes fetched via `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_<spoke>.md"], mode="full")` per hub §10 | — | — | `projects/bloomberg/README.md` — SSOT for mapping, triggers, and registry example. Workshop pass + RBR deferred until first PRISM round-trip surfaces frictions. |

PRISM destinations are expressed against the single `prism-main`
repository (2026-08-09 layout: root with `core/`, `jobs/`, `prism_meta/`,
`web/`, `entrypoint.py`, plus `prism-core/` — a plain vendored
subdirectory since `287311b`, no longer a submodule — holding
`prism_mcp/`, `context/`, `dashboards/`, `tests/`; there is still no
`ai_development/` tree). Current layout in `.cursor/rules/viz-platforms.mdc`
under "PRISM runtime layout"; the 2026-07-07 split-checkout map in
`scans/prism/2026-07-07_prism_main_module_structure.md` is superseded on
the submodule question but still accurate on paths. The frontend /
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
| Files per project | One per natural unit (topic / spoke / source). Active projects currently carry 5-9 files. |
| Prompts per file | 7 baseline prompts that mix broad regression coverage and specific implementation tests; explicitly pinned per-file additions are allowed for distinct regression classes. |
| Format | Pure prompt bodies separated by `---` horizontal rules. No headers, no frontmatter, no annotations. |
| Per-prompt convention | Each body is 1-3 sentences ending with "Let me know if frictions." |
| Drag-and-drop status | STAGING-ONLY. Carve-out from the byte-identical-payload invariant: `test_prompts/` does NOT ship to PRISM. The user drops `clients/` + `modules/` (apis), or the payload `.py` / `.md` files (altair / echarts) — NEVER `test_prompts/`. |
| Two purposes | (1) **Per-iteration verification** — Cursor surfaces the 1-2 most discriminating prompts to the user as the success-criterion loop after promoting a unit to PRISM. (2) **Regression sweep** — re-paste any subset after a payload update to verify nothing regressed. |
| Loop shape | User pastes prompt body into PRISM → PRISM responds → no frictions = unit is done; frictions = user pastes the reply back, Cursor iterates payload + prompt, loop. The same `<unit>_test.md` is reusable across iterations. |

Per-project unit count and file inventory:

| Project | Units | Files in `test_prompts/` |
|---|---|---|
| apis | per-source | 9 today (`treasury`, `treasury_direct`, `bis`, `statcan`, `bank_of_canada`, `wid`, `ai_buildout`, `ilo`, `imf`); grows as more clients are rebuilt (target ~20) |
| altair | per-topic | 8 (`chart_types`, `mapping`, `annotations`, `dual_axis`, `composites`, `tables`, `grids`, `colors`) — the inventory covers the registered core plus all six spokes. The 2026-05-10 Chart Center disable archived `chart_center_test.md` to `projects/altair/dev/archive/test_prompts/`; restore it alongside the studio call sites when re-enabling. |
| echarts | per ownership/test surface | 8 (`charts`, `diagnose`, `filters`, `pipelines`, `recipes`, `template_crud`, `widget_tool`, `widgets`) — 8/8 files, 63 pure prompt bodies total (`template_crud` has 10, `charts` has 9, `pipelines` and `widgets` have 8 each, and the other four files have 7 each). `build.md` is covered through the create/edit prompts rather than a separate prompt file. |
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
Produces static PNGs and Vega-Lite specifications for chat, email, and report
flows.

| Aspect | Value |
|---|---|
| Drag-and-drop status | **IN SYNC — confirmed by direct inspection 2026-08-09.** The installed chart engine and chart context are identical to `projects/altair/altair-payload/`. Production runs the split: the `chart_render` refactor merged to `master` via `a9cd506` (2026-08-08), so the pre-split flat layout frozen at `staging/altair-payload-aug2/` is history and the branch ref `macdist-refactor-chartRender` is stale (tip `97e9b441` is not an ancestor of HEAD; the content arrived through master). The later Ritik-authored commits on these paths — `5ff6e3f` (2026-08-08, two new chart types) and `a1620b6` (2026-08-09, chart functions improvements) — are promotions landing in PRISM's history, not PRISM-side edits. The `check_charts_quality` install hazard is void: `72fb925` retired Gemini chart QC entirely and `script_exec_tools.py` no longer imports the name. |
| Canonical payload | `projects/altair/altair-payload/` in two subfolders that mirror the two PRISM destinations: `chart_render/{__init__,core,house_style}.py` -> `prism-core/prism_mcp/chart_render/`, and `utils/{chart_functions,chart_functions_studio,chart_functions_studio_tables}.py` -> `prism-core/prism_mcp/utils/`. Plus the 7 flat `chart_context*.md`. `chart_render/units.py` is PRISM-owned (a pure `git mv` we only stub) and does not ship from here. Payload `.py` files carry no trailing newline. |
| Stub mirror | `projects/altair/{prism_mcp,prism_meta,core,web}/` — stub packages mirroring prism-main's import surface (`prism_mcp/chart_render/` shim + PRISM-owned `units.py` stub, 6 modules under `prism_mcp/utils/`, `prism_meta.REPO_ROOT` anchor, `core.s3_bucket_manager`, fonts dir). The `chart_render/__init__.py` shim prepends the payload dir to `__path__` so `core` and `house_style` resolve to the payload while `units` resolves to the stub. Pre-prism-main trees archived at `dev/archive/2026-07-07_pre_prism_main_stubs/`; pre-split payload and stubs at `dev/archive/2026-08-08_pre_chart_render/`. |
| Pinned interpreter | `projects/altair/.venv/` (regenerate after the 2026-05-02 restructure — shebangs point at old `GS/viz/altair/.venv/` paths) |
| Galleries | `projects/altair/dev/gallery_template.py` is the live starting point — run with no args to render a 2-card demo, then `cp dev/gallery_template.py dev/build_<topic>.py` per the per-edit workflow. Every gallery renders to `dev/output/<YYYY-MM-DD_HHMM>_<slug>/` and `webbrowser.open`s the index.html, per the timestamped-output convention in `.cursor/rules/viz-platforms.mdc`. ~80 historical per-edit galleries (including the original 22-card `gallery.py` and the `fail_gallery.py` LVL/annotation-overlap reproductions) are frozen at `projects/altair/dev/archive/galleries/` — they are history, not a regression suite, and are deliberately excluded from the `_migrate_title_kwargs.py verify` sweep. |
| Skill shape | Registered lean router/core + 6 spokes. `chart_context.md` (306 lines) carries namespace, routing, artifact/chart selection, plot-ready semantics, core v1 call/result/failure/QC contracts, current hard gates, chart catalog (including `bullet`), and mapping essentials. `chart_context_{annotations,dual_axis,composites,tables,grids,colors}.md` own specialized kwargs and examples; fetch through short paths such as `list_ai_repo(file_paths=["charts/chart_context_tables.md"], mode="full")`. The router retains the hard PNG-table rule while table detail stays on demand. |
| QC workflow | `workflows/altair_qc.md` — adversarial vision + validation hardening |
| Notes file | `projects/altair/dev/notes.md` |
| Tests | `projects/altair/dev/tests.py` (`python tests.py` interactive; `python tests.py unit -v` headless). 184 tests, 182 passing — the 2 failures are pre-existing skin/format-hint spoke-naming gates unrelated to the split. Paired with `dev/build_refactor_verification.py --run`, the closure gate: 10 chart types rendered through the trusted wrapper and the bare render core in separate interpreters, asserted byte-identical. API-only suite through `make_chart`, `make_table`, and composite helpers; no internal-function or engine-introspection drift gates. Paired with `dev/_probe_api_surface_contract.py run` (25 cases — every retired name rejects naming its canonical replacement) and `dev/_migrate_title_kwargs.py verify` (no call site passes a retired axis-title kwarg). |
| Test prompts | `altair-payload/test_prompts/{chart_types,mapping,annotations,dual_axis,composites,tables,grids,colors}_test.md` — one per core/spoke topic; 7 baseline prompts each, with one pinned regression addition in `chart_types` and `mapping` (58 total). STAGING-ONLY (does NOT ship). |
| Active feature work | `projects/altair/dev/specs/composites.md` — 4-batch plan for layered composites, forecast styling, new annotation classes (`BarValueLabels`, `BarHighlight`, `Connector`, `SeriesLabel`), two-level x-axis |
| Feedback queue + external signals | 3 historical incidents + 1 cross-project signal in `projects/altair/dev/feedback/` and `dev/notes.md` §External-signals / §Cross-project-signals. **FEEDBACK (3):** (a) `2026-04-26-2333-stress-test-results.md` — engine stress harness; (b) `2026-05-02_4pack_blowout.md` — grouped-bar 4-pack cell-budget blowout (RESOLVED — facet-width math now subtracts spacing overhead; 3px readability gate raises `GROUPED BAR CELL-BUDGET ERROR`); (c) `2026-05-02_chartspec_y_title_kwarg.md` — `ChartSpec(y_title=...)` hallucinated kwarg (skill rule lives in `chart_context.md` §7.1 + §10.2; optional engine convenience kwarg remains open). **PRISM DIAGNOSTIC (1):** `scans/prism/2026-05-02_bimodal_stir_report_diagnostic.md` issue 2 — heatmap >12 color cardinality silent-fail (skill rule lives in `chart_context.md` §6.3; optional `_validate_chart_inputs` binning-named error remains open). **CROSS-PROJECT SIGNAL (1):** GS Sans font registration for matplotlib — `projects/frontend/dev/notes.md` §A has the plan; sequenced AFTER frontend staging fonts mirror lands. Engine edit adds `_register_gs_fonts()` at `chart_functions.py` import time (matplotlib sandbox workaround — PRISM hard-blocks matplotlib imports at the sandbox surface) and flips `GS_CLEAN` `"font.family"` from `"Liberation Sans, Arial, sans-serif"` to `"GS Sans, Helvetica Neue, Arial, sans-serif"`. Details in `projects/altair/dev/notes.md` "Cross-project signals". **OPEN BUG (2026-05-14):** LVL + endpoint annotation overlap reproduced in `dev/fail_gallery.py` (control + 5 repros). PRISM-shaped `Callout` / `PointLabel` / `PointHighlight` placed at the line endpoint stacks visually next to the auto-injected `LastValueLabel`. No engine fix yet -- repro pixels are the bug report; engine should detect endpoint-clustered annotations and either suppress the auto-LVL or reposition. |

### echarts — interactive HTML dashboard compiler

The `compile_dashboard` pipeline + a hub-and-spoke skill. Emits
self-contained HTML dashboards with the echarts JS inlined; no external
dependencies at render time.

| Aspect | Value |
|---|---|
| Drag-and-drop status | All 10 Python modules plus the router, kernel, and spokes are installed; `dashboard_share.py` and `dashboard_user_input.py` both exist under `prism-core/dashboards/`. **The gitlink parity blocker is gone** — `prism-core` is no longer a submodule (vendored by `287311b`, 2026-08-07), so there is no parent-recorded SHA to be behind and parity is a direct one-repo measurement. Parity has not been re-verified since the vendoring and remains an open measurement — unlike altair, which was confirmed in sync on 2026-08-09. |
| Canonical payload | `projects/echarts/echarts-payload/` — `__init__.py`, `config.py`, `dashboards_time.py`, `echart_dashboard.py`, `echart_studio.py`, `rendering.py`, `dashboard_share.py`, `dashboard_user_input.py`, `refresh_runner.py`, `refresh_dashboards.py`, `dashboards.md`, `dashboards_hub.md`, and `dashboards/*.md`. Python files land in `prism-core/dashboards/` except `refresh_dashboards.py`, which lands in parent-repo `jobs/hourly/`; context files land in `prism-core/context/modules/static/tools/`. `test_prompts/` is always staging-only. |
| Local runtime mirrors | Production-shaped root packages: `core/` (filesystem-backed S3, common, user-manifest, and NY Fed client stubs), `dashboards/` (links to payload Python), `jobs/hourly/` (link to payload cron entry point), `prism_mcp/utils/` (data/log/completion stubs), `prism_meta/` (`REPO_ROOT`), and one primary asset at `web/backend_django/news/static/js/echarts.js`. The retired `ai_development/` mirror is archived under `dev/archive/` and not active. |
| Playwright sweep | `projects/echarts/dev/inspect_dashboard.py` plus `dev/live_refresh_harness.py --verify` for live refresh and persisted text/checklist/file input |
| Skill shape | Registered router + on-demand kernel + 10 ownership spokes. `dashboards.md` is the only `MODULE_REGISTRY` entry; it routes each phase to short-path `list_ai_repo` fetches. `dashboards_hub.md` owns cross-cutting contracts. `dashboards/{build,diagnose,template_crud,pipelines,recipes,productivity,charts,widgets,widget_tool,filters}.md` own first-build, repair, mutation, data-flow, archetype, productivity/workflow composition, and primitive depth. `TestContextIntegrity`, `TestContextBudgets`, and `TestSpokeDriftPrevention` pin the topology and engine/context contract. |
| Validation gates | Strict compilation reports all structural, compute, binding, and data diagnostics in one pass; always-blocking render failures raise even with `strict=False`. The Dashboard Garbage Gate adds a bounded one-line-per-panel review, flagged-panel drill-down, exact rationale acknowledgment, signature-stable raw refreshes, and the same current-data gate for saved-definition restores. Literal date tokens and invalid gauges block; sparse/gappy/spiky lines, categorical `ALL_ZERO`/`PARTIAL` marks, narrative-table wrap risk, and browser-only tools require review. Registered producer analysis follows local writer/materializer helpers, literal propagation, and finite literal loops while separating unresolved dynamic outputs from definite stale/unattached datasets. |
| Regression coverage | `dev/tests.py` runs 1,071 unit tests plus 11 deterministic stress scenarios. `dev/qc_runner.py` runs 72 adversarial validation fixtures across required-path, exhaustive-diagnostic, series-cap, messy-data, edit-regression, pipeline-graph, tool-JS, and empty-visual surfaces. Qualification adds subprocess, roleplay, smoke CLI, Playwright interaction, persisted-input browser flows, live-refresh, and full showcase gates. |
| Notes file | `projects/echarts/dev/notes.md` |
| QC workflow | `workflows/dashboard_qc.md` — adversarial manifest synth + vision grading |
| Test prompts | `echarts-payload/test_prompts/{charts,diagnose,filters,pipelines,recipes,template_crud,widget_tool,widgets}_test.md` — 8 files / 63 pure user blocks (`template_crud` has 10, `charts` has 9, `pipelines` and `widgets` have 8 each, and the other four files have 7). Chart/widget/tool/diagnosis prompts explicitly cover receipt review, panel drill-down, rationale acknowledgment, then guarded build. STAGING-ONLY; none ship to PRISM. The inventory is enforced by `TestContextIntegrity`; `build.md` is covered through create/edit prompts rather than a separate prompt file. |
| Feedback absorption | Dashboard incidents covering manifest loss, tool-JS leakage, parameterized inputs, popup behavior, derivation coupling, helper-hidden producer outputs, and reverts are absorbed into typed manifest/script transactions, helper-aware registered call graphs, shared popup/inline controllers, pipeline contracts, and blocking validation. Matching regression prompts live under `echarts-payload/test_prompts/`; per-incident routing remains in `projects/echarts/README.md` and `dev/notes.md`. |
| Remaining integration work | Browser-triggered refresh still does not update the user-manifest dashboard pointer; the hourly orchestrator does. Reconcile the `prism-core` gitlink/checkout and rerun byte classification before promotion. Live Composer now mounts response-only and allowlists all 12 kinds, but semantic markdown and legacy `note` render `.note-head` while the live boot looks for `.tile-header`; those two plus plain markdown, untitled image, and divider are not draggable. Its artifact remains the seven scalar fields; installed `getWidgetSnapshot(widgetId)` is uncalled, `composer.js` carries no snapshot fields, and `composer_dashboard_snapshot.py` plus production tests are absent. Finish `.note-head` binding, headerless grips, dragstart capture, state/history/POST preservation, purpose-split resolution, deterministic validation/per-kind merge, prompt framing, explicit errors, and owned/shared tests per `projects/echarts/dev/specs/composer_dashboard_stack.md`. Persisted user-input GET/save/upload/download and authoritative server resolution are already live; conditional S3 uses a raw-boto3 bypass with a non-atomic plain-put degrade on unsupported stores, and no production tests. Installed reload halves use the matched old streaming pair; candidate neutral navigation-hold naming awaits paired promotion. Preserve seven unstaged parent Composer files while implementing; `enable_inline_chat`, local-dev port/ACL cleanup, and empty `website_dev.md` remain follow-ups. |
| v2 install status (built 2026-05-04; production re-verified 2026-07-11) | The folder workflow is installed: `run_pull` / `build_dashboard` / `refresh_dashboard`, `refresh_runner.py`, and parent-tree `jobs/hourly/refresh_dashboards.py`. The runner records phase-specific errors and refresh status; the hourly orchestrator isolates per-dashboard failures, categorizes skips, and updates each successful user's manifest pointer after the walk. Django invokes the same runner through `Popen`, but does not perform that pointer update. The active paths are `prism-core/dashboards/refresh_runner.py`, `jobs/hourly/refresh_dashboards.py`, and `web/backend_django/news/views.py`; old `ai_development/...` install prompts are historical. |

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
| `altair-payload/` | Ephemeral drag-and-drop copy of `projects/altair/altair-payload/`. User refreshes before promoting to PRISM. Post-`chart_render` split, so it carries the `chart_render/` + `utils/` subfolders. |
| `altair-payload-aug8/` | Frozen pre-split snapshot (flat layout, Aug 2-3 chart types + lean context). The state of `staging/altair-payload/` immediately before the 2026-08-08 consolidation. |
| `altair-payload-aug2/` | Frozen snapshot of what is INSTALLED IN PRISM today, and the base PRISM branch `macdist-refactor-chartRender` was cut against. The byte-diff reference for the split. |
| `altair-payload-aug1/` | Older frozen snapshot, kept for provenance. |
| `echarts-payload/` | Ephemeral drag-and-drop copy of `projects/echarts/echarts-payload/`. Same semantics. |
| `frontend-payload/` | (FUTURE — not yet promoted) Will be the ephemeral drag-and-drop copy of `projects/frontend/frontend-payload/ai_development/`. Same semantics; lands when the first PRISM promotion happens after the `2026-05-02_frontend_full_context.md` reply lands. |
| `voice_memos.md` | Raw capture space — unstructured thoughts, undated. Content is promoted to a project-side design spec or endeavor file when it matures. Low-friction exception to the "staging has a narrow purpose" rule. |
| `specs/` + `dashboard_user_input.md` | Compatibility pointers only. The former duplicate ECharts specs were retired; maintained bodies live under `projects/echarts/dev/specs/`. |
| `2026-07-20_composer_streaming_reload_change.md` | Existing paired prism-main/payload implementation handoff, retained because its gallery and external workflow reference this path. Its status banner distinguishes the live matched old pair from the canonical neutral candidate. |
| `prompts/` | PRISM-facing context-extraction prompts. |
| `prompts/open/` | Live prompts waiting to be sent, or sent but with reply not yet folded into `prism/`. One file per prompt, named `YYYY-MM-DD_<topic>.md` (unique topic slug per prompt — concurrent agents never collide on a shared slot). Frontmatter carries the session, send date, reply pointer, and fold-in plan. |
| `prompts/archive/` | Dated archive of past prompts (`YYYY-MM-DD_<topic>.md`) with frontmatter metadata. A prompt moves here (same filename, no rename) once the PRISM reply has been folded into `prism/` and the frontmatter is finalized with `status: USED` + `reply_folded_into:` pointers. |

There are no active duplicate specs or general handoff directories in
staging. Maintained project contracts live under `projects/<name>/dev/`;
the pointer files and the path-stable Composer reload handoff listed
above are explicit compatibility exceptions.

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
