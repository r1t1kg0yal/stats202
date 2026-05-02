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
│  echarts      ████████████████████  mature (drag-and-drop verified) │
│  apis         ████████████████████  rule codified (S8 batch ready)  │
│  docstrings   ███░░░░░░░░░░░░░░░░░  scaffolded (L1 + L2-T1 stubs)   │
│  whitepapers  ██████░░░░░░░░░░░░░░  intake from OCR scan complete   │
│  frontend     █░░░░░░░░░░░░░░░░░░░  scoping (prompt + scans only)   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Project | Maturity | Repo path (canonical) | Payload source | PRISM destination | Rule | prism/ refs | Active endeavor / spec |
|---------|----------|-----------------------|----------------|-------------------|------|-------------|------------------------|
| altair | mature | `projects/altair/` | `projects/altair/altair-payload/` | `mcp/utils/chart_functions.py` + `context/modules/static/chart_context.md` (hub) + `context/modules/static/chart_context/*.md` (spokes) | `.cursor/rules/viz-platforms.mdc` | `code-sandbox.md`, `mcp-utils.md`, `vision-qc.md`, `mcp-tools.md` §3+§5 | `projects/altair/dev/specs/composites.md` (next feature build) |
| echarts | mature | `projects/echarts/` | `projects/echarts/echarts-payload/` | `ai_development/dashboards/*.py` + `context/modules/static/tools/dashboards.md` (hub) + `dashboards/*.md` (spokes) | `.cursor/rules/viz-platforms.mdc` | `dashboard-refresh.md`, `dashboards-portal.md` | — |
| apis | 2/24 rebuilt + rule codified, Session 8 batch ready | `projects/apis/` | `projects/apis/apis-payload/clients/*.py` + `apis-payload/modules/*.md` | `mcp/clients/*_client.py` + `context/modules/static/{data_guides,instruments,tools}/*.md` | `.cursor/rules/api-clients.mdc` | `gs-proxy.md`, `api-clients.md`, `data-functions.md` §0 | `projects/apis/dev/endeavors/apis_endeavor.md` (8-session plan) |
| frontend | scoping + v0 design system | `projects/frontend/` | (not yet) | Django views/urls/templates + `mysite/` (TBD) | — | `dashboards-portal.md`, `architecture.md` §10 | `projects/frontend/dev/specs/design_system.md` (v0 — colors / fonts / type scale / component rules, DNA-inspired by gs.com 2024 rebrand); scoping prompt at `projects/frontend/dev/prompt.md` |
| docstrings | scaffolded (L1 + L2 Tier 1 stubs) | `projects/docstrings/` | `projects/docstrings/docstrings-payload/{*.py, *.md}` | L1 tool docstrings in `mcp/tools/{context_tool,global_tools,data_tools}.py` + L2 Tier 1 always-on static modules in `context/modules/static/{core,parsing_issue,code_sandbox_context,search_indexes,directory_tree,security_and_status,macro_style_guide}.md` | — | `mcp-tools.md` §3, `architecture.md` §3.1, §3.3 | — |
| whitepapers | intake from OCR scan complete | `projects/whitepapers/` | `projects/whitepapers/whitepapers-payload/*.md` | `ai_development/context/white_papers/{whitepaper_data_integrations,whitepaper_user_personalization,whitepaper_world_state_and_reasoning,faq,email_usage_guide}.md` | — | (none yet — sourced from `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md`) | — (next: workshop pass + verify against S3 via a `staging/prompts/open/YYYY-MM-DD_whitepapers_s3_verify.md` PRISM round-trip) |

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

This flow applies uniformly to altair, echarts, apis. For docstrings,
the "copy" step is paste-the-DOCSTRING-string-into-the-tool-function-
docstring rather than filesystem copy. For frontend the flow
materialises when the first payload lands.

---

## test_prompts/ convention (cross-project)

Every project's payload folder carries a `test_prompts/` subfolder.
Apis (D7 / D13 in `projects/apis/dev/endeavors/apis_endeavor.md`)
established the shape; altair / echarts / docstrings adopted it on
2026-05-02. Whitepapers is deferred (portal-served documents, not
chat-loaded context — `test_prompts/` is reconsidered after the
workshop pass). Frontend is N/A (no payload yet).

```
projects/<name>/<name>-payload/test_prompts/
├── <unit_1>_test.md     ← one file per natural unit:
├── <unit_2>_test.md       per-spoke (altair, echarts)
└── ...                    per-docstring / per-module (docstrings)
                            per-source (apis)
```

