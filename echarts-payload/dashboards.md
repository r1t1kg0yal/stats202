# ECharts Dashboards Pre-flight

- **Module:** `dashboards`
- **Audience:** PRISM (all interfaces, all workflows)
- **Tier:** 2 (on-demand)
- **Scope:** Pre-flight pointer for ALL dashboard construction in PRISM. Carries the folder layout, data-routing rules, the pull-primitives cheat sheet, and the atomicity contract — the minimum context PRISM needs BEFORE Tool 1 (data pulls) executes. The full authoring hub (Tools 2-4 templates, §C/§D CRUD patterns, §F glance scripts, §H heal lexicon, §3 spoke menu, §0 contract rules, archetypes, palettes, anti-patterns) lives in `dashboards_hub.md` and is fetched on-demand AFTER pulls verify.

**ECharts is the ONLY sanctioned path for PRISM dashboards.** `compile_dashboard(manifest)` and the v2 entry points (`run_pull` / `build_dashboard` / `refresh_dashboard`) are the entire surface. Hand-rolled HTML / CSS / JS, third-party dashboard frameworks, and ad-hoc `make_chart` composites used as dashboards all produce undefined behaviour and are forbidden.

---

## 1. Folder layout — the workspace

Every persistent dashboard lives at `users/{kerberos}/dashboards/{dashboard_name}/` with a small canonical layout. The 5 required files (3 top-level + 2 scripts) plus a `data/` directory are what the §2.5 audit (`_audit_dashboard_layout`) checks for.

```
users/{kerberos}/dashboards/{dashboard_name}/
  manifest_template.json   [REQUIRED · 1] LLM-editable spec, NO data
  manifest.json            [REQUIRED · 1] template + fresh data, embedded
  dashboard.html           [REQUIRED · 1] compile_dashboard output
  refresh_status.json      [optional · ≤1] runner-owned runtime state
  thumbnail.png            [optional · ≤1] author-owned preview image
  scripts/
    pull_data.py           [REQUIRED · 1] PULLS = {<name>: <fn>, ...}
    build.py               [REQUIRED · 1] TRANSFORMS = [<fn>, ...]
  data/                    [REQUIRED · CSVs/JSONs whose stems match manifest.datasets keys]
    rates_eod.csv          one CSV per dataset; stem matches manifest key byte-for-byte
    rates_intraday.csv     pull_market_data appends _eod / _intraday
    rates_metadata.json    pull_market_data sidecar uses the bare name
    cpi.csv                pull_haver_data: no suffix
    cpi_metadata.json
    swap_curve.csv         pull_plottool_data: no suffix
    fdic_gs_bank.csv       save_artifact: no suffix
  history/                 [optional] snapshots when keep_history=true; runner-managed
  archive/<UTC>/           [optional] manual quarantine; ignored by runner + audit
```

Cardinality is exact: one `manifest_template.json`, one `manifest.json`, one `dashboard.html`, one `scripts/pull_data.py`, one `scripts/build.py`. No second copies, no `_v2` / `_old` / `_backup` siblings.

The §2.5 audit (`_audit_dashboard_layout(folder)`, imported from `ai_development.dashboards`) raises if any of the 5 canonical paths are missing. Run it at the START of any inheritance and at the END of every Recipe 1 build. If it raises, the missing paths are heal targets — the full hub's §H Heal lexicon covers re-authoring.

---

## 2. Rule 5 — every CSV at `{folder}/data/<dataset>.csv`

This is the single most load-bearing rule for Tool 1 (data pulls). Get it right and the rest of the build composes cleanly; get it wrong and the refresh runner cannot find the data.

- Inside `pull_data.py`, every pull-function call AND every `save_artifact(...)` MUST pass `output_path=f'{SESSION_PATH}/data'`.
- **`pull_data.py` and `build.py` MUST each open with an explicit `SESSION_PATH = "<dashboard-path-literal>"` line.** PRISM substitutes the dashboard path at author time so build-time and refresh-time both resolve to the same `{folder}/data` folder. The engine's `run_pull` / `build_dashboard` / `refresh_dashboard` execute the script bytes verbatim — they don't inject `SESSION_PATH` for you.
- Without `output_path`, CSVs land in per-source subfolders (`market_data/`, `haver/`, `plottool_data/`) — `build_dashboard()` does not look there → refresh fails.
- `pull_market_data` ALWAYS appends `_eod` / `_intraday` to the filename. Pass `name='rates'` → `data/rates_eod.csv`. Use `rates_eod` as the manifest dataset key. Pass `name='rates_eod'` → broken `data/rates_eod_eod.csv`.
- The dataset key in `manifest.datasets` matches the on-disk CSV stem byte-for-byte.

