---
class: context-extraction
topic: Composer, compiled-dashboard integration, persisted user input, and S3 full-stack current-state refresh
status: OPEN
created_at: 2026-07-21
baseline_date: 2026-07-20
reply_fold_in_targets:
  - projects/echarts/dev/specs/composer_dashboard_stack.md
  - projects/echarts/dev/specs/dashboard_user_input.md
  - projects/echarts/README.md
  - projects/echarts/dev/notes.md
  - staging/README.md
---

# Re-extract the full Composer, dashboard, user-input, and S3 stack

This is read-only source introspection. Do not edit, create, delete, stage,
commit, or format any file. Do not implement a fix or propose a redesign.
Inspect the current `prism-main` working tree and its currently checked-out
`prism-core` submodule. Do not answer from remembered context, prior sessions,
or documentation when live source is available.

The purpose is to refresh an external staging repository's understanding after
several Composer and dashboard changes landed or were handed off on
2026-07-18 through 2026-07-20. Some work may be committed, staged, unstaged,
partially landed, superseded, or absent. That distinction is part of the
answer.

For every baseline claim below, classify current source as exactly one of:

- `CONFIRMED` — current source matches the claim;
- `CHANGED` — current source differs; quote the current truth;
- `PARTIAL` — only part of the claimed path exists;
- `NOT FOUND` — a named path or symbol is absent after explicit search;
- `GONE` — the file, symbol, route, or behavior no longer exists;
- `NEW` — current source contains relevant behavior not represented here.

## Evidence rules

1. First inspect the repositories; do not infer.
2. Give repository-relative paths from the `prism-main` root.
3. Give current line numbers for every quoted source excerpt.
4. Quote exact signatures, constants, route patterns, decorators, request and
   response schemas, error codes, S3 key builders, and decisive control flow in
   fenced code blocks. Use short connective prose only.
5. For small Composer-specific files, quote the complete current file. For
   large files such as `views.py`, `composer.js`, `rendering.py`, and
   `echart_dashboard.py`, quote complete owning symbols plus enough surrounding
   lines to prove imports, callers, and ordering.
6. If a repository-reading tool warns that a file is too large, continue with
   numbered ranges or use read-only Python through `execute_analysis_script`.
   Do not stop at a size warning.
7. Search for symbols and imports as well as filenames. A file inventory based
   only on `*composer*` names is insufficient.
8. Distinguish committed `HEAD`, staged index, unstaged working tree, and
   untracked content. If a file differs between index and working tree, inspect
   both and treat the working tree as runtime source while reporting the split.
9. Never expose user-authored note text, checklist text, uploaded file bytes,
   signed URLs, tokens, or secrets. Source schemas and redacted test fixtures
   are sufficient.
10. If two copies of a module exist, identify which one is imported at runtime
    and which is stale, generated, archived, or otherwise inactive.

Use this discovery sequence so missing or large files do not collapse coverage:

```text
Phase A — list the five roots
  web/backend_django/news/
  web/prism_site/js/
  web/prism_site/css/
  core/
  prism-core/dashboards/

Phase B — collect signatures for all discovered Python files

Phase C — read small Composer/user-input files in full, subsystem by subsystem

Phase D — for views.py, composer.js, rendering.py, and echart_dashboard.py,
  locate owning symbols first and read numbered ranges around each complete
  definition plus imports/callers

Phase E — search every named symbol's import and call sites; if there are no
  hits, report NOT FOUND and the search terms used
```

Do not substitute a similarly named file or nearest symbol for a missing one.

Use exactly the reply structure below.

## 1. Repository identity, git state, and submodule state

Report:

```text
prism-main root:
prism-main branch:
prism-main HEAD:
prism-main HEAD timestamp:
prism-main status for every file in this prompt:

prism-core path:
prism-core branch or detached state:
prism-core HEAD:
prism-core HEAD timestamp:
prism-main-recorded prism-core gitlink:
gitlink == checked-out prism-core HEAD: yes/no
prism-core status for every file in this prompt:
```

Explicitly inspect for the previously observed failure mode where
`dashboard_composer.py` or `dashboard_composer.js` had an empty staged blob but
real unstaged content. State whether either file is now committed with its real
body.

For every relevant file found in the rest of this prompt, report:

| Path | Exists | Runtime owner | Lines | Bytes | Working-tree SHA-256 | Git state |
|---|---:|---|---:|---:|---|---|

`Git state` must be one of `committed`, `staged`, `unstaged`, `untracked`, or a
precise combination such as `staged + additional unstaged changes`.

## 2. Complete live file inventory

Discover the current implementation rather than assuming this list is
complete. Search all of `web/`, `core/`, `jobs/`, and `prism-core/` for:

```text
composer
dashboard_component
application/x-prism-artifact
PRISM_COMPOSER
prism:dashboard:ready
prism:navigation-hold-change
__prismNavigationHoldCount
dashboard_user_input
user-input
read_dashboard_user_input
user_input/widgets
S3BucketManager
s3_manager
If-Match
If-None-Match
ETag
```

At minimum, resolve the current existence and role of:

```text
web/backend_django/news/views.py
web/backend_django/news/urls.py
web/backend_django/news/composer_views.py
web/backend_django/news/composer_artifacts.py
web/backend_django/news/composer_dashboard_snapshot.py
web/backend_django/news/composer_prompt.py
web/backend_django/news/composer_email.py
web/backend_django/news/dashboard_composer.py
web/backend_django/news/dashboard_user_input.py
web/backend_django/news/tests/...

web/prism_site/js/composer.js
web/prism_site/js/dashboard_composer.js
web/prism_site/css/composer.css
web/prism_site/templates/base.html
web/prism_site/run.py

core/s3_bucket_manager.py

prism-core/dashboards/__init__.py
prism-core/dashboards/rendering.py
prism-core/dashboards/dashboard_user_input.py
prism-core/dashboards/echart_dashboard.py
```

List every additional Composer-, dashboard-component-, user-input-, or
conditional-S3-related file found, including tests, templates, settings,
middleware, helpers, and browser test files.

Then provide an import/call ownership graph:

```text
served dashboard view
  -> dashboard response/global injection
  -> Composer injector
  -> generic Composer browser client
  -> dashboard-specific drag client
  -> Composer Django endpoints
  -> artifact resolver
  -> snapshot validator/merger
  -> shared prompt builder
  -> email or inline agent

persisted user-input browser controller
  -> four Django routes
  -> user-input service/repository
  -> S3 manager conditional operations
  -> current pointer / immutable revision / file objects

Composer user_input submission
  -> canonical widget resolution
  -> trusted read_dashboard_user_input helper
  -> authoritative server_resolution
  -> shared prompt builder
```

Use the actual current symbols on every arrow.

## 3. Recent-change ledger

The external staging baseline records this sequence:

```text
2026-07-18
  rendering.py exported widget metadata, dispatched prism:dashboard:ready,
  and linked the dashboard brand mark to /profile/.

2026-07-19
  widget: user_input landed locally in text/checklist/files modes;
  dashboard_user_input.py supplied the browser controller;
  echart_dashboard.py exported read_dashboard_user_input(...).

2026-07-19 reviewed prism-main baseline
  served user dashboards received a response-only Composer injector;
  owner-only component drag covered six kinds;
  dashboard_component was an inlined prompt body;
  template_sha256 was advisory rather than a TOCTOU reject gate;
  Composer had DND modes, multi-tab state, question-grouped history,
  persisted inline runs, and chunk_type-based SSE classification.

2026-07-20
  rendering.py gained bounded getWidgetSnapshot(widgetId) producers for all
  12 top-level widget kinds;
  dashboard_user_input.py retained revision/hash/source authority metadata;
  a prism-main implementation contract requested all-12 transport,
  validation, merge, history, and user-input server resolution.

2026-07-20 later
  user-input file drag/drop, Outlook .msg support, human timestamps, improved
  checklist/file controls, and user-input chrome were added locally.

2026-07-20 final
  structural dashboard reload gained a neutral navigation-hold handshake:
  __prismNavigationHoldCount + prism:navigation-hold-change.
```

Return a table with one row per item:

| Baseline item | Classification | Current file/symbol | Committed? | Exact current behavior |
|---|---|---|---:|---|

Add rows for every material Composer, dashboard-component, user-input, or S3
change after this baseline.

## 4. `views.py`: dashboard serving, identity, ACL, hash, and injection

From `web/backend_django/news/views.py`, quote the complete current definitions
and direct callers for:

- the canonical served user-dashboard detail view, expected baseline name
  `public_user_dashboard_detail`;
- `_inject_prism_globals`;
- `_canonical_template_hash`;
- `_compute_template_hash`;
- any helper that resolves dashboard owner/id, registry entry, share token,
  viewer ACL, S3 folder, stored HTML key, or response headers;
- every helper reused by `dashboard_user_input.py`;
- every call to `inject_dashboard_composer`.

Answer precisely:

1. Which S3 object does the canonical user-dashboard route read:
   `dashboard.html`, `index.html`, or another key?
2. What are all fallback keys, if any?
3. Does it read bytes, decode text, strip NUL padding, or transform the stored
   document before injection?
4. What is the exact order of:

   ```text
   authentication
   ACL/share resolution
   S3 HTML read
   PRISM_* global injection
   Composer injection
   response construction
   ```

5. Quote the complete current `PRISM_*` global block. Resolve at least:

   ```text
   PRISM_VIEWER
   PRISM_DASHBOARD_AUTHOR
   PRISM_DASHBOARD_OWNER
   PRISM_DASHBOARD_ID
   PRISM_DASHBOARD_SHARED
   PRISM_DASHBOARD_SHARE_MODE
   PRISM_DASHBOARD_SHARE_TOKEN
   PRISM_TELEMETRY_ENDPOINT
   PRISM_IS_OBSERVATORY
   PRISM_TEMPLATE_HASH
   ```

6. Is `PRISM_DASHBOARD_AUTHOR` always the canonical S3 owner? Is
   `PRISM_DASHBOARD_OWNER` identical, and which one does each browser module
   consume?
7. Which current manifest/template bytes are hashed, and what exact
   canonicalization is used? Quote code proving NUL handling, UTF-8 handling,
   JSON parsing, key sorting, separators, and SHA-256.
8. Is this hashing algorithm byte-for-byte equivalent to the one used by
   `composer_artifacts.py`? If code is duplicated, show both definitions and
   any drift.
9. Does `inject_dashboard_composer` receive
   `FEATURE_FLAGS["enable_inline_chat"]`, a constant, or another value?
10. Which route families receive Composer, and which remain excluded?

Fill this current route matrix:

| URL pattern | View | HTML source | ACL source | Globals injected | Composer injected | Stored bytes mutated |
|---|---|---|---|---:|---:|---:|

