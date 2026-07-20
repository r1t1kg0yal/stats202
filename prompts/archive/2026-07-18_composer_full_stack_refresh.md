---
class: context-extraction
topic: Full Composer stack, dashboard integration, and inline chat — current-state refresh
status: ARCHIVED
archived_reason: Superseded by 2026-07-19 working-tree diff review
  (sessions/20260719_221610_goyalri_dashboard_website_diff_review/).
  Staging docs ingested into
  projects/echarts/dev/specs/composer_dashboard_stack.md and
  prism/dashboards-portal.md §11. Re-issue a fresh extraction only if
  the live tree drifts from that SSOT.
baseline: 2026-07-18 morning introspection (sessions/20260718_112944_goyalri_composer_architecture_introspection/) plus a supplied uncommitted working-tree diff
staleness_hypothesis: Stage 2b component drag, the DND-mode refactor, rendering.py promotion, and inline-chat changes may have landed since the baseline was captured
---

# Re-extract the full Composer stack (files, dashboard integration, inline chat)

This is read-only source introspection. Do not edit files, propose an
implementation, or build anything. Use `list_ai_repo` /
`execute_analysis_script` as needed to read the live repository state.

Our staging documentation of Composer was captured on 2026-07-18 from a
morning introspection session plus an **uncommitted working-tree diff**.
We believe the tree has moved since. Every section below states our
baseline claim; for each one, classify your finding as:

- `CONFIRMED` — the claim matches current source exactly;
- `CHANGED` — quote the current truth verbatim and note what moved;
- `GONE` — the file/flag/route/symbol no longer exists.

Quote signatures, docstrings, route patterns, flag dicts, and JSON
schemas verbatim in fenced code blocks. Do not paraphrase. Reply in
exactly the structure below.

## 1. File inventory and git state

Baseline inventory (paths relative to prism-main root):

| File | Baseline size |
|---|---|
| `web/prism_site/js/composer.js` | 1,252 lines baseline, +14 net in working tree |
| `web/prism_site/js/dashboard_composer.js` | 38 working-tree lines (NEW at baseline) |
| `web/prism_site/css/composer.css` | 1,662 lines / 57,799 bytes |
| `web/prism_site/templates/base.html` | Composer mount at lines 1447-1453 |
| `web/prism_site/run.py` | `FEATURE_FLAGS` at lines 167-174 |
| `web/backend_django/news/composer_views.py` | 657 lines / 25,264 bytes |
| `web/backend_django/news/composer_email.py` | 365 lines / 14,161 bytes |
| `web/backend_django/news/composer_artifacts.py` | 220 lines / 10,667 bytes |
| `web/backend_django/news/dashboard_composer.py` | 81 working-tree lines (NEW at baseline) |
| `web/backend_django/news/urls.py` | Composer routes at lines 153-160 |

For every file above, report the current exact path, line count, and
byte size. Report any additional Composer-related file that now exists
anywhere under `web/` (glob for `*composer*` and check for new imports
in `views.py` / `urls.py`).

For each file, also report git state: committed on the current branch,
staged, or unstaged-working-tree-only. At baseline,
`dashboard_composer.py` and `dashboard_composer.js` had **empty staged
blobs with real content unstaged** — state explicitly whether that has
been resolved and what the committed content now is.

Separately: does the installed `prism-core/dashboards/rendering.py` now
export `widgets` on `window.DASHBOARD` and dispatch a
`prism:dashboard:ready` `CustomEvent` after `initTools()`? This tells us
whether the staging `rendering.py` promotion happened. Quote the export
object and the dispatch call if present.

## 2. Feature flags and the DND mode

Baseline claims:

- `run.py::FEATURE_FLAGS` carried `enable_composer` and
  `enable_inline_chat`; the working tree flipped `enable_inline_chat`
  to `True` site-wide.
- The browser DND gate was a coarse boolean
  `window.PRISM_COMPOSER_DISABLE_DND` which, when true, hides upload,
  hides the drop-zone hint, skips `setupPanelDropTarget()`, returns
  early from `initDragSources()`, and never starts the body
  `MutationObserver`.
- A planned refactor replaces the boolean with
  `window.PRISM_COMPOSER_DND_MODE` with modes `standard` / `disabled` /
  `dashboard_components`.

