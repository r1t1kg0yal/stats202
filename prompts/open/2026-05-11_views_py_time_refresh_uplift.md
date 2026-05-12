---
session: views.py time + refresh + reloading uplift -- the PRISM-side half of the live-auto-refresh + time-handling architecture
sent: 2026-05-11
class: implementation-directive (NOT context-extraction; NOT end-usage)
preconditions:
  - The echarts payload v2 time uplift has already landed via drag-and-drop. Specifically `ai_development/dashboards/time.py` exists (canonical helpers `parse_iso` / `format_iso` / `is_stale` / `format_pill` / `freq_delta` / `utcnow`); `ai_development/dashboards/echart_dashboard.py::build_dashboard()` re-stamps `metadata.time.{data_domain_end,data_domain_freq,pull_completed_at,build_completed_at}` on every build and keeps `metadata.data_as_of` / `metadata.generated_at` as back-compat aliases; `ai_development/dashboards/echart_dashboard.py::_resolve_chart_specs(manifest, base_dir, diags)` is callable from outside the engine; `ai_development/dashboards/rendering.py::DASHBOARD_APP_JS` has the `applyLiveData()` + `pollLiveData()` poll loop wired and reads `window.PRISM_TEMPLATE_HASH` for structural-change detection.
files_to_modify:
  - ai_development/mysite/news/urls.py (add 1 path entry for the data endpoint)
  - ai_development/mysite/news/views.py (add `dashboard_data_api()` view; add `template_hash` injection to all dashboard-serving views; rewrite `refresh_status_api` auto-heal via canonical time helpers; route `_get_user_dashboards()` display formatting + `_format_last_run()` through canonical time helpers; remove every `datetime.utcnow()` (naive))
reply_folded_into:
  - confirmation back to staging (post-impl) so `prism/dashboard-refresh.md` and `prism/dashboards-portal.md` can absorb the new endpoint + injection contract; staging-side `projects/echarts/dev/notes.md` "Track 4 -- PRISM-side integration contract" closes one row.
status: pending
---

Title: views.py time + refresh + reloading uplift -- close the PRISM-side half of the live-auto-refresh + time-handling architecture

The echarts payload v2 time uplift has already landed -- the engine
now stamps `metadata.time.*` on every build, the chrome JS is wired
to swap datasets in place via a `pollLiveData()` loop, and the
canonical `dashboards/time.py` module gives every consumer one
parser/formatter pair to route through. This prompt closes the
PRISM-side half of that architecture: a new data endpoint to feed
the live-refresh loop, template-hash injection so the loop can
detect structural changes, and a sweep through `views.py` to remove
every ad-hoc datetime parser and silent timezone bug.

Six concrete things change inside `ai_development/mysite/news/`:

  1. **NEW endpoint** `GET /api/dashboard/data/` -- returns the live
     dataset payload + lowered chart specs + metadata + a
     `manifest_template_hash`. The chrome JS poll loop hits this
     every 60s (default) with `If-None-Match: <last_refreshed>` and
     replaces the page-level `location.reload()` UX.
  2. **`urls.py` route** for the new endpoint.
  3. **Template hash injection** in every dashboard-serving view
     (`user_dashboard_detail`, `community_dashboard_detail`,
     `observatory_dashboard_detail`, plus any `public_user_*` /
     `developer_*` variants that exist) so the served HTML carries
     `window.PRISM_TEMPLATE_HASH`.
  4. **`refresh_status_api` auto-heal** -- replace the
     naive-`datetime.utcnow()` path with `is_stale()` from the
     canonical time module. Closes the silent timezone bug
     described in `scans/prism/2026-05-11_dashboard_live_refresh_and_time.md`
     \u00a73 #8.
  5. **`_get_user_dashboards()` display formatting** -- route
     through `parse_iso` + an ET pretty-print so the
     `last_refreshed_display` field stops drifting between Z and
     `+00:00` ISO dialects.
  6. **`_format_last_run()` scheduled-process timestamps** --
     route through the canonical helpers and add an explicit
     timezone label so the user can read the pill at a glance.

