# Persisted dashboard user input

## Scope and ownership

`widget: "user_input"` is a dashboard-authored input surface with three modes:
`text`, `checklist`, and `files`. Its manifest definition is compiled with the
dashboard, while viewer-authored state is stored separately under the
dashboard's S3 subtree.

The ECharts payload owns:

- manifest validation and rendering;
- the browser controller and visible save states;
- the read-only `read_dashboard_user_input(...)` helper;
- the API contract exercised by the local parity harness.

`prism-main` owns:

- authenticated GET, save, upload, and download views;
- dashboard ACL resolution and owner-only write enforcement;
- conditional S3 writes, upload inspection, and response streaming.

No browser write may modify `manifest_template.json`, `manifest.json`,
`dashboard.html`, dashboard definition history, or the dashboard registry.

```text
manifest_template.json                  user-authored state
└─ widget: user_input                   user_input/widgets/<widget_id>/
   ├─ mode                                 ├─ current.json
   └─ seed                                 ├─ revisions/<revision_id>.json
          │                                ├─ files/<file_id>/{blob,metadata.json}
          ▼                                └─ tombstones/<file_id>/<revision_id>.json
compiled controller ── authenticated API ────────────────────────────────┘
          │
          └─ visible idle / loading / dirty / saving / saved /
             conflict / unavailable state
```

## Manifest contract

Every `user_input` widget has a stable `id`. The id is the persistence key and
must match `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`. Renaming the widget creates a
distinct empty persisted surface; state is not migrated implicitly.

### Common fields

| Field | Required | Contract |
|---|---:|---|
| `widget` | yes | Exact value `"user_input"` |
| `id` | yes | Stable path-safe id matching the expression above |
| `mode` | yes | One of `"text"`, `"checklist"`, `"files"` |
| `w` | no | Existing grid-width contract; defaults as other non-chart widgets |
| `title` | no | Visible heading; plain text |
| `description` | no | Short plain-text instruction |
| `placeholder` | no | `text` mode only; plain text, at most 500 characters |
| `rows` | no | `text` mode only; integer from 3 through 30, default 8 |
| `seed` | no | Mode-specific first-load state; never overwrites persisted state |

Unknown mode-specific fields are rejected.

### Text mode

```python
{
    "widget": "user_input",
    "id": "weekend_notes",
    "mode": "text",
    "w": 6,
    "title": "Weekend notes",
    "description": "Capture the items to revisit on Monday.",
    "placeholder": "Write a note…",
    "rows": 10,
    "seed": {"text": ""},
}
```

`seed` is either omitted or exactly `{"text": <string>}`. The UTF-8 encoded
seed may not exceed 250,000 bytes.

Persisted content is:

```json
{"text": "User-authored plain text"}
```

The browser renders and edits this value as plain text. Markdown and HTML are
not interpreted.

### Checklist mode

```python
{
    "widget": "user_input",
    "id": "reading_list",
    "mode": "checklist",
    "w": 6,
    "title": "Reading and listening",
    "seed": {
        "items": [
            {"id": "weekend-podcast", "text": "Listen to the podcast", "checked": False},
            {"id": "strategy-note", "text": "Read the strategy note", "checked": True},
        ],
    },
}
```

`seed` is either omitted or exactly `{"items": [...]}`. Each item has exactly:

| Field | Contract |
|---|---|
| `id` | Unique stable id matching `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$` |
| `text` | Non-empty plain text, at most 2,000 UTF-8 bytes |
| `checked` | Boolean |

A checklist contains at most 500 items. List order is the display order. The
browser may add, edit, reorder, check, uncheck, and remove items. Persisted
content has the same `{"items": [...]}` shape.

### Files mode

```python
{
    "widget": "user_input",
    "id": "knowledge_drop",
    "mode": "files",
    "w": 12,
    "title": "Knowledge files",
    "description": "Upload supporting documents for this dashboard.",
    "seed": {"files": []},
}
```

