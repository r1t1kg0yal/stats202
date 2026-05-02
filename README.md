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
│  apis         ████████████████░░░░  payload built (Session 4 ready) │
│  docstrings   ███░░░░░░░░░░░░░░░░░  scaffolded (L1 + L2-T1 stubs)   │
│  frontend     █░░░░░░░░░░░░░░░░░░░  scoping (prompt + scans only)   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Project | Maturity | Repo path (canonical) | Payload source | PRISM destination | Rule | prism/ refs | Active endeavor / spec |
|---------|----------|-----------------------|----------------|-------------------|------|-------------|------------------------|
| altair | mature | `projects/altair/` | `projects/altair/altair-payload/` | `mcp/utils/chart_functions.py` + `context/modules/static/chart_context.md` | `.cursor/rules/viz-platforms.mdc` | `code-sandbox.md`, `mcp-utils.md`, `vision-qc.md` | `projects/altair/dev/specs/composites.md` (next feature build) |
| echarts | mature | `projects/echarts/` | `projects/echarts/echarts-payload/` | `ai_development/dashboards/*.py` + `context/modules/static/tools/dashboards.md` (hub) + `dashboards/*.md` (spokes) | `.cursor/rules/viz-platforms.mdc` | `dashboard-refresh.md`, `dashboards-portal.md` | — |
| apis | payload built, Session 4 ready | `projects/apis/` | `projects/apis/apis-payload/clients/*.py` + `apis-payload/modules/*.md` | `mcp/clients/*_client.py` + `context/modules/static/{data_guides,instruments,tools}/*.md` | (future `api-clients.mdc`; Session 7) | `gs-proxy.md`, `api-clients.md`, `data-functions.md` §0 | `projects/apis/dev/endeavors/apis_endeavor.md` (8-session plan) |
| frontend | scoping | `projects/frontend/` | (not yet) | Django views/urls/templates + `mysite/` (TBD) | — | `dashboards-portal.md`, `architecture.md` §10 | — (scoping prompt at `projects/frontend/dev/prompt.md`) |
| docstrings | scaffolded (L1 + L2 Tier 1 stubs) | `projects/docstrings/` | `projects/docstrings/docstrings-payload/{*.py, *.md}` | L1 tool docstrings in `mcp/tools/{context_tool,global_tools,data_tools}.py` + L2 Tier 1 always-on static modules in `context/modules/static/{core,parsing_issue,code_sandbox_context,search_indexes,directory_tree,security_and_status,macro_style_guide}.md` | — | `mcp-tools.md` §3, `architecture.md` §3.1, §3.3 | — |

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

## Per-project details

### altair — static PNG chart engine

The single-chart builder (`make_chart`) and the composite family
(`make_2pack_*`, `make_3pack_*`, `make_4pack_grid`, `make_6pack_grid`).
Produces static PNGs (and an interactive HTML companion) for chat,
email, and report flows.

| Aspect | Value |
|---|---|
| Drag-and-drop status | READY. 15/15 demos pass. PRISM-runtime introspection confirmed every helper signature + the verbatim 14-entry namespace literal + sole-consumer property (`mcp/tools/script_exec_tools.py`). A live PRISM session is the only remaining verification step. |
| Canonical payload | `projects/altair/altair-payload/chart_functions.py`, `chart_functions_studio.py`, `chart_context.md` |
| Stub mirror | `projects/altair/ai_development/mcp/utils/*.py` — mirrors the 5 helpers `chart_functions.py` imports |
| Pinned interpreter | `projects/altair/.venv/` (regenerate after the 2026-05-02 restructure — shebangs point at old `GS/viz/altair/.venv/` paths) |
| Demo gallery | `projects/altair/dev/demos/01..25_*.py` (one file per demo; `run_all.py --all`) |
| QC workflow | `workflows/altair_qc.md` — adversarial vision + validation hardening |
| Notes file | `projects/altair/dev/notes.md` |
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

### apis — external API client platform

17 PRISM-side clients (treasury, treasurydirect, fdic, bis, ofr,
sec_edgar, prediction_markets, …) plus 7 staging-only sources. Unified
plug-and-play layout — 20 clients + 20 guide markdowns built as of
2026-05-02.

