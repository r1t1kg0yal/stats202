# Explainer: Stage 2 component drag on prism-main

Paste this into a fresh Cursor session opened against the **PRISM
working tree** (`prism-main/`). The ECharts payload half is already
done in staging; this document is only the PRISM web/backend work.

Companion (full contract + history):

`projects/echarts/dev/handoffs/2026-07-18_dashboard_component_composer_drag.md`

---

## Status of the ECharts half (already shipped in staging)

Canonical file:

`projects/echarts/echarts-payload/rendering.py`

What landed:

```text
1. window.DASHBOARD.widgets = WIDGET_META
2. document event prism:dashboard:ready
   (once, after initTools(), detail.dashboard = window.DASHBOARD)
3. no Composer literals in rendering.py
4. tests: TestDashboardComponentReadyHook
5. gallery: projects/echarts/dev/_gallery_component_ready_hook.py
```

Promote `rendering.py` into `prism-core/dashboards/rendering.py` (or
whatever the live dashboards package path is) **before or with** the
PRISM leaf work below. Without that promote, `dashboard_composer.js`
will wait forever for `prism:dashboard:ready` / missing `widgets`.

Stable DOM already present (no further ECharts work needed):

```text
[data-tile-id="<widget-id>"]
  chart / table / data_grid / pivot / stat_grid  -> .tile-header
  kpi                                            -> .kpi-header
```

---

## Mission on prism-main

```text
owner drags one rendered dashboard component by its header
  -> standard Composer attachment card
  -> /api/composer/artifact-info/ enriches the pointer
  -> fire-off / chat gets one compact reference line
```

Read-only component reference. Do **not** add manifest mutation,
layout editing, screenshots, HTML attachments, dataset rows, or
Stage 3 operations (`describe_dashboard`, `apply_manifest_operations`,
`review_dashboard`, `publish_dashboard`, `launch_clean_refresh`).

---

## Files to inspect first (live bodies, not screenshots)

```text
web/backend_django/news/dashboard_composer.py
web/backend_django/news/views.py
web/backend_django/news/composer_artifacts.py
web/backend_django/news/composer_email.py
web/prism_site/js/dashboard_composer.js
web/prism_site/js/composer.js
web/prism_site/css/composer.css
```

Stage 1 already mounts Composer on served user dashboards via
`inject_dashboard_composer(html)` from
`public_user_dashboard_detail`. Observatory / developer views stay
excluded. Do not rewrite the dashboard inline-chat force-off
(`PRISM_COMPOSER_INLINE_CHAT=false`) while doing this work.

Ignore unrelated dirty trees:

- `core/configs/access_control_lists.py`
- `prism-core/prism_mcp/utils/skill_crud_functions.py`

If `dashboard_composer.py` / `dashboard_composer.js` show empty staged
blobs, re-stage the real working-tree content before committing.

---

## Architecture (PRISM leaf only)

```text
┌─────────────────────────────────────────────────────────────┐
│ promoted rendering.py (ECharts)                             │
│   widgets + prism:dashboard:ready                           │
└──────────────────────────┬──────────────────────────────────┘
                           │ event
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ dashboard_composer.js                                       │
│   owner check + allowlist + header drag                     │
│   emit application/x-prism-artifact                         │
└──────────────────────────┬──────────────────────────────────┘
                           │ drop
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ composer.js                                                 │
│   PRISM_COMPOSER_DND_MODE = dashboard_components            │
│   drop target on; upload off; generic sources off           │
│   accept dashboard_component -> normal card                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ artifact-info / fire-off / chat
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ composer_artifacts.py + composer_email.py                   │
│   owner/dashboard/widget/hash validate                      │
│   one reference line; attachment_paths = []                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Exact changes

### 1. Replace coarse DND boolean with an explicit mode

Today Stage 1 sets `PRISM_COMPOSER_DISABLE_DND = true`, which kills
drop target, upload, and generic source discovery together.

Replace with:

```javascript
window.PRISM_COMPOSER_DND_MODE
```

Semantics:

```text
standard
    drop target on, file upload on, generic source scan on

disabled
    drop target off, file upload off, generic source scan off
    (legacy Stage 1 read-only; keep as fallback if useful)

dashboard_components
    drop target on
    file upload off
    generic source scan off
    allowed artifact type: dashboard_component