`seed` is omitted or exactly `{"files": []}`. A manifest cannot seed file
paths, URLs, bytes, or metadata. A files widget may contain at most 100 active
files. Each file is at most 25,000,000 bytes.

Persisted revision content is:

```json
{
  "files": [
    {
      "file_id": "3f75f764-2e4c-4789-841c-b700a812db46",
      "original_filename": "Weekend Reading.pdf",
      "normalized_filename": "Weekend Reading.pdf",
      "size_bytes": 184239,
      "sha256": "64 lowercase hexadecimal characters",
      "detected_mime": "application/pdf",
      "uploaded_at": "2026-07-20T03:30:00.000000Z",
      "uploaded_by": "owner"
    }
  ]
}
```

The browser response adds `download_url`; it never exposes an S3 object key.
The Python read helper adds `object_key` for Prism's trusted server-side use.

## Seed and first-save semantics

Seed state is definition data, not persisted user data.

1. GET reads the widget's `current.json`.
2. If no current pointer exists, the API returns the manifest seed with
   `source: "seed"` and `revision_id: null`.
3. The browser remains clean; merely viewing a seed does not write it.
4. The first save must send `expected_revision_id: null`.
5. The server creates the first immutable revision and conditionally creates
   `current.json` with `If-None-Match: *`.
6. If another first save wins, the loser receives HTTP 409 and the current
   state. The client never retries or overwrites automatically.
7. Once a current revision exists, manifest seed changes have no effect on
   that widget's state.

## S3 persistence model

The server derives the root from an ACL-validated dashboard identity:

```text
users/{owner}/dashboards/{dashboard_id}/user_input/
└─ widgets/
   └─ {widget_id}/
      ├─ current.json
      ├─ revisions/
      │  └─ {revision_id}.json
      ├─ files/
      │  └─ {file_id}/
      │     ├─ blob
      │     └─ metadata.json
      └─ tombstones/
         └─ {file_id}/
            └─ {revision_id}.json
```

`owner`, `dashboard_id`, `widget_id`, `revision_id`, and `file_id` are
validated identifiers. User filenames never appear in an S3 key.

### Current pointer

`current.json` is the only mutable object:

```json
{
  "schema_version": 1,
  "owner": "owner",
  "dashboard_id": "chief_of_staff",
  "widget_id": "weekend_notes",
  "mode": "text",
  "revision_id": "aa746ec3-a6b0-44d4-8f67-39d97d86d345",
  "revision_key": "users/owner/dashboards/chief_of_staff/user_input/widgets/weekend_notes/revisions/aa746ec3-a6b0-44d4-8f67-39d97d86d345.json",
  "content_sha256": "64 lowercase hexadecimal characters",
  "updated_at": "2026-07-20T03:30:00.000000Z",
  "updated_by": "owner"
}
```

The S3 ETag is used only inside the server's conditional write. It is not a
public concurrency token.

### Immutable revision

```json
{
  "schema_version": 1,
  "owner": "owner",
  "dashboard_id": "chief_of_staff",
  "widget_id": "weekend_notes",
  "mode": "text",
  "revision_id": "aa746ec3-a6b0-44d4-8f67-39d97d86d345",
  "parent_revision_id": null,
  "created_at": "2026-07-20T03:30:00.000000Z",
  "created_by": "owner",
  "content_sha256": "64 lowercase hexadecimal characters",
  "content": {"text": "User-authored plain text"}
}
```

Revision ids and file ids are server-generated UUID4 strings. A revision key
is written with `If-None-Match: *` and is never overwritten or deleted.
`content_sha256` is SHA-256 over UTF-8 canonical JSON produced with sorted
keys, compact separators, and `ensure_ascii=False`.

### File metadata and binary

`files/{file_id}/blob` contains the exact accepted bytes and is written once.
`files/{file_id}/metadata.json` is immutable:

```json
{
  "schema_version": 1,
  "owner": "owner",
  "dashboard_id": "chief_of_staff",
  "widget_id": "knowledge_drop",
  "file_id": "3f75f764-2e4c-4789-841c-b700a812db46",
  "original_filename": "Weekend Reading.pdf",
  "normalized_filename": "Weekend Reading.pdf",
  "object_key": "users/owner/dashboards/chief_of_staff/user_input/widgets/knowledge_drop/files/3f75f764-2e4c-4789-841c-b700a812db46/blob",
  "size_bytes": 184239,
  "sha256": "64 lowercase hexadecimal characters",
  "detected_mime": "application/pdf",
  "uploaded_at": "2026-07-20T03:30:00.000000Z",
  "uploaded_by": "owner"
}
```

Removing a file from the active list creates an immutable tombstone before
the pointer swap:

```json
{
  "schema_version": 1,
  "file_id": "3f75f764-2e4c-4789-841c-b700a812db46",
  "removed_in_revision_id": "59ef82ad-e003-4c2d-b3bd-b2071f70e9ab",
  "removed_at": "2026-07-20T04:00:00.000000Z",
  "removed_by": "owner",
  "reason": "removed_from_active_state"
}
```

The blob and metadata remain immutable. Normal GET and download resolve only
the current active file list, so a tombstoned file is not downloadable.

### Conditional write sequence

Every state mutation follows this sequence:

```text
read current pointer + ETag
        │
        ├─ expected_revision_id mismatch ───────────────► HTTP 409
        │
        ▼
validate canonical content and create revision id
        │
        ├─ upload: write immutable blob + metadata
        ├─ removal: write immutable tombstone(s)
        ▼
write immutable revision with If-None-Match: *
        ▼
conditionally create/swap current.json
        ├─ first revision: If-None-Match: *
        └─ existing revision: If-Match: previously read pointer ETag
                │
                ├─ precondition failure ────────────────► HTTP 409
                ▼
             success
```

A losing write may leave an unlinked immutable revision or upload object.
Readers follow only `current.json` and its parent chain, so unlinked attempts
are never exposed as current history. The implementation must record these
objects for lifecycle cleanup; it must not treat them as successful saves.

## HTTP API

All endpoints require authenticated Django sessions and the normal CSRF
contract for POST. JSON responses use UTF-8 and `Cache-Control: no-store`.

### Error envelope

```json
{
  "ok": false,
  "error": {
    "code": "revision_conflict",
    "message": "This input changed after it was loaded.",
    "details": {}
  }
}
```

The server never returns a successful HTTP status with `ok: false`.

| Status | Code | Meaning |
|---:|---|---|
| 400 | `invalid_request` | Malformed query, JSON, multipart body, or identifier |
| 401 | `authentication_required` | No authenticated viewer |
| 403 | `dashboard_read_forbidden` / `dashboard_write_forbidden` | ACL denial |
| 404 | `dashboard_not_found` / `widget_not_found` / `file_not_found` | Valid identity but missing object |
| 409 | `revision_conflict` | Expected revision or conditional pointer write lost |
| 413 | `file_too_large` | More than 25,000,000 bytes |
| 415 | `unsupported_file_type` / `content_type_mismatch` | Extension or inspected content rejected |
| 422 | `invalid_content` | Mode-specific content fails validation |
| 500 | `persistence_error` | Server could not complete a safe persistence operation |
| 503 | `persistence_unavailable` | S3 or required inspection service unavailable |

### GET state

```http
GET /api/dashboard/user-input/?owner=owner&dashboard_id=chief_of_staff
GET /api/dashboard/user-input/?owner=owner&dashboard_id=chief_of_staff&widget_id=weekend_notes
```

`owner` and `dashboard_id` are identifiers, never paths. The server resolves
the canonical dashboard, checks its current read ACL, reads the current
manifest, and considers only manifest-declared `user_input` widgets.

Response:

