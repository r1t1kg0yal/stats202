---
class: context-extraction
topic: light-refresh-open-presence
status: OPEN
created: 2026-07-16
reply_folded_into:
  - prism/dashboard-refresh.md
  - prism/dashboards-portal.md
  - projects/echarts/echarts-payload/dashboards_hub.md
---

# Context-extraction prompt — light refresh + open-tab presence

**Why this exists (staging-side note; do not paste this section into
PRISM):**

Staging is implementing two contracts:

1. **Light refresh (button):** pull CSVs → update `manifest.json`
   datasets/specs + stamp registry → skip `compile_dashboard` / HTML
   rewrite. Open tabs consume via `GET /api/dashboard/data/` +
   `setOption`.
2. **Open-tab autorefresh:** browser heartbeat + short-cadence light
   pull for dashboards that are currently open; 15-minute full walk
   remains for cold HTML.

We already know the broad runner/cron shape from
`2026-07-11_dashboard_architecture_validation.md`. This prompt only
closes the live-data API, refresh spawn argv, serving-view injection,
and whether any presence/telemetry surface can drive open-only light
refresh.

Fold the reply into the paths listed in `reply_folded_into` after
review. Do not invent presence infrastructure in docs until the reply
confirms what exists.

---

## Paste the following into PRISM

# Light refresh + open-tab presence contracts (read-only)

You are being asked to introspect the live dashboard refresh / live-data /
presence surfaces so staging can implement a data-only refresh path and
open-tab autorefresh. This is a pure read-only context-extraction request.

Use `list_ai_repo`, repository search, direct source reads, and narrowly
scoped read-only `execute_analysis_script` as needed. Do not answer from
memory or from prior conversation summaries.

Do not reproduce the full dashboard subsystem inventory from earlier
architecture validation. Bound reads to the contracts below.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify any repository file;
- run `refresh_runner.py`, `refresh_dashboards.py`, `compile_dashboard`,
  `build_dashboard`, `refresh_dashboard`, `run_pull`, or any pull/build;
- issue POST/PUT/PATCH/DELETE to dashboard endpoints;
- write, copy, move, or delete S3 objects;
- update registries, manifests, refresh_status, or user manifests;
- install/upgrade packages or monkey-patch runtime.

If a subsection cannot be answered, skip it and list it under
## Could not resolve at the end.

## Reply protocol

- Mirror the numbered section headings exactly.
- Cite `path:line` for every claim.
- Paste complete bounded source blocks verbatim in fenced code blocks.
- Prefer exact signatures, JSON shapes, and argv over paraphrase.

---

## 1. Live data API (`GET /api/dashboard/data/`)

1.1 Paste the full `dashboard_data_api` view (or current name) from
`web/backend_django/news/views.py`, including auth, share handling,
ETag / `If-None-Match`, 304 path, and response construction.

1.2 Exact `urls.py` pattern + view name for this route.

1.3 Response JSON schema on HTTP 200: every top-level key, types, and
which fields come from manifest vs `resolve_chart_specs` vs registry.
Paste one anonymized example shape (keys only / placeholder values).

1.4 How `last_refreshed` / ETag is computed. What must change on S3 for
a subsequent poll to return 200 instead of 304.

1.5 Does this endpoint recompile HTML? Does it call
`resolve_chart_specs`? Paste the call site.

## 2. On-demand refresh API (heavy path today)

2.1 Paste full `refresh_dashboard_api` and `refresh_status_api`.

2.2 Exact Popen / spawn argv, cwd, env, `start_new_session`, log path.
Confirm whether any `mode` / `light` / `data_only` flag exists today
(yes/no + evidence).

2.3 Stale-lock / 409 rules as implemented (paste the condition block).

2.4 Does on-demand success call `update_dashboard_pointer`? Cite yes/no.

2.5 Developer refresh route
`/api/developer/dashboards/<dashboard_id>/refresh/`: paste view; note
differences from the user refresh API.

## 3. Serving-view injection for open dashboards

3.1 For `user_dashboard_detail`, `community_dashboard_detail`, and
`observatory_dashboard_detail` (or current names): paste the blocks that
inject into served HTML any of:
`PRISM_TEMPLATE_HASH`, `PRISM_VIEWER`, `data_url`, `live_refresh_seconds`,
`api_url`, `status_url`, kerberos, dashboard_id.

3.2 If injection is template-side, paste the relevant template fragment
paths + contents.

3.3 Confirm whether a dashboard opened via community/share URL can hit
`/api/dashboard/data/` and `/api/dashboard/refresh/` (auth rules).

## 4. Presence / open-tab / telemetry

4.1 Paste the `/api/dashboard/telemetry/` view (or current name) in full.
What events does it accept? Does it record "dashboard open / still
viewing"? Retention / TTL?

4.2 Search the repo for presence, heartbeat, viewer, open dashboard,
`live_refresh`, or similar. Paste every match that implies server-side
knowledge of which dashboards are currently open. If none, say NONE
with the search terms used.

4.3 Is there any scheduler, job, or in-view loop that refreshes only
dashboards with active viewers today? Yes/no + evidence.

## 5. Runner + orchestrator mode surface

5.1 Paste `refresh_runner.py` CLI argparse / `main()` entry and the
phase list inside `run()`. Confirm only `--folder` and `--log-path`
(or list every flag).

5.2 Paste the spawn site(s) in `jobs/hourly/refresh_dashboards.py`
that launch the runner (argv only; skip due-logic prose already known).

5.3 Confirm whether `build_dashboard` always writes `dashboard.html`.
Paste the persist call site. Is there any existing function that updates
`manifest.json` datasets without compiling HTML?

## 6. Emitted browser chrome contract (from installed rendering.py)

6.1 From installed `prism-core/dashboards/rendering.py`, paste the
`doRefresh` / `pollStatus` / `pollLiveData` / `applyLiveData` blocks
(or line ranges + SHA if too large — prefer bounded function bodies).

6.2 Default `live_refresh_seconds` when metadata omits it. Behavior when
value is `0`.

6.3 After Refresh success, does chrome call `pollLiveData()` or
`location.reload()`? Paste the exact success branch.

## 7. Gap checklist for staging design (fill yes/no/unknown)

| Question | Answer | Evidence |
|---|---|---|
| Server light/data-only refresh exists? | | |
| Open-tab presence map exists? | | |
| Telemetry usable as presence heartbeat? | | |
| Data API sufficient for setOption live swap? | | |
| TEMPLATE_HASH injected on all detail views? | | |
| Refresh POST accepts a mode field today? | | |

## Could not resolve

List any subsection blocked, with what you tried.
