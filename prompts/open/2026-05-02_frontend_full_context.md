---
session: Frontend portal — full Django runtime introspection. mysite/ tree, settings.py, urls.py, base.html chrome, every major page-level template, every view function, S3 caching layer, image-asset architecture (logos / favicons / hero), Kerberos URL resolution, PAGE_ACCESS_RULES, existing CSS architecture (inline style block size + rule count). Explicitly DELTA-TRACKED against the 2026-05-02 portal source scan because the user has flagged that base.html and settings.py have moved since (esp. logo storage / referencing).
sent: 2026-05-02
reply: projects/frontend/dev/scans/2026-05-02_frontend_full_context_reply.md
reply_folded_into:
  - prism/frontend.md (CREATE — new curated doc covering Django runtime architecture, settings, mysite/ tree, all views, all templates, static-files wiring, S3 caching layer, image-asset architecture; cross-references prism/dashboards-portal.md for dashboard-specific viewing/sharing flows)
  - projects/frontend/frontend-payload/ (CREATE — payload skeleton: mysite/news/{views.py,urls.py,templates/news/} initially copied verbatim from PRISM, plus settings.py with STATICFILES_DIRS now SET, plus static/{css,js,images,fonts}/ scaffolding)
  - projects/frontend/ai_development/ (CREATE — stub mirror byte-identical to PRISM so the same payload runs identically here)
  - projects/frontend/dev/specs/inline_css_migration.md (DECIDE per the §10 quantification: standalone if base.html <style> block is >300 lines / >15 KB / >50 rules; folded into payload-creation iteration otherwise)
  - projects/frontend/dev/specs/design_system.md (delta-spec adjustments: §1.4 letter-spacing rules vs reality; §2 color tokens vs the actual hex/rgba in base.html; §6 component primitives vs what observation-card / hero / nav-dropdown etc. actually render today)
  - projects/frontend/README.md (status row → "scoping → scaffolded once payload skeleton lands")
  - staging/README.md (frontend row in lockstep)
  - prism/_changelog.md (entry: "frontend full-context introspection landed; prism/frontend.md created")
status: OPEN
---

Title: Frontend portal — full Django runtime context for staging-side scaffolding

The Cursor staging side has `projects/frontend/` in scoping with a v0
design system token spec at `projects/frontend/dev/specs/design_system.md`
(~840 lines), a fonts inventory landed via the 2026-05-02 fonts +
Python font-stack reply, and a verbatim portal source scan dated
2026-05-02 (~8,800 lines covering Django app structure / settings /
urls / views / templates / Flask report server). The next gating step
is **scaffolding `projects/frontend/frontend-payload/` and the stub
mirror at `projects/frontend/ai_development/`** so UI / template /
URL / sharing / CSS work can happen here with browser access and
Cursor vision on rendered snapshots, then drag-and-drop into PRISM
unchanged.

The 2026-05-02 portal scan is a structural baseline but **the user has
flagged that base.html and settings.py have moved since that scan,
especially around image-asset / logo paths**. Scaffolding against a
stale baseline would create drift the stub-mirror-parity invariant
will then fight against. So this round-trip is a **delta-tracked
re-introspection** plus **gap-fill on surfaces the 2026-05-02 scan
covered thinly** (S3 caching layer, image-asset architecture, inline
CSS quantification).

Use `list_ai_repo` (for verbatim source pulls) and
`execute_analysis_script` (for runtime introspection — file-system
walks, byte counts, regex matches across files, package versions,
S3 verifications). Reply with verbatim source in fenced code blocks
with language tags, exact paths, and **mirror the section structure
below** — each numbered section in your reply answers the
same-numbered section here, in order. No paraphrase, no summary, no
"based on my investigation" framing.

For every section the framing is **"what changed vs the 2026-05-02
capture, plus what was thin/missing then"**. If a surface is
unchanged, say so explicitly (`No delta vs 2026-05-02 scan §X`) and
move on — the staging side just needs the confirmation. If a surface
HAS changed, paste the current verbatim and call out the diff. If
a surface was missing/thin in the prior scan (notably §7 S3 caching
and §8 image-asset architecture), this round is the first
substantive capture.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried and
what blocked it. This is NOT a frictions report — it is a minimal
coverage note.

Approximate target reply size: ~3-6 KLOC of verbatim source +
introspection output. Don't compress; the staging side will distil.

---

## 1. `ai_development/mysite/` tree

### 1.1 Verbatim recursive listing

Run inside `execute_analysis_script`:

```python
import os
ROOT = "ai_development/mysite"
for dirpath, dirnames, filenames in os.walk(ROOT):
    rel = os.path.relpath(dirpath, ROOT)
    print(f"{'.' if rel == '.' else rel}/")
    for f in sorted(filenames):
        full = os.path.join(dirpath, f)
        try:
            sz = os.path.getsize(full)
        except OSError:
            sz = -1
        print(f"  {f}  ({sz} B)")
```

Paste the full stdout. Sort directories naturally; within a directory
sort filenames alphabetically. Include hidden files (dotfiles) if any.

### 1.2 Delta vs the 2026-05-02 portal scan

The 2026-05-02 portal scan (filed at
`projects/frontend/dev/scans/2026-05-02_portal_views_urls_templates.md`)
captured the following high-level shape:

```
mysite/
├── manage.py
├── mysite/                  (Django config app)
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── news/                    (the only Django app)
│   ├── urls.py
│   ├── context_processors.py
│   ├── views.py
│   └── templates/news/
│       ├── base.html
│       ├── home.html
│       ├── observations.html
│       ├── observation_detail.html
│       ├── dashboards.html
│       ├── dashboard_detail.html
│       ├── profile.html
│       ├── user_dashboards.html
│       ├── franchise.html
│       ├── doc_page.html
│       ├── article_detail.html
│       ├── access_denied.html
│       ├── whitepapers.html
│       ├── (user guides / faq / commentary / contact / about / report_detail)
├── fonts/                   (added 2026-05-02 — 20 GS Sans + GS Sans Condensed TTFs)
└── (no static/ directory at all — zero .css files; static_collected was not present)
```

