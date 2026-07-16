---
class: end-usage
topic: django-light-refresh-presence-wire
status: SUPERSEDED
created: 2026-07-16
superseded_on: 2026-07-16
superseded_by: staging/prompts/archive/2026-07-16_django_entrypoint_refresh_visibility.md
depends_on:
  - staging/prompts/archive/2026-07-16_light_refresh_open_presence.md
prerequisite_payload:
  - prism-core/dashboards/refresh_runner.py  # must accept --mode light|full
  - prism-core/dashboards/echart_dashboard.py  # record_open_presence, list_open_dashboards, build_dashboard_data_only
  - prism-core/dashboards/refresh_dashboards.py  # --open-interval (jobs/hourly copy)
  - prism-core/dashboards/rendering.py  # POSTs mode=light + presence heartbeat
---

# PRISM patch prompt — wire light refresh + open-tab presence in Django

**SUPERSEDED 2026-07-16.** Afternoon visibility extraction confirmed
presence route, `mode`→`--mode` forward (default `light`), and
`dashboard_presence_api` are already LIVE on `prism-main` `a9dfe6c`.
Do not re-apply this patch. Retained for audit only.

**Why this exists (staging-side note; do not paste this section into
PRISM):**

Staging already shipped the echarts payload half:

- `refresh_runner.py --mode light|full`
- `build_dashboard_data_only` / `light_refresh` / `record_open_presence`
- chrome POSTs `{mode: "light"}` and heartbeats `/api/dashboard/presence/`

Live Django (as of 2026-07-16 introspection) still:

- ignores `mode` and always spawns a full compile refresh
- has no `/api/dashboard/presence/` route

This prompt is the exact PRISM-side patch list. **Prerequisite:** drop
the updated `echarts-payload` into `prism-core/dashboards/` (and
`refresh_dashboards.py` into `jobs/hourly/`) before applying these
Django edits, or `--mode` / `record_open_presence` will not resolve.

---

## Paste the following into PRISM

# Implement Django light-refresh + open-tab presence wiring

You are being asked to apply a bounded Django patch so the staged
echarts chrome contracts work in production. This is an **end-usage /
implementation** request: edit the live files named below.

**Prerequisite (verify first, do not skip):**

1. `prism-core/dashboards/refresh_runner.py` argparse accepts
   `--mode` with choices `full` and `light` (default `full`).
2. `from dashboards import record_open_presence` imports cleanly.
3. Installed `rendering.py` chrome POSTs
   `{"kerberos", "dashboard_id", "mode": "light"}` to
   `/api/dashboard/refresh/` and POSTs presence to
   `/api/dashboard/presence/`.

If any prerequisite fails, stop and report which file is stale. Do not
invent a parallel light path inside Django.

As you come into Frictions, document and let me know what those
Frictions are.

## Non-goals

- Do not change `dashboard_data_api` (already correct).
- Do not change refresh ACL (still allowlist; share tokens still cannot
  POST refresh).
- Do not rewrite telemetry into a presence system.
- Do not change the 15-minute full walk default for cold HTML.
- Do not edit echarts payload files in this pass unless a prerequisite
  is missing and you must report that.

---

## Change 1 — `web/backend_django/news/urls.py`

Find the existing dashboard API routes (near
`path('api/dashboard/data/', ...)` and
`path('api/dashboard/refresh/', ...)`).

**Add** (same style as siblings):

```python
path(
    'api/dashboard/presence/',
    views.dashboard_presence_api,
    name='dashboard_presence_api',
),
```

Place it next to the telemetry / refresh routes. Do not rename existing
routes.

---

## Change 2 — `web/backend_django/news/views.py` :: `refresh_dashboard_api`

### 2.1 Read `mode` from the JSON body

After parsing the POST body for `kerberos` / `dashboard_id`, add:

```python
mode = (data.get("mode") or "light")
if not isinstance(mode, str):
    return JsonResponse({"error": "mode must be a string"}, status=400)
mode = mode.strip().lower()
if mode not in ("light", "full"):
    return JsonResponse(
        {"error": "mode must be 'light' or 'full'"},
        status=400,
    )
```

Default is **`light`** when omitted (browser Refresh path). Cron /
`launch_clean_refresh` keep spawning `--mode full` and do not go through
this view.

### 2.2 Forward `mode` into the runner argv

Today the spawn looks like:

```python
proc = subprocess.Popen(
    [sys.executable, refresh_runner_path,
     '--folder', dashboard_folder.rstrip('/'),
     '--log-path', log_key],
    start_new_session=True,
    stdout=pipe_w,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    cwd=repo_root,
    env=env,
)
```

**Change argv to:**

```python
proc = subprocess.Popen(
    [sys.executable, refresh_runner_path,
     '--folder', dashboard_folder.rstrip('/'),
     '--log-path', log_key,
     '--mode', mode],
    start_new_session=True,
    stdout=pipe_w,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    cwd=repo_root,
    env=env,
)
```

Keep every other spawn detail identical (`cwd=REPO_ROOT`,
`start_new_session=True`, `PRISM_SUBPROCESS_S3_FOLDER_KEY`, S3 log
streamer, stale-lock / 409 logic, registry existence check, auth).

### 2.3 Include `mode` in the start response (optional but useful)

When returning `{status: "refreshing", pid: ...}`, also include
`"mode": mode` so triage can see which path was launched.

Do **not** call `update_dashboard_pointer` from this view (ownership
unchanged).

---

## Change 3 — `web/backend_django/news/views.py` :: new `dashboard_presence_api`

Add a new view next to `dashboard_telemetry_api` / refresh views.

### Contract

| Item | Value |
|---|---|
| Method | POST only (405 otherwise) |
| Path | `/api/dashboard/presence/` |
| Auth | `get_kerberos(request)` required (403 if missing) |
| Body JSON | `{kerberos, dashboard_id, viewer?}` |
| Success | `200 {"ok": true, "presence": {...}}` |