Reply with:

  - a single `## Confirmation` block at the end listing the file:line
    ranges actually edited (and any helper-function names you added
    or renamed), plus a 1-line summary per change.
  - a `## Frictions` section IF anything in this spec did not apply
    cleanly (e.g. an existing `_inject_prism_globals` shape that
    differs from what \u00a74 assumes, an existing `dashboard_data_api`
    placeholder, an existing canonical time module that already
    exists at a different import path, etc.). No friction = no
    section.

This is an **implementation directive**, not a context-extraction
prompt. Do not paste signatures or docstrings back; edit the files,
confirm what changed, surface any frictions.

---

## 1. NEW: `dashboard_data_api()` view body

Add this view to `ai_development/mysite/news/views.py`. Drop it
near the other `/api/dashboard/*` views (next to
`refresh_dashboard_api` / `refresh_status_api`). Approx 80 LOC.

```python
@csrf_exempt
def dashboard_data_api(request):
    """Return the live dataset payload for a dashboard.

    Powers the chrome's live-refresh loop in `dashboards/rendering.py`
    (DASHBOARD_APP_JS::pollLiveData). Returns the same shape the
    in-page PAYLOAD.datasets / PAYLOAD.specs carry (fresh on every
    call), plus a lightweight metadata block (data_as_of, summary,
    methodology, time.*) and a manifest_template_hash. The hash
    lets the browser detect structural changes (new widget / tab /
    filter) and fall back to a full page reload in that case.

    GET params (required):
      - dashboard_id : str
      - kerberos     : str (the OWNER kerberos; viewer auth is
                       enforced separately below)

    ACL (mirrors the dashboard-serving views):
      - god-mode users: see anything
      - authors:        see their own
      - everyone else:  need shared=True on the dashboard

    ETag: `last_refreshed` from the registry. A 304 with no body is
    returned when the client's If-None-Match matches; this is the
    gating mechanism for the polling loop (most polls 304).
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required'}, status=405)

    viewer = get_kerberos(request)
    if not viewer:
        return JsonResponse({'error': 'Authentication required'}, status=403)

    owner        = request.GET.get('kerberos') or viewer
    dashboard_id = request.GET.get('dashboard_id')
    if not dashboard_id:
        return JsonResponse({'error': 'dashboard_id required'}, status=400)

    # ACL: viewer must be the owner, OR the dashboard must be shared,
    # OR the viewer must be in the god-mode allowlist. Mirrors the
    # dashboard-serving views' policy exactly.
    from ai_development.core.s3_bucket_manager import s3_manager
    registry_path = f"users/{owner}/dashboards/dashboards_registry.json"
    try:
        raw      = s3_manager.get(registry_path)
        registry = json.loads(raw.rstrip(b'\x00').decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Dashboard not found'}, status=404)

    entry = next(
        (d for d in registry.get('dashboards', []) if d.get('id') == dashboard_id),
        None,
    )
    if entry is None:
        return JsonResponse({'error': 'Dashboard not found'}, status=404)

    if owner != viewer:
        if not entry.get('shared', False):
            allowed = _get_prism_users()
            if not (allowed and viewer in allowed):
                return JsonResponse({'error': 'Dashboard not found'}, status=404)

    # ETag short-circuit. The registry's last_refreshed is the
    # canonical "data freshness" pointer; no need to re-read manifest.
    last_refreshed = entry.get('last_refreshed') or ''
    if_none_match  = (request.META.get('HTTP_IF_NONE_MATCH') or '').strip('"')
    if last_refreshed and if_none_match == last_refreshed:
        return HttpResponse(status=304)

    folder        = entry.get('folder') or f"users/{owner}/dashboards/{dashboard_id}"
    manifest_path = f"{folder}/manifest.json".replace('//', '/')
    template_path = f"{folder}/manifest_template.json".replace('//', '/')

    try:
        manifest = json.loads(s3_manager.get(manifest_path).rstrip(b'\x00').decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Dashboard manifest not found'}, status=404)

    # Re-resolve chart specs (lowering spec={chart_type, mapping, ...}
    # widgets into the ECharts option dicts the JS poll loop assigns
    # into SPECS[cid]). Same function compile_dashboard calls; safe
    # against per-widget failure (it captures into diags and
    # substitutes a placeholder option so siblings still resolve).
    from ai_development.dashboards.echart_dashboard import _resolve_chart_specs
    specs = _resolve_chart_specs(manifest, base_dir=None, diags=[])

    # Template hash: gates the chrome's reload-vs-swap decision.
    try:
        template_bytes = s3_manager.get(template_path)
        template_hash  = hashlib.sha256(template_bytes).hexdigest()
    except Exception:
        template_hash = None

    response = JsonResponse({
        'ok':                      True,
        'datasets':                manifest.get('datasets', {}),
        'specs':                   specs,
        'metadata':                manifest.get('metadata', {}),
        'manifest_template_hash':  template_hash,
        'last_refreshed':          last_refreshed,
        'last_refresh_status':     entry.get('last_refresh_status'),
    })
    if last_refreshed:
        response['ETag'] = f'"{last_refreshed}"'
    return response
```