| Aspect | Rule |
|---|---|
| Files per project | One per natural unit (spoke / docstring / module / source). 5-7 files per project today. |
| Prompts per file | 7 canonical prompts that mix broad regression coverage AND specific recent-implementation tests for that unit. |
| Format | Pure prompt bodies separated by `---` horizontal rules. No headers, no frontmatter, no annotations. |
| Per-prompt convention | Each body is 1-3 sentences ending with "Let me know if frictions." |
| Drag-and-drop status | STAGING-ONLY. Carve-out from the byte-identical-payload invariant: `test_prompts/` does NOT ship to PRISM. The user drops `clients/` + `modules/` (apis), or the payload `.py` / `.md` files (altair / echarts / docstrings) — NEVER `test_prompts/`. |
| Two purposes | (1) **Per-iteration verification** — Cursor surfaces the 1-2 most discriminating prompts to the user as the success-criterion loop after promoting a unit to PRISM. (2) **Regression sweep** — re-paste any subset after a payload update to verify nothing regressed. |
| Loop shape | User pastes prompt body into PRISM → PRISM responds → no frictions = unit is done; frictions = user pastes the reply back, Cursor iterates payload + prompt, loop. The same `<unit>_test.md` is reusable across iterations. |

Per-project unit count and file inventory:

| Project | Units | Files in `test_prompts/` |
|---|---|---|
| apis | per-source | 1 today (`treasury_test.md`); grows as more clients are rebuilt (target ~20) |
| altair | per-spoke | 6 (`chart_types`, `mapping`, `annotations`, `dual_axis`, `composites`, `chart_center`) |
| echarts | per-spoke | 5 (`charts`, `widgets`, `widget_tool`, `filters`, `recipes`) |
| docstrings | per-unit (3 L1 + 3 L2-T1) | 6 (`get_context`, `global_context`, `data_context`, `core`, `parsing_issue`, `macro_style_guide`) |
| whitepapers | — (deferred) | 0 |
| frontend | — (no payload) | 0 |