```

Set `dashboard_components` in `dashboard_composer.py` injector and
`dashboard_composer.js` boot. Preserve Portal Composer on `standard`.
Prefer one mode enum over stacking more booleans. Migrate readers of
`PRISM_COMPOSER_DISABLE_DND` so dashboard pages stop using the coarse
flag.

### 2. Bind component drag in `dashboard_composer.js`

Two-latch startup (no polling):

```text
composerReady   <- composer.js load callback
dashboardReady  <- prism:dashboard:ready
bind once when both are true
```

On bind:

1. Require `PRISM_VIEWER === PRISM_DASHBOARD_OWNER`.
2. Read `event.detail.dashboard.widgets`.
3. Allow only: `chart`, `kpi`, `table`, `data_grid`, `pivot`, `stat_grid`.
4. Find `[data-tile-id="<id>"]`.
5. KPI -> `.kpi-header`; others -> `.tile-header`.
6. `draggable=true` on that header only; grab cursor/class only.
7. On `dragstart`, reject if origin is interactive:
   `button`, `a`, `input`, `select`, `textarea`, `[role="button"]`,
   `.tile-info`, toolbar/control affordances.
8. Write MIME `application/x-prism-artifact` with `effectAllowed="copy"`.

Do not modify ECharts chart/table/filter handlers. Do not add a second
card renderer here.

Browser payload:

```json
{
  "type": "dashboard_component",
  "id": "<widget_id>",
  "path": "users/<owner>/dashboards/<dashboard_id>",
  "label": "<dashboard title> · <widget title or label>",
  "widget_kind": "<chart|kpi|table|data_grid|pivot|stat_grid>",
  "template_sha256": "<window.PRISM_TEMPLATE_HASH>"
}
```

Derive owner / dashboard id / title / kind / hash from PRISM globals
+ `window.DASHBOARD`. Do not trust a client path that points at another
user folder as authority.

Non-owner served dashboards: Composer panel may stay mounted; component
handles must not bind.

### 3. Generic Composer (`composer.js`)

In `dashboard_components` mode:

- run `setupPanelDropTarget()`
- keep file input hidden
- skip `initDragSources()` and its body observer
- accept `dashboard_component`
- reuse optimistic card + artifact-info enrichment
- keep `standard` and `disabled` behavior exact

### 4. Backend resolver (`composer_artifacts.py`)

Extend shared `read_artifact_content(artifact, kerberos)` for
`dashboard_component`:

1. Authenticated `kerberos` must equal owner encoded by the folder.
2. Reconstruct `users/{kerberos}/dashboards/{dashboard_id}` server-side.
3. Read `manifest_template.json` bytes; SHA-256 must match
   `template_sha256` or return a typed stale-reference error.
4. Walk tabbed or flat layout; require exactly one matching widget id.
5. Kind must be in the six-kind allowlist.
6. Label/kind from server-read template.

Return:

```json
{
  "type": "dashboard_component",
  "label": "<dashboard> · <component>",
  "content_summary": "<one compact reference line>",
  "attachment_paths": [],
  "live_url": "/users/<owner>/dashboards/<dashboard_id>/",
  "s3_paths": []
}
```

Recommended prompt line:

```text
Dashboard component reference: dashboard=<dashboard_id>;
widget=<widget_id>; kind=<widget_kind>;
template_sha256=<sha>; manifest=users/<owner>/dashboards/<dashboard_id>/manifest_template.json
```

In `composer_email.py`, classify `dashboard_component` as reference-only
(never attach manifest or compiled HTML). Use the same resolver from
artifact-info, preview, fire-off, and chat. No new endpoint.

---

## Tests to add on prism-main

### JS

- `standard` / `disabled` / `dashboard_components` mode matrix
- bind waits for both latches; runs once
- only six kinds get handles; KPI uses `.kpi-header`
- interactive descendants do not start drag
- payload fields locked
- non-owner: Composer visible, no handles

### Backend

- valid owner/dashboard/widget/hash -> reference-only artifact
- missing widget / bad kind / bad id / cross-user / stale hash fail loud
- shared resolver across artifact-info, preview, fire-off, chat
- prompt has exactly one reference line
- `attachment_paths` and S3 lists empty; no mutations

### Browser smoke

1. Owned dashboard -> open Composer -> drag chart header -> card
2. Drag KPI via `.kpi-header` -> same card path
3. Chart controls / table sort still work (no accidental drag)
4. Fire-off -> inspect body for one reference line
5. Shared non-owner -> no handles
6. Stored `dashboard.html` still opens from `file://` with no Composer
   dependency (Composer is injector-only)

---

## Definition of done (PRISM side)

```text
[ ] rendering.py promoted so ready event + widgets exist in prod HTML
[ ] PRISM_COMPOSER_DND_MODE = dashboard_components on dashboard mount
[ ] owner-only eligible header binding
[ ] standard Composer card path
[ ] server-validated reference-only resolver
[ ] one prompt pointer line; no attachments / mutations
[ ] smoke: chart + KPI + table; non-owner clean; portable HTML intact
```

---

## Explicit non-goals

- Stage 3 typed-operation builder / layout DnD between tiles
- PNG / HTML / dataset attachments
- DashboardReview / PanelReceipt evidence in the card
- Changing site-wide inline-chat (`run.py`) or dashboard
  `PRISM_COMPOSER_INLINE_CHAT=false`
- Any Composer import inside ECharts payload files