---

## 3. Pull primitives cheat sheet

### 3.0 Required imports for `pull_data.py` (NON-NEGOTIABLE)

**Every `pull_data.py` MUST open with this exact import block, immediately after the `SESSION_PATH` literal:**

```python
SESSION_PATH = "users/{kerberos}/dashboards/{dashboard_name}"  # Rule 5 literal

from ai_development.core.s3_bucket_manager import s3_manager
from ai_development.mcp.utils.data_functions import (
    pull_market_data, pull_haver_data, pull_plottool_data,
    pull_fred_data, save_artifact,
)
```

**Why this is mandatory:** The in-session sandbox pre-injects `s3_manager`, `pull_market_data`, `pull_haver_data`, `pull_plottool_data`, `pull_fred_data`, and `save_artifact` into the namespace -- Tool 1's in-process verification loop passes because injection IS active during authoring. But `refresh_runner.py` (the cron + Refresh-button subprocess) re-execs `pull_data.py` in a CLEAN Python interpreter with NO sandbox injection. Without the imports above, the subprocess crashes immediately with `NameError: name 'pull_market_data' is not defined` and the dashboard refresh fails wholesale before a single pull runs. The `refresh_runner.py` engine has a defensive namespace-injection layer as backup (see `_build_exec_namespace`), but authoring the imports correctly is the FIRST line of defense and the only way to make the script readable as a standalone Python module.

Inside `pull_data.py` they all land their CSVs in the same flat folder by passing `output_path=f'{SESSION_PATH}/data'`. Per Rule 5, `SESSION_PATH` is a literal `pull_data.py` self-defines on its first line.

| Function | Call | On-disk CSV | Metadata sidecar | Manifest key |
|---|---|---|---|---|
| `pull_haver_data` | `pull_haver_data(codes=[...], start='YYYY-MM-DD', name='cpi', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/cpi.csv` | `data/cpi_metadata.json` | `"cpi"` |
| `pull_market_data` (eod) | `pull_market_data(coordinates=[...], start='YYYY-MM-DD', name='rates', mode='eod', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/rates_eod.csv` (always `_eod` suffix) | `data/rates_metadata.json` (no suffix) | `"rates_eod"` |
| `pull_market_data` (intraday) | same but `mode='iday'` | `data/rates_intraday.csv` | `data/rates_metadata.json` | `"rates_intraday"` |
| `pull_plottool_data` | `pull_plottool_data(expressions=[...], labels=[...], start='YYYY-MM-DD', name='swap_curve', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/swap_curve.csv` | `data/swap_curve_metadata.json` | `"swap_curve"` |
| `pull_fred_data` | `pull_fred_data(series=[...], start='YYYY-MM-DD', name='unrate', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/unrate.csv` | `data/unrate_metadata.json` | `"unrate"` |
| `save_artifact` | `save_artifact(data, name='gs_bank', output_path=f'{SESSION_PATH}/data', s3_manager=s3_manager)` | `data/gs_bank.csv` (or `.json` if dict) | none | `"gs_bank"` |

Three rules from the table that are easy to get wrong:

1. **`name=` does NOT include `_eod` / `_intraday`.** `pull_market_data` appends them. Pass `name='rates'` → `data/rates_eod.csv`. Pass `name='rates_eod'` → `data/rates_eod_eod.csv` (broken).
2. **`pull_market_data` metadata sidecar uses the bare `name`,** not the suffixed CSV stem. So `name='rates'` produces `data/rates_metadata.json` (one file even when both eod and intraday CSVs exist).
3. **`mode='eod'` is the default** but pass it explicitly. The intraday CSV is only written when `mode in ('iday', 'both')`. Wrap intraday calls in `try/except` (intraday is unavailable overnight / weekends / holidays) — see hub §6.1 for the defensive pattern.

The four pull primitives only cover Haver / GS Market Data / TSDB expressions / FRED. For everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, scraped tables, hand-built DataFrames), `save_artifact()` is the universal save helper. Same `output_path` semantics; lands a CSV (or JSON for `dict` payloads) at `{output_path}/{name}.{ext}` and is idempotent on re-run.

---

## 4. Rule 7 — the build flow is atomic (NO DEFERRED WORK)