If `hashlib` / `json` / `JsonResponse` / `HttpResponse` /
`get_kerberos` / `_get_prism_users` are not already imported at
the top of `views.py`, add the imports they need.

---

## 2. urls.py route

Add to `ai_development/mysite/news/urls.py`, alongside the existing
`api/dashboard/refresh/` and `api/dashboard/refresh/status/` paths:

```python
path('api/dashboard/data/', views.dashboard_data_api, name='dashboard_data_api'),
```

Order doesn't matter; place it next to the other `api/dashboard/*`
patterns for grep-ability.

---

## 3. Template hash injection in dashboard-serving views

Every view that returns compiled `dashboard.html` from S3 must inject
the manifest-template hash into a fourth JS global so the chrome's
live-refresh loop can detect structural changes and fall back to
`location.reload()` instead of an in-place data swap.

The current `_inject_prism_globals(html, viewer, author, shared, is_observatory)`
helper produces:

```html
<script>
window.PRISM_VIEWER          = "{viewer_kerberos}";
window.PRISM_DASHBOARD_AUTHOR = "{owner_kerberos}";
window.PRISM_DASHBOARD_SHARED = {shared};
window.PRISM_IS_OBSERVATORY  = {is_observatory};
</script>
```

### 3.1 Update `_inject_prism_globals` signature

Add a `template_hash: str | None = None` kwarg to the helper, and
emit one extra line into the injected script:

```html
window.PRISM_TEMPLATE_HASH   = {template_hash};
```

Use `json.dumps(template_hash)` so `None` becomes JS `null` and the
viewer-side guard `LAST_KNOWN_TEMPLATE_HASH = (typeof window.PRISM_TEMPLATE_HASH !== 'undefined') ? window.PRISM_TEMPLATE_HASH : null;` falls through cleanly when an old served HTML lacks the field.

### 3.2 Per-view `template_hash` computation

In each dashboard-serving view, compute the hash from
`manifest_template.json` BEFORE injection. The pattern:

```python
import hashlib

template_path = f"{folder}/manifest_template.json".replace('//', '/')
try:
    template_hash = hashlib.sha256(s3_manager.get(template_path)).hexdigest()
except Exception:
    template_hash = None

html = _inject_prism_globals(
    html, viewer=viewer, author=author,
    shared=shared, is_observatory=is_observatory,
    template_hash=template_hash,                          # NEW
)
```

Apply this to EVERY view that calls `_inject_prism_globals` today:

  - `user_dashboard_detail`        (`folder = users/{viewer}/dashboards/{dashboard_id}`)
  - `community_dashboard_detail`   (`folder = users/{author}/dashboards/{dashboard_id}`)
  - `observatory_dashboard_detail` (`folder = secondary/prism_observations/dashboards/{dashboard_id}`)
  - any `public_user_dashboard_detail` / `developer_dashboard_detail`
    variant that exists -- enumerate by grepping for
    `_inject_prism_globals(` and ensure every call site passes
    `template_hash=`.