Report:

1. The current `FEATURE_FLAGS` dict verbatim, with line numbers.
2. The exact `base.html` mount block verbatim (CSS link, root div,
   inline-chat flag script, deferred script tags), with line numbers.
3. Which DND control exists today: `PRISM_COMPOSER_DISABLE_DND`,
   `PRISM_COMPOSER_DND_MODE`, both, or something else. Quote every
   writer and every reader of each flag (file + line), and the exact
   per-mode behavior in `composer.js` (drop target, file upload,
   generic source scan, allowed artifact types).

## 3. Dashboard mount seam

Baseline claims:

- `public_user_dashboard_detail` reads stored `dashboard.html` from S3,
  calls `_inject_prism_globals(...)` (splice before `</head>`, ten
  `PRISM_*` globals), then calls
  `dashboard_composer.inject_dashboard_composer(html)` route-wide (not
  owner-only) before returning.
- `inject_dashboard_composer(html)` splices before the last `</body>`:
  scoped `--gs-uitk-*` token style, `/static/css/composer.css`,
  `#prism-composer-root`, `PRISM_COMPOSER_DISABLE_DND = true`,
  `PRISM_COMPOSER_INLINE_CHAT = false`, deferred
  `/static/js/dashboard_composer.js`.
- `dashboard_composer.js` repeats the two flags, guards with
  `window.__prismComposerDashboardBooted`, and appends deferred
  `/static/js/composer.js`.
- Observatory and developer detail routes get no Composer mount;
  profile and community detail routes 301 into the canonical user
  route.

Report the current bodies of `inject_dashboard_composer` and
`dashboard_composer.js` verbatim (both are small). Then report:

1. exactly which views call the injector today, and whether any call is
   now conditioned on owner/viewer identity;
2. the full list of globals/flags the injected block writes;
3. whether Observatory and developer routes are still excluded;
4. the full injected-globals list from `_inject_prism_globals` (baseline
   was ten: VIEWER, DASHBOARD_AUTHOR, DASHBOARD_OWNER, DASHBOARD_ID,
   DASHBOARD_SHARED, DASHBOARD_SHARE_MODE, DASHBOARD_SHARE_TOKEN,
   TELEMETRY_ENDPOINT, IS_OBSERVATORY, TEMPLATE_HASH).

## 4. Composer endpoint inventory

Baseline: seven routes at `urls.py:153-160`, all views `@csrf_exempt`,
method-restricted (405 otherwise), inline `get_kerberos(request)` with
HTTP 401 when absent:

| Route | Method | Baseline success shape |
|---|---|---|
| `/api/composer/fire-off/` | POST | `{ok, fire_off_id, subject, recipients, message}` |
| `/api/composer/chat/` | POST | `StreamingHttpResponse`, `text/event-stream` |
| `/api/composer/history/` | GET | `{items, total, offset, page_size}` (page_size cap 50) |
| `/api/composer/replay/` | POST | edit → `{ok, prefill}`; send delegates to fire-off |
| `/api/composer/preview/` | POST | `{ok, preview_body, preview_subject, artifact_count}` |
| `/api/composer/delete/` | POST | `{ok: true}` |
| `/api/composer/artifact-info/` | GET | `{type, id, path, label, preview}` |

Quote the current composer URL patterns from `urls.py` verbatim. For
each view: signature, decorators, accepted methods, request JSON keys,
response shape, and error status codes. Explicitly flag any route added
or removed relative to the seven above. Confirm `/api/users/me` and
`/api/users/search/` remain separate GET-only identity helpers.

## 5. `dashboard_component` — Stage 2b implementation status

At baseline this was a designed-but-unimplemented contract. Determine
how much has now landed. The planned contract, for reference:

- `dashboard_composer.js`: two-latch startup (composer loaded +
  `prism:dashboard:ready`), bind once, owner-only
  (`PRISM_VIEWER === PRISM_DASHBOARD_OWNER`), allowlist
  `chart` / `kpi` / `table` / `data_grid` / `pivot` / `stat_grid`,
  drag handle `.tile-header` (`.kpi-header` for KPI), reject drags from
  interactive descendants, write `application/x-prism-artifact` with
  `{type: "dashboard_component", id, path, label, widget_kind,
  template_sha256}` and `effectAllowed="copy"`.