The four steps of Recipe 1 (Tools 1, 2, 3, 4 in hub §B) are **non-divisible**. PRISM does not return to the user between Tool 1 and Tool 4. The dashboard does not exist as a deliverable until every artefact is on S3, the entry sits in `registry["dashboards"][]` (not as a top-level key), the user-manifest pointer reflects it, the §2.5 audit passes, AND Tool 4's subprocess refresh exits 0 with `refresh_status.json.status == "success"`.

**Once you respond, you terminate.** When PRISM sends a response, the pipeline TERMINATES. There is no background process, no autonomous follow-up, no "I'll keep working." There are exactly two acceptable patterns:

- **Pattern A (DEFAULT) — Build it this turn.** Author all three surfaces, run Tools 1-4 atomically, hand back the portal URL. Describe what was built in past tense. This is the right choice for >95% of dashboard asks because PRISM has 20+ tool calls per turn and a typical full build fits comfortably in that budget.

- **Pattern B — Hand control back to the user.** Only if the build genuinely cannot complete this turn (Rule 8 "genuine blocker" conditions in the hub). Surface the blocker plainly, build the slice that IS deliverable as a registered dashboard at a portal URL, and ask the specific question that unblocks the next slice.

**Forbidden phrasing — TWO categories. Strip every one of these from any user-facing message.**

Category 1 — future-tense leaks (any PRISM action that implies work after the response sends): "kicking off the build now", "next steps", "would you like me to", "to make this fully persistent", "I'll send you the portal URL once the build completes", "building lean v1 in your folder now" (when no Tools 1-4 sequence is about to execute in this same response), "I'll continue this in the next turn", "working on it now — update to follow".

Category 2 — engineering-detail leaks (any reference to internal vocabulary the user did not ask about; see §0 for the full principle): "pull_data.py / build.py / manifest_template.json / refresh_runner.py / data_functions.py / s3_manager / PULLS / TRANSFORMS / populate_template / compile_dashboard / _audit_dashboard_layout / SESSION_PATH", "the canonical import block", "namespace injection", "the refresh runner re-execs in a clean Python interpreter", "the attachment auditor rejected the dashboard", "contract drift", "the v3.0 / TRANSFORMS contract", "two ways to fix it: (1) refactor X to declare Y -- (2) push the derivations into Z", "I filed a ticket noting the contract gap". The user did not ask how the dashboard is built; they asked for the dashboard. Pick the implementation path, take the action, surface the outcome in product language.

If you genuinely can't complete the build this turn, ask plainly and wait for the reply. Failure handling: if any tool raises, the response to the user is the failure (with its diagnostic), not a rendered HTML preview gated behind a registration question.

---

## 4a. Portal URL hand-off (CRITICAL -- memorize the exact host)

The deliverable PRISM surfaces at the end of any build is the **portal URL**. There is exactly ONE canonical URL pattern and PRISM must NEVER invent, abbreviate, or guess at it:

```
http://reports.prism-ai.url.gs.com:8501/users/{kerberos}/dashboards/{dashboard_id}/
```

Breakdown of the load-bearing pieces (all required, all literal):

| Piece | Value | Notes |
|---|---|---|
| Scheme | `http://` | NOT `https://`. The host runs HTTP on port 8501 |
| Host | `reports.prism-ai.url.gs.com` | NOT `prism.gs.com`, NOT `prism-ai.gs.com`, NOT `dashboards.gs.com`. The host is `reports.prism-ai.url.gs.com` -- the `reports` subdomain on the `prism-ai.url.gs.com` zone |
| Port | `:8501` | Required. The portal does NOT listen on 80/443. (Live host is mysite_3 on `:8501`; legacy `:8501` was the mysite predecessor.) |
| Path | `/users/{kerberos}/dashboards/{dashboard_id}/` | Trailing slash required. `{kerberos}` is the author's kerberos; `{dashboard_id}` is the folder leaf under `users/{kerberos}/dashboards/`, matches `manifest.id` byte-for-byte. Every dashboard has ONE canonical URL containing the author's kerberos -- legacy `/profile/dashboards/<id>/` and `/community/dashboards/<author>/<id>/` 301-redirect here |

Why this matters: the portal URL is load-bearing because the serving Django view at this host:port injects the `window.PRISM_VIEWER` / `PRISM_DASHBOARD_AUTHOR` / `PRISM_DASHBOARD_SHARED` JS globals before `</head>`. Opening any other URL (including the bare `dashboard.html` from S3) skips that injection and the chrome silently degrades. Sending the user a wrong URL means they get a 404 / DNS error / page that loads but is missing functionality -- the dashboard build is effectively undelivered.