```json
{
  "ok": true,
  "dashboard": {"owner": "owner", "dashboard_id": "chief_of_staff"},
  "can_write": true,
  "widgets": {
    "weekend_notes": {
      "widget_id": "weekend_notes",
      "mode": "text",
      "source": "persisted",
      "revision_id": "aa746ec3-a6b0-44d4-8f67-39d97d86d345",
      "parent_revision_id": null,
      "updated_at": "2026-07-20T03:30:00.000000Z",
      "updated_by": "owner",
      "content": {"text": "User-authored plain text"}
    }
  }
}
```

`source` is `"seed"` only when no current pointer exists; in that case
`revision_id`, `parent_revision_id`, `updated_at`, and `updated_by` are null.
A viewer receives the same shared state as the owner with `can_write: false`.

### Save text or checklist state

```http
POST /api/dashboard/user-input/save/
Content-Type: application/json
X-CSRFToken: <token>
```

```json
{
  "owner": "owner",
  "dashboard_id": "chief_of_staff",
  "widget_id": "weekend_notes",
  "mode": "text",
  "expected_revision_id": "aa746ec3-a6b0-44d4-8f67-39d97d86d345",
  "content": {"text": "Updated text"}
}
```

First save uses `expected_revision_id: null`. `mode` must equal the current
manifest definition. Success is HTTP 200 and returns:

```json
{
  "ok": true,
  "can_write": true,
  "widget": {
    "widget_id": "weekend_notes",
    "mode": "text",
    "source": "persisted",
    "revision_id": "59ef82ad-e003-4c2d-b3bd-b2071f70e9ab",
    "parent_revision_id": "aa746ec3-a6b0-44d4-8f67-39d97d86d345",
    "updated_at": "2026-07-20T04:00:00.000000Z",
    "updated_by": "owner",
    "content": {"text": "Updated text"}
  }
}
```

For `files` mode, the same endpoint accepts only:

```json
{
  "owner": "owner",
  "dashboard_id": "chief_of_staff",
  "widget_id": "knowledge_drop",
  "mode": "files",
  "expected_revision_id": "current revision or null",
  "content": {
    "active_file_ids": [
      "3f75f764-2e4c-4789-841c-b700a812db46"
    ]
  }
}
```

Every id must already belong to that widget. Omitting a currently active id
creates its tombstone. The endpoint cannot introduce a file id or object key.

Conflict is HTTP 409 and includes the authoritative current widget:

```json
{
  "ok": false,
  "error": {
    "code": "revision_conflict",
    "message": "This input changed after it was loaded.",
    "details": {
      "expected_revision_id": "stale revision",
      "current_revision_id": "current revision",
      "current_widget": {}
    }
  }
}
```

### Upload one file

```http
POST /api/dashboard/user-input/upload/
Content-Type: multipart/form-data
X-CSRFToken: <token>

owner=owner
dashboard_id=chief_of_staff
widget_id=knowledge_drop
mode=files
expected_revision_id=<current revision or empty for first save>
file=<one binary part>
```

Exactly one `file` part is accepted. The server streams while hashing and
aborts once byte 25,000,001 is observed. It does not trust browser MIME.
Success is HTTP 201 and returns the same `widget` envelope as save, with the
new file appended to `content.files`.

### Download one active file

```http
GET /api/dashboard/user-input/download/?owner=owner&dashboard_id=chief_of_staff&widget_id=knowledge_drop&file_id=3f75f764-2e4c-4789-841c-b700a812db46
```

The server rechecks dashboard read ACL and the current active file list before
opening the object. Success streams bytes with:

```text
Content-Type: <server-detected MIME>
Content-Disposition: attachment; filename="<ASCII-safe name>";
                     filename*=UTF-8''<RFC 5987 encoded normalized name>
X-Content-Type-Options: nosniff
Cache-Control: private, no-store
Content-Length: <exact bytes>
```

The response never renders uploaded content inline.

## File policy

The extension and inspected content must agree.