After §1.1 finishes, in a short note: list every file/directory present
NOW that was NOT in the 2026-05-02 scan tree above, and every
file/directory that was THERE then but is gone now. One line each.

### 1.3 Static directories

Are any of the following present in the tree, and if so, list their
recursive contents (filename + bytes):

| Path                             | If present, paste contents (filename + bytes) |
|----------------------------------|-----------------------------------------------|
| `mysite/static/`                 |                                               |
| `mysite/news/static/`            |                                               |
| `mysite/news/static/news/`       |                                               |
| `mysite/staticfiles/`            |                                               |
| `mysite/static_collected/`       |                                               |
| `mysite/images/`                 |                                               |
| `mysite/news/images/`            |                                               |

Notably I want to know whether **any image asset** (logo, hero, favicon)
lives on disk under `mysite/`, and what its filename + path is — see
§8.

---

## 2. `mysite/mysite/settings.py` — verbatim + delta

### 2.1 Full verbatim

Paste the entire current contents of `ai_development/mysite/mysite/settings.py`
in a fenced `python` code block. Don't elide anything — even
boilerplate `INSTALLED_APPS` / `MIDDLEWARE` / `TEMPLATES` /
`AUTH_PASSWORD_VALIDATORS` / `LANGUAGE_CODE` blocks. The staging side
needs every line to byte-mirror.

### 2.2 Delta against the 2026-05-02 capture

The 2026-05-02 scan captured:

| Setting               | 2026-05-02 value                                          |
|-----------------------|-----------------------------------------------------------|
| `BASE_DIR`            | `Path(__file__).resolve().parent.parent`                  |
| `SECRET_KEY`          | `'django-insecure-!f749^z3xs8r34qwn))b5ub3lcljcd+9a38rqu_w&h&htgk*1'` |
| `DEBUG`               | `True`                                                    |
| `ALLOWED_HOSTS`       | `['10.69.246.111', 'localhost', '127.0.0.1', 'portal.prism-ai.url.gs.com', '10.69.245.42', 'reports.prism-ai.url.gs.com', 'irp-qa.usrates.site.gs.com', 'irpstqaam90971-063.dc.gs.com']` |
| `INSTALLED_APPS`      | django defaults + `'news'`                                |
| `MIDDLEWARE`          | django defaults — NO Kerberos middleware                  |
| `ROOT_URLCONF`        | `'mysite.urls'`                                           |
| `TEMPLATES.OPTIONS.context_processors` | django defaults + `'news.context_processors.nav_observations'` |
| `WSGI_APPLICATION`    | `'mysite.wsgi.application'`                               |
| `DATABASES.default.ENGINE` | `'django.db.backends.sqlite3'`                       |
| `LANGUAGE_CODE`       | `'en-us'`                                                 |
| `TIME_ZONE`           | `'UTC'`                                                   |
| `STATIC_URL`          | `'static/'`                                               |
| `STATICFILES_DIRS`    | NOT DEFINED                                               |
| `STATIC_ROOT`         | NOT DEFINED                                               |
| `STATICFILES_FINDERS` | NOT DEFINED                                               |
| `DEFAULT_AUTO_FIELD`  | `'django.db.models.BigAutoField'`                         |

After §2.1, produce a short delta note for any setting whose value has
changed, was added, or was removed. Format:

```
DELTA  STATIC_URL              '/static/'  (was 'static/')
ADDED  STATICFILES_DIRS        [BASE_DIR / 'static', BASE_DIR / 'fonts']
REMOVED  <none>
```

### 2.3 Other settings of interest

Even if absent, please confirm explicitly (NOT DEFINED) for each:

- `AUTH_USER_MODEL`
- `LOGIN_URL`
- `LOGOUT_URL`
- `SESSION_*` (`SESSION_ENGINE`, `SESSION_COOKIE_AGE`, `SESSION_COOKIE_SECURE`, …)
- `CSRF_*` (`CSRF_COOKIE_SECURE`, `CSRF_TRUSTED_ORIGINS`, …)
- `MEDIA_URL` / `MEDIA_ROOT`
- Any constant whose name contains `S3` / `BUCKET` / `IMAGE` / `LOGO` / `KERBEROS` / `GS_`
- Any custom logging config block
- Any environment variable read at module scope (`os.environ.get(...)`,
  `os.getenv(...)`)

### 2.4 manage.py + asgi.py + wsgi.py

Paste each of these three files verbatim if they have changed since
the 2026-05-02 scan — otherwise just confirm `No delta vs 2026-05-02
scan` and skip the body. The 2026-05-02 capture had:

- `manage.py` — Django boilerplate, `DJANGO_SETTINGS_MODULE = 'mysite.settings'`
- `mysite/wsgi.py` — Django boilerplate
- `mysite/asgi.py` — Django boilerplate

---

## 3. `urls.py` — top-level + news app

### 3.1 `mysite/mysite/urls.py` (top-level)

Paste verbatim. Confirm or update against the 2026-05-02 capture:

```python
# mysite/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("news.urls")),
]
```

### 3.2 `mysite/news/urls.py` (news app)

Paste the entire current file verbatim. Show every `path(...)` entry
with its view, name, and any decorator-style argument. The staging
side needs the canonical route table, not a sampled subset.

### 3.3 Delta against the 2026-05-02 route table

The 2026-05-02 scan captured the following dashboard-related routes
(non-exhaustive — please diff against the FULL current `news/urls.py`):

