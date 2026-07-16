---
class: context-extraction
topic: django-entrypoint-refresh-visibility
status: FOLDED
created: 2026-07-16
reply_received: 2026-07-16
reply_source: cursor-chat screenshots (25 images, 14:50–14:53 ET)
folded_on: 2026-07-16
checkout:
  prism_main_HEAD: a9dfe6c
  prism_core_HEAD: 9a27923
file_identities:
  urls.py: {bytes: 11052, lines: 176, sha256: e61d8162dbf3a2bc1e0d5e909b417a484f404c5c5958bfc2a7d9ee0305302da6}
  views.py: {bytes: 269772, lines: 6856, sha256: a99b366983d0471a1b49f458d8068dd8644340430ba8d00622eb35937c548b6e}
  entrypoint.py: {bytes: 94755, lines: 2317, sha256: a1a3cd1fb6ef7ca91ac0ccb9ceb782e1817602fb1111283dbfec73de83e2e83b}
reply_folded_into:
  - prism/dashboard-refresh.md
  - prism/dashboards-portal.md
  - prism/_changelog.md
supersedes_gap_from:
  - staging/prompts/archive/2026-07-16_light_refresh_open_presence.md
---

# Context-extraction prompt — verbatim `views.py` / `urls.py` / `entrypoint.py`

**Folded 2026-07-16.** Live reply confirmed the parent-tree wire that
morning extraction still listed as GAP:

| Checklist item | Live answer |
|---|---|
| `/api/dashboard/presence/` registered | yes (`urls.py:70`) |
| `dashboard_presence_api` defined | yes (`views.py:5544-5638`) |
| refresh forwards body `mode` → `--mode` | yes (default `light`) |
| runner accepts `--mode light\|full` | yes (default `full`) |
| `site` spawns `--open-interval` alone | yes (no `--interval`) |
| `site --no-open-refresh` | yes |
| `PRISM_TEMPLATE_HASH` injected | yes (`_inject_prism_globals`) |

The two END-USAGE patch prompts
(`django_light_refresh_presence_wire`, `entrypoint_site_open_refresh`)
are superseded by this live state.

Original paste body retained below for audit only.

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