Include canonical user, profile alias, community alias, shared/link,
Observatory, developer, report-server, `file://`/download, and any new route.

Quote response `Content-Type`, CSP, framing, cache, and other security headers
that affect injected scripts or same-origin API calls.

## 5. `dashboard_composer.py`: response-only injector

Quote the complete current
`web/backend_django/news/dashboard_composer.py`.

Report:

- exact `inject_dashboard_composer` signature and docstring;
- idempotence marker and duplicate-injection behavior;
- insertion location and behavior when `</body>` is absent;
- exact injected ordering of scoped tokens, CSS, root, globals, generic
  Composer JavaScript, and dashboard Composer JavaScript;
- all globals written by the injector;
- exact value of `PRISM_COMPOSER_DND_MODE`;
- how `enable_inline_chat` is serialized;
- all `.prism-composer-drag-grip` CSS;
- whether the injector includes any navigation-hold code;
- whether it ever writes S3 or changes stored `dashboard.html`;
- all current callers.

Confirm or correct this baseline block:

```text
1. scoped --gs-uitk-* tokens on #prism-composer-root
2. /static/css/composer.css
3. <div id="prism-composer-root"></div>
4. window.PRISM_COMPOSER_INLINE_CHAT = <site flag>
5. window.PRISM_COMPOSER_DND_MODE = "dashboard_components"
6. deferred /static/js/composer.js
7. deferred /static/js/dashboard_composer.js
```

Also quote and resolve the ordinary Portal mount:

- the complete Composer block in `web/prism_site/templates/base.html`;
- the complete current `FEATURE_FLAGS` definition in
  `web/prism_site/run.py`, including committed versus working-tree values;
- every template/view that extends or bypasses that base mount;
- whether Portal and compiled-dashboard delivery load the same
  `composer.js` and `composer.css` bytes;
- the Composer-specific selector inventory in `composer.css`, grouped by
  root/pill/panel, DND/drop cards, tabs, resize, inline chat, thinking/final
  response, history/replay, errors, and dashboard drag grips;
- dead selectors or JavaScript class names with no CSS owner, and CSS selectors
  with no current JavaScript/template writer.

Quote complete CSS rules only for dashboard injection/grips, snapshot or
persistence errors, DND-mode visibility, tabs, inline stream state, and
history/replay. For the rest, give exact selector names and line ranges rather
than reproducing the entire stylesheet.

## 6. `dashboard_composer.js`: dashboard-specific drag producer

Quote the complete current
`web/prism_site/js/dashboard_composer.js`.

Then extract and explain with exact source:

1. The two-latch startup and bind-once mechanism.
2. The owner gate and exact identity globals compared.
3. The closed `ALLOWED_KINDS` set and its order.
4. Whether the live set is still six kinds or now all 12:

   ```text
   chart, kpi, table, data_grid, pivot, stat_grid,
   tool, user_input, markdown, note, image, divider
   ```

5. Top-level eligibility: does it bind only widgets represented by
   `[data-tile-id]` and `window.DASHBOARD.widgets`, or can nested content
   accidentally bind?
6. Exact natural handles by kind:

   ```text
   .tile-header
   .kpi-header
   .note-head
   ```

7. Exact injected-grip behavior for headerless markdown, untitled image, and
   divider, including idempotence and non-owner behavior.
8. `INTERACTIVE_SELECTOR` and every descendant excluded from drag initiation.
9. Whether snapshot capture occurs synchronously at every `dragstart`.
10. Exact call to `window.DASHBOARD.getWidgetSnapshot(widgetId)`.
11. Exact preflight for id, kind, schema, size, and capture errors.
12. Exact UTF-8 byte calculation.
13. Exact `application/x-prism-artifact` payload written to `DataTransfer`.
14. Label-prefix map and title-selection precedence.
15. `effectAllowed`, drag image behavior, selection suppression, and cleanup.
16. Visible error handoff to generic Composer, including exact error codes.
17. Proof that this file does not mutate manifest data, widget definitions,
    stored HTML, or S3.

The expected all-12 drag payload has these ten top-level fields:

```json
{
  "type": "dashboard_component",
  "id": "widget-id",
  "path": "users/owner/dashboards/dashboard-id",
  "label": "Kind: Title",
  "dashboard_id": "dashboard-id",
  "widget_kind": "kind",
  "template_sha256": "64hex",
  "snapshot_schema_version": 1,
  "snapshot_bytes": 123,
  "view_snapshot": {}
}
```

Classify the live payload as `CONFIRMED`, `PARTIAL`, or `CHANGED`, and quote the
actual object literal.

## 7. `composer.js`: generic Composer state, transport, streaming, and reload hold

`web/prism_site/js/composer.js` is large. Quote the complete definitions of
every symbol named below plus all direct mutation/call sites.

### 7.1 Modes, flags, and initialization

Report:

- `PRISM_COMPOSER_DND_MODE` readers;
- legacy `PRISM_COMPOSER_DISABLE_DND` handling;
- `standard`, `disabled`, and `dashboard_components` behavior;
- `PRISM_COMPOSER_INLINE_CHAT` handling;
- exact Composer root lookup and initialization order;
- file-upload visibility and allowed MIME artifact types per mode;
- generic drag-source scanning and `MutationObserver` behavior per mode.

Fill:

| DND mode | Drop target | File upload | Generic source scan | Accepted artifact types |
|---|---:|---:|---:|---|

### 7.2 State and persistence

Quote:

- all storage keys;
- complete default state;
- complete per-tab state;
- tab-list/active-tab state;
- attachment/artifact normalization;
- serialization and restoration;
- legacy-state migration;
- panel-size persistence;
- duplicate-artifact identity and replacement behavior.

State whether storage uses `sessionStorage`, `localStorage`, or both. For
`dashboard_component`, list every field preserved at each transition:

```text
drag parse
  -> normalized artifact
  -> optimistic card
  -> artifact-info merge
  -> active tab
  -> tab switch
  -> storage write
  -> storage restore
  -> fire-off POST
  -> chat POST
  -> history record
  -> replay
```

Prove whether `snapshot_schema_version`, `snapshot_bytes`, and the nested
`view_snapshot` survive unchanged. Quote any copy/allowlist that can strip
fields. Report quota or serialization failures and whether any memory-only or
canonical-only fallback exists.

### 7.3 Artifact-info preview

Quote `resolveArtifactInfo` and response merge logic. Report:

- exact query parameters sent for `dashboard_component`;
- whether the three snapshot fields are omitted from the GET;
- which card fields the response may update;
- whether an older in-flight response can overwrite a newer snapshot;
- whether `template_sha256` is ever silently upgraded.

### 7.4 Fire-off, inline chat, history, and replay

Quote exact request builders and request JSON schemas for fire-off and chat.
Quote history/replay artifact serialization. Resolve:

- seven current Composer endpoints;
- question-grouped `runs[]` history;
- `mode="email"` and `mode="inline"`;
- completed inline transcript persistence;
- `mode="view"` replay versus run replay;
- `question_id` versus legacy `supersedes_id`;
- whether replay reuses the stored capture or recaptures the browser.

### 7.5 Navigation-hold handshake

The latest external canonical ECharts payload uses the neutral host contract:

```javascript
window.__prismNavigationHoldCount
window.dispatchEvent(new CustomEvent(
  'prism:navigation-hold-change',
  {detail: {count: count}}
));
```

Report whether live `composer.js` implements it. Quote:

- `_streams` declaration and shape;
- initialization of `__prismNavigationHoldCount`;
- the publisher function;
- every `_streams` create, delete, replacement, and reset;
- the publisher call immediately following each mutation;
- `_finishChat` ordering;
- tab-close abort;
- chat-back abort;
- error/disconnect/abort cleanup;
- multi-tab behavior with two simultaneous streams.

The transition to count zero must occur only after final response rendering and
history persistence are safe. Confirm or correct that ordering.

Also search for the superseded Composer-specific names:

```text
__prismComposerStreaming
prism:composer-streaming-change
```

State whether either remains live and whether `composer.js` matches the
installed `rendering.py` listener. A mixed pair is a runtime defect; report it
plainly.

### 7.6 Visible errors

Quote `ComposerManager.reportArtifactError` or its current equivalent. List
browser-visible codes, especially:

```text
snapshot_api_unavailable
snapshot_capture_failed
snapshot_persistence_failed
```

State whether capture/persistence failures block card creation and send, or
silently downgrade.

## 8. `composer_views.py`: every endpoint and side-effect boundary

Quote all Composer URL patterns from `urls.py`, then provide one row per view:

| Route | View | Decorators | Method | Auth | CSRF | Request keys | Success shape | Error statuses |
|---|---|---|---|---|---|---|---|---|

Resolve at least:

```text
/api/composer/fire-off/
/api/composer/chat/
/api/composer/history/
/api/composer/replay/
/api/composer/preview/
/api/composer/delete/
/api/composer/artifact-info/
```

Also quote and classify the separate identity helpers
`/api/users/me` and `/api/users/search/`, including methods and response
schemas. State whether Composer depends on either and whether either can mutate
identity, recipient, or dashboard state.

For `web/backend_django/news/composer_views.py`, quote complete definitions
for:

- every public endpoint;
- request JSON parsing/normalization;
- authenticated Kerberos resolution;
- artifact resolution helpers;
- snapshot-error response mapping;
- aggregate snapshot-byte validation;
- prompt construction;
- email dispatch;
- inline-agent construction;
- SSE frame construction and stream generator;
- history persistence;
- replay;
- disconnect/abort cleanup;
- development notification email, if still present.

Answer:

1. Does artifact-info call `read_artifact_content(..., purpose="preview")`?
2. Do fire-off, chat, and run replay call
   `read_artifact_content(..., purpose="submit")`?
3. Are all artifacts resolved before any email, LLM/agent, SSE response, or
   success-history side effect?
4. Is the aggregate 1 MiB check based on server-recomputed canonical
   `view_snapshot` bytes only?
5. Does chat validation complete before `StreamingHttpResponse` is opened?
6. How is `DashboardSnapshotError` converted to JSON and HTTP status?
7. Do email and inline paths persist the complete normalized artifact?
8. What exact SSE event grammar and headers are current?
9. Does final-response classification use `chunk_type == "response"`?
10. Are tool-call events suppressed, emitted, or persisted?
11. Does `_finishChat` on the browser release the navigation hold only after
    the matching server/history lifecycle is complete?
12. Are any Composer endpoints still `@csrf_exempt`? Quote each occurrence.

## 9. `composer_artifacts.py`: complete resolver and dashboard-component branch

Quote:

- complete module-level routing constants;
- exact `read_artifact_content` signature and docstring;
- complete return schema;
- every caller and import site;
- exact handling for every accepted artifact type.

Fill:

| Artifact type | Canonical files/S3 keys read | Inline body | Reference only | Attachments | Live URL | Preview behavior |
|---|---|---:|---:|---|---|---|

For `dashboard_component`, quote the complete branch and every helper it calls.
Resolve:

1. Current `_ALLOWED_KINDS` and `_KIND_PREFIX`.
2. Whether `purpose` exists and is limited to `preview|submit`.
3. Server-derived owner/folder construction from authenticated Kerberos.
4. Treatment of client `art_path`, `path`, label, owner, and dashboard id.
5. Exact current `manifest_template.json` read and hash.
6. Top-level traversal rules for flat and tabbed layouts.
7. Missing, duplicate, nested-only, and kind-mismatch behavior.
8. Stale `template_sha256` behavior.
9. Call into `composer_dashboard_snapshot.py`.
10. Call into `read_dashboard_user_input`.
11. Exact merged `content_summary`.
12. Exact `attachment_paths`, `s3_paths`, and file-reference behavior.
13. Whether binary bytes, screenshots, HTML, datasets, or review receipts
    enter the component body.
14. The historical `index.html` versus canonical `dashboard.html` issue for
    whole-dashboard artifacts. State the current key and whether it exists in
    current dashboard folders.

Preview must remain small. Submit must remain authoritative. State plainly if
the live code still has one unsplit resolver behavior.

## 10. `composer_dashboard_snapshot.py`: schemas, validation, and merge

If `web/backend_django/news/composer_dashboard_snapshot.py` is absent, say
`GONE/NOT IMPLEMENTED` and skip invented behavior. If present, quote the
complete file.

At minimum, report exact current values and definitions for:

```text
SNAPSHOT_SCHEMA_VERSION
COMPONENT_SCHEMA_VERSION
ALLOWED_WIDGET_KINDS
MAX_VIEW_SNAPSHOT_BYTES
MAX_TURN_VIEW_SNAPSHOT_BYTES
MAX_STRING_BYTES
MAX_JSON_DEPTH
LANDED_LIMITS
RECURSIVE_PROTOTYPE_KEYS
FORBIDDEN_CONTROL_KEYS
ERROR_HTTP_STATUS
DashboardSnapshotError
canonical_view_snapshot_bytes
validate_view_snapshot
merge_widget_snapshot
validate_turn_view_snapshot_size
```

Report:

- exact required envelope keys;
- unknown-key behavior;
- recursive JSON/prototype/control-key validation;
- finite-number validation;
- depth and string bounds;
- exact per-kind schemas for all 12 kinds;
- exact source-ref schemas;
- truncation ledger validation;
- browser advisory bytes versus server canonical bytes;
- per-component and per-turn enforcement;
- artifact/snapshot/canonical identity checks;
- explicit per-kind merge construction;
- template `current|stale` classification;
- `user_input_state` requirements;
- side effects, if any.

Fill the exact current error table:

| Error code | HTTP | Raised by | Details schema |
|---|---:|---|---|

Resolve at least the baseline codes:

```text
snapshot_missing
snapshot_schema_unsupported
snapshot_malformed
snapshot_forbidden_key
snapshot_depth_exceeded
snapshot_string_oversized
snapshot_truncation_invalid
snapshot_identity_mismatch
dashboard_widget_not_found
dashboard_widget_ambiguous
dashboard_widget_kind_not_allowed
snapshot_component_oversized
snapshot_turn_oversized
user_input_resolution_failed
user_input_source_ref_unauthorized
```

## 11. `composer_prompt.py` and `composer_email.py`

Quote the complete current `composer_prompt.py` and the complete current
`composer_email.py`.

Report:

- exact `_INLINE_BODY_TYPES`;
- exact `_REFERENCE_ONLY_TYPES`;
- exact `_NON_ATTACHED_TYPES`;
- `build_composer_prompt` signature and complete body;
- `compose_email_body` signature and complete body;
- `_build_chat_prompt` call site;
- section order and headings;
- exact dashboard-component framing;
- treatment of canonical definition, captured view, source references,
  truncation, template status, and `server_resolution`;
- attachment-set construction;
- whether user-input file bytes are fetched or attached;
- whether screenshot language exists;
- whether email and inline chat use one prompt SSOT.

For email composition and dispatch, also report:

- exact public function signatures and callers;
- authenticated sender and self-recipient derivation;
- whether client-supplied primary recipients are ignored;
- CC normalization, UserRegistry lookup, and closed/unresolvable-user handling;
- exact subject sentinels and subject derivation;
- attachment and S3-path union/deduplication;
- MIME/content handling and size guards;
- SMTP/email transport call;
- failure handling and returned identifiers;
- whether persistence/history lives here or in `composer_views.py`;
- any developer-notification copy of the exact inline prompt.

Quote one redacted exact prompt fixture from current tests for a
`dashboard_component` and one for `user_input` files mode.

## 12. Parent Django `dashboard_user_input.py`: complete HTTP/service contract

If `web/backend_django/news/dashboard_user_input.py` is absent, state that
plainly. If present, quote the complete current file.

Then quote its URL registrations and all settings/middleware it depends on.
Provide:

| Route | View | Method | Decorators | Auth/ACL helper | Request schema | Success schema | Error schema |
|---|---|---|---|---|---|---|---|

Resolve these expected routes:

```text
GET  /api/dashboard/user-input/
POST /api/dashboard/user-input/save/
POST /api/dashboard/user-input/upload/
GET  /api/dashboard/user-input/download/
```