| Extensions | Required inspected type and validation |
|---|---|
| `.pdf` | `application/pdf`; valid PDF signature and parser acceptance |
| `.docx` | OOXML Word package; package content type matches Word |
| `.xlsx` | OOXML Excel package; package content type matches Excel |
| `.pptx` | OOXML PowerPoint package; package content type matches PowerPoint |
| `.txt` | UTF-8, NUL-free text |
| `.md` | UTF-8, NUL-free text; stored/rendered as inert text |
| `.csv` | UTF-8, NUL-free text accepted by the CSV parser |
| `.json` | UTF-8 JSON parsed successfully |
| `.png` | Valid PNG decoded by the image verifier |
| `.jpg`, `.jpeg` | Valid JPEG decoded by the image verifier |
| `.gif` | Valid GIF decoded by the image verifier |
| `.webp` | Valid WebP decoded by the image verifier |
| `.bmp` | Valid BMP decoded by the image verifier |
| `.tif`, `.tiff` | Valid TIFF decoded by the image verifier |

OOXML packages must:

- contain `[Content_Types].xml` with the expected primary document type;
- contain no absolute, parent-traversing, or duplicate normalized member path;
- contain no `vbaProject.bin`, ActiveX, executable, script, HTML, or external
  relationship payload;
- contain no more than 10,000 members and no more than 200,000,000 total
  uncompressed bytes.

Images must pass full decoder verification and contain at most 100,000,000
pixels. Macro-enabled Office formats, legacy compound Office formats, SVG,
HTML, XML, archives, audio/video, executables, installers, scripts, notebooks,
shortcuts, and disk images are blocked.

Filename normalization:

1. Decode as Unicode and normalize to NFC.
2. Take the basename; reject any submitted path component, `/`, `\`, or NUL.
3. Remove ASCII controls, bidi controls, and leading/trailing whitespace.
4. Collapse internal whitespace.
5. Require a non-empty stem and an allowlisted lower-cased extension.
6. Truncate the stem so the complete UTF-8 name is at most 180 bytes.
7. Preserve the verified extension.

An empty or invalid result is rejected; the server does not invent a fallback
filename.

## Authorization and trust boundaries

```text
authenticated viewer
        │
        ▼
resolve dashboard from (owner, dashboard_id)
        │
        ├─ no matching canonical registry/detail route ─► 404
        ▼
evaluate the same dashboard read ACL used by the detail page
        │
        ├─ denied ──────────────────────────────────────► 403
        ▼
read state / download

write request
        │
        ├─ authenticated Kerberos != canonical owner ──► 403
        ▼
validate widget id and mode against current manifest_template.json
        │
        ├─ missing or changed ──────────────────────────► 404 / 409
        ▼
conditional S3 transaction
```

The server must not:

- accept `folder`, S3 prefix, object key, revision key, or download key from
  the browser;
- authorize from client globals, share booleans, or a claimed owner alone;
- permit a shared viewer, workspace member, department viewer, public viewer,
  or link-token viewer to write;
- use `@csrf_exempt`;
- reflect user text or filenames through `innerHTML`;
- log file bytes, note text, checklist text, CSRF tokens, or signed URLs.

All user text and filenames are rendered with DOM text nodes or form values.
The CSP remains unchanged. Download remains attachment-only with `nosniff`.

## Browser controller

The compiled payload receives manifest definitions only:

```json
{
  "userInputs": {
    "weekend_notes": {
      "widget_id": "weekend_notes",
      "mode": "text",
      "seed": {"text": ""},
      "placeholder": "Write a note…",
      "rows": 10
    }
  }
}
```

The controller reads `PRISM_VIEWER`, `PRISM_DASHBOARD_AUTHOR`, and
`PRISM_DASHBOARD_ID`, then calls GET. Missing identity or a failed GET enters
`unavailable`; the controls remain read-only and show the error. It does not
read or write `localStorage`, IndexedDB, Cabinet, or S3 directly.

State machine:

```text
          GET