| Aspect | Value |
|---|---|
| Status | Payload built (`apis-payload/clients/` has 20 `*_client.py`, `apis-payload/modules/` has 20 skill markdowns). Session 4 (stub mirror body + harness + smoke demos) is the next step. |
| Canonical payload | `projects/apis/apis-payload/{clients,modules}/` (flat — user sorts `.md` into PRISM pillars on drop per D7) |
| Stub mirror | `projects/apis/ai_development/mcp/gs_app_proxy_negotiate.py` (placeholder; raises `NotImplementedError` — Session 4 fills body) |
| Harness | `projects/apis/dev/_harness.py` (placeholder — Session 4 fills body) |
| Transport buckets | 3 (per L1 in `apis_endeavor.md`): A = standard requests proxy (6 clients), B = manual CONNECT (5), C = direct vanilla requests (6). Plus `newyorkfed` as a function-injection exception (L4). |
| Session-by-session plan | `projects/apis/dev/endeavors/apis_endeavor.md` (8 sessions; 1-3 complete) |
| Next session handoff | `projects/apis/dev/handoffs/session_4.md` |
| Pre-payload archives | `projects/apis/dev/archive/_pre_payload/<src>/` (24 per-source folders; each migration archives here) |
| Source inventory | `projects/apis/README.md` (24 sources + per-source table) |
| Future rule | `.cursor/rules/api-clients.mdc` — writes in Session 7, after Sessions 5 (treasury) + 6 (treasurydirect) prove the pattern |

### frontend — staging mockup of PRISM's Django UI

Faux frontend infrastructure (Kerberos URL structure, S3 mock, sharing
rules, link structure, whitepaper refactor, UI aesthetics) so UI work
can happen here with browser access and Cursor vision on rendered
snapshots. Follows the viz/apis two-sided contract idea, but the
destination side is Django / mysite / templates, not the MCP layer.

| Aspect | Value |
|---|---|
| Status | SCOPING. Prompt and two OCR scans only; no code, no scaffold. |
| Scoping doc | `projects/frontend/dev/prompt.md` |
| Input scans | `projects/frontend/dev/scans/Scan May 2, 2026 at 2.36 AM.md`, `projects/frontend/dev/scans/Scan May 2, 2026 at 2.52 AM.md` |
| Next step | Comprehensive PRISM context-extraction prompt to capture current frontend structure (views.py, urls.py, templates, mysite/, S3 paths, caching layer, Kerberos URL resolution). Once that context lands in `prism/`, this project can be scaffolded properly (stub mirror + payload skeleton + first dev iteration). |
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
| Status | SCAFFOLDED. Placeholder files only; actual content pending verbatim PRISM scans (supplied as OCR'd markdown under `papers/converted/`, not via a context-extraction prompt). |
| Canonical payload | `projects/docstrings/docstrings-payload/` — flat folder with `.py` for L1 docstrings (DOCSTRING constant) and `.md` for L2 Tier 1 modules (raw markdown). |
| L1 files | `get_context.py`, `global_context.py`, `data_context.py` — each carries a module-level `DOCSTRING: str` constant. |
| L1 destinations | `mcp/tools/context_tool.py` (`get_context`), `mcp/tools/global_tools.py` (`global_context`), `mcp/tools/data_tools.py` (`data_context`, path TBD). Promote = paste the string between triple quotes into the PRISM function body as its docstring. |
| L2 Tier 1 files (seed triplet) | `core.md`, `parsing_issue.md`, `macro_style_guide.md`. The other 4 (`code_sandbox_context.md`, `search_indexes.md`, `directory_tree.md`, `security_and_status.md`) get scaffolded as their scans land. `user_context` is also Tier 1 always-on but is a runtime module and out of scope for this project. |
| L2 Tier 1 destinations | `context/modules/static/<name>.md` in PRISM (except `search_indexes`, which is cached in `context_cache/`). Promote = byte-identical file copy into PRISM. |
| Partial verbatim already available | `prism/mcp-tools.md` §3 carries the verbatim `get_context` "ONCE PER USER MESSAGE" / "NEVER CALL TWICE IN ONE TURN" rules. `prism/architecture.md` §3.3 lists the Tier 1 module catalog. |
| Skill-discipline | Applies to both layers per `.cursor/rules/skill-discipline.mdc` — every byte costs context budget at conversation start, weighted by load frequency (Tier 1 = always). |
| Next step | First scan to land overwrites the relevant placeholder. No `.cursor/rules/docstrings.mdc` yet — same discipline as apis (wait for the pattern to prove itself before codifying). |

---

## staging/ file index

| File / folder | Role |
|---|---|
| `README.md` | This file — the living projects roster |
| `altair-payload/` | Ephemeral drag-and-drop copy of `projects/altair/altair-payload/`. User refreshes before promoting to PRISM. |
| `echarts-payload/` | Ephemeral drag-and-drop copy of `projects/echarts/echarts-payload/`. Same semantics. |
| `voice_memos.md` | Raw capture space — unstructured thoughts, undated. Content is promoted to a project-side design spec or endeavor file when it matures. Low-friction exception to the "staging has a narrow purpose" rule. |
| `prompts/` | PRISM-facing context-extraction prompts. |
| `prompts/active.md` | Current live prompt (holding-pattern note when no round-trip is in flight) |
| `prompts/archive/` | Dated archive of past prompts (`YYYY-MM-DD_<topic>.md`) with frontmatter metadata |

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
| `papers/converted/` | OCR scans that feed knowledge ingestion and PRISM curation | When a scan is the input for a curation pass, it's referenced by line ranges from the relevant `prism/<topic>.md`. |
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