For the complete module, identify and quote:

- constants and identifier regexes;
- exception classes and HTTP mapping;
- canonical dashboard resolver;
- read-ACL and owner-write checks;
- manifest widget resolver;
- seed synthesis;
- mode-specific validators;
- JSON canonicalization and SHA-256;
- current-pointer reader including ETag;
- immutable revision writer;
- conditional pointer writer;
- file upload streamer/hasher;
- filename normalizer;
- MIME/content inspectors;
- OOXML and Outlook `.msg` inspection;
- image and text validation;
- file removal/tombstone writer;
- active-file resolver;
- download response;
- response serializer;
- cache/security headers;
- orphan/lifecycle-cleanup recording.

Answer:

1. Is normal Django CSRF enforced on both POST routes?
2. Does any route use `@csrf_exempt`?
3. Can an authorized non-owner read and download?
4. Can any non-owner write?
5. Is authorization delegated to the same helper as the detail view?
6. Are `folder`, S3 prefix, object key, revision key, and download key rejected
   from browser input?
7. Is `mode` revalidated against the current manifest?
8. Is seed returned without a write?
9. Does first save require expected revision null?
10. Are conflicts returned as HTTP 409 with authoritative current state?
11. Are uploads sequential only in the browser, or is server concurrency also
    protected?
12. Is the 25,000,000-byte limit enforced while streaming or after buffering?
13. Is `.msg` currently accepted and actually inspected as an Outlook message?
14. Does download always use attachment disposition plus `nosniff` and
    `private, no-store`?
15. Are user text, filenames, bytes, tokens, and URLs excluded from logs?
16. Which request/upload-size settings permit multipart overhead?
17. Does the compiled browser controller call the user-input GET on
    `file://`, email/downloaded HTML, presigned-S3 HTML, Observatory, or
    developer delivery? Quote every protocol/surface guard.
18. How is each browser `download_url` constructed, and does the exported
    `USER_INPUT_DOWNLOAD_API` constant have a live caller?

Report exact request and response schemas, including all fields returned to the
browser. Resolve whether `content_sha256` is included in GET/save/upload
responses; the current ECharts snapshot producer expects it in browser state.

## 13. `core/s3_bucket_manager.py`: complete production S3 contract

Quote the complete current `core/s3_bucket_manager.py`, including imports,
configuration, class definitions, singleton construction, and helper
functions. If it delegates to another transport module, quote that module too.

Report the exact signature, return type/shape, serialization behavior, and
exceptions for every public method. Resolve at least:

```text
get
put
exists
list
delete
move
```

Discover and report every additional method related to:

```text
ETag
object metadata
head
conditional put
If-Match
If-None-Match
presigned download/upload
streaming
copy
atomic create/replace
```

For each method used by persisted user input, quote the exact call site in
`dashboard_user_input.py` and the exact manager implementation it reaches.

Answer precisely:

1. What AWS/boto client/resource is used?
2. How is the bucket selected and configured?
3. Are keys normalized, prefixed, or path-validated?
4. Does `get(path)` return raw bytes, decoded text, JSON, or another wrapper?
5. How is an object's ETag obtained together with the exact bytes read?
6. Are ETag quotes preserved or stripped?
7. What is the exact conditional-write API?
8. Which underlying `put_object` parameters carry `IfMatch` and
   `IfNoneMatch`?
9. Does immutable-object creation use `If-None-Match: *`?
10. Does pointer replacement use `If-Match: <read ETag>`?
11. What exact exception is raised for an S3 precondition failure?
12. Where is that exception mapped to `revision_conflict` HTTP 409?
13. Are transport/auth/timeouts/retries configured?
14. Does `put` auto-serialize dict/string/bytes, and with what JSON encoding?
15. Does any code NUL-pad stored bytes?
16. Does `list(prefix)` return `List[str]`, boto-style dicts, or another
    shape?
17. Is delete idempotent?
18. Is move atomic, copy-then-delete, or another operation?
19. Are server-side encryption, content type, cache control, or object ACLs
    set?
20. Are user-input downloads server-streamed or presigned?
21. Are user-input uploads server-mediated or direct-to-S3/presigned?
22. Is the conditional API genuinely one S3 conditional request, or a
    read-then-unconditional-write race?
23. What test double exercises the same ETag/precondition semantics?

The pre-2026-07-20 local staging stub exposed only:

```python
get(path)
put(data, path)
exists(path)
list(prefix="")
delete(path)
move(src, dst)
```

Do not assume production still has only that surface. If conditional operations
were added, report their exact names and signatures. If they were not added,
state plainly that the persisted-input concurrency contract is not atomic.

## 14. Actual S3 persistence model for `user_input`

Using source and tests, not user content, report the exact current key tree.
Confirm or correct:

```text
users/{owner}/dashboards/{dashboard_id}/user_input/
└── widgets/
    └── {widget_id}/
        ├── current.json
        ├── revisions/{revision_id}.json
        ├── files/{file_id}/blob
        ├── files/{file_id}/metadata.json
        └── tombstones/{file_id}/{revision_id}.json
```

Quote the exact key-builder functions and identifier validators. Then quote
the exact current JSON schema written for:

1. `current.json`;
2. immutable revision;
3. file metadata;
4. tombstone;
5. any orphan/cleanup record;
6. any schema/version manifest not listed above.

For each object, report:

| Object | Mutable? | Create precondition | Replace precondition | Reader | Writer | Retention/cleanup |
|---|---:|---|---|---|---|---|

