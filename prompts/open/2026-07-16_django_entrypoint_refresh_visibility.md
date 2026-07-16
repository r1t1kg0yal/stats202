---
class: context-extraction
topic: django-entrypoint-refresh-visibility
status: OPEN
created: 2026-07-16
depends_on:
  - staging/prompts/archive/2026-07-16_light_refresh_open_presence.md
prerequisite_payload: []
reply_folded_into:
  - prism/dashboard-refresh.md
  - prism/dashboards-portal.md
  - prism/_changelog.md
---

# Context-extraction prompt — verbatim `views.py` / `urls.py` / `entrypoint.py`

**Why this exists (staging-side note; do not paste this section into
PRISM):**

Staging already owns the echarts payload half of open-tab light refresh
(`refresh_runner --mode light|full`, `record_open_presence`, chrome
heartbeat + `pollLiveData`). Two END-USAGE patch prompts are also open:

- `2026-07-16_django_light_refresh_presence_wire.md`
- `2026-07-16_entrypoint_site_open_refresh.md`

Cursor still lacks **verbatim current source** for the three PRISM-parent
files that close the loop. A prior extraction
(`2026-07-16_light_refresh_open_presence`) confirmed gaps (Django ignored
`mode`; no `/api/dashboard/presence/`) but did not paste full route
tables, full refresh/presence views, or `entrypoint.py site` wiring.

This prompt is read-only introspection of exactly those three files so
docs can pin live behavior vs staged contract without guessing.

Fold the reply into the paths listed in `reply_folded_into` after
review.

---

## Paste the following into PRISM

# Verbatim refresh wire: views.py + urls.py + entrypoint.py

You are being asked for a pure read-only context-extraction of the three
parent-tree files that sit outside the echarts payload and close the
dashboard live-refresh loop. Do not answer from memory or prior chat
summaries.

Use `list_ai_repo`, repository search, and direct source reads. Narrow
read-only `execute_analysis_script` is allowed only to resolve paths /
line numbers / `inspect` metadata — not to mutate state.

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
- Prefer exact signatures, argv lists, and route tables over paraphrase.
- When a symbol is absent, say **ABSENT** with the search terms used.

---

## 0. File identities

For each path below, report: exists yes/no, absolute path, byte size,
line count, and SHA-256 (or `sha256sum` / hashlib) of the file on disk.

| Path |
|---|
| `web/backend_django/news/urls.py` |
| `web/backend_django/news/views.py` |
| `entrypoint.py` (repo-root; confirm exact path if nested) |

Also report: current `prism-main` HEAD (short) and whether
`prism-core/dashboards/refresh_runner.py` argparse includes `--mode`
with choices `light`/`full` (yes/no + paste the argparse lines only).

---

## 1. `urls.py` — dashboard API + detail routes

1.1 Paste every `path(...)` / `re_path(...)` entry in
`web/backend_django/news/urls.py` whose route string contains
`dashboard` (case-insensitive). Include the full call (pattern, view,
`name=`).

1.2 Explicit checklist (yes/no + cite the line):

| Route | Present? |
|---|---|
| `api/dashboard/data/` | |
| `api/dashboard/refresh/` | |
| `api/dashboard/refresh/status/` | |
| `api/dashboard/telemetry/` | |
| `api/dashboard/presence/` | |
| `api/dashboard/share/` | |
| developer dashboard refresh route(s) | |

1.3 If `api/dashboard/presence/` is ABSENT, say so plainly. Do not invent
it.

---

## 2. `views.py` — live data + refresh + presence + telemetry

Paste each of the following **in full** (entire function body). If a
name differs, paste the current name and note the rename.

2.1 `dashboard_data_api` (GET live datasets / ETag / 304).

2.2 `refresh_dashboard_api` (POST spawn). Call out whether the JSON body
field `mode` is read and whether `--mode` appears in the Popen argv.
Paste the exact argv list construction.

2.3 `refresh_status_api` (GET status poll).

2.4 Telemetry POST view (`dashboard_telemetry_api` or current name).

2.5 `dashboard_presence_api` — if ABSENT, write **ABSENT** and paste the
`rg`/`grep` result for `presence` / `record_open_presence` under
`web/backend_django/`. If present, paste the full function.

2.6 Stale-lock / HTTP 409 block inside the refresh view (paste the
condition only if not already inside 2.2).

2.7 Does `refresh_dashboard_api` call
`UserManifestManager.update_dashboard_pointer`? yes/no + cite.

---

## 3. `views.py` — serving-view HTML injection

For each of `user_dashboard_detail`, `community_dashboard_detail`,
`observatory_dashboard_detail` (or current names):

3.1 Paste the blocks that inject any of:
`PRISM_TEMPLATE_HASH`, `PRISM_VIEWER`, `PRISM_DASHBOARD_AUTHOR`,
`PRISM_DASHBOARD_SHARED`, `PRISM_IS_OBSERVATORY`, `data_url`,
`presence_url`, `live_refresh_seconds`, `api_url` / refresh URL,
`kerberos`, `dashboard_id`.

3.2 If injection lives in templates instead, paste template path + the
relevant fragment.

3.3 One-line ACL note per detail view: who can open it, and whether
share-token viewers can hit `/api/dashboard/data/` and
`/api/dashboard/refresh/`.

---

## 4. `entrypoint.py` — `site` + scheduled full walk

4.1 Paste the CLI definition for the `site` command (click/typer/argparse
— whichever is live), including every flag (`--port`,
`--no-open-refresh`, `--open-interval`, etc.). If a flag is ABSENT, say
so.

4.2 Paste `_run_site` (or current name) in full — especially child
process spawn + shutdown.

4.3 Does `site` currently spawn `jobs/hourly/refresh_dashboards.py`?
yes/no. If yes, paste the **exact argv list**. State whether `--interval`
and/or `--open-interval` appear.

4.4 Paste every call site that invokes `refresh_dashboards.main` /
`jobs/hourly/refresh_dashboards.py` / the 15-minute / five-minute
context generator group. Include function names + sleep/interval
constants.

4.5 Confirm: is there today any process that light-refreshes only
open/presence-fresh dashboards? yes/no + evidence (must cite
`entrypoint.py` or a job file).

---

## 5. Gap checklist (fill from THIS read only)

| Question | Answer (yes/no/unknown) | Evidence (`path:line`) |
|---|---|---|
| `urls.py` registers `/api/dashboard/presence/`? | | |
| `views.py` defines `dashboard_presence_api`? | | |
| `refresh_dashboard_api` forwards body `mode` into runner argv? | | |
| Default mode when body omits `mode`? (`light` / `full` / n/a) | | |
| Installed runner accepts `--mode light\|full`? | | |
| `entrypoint.py site` spawns `--open-interval` alone? | | |
| `entrypoint.py site` still spawns a full `--interval` walk? | | |
| `site --no-open-refresh` exists? | | |
| Serving views inject `PRISM_TEMPLATE_HASH`? | | |
| Any server-side open-tab presence index consumer outside staging docs? | | |

---

## Could not resolve

List any subsection blocked, with what you tried.