If `_inject_prism_globals` doesn't exist as a helper in the live
codebase (each view inlines the `<script>` injection instead), add
the helper with the signature above and refactor each view to use it
in this same change. Less drift between views = fewer places to keep
in sync next time.

---

## 4. `refresh_status_api` -- route through `is_stale`

The current auto-heal block uses `datetime.utcnow()` (NAIVE) and
masks an aware-vs-naive `TypeError` only by accident -- per
`scans/prism/2026-05-11_dashboard_live_refresh_and_time.md` \u00a73 #8.
Replace the entire `if status_data.get("status") == "running":`
block with a call into the canonical time module:

```python
from ai_development.dashboards.time import is_stale, parse_iso, utcnow, format_iso

if status_data.get("status") == "running":
    started_at = status_data.get("started_at", "")
    pid        = status_data.get("pid")

    is_stale_lock = False
    stale_reason  = ""

    # Check 1: running for >10 minutes = stale (canonical 600s threshold).
    if is_stale(started_at, max_age_seconds=600):
        is_stale_lock = True
        age = (utcnow() - parse_iso(started_at)).total_seconds() if parse_iso(started_at) else None
        stale_reason  = f"Exceeded 10-minute timeout (age: {age:.0f}s)" if age is not None else "Exceeded 10-minute timeout"
    # Check 2: PID provided but process is dead.
    elif pid is not None:
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            is_stale_lock = True
            age = (utcnow() - parse_iso(started_at)).total_seconds() if parse_iso(started_at) else None
            stale_reason  = (f"Process {pid} is no longer running"
                             + (f" (age: {age:.0f}s)" if age is not None else ""))
    # Check 3: no PID after 30s = subprocess never started.
    elif pid is None and parse_iso(started_at):
        age = (utcnow() - parse_iso(started_at)).total_seconds()
        if age > 30:
            is_stale_lock = True
            stale_reason  = f"No PID after {age:.0f}s -- subprocess failed to start"

    if is_stale_lock:
        healed_status = {
            "status":       "error",
            "started_at":   started_at,
            "completed_at": format_iso(utcnow()),                # was: datetime.utcnow().isoformat() + "Z"
            "errors":       [f"Auto-healed stale lock: {stale_reason}"],
            "pid":          pid,
            "auto_healed":  True,
        }
        try:
            s3_manager.put(healed_status, status_path)
            logger.warning(
                "Auto-healed stale refresh status for %s/%s: %s",
                kerberos, dashboard_id, stale_reason,
            )
        except Exception:
            pass  # Best-effort healing
        return JsonResponse(healed_status)
```

The behavioural contract is unchanged (10-minute timeout, dead-PID
check, no-PID-after-30s check, healed JSON shape). The wins:

  - `is_stale()` parses Z-suffix and `+00:00` ISO dialects identically
    via `parse_iso()`; no more `.rstrip("Z")` strip-and-naive-reparse.
  - No `datetime.utcnow()` in the body; `utcnow()` from the canonical
    module returns aware UTC.
  - `format_iso()` emits `+00:00` consistently with what
    `refresh_runner.py::_utcnow_iso` writes (the runner emits Z to
    match registry-historical entries; the canonical module accepts
    both and normalises emit to `+00:00` going forward).

---

## 5. `_get_user_dashboards()` -- route display formatting through canonical helpers

The current body uses ad-hoc `datetime.fromisoformat(raw_ts.rstrip("Z")).replace(tzinfo=ZoneInfo("UTC"))`
which silently falls back to `raw_ts[:16]` when the string emits
`+00:00` instead of Z. Replace the per-dashboard timestamp loop:

```python
def get_user_dashboards(kerberos):
    """Read dashboard registry from S3, return list of dashboard config dicts."""
    from ai_development.dashboards.time import parse_iso
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("US/Eastern")

    try:
        from ai_development.core.s3_bucket_manager import s3_manager
        registry_path = f"users/{kerberos}/dashboards/dashboards_registry.json"
        raw      = s3_manager.get(registry_path)
        registry = json.loads(raw.rstrip(b'\x00').decode('utf-8'))
        dashboards = registry.get("dashboards", [])
        for dash in dashboards:
            raw_ts = dash.get("last_refreshed", "")
            dt = parse_iso(raw_ts)
            if dt is not None:
                dash["last_refreshed_display"] = dt.astimezone(ET).strftime("%b %d, %Y %H:%M") + " ET"
            else:
                dash["last_refreshed_display"] = raw_ts[:16] if raw_ts else ""
        return dashboards
    except Exception:
        return []
```

Behaviour identical for valid Z-suffix; now also identical for
`+00:00`-suffix and naive ISO. The fallback string-slice path stays
as the last-ditch in case `parse_iso` returns `None` for genuinely
malformed input.

---

## 6. `_format_last_run()` -- canonical helpers + explicit timezone label

The scheduled-process formatter today calls
`datetime.fromisoformat(last_run_iso.replace('Z', '+00:00'))` and
formats with `%I:%M %p` (12-hour) without a timezone label, so the
user can't tell whether the time is local, UTC, or ET. Route
through the canonical module and stamp the timezone:

```python
def _format_last_run(last_run_iso):
    """Format a scheduled-process last_run timestamp for display."""
    from ai_development.dashboards.time import parse_iso
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("US/Eastern")

    dt = parse_iso(last_run_iso)
    if dt is None:
        return ""
    return dt.astimezone(ET).strftime("%b %d, %Y %I:%M %p ET")
```

If there are other ad-hoc datetime parsers elsewhere in `views.py`
(grep for `datetime.fromisoformat` and `.replace("Z"`), route them
through `parse_iso` / `format_iso` / `is_stale` from
`ai_development.dashboards.time` in the same change. The goal is
zero callers reinventing ISO parsing inside `views.py`.

---

## 7. Audit + cleanup pass

After the six edits above land, do one grep pass and surface any
residue:

  - `rg "datetime\.utcnow\(\)" ai_development/mysite/news/views.py`
    -- expected hit count after edits: **0**. Every prior call site
    should be using `utcnow()` from the canonical module (which
    returns aware UTC) or `format_iso(utcnow())` for ISO emit.
  - `rg "fromisoformat" ai_development/mysite/news/views.py`
    -- expected hit count after edits: **0** (every ISO parse goes
    through `parse_iso`).
  - `rg "_inject_prism_globals\(" ai_development/mysite/news/views.py`
    -- every call site must pass `template_hash=`.

Surface any remaining hits in the `## Frictions` section so we know
to chase them in a follow-up.

---

## 8. What this buys us (after this change + the staging-side payload uplift)

  - The chrome's live-refresh loop has a working endpoint to hit; the
    polling loop swaps datasets in place every 60s without ever
    reloading the page. Filters, dataZoom slider, dark mode, table
    sort all survive cron-driven data updates.
  - Structural changes (new widget / tab / filter) trigger one clean
    `location.reload()` via the template-hash mismatch path; no
    confusion between "data changed" and "structure changed."
  - The "Data as of 2026-03-31 00:00:00 UTC" lie disappears: the
    chrome reads `metadata.time.refresh_cycle_at` (cron tick wall
    time) for the secondary, and the build-stamped
    `metadata.time.data_domain_end` for the primary, formatted
    via the Python-side `format_pill()` helper so JS isn't doing
    timezone math.
  - Every `views.py` consumer of timestamps routes through one
    parser/formatter pair. The silent timezone bug in
    `refresh_status_api` (\u00a74) goes away. Display drift in
    `_get_user_dashboards` and `_format_last_run` goes away.

The echarts payload v2 time uplift (engine + chrome JS + canonical
time module + payload pull-helper sidecar stamping) is the
prerequisite -- this prompt closes the PRISM-side half (the data
endpoint + template-hash injection + the views.py time helpers).
The two halves together complete the full uplift of time + refresh
+ reloading.