- `composer.js`: in dashboard mode, drop target on, upload off, generic
  source scan off, accept `dashboard_component`, reuse the normal
  optimistic card + artifact-info enrichment.
- `composer_artifacts.py`: `dashboard_component` branch in the shared
  resolver — server-side folder reconstruction from authenticated
  kerberos, `manifest_template.json` byte-hash compared against
  `template_sha256` with a typed stale-reference error, exactly-one
  widget-id match across tabbed/flat layout, six-kind allowlist,
  reference-only return (`attachment_paths: []`, `s3_paths: []`).
- `composer_email.py`: `dashboard_component` classified reference-only;
  one compact reference line in the constructed prompt.

Report, with verbatim quotes of the relevant current code:

1. which of these four pieces exist today, and where each deviates from
   the planned contract;
2. the exact browser payload fields as implemented;
3. the exact resolver branch: validation steps, error shapes, and the
   returned artifact dict;
4. the exact reference line emitted into the fire-off/chat prompt;
5. whether the non-owner path (shared dashboard, viewer != owner) binds
   any handles or exposes any component surface;
6. any tests added around this path (file + test names).

If none of it has landed, say so plainly — that is a valid answer.

## 6. Artifact resolver

Baseline: `composer_artifacts.read_artifact_content(artifact, kerberos)`
is the single shared resolver, returning
`{type, label, content_summary, attachment_paths, live_url, s3_paths}`,
with per-type behavior:

| Type | Read | Inline | Attach | Notes |
|---|---|---|---|---|
| dashboard | `{prefix}/manifest.json`, `index.html` | no | `index.html` | live URL `/users/{kerberos}/dashboards/{id}/` |
| report | `{path}/report.md` | no | no | |
| observation | `{path}/observation.json` | no | no | |
| process | `prompt.md`, `scripts/*.py` | no | no | |
| cabinet folder | `show_all(path)` | no | no | |
| cabinet text | file body | no | no | |
| cabinet PDF/binary | file | no | binary | |
| preference | `preferences.json[idx]` | full text | no | |
| skill | `users/{kerberos}/skills/{file}` | full body, `APPLY THIS SKILL:` prefix | no | |
| thread | `threads/{id}/metadata.json` + last 5 messages | no | no | |

Report the current signature, complete return schema, and the full
per-type table (including any new types). Quote the routing constants
in `composer_email.py` that classify inline / reference-only /
attachable. Identify every current caller of the resolver with
import/call sites.

Baseline open question, resolve explicitly: the resolver read dashboard
`index.html` while the canonical ECharts folder contract names
`dashboard.html`. Does the resolver still name `index.html`? Do current
user dashboard folders actually carry a file at that key, or does
dashboard attachment silently fail / typed-error today?

## 7. Fire-off and email composition

Baseline: fire-off ignores client recipients, derives sender/recipient
from authenticated Kerberos via
`UserRegistry.instance().get_user_info(kerberos)[1]` (fails closed HTTP
400 when no email), subject prefixed with a Composer sentinel (or the
hallucination-judge sentinel when selected), body sections Request /
Attached Files / Cabinet References / Composition Notes plus inline
Preference and Applied Skill blocks, attachment set = union of
`attachment_paths` + `s3_paths` for non-inline/non-reference artifacts.
History under `users/{kerberos}/fire_offs/` (`manifest.json` capped at
200 newest-first summaries + `{fire_off_id}/fire_off.json`), id format
`FO-{YYYYMMDD_HHMMSS}-{8hex}`, `supersedes_id` drops the old summary
and best-effort deletes the detail folder.

Confirm or correct every element above with quotes: exact sentinel
strings, subject derivation, body section builder, attachment-set
logic, recipient/CC resolution (including closed-user drop behavior),
persistence schemas, manifest cap, and supersession behavior.

## 8. Inline chat

Baseline:

- gated by `FEATURE_FLAGS["enable_inline_chat"]` →
  `window.PRISM_COMPOSER_INLINE_CHAT` → `INLINE_CHAT_ENABLED` in
  `composer.js`; site-wide `True` in the working tree while the
  dashboard injector forces `false`, so dashboards are fire-off-only;