### Semantics

1. Authenticate viewer via `get_kerberos`.
2. Parse JSON body. Require non-empty `dashboard_id` (400 if missing).
3. Resolve owner folder:
   - Prefer body `kerberos` as the dashboard owner when present and the
     viewer is allowed to heartbeat that dashboard.
   - ACL: allow if `viewer == owner` OR god-mode OR the dashboard is
     readable under the same rules as `dashboard_data_api` (owner /
     public / link-token if you already have share on the request).
   - If the viewer is not allowed, return **404** with a generic
     "Dashboard not found" (same non-leak style as the data API).
4. Confirm the dashboard exists in
   `users/{owner}/dashboards/dashboards_registry.json`.
5. Call:

```python
from dashboards import record_open_presence

folder = f"users/{owner}/dashboards/{dashboard_id}".rstrip("/")
presence = record_open_presence(
    folder,
    viewer=(data.get("viewer") or viewer),
)
return JsonResponse({"ok": True, "presence": presence})
```

6. Do **not** append to `console_log.jsonl`. Presence is not telemetry.
7. Wrap unexpected exceptions as `500 {"error": "..."}`.

### Minimal reference shape (adapt to local helpers / imports)

```python
@csrf_exempt  # only if sibling JSON POST dashboard APIs use it
def dashboard_presence_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    viewer = get_kerberos(request)
    if not viewer:
        return JsonResponse({"error": "Authentication required"}, status=403)
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "JSON body must be an object"}, status=400)

    dashboard_id = data.get("dashboard_id")
    if not isinstance(dashboard_id, str) or not dashboard_id.strip():
        return JsonResponse({"error": "dashboard_id required"}, status=400)
    dashboard_id = dashboard_id.strip()

    owner = data.get("kerberos") or viewer
    if not isinstance(owner, str) or not owner.strip():
        return JsonResponse({"error": "kerberos required"}, status=400)
    owner = owner.strip()

    # Reuse the same registry lookup + ACL style as dashboard_data_api
    # (owner / god-mode / public / link+share). On deny → 404.
    # ... insert your existing helper calls here ...

    folder = f"users/{owner}/dashboards/{dashboard_id}"
    try:
        from dashboards import record_open_presence
        presence = record_open_presence(
            folder,
            str(data.get("viewer") or viewer),
        )
    except Exception as exc:
        return JsonResponse(
            {"error": f"{type(exc).__name__}: {exc}"},
            status=500,
        )
    return JsonResponse({"ok": True, "presence": presence})
```

Mirror `@csrf_exempt` / auth decorator patterns from
`refresh_dashboard_api` / `dashboard_telemetry_api` — do not invent a
new auth stack.

---

## Change 4 — optional but recommended: open-tab light orchestrator

File: `jobs/hourly/refresh_dashboards.py` (parent tree; must match the
staged payload that already has `--open-interval`).

After the updated payload is dropped:

1. Confirm CLI accepts `--open-interval N` and `--open-once`.
2. Wire production activation so open dashboards get light refresh while
   viewed. Preferred shapes (pick what matches your procmon layout):

```text
# A) Daemon alongside the 15-minute full walk
python jobs/hourly/refresh_dashboards.py --interval 900 --open-interval 60

# B) Separate frequent one-shot (if you cannot run a daemon)
python jobs/hourly/refresh_dashboards.py --open-once
# invoke every ~60s from procmon / entrypoint
```

The existing 15-minute / hourly **full** walk must keep calling
`launch_clean_refresh(folder)` with default `mode="full"` (or omit
mode). Do **not** convert the cold-HTML walk to light.

If you cannot change activation in this pass, implement Changes 1–3
only and report Change 4 under Frictions as "activation pending".

---

## Change 5 — do NOT touch (confirmation)

| File / surface | Leave alone |
|---|---|
| `dashboard_data_api` | Already serves datasets/specs + ETag |
| `_inject_prism_globals` | Already injects `PRISM_TEMPLATE_HASH` |
| Developer refresh route | In-process generators; unrelated |
| Telemetry route | Keep append-only console log |

---

## Verification (run after edits)

Report results for each:

1. **Argparse:**  
   `python prism-core/dashboards/refresh_runner.py --help`  
   shows `--mode {full,light}`.

2. **Light spawn (dry read):**  
   In `refresh_dashboard_api`, confirm the Popen argv list includes
   `'--mode', mode` with `mode` from the body.

3. **Route:**  
   `urls.py` registers `api/dashboard/presence/` →
   `dashboard_presence_api`.

4. **Presence write:**  
   POST `/api/dashboard/presence/` with a real owned dashboard body
   `{kerberos, dashboard_id, viewer}` → `200 {"ok": true, ...}` and
   S3 key `secondary/dashboard_open_presence/index.json` contains the
   folder.

5. **Button path:**  
   Open an owned dashboard, click Refresh → status becomes `success`
   without rewriting `dashboard.html` (compare S3 ETag/size or mtime of
   `dashboard.html` before/after; `manifest.json` and registry
   `last_refreshed` must change). Then confirm the page updates via
   `/api/dashboard/data/` without full reload.

6. **Open path (if Change 4 landed):**  
   Keep a tab open → presence heartbeats → within ~60–90s a light
   refresh runs for that folder only.

---

## Reply format

1. **Prerequisite check** — pass/fail per file.
2. **Diff summary** — files touched + what changed (paths + brief).
3. **Verification** — results for steps 1–6 above.
4. **## Frictions** — anything that blocked a clean wire-up
   (missing payload drop, ACL helper ambiguity, csrf pattern mismatch,
   open-interval activation unknown, etc.).