```
path('dashboards/',                                                  views.dashboards,                    name='dashboards'),
path('dashboards/<str:dashboard_id>/',                               views.dashboard_detail,              name='dashboard_detail'),
path('observatory/dashboards/<str:dashboard_id>/',                   views.observatory_dashboard_detail,  name='observatory_dashboard_detail'),
path('community/dashboards/<str:author>/<str:dashboard_id>/',        views.community_dashboard_detail,    name='community_dashboard_detail'),
path('franchise/',                                                   views.franchise_data,                name='franchise_data'),
path('franchise/<str:dashboard_id>/',                                views.franchise_detail,              name='franchise_detail'),
path('api/dashboard/refresh/',                                       views.refresh_dashboard_api,         name='refresh_dashboard_api'),
path('api/dashboard/refresh/status/',                                views.refresh_status_api,            name='refresh_status_api'),
path('api/dashboard/share/',                                         views.share_dashboard_api,           name='share_dashboard_api'),
path('profile/dashboards/',                                          views.user_dashboards_list,          name='user_dashboards_list'),
path('profile/dashboards/<str:dashboard_id>/',                       views.user_dashboard_detail,         name='user_dashboard_detail'),
```

Plus (also in 2026-05-02 scan): `home`, `observations`,
`observation_detail`, `franchise`, `whitepapers`, `user_guides`,
`faq`, `email_guide`, `download_whitepaper`, `commentary`,
`commentary_detail`, `contact`, `about`, `article_detail`,
`access_denied`, `report_detail`, `doc_page`.

For each `path(...)` in current `news/urls.py`:

- If unchanged from above: no action.
- If added since 2026-05-02: list the new entry.
- If removed since 2026-05-02: list it explicitly as REMOVED.
- If the URL pattern, view function, or `name=` changed: list the
  before/after.

### 3.4 `news/context_processors.py`

Paste the entire file verbatim. The 2026-05-02 scan named
`nav_observations` as a context processor; this round confirms its
current body and any additional processors that have landed.

---

## 4. `news/templates/news/base.html` — verbatim full

### 4.1 Full verbatim

Paste the **entire current contents** of
`ai_development/mysite/news/templates/news/base.html` in one fenced
`html` code block. Do not elide. The staging side will diff against
the 2026-05-02 capture and feed the delta into
`projects/frontend/dev/specs/design_system.md` and
`projects/frontend/dev/specs/inline_css_migration.md`. The user has
explicitly flagged this file as drifted since 2026-05-02 — every line
matters.

### 4.2 Delta callouts

After the verbatim paste, list each of the following as either
`UNCHANGED` or `CHANGED` against the 2026-05-02 capture, and if
changed paste the new value:

| Surface                                                             | 2026-05-02 captured value (paraphrased — confirm or correct) |
|---------------------------------------------------------------------|--------------------------------------------------------------|
| `<title>` template block                                            | `Prism AI Observatory` / per-page override via `{% block title %}` |
| Google Fonts `<link>` for Inter + Lora                              | Loaded from `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Lora:ital,wght@0,400;0,600;1,400&display=swap` |
| Favicon SVG                                                         | `{% static 'images/prism_logo64_transparent.svg' %}` |
| Favicon PNG fallback                                                | `{% static 'images/prism_logo.png' %}` |
| Body default `font-family`                                          | `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` |
| Top header / navbar logo                                            | `<img src="static/images/prism_logo64_transparent.svg %}" ...>` (note: malformed Django tag in the 2026-05-02 capture — confirm whether this is an OCR artifact or a real bug) |
| Header brand text                                                   | `Prism AI` |
| Inline `<style>` block size                                         | (please measure — see §10) |
| Mermaid CDN `<script>`                                              | `mermaid.min.js` loaded from `{% static 'js/mermaid.min.js' %}` |
| ECharts CDN / static `<script>`                                     | `echarts.min.js` loaded from `{% static 'js/echarts.js' %}` |
| Footer block                                                        | (paste — was not captured fully in 2026-05-02 scan) |

### 4.3 Logo / image references in base.html

Grep base.html for every logo / image reference and paste each match
with its line number. Specifically:

```python
import re
with open("ai_development/mysite/news/templates/news/base.html") as f:
    lines = f.readlines()
patterns = [
    r'\{%\s*static\s+["\']images/',
    r'\{\{\s*s3_image',
    r'background-image\s*:\s*url',
    r'\bsrc\s*=\s*["\']',
    r'\bhref\s*=\s*["\'][^"\']*\.(png|jpg|jpeg|svg|jiff|jfif|ico|webp)',
    r'_get_s3_image_url|get_s3_image_url|HERO_IMAGE_KEY|NAV_LOGO_KEY|DEFAULT_IMAGE_KEY',
]
for i, line in enumerate(lines, 1):
    for p in patterns:
        if re.search(p, line):
            print(f"{i:5d}  {line.rstrip()}")
            break
```

Paste the full stdout. The pattern this exposes is whether logos
are still being served via `{% static 'images/...' %}` (a Django
static URL) or have flipped over to S3-served URLs (via
`{{ s3_image1_url }}` template variables computed in the view). The
2026-05-02 portal scan showed BOTH patterns coexisting, which is
exactly the sort of drift the staging side needs to map.

### 4.4 Nav structure

Paste the verbatim `<nav>` / header chrome block from base.html
(from the opening `<header>` or `<nav>` tag through the closing tag).
The 2026-05-02 capture showed a dropdown with Franchise / Macro /
empty-state branches at lines 967-993 of the scan; this re-pull
captures whatever the current dropdown structure is, including the
Community Dashboards rename (per `prism/dashboards-portal.md` §7.1)
that was inferred but not verbatim-captured in 2026-05-02.

---

## 5. Page-level templates — each major view, verbatim

For each template below, paste the **entire current file contents**
in a fenced `html` code block. If the template hasn't changed since
the 2026-05-02 scan, paste it anyway — the staging side needs every
template byte-mirrored, not the diff.