The URL is a literal string. Substitute only `{dashboard_id}`. Everything else is byte-identical across every build, every user, every dashboard.

---

## 5. The handoff — fetch the hub PLUS the spokes you need, in ONE call

You have enough context here to author `pull_data.py` from scratch (folder layout + Rule 5 + §3 pull primitives table) and to know the commitment you're making (Rule 7 atomicity). You do NOT have Tool 2 (build.py + manifest_template authoring), Tool 3 (registry write + user-manifest update), Tool 4 (subprocess refresh), the §C / §D CRUD patterns for subsequent edits, the §F glance patterns for inheriting an existing dashboard, the §H heal lexicon for drift, the §0 contract rules in their full discussion form, or any of the per-primitive spoke depth (chart-type mapping rules, widget specs, filter mechanics, tool-widget compute, archetype recipes, pipeline reuse decisions).

**The working model: a SINGLE `list_ai_repo` call fetches `dashboards_hub.md` PLUS every spoke this dashboard will need.** Decide the spoke list HERE during preflight, based on the user's ask + what `pull_data.py` produced. Do not fetch the hub first and then come back for spokes in a second tool call — that is the wrong shape and is forbidden. The hub does NOT carry a spoke menu; the spoke menu lives here, in this preflight, because spoke selection is a preflight decision.

### 5.1 When to fetch