- `chat_api` builds
  `GSLLM(mcp_servers=[os.environ.get("PRISM_MCP_SERVER", "fred-mcp5")],
  default_model=AIModel.Claude_Opus.value, stream=True,
  user_id_suffix="composer_chat")`, tagged `medium_query="teams"`;
- SSE grammar `event: <name>\ndata: <json>\n\n` with `thinking`,
  `tool`, `final` (`text` + `accumulated`), `error`, `done`;
  `Cache-Control: no-cache`, `X-Accel-Buffering: no`;
- ephemeral: no fire-off record, no history entry; transcript lives
  only in the browser DOM; client abort via `AbortController`, server
  closes the async iterator on disconnect; mid-stream failures emit SSE
  `error` then `done`, never a late JSON 500.

Report the current state of each bullet with verbatim quotes: flag
values as committed vs working tree, the dashboard force-off (still
present?), the exact LLM constructor and model, request tagging, the
SSE event grammar, response headers, persistence (has any chat history
or transcript storage been added?), and abort/disconnect handling.

## 9. Client state machine and drag sources

Baseline `composer.js` behavior:

- `sessionStorage` key `prism_composer_state`; persisted shape includes
  mode, attachments, CC, message, name, supersession state, and
  inline-mode state;
- four modes `pill -> expanded -> history -> chat`;
- one delegated click listener on the root, per-element binding guards
  for inputs rebuilt by `innerHTML`, in-place drop-card append,
  optimistic artifact cards enriched by `/api/composer/artifact-info/`,
  optimistic fire-off, replay-in-flight and chat-abort guards;
- `initDragSources()` selector families: `.tree-node.file`,
  `.tree-node.folder`, `.dashboard-card`, `.process-card`,
  `.preference-item`, `.skill-card`, `.conversation-item`,
  `.prism-conversation-item`, `.gs-card[data-artifact-type]`;
  body-level `MutationObserver` re-registers late sources; full panel
  and pill are both drop targets; drag payload MIME
  `application/x-prism-artifact` with at least
  `{type, id, path, label}`.

Report the current `sessionStorage` key and complete persisted state
shape, the mode set, the current selector table (any additions —
especially anything dashboard-tile-related), the observer setup, the
drop-target set, and how behavior differs per DND mode on dashboard
pages. Quote the drag payload writer.

## 10. Security boundary

Baseline: all Composer endpoints `@csrf_exempt` with inline
`get_kerberos` (401 on absence); self-send enforced server-side
(client recipients ignored); `/api/users/me` returns `{ok, kerberos,
display_name, email, department, department_member_count}`; CC accepts
Kerberos ids or emails, resolves through `UserRegistry`, drops
unresolvable/closed identities with a warning; no endpoint can send or
write as another user.

Confirm or correct each element. Additionally, if `dashboard_component`
has landed: quote the server-side ownership check for component
references, and state whether any part of the component path trusts a
client-supplied owner/path.

## 11. Serving-route Composer matrix

Fill in the current truth for this baseline matrix:

| Surface | Delivery | Composer today |
|---|---|---|
| `/dashboards/` | template render | yes, via `base.html` |
| `/dashboards/<id>/` | report-server bytes or template fallback | only on fallback branch |
| `/users/<kerberos>/dashboards/` | template render | yes; cards draggable |
| `/users/<kerberos>/dashboards/<id>/` | S3 bytes + globals + injector | mounted without `base.html`, read-only |
| `/observatory/dashboards/<id>/` | S3 bytes + globals | no |
| `/developer/dashboards/<id>/` | S3 bytes, no globals | no |
| profile/community detail | 301 to canonical user route | inherited |

Flag any row that has changed, and any new dashboard-serving route.

## 12. Documentation verdict

Close with four lists:

1. baseline claims confirmed exactly;
2. baseline claims corrected by current source (cite section numbers
   from this prompt);
3. net-new facts since the 2026-07-18 baseline that none of the
   sections above asked about;
4. anything you observed that suggests in-flight, half-landed work
   (uncommitted files, dead flags, partially migrated readers).

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end naming exactly what could not
be resolved and why.