Trace exact mutation ordering for:

```text
first text/checklist save
subsequent text/checklist save
file upload
active-file removal
two concurrent writers
pointer-write failure after immutable objects were created
```

Resolve:

- UUID version and canonical string rules;
- parent-revision linkage;
- canonical JSON algorithm for `content_sha256`;
- whether revision/file/tombstone objects are ever overwritten or deleted;
- whether unlinked losing-write objects are recorded and cleaned;
- whether refresh/build/archive/version-restore can touch `user_input/`;
- whether dashboard deletion removes this subtree;
- whether widget rename or mode change migrates state;
- whether list/read consistency assumptions are documented or tested.

## 15. Installed `read_dashboard_user_input` helper

From the live installed `prism-core/dashboards/echart_dashboard.py`, quote the
complete definitions of:

```text
_canonical_dashboard_identity
_s3_relative_listing
_decode_json_object
_user_input_content_sha256
_validate_user_input_uuid
read_dashboard_user_input
```

Also quote its exports from both `echart_dashboard.py::__all__` and
`dashboards/__init__.py`.

Report:

- exact public signature and docstring;
- manager resolution;
- requested-one versus list-all behavior;
- missing-state behavior;
- pointer identity validation;
- revision-key reconstruction;
- mode and parent validation;
- content hash validation;
- file metadata/blob identity, size, and SHA validation;
- `object_key` output;
- tombstone behavior under `include_deleted=True`;
- exception types/messages;
- whether it mutates S3 or consults Cabinet;
- whether it reads complete file bytes merely to verify SHA-256.

Then identify every current production caller. Distinguish analysis/sandbox
consumers from Composer's server resolver.

## 16. End-to-end Composer resolution for a `user_input` component

Trace one owner dragging a files-mode `user_input` widget into Composer and
sending it through inline chat. Quote the exact live symbol at every step:

```text
manifest definition
  -> compiled PAYLOAD.userInputs entry
  -> authenticated GET of current persisted state
  -> USER_INPUT_STATE authority metadata
  -> rendering.getWidgetSnapshot(widgetId)
  -> dashboard_composer.js drag payload
  -> composer.js normalized/stored artifact
  -> chat POST
  -> composer_views preflight
  -> composer_artifacts canonical widget resolve
  -> read_dashboard_user_input(server-derived folder, widget_id, ...)
  -> composer_dashboard_snapshot validation + merge
  -> composer_prompt inlined body
  -> agent prompt
  -> history/replay record
```

At each step, state which fields are:

```text
browser-authoritative current-view evidence
server-authoritative canonical definition
server-authoritative persisted user content
display-only hints
comparison-only revision/hash evidence
server-rebuilt authorized source references
forbidden binary/authority fields
```

Resolve these expected rules:

1. Browser snapshot contains mode, phase, revision/hash/source metadata, counts,
   and bounded file metadata, but no text body, checklist item text, object key,
   download URL, or bytes.
2. Server derives the folder from authenticated owner plus dashboard id.
3. Server calls `read_dashboard_user_input(..., include_deleted=False)`.
4. Missing persisted state synthesizes canonical seed in memory without write.
5. Captured/current revision and hash are classified `seed`, `current`, or
   `stale`.
6. Current trusted server content always wins.
7. Active file object keys are reconstructed and authorized server-side.
8. Binary bytes never enter artifact, prompt, browser storage, history, replay,
   email, or inline-agent input.
9. Missing/invalid required snapshots fail; there is no canonical-only or
   client-content fallback.
10. Artifact-info GET remains a small canonical preview and does not return
    persisted user content.

Quote the exact live `server_resolution` schema for text, checklist, and files
mode. Quote the exact server source-ref schema. Explain whether user-input
trusted content is inside or outside snapshot byte limits and what separate
prompt-body guard applies.

## 17. Installed ECharts producer and candidate comparison

The current external canonical candidate files measured on 2026-07-21 are:

| Candidate destination | Bytes | `wc -l` | SHA-256 |
|---|---:|---:|---|
| `prism-core/dashboards/rendering.py` | 730939 | 18776 | `b4d5e4c2686d4c3235d0393778688c8bd33bdf1042d16765b2fee0081552ebfa` |
| `prism-core/dashboards/dashboard_user_input.py` | 26466 | 847 | `ea680ea6bbd54759ac5b0333e847d95a637db6da59a4ad0552ad0c4964bc4551` |
| `prism-core/dashboards/echart_dashboard.py` | 900772 | 21759 | `979d2a6f05700b022d812e298b88e1c2298abea16d380669c6c6143541f8a5cf` |
| `prism-core/dashboards/__init__.py` | 9836 | 269 | `d6b98506c5d795f3002837b4e990eb190822d413a3c2000e38fb9d8add33f8ce` |

These hashes describe the external canonical candidate, not an installed
parity claim. Compute the same measurements for the live installed files and
classify each:

```text
BYTE-IDENTICAL
DIFFERS
MISSING
```

For every `DIFFERS`, give a semantic diff focused on Composer, snapshots,
user input, S3 reads, and the navigation-hold handshake.

From live `rendering.py`, quote:

- `TOP_LEVEL_WIDGET_META`;
- complete `WIDGET_SNAPSHOTTERS`;
- `getWidgetSnapshot`;
- `window.DASHBOARD` export;
- `prism:dashboard:ready` dispatch and exact ordering after tools/user inputs;
- `_snapshotUserInput`;
- snapshot limits and truncation accounting;
- live structural-reload branch and listener.