| # | Template path                                                      | View it serves                          |
|---|--------------------------------------------------------------------|-----------------------------------------|
| 1 | `news/templates/news/home.html`                                    | `home`                                  |
| 2 | `news/templates/news/dashboards.html`                              | `dashboards` (3-section listing)        |
| 3 | `news/templates/news/dashboard_detail.html`                        | `dashboard_detail` (franchise fallback) |
| 4 | `news/templates/news/user_dashboards.html`                         | `user_dashboards_list`                  |
| 5 | `news/templates/news/observations.html`                            | `observations`                          |
| 6 | `news/templates/news/observation_detail.html`                      | `observation_detail`                    |
| 7 | `news/templates/news/profile.html`                                 | `profile` (per kerberos)                |
| 8 | `news/templates/news/franchise.html`                               | `franchise_data`                        |
| 9 | `news/templates/news/whitepapers.html`                             | `whitepapers`                           |
|10 | `news/templates/news/user_guides.html`                             | `user_guides` (if exists; else NOT FOUND) |
|11 | `news/templates/news/faq.html`                                     | `faq` (if exists; else NOT FOUND) |
|12 | `news/templates/news/doc_page.html`                                | `doc_page` (whitepaper / guide rendering) |
|13 | `news/templates/news/article_detail.html`                          | `article_detail`                        |
|14 | `news/templates/news/access_denied.html`                           | error fallback (`@require_auth` reject) |
|15 | `news/templates/news/contact.html`                                 | `contact`                               |
|16 | `news/templates/news/about.html`                                   | `about`                                 |
|17 | `news/templates/news/commentary.html`                              | `commentary`                            |
|18 | `news/templates/news/commentary_detail.html`                       | `commentary_detail`                     |
|19 | `news/templates/news/report_detail.html`                           | `report_detail`                         |
|20 | (any page-level template not listed above)                         | (list each)                             |

For each template:

- If the file does not exist, write `NOT FOUND` and skip.
- If the file exists, paste the entire body verbatim.
- After the body, in 1-3 sentences, identify the two largest
  inline `<style>` or inline `style="..."` declarations (line
  numbers + ~20-char preview), since those will need to migrate to
  `static/css/base.css` per `dev/specs/inline_css_migration.md`.

If any template not in the table above is also page-level (rendered
directly by a view), include it with its own row.

---

## 6. `news/views.py` — every view function, verbatim

### 6.1 File overview

Paste the first 30 lines of `news/views.py` (imports + module
constants) verbatim. Then report the file's total line count + total
bytes.

### 6.2 Module-level constants

Paste each of the following constant definitions verbatim, with line
number:

```
HERO_IMAGE_KEY
NAV_LOGO_KEY
DEFAULT_IMAGE_KEY
LOGO_IMAGE_KEY (if present)
PRISM_LOGO_KEY (if present)
GS_LOGO_KEY (if present)
TRANSPARENT_LOGO_KEY (if present)
HERO_IMAGE_KEY_FALLBACK (if present)
FRANCHISE_DASHBOARDS_CONFIG
COMMUNITY_DASHBOARDS_CONFIG (if still present)
PAGE_ACCESS_RULES
WHITEPAPER_MAP (if still present)
REPORT_SERVER_BASE
S3_BUCKET (or any module-level S3 config string)
```

If any constant has a different name in current `views.py`, list the
real name + value. The staging side will reconcile with the 2026-05-02
capture.

### 6.3 Helpers + utility functions

Paste each of the following helper functions in full (body + decorators
+ docstring), with line range. If a helper has been renamed or
deleted, note that and paste the replacement.

| Helper                              | 2026-05-02 line ref (approx) |
|-------------------------------------|------------------------------|
| `get_kerberos(request)`             | 170                          |
| `_get_s3_image_url(key, expiry=...)`| 1128                         |
| `get_s3_image_url(...)`             | 2199 / 2451 / 2742 / 3150 (the no-leading-underscore variant — possibly an alias, possibly drift; please clarify) |
| `_get_user_display_name(kerberos)`  | (referenced in dashboards-portal.md but body not captured)|
| `_build_nav_context(kerberos)`      | (verbatim in dashboards-portal.md §7.3) |
| `_get_nav_recent_observations()`    | (referenced, body not captured) |
| `_get_prism_users()`                | (referenced, body not captured) |
| `_get_access_group_users(group_name)`| (referenced, body not captured) |
| `check_page_access(kerberos, page_id)`| (verbatim in dashboards-portal.md §9.2) |
| `_inject_prism_globals(html, ...)`  | (referenced, body not captured) |
| `_read_share_state(kerberos, dashboard_id)` | (referenced, body not captured) |
| `get_user_dashboards(kerberos)`     | (verbatim in dashboards-portal.md §5) |
| `require_auth(view_func)`           | (verbatim in dashboards-portal.md §8.3) |
| `require_page_access(page_id)`      | (verbatim in dashboards-portal.md §8.3) |
| Any `_get_*_image_url` / `_get_*_logo_url` helpers I missed | — |

### 6.4 View functions

For each route in §3, paste the corresponding view function's full body
(decorators + signature + body) verbatim with line range. If a view's
body is large (>200 lines), paste it anyway — the staging side will
distil. Do NOT replace bodies with `# ...`.

Group them under their URL pattern for readability:

```
###  /  → home
<full view body>

###  /dashboards/  → dashboards
<full view body>
...
```

The list (mirror §3 routes):

- `home`
- `dashboards`
- `dashboard_detail`
- `observatory_dashboard_detail`
- `community_dashboard_detail`
- `franchise_data`
- `franchise_detail`
- `refresh_dashboard_api`
- `refresh_status_api`
- `share_dashboard_api`
- `user_dashboards_list`
- `user_dashboard_detail`
- `observations`
- `observation_detail`
- `whitepapers`
- `user_guides`
- `faq`
- `email_guide`
- `download_whitepaper`
- `commentary`
- `commentary_detail`
- `contact`
- `about`
- `article_detail`
- `access_denied`
- `report_detail`
- `doc_page`
- (any view not in the list above)

If any of these no longer exist or have been renamed/merged, note
that explicitly.

### 6.5 Context-dict shape per view

