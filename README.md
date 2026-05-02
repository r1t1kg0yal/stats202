# staging/

Cross-project meta layer for the PRISM-staging repo. Every artifact here
is either (a) a multi-session plan, (b) a design spec, (c) a handoff
between sessions, (d) an active PRISM context-extraction prompt, or (e)
the **living projects roster below**. None of this ships to PRISM.

The counterpart is `prism/` — the curated PRISM-side SSOT that Cursor
reads whenever it edits anything under `GS/` that has to interoperate
with PRISM. Where `prism/` describes how PRISM works, `staging/`
describes what is being built for PRISM right now.

---

## Staging projects (the living cheat sheet)

```
┌─────────────────────────────────────────────────────────────────────┐
│ STATUS AT A GLANCE                                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  altair       ████████████████████  mature (drag-and-drop ready)    │
│  echarts      ████████████████████  mature (drag-and-drop verified) │
│  apis         ███████░░░░░░░░░░░░░  scaffolded (Session 4 ready)    │
│  L1 docstr.   ██░░░░░░░░░░░░░░░░░░  scaffolded (placeholder only)   │
│  frontend     █░░░░░░░░░░░░░░░░░░░  scoping (prompt + scans only)   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

| Project | Maturity | Repo path | PRISM destination | Rule | prism/ refs | Active endeavor / SSOT |
|---------|----------|-----------|-------------------|------|-------------|------------------------|
| altair | mature | `GS/viz/altair/` | `mcp/utils/chart_functions.py` + `context/modules/static/chart_context.md` | `.cursor/rules/viz-platforms.mdc` | `code-sandbox.md`, `mcp-utils.md`, `vision-qc.md` | `staging/altair_composites_spec.md` (next feature build) |
| echarts | mature | `GS/viz/echarts/` | `ai_development/dashboards/*.py` + `context/modules/static/tools/dashboards.md` (hub) + `dashboards/*.md` (spokes) | `.cursor/rules/viz-platforms.mdc` | `dashboard-refresh.md`, `dashboards-portal.md` | — |
| apis | scaffolded | `GS/data/apis/` | `mcp/clients/*_client.py` + `context/modules/static/{data_guides,instruments,tools}/*.md` | (future `api-clients.mdc`; Session 7) | `gs-proxy.md`, `api-clients.md`, `data-functions.md` §0 | `staging/apis_endeavor.md` (8-session plan) |
| frontend | scoping | `GS/frontend/` | Django views/urls/templates + `mysite/` (TBD) | — | `dashboards-portal.md`, `architecture.md` §10 | — (scoping prompt only) |
| L1 docstrings | proposed | `GS/knowledge/docstrings/` | PRISM tool docstrings in `mcp/tools/context_tool.py`, `mcp/tools/global_tools.py`, `mcp/tools/data_tools.py` | — | `mcp-tools.md` §3, `architecture.md` §3.1 | — |

Always-applied rule: `.cursor/rules/prism.mdc` (the repo orientation).
Orthogonal rule: `.cursor/rules/skill-discipline.mdc` (applies to every
skill/context file under `context/modules/static/`).

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
| Stub mirror | `GS/viz/altair/ai_development/mcp/utils/*.py` — mirrors the 5 helpers `chart_functions.py` imports |
| Pinned interpreter | `GS/viz/altair/.venv/` |
| Demo gallery | `GS/viz/altair/dev/demos/01..25_*.py` (one file per demo; `run_all.py --all`) |
| QC workflow | `workflows/altair_qc.md` — adversarial vision + validation hardening |
| Notes file | `GS/viz/altair/dev/notes.md` |
| Active feature work | `staging/altair_composites_spec.md` — 4-batch plan for layered composites, forecast styling, new annotation classes (`BarValueLabels`, `BarHighlight`, `Connector`, `SeriesLabel`), two-level x-axis |

### echarts — interactive HTML dashboard compiler

The `compile_dashboard` pipeline + a hub-and-spoke skill. Emits
self-contained HTML dashboards with the echarts JS inlined; no external
dependencies at render time.

| Aspect | Value |
|---|---|
| Drag-and-drop status | VERIFIED end-to-end (local tests + demos) |
| Static-asset mirror | `GS/viz/echarts/ai_development/mysite/news/static/js/echarts.js` (no Python stub mirror needed — stdlib + pandas only) |
| Playwright sweep | `GS/viz/echarts/dev/inspect_dashboard.py` |
| Skill shape | Hub-and-spoke since 2026-05-01. `dashboards.md` is the L2 hub; per-primitive depth in `dashboards/{charts,widgets,widget_tool,filters,recipes}.md`. `TestSpokeDriftPrevention` pins the hub/spoke/engine triple. |
| Notes file | `GS/viz/echarts/dev/notes.md` |
| QC workflow | `workflows/dashboard_qc.md` — adversarial manifest synth + vision grading |

### apis — external API client platform

17 PRISM-side clients (treasury, treasurydirect, fdic, bis, ofr,
sec_edgar, prediction_markets, …) plus 7 staging-only sources. Moving
from vanilla-`requests` staging scripts + PRISM-side clients into a
byte-identical plug-and-play model that mirrors the viz pattern.

| Aspect | Value |
|---|---|
| Status | SCAFFOLDED. Session 4 (stub mirror + harness) is ready to start. |
| Payload model | Unified `apis-payload/{clients,modules}/` at the apis root (flat — user sorts `.md` into PRISM pillars on drop). Locked 2026-05-02 as D4 in `apis_endeavor.md`. |
| Stub mirror | `GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py` (placeholder; raises `NotImplementedError`) |
| Harness | `GS/data/apis/dev/_harness.py` (placeholder) |
| Transport buckets | 3 (per L1 in `apis_endeavor.md`): A = standard requests proxy (6 clients), B = manual CONNECT (5), C = direct vanilla requests (6). Plus `newyorkfed` as a function-injection exception (L4). |
| Session-by-session plan | `staging/apis_endeavor.md` (8 sessions; 1-3 complete) |
| Next session handoff | `staging/handoffs/session_4.md` |
| Source inventory | `GS/data/apis/README.md` (24 sources + per-source table) |
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
| Scoping doc | `GS/frontend/prompt.md` |
| Input scans | `GS/frontend/Scan May 2, 2026 at 2.36 AM.md`, `GS/frontend/Scan May 2, 2026 at 2.52 AM.md` |
| Next step | Comprehensive PRISM context-extraction prompt to capture current frontend structure (views.py, urls.py, templates, mysite/, S3 paths, caching layer) before scaffolding. |
| PRISM references for context | `prism/dashboards-portal.md` (Django identity, PAGE_ACCESS_RULES, share toggle), `prism/architecture.md` §10 (user system, kerberos resolution), `prism/dashboard-refresh.md` (refresh pipeline) |

### L1 docstrings — SSOT for PRISM's always-loaded tool docstrings

PRISM's L1 context layer = tool signatures + docstrings, always visible
before any tool call. The docstrings are large and carry critical
behavior rules (e.g. `get_context`'s "ONCE PER USER MESSAGE" invariant).
This project holds the SSOT for those docstrings so they can be edited,
diffed, and reviewed in staging, then pasted into PRISM source at
promote time.

| Aspect | Value |
|---|---|
| Status | SCAFFOLDED. Placeholder files only; actual docstring content pending a PRISM context-extraction round-trip. |
| Folder | `GS/knowledge/docstrings/` |
| Files | `README.md`, `get_context.py`, `global_context.py`, `data_context.py` — each with a module-level `DOCSTRING: str` constant |
| PRISM destinations | `mcp/tools/context_tool.py` (get_context), `mcp/tools/global_tools.py` (global_context), `mcp/tools/data_tools.py` (data_context) — docstrings are embedded in the function bodies; promote = paste the string |
| Partial verbatim already available | `prism/mcp-tools.md` §3 carries the verbatim `get_context` "ONCE PER USER MESSAGE" / "NEVER CALL TWICE IN ONE TURN" rules. Session 2 of the apis endeavor surfaced much of the `get_context` docstring context. |
| Next step | Context-extraction prompt to PRISM for verbatim docstrings. No `.cursor/rules/l1-docstrings.mdc` yet — same discipline as apis (wait for the pattern to prove itself before codifying). |

---

## staging/ file index

| File / folder | Role |
|---|---|
| `README.md` | This file — the living projects roster |
| `apis_endeavor.md` | Active multi-session plan for the apis project |
| `altair_composites_spec.md` | One-shot design spec for altair's next feature (composites + forecast) |
| `voice_memos.md` | Raw capture space — unstructured thoughts, undated. Content is promoted to a design spec or an endeavor file when it matures. |
| `prompts.md` | Active PRISM context-extraction prompt. Holding pattern ("no active prompt") when no round-trip is in flight. |
| `handoffs/` | Per-session handoff prompts. `session_<N>.md` for apis sessions; `<workflow>_session_<N>.md` for workflow runs (e.g. `dashboard_qc_session_1.md`). |
| `prompts_archive/` | Archived context-extraction prompts. Dated-named (`YYYY-MM-DD_<topic>.md`) with frontmatter metadata. |
| `archive/external_repos/` | Archived external repo references |

---

## Related folders (for cross-orientation)

| Folder | What it is | When it's relevant |
|---|---|---|
| `prism/` | Curated PRISM-side SSOT (architecture, helpers, tool contracts) | Always, when editing anything that PRISM consumes. `prism/README.md` is the routing table. |
| `workflows/` | Timeless, pasteable workflow prompts (`altair_qc.md`, `dashboard_qc.md`, …) | When kicking off a named workflow-type session. Not session-specific. |
| `papers/converted/` | OCR scans that feed knowledge ingestion and PRISM curation | When a scan is the input for a curation pass, it's referenced by line ranges from the relevant `prism/<topic>.md`. |
| `.cursor/rules/` | Agent behavior rules (`prism.mdc` is always-applied) | Always — `prism.mdc` is the repo orientation rule |

---

## Freshness mandate

This cheat sheet is load-bearing for Cursor sessions: agents rely on it
to orient to the active staging surface. A stale roster is worse than
no roster. Update this file whenever any of the following happens:

| Event | What to update here |
|---|---|
| A project's maturity changes (scoping → scaffolded → mature) | The status-at-a-glance bar + the summary-table Maturity column + the per-project subsection |
| A new staging project starts (new folder under `GS/`) | A new row in the summary table + a new per-project subsection + a status bar entry |
| A project retires or merges into another | Move the section to an `archive/` reference (never delete), update the table row, update the status bar |
| A new endeavor file lands under `staging/` | Update the relevant project's "Active endeavor" cell + add to the staging/ file index if not already present |
| A new rule lands that governs a project | Update the relevant project's Rule cell + the per-project subsection |
| A PRISM destination path changes (rare — PRISM-side restructure) | Update the PRISM destination cell + the per-project subsection + verify `prism/codebase-tree.md` matches |

This freshness invariant is identical in spirit to the one in the
archived `project-clis.mdc` rule (which governs the `cli_<project>.py`
files at the repo root): if the roster doesn't match reality, it lies,
and agents are misled.

A stale cheat sheet is a bug. Treat "cheat sheet drift detected" the
same way you'd treat "PRISM payload drift detected": stop, fix it, then
continue.