Confirm whether all 12 kinds are implemented and whether the payload remains
neutral: no Composer MIME, route, card, prompt, or drag-grip policy.

The immediately prior reload implementation used:

```text
__prismComposerStreaming
prism:composer-streaming-change
```

The latest candidate replaced it with:

```text
__prismNavigationHoldCount
prism:navigation-hold-change
```

State which pair the installed file uses and whether it matches current
`composer.js`.

From live installed `dashboard_user_input.py`, quote:

- endpoint constants;
- valid modes and limits;
- identity construction;
- full server-state retention;
- human timestamp formatting;
- file picker/drop behavior;
- Outlook `.msg` accept behavior;
- conflict and unavailable states;
- browser storage behavior;
- exported globals.

## 18. Security and trust-boundary audit

Build this matrix from current source:

| Boundary | Client-supplied | Server-derived | Validation | Failure |
|---|---|---|---|---|
| authenticated identity | | | | |
| dashboard owner/id | | | | |
| read ACL | | | | |
| write ACL | | | | |
| widget id/kind/mode | | | | |
| template hash | | | | |
| current-view snapshot | | | | |
| persisted revision/hash | | | | |
| file id/object key | | | | |
| S3 ETag | | | | |
| prompt body | | | | |

Explicitly resolve:

- whether any client path chooses an S3 key;
- cross-user and cross-dashboard claims;
- owner-only drag versus shared-view read access;
- CSRF on Composer and user-input endpoints;
- share/link tokens and write authority;
- prototype/control-key defense;
- filename/path traversal;
- uploaded active content;
- response HTML injection safety;
- logging of sensitive data;
- same-origin/CSP assumptions;
- presigned URL leakage;
- TOCTOU behavior for canonical template and persisted current pointer.

Search both browser and server Composer code for:

```text
describe_dashboard
apply_manifest_operations
review_dashboard
acknowledge_dashboard_review
publish_dashboard
launch_clean_refresh
```

State whether any is callable through Composer. The current product boundary is
read-only component context; any manifest, layout, publish, or refresh mutation
bridge is a net-new Stage 3 capability and must be reported explicitly.

Do not give generic security advice. Quote current enforcement.

## 19. Tests and executable evidence

Inventory every current test touching:

```text
dashboard Composer injection
dashboard_composer.js owner/all-kind drag
composer.js snapshot preservation
artifact preview/submit split
snapshot schemas and bounds
Composer endpoint preflight
history and replay
navigation-hold streaming
dashboard user-input routes
ACL and CSRF
conditional S3 races
upload inspection
read_dashboard_user_input integrity
refresh/build preservation
owned and shared browser smoke
```

Check at least these expected files or their discovered current equivalents:

```text
web/backend_django/news/tests/test_composer_dashboard_snapshot.py
web/backend_django/news/tests/test_composer_artifacts.py
web/backend_django/news/tests/test_composer_views.py
web/backend_django/news/tests/test_dashboard_composer.py
web/backend_django/news/tests/test_dashboard_user_input.py
the live JavaScript or Playwright dashboard-Composer test surface
```

For each, report:

| Test path | Test class/name | What it proves | Committed/staged/unstaged | Last known result available in source/logs |
|---|---|---|---|---|

Do not claim a test passed merely because it exists. Do not run a broad suite
for this extraction. If recent checked-in or available local test output exists,
quote its exact command, timestamp, and result. Otherwise say `not established
by this extraction`.

Identify required behavior that has no test.

## 20. Current end-to-end verdict

Return these status rows:

| Capability | Status | Exact evidence | Blocking gap |
|---|---|---|---|
| Composer mounted on served user dashboards | | | |
| Stored dashboard bytes remain Composer-free | | | |
| Six-kind baseline drag | | | |
| All-12 drag handles/grips | | | |
| All-12 neutral current-view producer | | | |
| Snapshot preserved through tabs/storage/POST/history/replay | | | |
| Server snapshot validation and per-kind merge | | | |
| Shared prompt builder for email/chat | | | |
| Persisted user-input GET/save/upload/download | | | |
| Atomic conditional S3 writes | | | |
| Composer authoritative user-input resolution | | | |
| Authorized file refs without binary embedding | | | |
| Neutral streaming/reload hold handshake | | | |
| Owned browser smoke | | | |
| Shared/non-owner browser smoke | | | |
| Candidate/installed ECharts byte parity | | | |

Then close with exactly these subsections:

### Confirmed current architecture

Only facts proven from current source.

### Corrections to the 2026-07-20 baseline

For each correction, cite the prompt section and current file/line.

### Net-new changes after the baseline

Include committed and uncommitted changes.

### Half-landed or internally mismatched work

Include mismatched browser/server schemas, route registration gaps, staged versus
unstaged splits, stale duplicate files, mismatched reload event names, missing
conditional S3 primitives, missing tests, and checkout/gitlink mismatch.

### Documentation fields that must be updated

Give a field-level patch checklist grouped under:

```text
projects/echarts/dev/specs/composer_dashboard_stack.md
projects/echarts/dev/specs/dashboard_user_input.md
projects/echarts/README.md
projects/echarts/dev/notes.md
staging/README.md
```

Do not draft prose for those files. List only the specific claims/sections that
the evidence says are stale.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end naming exactly what could not be resolved, what paths or
symbols were tried, and why.