For each view, after its body, in a single line, list the keys it
puts into the `context` dict passed to `render(...)`. Format:

```
home              → {kerberos, display_name, s3_image1_url, nav_franchise_dashboards, nav_community_dashboards, nav_recent_observations, ...}
```

This is what the staging side needs to mirror in its mock views.

---

## 7. S3 caching layer — paths + TTL + invalidation triggers

This was thinly covered in the 2026-05-02 portal scan (only a
`CacheBuilder Class:  The ONLY code that touches S3` reference at
line 161 with no body). This is the most novel section.

### 7.1 The S3 manager itself

Paste verbatim from `ai_development/core/s3_bucket_manager.py` (or
wherever the `s3_manager` singleton lives — please confirm the path):

- The full `class S3BucketManager` definition (signature + every
  public method body), or whatever the equivalent class is called.
- The module-level `s3_manager = S3BucketManager(...)` instantiation
  if any.
- The bucket name(s) hardcoded into the class.
- The `get(key)`, `put(data, key)`, `list(prefix=...)`,
  `delete(key)`, `exists(key)` method bodies (or whatever the actual
  surface is).
- Any in-memory cache the manager maintains (e.g. an LRU on `get`).

### 7.2 Cache layer above the S3 manager

Is there a separate caching class layered on top of `s3_manager`?
The 2026-05-02 scan referenced a `CacheBuilder` class at line 161 —
paste its definition + body verbatim if it still exists. If it
has been renamed / refactored, paste the current equivalent. Specifically I want:

- The class name + path
- Every method signature
- Every TTL / expiry constant (e.g. presigned URL expiry = 7 days /
  604800 s per 2026-05-02 line 1128 reading
  `_get_s3_image_url(key, expiry=604800)`)
- Every cache-invalidation trigger (write-through? time-based? event-
  driven on dashboard refresh?)
- Every cache key that is computed (so staging knows which keys to
  mock)

### 7.3 What's cached vs what's not

Tabulate the per-surface caching story. One row per surface; please
include any I've missed:

| S3 path / surface                                    | Cached? | TTL / expiry | Invalidated when                | Reader (view / job)                  |
|------------------------------------------------------|---------|--------------|----------------------------------|--------------------------------------|
| `users/{kerb}/dashboards/dashboards_registry.json`   |         |              |                                  | `dashboards`, `user_dashboards_list` |
| `users/{kerb}/dashboards/{id}/dashboard.html`        |         |              |                                  | `user_dashboard_detail`              |
| `users/{kerb}/dashboards/{id}/refresh_status.json`   |         |              |                                  | `refresh_status_api`                 |
| `secondary/prism_observations/dashboards/dashboards_registry.json` |    |    |                                  | `dashboards`                         |
| `secondary/prism_observations/dashboards/{id}/dashboard.html` |        |       |                                  | `observatory_dashboard_detail`       |
| `secondary/sod/prism_users_list.json`                |         |              |                                  | `_get_prism_users`                    |
| `secondary/prism_observations/observations/...`      |         |              |                                  | `observations`                       |
| `secondary/prism_observations/reports/...`           |         |              |                                  | `report_detail`                      |
| `secondary/technical_docs/<doc>.md`                  |         |              |                                  | `whitepapers`, `doc_page`            |
| `development/images/<name>`                          |         |              |                                  | `_get_s3_image_url`                  |
| `mysite/images/<name>`                               |         |              |                                  | (?)                                  |
| Presigned image URLs                                 | yes     | 604800 s ?   |                                  | hero / favicon / nav                 |

For each row, mark "no" / "yes (in-memory)" / "yes (presigned URL
TTL only)" / "yes (S3-side ETag)" — whichever applies. If a row's
storage path has changed since 2026-05-02, call it out.

### 7.4 Page-load cost