This convention is intentionally **not codified as a `.cursor/rules/`
file yet** — same wait-for-pattern-to-prove-itself discipline applied
to apis (no `api-clients.mdc` until Session 7), docstrings, and
whitepapers. After at least one full feedback loop on a non-apis
project, the cross-project shape can be promoted to a rule if drift
warrants it.

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
| Canonical payload | `projects/altair/altair-payload/chart_functions.py`, `chart_functions_studio.py`, `chart_context.md` (hub) + `chart_context/*.md` (spokes) |
| Stub mirror | `projects/altair/ai_development/mcp/utils/*.py` — mirrors the 5 helpers `chart_functions.py` imports |
| Pinned interpreter | `projects/altair/.venv/` (regenerate after the 2026-05-02 restructure — shebangs point at old `GS/viz/altair/.venv/` paths) |
| Demo gallery | `projects/altair/dev/demos/01..25_*.py` (one file per demo; `run_all.py --all`) |
| Skill shape | Hub-and-spoke since 2026-05-02 (mirrors echarts' pattern). `chart_context.md` is the L2 hub; per-primitive depth in `chart_context/{chart_types,mapping,annotations,dual_axis,composites,chart_center}.md`. `TestSpokeDriftPrevention` in `dev/tests.py` pins the hub/spoke/engine triple. |
| QC workflow | `workflows/altair_qc.md` — adversarial vision + validation hardening |
| Notes file | `projects/altair/dev/notes.md` |
| Tests | `projects/altair/dev/tests.py` (`python tests.py` interactive; `python tests.py unit -v` headless). Currently houses the spoke-drift gate. |
| Test prompts | `altair-payload/test_prompts/{chart_types,mapping,annotations,dual_axis,composites,chart_center}_test.md` — one per spoke, 7 prompts each. Per the cross-project convention. STAGING-ONLY (does NOT ship). |
| Active feature work | `projects/altair/dev/specs/composites.md` — 4-batch plan for layered composites, forecast styling, new annotation classes (`BarValueLabels`, `BarHighlight`, `Connector`, `SeriesLabel`), two-level x-axis |

### echarts — interactive HTML dashboard compiler

The `compile_dashboard` pipeline + a hub-and-spoke skill. Emits
self-contained HTML dashboards with the echarts JS inlined; no external
dependencies at render time.

| Aspect | Value |
|---|---|
| Drag-and-drop status | VERIFIED end-to-end (local tests + demos) |
| Canonical payload | `projects/echarts/echarts-payload/` (__init__.py, config.py, echart_*.py, rendering.py, dashboards.md hub + dashboards/*.md spokes) |
| Static-asset mirror | `projects/echarts/ai_development/mysite/news/static/js/echarts.js` (no Python stub mirror needed — stdlib + pandas only) |
| Playwright sweep | `projects/echarts/dev/inspect_dashboard.py` |
| Skill shape | Hub-and-spoke since 2026-05-01. `dashboards.md` is the L2 hub; per-primitive depth in `dashboards/{charts,widgets,widget_tool,filters,recipes}.md`. `TestSpokeDriftPrevention` pins the hub/spoke/engine triple. |
| Notes file | `projects/echarts/dev/notes.md` |
| QC workflow | `workflows/dashboard_qc.md` — adversarial manifest synth + vision grading |
| Test prompts | `echarts-payload/test_prompts/{charts,widgets,widget_tool,filters,recipes}_test.md` — one per spoke, 7 prompts each. Per the cross-project convention. STAGING-ONLY (does NOT ship). |

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
| Status | SCOPING + v0 design system. Scoping brief, two OCR input scans, and `dev/specs/design_system.md` (v0 token SSOT) in place; no code, no Django scaffold yet. GS 2024 rebrand TTFs (GS Sans / GS Sans Condensed / GS Serif) dropped into PRISM `ai_development/mysite/fonts/` on 2026-05-02. |
| Scoping doc | `projects/frontend/dev/prompt.md` |
| Design system | `projects/frontend/dev/specs/design_system.md` — v0 SSOT. Every color, font, type size, spacing unit, and component primitive resolved to a named CSS variable. DNA-inspired by goldmansachs.com 2024 rebrand language (GS-owned typography, `#092C61` "Sky Blue" navy, alpha-on-black text tiers, sharp corners `--radius-none`, tight letter-spacing with `1px` only on uppercase labels). PRISM-voiced, not a gs.com clone. Tightens into a delta spec after the PRISM context-extraction prompt returns. |
| Input scans | `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md`, `projects/frontend/dev/scans/2026-05-02_portal_views_urls_templates.md` |
| Next step | (a) Comprehensive PRISM context-extraction prompt to capture current frontend structure (views.py, urls.py, templates, mysite/, S3 paths, caching layer, Kerberos URL resolution). Once that lands in `prism/`, this project can be scaffolded properly (stub mirror + payload skeleton + first dev iteration). (b) Fill in `<TO_FILL>` font filenames in `design_system.md` §1.2 from `ls ai_development/mysite/fonts/` in PRISM. |
| PRISM references for context | `prism/dashboards-portal.md` (Django identity, PAGE_ACCESS_RULES, share toggle), `prism/architecture.md` §10 (user system, kerberos resolution), `prism/dashboard-refresh.md` (refresh pipeline) |

### docstrings — SSOT for PRISM's always-loaded operating instructions

PRISM has two parallel "always-loaded" surfaces that both function as
operating instructions: the L1 tool docstrings (visible before any tool
call) and the L2 Tier 1 always-on static modules (loaded into
`<CONTEXT_START>` on every user message). This project owns the SSOT
for both, so they can be edited, diffed, and reviewed in staging, then
pasted into PRISM source at promote time.

| Aspect | Value |
|---|---|
| Status | SCAFFOLDED. Placeholder files only; actual content pending verbatim PRISM scans (supplied as OCR'd markdown under `scans/inbox/` and triaged into `scans/prism/` per `.cursor/rules/scans.mdc`, not via a context-extraction prompt). |
| Canonical payload | `projects/docstrings/docstrings-payload/` — flat folder with `.py` for L1 docstrings (DOCSTRING constant) and `.md` for L2 Tier 1 modules (raw markdown). |
| L1 files | `get_context.py`, `global_context.py`, `data_context.py` — each carries a module-level `DOCSTRING: str` constant. |
| L1 destinations | `mcp/tools/context_tool.py` (`get_context`), `mcp/tools/global_tools.py` (`global_context`), `mcp/tools/data_tools.py` (`data_context`, path TBD). Promote = paste the string between triple quotes into the PRISM function body as its docstring. |
| L2 Tier 1 files (seed triplet) | `core.md`, `parsing_issue.md`, `macro_style_guide.md`. The other 4 (`code_sandbox_context.md`, `search_indexes.md`, `directory_tree.md`, `security_and_status.md`) get scaffolded as their scans land. `user_context` is also Tier 1 always-on but is a runtime module and out of scope for this project. |
| L2 Tier 1 destinations | `context/modules/static/<name>.md` in PRISM (except `search_indexes`, which is cached in `context_cache/`). Promote = byte-identical file copy into PRISM. |
| Partial verbatim already available | `prism/mcp-tools.md` §3 carries the verbatim `get_context` "ONCE PER USER MESSAGE" / "NEVER CALL TWICE IN ONE TURN" rules. `prism/architecture.md` §3.3 lists the Tier 1 module catalog. |
| Skill-discipline | Applies to both layers per `.cursor/rules/skill-discipline.mdc` — every byte costs context budget at conversation start, weighted by load frequency (Tier 1 = always). |
| Test prompts | `docstrings-payload/test_prompts/{get_context,global_context,data_context,core,parsing_issue,macro_style_guide}_test.md` — one per unit (3 L1 + 3 L2-T1), 7 prompts each. Each prompt exercises a behavior the docstring/module is supposed to govern (e.g. ONCE-per-message for `get_context`, routing decisions for `data_context`, macro tone for `macro_style_guide`). STAGING-ONLY (does NOT ship). |
| Next step | First scan to land overwrites the relevant placeholder. No `.cursor/rules/docstrings.mdc` yet — same discipline as apis (wait for the pattern to prove itself before codifying). |

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
| Status | INTAKE COMPLETE (from OCR scan). All 5 payload files populated verbatim from `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md`. Workshop pass pending. |
| Canonical payload | `projects/whitepapers/whitepapers-payload/` — flat folder, 5 markdown files. |
| Files (3 white papers) | `whitepaper_data_integrations.md`, `whitepaper_user_personalization.md`, `whitepaper_world_state_and_reasoning.md` |
| Files (2 how-to guides) | `faq.md`, `email_usage_guide.md` |
| PRISM destinations | `ai_development/context/white_papers/<name>.md` — byte-identical drag-and-drop. |
| Portal coupling | `WHITEPAPER_MAP`, `views.{whitepapers,user_guides,faq,email_guide,download_whitepaper}`, templates `news/{whitepapers,user_guides,doc_page}.html`, URLs `/whitepapers/`, `/user-guides/`, `/faq/`, `/guide/email/`, `/resources/<doc_name>/`. All live in `projects/frontend/`, not here. |
| Source for content intake | `projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md` (OCR scan; carries known artifacts — full-section duplication in User Personalization, title-drift on World State & FICC Reasoning vs portal's "World State & Reasoning") |
| Source for portal wiring | `projects/frontend/dev/scans/2026-05-02_portal_views_urls_templates.md` (`WHITEPAPER_MAP`, view bodies, templates) |
| Workshopping flow | PULL (verbatim, complete) → INQUIRE (verify intake gaps via a dedicated `staging/prompts/open/YYYY-MM-DD_<topic>.md` PRISM round-trip) → WORKSHOP (refactor opinionated) → PROMOTE (staging-upstream from there). Same direction-of-flow shift as docstrings. |
| Skill-discipline | Applies — every byte serves a portal-rendered page; noise compounds across visitors. |
| Test prompts | DEFERRED. Whitepapers are portal-served customer documents, not chat-loaded context. The `test_prompts/` model (per-iteration PRISM round-trip) doesn't map cleanly until the workshop pass clarifies what "testing" means for portal docs (RAG-style? rendered-page check?). Re-evaluate after workshop. |
| Next step | (a) Generate a `staging/prompts/open/YYYY-MM-DD_whitepapers_s3_verify.md` PRISM round-trip to verify the OCR-extracted content matches S3 bytes and close inventory gaps; (b) workshop pass to collapse the User Personalization OCR duplication, reconcile World State title drift, and apply broader content/aesthetic refactor. No `.cursor/rules/whitepapers.mdc` yet — same wait-for-pattern discipline as apis/docstrings. |

---

## staging/ file index

| File / folder | Role |
|---|---|
| `README.md` | This file — the living projects roster |
| `altair-payload/` | Ephemeral drag-and-drop copy of `projects/altair/altair-payload/`. User refreshes before promoting to PRISM. |
| `echarts-payload/` | Ephemeral drag-and-drop copy of `projects/echarts/echarts-payload/`. Same semantics. |
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