idle ─────────────► loading
                       │
              ┌────────┴────────┐
              ▼                 ▼
            ready          unavailable
              │ edit
              ▼
            dirty
              │ Save / upload
              ▼
            saving
      ┌────────┼───────────┐
      ▼        ▼           ▼
    saved   conflict   unavailable
      │        │
      └─edit──►dirty       └─ explicit Retry GET only
```

`saved` displays the server timestamp and returns to `ready` after a short
visual acknowledgment. `conflict` shows that another save won and offers:

- `Reload current`, which discards local dirty state after confirmation; or
- `Keep editing`, which preserves the local draft but does not save it.

There is no automatic merge, retry, queue, or silent overwrite.

Owner controls:

- text: textarea plus explicit Save;
- checklist: add/edit/remove/reorder/check controls plus explicit Save;
- files: file picker, Upload, download, and remove-from-active-list.

Authorized viewers see the same text/checklist/file list and download links,
with all mutation controls disabled and a `Read only` label.

## Python read helper

The payload exports:

```python
read_dashboard_user_input(
    folder: str,
    widget_id: Optional[str] = None,
    *,
    s3_manager: Any = None,
    include_deleted: bool = False,
) -> Dict[str, Any]
```

Behavior:

- validates canonical `users/{owner}/dashboards/{dashboard_id}`;
- reads only `user_input/widgets/*/current.json` and referenced immutable
  revisions;
- returns `{widget_id: state}` when `widget_id` is omitted, or one state when
  supplied;
- returns `{}` for an absent user-input root or absent requested widget;
- raises on corrupt pointers, missing referenced revisions, hash mismatch,
  identity mismatch, or mode mismatch;
- returns active file metadata with stable `object_key`;
- when `include_deleted=True`, adds tombstoned metadata under
  `deleted_files`; the default excludes it;
- never mutates S3 and never consults Cabinet.

This helper is for trusted Prism-side analysis. Browser authorization remains
the Django API's responsibility.

## `prism-main` implementation targets

The Prism developer should implement the server side in the parent checkout,
without editing payload behavior there:

| Target | Required work |
|---|---|
| `prism-main/web/backend_django/news/dashboard_user_input.py` | State service, serializers, ACL gates, conditional S3 operations, upload inspectors, and Django views |
| `prism-main/web/backend_django/news/urls.py` | Register the four exact routes |
| `prism-main/web/backend_django/news/views.py` | Reuse the dashboard-detail identity/ACL helper and ensure author/id globals are injected; do not duplicate policy |
| `prism-main/web/backend_django/news/tests/` | Unit and Django client tests listed below |
| production S3 wrapper | Expose conditional put with `If-Match` and `If-None-Match`; do not emulate it with read-then-unconditional-put |
| request/upload settings | Permit multipart overhead above 25,000,000 bytes while retaining the application-level streaming limit |

The module should split policy from transport:

```text
views
├─ parse request + CSRF/session
├─ resolve canonical dashboard + ACL
└─ call service
   ├─ manifest widget resolver
   ├─ content validators
   ├─ upload inspector
   ├─ revision repository
   └─ response serializer
```

The Django implementation must match the payload constants and local parity
harness byte-for-byte for endpoint paths, field names, status codes, and
error codes.

## Prism developer acceptance tests

### Manifest and identity

1. GET returns only manifest-declared `user_input` widgets.
2. A widget id with `/`, `\`, `..`, percent-encoded traversal, control
   characters, or more than 128 characters is rejected before S3 access.
3. Raw `folder`, object-key, and revision-key parameters are rejected.
4. A current pointer whose owner/dashboard/widget does not equal the
   server-derived identity fails with `persistence_error`.
5. A manifest mode change causes stale-mode saves to return 409.

### ACL and CSRF

1. Owner GET/save/upload/download succeeds.
2. Every viewer accepted by the dashboard detail ACL can GET and download.
3. The same non-owner receives 403 on save and upload.
4. An unauthorized viewer receives 403 before existence-sensitive state is
   disclosed.
5. Unauthenticated requests receive 401.
6. POST without a valid CSRF token is rejected by Django.
7. Link/share parameters alone never grant writes.

### Revision safety

1. First save with expected null creates revision plus pointer.
2. A second first save loses with 409 and does not change the pointer.
3. Save at current revision creates one child with exact parent id.
4. Save at stale revision returns 409 and current state.
5. Two workers racing on the same ETag produce one success and one 409.
6. Every successful pointer references an existing immutable revision whose
   hash verifies.
7. Prior revision, file metadata, and blob bytes remain unchanged.
8. A simulated pointer-write failure returns 500/503 and does not report
   success.
9. Refresh/build leaves the complete `user_input/` subtree byte-identical.

### Mode validation

1. Text round-trips Unicode and newlines exactly.
2. Text over 250,000 UTF-8 bytes returns 422.
3. Checklist add/edit/reorder/check/remove round-trips exact list order.
4. Duplicate checklist ids, invalid ids, non-boolean `checked`, empty text,
   overlong text, and item 501 return 422.
5. A request mode differing from the current manifest returns 409.
6. Files save cannot introduce a file id or move one from another widget.
7. Removing an active file creates a tombstone and preserves blob/metadata.

### Upload policy

1. Each allowlisted extension passes with matching inspected content.
2. Byte 25,000,000 passes; byte 25,000,001 returns 413.
3. Renamed executable, HTML, SVG, script, archive, and MIME mismatch return
   415.
4. Macro-enabled or ActiveX-bearing OOXML returns 415.
5. OOXML traversal, duplicate paths, member-count overflow, and expansion
   overflow return 415.
6. Invalid UTF-8 text, malformed JSON, malformed CSV, corrupt image, and
   image pixel overflow return 415.
7. Filename traversal/control/bidi/empty-stem cases return 400.
8. Stored blob SHA-256, size, MIME, and normalized filename equal metadata.
9. Download streams exact bytes as attachment with `nosniff`.
10. Tombstoned and cross-widget file ids return 404.

### Browser behavior

1. Seed renders without causing a write.
2. Text save survives full reload.
3. Checklist mutation survives full reload.
4. Upload appears, downloads exact bytes, and survives full reload.
5. Light/full dashboard refresh does not mutate or reset input state.
6. Authorized viewer sees current state and disabled controls.
7. Viewer cannot trigger a write by modifying DOM attributes.
8. 409 produces visible conflict state and no automatic retry.
9. 403/503 produces visible unavailable state.
10. No text, checklist item, filename, or download URL is inserted with
    `innerHTML` or persisted in browser storage.

## Composer component snapshots

`user_input` participates in the neutral dashboard widget snapshot API, but
the browser is not authoritative for persisted content. Its client snapshot
contains only the rendered mode, load phase, revision id, content hash, and
bounded display metadata. File mode contains metadata and references only;
binary bytes are never serialized into the component snapshot.

When a `user_input` component is sent through Composer, `prism-main` must:

1. resolve the dashboard and widget from the authenticated Kerberos identity;
2. validate that the client snapshot id, kind, mode, and schema match;
3. call `read_dashboard_user_input(...)` against the server-derived folder;
4. use the server-returned text, checklist, or active file metadata in the
   prompt;
5. treat the client revision/hash as comparison evidence and state any
   mismatch explicitly;
6. preserve authorized file `object_key` references and metadata without
   fetching or embedding binary bytes.

Missing or invalid component snapshots fail the Composer POST. There is no
canonical-only or client-content fallback. The canonical artifact-info GET
remains a small preview and does not carry persisted input content.

## Non-goals

- Per-viewer private notes;
- collaborative live editing or automatic merges;
- direct browser-to-S3 uploads;
- Cabinet storage or fallback reads;
- localStorage/IndexedDB offline queues;
- inline rendering or execution of uploaded files;
- editing persisted state through manifest operations;
- implicit migration when a widget or dashboard id changes;
- Prism-side server code authored from this staging repository.