- **First-time creation:** fetch AFTER `pull_data.py` is authored, persisted, and every PULLS function has verified its CSV lands at `{folder}/data/<stem>.csv` with the expected shape. The pulls inform which spokes you need (e.g. did intraday come through? then you'll want filters.md for the per-chart dataZoom; did you pull a correlation-friendly cross-section? then charts.md for the matrix recipe).
- **Edits to an existing dashboard** (CRUD on `manifest_template.json`, `scripts/pull_data.py`, `scripts/build.py`, or any heal): skip Tool 1 entirely and fetch the hub + spokes IMMEDIATELY — there is no fresh pull to gate on. Inspect the existing folder first (the hub's §F glance patterns also live in the hub, but you can read the manifest yourself with `s3_manager.get` to inform spoke selection).

### 5.2 The spoke menu — pick what this dashboard needs

| Spoke | What it carries | Pick when... |
|-------|-----------------|--------------|
| `dashboards/charts.md` | 30 chart types; mapping keys; cosmetic / layout knobs; annotations; `scatter_studio`; `correlation_matrix`; computed columns | ALWAYS for builds (every dashboard has charts). Skip only for pure-table or pure-tool dashboards |
| `dashboards/widgets.md` | KPI, table (incl. `row_click`), pivot, stat_grid, image, markdown, divider; provenance; `show_when` / `initial_state` / stat strip; markdown grammar | Whenever the build has KPIs, tables, pivots, stat_grids, markdown banners, or any non-chart widget |
| `dashboards/widget_tool.md` | `widget: tool` (form-driven compute) — pricers, scenarios, calculators; tool def shape; input + output kinds; canonical examples | Pricers, scenario calculators, what-if tools, any widget that takes user inputs and computes outputs |
| `dashboards/filters.md` | 10 filter types + 11 ops; cascading filters; per-chart `dataZoom`; `click_emit_filter`; compound rule filters; links (sync + brush) | Multi-tab dashboards with cross-widget filtering, intraday charts (per-chart dataZoom), click-to-filter interactions, linked-axis groups |
| `dashboards/template_crud.md` | THIN reference — niche per-CRUD-pattern cases (multi-target filter rebinding, `show_when` reference cleanup, etc.) | Only for unusually complex CRUD edits; the hub's §C carries the daily patterns |
| `dashboards/recipes.md` | 21 data-shape archetypes → chart types (the cookbook) + transforms hook patterns (YoY / composition / cross-dataset join / subset projection) for `build.py` | When you want a worked archetype to start from, or you're authoring `build.py` transforms (YoY, ratios, joins) |
| `dashboards/pipelines.md` | The pipeline cataloging mental model + reuse decision ladder (reuse-existing-CSV / extend-existing-pipeline / add-new-pipeline) + active-pipeline integrity rules | Editing data shape (new column / pull source / derived dataset); inheriting a dashboard with multiple pipelines |

### 5.3 The single fetch call

Mix and match. The call shape:

```python
list_ai_repo(
    file_paths=["dashboards_hub.md", "dashboards/charts.md", "dashboards/widgets.md", ...],
    mode="full",
)
```

Pass ONLY `file_paths` and `mode` actively — omit every other parameter. **Do NOT call `get_context()` again** — it is one-shot per user message. **Do NOT make a second `list_ai_repo` call later for spokes you forgot** — pick the full list now.

**Common combos** (one call, copy-paste verbatim):

| Build shape | Single call to copy |
|-------------|---------------------|
| Charts only (rare — no KPIs, no tables, no filters) | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/charts.md"], mode="full")` |
| Charts + KPI / table strip (typical small build) | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/charts.md", "dashboards/widgets.md"], mode="full")` |
| Charts + widgets + filters (typical multi-tab build) | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/charts.md", "dashboards/widgets.md", "dashboards/filters.md"], mode="full")` |
| Charts + widgets + filters + recipes (when you want a worked archetype to start from) | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/charts.md", "dashboards/widgets.md", "dashboards/filters.md", "dashboards/recipes.md"], mode="full")` |
| Pricer / scenario tool | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/widget_tool.md", "dashboards/widgets.md"], mode="full")` |
| Editing data shape (new column / pull source / derived dataset) | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/pipelines.md", "dashboards/recipes.md"], mode="full")` |
| Inheriting an unfamiliar dashboard for a substantial edit | `list_ai_repo(file_paths=["dashboards_hub.md", "dashboards/charts.md", "dashboards/widgets.md", "dashboards/filters.md", "dashboards/pipelines.md"], mode="full")` — the full kitchen-sink load |

When in doubt, lean toward including more spokes — the marginal cost of an extra spoke is small; the cost of a forbidden second `list_ai_repo` call (or worse, authoring against guessed APIs) is large.

### 5.4 What the hub carries

- **§A.2 path-decision table** — disambiguates which recipe applies (Recipe 1 first build; Recipe 2 / §C manifest-only edits; Recipe 3 / §D data-shape or transform edits; Recipe 4 / §E in-session recompile; Recipe 5 / §F glance/inspect; Recipe 6 / §G revert; Recipe 7 / §H heal; §I diagnose user-reported issue)
- **§B Recipe 1 Tools 2-4** — `build.py` authoring template, `manifest_template.json` composition, `dashboards_registry.json` write, `update_user_manifest`, `refresh_runner.py` subprocess spawn, success-message conventions. Tool 1 skeleton (the ~80-line `pull_data_py = "..."` author block plus the in-process verification loop) is here too if you want a copy-paste reference
- **§C Recipe 2** — surgical CRUD on `manifest_template.json` (add chart, add tab, edit filter, swap chart_type, etc.) with the `_walk_rows` helper and 8 mutation patterns
- **§D Recipe 3** — surgical CRUD on `pull_data.py` and `build.py` (add a pull, extend a pull, add a derived dataset) via READ → MUTATE → WRITE on persisted bytes
- **§E Recipe 4** — refresh discipline (`run_pull` vs `build_dashboard` vs `refresh_dashboard` vs subprocess; in-process vs subprocess decision)
- **§F Recipe 5** — HIGH-LEVEL GLANCE and DEEP GLANCE scripts for inheriting an existing dashboard
- **§G Recipe 6** — revert (chat history / `history/<UTC>/` snapshots / re-build from description)
- **§H Recipe 7** — heal lexicon (validator code → surgical fix mapping); silent-heal-vs-escalate rules
- **§I Diagnostic playbook** — three-read first move on user-reported issues (`refresh_status.json` + `console_log.jsonl` + `manifest.json`)
- **§0 Contract rules** — full discussion of Rules 1-8 (real data only, no literals in JSON, order of operations, canonical layout, data routing, portal URL hand-off, atomicity, one-shot vs slice)
- **§1 Engine entry points**, **§2 manifest shape**, **§2.3 metadata block + chrome contract**, **§2.5 audit**, **§4 layouts**, **§5 header actions**, **§6.1 intraday robustness**, **§6.2 save_artifact patterns**, **§7 palettes**, **§8 anti-patterns**, **§9 pre-flight checklist**, **§10 time horizons**

---

## 6. Browser-side telemetry beacon — the dashboard self-reports its own bugs

Every rendered dashboard ships with a JS beacon (emitted by `dashboards/rendering.py` into the `<head>` `<script>` block) that captures uncaught exceptions, unhandled promise rejections, `console.error` / `console.warn` calls, and resource-load failures (404s on dataset fetches, missing chart icons, etc.). Events are buffered client-side and POSTed via `navigator.sendBeacon` to `/api/dashboard/telemetry/` (`dashboard_telemetry_api` in `mysite/news/views.py`).

The receiving endpoint append-writes each event as a JSONL line to:

```
users/{kerberos}/dashboards/{dashboard_id}/console_log.jsonl
```

This sits right next to `refresh_status.json` in the canonical dashboard folder. Same kerberos-scoped data boundary as everything else.

**Event schema** (one JSON object per line):

```json
{
  "ts":         "2026-05-14T18:21:00.000Z",   // browser-side capture time
  "kind":       "error|unhandled_rejection|console_error|console_warn|resource_404|page_view",
  "message":    "...",            // truncated to 500 chars
  "source":    "...",             // for kind=error: filename
  "line":      123,               // for kind=error: lineno
  "col":       45,                // for kind=error: colno
  "stack":     "...",             // truncated to 2000 chars
  "tag":       "img|script|link", // for kind=resource_404
  "url":       "/users/.../dashboards/.../", // location.pathname at capture
  "ua":        "Mozilla/5.0 ...", // truncated to 200 chars
  "viewer":    "goyalri" | None,  // server-stamped (from GSSSO cookie)
  "received_at": "2026-05-14T18:21:04Z"     // server-stamped on POST receipt
}
```

**When to read it.** Any user complaint that smells like a front-end / rendering issue (chart blank, KPI shows `--`, dashboard hangs, layout broken, widget throws, refresh ran successfully but the page looks wrong). Distinct categories the beacon catches that the refresh log does NOT:

- ECharts option-validation warnings (`series[0].data is not an array`, etc.) surface as `console_error`
- Async ECharts init failures surface as `unhandled_rejection`
- Missing dataset 404s where the visual is broken but no JS error throws surface as `resource_404`
- Browser-specific crashes (ad-blockers, extension conflicts, CSP violations) surface as `error`

**How to read it (one-liner from a session script):**

```python
log_key = f'users/{kerberos}/dashboards/{dashboard_id}/console_log.jsonl'
if s3_manager.exists(log_key):
    body = s3_manager.get(log_key).decode('utf-8')
    events = [json.loads(l) for l in body.strip().split('\n') if l]
    # most recent first
    for evt in events[-50:]:
        print(evt['ts'], evt['kind'], (evt.get('message') or '')[:200])
else:
    print('No console_log.jsonl yet -- nobody has loaded the dashboard since the beacon shipped, or no events fired')
```

**Caveats:**
- The file only exists once at least one event has been POSTed. Absence of the file is NOT evidence of a healthy dashboard — it can also mean the dashboard hasn't been viewed since the beacon was deployed (older `dashboard.html` files compiled before the beacon shipped won't have it).
- Append-only. There is no rotation today; if a dashboard ever produces a runaway error flood, the file will grow unbounded. Escalate that as a friction if you see it.
- The `viewer` field is best-effort — anonymous loads of shared dashboards leave it `None` but the event still records.
- To force the beacon onto a stale dashboard, trigger a refresh (the rebuild re-emits `dashboard.html` from the current `rendering.py` template, which inlines the current beacon code).

**The diagnostic playbook for "dashboard X is broken":**

1. Pull `users/{kerberos}/dashboards/{dashboard_id}/refresh_status.json` — did the last refresh succeed? Look for log_path on failure.
2. Pull `users/{kerberos}/dashboards/{dashboard_id}/console_log.jsonl` — what did the user's BROWSER see while looking at it?
3. Cross-reference: refresh succeeded but console_log shows ECharts errors — the bug is in the manifest / chart spec, not the data pull. Refresh failed AND console_log empty — rebuild contract is broken; the user is seeing a stale HTML.
4. If the console_log shows a `resource_404` for a dataset path, the manifest is referencing a dataset key whose CSV no longer lands there (Rule 5 violation downstream of a recent edit).

---

## Quick reference

| Need | Where |
|---|---|
| Folder layout | §1 |
| `output_path` rule, `SESSION_PATH` literal, `_eod` suffix gotcha | §2 |
| Per-pull-function CSV name + manifest key | §3 |
| Atomicity contract, forbidden phrasing | §4 |
| Browser-side telemetry beacon (`console_log.jsonl`) | §6 |
| Everything else (Tool 2-4, CRUD, glance, heal, spokes, anti-patterns) | `list_ai_repo(file_paths=["dashboards_hub.md"], mode="full")` |