For a single `/dashboards/` page load by a logged-in user with N
peer users in the registry, how many `s3_manager.get(...)` calls
happen and against which keys? Mirror the cost analysis in
`prism/dashboards-portal.md` §4 ("Cost shape: O(N_users) S3 reads
per listing-page load") — please confirm or update.

### 7.5 Forward-cache hooks

Are there any **planned** caches that aren't implemented yet but are
hooked in code (TODO comments, `# CACHE_INVALIDATION_HERE`,
no-op decorators, etc.)? Paste each with line + filepath.

---

## 8. Image-asset architecture (logos / favicons / hero images)

The user has flagged this surface as drifted. The 2026-05-02 portal
scan + the 2026-05-02 S3-logos email feedback together captured:

| Asset                       | Where it lives in 2026-05-02 scan                                            |
|-----------------------------|------------------------------------------------------------------------------|
| `prism_logo.png`            | S3 `development/images/prism_logo.png` (1.3 MB, accessible)                  |
| `gs_logo.png`               | S3 `development/images/gs_logo.png` (21 KB, accessible) — added 2026-05-02 |
| `logo_transparent.jiff`     | S3 `development/images/logo_transparent.jiff` (13 KB, accessible) — added 2026-05-02 |
| `prism_logo64_transparent.svg` | (referenced via `{% static 'images/prism_logo64_transparent.svg' %}` in base.html — Django static, NOT S3) |
| Hero background image       | S3 `mysite/images/site_image1.PNG` (per `HERO_IMAGE_KEY` constant)           |
| Nav logo                    | S3 `mysite/images/prism_logo64_transparent.svg` (per `NAV_LOGO_KEY` constant) |

That table immediately shows two coexisting conventions:

- **S3-served via `_get_s3_image_url(key)`** → presigned URL injected
  into context as `s3_image1_url`, used as
  `<section style="background-image: url('{{ s3_image1_url }}');">`.
  Paths under `mysite/images/` and `development/images/`.
- **Django-static-served via `{% static 'images/<file>' %}`** →
  resolves through `STATIC_URL` (which today is `'static/'` and is
  not actually configured to find `news/static/images/` because
  `STATICFILES_DIRS` is NOT DEFINED). Paths must be under whatever
  `STATICFILES_DIRS` resolves.

This round-trip captures **the current state** of that split.

### 8.1 All image-key constants in views.py

Paste each module-level constant whose value is an image S3 key or
file path. Mirror §6.2. Format:

```
HERO_IMAGE_KEY        = 'mysite/images/site_image1.PNG'
NAV_LOGO_KEY          = 'mysite/images/prism_logo64_transparent.svg'
DEFAULT_IMAGE_KEY     = '<value if present>'
PRISM_LOGO_KEY        = '<value if present>'
GS_LOGO_KEY           = '<value if present>'
TRANSPARENT_LOGO_KEY  = '<value if present>'
LOGO_IMAGE_KEY        = '<value if present>'
```

For any image-key constant whose **path string has changed** since
2026-05-02, list the before → after explicitly.

### 8.2 The `_get_s3_image_url` helper

Paste the full body verbatim. Specifically I need:

- Default `expiry` value
- The exact S3 method called (`generate_presigned_url`? something else?)
- Whether it caches (per 7.2)
- Behaviour on miss (raises? returns `''`? returns DEFAULT_IMAGE_KEY's URL?)
- Whether there's a `get_s3_image_url` (no leading underscore) variant
  — the 2026-05-02 scan showed BOTH names called from views.py
  (`get_s3_image_url(HERO_IMAGE_KEY)` at line 930/939/2199 vs
  `_get_s3_image_url(HERO_IMAGE_KEY)` at line 2482/2495/2507/2593/etc.)
  — please clarify whether this is two functions or an alias

### 8.3 Where is each image asset actually loaded from?

For each asset below, trace it from the browser-visible URL back to
the disk / S3 path. Format:

```
prism_logo.png (favicon)
  base.html line <N>:  <link rel="icon" type="image/png" href="{% static 'images/prism_logo.png' %}">
  resolves to:           /static/images/prism_logo.png
  served by:             Django staticfiles → <where on disk?>  (or 404 because STATICFILES_DIRS unset?)
```

Repeat for:

- `prism_logo.png` (favicon)
- `prism_logo64_transparent.svg` (favicon SVG + nav logo)
- `gs_logo.png` (where rendered? in `news/base.html`? footer? nowhere yet?)
- `logo_transparent.jiff` (where rendered?)
- `site_image1.PNG` (hero background)
- Any other static-image asset reachable from the browser

If `STATICFILES_DIRS` is still unset, every `{% static 'images/...' %}`
URL in templates currently 404s on a real Django dev-server run —
please confirm explicitly whether this is the case today, OR whether
something has moved (e.g. logos now served via S3 presigned URLs
instead of Django static, or `STATICFILES_DIRS` now set, or
`mysite/images/` actually exists on disk and is auto-discovered, or
there's a `news/static/news/images/` app-level static dir that resolves
without `STATICFILES_DIRS`).

### 8.4 New image-asset surfaces since 2026-05-02

If any **new** image-asset usage has been added to base.html or any
template since 2026-05-02 (e.g. a footer GS logo, a sign-in lockup
mark, an inline SVG sprite), paste each with `<filepath>:<line>` and
the rendered HTML around it.

### 8.5 The `s3_image1_url` context variable proliferation

The 2026-05-02 scan showed `s3_image1_url` injected into ~25 view
context dicts (lines 930, 939, 2199, 2451, 2461, 2482, 2495, 2507,
2593, 2712, 2742, 2779, 2890, 2951, 3059, 3088, 3106, 3134, 3150,
3213, 3232, 3524, 3553, 6776, 6852, 6884). All of those resolve to
the SAME hero-image URL (always `_get_s3_image_url(HERO_IMAGE_KEY)`),
suggesting a refactoring opportunity — please confirm:

- Is there a single context-processor injecting `s3_image1_url`
  globally that the per-view `context.update(...)` calls duplicate?
- If yes, paste it.
- If no, confirm explicitly that 25+ views each independently call
  `_get_s3_image_url(HERO_IMAGE_KEY)` and put the result into their
  own context dict.

This decides whether the staging-side refactor folds it into
`news.context_processors`.

---

## 9. Kerberos URL resolution + `PAGE_ACCESS_RULES`

This is well-captured in `prism/dashboards-portal.md` §8 + §9. Please
confirm the relevant facts are still true OR list the deltas.

### 9.1 `get_kerberos(request)` body

The 2026-05-02 capture (verbatim from
`prism/dashboards-portal.md` §8.1):

```python
def get_kerberos(request):
    """Extract kerberos from GSSSO cookie if present.

    Mirrors report_portal.py's get_current_user() logic but adapted for
    Django's request object. No authentication gate -- just best-effort
    identification so we can personalise the UI.
    """
    # 1. Try GSSSO cookie (primary)
    gssso_cookie = request.COOKIES.get("GSSSO", "")
    if gssso_cookie:
        try:
            from gs_auth import webauth
            authenticated, parsed_cookie, _ = webauth(gssso_cookie, "")
            if authenticated:
                user = parsed_cookie.get_details().get("username")[1]
                if user:
                    return user
        except Exception:
            pass

    # 2. Fallback: gsweb-kerberos cookie
    gsweb_kerb = request.COOKIES.get("gsweb-kerberos", "").strip()
    if gsweb_kerb:
        return gsweb_kerb

    # 3. Fallback: OS-level user (works on GS dev boxes where the
    # logged-in user IS the kerberos -- no SSO needed)
    try:
        return os.getlogin()
    except OSError:
        pass

    return os.environ.get("USER") or os.environ.get("USERNAME")
```

Confirm `UNCHANGED` or paste the current body.

### 9.2 `PAGE_ACCESS_RULES`

The 2026-05-02 capture:

```python
PAGE_ACCESS_RULES = {
    'irp_inquiries': 'strats_trading',
    'coalition':     'strats_trading',
}
```

Confirm `UNCHANGED` or paste the current dict.

### 9.3 `check_page_access` + `_get_access_group_users`

Confirm `UNCHANGED` or paste both helpers verbatim.

### 9.4 The `@require_auth` and `@require_page_access(page_id)` decorators

Confirm `UNCHANGED` or paste both verbatim (see
`prism/dashboards-portal.md` §8.3 for the 2026-05-02 capture).

### 9.5 Kerberos-bearing URL patterns

Today, exactly one URL pattern in `news/urls.py` carries another
user's kerberos in the path:
`/community/dashboards/<author>/<dashboard_id>/`. Confirm this is
still the only such pattern, or list any new ones.

---

## 10. Existing CSS architecture + inline-style quantification

### 10.1 Inventory `.css` files

```python
import os, glob
patterns = [
    "ai_development/mysite/**/*.css",
    "ai_development/mysite/static/**/*.css",
    "ai_development/mysite/news/static/**/*.css",
    "ai_development/mysite/staticfiles/**/*.css",
]
hits = set()
for pat in patterns:
    hits.update(glob.glob(pat, recursive=True))
print(f"Total .css files under mysite/: {len(hits)}")
for p in sorted(hits):
    print(f"  {p}  ({os.path.getsize(p)} B)")
```

Paste the full stdout. Per the 2026-05-02 fonts reply this set was
**empty**; please confirm or update.

### 10.2 base.html inline `<style>` block — quantify

This drives the open decision on whether
`projects/frontend/dev/specs/inline_css_migration.md` is authored
standalone or folded into the payload-creation iteration. Run inside
`execute_analysis_script`:

```python
import re
with open("ai_development/mysite/news/templates/news/base.html") as f:
    html = f.read()

style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html, flags=re.DOTALL | re.IGNORECASE)
total_bytes = sum(len(b) for b in style_blocks)
total_lines = sum(b.count("\n") for b in style_blocks)
total_rules = 0
for b in style_blocks:
    # Strip @-rules + count brace-delimited rule bodies as a coarse approximation
    bodies = re.findall(r'\{[^{}]*\}', b)
    total_rules += len(bodies)

print(f"Number of <style> blocks: {len(style_blocks)}")
print(f"Total inline-style bytes (sum across blocks): {total_bytes}")
print(f"Total inline-style line count:                {total_lines}")
print(f"Approx CSS rule count (brace-delimited):      {total_rules}")

# Top 10 selectors by frequency (rough)
all_css = "\n".join(style_blocks)
selectors = re.findall(r'([^{}\n][^{}]*?)\s*\{', all_css)
selectors = [s.strip() for s in selectors if s.strip() and not s.strip().startswith('@')]
from collections import Counter
top = Counter(selectors).most_common(10)
print("\nTop 10 selectors by frequency:")
for sel, cnt in top:
    print(f"  {cnt:4d}  {sel[:100]}")
```

Paste the full stdout. Specifically I need the four numbers
(`<style>` block count, total bytes, total lines, rule count) plus the
top-10 selectors so the staging side can decide whether the migration
warrants its own spec file.

### 10.3 Inline `style="..."` attributes

The 2026-05-02 capture showed many inline `style="..."` attributes in
templates (e.g. the user_dashboards.html status pills:
`style="font-size: 0.72rem; background: #0f3d0f; color: #4ade80; ..."`).
Quantify across all templates:

```python
import os, re
ROOT = "ai_development/mysite/news/templates/news"
total = 0
per_file = {}
for fname in sorted(os.listdir(ROOT)):
    if not fname.endswith(".html"):
        continue
    with open(os.path.join(ROOT, fname)) as f:
        body = f.read()
    hits = re.findall(r'\bstyle\s*=\s*"[^"]*"', body)
    per_file[fname] = (len(hits), sum(len(h) for h in hits))
    total += len(hits)
print(f"Total inline style=\"...\" occurrences across all templates: {total}")
for fname, (cnt, bytes_) in sorted(per_file.items(), key=lambda kv: -kv[1][0]):
    print(f"  {cnt:5d}  {bytes_:7d} B  {fname}")
```

Paste the full stdout. The top-3 templates by inline-style count are
the highest-leverage migration targets.

### 10.4 Static JS files

```python
import os, glob
patterns = [
    "ai_development/mysite/**/*.js",
    "ai_development/mysite/static/**/*.js",
    "ai_development/mysite/news/static/**/*.js",
]
hits = set()
for pat in patterns:
    hits.update(glob.glob(pat, recursive=True))
print(f"Total .js files under mysite/: {len(hits)}")
for p in sorted(hits):
    print(f"  {p}  ({os.path.getsize(p)} B)")
```

The 2026-05-02 scan referenced `echarts.js`, `mermaid.min.js`,
`mermaid_init.js`, `dashboard_refresh.js` (the last one referenced
in `user_dashboards.html` at scan line 912:
`<script src="{% static 'js/dashboard_refresh.js' %}"></script>`).
Confirm path + size for each.

---

## 11. Whitepapers / user_guides / FAQ wiring (S3 vs codebase split)

The `projects/whitepapers/` staging project will eventually ship its
3 workshopped docs (`whitepaper_data_integrations.md`,
`whitepaper_user_personalization.md`,
`whitepaper_world_state_and_reasoning.md`) plus 2 how-to guides
(`faq.md`, `email_usage_guide.md`) into PRISM at
`ai_development/context/white_papers/<name>.md`. The
`projects/frontend/` project is the one that rewires `views.py`
from the current S3 path (`secondary/technical_docs/`) to the
codebase path. This section captures the current state of that
wiring so the rewire can land cleanly.

### 11.1 `WHITEPAPER_MAP`

The 2026-05-02 scan referenced a `WHITEPAPER_MAP` constant. Paste it
verbatim (or note REMOVED/RENAMED):

### 11.2 Whitepaper-rendering views

Paste each of the following view bodies verbatim (mirror §6.4 if not
already covered). For each, identify whether it reads from S3
(`secondary/technical_docs/...`) or from a codebase path
(`ai_development/context/white_papers/...`):

- `whitepapers`
- `user_guides`
- `faq`
- `email_guide`
- `download_whitepaper`
- `doc_page` (the per-document renderer)

Note for each: which markdown lib + extensions it uses (the 2026-05-02
whitepapers verify reply §5 said `markdown` + `[tables, fenced_code,
toc, nl2br]` — confirm).

### 11.3 `ai_development/context/white_papers/` directory state

Run inside `execute_analysis_script`:

```python
import os
ROOT = "ai_development/context/white_papers"
if not os.path.exists(ROOT):
    print(f"{ROOT} DOES NOT EXIST")
else:
    for f in sorted(os.listdir(ROOT)):
        full = os.path.join(ROOT, f)
        if os.path.isfile(full):
            print(f"  {f}  ({os.path.getsize(full)} B)")
```

Paste the stdout. The whitepapers verify reply §8 noted this
directory ALREADY EXISTS in PRISM with stale 2026-05-02 versions of
all 5 files; please confirm the file list + sizes today.

### 11.4 Mermaid + render path

Confirm or update from the 2026-05-02 whitepapers verify reply §5:

- Mermaid renders client-side via `news/base.html`'s
  `mermaid.min.js` script tag.
- `<details>` / `<summary>` survives unchanged.
- No LaTeX / MathJax.
- No syntax highlighting.
- No native chart embedding.

If any of these has changed (Mermaid moved server-side? KaTeX added?
Pygments wired in?), call it out.

---

## 12. Summary artifacts at the end of your reply

After §1-§11, please produce two compact summary artifacts. These let
the staging side mechanically update `prism/frontend.md` (NEW) +
`projects/frontend/dev/specs/design_system.md` + the staging-side
README without me paraphrasing.

### 12.1 Capability / state JSON (one-line per field)

```json
{
  "scan_date": "2026-05-XX",
  "django_version": "<X.Y.Z>",
  "mysite_total_files": <int>,
  "mysite_total_bytes": <int>,
  "templates_count": <int>,
  "views_py_total_lines": <int>,
  "views_py_view_function_count": <int>,
  "static_css_files_count": <int>,
  "static_js_files_count": <int>,
  "base_html_total_lines": <int>,
  "base_html_inline_style_block_bytes": <int>,
  "base_html_inline_style_block_lines": <int>,
  "base_html_inline_style_rule_count_approx": <int>,
  "templates_inline_style_attribute_count": <int>,
  "STATICFILES_DIRS_defined": true | false,
  "STATIC_ROOT_defined": true | false,
  "STATIC_URL_value": "<value>",
  "STATICFILES_DIRS_value": "<list of paths or null>",
  "DEBUG_value": true | false,
  "ALLOWED_HOSTS_count": <int>,
  "context_processors_count": <int>,
  "url_patterns_count": <int>,
  "kerberos_bearing_url_patterns": <int>,
  "page_access_rules_keys": [<list of page_ids>],
  "image_key_constants": {
    "HERO_IMAGE_KEY": "<value>",
    "NAV_LOGO_KEY": "<value or null>",
    "DEFAULT_IMAGE_KEY": "<value or null>",
    "PRISM_LOGO_KEY": "<value or null>",
    "GS_LOGO_KEY": "<value or null>",
    "TRANSPARENT_LOGO_KEY": "<value or null>"
  },
  "s3_image_url_helper_name": "_get_s3_image_url" | "get_s3_image_url" | "BOTH",
  "s3_image_url_default_expiry_seconds": <int>,
  "s3_buckets_referenced": ["<bucket_name>", ...],
  "cache_class_name": "<class name or null>",
  "cache_class_path": "<filepath or null>",
  "white_papers_directory_exists": true | false,
  "white_papers_directory_file_count": <int>,
  "whitepaper_views_read_from": "S3" | "CODEBASE" | "MIXED",
  "navbar_logo_served_via": "DJANGO_STATIC" | "S3_PRESIGNED_URL" | "INLINE_SVG" | "OTHER",
  "favicon_served_via": "DJANGO_STATIC" | "S3_PRESIGNED_URL" | "OTHER"
}
```

### 12.2 Delta table vs the 2026-05-02 scan

One row per surface that changed. Format:

```
SURFACE                                  STATUS       DELTA SUMMARY
mysite/news/templates/news/base.html      CHANGED      +N lines, logo hrefs flipped from {% static %} to {{ s3_logo_url }}
mysite/mysite/settings.py                 UNCHANGED    —
mysite/news/views.py                      CHANGED      +12 helper functions, _get_s3_image_url renamed to get_s3_image_url
mysite/news/urls.py                       UNCHANGED    —
news/templates/news/whitepapers.html      CHANGED      now reads from ai_development/context/white_papers/
ai_development/mysite/fonts/              UNCHANGED    20 TTFs (per 2026-05-02 fonts reply)
news/context_processors.py                CHANGED      added s3_image1_url to nav_observations
ai_development/core/s3_bucket_manager.py  NOT_PREVIOUSLY_CAPTURED   <full body in §7.1>
ai_development/core/<cache_class>.py      NOT_PREVIOUSLY_CAPTURED   <full body in §7.2>
```

Include EVERY surface that touches §1-§11, even if `UNCHANGED`. The
staging side needs the full coverage map to know what's drift-checked
vs what's still stale.

### 12.3 Files we'd benefit from but didn't ask for above

If during the introspection you find a file that you'd flag as
load-bearing for the staging-side scaffolding but isn't listed in
§1-§11, list it with one-sentence rationale. Examples:

- A custom template tag library (`news/templatetags/...`)
- A signals.py / apps.py / admin.py if any have non-trivial body
- A `requirements.txt` or `pyproject.toml` for the portal app

We'd rather one extra round-trip cost in this reply than discover the
gap mid-scaffold.

---

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried and
what blocked it. This is NOT a frictions report — it is a minimal
coverage note.
